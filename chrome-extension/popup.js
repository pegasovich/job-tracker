// Popup script for Job Apply AI Assistant

const DEFAULT_PROFILE = `Name: Oleg Kryvokobylskyi
Role: QA Automation Engineer / SDET | Python & Cloud Automation (15+ years)
Location: Cahersiveen, Co. Kerry, Ireland | +353 83 395 9693 | pegasovich@gmail.com
Work Authorization: Stamp 4 / EU Work Rights (No Sponsorship Needed); PAYE & B2B Contracting (Umbrella / Ltd); 100% Remote (Worldwide / EMEA / Ireland) or Hybrid (Munster / Kerry Area)
Links: LinkedIn: oleg-kryvokobylskyi | GitHub: pegasovich

SUMMARY:
15+ years of international experience designing, architecting, and scaling end-to-end QA and test automation across Web, Cloud, Distributed Systems, Desktop, and APIs using Python (Playwright, PyTest, Requests) and C# (.NET Core, SpecFlow BDD, Selenium WebDriver, NUnit, XUnit), plus CI/CD (GitHub Actions, Azure DevOps), API validation (REST, GraphQL, Postman, Swagger/OpenAPI), SQL (PostgreSQL, MS SQL, MySQL, Azure SQL, SQLite), and AI-augmented testing (LLM-assisted API test generation, AI log triage/RCA, synthetic GDPR-compliant test data, self-healing locators).

EXPERIENCE:
- Software Testing Engineer (Manual & Automation) — EPAM Systems (Mar 2023 – Sep 2025) | Project: Unified UI (UUI) Framework: Led E2E functional, regression, accessibility, and cross-browser testing for an enterprise open-source UI Design Library; built Python automation/validation scripts for data consistency, component contracts, and GraphQL APIs; mobile web & multi-device cloud farm testing; Agile (30+ devs, 12 QAs).
- Software Testing Engineer (Automation & BDD Focus) — EPAM Systems (Nov 2020 – Mar 2023) | Client: WPP Digital: Architected scalable UI & API automation in C#, .NET Core 3.1, SpecFlow (BDD), Selenium WebDriver; Azure DevOps CI/CD stages; test plans, Gherkin scenarios, REST API testing (Postman, Swagger).
- QA Engineer — EPAM Systems (Feb 2020 – Sep 2020) | Client: Wolters Kluwer: QA migration strategy from VB6 (32-bit) to VB.NET (64-bit), 64-bit MS Office compatibility, MS SQL Server integrity validation suites.
- Software Testing Engineer — EPAM Systems (Sep 2017 – Jan 2020) | Client: Barclays Capital (Tier-1 Investment Banking): APAC Regional Electronic Trading Platforms (Bloomberg, TradeWeb, Yensai); low-latency order execution, Windows Desktop trading terminals, Python & TestComplete server-side verification scripts for real-time market data feeds and algorithmic order flows.
- QA Engineer — GlobalLogic (Feb 2012 – Jun 2017) | Client: Avid Technology: Avid NEXIS enterprise shared storage for broadcast media; Linux (Debian), macOS, Windows Server test labs; Cisco/Force10 10GbE, Fibre Channel, SAN/NAS failover/performance; Python node verification scripts.
- QA Engineer — Quest Software / Vizioncore Inc. (Feb 2008 – Oct 2011): System/functional QA for vOptimizer & VM Backup & Replication; VMware ESXi, vCenter, stress/load testing, Jira, TestRail.

FEATURED PROJECT:
- Automated Job Intelligence & Real-Time Alerting Engine (github.com/pegasovich/job-tracker, Sep 2025 – Present): Python 3.12/3.13, PyTest (mocked APIs, 90%+ coverage), SQLite, GitHub Actions CI/CD, Telegram Bot API, HTTP 429 backoff, multi-stage filtering.

EDUCATION & LANGUAGES:
- B.E. in Computer Science, National Technical University of Ukraine "KPI" (1995 – 2001).
- Languages: English (Professional Working Proficiency), Ukrainian / Russian (Native).`;

