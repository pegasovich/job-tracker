(() => {
  const marker = "data-job-apply-universal-autofill";
  if (document.documentElement.hasAttribute(marker)) return;
  document.documentElement.setAttribute(marker, "true");

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.action !== "job_apply_autofill_contact") return;
    fillContactFields().then(
      filledCount => sendResponse({ filledCount }),
      () => sendResponse({ filledCount: 0 })
    );
    return true;
  });

  async function fillContactFields() {
    const profile = await chrome.storage.sync.get([
      "firstName", "lastName", "candidateEmail", "candidatePhone", "candidateCountry"
    ]);
    const data = {
      firstName: profile.firstName || "Oleg",
      lastName: profile.lastName || "Kryvokobylskyi",
      email: profile.candidateEmail || "pegasovich@gmail.com",
      phone: profile.candidatePhone || "+353 83 395 9693",
      country: profile.candidateCountry || "Ireland"
    };
    let filledCount = 0;

    for (const element of document.querySelectorAll("input, textarea, select")) {
      if (element.disabled || element.readOnly || !isVisible(element) || isAlreadyFilled(element)) continue;
      if (element.matches('input[type="hidden"], input[type="file"], input[type="checkbox"], input[type="radio"], input[type="submit"], input[type="button"], input[type="password"]')) continue;

      const context = getContext(element);
      const type = (element.getAttribute("type") || "").toLowerCase();
      const autocomplete = (element.getAttribute("autocomplete") || "").toLowerCase();
      let value = null;

      if (element.tagName === "SELECT") {
        if (isCountryField(context, autocomplete)) {
          if (chooseOption(element, ["ireland", "republic of ireland", "ie", "irl"])) filledCount++;
        }
        continue;
      }

      if (autocomplete === "given-name" || hasAny(context, ["first name", "given name", "firstname", "first_name"])) {
        value = data.firstName;
      } else if (autocomplete === "family-name" || hasAny(context, ["last name", "family name", "surname", "lastname", "last_name"])) {
        value = data.lastName;
      } else if (autocomplete === "name" || hasAny(context, ["full name", "your name", "fullname"]) || context.trim() === "name") {
        value = `${data.firstName} ${data.lastName}`;
      } else if (autocomplete === "email" || type === "email" || hasAny(context, ["email", "e-mail"])) {
        value = data.email;
      } else if (autocomplete === "tel" || type === "tel" || hasAny(context, ["phone number", "phone", "mobile", "telephone"])) {
        if (!hasAny(context, ["phone code", "country code", "dialing code"])) value = data.phone;
      } else if (isCountryField(context, autocomplete)) {
        value = data.country;
      }

      if (value !== null && setValue(element, value)) filledCount++;
    }

    return filledCount;
  }

  function getContext(element) {
    const parts = [
      element.labels ? Array.from(element.labels).map(label => label.innerText).join(" ") : "",
      element.getAttribute("aria-label") || "",
      element.getAttribute("placeholder") || "",
      element.getAttribute("aria-labelledby")
        ? element.getAttribute("aria-labelledby").split(/\s+/).map(id => document.getElementById(id)?.innerText || "").join(" ")
        : "",
      element.name || "",
      element.id || ""
    ];
    const wrapper = element.closest(".form-group, .form-field, .field, [class*='question'], [class*='field']");
    const label = wrapper?.querySelector("label, legend, [class*='label']");
    if (label && !parts.includes(label.innerText)) parts.push(label.innerText);

    // Some application forms render labels as plain sibling elements without
    // label/for, aria-label, or useful input names. Look for the nearest small
    // preceding text block that contains a recognizable contact-field label.
    const labelTerms = ["first name", "first_name", "given name", "last name", "last_name", "family name", "surname", "email", "e-mail", "phone", "mobile", "telephone", "country", "name"];
    if (!hasAny(parts.join(" ").toLowerCase(), labelTerms)) {
      let current = element;
      for (let depth = 0; depth < 4 && current.parentElement; depth++) {
        const siblings = Array.from(current.parentElement.children);
        const currentIndex = siblings.indexOf(current);
        for (let index = currentIndex - 1; index >= 0; index--) {
          const sibling = siblings[index];
          if (sibling.querySelector("input, textarea, select")) continue;
          const text = (sibling.innerText || "").replace(/\s+/g, " ").trim();
          if (text.length <= 100 && hasAny(text.toLowerCase(), labelTerms)) {
            parts.push(text);
            break;
          }
        }
        if (parts.length > 0) break;
        current = current.parentElement;
      }
    }

    return parts.join(" ").replace(/\s+/g, " ").toLowerCase();
  }

  function isCountryField(context, autocomplete) {
    return (autocomplete === "country-name" || hasAny(context, ["country", "residence country", "country of residence"])) &&
      !hasAny(context, ["phone code", "country code", "dialing code", "county"]);
  }

  function hasAny(text, terms) {
    return terms.some(term => text.includes(term));
  }

  function isVisible(element) {
    const style = window.getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
  }

  function isAlreadyFilled(element) {
    if (element.tagName === "SELECT") {
      const option = element.options[element.selectedIndex];
      return Boolean(element.value && option && option.value && !/select|choose|please choose/i.test(option.text));
    }
    return Boolean(String(element.value || "").trim());
  }

  function setValue(element, value) {
    const prototype = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (setter) setter.call(element, value);
    else element.value = value;
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  }

  function chooseOption(select, matches) {
    const option = Array.from(select.options).find(item => {
      const text = (item.text || "").trim().toLowerCase();
      const value = (item.value || "").trim().toLowerCase();
      return matches.some(match => text === match || value === match || text.includes(match));
    });
    if (!option) return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
    if (setter) setter.call(select, option.value);
    else select.value = option.value;
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
})();
