// Content script for Job Apply AI Assistant
// Supports: plain <textarea>, rich-text editors (Froala, Tiptap, Quill, CKEditor, etc.)

(() => {
  const PROCESSED_ATTR = "data-job-ai-attached";

  // Observe DOM for dynamic forms (e.g. clicking 'Відгукнутися' on DOU, or SPA navigation)
  let scanTimeout = null;
  const observer = new MutationObserver(() => {
    if (scanTimeout) clearTimeout(scanTimeout);
    scanTimeout = setTimeout(scanAndInject, 300);
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Initial scan (with a small delay for SPA hydration)
  setTimeout(scanAndInject, 500);
  setTimeout(scanAndInject, 1500);

  function scanAndInject() {
    const fields = findApplicationFields();
    for (const field of fields) {
      const anchor = field.anchor; // the element we attach the toolbar near
      if (anchor.hasAttribute(PROCESSED_ATTR)) continue;
      anchor.setAttribute(PROCESSED_ATTR, "true");
      injectToolbar(field);
    }
  }

  /**
   * Returns an array of { type, anchor, textarea, editableEl, container }
   *   type: "textarea" | "richtext"
   *   anchor: element to insert the toolbar before
   *   textarea: the <textarea> to write to (may be hidden for richtext)
   *   editableEl: the contenteditable div (for richtext)
   *   container: the wrapper div that contains the whole field
   */
  function findApplicationFields() {
    const results = [];
    const hostname = window.location.hostname;

    // ─── Strategy 1: Plain <textarea> elements ───
    const allTextareas = document.querySelectorAll("textarea");
    for (const ta of allTextareas) {
      // Skip hidden textareas that belong to rich-text editors (we handle those below)
      if (ta.classList.contains("hidden") || ta.style.display === "none") continue;
      if (ta.offsetParent === null && ta.offsetHeight === 0) continue;
      if (ta.offsetWidth < 120 && ta.offsetHeight < 30) continue;

      if (isApplicationField(ta, hostname)) {
        results.push({
          type: "textarea",
          anchor: ta,
          textarea: ta,
          editableEl: null,
          container: ta.parentElement
        });
      }
    }

    // ─── Strategy 2: Rich-text editors (contenteditable divs) ───

    // 2a. PeopleForce: data-controller="forms--rich-text-component"
    const richTextContainers = document.querySelectorAll(
      '[data-controller="forms--rich-text-component"], ' +
      '.rich-text-component, ' +
      '[data-controller*="rich-text"]'
    );
    for (const container of richTextContainers) {
      const hiddenTa = container.querySelector("textarea");
      const editable = container.querySelector('[contenteditable="true"], .fr-element, .fr-view, .ql-editor, .ProseMirror, [role="textbox"]');
      if (!editable && !hiddenTa) continue;

      // Check if this is a cover-letter / message field (not some other rich text)
      const label = findLabelFor(container);
      const labelText = (label?.innerText || "").toLowerCase();
      const idOrName = (hiddenTa?.name || hiddenTa?.id || container.id || "").toLowerCase();
      const combined = labelText + " " + idOrName;

      const coverKeywords = [
        "cover", "letter", "message", "о себе", "про себе", "сопроводительное",
        "супровідн", "отклик", "відгук", "почему", "чому", "motivation"
      ];

      if (coverKeywords.some(k => combined.includes(k))) {
        // Find the best anchor to insert toolbar before
        const anchor = editable || container;
        results.push({
          type: "richtext",
          anchor: container, // insert toolbar before the whole rich-text container
          textarea: hiddenTa,
          editableEl: editable,
          container: container
        });
      }
    }

    // 2b. Generic: any contenteditable div near a "cover letter" label
    if (results.length === 0) {
      const allEditables = document.querySelectorAll(
        '[contenteditable="true"], .fr-element, .ql-editor, .ProseMirror, [role="textbox"]'
      );
      for (const el of allEditables) {
        if (el.hasAttribute(PROCESSED_ATTR)) continue;
        // Walk up to find a label
        const wrapper = el.closest(".form-group, .field, .form-field, [class*=cover], [class*=letter]") || el.parentElement?.parentElement;
        if (!wrapper) continue;
        const label = findLabelFor(wrapper);
        const labelText = (label?.innerText || "").toLowerCase();
        const wrapperText = (wrapper.innerText || "").substring(0, 300).toLowerCase();
        const combined = labelText + " " + wrapperText;

        const keywords = [
          "cover letter", "cover_letter", "message", "о себе", "про себе",
          "сопроводительное", "супровідн", "отклик", "відгук", "motivation"
        ];

        if (keywords.some(k => combined.includes(k))) {
          const hiddenTa = wrapper.querySelector("textarea");
          results.push({
            type: "richtext",
            anchor: el.closest('[data-controller]') || el.parentElement || el,
            textarea: hiddenTa,
            editableEl: el,
            container: wrapper
          });
        }
      }
    }

    return results;
  }

  /** Check if a plain <textarea> is an application/cover-letter field */
  function isApplicationField(ta, hostname) {
    // 1. DOU
    if (hostname.includes("dou.ua")) {
      const inReply = ta.closest(".reply, #reply-form, .b-reply, form");
      const nameOrId = ((ta.name || "") + (ta.id || "")).toLowerCase();
      if (inReply || nameOrId.includes("message") || nameOrId.includes("reply") || nameOrId.includes("comment")) {
        return true;
      }
    }

    // 2. Djinni
    if (hostname.includes("djinni.co")) {
      const inDjinniForm = ta.closest(".inbox-thread--reply-form, form, .lead-response");
      if (inDjinniForm || ta.name === "message") return true;
    }

    // 3. Generic context check
    const parentText = (ta.parentElement?.innerText || "").toLowerCase();
    const grandParentText = (ta.parentElement?.parentElement?.innerText || "").toLowerCase();
    const combined = parentText + " " + grandParentText;

    const keywords = [
      "о себе", "про себе", "сопроводительное", "супровідний",
      "вакансия вам подходит", "чому саме ви", "cover letter",
      "почему вакансия", "отклик", "відгук", "message", "motivation"
    ];

    if (keywords.some(k => combined.includes(k))) return true;

    // 4. Inside a form with a submit button
    const form = ta.closest("form");
    if (form) {
      const formText = form.innerText.toLowerCase();
      if (formText.includes("отправить") || formText.includes("відгукнутися") ||
          formText.includes("apply") || formText.includes("send")) {
        return true;
      }
    }

    return false;
  }

  /** Find a label element associated with a container */
  function findLabelFor(container) {
    // Check for a <label> inside or just before the container
    const labelInside = container.querySelector("label");
    if (labelInside) return labelInside;

    const prev = container.previousElementSibling;
    if (prev && prev.tagName === "LABEL") return prev;

    // Look in parent
    const parent = container.parentElement;
    if (parent) {
      const label = parent.querySelector("label");
      if (label) return label;
    }

    return null;
  }

  function extractJobDetails() {
    let title = "";
    let company = "";
    let description = "";

    const hostname = window.location.hostname;

    if (hostname.includes("dou.ua")) {
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
    } else if (hostname.includes("peopleforce.io")) {
      title = document.querySelector("h1")?.innerText?.trim() || "";
      // Company name is often in header or breadcrumb
      company = document.querySelector(".company-name, .tw-text-lg, header a, [class*=company]")?.innerText?.trim() || "";
      // The job description is on the previous page; on the apply page, grab whatever text is available
      const main = document.querySelector("main, article, .career-page, [class*=career]") || document.body;
      description = main.innerText.substring(0, 3500);
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

  /**
   * Write text into the field (supports both plain textarea and rich-text editors)
   */
  function writeToField(field, text) {
    if (field.type === "textarea" && field.textarea && !field.textarea.classList.contains("hidden")) {
      // Plain textarea
      field.textarea.value = text;
      field.textarea.dispatchEvent(new Event("input", { bubbles: true }));
      field.textarea.dispatchEvent(new Event("change", { bubbles: true }));

      // Auto-resize
      if (field.textarea.scrollHeight > field.textarea.clientHeight) {
        field.textarea.style.height = `${Math.min(field.textarea.scrollHeight + 20, 400)}px`;
      }
    }

    if (field.type === "richtext") {
      // Write into contenteditable div
      if (field.editableEl) {
        // Convert plain text to HTML paragraphs
        const htmlContent = text
          .split("\n\n")
          .map(p => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
          .join("");

        field.editableEl.innerHTML = htmlContent;

        // Trigger events so the framework picks up the change
        field.editableEl.dispatchEvent(new Event("input", { bubbles: true }));
        field.editableEl.dispatchEvent(new Event("change", { bubbles: true }));
        field.editableEl.dispatchEvent(new Event("blur", { bubbles: true }));
        field.editableEl.dispatchEvent(new Event("focus", { bubbles: true }));

        // Also try to dispatch keyup for frameworks that listen to it
        field.editableEl.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true }));
      }

      // Also update the hidden textarea (Froala, etc., sync from it on submit)
      if (field.textarea) {
        field.textarea.value = text;
        field.textarea.innerHTML = text;
        field.textarea.dispatchEvent(new Event("input", { bubbles: true }));
        field.textarea.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
  }

  function injectToolbar(field) {
    const container = document.createElement("div");
    container.className = "job-ai-container";

    container.innerHTML = `
      <div class="job-ai-bar">
        <div class="job-ai-left">
          <button type="button" class="job-ai-btn-generate">
            <span class="job-ai-icon">✨</span>
            <span class="job-ai-btn-text">Написать отклик с Gemini</span>
          </button>
          <button type="button" class="job-ai-btn-settings" title="Открыть настройки профиля / API ключа">
            ⚙️
          </button>
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

    btnSettings.addEventListener("click", () => {
      if (modalEl.style.display === "none") {
        modalEl.style.display = "block";
        modalEl.innerHTML = `
          <strong>💡 Настройки расширения:</strong><br>
          Чтобы изменить ваш опыт, навыки или вставить Gemini API ключ, нажмите на иконку расширения <b>Job Apply AI</b> в правом верхнем углу панели Chrome (значок пазла 🧩 или закреплённая иконка ✨).
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

      // Update UI
      btnGenerate.disabled = true;
      btnText.textContent = "Генерирую отклик...";
      statusEl.className = "job-ai-status";
      statusEl.innerHTML = '<span class="job-ai-spinner"></span> Gemini читает вакансию...';
      modalEl.style.display = "none";

      try {
        const response = await chrome.runtime.sendMessage({
          action: "generate_cover_letter",
          vacancyTitle: details.title,
          company: details.company,
          vacancyText: details.description
        });

        if (response && response.success) {
          writeToField(field, response.text);

          statusEl.className = "job-ai-status success";
          statusEl.textContent = `✅ Отклик готов! (${response.modelUsed || "Gemini"})`;
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

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
})();