const DEFAULT_DEGREE_RESULT = `Bachelor of Engineering (B.E.) in Computer Science, National Technical University of Ukraine "Kyiv Polytechnic Institute" (NTUU KPI). Degree result: 4.8 out of 5.0 (Grading system: 5-point scale where 5 is Excellent / Equivalent to First-Class Honours / Top 5% of class).`;

const DEFAULT_SCHOOL_RATIONALE = `I graduated from secondary school in Ukraine with an above-average academic standing, consistently placing in the top 20–25% (upper quartile) of my graduating cohort. Under the Ukrainian national educational grading system, my Certificate of Complete General Secondary Education reflected strong results across STEM disciplines, achieving an overall GPA of 4.3 out of 5.0 (equivalent to B+ / First-Class standing), with top marks in Mathematics, Physics, and native language.

Furthermore, in the nation-wide state matriculation and entrance examinations (DPA / state testing), my scores in Mathematics and Physics ranked in the upper quartile nationally (top 20%). This above-average performance secured my competitive admission into the selective Bachelor of Science in Computer Science program at the National Technical University of Ukraine "Kyiv Polytechnic Institute" (NTUU KPI) — Ukraine's premier technical university, which admits applicants through a rigorous, high-cut-off national entrance competition.`;

document.addEventListener("DOMContentLoaded", async () => {
  const btnFillCurrentPage = document.getElementById("btn-fill-current-page");
  const autofillStatus = document.getElementById("autofill-status");

  btnFillCurrentPage.addEventListener("click", async () => {
    btnFillCurrentPage.disabled = true;
    autofillStatus.className = "";
    autofillStatus.textContent = "Ищу незаполненные стандартные поля...";

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !/^https?:/.test(tab.url || "")) {
        throw new Error("Откройте страницу с формой заявки и попробуйте снова.");
      }

      // Some job forms are hosted in a cross-origin iframe. Discover its origin
      // in the active page and request only that origin when Chrome requires it.
      const [pageInfo] = await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        func: () => Array.from(document.querySelectorAll("iframe"))
          .map(frame => frame.getAttribute("src"))
          .filter(Boolean)
      });
      const pageOrigin = new URL(tab.url).origin;
      const iframeOrigins = [...new Set((pageInfo?.result || []).flatMap(src => {
        try {
          const frameUrl = new URL(src, tab.url);
          return /^https?:$/.test(frameUrl.protocol) && frameUrl.origin !== pageOrigin
            ? [`${frameUrl.origin}/*`]
            : [];
        } catch (_error) {
          return [];
        }
      }))];
      if (iframeOrigins.length && !(await chrome.permissions.contains({ origins: iframeOrigins }))) {
        autofillStatus.textContent = `Нужен доступ к встроенной форме: ${iframeOrigins.join(", ")}`;
        const granted = await chrome.permissions.request({ origins: iframeOrigins });
        if (!granted) throw new Error("Chrome не разрешил доступ к домену встроенной формы.");
      }

      let injectedFrames;
      try {
        injectedFrames = await chrome.scripting.executeScript({
          target: { tabId: tab.id, allFrames: true },
          files: ["universal-autofill.js"]
        });
      } catch (_error) {
        // If the browser blocks one or more embedded frames, still try the page itself.
        injectedFrames = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["universal-autofill.js"]
        });
      }
      const frameResults = await Promise.all(injectedFrames.map(async frame => {
        try {
          return await chrome.tabs.sendMessage(
            tab.id,
            { action: "job_apply_autofill_contact" },
            { frameId: frame.frameId }
          );
        } catch (_error) {
          return null;
        }
      }));
      const filledCount = frameResults.reduce((total, result) => total + (result?.filledCount || 0), 0);

      autofillStatus.className = filledCount ? "status-ok" : "";
      autofillStatus.textContent = filledCount
        ? `Заполнено полей: ${filledCount}. Проверьте данные перед отправкой.`
        : "Поля не найдены в доступных фреймах. Возможно, сайт использует отдельный защищённый фрейм.";
    } catch (error) {
      autofillStatus.className = "status-err";
      autofillStatus.textContent = error.message || "Не удалось заполнить страницу.";
    } finally {
      btnFillCurrentPage.disabled = false;
    }
  });

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
  const firstNameInput = document.getElementById("first-name");
  const lastNameInput = document.getElementById("last-name");
  const emailInput = document.getElementById("candidate-email");
  const countryInput = document.getElementById("candidate-country");
  const findAddressInput = document.getElementById("candidate-find-address");
  const addressLine1Input = document.getElementById("candidate-address-line1");
  const addressLine2Input = document.getElementById("candidate-address-line2");
  const cityInput = document.getElementById("candidate-city");
  const countyInput = document.getElementById("candidate-county");
  const postcodeInput = document.getElementById("candidate-postcode");
  const otherContactDetailsInput = document.getElementById("candidate-other-contact-details");
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
    "firstName",
    "lastName",
    "candidateEmail",
    "candidateCountry",
    "candidateFindAddress",
    "candidateAddressLine1",
    "candidateAddressLine2",
    "candidateCity",
    "candidateCounty",
    "candidatePostcode",
    "candidateOtherContactDetails",
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

  if (firstNameInput) firstNameInput.value = stored.firstName || "Oleg";
  if (lastNameInput) lastNameInput.value = stored.lastName || "Kryvokobylskyi";
  if (emailInput) emailInput.value = stored.candidateEmail || "pegasovich@gmail.com";
  if (countryInput) countryInput.value = stored.candidateCountry || "Ireland";
  if (findAddressInput) findAddressInput.value = stored.candidateFindAddress || "";
  if (addressLine1Input) addressLine1Input.value = stored.candidateAddressLine1 || "";
  if (addressLine2Input) addressLine2Input.value = stored.candidateAddressLine2 || "";
  if (cityInput) cityInput.value = stored.candidateCity || "Cahersiveen";
  if (countyInput) countyInput.value = stored.candidateCounty || "Kerry";
  if (postcodeInput) postcodeInput.value = stored.candidatePostcode || "";

  degreeResultArea.value = stored.degreeResult || DEFAULT_DEGREE_RESULT;
  schoolRationaleArea.value = stored.schoolRationale || DEFAULT_SCHOOL_RATIONALE;
  locationInput.value = stored.candidateLocation || "Cahersiveen, Co. Kerry, Ireland";
  phoneInput.value = stored.candidatePhone || "+353 83 395 9693";
  linkedinInput.value = stored.candidateLinkedin || "https://www.linkedin.com/in/oleg-kryvokobylskyi/";
  githubInput.value = stored.candidateGithub || "https://github.com/pegasovich";
  if (otherContactDetailsInput) {
    otherContactDetailsInput.value = stored.candidateOtherContactDetails !== undefined
      ? stored.candidateOtherContactDetails
      : `LinkedIn: ${linkedinInput.value}\nGitHub: ${githubInput.value}`;
  }
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
    const firstName = firstNameInput ? firstNameInput.value.trim() : "Oleg";
    const lastName = lastNameInput ? lastNameInput.value.trim() : "Kryvokobylskyi";
    const candidateEmail = emailInput ? emailInput.value.trim() : "pegasovich@gmail.com";
    const candidateCountry = countryInput ? countryInput.value.trim() : "Ireland";
    const candidateFindAddress = findAddressInput ? findAddressInput.value.trim() : "";
    const candidateAddressLine1 = addressLine1Input ? addressLine1Input.value.trim() : "";
    const candidateAddressLine2 = addressLine2Input ? addressLine2Input.value.trim() : "";
    const candidateCity = cityInput ? cityInput.value.trim() : "Cahersiveen";
    const candidateCounty = countyInput ? countyInput.value.trim() : "Kerry";
    const candidatePostcode = postcodeInput ? postcodeInput.value.trim() : "";
    const candidateOtherContactDetails = otherContactDetailsInput ? otherContactDetailsInput.value.trim() : "";
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
        firstName,
        lastName,
        candidateEmail,
        candidateCountry,
        candidateFindAddress,
        candidateAddressLine1,
        candidateAddressLine2,
        candidateCity,
        candidateCounty,
        candidatePostcode,
        candidateOtherContactDetails,
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
