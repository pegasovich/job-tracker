// Service worker for Job Apply AI Assistant (Gemini)

const DEFAULT_MODEL = "gemini-3.8-flash";
const FALLBACK_MODELS = [
  "gemini-3.8-flash",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "gemini-1.5-flash"
];

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "test_gemini_key") {
    handleKeyTest(request.apiKey)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open for async
  }

  if (request.action === "generate_cover_letter") {
    handleGenerateCoverLetter(request)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open for async
  }
});

async function handleKeyTest(apiKey) {
  if (!apiKey || typeof apiKey !== "string" || apiKey.trim().length < 10) {
    return { success: false, error: "Ключ пустой или слишком короткий." };
  }

  const trimmedKey = apiKey.trim();
  const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${trimmedKey}`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      const errorJson = await response.json().catch(() => ({}));
      const msg = errorJson.error?.message || `Ошибка HTTP ${response.status}: ${response.statusText}`;
      return { success: false, error: msg };
    }
    const data = await response.json();
    const flashModels = (data.models || [])
      .filter(m => m.name && m.supportedGenerationMethods?.includes("generateContent"))
      .map(m => m.name.replace("models/", ""));

    return {
      success: true,
      modelsCount: flashModels.length,
      availableModels: flashModels
    };
  } catch (e) {
    return { success: false, error: `Сетевая ошибка: ${e.message}` };
  }
}

async function handleGenerateCoverLetter(params) {
  // 1. Get stored settings
  const stored = await chrome.storage.sync.get([
    "geminiApiKey",
    "userProfile",
    "geminiModel",
    "letterLanguage",
    "letterTone"
  ]);

  const apiKey = (params.apiKey || stored.geminiApiKey || "").trim();
  if (!apiKey) {
    return {
      success: false,
      error: "API ключ Gemini не настроен. Откройте расширение в панели Chrome и введите бесплатный ключ."
    };
  }

  const modelChoice = params.model || stored.geminiModel || DEFAULT_MODEL;
  const userProfile = params.userProfile || stored.userProfile || "Опытный QA Engineer с коммерческим опытом тестирования ПО.";
  const language = params.language || stored.letterLanguage || "auto";
  const tone = params.tone || stored.letterTone || "concise";

  // Build the prompt
  const prompt = buildPrompt({
    vacancyTitle: params.vacancyTitle || "Специалист",
    company: params.company || "",
    vacancyText: params.vacancyText || "",
    userProfile,
    language,
    tone
  });

  // Try generating with preferred model, with automatic fallback
  const modelsToTry = [modelChoice, ...FALLBACK_MODELS.filter(m => m !== modelChoice)];

  let lastError = null;
  for (const model of modelsToTry) {
    try {
      const result = await callGeminiApi(apiKey, model, prompt);
      if (result && result.text) {
        return { success: true, text: result.text, modelUsed: model };
      }
    } catch (err) {
      lastError = err;
      const errLower = (err.message || "").toLowerCase();
      // If error is related to model availability/deprecation/404, try next model
      if (
        errLower.includes("no longer available") ||
        errLower.includes("not available") ||
        errLower.includes("not found") ||
        errLower.includes("404") ||
        errLower.includes("deprecated") ||
        errLower.includes("invalid") ||
        errLower.includes("supported")
      ) {
        continue;
      }
      // If it's another error (e.g. invalid API key quota), break
      break;
    }
  }

  return {
    success: false,
    error: lastError ? lastError.message : "Не удалось сгенерировать ответ от Gemini API."
  };
}

async function callGeminiApi(apiKey, model, prompt) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  const payload = {
    contents: [
      {
        parts: [
          {
            text: prompt
          }
        ]
      }
    ],
    generationConfig: {
      temperature: 0.65,
      maxOutputTokens: 1200
    }
  };

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorJson = await response.json().catch(() => ({}));
    const message = errorJson.error?.message || `HTTP ${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  const data = await response.json();
  const candidate = data.candidates?.[0];
  const replyText = candidate?.content?.parts?.[0]?.text;

  if (!replyText) {
    throw new Error("Gemini вернул пустой ответ.");
  }

  return { text: replyText.trim() };
}

function buildPrompt({ vacancyTitle, company, vacancyText, userProfile, language, tone }) {
  let langInstruction = "";
  if (language === "uk") {
    langInstruction = "Текст отклика должен быть строго на украинском языке.";
  } else if (language === "en") {
    langInstruction = "The cover letter MUST be written in English.";
  } else if (language === "ru") {
    langInstruction = "Текст отклика должен быть на русском языке.";
  } else {
    langInstruction = "Определи язык описания вакансии (украинский, английский или русский) и пиши отклик СТРОГО на том же языке, на котором написана вакансия.";
  }

  let toneInstruction = "";
  if (tone === "detailed") {
    toneInstruction = "Тон: уверенный, профессиональный, подробный. Разбери основные требования вакансии и покажи, как профиль кандидата закрывает задачи работодателя.";
  } else {
    toneInstruction = "Тон: лаконичный, энергичный, строго по делу (3-4 небольших абзаца). Без лишней 'воды' и общих фраз, только конкретные навыки и опыт, релевантные вакансии.";
  }

  return `Ты — профессиональный IT-карьерный консультант. Твоя задача — составить убедительное, честное и живое сопроводительное письмо (Cover Letter) для отклика на вакансию через веб-форму на сайте (поле 'Напишите немного о себе и почему вакансия вам подходит').

ДАННЫЕ О КАНДИДАТЕ (ЕДИНСТВЕННЫЙ ИСТОЧНИК ПРАВДЫ):
${userProfile}

ВАКАНСИЯ:
Позиция: ${vacancyTitle}
Компания: ${company || "Не указана"}
Описание и требования:
${vacancyText.substring(0, 4000)}

КРИТИЧЕСКИЕ ПРАВИЛА И СТРАТЕГИЯ ГЕНЕРАЦИИ:

1. ПРАВИЛО ДОСТОВЕРНОСТИ (НЕ ВРАТЬ И НЕ ПРИДУМЫВАТЬ):
   - Строго запрещено приписывать кандидату опыт, коммерческие годы стажа, стек или инструменты, которых НЕТ в блоке 'ДАННЫЕ О КАНДИДАТЕ'.
   - Кандидат пойдёт на собеседование лично, поэтому каждое утверждение должно соответствовать реальности.

2. СТРАТЕГИЯ ПРИ НЕСОВПАДЕНИИ ТРЕБОВАНИЙ (TRANSFERABLE SKILLS):
   - Если вакансия требует технологии или домен, которых нет в профиле кандидата:
     * НИКОГДА не оправдывайся и не используй слабые фразы ('К сожалению, я не знаю...', 'У меня нет опыта в...').
     * Найди смежные и фундаментальные навыки кандидата (например: общая база тест-дизайна, тестирование API через Postman, работа с клиент-серверной архитектурой, базами данных, логами, процессами Agile).
     * Сделай сильный профессиональный 'мостик': покажи, как имеющаяся инженерная база и схожий опыт позволяют быстро и качественно освоить необходимый стек проекта.

3. ПРИОРИТЕТ ТОЧНЫХ СОВПАДЕНИЙ:
   - В первую очередь подсвети те навыки и инструменты кандидата, которые НАПРЯМУЮ совпадают с требованиями вакансии.

4. ЯЗЫК И СТИЛЬ:
   - ${langInstruction}
   - ${toneInstruction}
   - Никаких шаблонных пустых фраз вроде 'я стрессоустойчивый', 'коммуникабельный', 'быстро обучаюсь'. Пиши как практикующий инженер.
   - Если указана компания (${company}), органично упомяни её.

5. ФОРМАТ ВЫВОДА:
   - ВЫВЕДИ ТОЛЬКО ГОТОВЫЙ ТЕКСТ ПИСЬМА для отправки.
   - Не добавляй никаких предисловий от себя ('Вот текст отклика:', 'Здравствуйте, держите вариант'), не пиши 'Тема:' или markdown-заголовки (#, ##).
   - Начинай сразу с приветствия (например, 'Здравствуйте!' / 'Вітаю!' / 'Hello team!').`;
}
