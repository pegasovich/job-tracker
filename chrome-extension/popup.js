// Popup script for Job Apply AI Assistant

const DEFAULT_PROFILE = `Имя: Олег
Специализация: QA Engineer (Manual Mobile & Web QA, базовый Automation)
Опыт: 2+ года коммерческого опыта в тестировании программного обеспечения (iOS, Android, Web).

Ключевые навыки и стек:
- Функциональное, регрессионное, смоук и исследовательское тестирование мобильных приложений (iOS и Android) на реальных девайсах и эмуляторах/симуляторах.
- Анализ требований, составление и актуализация тест-кейсов, чек-листов и баг-репортов.
- Инструменты: Jira, TestRail, Postman (REST API), Charles Proxy / Fiddler (инспекция и подмена трафика).
- Базовый опыт работы с логами и сборками через Android Studio (Logcat, ADB) и Xcode.
- Понимание архитектуры клиент-сервер, базовые знания SQL запросов.
- Практика работы по Agile / Scrum в тесном контакте с разработчиками и дизайнерами.
- Знание основ Python и интерес к автоматизации тестирования.
- Английский язык: B1 (Intermediate) — чтение документации, ведение тасок и коммуникация.`;

document.addEventListener("DOMContentLoaded", async () => {
  const apiKeyInput = document.getElementById("api-key");
  const btnToggleKey = document.getElementById("btn-toggle-key");
  const btnTestKey = document.getElementById("btn-test-key");
  const testStatus = document.getElementById("test-status");

  const userProfileArea = document.getElementById("user-profile");
  const btnResetProfile = document.getElementById("btn-reset-profile");

  const letterLangSelect = document.getElementById("letter-lang");
  const letterToneSelect = document.getElementById("letter-tone");
  const geminiModelSelect = document.getElementById("gemini-model");

  const btnSave = document.getElementById("btn-save");
  const saveStatus = document.getElementById("save-status");

  // Load saved settings
  const stored = await chrome.storage.sync.get([
    "geminiApiKey",
    "userProfile",
    "geminiModel",
    "letterLanguage",
    "letterTone"
  ]);

  if (stored.geminiApiKey) apiKeyInput.value = stored.geminiApiKey;
  userProfileArea.value = stored.userProfile || DEFAULT_PROFILE;
  if (stored.geminiModel && stored.geminiModel !== "gemini-2.5-flash") {
    geminiModelSelect.value = stored.geminiModel;
  } else {
    geminiModelSelect.value = "gemini-3.8-flash";
  }
  if (stored.letterLanguage) letterLangSelect.value = stored.letterLanguage;
  if (stored.letterTone) letterToneSelect.value = stored.letterTone;

  // Toggle API key visibility
  btnToggleKey.addEventListener("click", () => {
    if (apiKeyInput.type === "password") {
      apiKeyInput.type = "text";
      btnToggleKey.textContent = "🔒";
    } else {
      apiKeyInput.type = "password";
      btnToggleKey.textContent = "👁️";
    }
  });

  // Reset profile to default QA template
  btnResetProfile.addEventListener("click", () => {
    if (confirm("Заполнить шаблонными данными для QA Engineer? (Текущий текст будет заменён)")) {
      userProfileArea.value = DEFAULT_PROFILE;
    }
  });

  // Test API Key
  btnTestKey.addEventListener("click", async () => {
    const key = apiKeyInput.value.trim();
    if (!key) {
      testStatus.className = "status-err";
      testStatus.textContent = "⚠️ Сначала введите API ключ.";
      return;
    }

    btnTestKey.disabled = true;
    testStatus.className = "";
    testStatus.textContent = "Проверка ключа...";

    try {
      const response = await chrome.runtime.sendMessage({
        action: "test_gemini_key",
        apiKey: key
      });

      if (response && response.success) {
        testStatus.className = "status-ok";
        testStatus.textContent = "✅ Ключ верный! Gemini API доступен.";
      } else {
        testStatus.className = "status-err";
        testStatus.textContent = `❌ Ошибка: ${response?.error || "Неверный ключ"}`;
      }
    } catch (e) {
      testStatus.className = "status-err";
      testStatus.textContent = `❌ Ошибка запроса: ${e.message}`;
    } finally {
      btnTestKey.disabled = false;
    }
  });

  // Save Settings
  btnSave.addEventListener("click", async () => {
    const dataToSave = {
      geminiApiKey: apiKeyInput.value.trim(),
      userProfile: userProfileArea.value.trim(),
      geminiModel: geminiModelSelect.value,
      letterLanguage: letterLangSelect.value,
      letterTone: letterToneSelect.value
    };

    btnSave.disabled = true;
    saveStatus.textContent = "Сохранение...";

    try {
      await chrome.storage.sync.set(dataToSave);
      saveStatus.className = "status-ok";
      saveStatus.textContent = "✓ Настройки успешно сохранены!";
      setTimeout(() => {
        saveStatus.textContent = "";
      }, 3000);
    } catch (e) {
      // Fallback to local storage if sync fails (e.g. quota limit)
      try {
        await chrome.storage.local.set(dataToSave);
        saveStatus.className = "status-ok";
        saveStatus.textContent = "✓ Настройки сохранены локально!";
        setTimeout(() => {
          saveStatus.textContent = "";
        }, 3000);
      } catch (err) {
        saveStatus.className = "status-err";
        saveStatus.textContent = `❌ Ошибка: ${err.message}`;
      }
    } finally {
      btnSave.disabled = false;
    }
  });
});
