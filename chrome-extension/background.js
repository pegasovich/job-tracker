// Service worker for Job Apply AI Assistant (Gemini)

const DEFAULT_MODEL = "gemini-2.0-flash";
const FALLBACK_MODELS = [
  "gemini-2.0-flash",
  "gemini-1.5-flash",
  "gemini-2.5-flash",
  "gemini-3.8-flash"
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

  if (request.action === "answer_screening_question") {
    handleAnswerScreeningQuestion(request)
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
  const userProfile = params.userProfile || stored.userProfile || "Опытный Senior QA / SDET инженер.";
  const language = params.language || stored.letterLanguage || "auto";
  const tone = params.tone || stored.letterTone || "concise";

  const prompt = buildCoverLetterPrompt({
    vacancyTitle: params.vacancyTitle || "Специалист",
    company: params.company || "",
    vacancyText: params.vacancyText || "",
    userProfile,
    language,
    tone
  });

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

      const isAuthError =
        errLower.includes("api key not valid") ||
        errLower.includes("api_key_invalid") ||
        errLower.includes("permission_denied") ||
        errLower.includes("unauthenticated") ||
        errLower.includes("forbidden");

      if (isAuthError) {
        break;
      }

      console.warn(`[JobApplyAI] Model ${model} encountered: ${err.message}. Trying next fallback model...`);
      continue;
    }
  }

  return {
    success: false,
    error: lastError ? lastError.message : "Не удалось сгенерировать ответ от Gemini API."
  };
}

