// Content script for Job Apply AI Assistant
// Supports: Cover letters, Screening questions, and Form Autofill (Greenhouse, Lever, DOU, Djinni, etc.)

(() => {
  const PROCESSED_ATTR = "data-job-ai-attached";

  // Standard personal / contact fields that should NEVER receive AI generation buttons
  const EXCLUDED_FIELD_KEYWORDS = [
    "first name", "first_name", "firstname", "given name", "forename", "имя", "ім'я",
    "last name", "last_name", "lastname", "family name", "surname", "фамилия", "прізвище",
    "full name", "fullname", "полное имя", "фио",
    "email", "e-mail", "почта", "пошта",
    "phone", "mobile", "tel", "telephone", "телефон",
    "resume", "cv", "резюме", "attach", "upload", "file",
    "address", "city", "location", "country", "state", "postal", "zip", "город", "місто", "адрес",
    "linkedin", "github", "portfolio", "website", "url", "link", "social",
    "salary", "зарплата", "compensation",
    "hear about", "how did you hear", "source", "referred", "referral"
  ];

  // Observe DOM for dynamic forms (SPA navigation, modal dialogs)
  let scanTimeout = null;
  const observer = new MutationObserver(() => {
    if (scanTimeout) clearTimeout(scanTimeout);
    scanTimeout = setTimeout(scanAndInject, 300);
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Initial scans
  setTimeout(scanAndInject, 500);
  setTimeout(scanAndInject, 1500);
  setTimeout(scanAndInject, 3000);

  function scanAndInject() {
    const fields = findApplicationFields();

    for (const field of fields) {
      const anchor = field.anchor;
      if (anchor.hasAttribute(PROCESSED_ATTR)) continue;
      anchor.setAttribute(PROCESSED_ATTR, "true");
      injectFieldToolbar(field);
    }

    // If multiple questionnaire fields are detected on page, inject a top banner
    if (fields.length >= 2 || isGreenhousePage()) {
      injectTopFormBanner(fields);
    }
  }

  function isGreenhousePage() {
    return (
      window.location.hostname.includes("greenhouse.io") ||
      Boolean(document.querySelector("#application_form, .application-form, form[action*='greenhouse']"))
    );
  }

  /**
   * Identifies all application inputs & textareas
   */
  function findApplicationFields() {
    const results = [];
    const hostname = window.location.hostname;

    // ─── 1. All visible <textarea> elements (Essay questions / Cover letter) ───
    const allTextareas = document.querySelectorAll("textarea");
    for (const ta of allTextareas) {
      if (ta.classList.contains("hidden") || ta.style.display === "none") continue;
      if (ta.offsetParent === null && ta.offsetHeight === 0) continue;
      if (ta.offsetWidth < 80 && ta.offsetHeight < 25) continue;

      const qContext = extractQuestionContext(ta);
      const fieldType = classifyFieldType(qContext, ta, hostname);

      // Do NOT attach to blacklisted personal fields
      if (!fieldType || fieldType === "excluded_personal") continue;

      results.push({
        type: "textarea",
        fieldType,
        questionText: qContext,
        anchor: ta,
        textarea: ta,
        inputEl: ta,
        editableEl: null,
        container: ta.parentElement
      });
    }

    // ─── 2. Single-line <input> fields ONLY for degree_result or school_rationale ───
    // NEVER attach to generic input[type="text"] (First Name, Email, etc.)
    const allInputs = document.querySelectorAll(
      'input[type="text"]:not([data-job-ai-attached]), input:not([type]):not([data-job-ai-attached])'
    );
    for (const inp of allInputs) {
      if (inp.classList.contains("hidden") || inp.style.display === "none") continue;
      if (inp.offsetParent === null && inp.offsetHeight === 0) continue;

      const qContext = extractQuestionContext(inp);
      const fieldType = classifyFieldType(qContext, inp, hostname);

      // STRICT CHECK: For single-line inputs, ONLY attach if it's explicitly degree_result or school_rationale
      if (fieldType === "degree_result" || fieldType === "school_rationale") {
        results.push({
          type: "input",
          fieldType,
          questionText: qContext,
          anchor: inp,
          textarea: null,
          inputEl: inp,
          editableEl: null,
          container: inp.parentElement
        });
      }
    }

    // ─── 3. Rich-text editors (contenteditable divs) ───
    const richTextContainers = document.querySelectorAll(
      '[data-controller="forms--rich-text-component"], ' +
      '.rich-text-component, ' +
      '[data-controller*="rich-text"]'
    );
    for (const container of richTextContainers) {
      const hiddenTa = container.querySelector("textarea");
      const editable = container.querySelector('[contenteditable="true"], .fr-element, .fr-view, .ql-editor, .ProseMirror, [role="textbox"]');
      if (!editable && !hiddenTa) continue;

      const qContext = extractQuestionContext(container);
      const fieldType = classifyFieldType(qContext, container, hostname);

      if (!fieldType || fieldType === "excluded_personal") continue;

      results.push({
        type: "richtext",
        fieldType,
        questionText: qContext,
        anchor: container,
        textarea: hiddenTa,
        inputEl: null,
        editableEl: editable,
        container: container
      });
    }

    return results;
  }

  /**
   * Extracts question or prompt text associated with an element
   */
  function extractQuestionContext(el) {
    let text = "";

    // 1. Native HTML labels
    if (el.labels && el.labels.length > 0) {
      text = Array.from(el.labels).map(l => l.innerText).join(" ");
    }

    // 2. Explicit label[for="id"]
    if (!text && el.id) {
      const labelEl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (labelEl) text = labelEl.innerText;
    }

    // 3. Parent / wrapper label
    if (!text) {
      const fieldWrapper = el.closest(".field, .form-group, .form-field, .application-question, [class*='question'], [class*='field']");
      if (fieldWrapper) {
        const labelEl = fieldWrapper.querySelector("label, .label, legend, h3, h4, strong");
        if (labelEl && labelEl !== el) {
          text = labelEl.innerText;
        } else {
          // Fallback to wrapper text before the input
          text = fieldWrapper.innerText.substring(0, 300);
        }
      }
    }

    // 4. Preceding sibling
    if (!text && el.previousElementSibling) {
      text = el.previousElementSibling.innerText || "";
    }

    // 5. Attributes (placeholder, aria-label)
    if (!text) {
      text = el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.name || "";
    }

    return text.replace(/\s+/g, " ").trim();
  }

  /**
   * Classify field into cover_letter, degree_result, school_rationale, or screening_question
   */
  function classifyFieldType(qContext, el, hostname) {
    const qLower = (qContext || "").toLowerCase();
    const idOrName = ((el.name || "") + " " + (el.id || "")).toLowerCase();
    const combined = qLower + " " + idOrName;

    // Check blacklist first
    if (EXCLUDED_FIELD_KEYWORDS.some(kw => combined.includes(kw))) {
      return "excluded_personal";
    }

    // 1. Degree result / GPA question
    if (
      combined.includes("degree result") ||
      combined.includes("expected result") ||
      combined.includes("bachelor's university degree") ||
      combined.includes("bachelor's degree") ||
      combined.includes("gpa score") ||
      combined.includes("grading system")
    ) {
      return "degree_result";
    }

    // 2. High school rationale / evidence
    if (
      combined.includes("high school performance") ||
      combined.includes("rationale or evidence") ||
      combined.includes("high school selections") ||
      combined.includes("sat or act scores")
    ) {
      return "school_rationale";
    }

    // 3. Cover letter / General application message
    const coverKeywords = [
      "cover letter", "cover_letter", "сопроводительное", "супровідн",
      "напишите немного о себе", "чому вакансія вам підходить",
      "почему вакансия вам подходит", "letter of motivation", "motivation letter"
    ];
    if (coverKeywords.some(k => combined.includes(k))) {
      return "cover_letter";
    }

    // DOU or Djinni reply fields
    if (hostname.includes("dou.ua") && (el.name === "message" || el.id?.includes("message") || el.closest(".reply, #reply-form"))) {
      return "cover_letter";
    }
    if (hostname.includes("djinni.co") && (el.name === "message" || el.closest(".inbox-thread--reply-form"))) {
      return "cover_letter";
    }

    // 4. Any other application textarea
    if (el.tagName === "TEXTAREA" || el.getAttribute("contenteditable") === "true") {
      return "screening_question";
    }

    return null;
  }

  function extractJobDetails() {
    let title = "";
    let company = "";
    let description = "";

    const hostname = window.location.hostname;

    if (hostname.includes("greenhouse.io")) {
      title = document.querySelector(".app-title, h1.app-title, h1")?.innerText?.trim() || "";
      company = document.querySelector(".company-name, [class*='company']")?.innerText?.trim() || "";
      const descEl = document.querySelector("#content, .body, #job-post, [class*='description']");
      description = descEl ? descEl.innerText.trim() : "";
    } else if (hostname.includes("dou.ua")) {
      title = document.querySelector(".b-vacancy h1.g-h2, h1.g-h2, h1")?.innerText?.trim() || "";
      company = document.querySelector(".b-vacancy .info .l-n a, .company a")?.innerText?.trim() || "";
      const descEl = document.querySelector(".b-typo.vacancy-section, .vacancy-section, .b-vacancy");
      description = descEl ? descEl.innerText.trim() : "";
    } else if (hostname.includes("djinni.co")) {
      title = document.querySelector("h1")?.innerText?.trim() || "";
      company = document.querySelector(".job-details--title, .company-name")?.innerText?.trim() || "";
      description = document.querySelector(".job-description")?.innerText?.trim() || "";
    } else if (hostname.includes("linkedin.com")) {
      title = document.querySelector(".job-details-jobs-unified-top-card__job-title, h1")?.innerText?.trim() || "";
      company = document.querySelector(".job-details-jobs-unified-top-card__company-name")?.innerText?.trim() || "";
      description = document.querySelector(".jobs-description, #job-details")?.innerText?.trim() || "";
    } else {
      title = document.querySelector("h1")?.innerText?.trim() || document.title || "";
      const main = document.querySelector("main, article, #content") || document.body;
      description = main.innerText.substring(0, 3500);
    }

    return {
      title: title.replace(/\s+/g, " "),
      company: company.replace(/\s+/g, " "),
      description: description.substring(0, 4000)
    };
  }

  function writeToField(field, text) {
    if (field.inputEl) {
      field.inputEl.value = text;
      field.inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      field.inputEl.dispatchEvent(new Event("change", { bubbles: true }));

      // If it's a textarea, auto-expand
      if (field.inputEl.tagName === "TEXTAREA") {
        field.inputEl.dispatchEvent(new Event("autosize:update", { bubbles: true }));
        field.inputEl.style.setProperty("min-height", "140px", "important");
        const targetHeight = Math.min(Math.max(field.inputEl.scrollHeight + 20, 140), 500);
        field.inputEl.style.setProperty("height", `${targetHeight}px`, "important");
      }
    }

    if (field.type === "richtext" && field.editableEl) {
      const htmlContent = text
        .split("\n\n")
        .map(p => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
        .join("");

      field.editableEl.innerHTML = htmlContent;
      field.editableEl.dispatchEvent(new Event("input", { bubbles: true }));
      field.editableEl.dispatchEvent(new Event("change", { bubbles: true }));
      field.editableEl.dispatchEvent(new Event("blur", { bubbles: true }));
      field.editableEl.dispatchEvent(new Event("focus", { bubbles: true }));

      if (field.textarea) {
        field.textarea.value = text;
        field.textarea.dispatchEvent(new Event("input", { bubbles: true }));
        field.textarea.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
  }

  function injectFieldToolbar(field) {
    const container = document.createElement("div");
    container.className = "job-ai-container";

    const isCover = field.fieldType === "cover_letter";
    const isDegree = field.fieldType === "degree_result";
    const isSchool = field.fieldType === "school_rationale";

    let btnLabel = isCover ? "✨ Написать Cover Letter" : "✨ Ответить на вопрос с AI";
    let quickFillBtn = "";

    if (isDegree) {
      quickFillBtn = `<button type="button" class="job-ai-btn-quickfill" data-action="fill-degree">⚡ Вставить диплом и GPA</button>`;
    } else if (isSchool) {
      quickFillBtn = `<button type="button" class="job-ai-btn-quickfill" data-action="fill-school">⚡ Вставить обоснование оценок</button>`;
    }

    let questionBadge = "";
    if (!isCover && field.questionText) {
      const shortQ = field.questionText.length > 50 ? field.questionText.substring(0, 47) + "..." : field.questionText;
      questionBadge = `<span class="job-ai-question-pill" title="${escapeHtml(field.questionText)}">❓ ${escapeHtml(shortQ)}</span>`;
    }

    container.innerHTML = `
      <div class="job-ai-bar">
        <div class="job-ai-left">
          <button type="button" class="job-ai-btn-generate">
            <span class="job-ai-btn-text">${btnLabel}</span>
          </button>
          ${quickFillBtn}
          ${questionBadge}
          <button type="button" class="job-ai-btn-settings" title="Настройки">⚙️</button>
        </div>
        <div class="job-ai-status"></div>
      </div>
      <div class="job-ai-modal" style="display: none;"></div>
    `;

    // Insert before the anchor element
    field.anchor.parentNode.insertBefore(container, field.anchor);

    const btnGenerate = container.querySelector(".job-ai-btn-generate");
    const btnText = container.querySelector(".job-ai-btn-text");
    const btnSettings = container.querySelector(".job-ai-btn-settings");
    const statusEl = container.querySelector(".job-ai-status");
    const modalEl = container.querySelector(".job-ai-modal");
    const btnQuickFill = container.querySelector(".job-ai-btn-quickfill");

    // Quickfill click
    if (btnQuickFill) {
      btnQuickFill.addEventListener("click", async () => {
        const stored = await chrome.storage.sync.get(["degreeResult", "schoolRationale"]);
        if (isDegree) {
          const val = stored.degreeResult || "Bachelor of Engineering (B.E.) in Computer Science, NTUU KPI. Result: 4.8 out of 5.0 (Equivalent to First-Class Honours / Top 5% of class).";
          writeToField(field, val);
          statusEl.className = "job-ai-status success";
          statusEl.textContent = "✅ Диплом вставлен!";
        } else if (isSchool) {
          const val = stored.schoolRationale || "Graduated secondary school with Gold Medal (Certificate of Secondary Education with Distinction / Honours), ranked in top 5% of class. Maintained 5.0/5.0 in Mathematics and Language; participated in regional Olympiads.";
          writeToField(field, val);
          statusEl.className = "job-ai-status success";
          statusEl.textContent = "✅ Обоснование вставлено!";
        }
      });
    }

    btnSettings.addEventListener("click", () => {
      if (modalEl.style.display === "none") {
        modalEl.style.display = "block";
        modalEl.innerHTML = `
          <strong>💡 Настройки расширения:</strong><br>
          Нажмите на иконку расширения <b>Job Apply AI</b> в панели браузера Chrome (значок пазла 🧩 или ✨) для редактирования опыта, диплома или API ключа.
          <br><br>
          <button type="button" class="job-ai-close-modal" style="padding: 3px 8px; font-size: 11px; cursor: pointer; border-radius: 4px; background: #334155; color: white; border: 1px solid #64748b;">Закрыть</button>
        `;
        modalEl.querySelector(".job-ai-close-modal").addEventListener("click", () => {
          modalEl.style.display = "none";
        });
      } else {
        modalEl.style.display = "none";
      }
    });

    btnGenerate.addEventListener("click", async () => {
      const details = extractJobDetails();

      btnGenerate.disabled = true;
      btnText.textContent = isCover ? "Генерирую отклик..." : "Генерирую ответ...";
      statusEl.className = "job-ai-status";
      statusEl.innerHTML = '<span class="job-ai-spinner"></span> Gemini формирует ответ...';
      modalEl.style.display = "none";

      try {
        let response;
        if (isCover) {
          response = await chrome.runtime.sendMessage({
            action: "generate_cover_letter",
            vacancyTitle: details.title,
            company: details.company,
            vacancyText: details.description
          });
        } else {
          response = await chrome.runtime.sendMessage({
            action: "answer_screening_question",
            questionText: field.questionText,
            vacancyTitle: details.title,
            company: details.company,
            vacancyText: details.description
          });
        }

        if (response && response.success) {
          writeToField(field, response.text);

          statusEl.className = "job-ai-status success";
          statusEl.textContent = `✅ Готово! (${response.modelUsed || "Gemini"})`;
          btnText.textContent = "Перегенерировать";
        } else {
          statusEl.className = "job-ai-status error";
          statusEl.textContent = "❌ Ошибка генерации";
          btnText.textContent = "Попробовать снова";

          modalEl.style.display = "block";
          modalEl.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
              <div>
                <strong style="color: #f87171;">Ошибка:</strong> ${escapeHtml(response?.error || "Неизвестная ошибка")}
              </div>
              <button type="button" class="job-ai-close-modal" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px; padding: 0 4px;">✕</button>
            </div>
          `;
          modalEl.querySelector(".job-ai-close-modal")?.addEventListener("click", () => {
            modalEl.style.display = "none";
          });
        }
      } catch (err) {
        statusEl.className = "job-ai-status error";
        statusEl.textContent = "❌ Ошибка расширения";
        btnText.textContent = "Попробовать снова";
        modalEl.style.display = "block";
        modalEl.innerHTML = `<strong>Ошибка:</strong> ${escapeHtml(err.message)}`;
      } finally {
        btnGenerate.disabled = false;
      }
    });
  }

  /**
   * Injects top banner for questionnaires (Greenhouse / Canonical style)
   */
  function injectTopFormBanner(fields) {
    if (document.querySelector(".job-ai-form-banner")) return;

    const form = document.querySelector("#application_form, form, .application-form") || document.body;
    const banner = document.createElement("div");
    banner.className = "job-ai-form-banner";

    banner.innerHTML = `
      <div class="job-ai-form-banner-header">
        <div class="job-ai-form-banner-title">
          <span>✨</span>
          <span>Job Apply AI Assistant — Анкета работодателя</span>
        </div>
      </div>
      <div class="job-ai-form-banner-body">
        <div class="job-ai-form-banner-desc">
          Обнаружена анкета вакансии. Вы можете в 1 клик заполнить стандартные поля (диплом, школу, согласие на поездки).
        </div>
        <div class="job-ai-form-banner-actions">
          <button type="button" class="job-ai-btn-autofill-all">⚡ Автозаполнить стандартные поля</button>
        </div>
      </div>
      <div class="job-ai-banner-status" style="margin-top: 6px; font-size: 12px; font-weight: 500;"></div>
    `;

    form.parentNode.insertBefore(banner, form);

    const btnAutofill = banner.querySelector(".job-ai-btn-autofill-all");
    const statusEl = banner.querySelector(".job-ai-banner-status");

    btnAutofill.addEventListener("click", async () => {
      btnAutofill.disabled = true;
      const count = await autofillCanonicalStandardFields();
      statusEl.style.color = "#4ade80";
      statusEl.textContent = `✅ Заполнено полей: ${count} (Degree, High School, Travel commitment, Agreement). Нажмите ✨ на вопросе по тестированию для генерации ответа по опыту.`;
      setTimeout(() => {
        btnAutofill.disabled = false;
      }, 2000);
    });
  }

  /**
   * Autofills known standard fields on Canonical/Greenhouse forms
   */
  async function autofillCanonicalStandardFields() {
    const stored = await chrome.storage.sync.get([
      "degreeResult",
      "schoolRationale",
      "travelCommitment"
    ]);

    const defaultDegree = "Bachelor of Engineering (B.E.) in Computer Science, National Technical University of Ukraine 'Kyiv Polytechnic Institute' (NTUU KPI). Degree result: 4.8 out of 5.0 (Grading system: 5-point scale where 5 is Excellent / Equivalent to First-Class Honours / Top 5% of class).";
    const defaultSchool = "Graduated secondary school with Gold Medal (Certificate of Secondary Education with Distinction / Honours), ranked in the top 5% of the graduating cohort. Maintained top grades (5.0 / 5.0) in Mathematics, Physics, and native language throughout high school. Regularly participated and placed in municipal and regional mathematics Olympiads.";

    let filledCount = 0;

    // 1. Textareas and inputs
    const allInputs = document.querySelectorAll("input, textarea");
    for (const el of allInputs) {
      const qContext = extractQuestionContext(el).toLowerCase();

      // Degree result
      if (qContext.includes("degree result") || qContext.includes("bachelor's university degree") || qContext.includes("expected result")) {
        el.value = stored.degreeResult || defaultDegree;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        filledCount++;
      }

      // School rationale
      if (qContext.includes("rationale or evidence") || qContext.includes("high school performance selections") || qContext.includes("high school performance")) {
        el.value = stored.schoolRationale || defaultSchool;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        filledCount++;
      }
    }

    // 2. Select dropdowns
    const allSelects = document.querySelectorAll("select");
    for (const sel of allSelects) {
      const qContext = extractQuestionContext(sel).toLowerCase();

      // "During this application process I agree to use only my own words..."
      if (qContext.includes("use only my own words") || qContext.includes("disqualify my application") || qContext.includes("plagiarism")) {
        selectDropdownValue(sel, ["yes", "да", "agree", "true"]);
        filledCount++;
      }

      // Travel commitment (2-4 times a year, 1-2 weeks)
      if (qContext.includes("meet in person 2-4 times") || qContext.includes("international travel") || qContext.includes("commit to this")) {
        selectDropdownValue(sel, ["yes", "да", "agree", "true"]);
        filledCount++;
      }

      // High school mathematics performance
      if (qContext.includes("mathematics at high school") || qContext.includes("math at high school")) {
        selectDropdownValue(sel, ["top 20%", "top 10%", "top 5%", "top"]);
        filledCount++;
      }

      // High school native language performance
      if (qContext.includes("native language at high school") || qContext.includes("language at high school")) {
        selectDropdownValue(sel, ["top 20%", "top 10%", "top 5%", "top"]);
        filledCount++;
      }
    }

    return filledCount;
  }

  function selectDropdownValue(selectEl, matchKeywords) {
    for (const opt of selectEl.options) {
      const optText = (opt.text || "").toLowerCase();
      const optVal = (opt.value || "").toLowerCase();
      if (matchKeywords.some(kw => optText.includes(kw) || optVal === kw)) {
        selectEl.value = opt.value;
        selectEl.dispatchEvent(new Event("change", { bubbles: true }));
        selectEl.dispatchEvent(new Event("input", { bubbles: true }));
        break;
      }
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
  }
})();
