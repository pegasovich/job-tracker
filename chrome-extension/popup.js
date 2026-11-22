// Popup script for Job Apply AI Assistant

const DEFAULT_PROFILE = `Имя: Олег Кривокобыльский (Oleg Kryvokobylskyi)
Локация: Cahersiveen, Co. Kerry, Ireland (Full Right to Work in Ireland / No Sponsorship Required)
Контакты: +353 83 395 9693 | pegasovich@gmail.com
Роль: Senior QA Engineer / QA Automation Engineer (SDET)
Опыт: 15+ лет коммерческого опыта в Quality Assurance & Test Automation (Web, Desktop, API, Cloud Distributed Systems).
Компании: EPAM Systems (2017 – 2025, Senior Test Automation Engineer / QA Lead), GlobalLogic (2012 – 2017, Senior QA / Automation).

Ключевые навыки и стек:
- Языки & Фреймворки автоматизации: Python (Playwright, PyTest), C# (.NET, SpecFlow, Selenium WebDriver, NUnit).
- Тестирование API: REST API, Postman, Swagger, Fiddler, GraphQL.
- Базы данных & Инфраструктура: SQL (PostgreSQL, MS SQL, MySQL, Azure SQL), Docker, Kubernetes, Linux (Ubuntu, bash), Windows Server.
- CI/CD & Репозитории: GitHub Actions, Jenkins, Azure DevOps, Git.
- Процессы и домены: FinTech (Investment Banking), Media Technology, Cloud Virtualization, Distributed Systems Testing.
- Образование: Высшее техническое (Bachelor of Engineering in Computer Science, НТУУ 'КПИ' / NTUU KPI, 1995–2001, диплом с отличием / GPA 4.8 из 5.0).
- Английский язык: Professional Working Proficiency (C1 / Full professional communication).
- Готовность к командировкам: Полная готовность к международным командировкам (2-4 недели в год).`;

const DEFAULT_DEGREE_RESULT = `Bachelor of Engineering (B.E.) in Computer Science, National Technical University of Ukraine "Kyiv Polytechnic Institute" (NTUU KPI). Degree result: 4.8 out of 5.0 (Grading system: 5-point scale where 5 is Excellent / Equivalent to First-Class Honours / Top 5% of class).`;

const DEFAULT_SCHOOL_RATIONALE = `Graduated secondary school with Gold Medal (Certificate of Secondary Education with Distinction / Honours), ranked in the top 5% of the graduating cohort. Maintained top grades (5.0 / 5.0) in Mathematics, Physics, and native language throughout high school. Regularly participated and placed in municipal and regional mathematics Olympiads.`;

document.addEventListener("DOMContentLoaded", async () => {
  // Tab switching
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId)?.classList.add("active");
    });
  });

  // Elements
  const apiKeyInput = document.getElementById("api-key");
  const btnToggleKey = document.getElementById("btn-toggle-key");
  const btnTestKey = document.getElementById("btn-test-key");
  const testStatus = document.getElementById("test-status");

  const userProfileArea = document.getElementById("user-profile");
  const btnResetProfile = document.getElementById("btn-reset-profile");

  const letterLangSelect = document.getElementById("letter-lang");
  const letterToneSelect = document.getElementById("letter-tone");
  const geminiModelSelect = document.getElementById("gemini-model");

  const degreeResultArea = document.getElementById("degree-result");
  const schoolRationaleArea = document.getElementById("school-rationale");
  const locationInput = document.getElementById("candidate-location");
  const phoneInput = document.getElementById("candidate-phone");
  const linkedinInput = document.getElementById("candidate-linkedin");
  const githubInput = document.getElementById("candidate-github");
  const travelCommitmentSelect = document.getElementById("travel-commitment");

  const btnSave = document.getElementById("btn-save");
  const saveStatus = document.getElementById("save-status");

  // Load saved settings
  const stored = await chrome.storage.sync.get([
    "geminiApiKey",
    "userProfile",
    "geminiModel",
    "letterLanguage",
    "letterTone",
    "degreeResult",
    "schoolRationale",
    "candidateLocation",
    "candidatePhone",
    "candidateLinkedin",
    "candidateGithub",
    "travelCommitment"
  ]);

  if (stored.geminiApiKey) apiKeyInput.value = stored.geminiApiKey;
  userProfileArea.value = stored.userProfile || DEFAULT_PROFILE;

  if (stored.geminiModel && ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"].includes(stored.geminiModel)) {
    geminiModelSelect.value = stored.geminiModel;
  } else {
    geminiModelSelect.value = "gemini-2.0-flash";
  }

  if (stored.letterLanguage) letterLangSelect.value = stored.letterLanguage;
  if (stored.letterTone) letterToneSelect.value = stored.letterTone;

  degreeResultArea.value = stored.degreeResult || DEFAULT_DEGREE_RESULT;
  schoolRationaleArea.value = stored.schoolRationale || DEFAULT_SCHOOL_RATIONALE;
  locationInput.value = stored.candidateLocation || "Cahersiveen, Co. Kerry, Ireland";
  phoneInput.value = stored.candidatePhone || "+353 83 395 9693";
  linkedinInput.value = stored.candidateLinkedin || "";
  githubInput.value = stored.candidateGithub || "https://github.com/pegasovich";
  if (stored.travelCommitment) travelCommitmentSelect.value = stored.travelCommitment;

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

  // Reset profile to default CV template
  btnResetProfile.addEventListener("click", () => {
    if (confirm("Заполнить данными из вашего резюме (Senior QA / SDET 15+ лет)?")) {
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
    const geminiApiKey = apiKeyInput.value.trim();
    const userProfile = userProfileArea.value.trim();
    const geminiModel = geminiModelSelect.value;
    const letterLanguage = letterLangSelect.value;
    const letterTone = letterToneSelect.value;

    const degreeResult = degreeResultArea.value.trim();
    const schoolRationale = schoolRationaleArea.value.trim();
    const candidateLocation = locationInput.value.trim();
    const candidatePhone = phoneInput.value.trim();
    const candidateLinkedin = linkedinInput.value.trim();
    const candidateGithub = githubInput.value.trim();
    const travelCommitment = travelCommitmentSelect.value;

    btnSave.disabled = true;
    saveStatus.className = "";
    saveStatus.textContent = "Сохранение...";

    try {
      await chrome.storage.sync.set({
        geminiApiKey,
        userProfile,
        geminiModel,
        letterLanguage,
        letterTone,
        degreeResult,
        schoolRationale,
        candidateLocation,
        candidatePhone,
        candidateLinkedin,
        candidateGithub,
        travelCommitment
      });

      saveStatus.className = "status-ok";
      saveStatus.textContent = "✅ Настройки успешно сохранены!";
      setTimeout(() => {
        saveStatus.textContent = "";
      }, 3000);
    } catch (e) {
      saveStatus.className = "status-err";
      saveStatus.textContent = `❌ Ошибка сохранения: ${e.message}`;
    } finally {
      btnSave.disabled = false;
    }
  });
});