async function handleAnswerScreeningQuestion(params) {
  const stored = await chrome.storage.sync.get([
    "geminiApiKey",
    "userProfile",
    "geminiModel",
    "letterLanguage",
    "degreeResult",
    "schoolRationale"
  ]);

  const apiKey = (params.apiKey || stored.geminiApiKey || "").trim();
  if (!apiKey) {
    return {
      success: false,
      error: "API ключ Gemini не настроен. Откройте расширение в панели Chrome и введите бесплатный ключ."
    };
  }

  const modelChoice = params.model || stored.geminiModel || DEFAULT_MODEL;
  const userProfile = params.userProfile || stored.userProfile || "";
  const questionText = params.questionText || "";
  const vacancyTitle = params.vacancyTitle || "";
  const company = params.company || "";
  const vacancyText = params.vacancyText || "";
  const language = params.language || stored.letterLanguage || "auto";

  const prompt = buildScreeningQuestionPrompt({
    questionText,
    vacancyTitle,
    company,
    vacancyText,
    userProfile,
    language,
    degreeResult: stored.degreeResult,
    schoolRationale: stored.schoolRationale
  });

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

      const isAuthError =
        errLower.includes("api key not valid") ||
        errLower.includes("api_key_invalid") ||
        errLower.includes("permission_denied") ||
        errLower.includes("unauthenticated") ||
        errLower.includes("forbidden");

      if (isAuthError) {
        break;
      }

      console.warn(`[JobApplyAI] Model ${model} screening error: ${err.message}. Trying next fallback model...`);
      continue;
    }
  }

  return {
    success: false,
    error: lastError ? lastError.message : "Не удалось сгенерировать ответ на вопрос."
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
      temperature: 0.6,
      maxOutputTokens: 2048
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

function buildCoverLetterPrompt({ vacancyTitle, company, vacancyText, userProfile, language, tone }) {
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

  return `Ты — профессиональный IT-карьерный консультант. Твоя задача — составить убедительное, честное и живое сопроводительное письмо (Cover Letter) для отклика на вакансию через веб-форму на сайте.

ДАННЫЕ О КАНДИДАТЕ (ЕДИНСТВЕННЫЙ ИСТОЧНИК ПРАВДЫ):
${userProfile}

ВАКАНСИЯ:
Позиция: ${vacancyTitle}
Компания: ${company || "Не указана"}
Описание и требования:
${vacancyText.substring(0, 4000)}

КРИТИЧЕСКИЕ ПРАВИЛА И СТРАТЕГИЯ ГЕНЕРАЦИИ:
1. ПРАВИЛО ДОСТОВЕРНОСТИ:
   - Строго запрещено приписывать кандидату опыт, стаж, стек или инструменты, которых НЕТ в блоке 'ДАННЫЕ О КАНДИДАТЕ'.
2. СТРАТЕГИЯ ПРИ НЕСОВПАДЕНИИ ТРЕБОВАНИЙ (TRANSFERABLE SKILLS):
   - Если вакансия требует технологии, которых нет в профиле: покажи, как имеющаяся инженерная база (Python, тест-архитектура, API, CI/CD, Linux) позволяет быстро освоить нужный стек.
3. ПРИОРИТЕТ ТОЧНЫХ СОВПАДЕНИЙ:
   - В первую очередь подсвети навыки и инструменты кандидата, которые НАПРЯМУЮ совпадают с требованиями вакансии.
4. ЯЗЫК И СТИЛЬ:
   - ${langInstruction}
   - ${toneInstruction}
   - Пиши живым языком практикующего инженера. Без шаблонных фраз вроде 'я стрессоустойчивый', 'быстро обучаюсь'.
5. ФОРМАТ ВЫВОДА:
   - ВЫВЕДИ ТОЛЬКО ГОТОВЫЙ ТЕКСТ ПИСЬМА для отправки. Без предисловий, без markdown-заголовков (#). Начинай сразу с приветствия.`;
}

function buildScreeningQuestionPrompt({ questionText, vacancyTitle, company, vacancyText, userProfile, language, degreeResult, schoolRationale }) {
  let langInstruction = "Answer strictly in the SAME language the question is written in (if the question is in English, write in English).";
  if (language === "en") langInstruction = "Answer strictly in English.";
  if (language === "uk") langInstruction = "Відповідай суворо українською мовою.";
  if (language === "ru") langInstruction = "Отвечай строго на русском языке.";

  return `You are an experienced Senior QA Automation / SDET Engineer filling out a detailed online job application questionnaire.
The employer (${company || "the company"}, position: "${vacancyTitle}") has asked a specific screening question in the application form.

QUESTION FROM EMPLOYER:
"${questionText}"

CANDIDATE'S PROFILE & REAL EXPERIENCE (SOLE SOURCE OF TRUTH):
${userProfile}

ADDITIONAL CANDIDATE FACTS:
- Education / Degree: ${degreeResult || "Bachelor of Engineering in Computer Science, NTUU KPI"}
- High School Rationale: ${schoolRationale || "High school Gold Medal (Honours), top 5% in mathematics and native language"}

CRITICAL REQUIREMENTS:
1. ANSWER DIRECTLY AND CONCISELY:
   - Do NOT write a cover letter, do NOT add greetings ("Dear Hiring Manager", "Hello") and do NOT add sign-offs ("Best regards", "Sincerely").
   - Jump straight into the direct answer to the exact question asked.
   - Keep it high-impact, factual, and concise (1-3 paragraphs or structured bullet points if summarizing experience/tools).

2. HUMAN ENGINEER VOICE (STRICT ANTI-AI DETECTION):
   - IMPORTANT: The employer uses automated AI-detection software to disqualify AI-generated answers.
   - Speak in the first person ("I have built...", "Over my 15+ years in QA...", "At EPAM, I designed...", "My primary stack is...").
   - FORBIDDEN AI WORDS AND CLICHES: Never use words such as "thrilled", "delve", "testament", "tapestry", "in today's rapidly evolving", "beacon", "furthermore", "spearhead", "foster", "cutting-edge".
   - Write like a pragmatic, battle-tested software engineer describing real hands-on experience, architecture, frameworks, and tools (Python, PyTest, Playwright, API testing, Linux, CI/CD, distributed cloud testing).

3. TRUTHFULNESS:
   - Stick 100% to the candidate's real background. Never fabricate companies, tools, or projects.

4. LANGUAGE:
   - ${langInstruction}

5. OUTPUT FORMAT:
   - Output ONLY the ready-to-paste text of the answer. No quotation marks around the answer, no markdown headers (# or ##), no conversational preamble.`;
}
