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
      "firstName", "lastName", "candidateEmail", "candidatePhone", "candidateCountry",
      "candidateFindAddress", "candidateAddressLine1", "candidateAddressLine2",
      "candidateCity", "candidateCounty", "candidatePostcode", "candidateOtherContactDetails",
      "candidateLinkedin", "candidateGithub"
    ]);
    const phone = splitInternationalPhone(profile.candidatePhone || "+353 83 395 9693");
    const linkedin = profile.candidateLinkedin || "https://www.linkedin.com/in/oleg-kryvokobylskyi/";
    const github = profile.candidateGithub || "https://github.com/pegasovich";
    const data = {
      firstName: profile.firstName || "Oleg",
      lastName: profile.lastName || "Kryvokobylskyi",
      email: profile.candidateEmail || "pegasovich@gmail.com",
      phone: phone.nationalNumber,
      phoneCountryCode: phone.countryCode,
      phoneCountry: phone.country,
      country: profile.candidateCountry || "Ireland",
      findAddress: profile.candidateFindAddress || "",
      addressLine1: profile.candidateAddressLine1 || "",
      addressLine2: profile.candidateAddressLine2 || "",
      city: profile.candidateCity || "Cahersiveen",
      county: profile.candidateCounty || "Kerry",
      postcode: profile.candidatePostcode || "",
      linkedin,
      otherContactDetails: profile.candidateOtherContactDetails !== undefined
        ? profile.candidateOtherContactDetails
        : `LinkedIn: ${linkedin}\nGitHub: ${github}`
    };
    let filledCount = 0;

    for (const element of document.querySelectorAll("input, textarea, select")) {
      if (element.disabled || element.readOnly || !isVisible(element)) continue;
      if (element.matches('input[type="hidden"], input[type="file"], input[type="checkbox"], input[type="radio"], input[type="submit"], input[type="button"], input[type="password"]')) continue;

      const context = getContext(element);
      const autocomplete = (element.getAttribute("autocomplete") || "").toLowerCase();
      const phoneCodeField = element.tagName === "SELECT" && isPhoneCodeField(element, context, autocomplete);

      // PeopleHR uses an intl-tel-input combobox instead of a native <select>.
      if (data.phoneCountryCode && isPhoneField(context, autocomplete, element.type) &&
          choosePhonePrefixWidget(element, data.phoneCountryCode)) {
        filledCount++;
      }

      // Phone-code controls often start with a non-matching default such as +44.
      // Other non-empty fields are deliberately left alone.
      if (isAlreadyFilled(element) && !phoneCodeField) continue;

      if (element.tagName === "SELECT") {
        if (phoneCodeField) {
          if (data.phoneCountryCode && choosePhoneCode(element, data.phoneCountryCode, data.phoneCountry)) filledCount++;
        } else if (isCountryField(context, autocomplete)) {
          if (chooseOption(element, [data.country, "Ireland", "Republic of Ireland", "IE", "IRL"])) filledCount++;
        } else {
          const value = getAddressFieldValue(context, autocomplete, data);
          if (value && chooseOption(element, [value])) filledCount++;
        }
        continue;
      }

      const value = getFieldValue(context, autocomplete, element, data);
      if (value && setValue(element, value)) filledCount++;
    }

    return filledCount;
  }

  function getFieldValue(context, autocomplete, element, data) {
    const normalized = normalize(context);
    if (autocomplete === "given-name" || hasAny(normalized, ["first name", "given name", "firstname"])) {
      return data.firstName;
    }
    if (autocomplete === "family-name" || hasAny(normalized, ["last name", "family name", "surname", "lastname"])) {
      return data.lastName;
    }
    if (autocomplete === "name" || hasAny(normalized, ["full name", "your name", "fullname"]) || normalized.trim() === "name") {
      return `${data.firstName} ${data.lastName}`;
    }
    if (autocomplete === "email" || element.type === "email" || hasAny(normalized, ["email", "e mail"])) {
      return data.email;
    }
    if (hasAny(normalized, ["linkedin", "linked in"])) return data.linkedin;
    if (isCountryField(normalized, autocomplete)) return data.country;

    const addressValue = getAddressFieldValue(normalized, autocomplete, data);
    if (addressValue !== null) return addressValue;

    if (autocomplete === "tel-country-code") return data.phoneCountryCode ? `+${data.phoneCountryCode}` : null;
    if (isPhoneField(normalized, autocomplete, element.type)) return data.phone;
    return null;
  }

  function getAddressFieldValue(context, autocomplete, data) {
    const normalized = normalize(context);
    if (hasAny(normalized, ["find address", "address search", "address lookup"])) {
      return data.findAddress || null;
    }
    if (autocomplete === "street-address") {
      const streetAddress = [data.addressLine1, data.addressLine2].filter(Boolean).join(", ");
      return streetAddress || null;
    }
    if (autocomplete === "address-line2" || hasAny(normalized, [
      "address line 2", "address line2", "addressline2", "address 2", "address2", "apartment", "suite", "unit number"
    ])) {
      return data.addressLine2 || null;
    }
    if (autocomplete === "address-level2" || hasAny(normalized, ["town", "city", "municipality", "locality", "addressline3"])) {
      return data.city || null;
    }
    if (autocomplete === "address-level1" || hasAny(normalized, ["county", "state", "province", "region"])) {
      return data.county || null;
    }
    if (autocomplete === "postal-code" || hasAny(normalized, ["postal code", "postcode", "post code", "zip code", "zip"])) {
      return data.postcode || null;
    }
    if (hasAny(normalized, ["other contact details", "othercontactdetails", "additional contact details", "contact details"])) {
      return data.otherContactDetails || null;
    }
    if (autocomplete === "address-line1" || hasAny(normalized, [
      "address line 1", "address line1", "addressline1", "address 1", "address1", "street address", "address"
    ])) {
      return data.addressLine1 || null;
    }
    return null;
  }

  function getContext(element) {
    const labelParts = [
      element.labels ? Array.from(element.labels).map(label => label.innerText).join(" ") : "",
      element.getAttribute("aria-label") || "",
      element.getAttribute("aria-labelledby")
        ? element.getAttribute("aria-labelledby").split(/\s+/).map(id => document.getElementById(id)?.innerText || "").join(" ")
        : ""
    ];
    const placeholder = element.getAttribute("placeholder") || "";
    const wrapper = element.closest(".form-group, .form-field, .field, [class*='question'], [class*='field']");
    const label = wrapper?.querySelector("label, legend, [class*='label']");
    const wrapperControls = wrapper?.querySelectorAll?.("input, textarea, select");
    if (label && (!wrapperControls || wrapperControls.length <= 1) && !labelParts.includes(label.innerText)) {
      labelParts.push(label.innerText);
    }

    // Some sites render labels as plain siblings without label/for or useful input names.
    const labelTerms = [
      "first name", "first_name", "given name", "last name", "last_name", "family name", "surname",
      "email", "e-mail", "phone", "mobile", "telephone", "country", "name", "find address",
      "address", "street", "town", "city", "county", "state", "province", "postal", "postcode",
      "post code", "zip", "contact details", "linkedin", "linked in"
    ].map(normalize);
    const nearbyLabels = [];
    if (!hasAny(normalize(labelParts.join(" ")), labelTerms)) {
      let current = element;
      for (let depth = 0; depth < 4 && current.parentElement; depth++) {
        const siblings = Array.from(current.parentElement.children);
        const currentIndex = siblings.indexOf(current);
        for (let index = currentIndex - 1; index >= 0; index--) {
          const sibling = siblings[index];
          if (sibling.querySelector("input, textarea, select")) continue;
          const text = (sibling.innerText || "").replace(/\s+/g, " ").trim();
          if (text.length <= 100 && hasAny(normalize(text), labelTerms)) {
            nearbyLabels.push(text);
            break;
          }
        }
        if (nearbyLabels.length) break;
        current = current.parentElement;
      }
    }

    return [...labelParts, ...nearbyLabels, placeholder, element.name || "", element.id || ""]
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .toLowerCase();
  }

  function isCountryField(context, autocomplete) {
    const normalized = normalize(context);
    return (autocomplete === "country-name" || hasAny(normalized, ["country", "residence country", "country of residence"])) &&
      !hasAny(normalized, ["phone code", "country code", "dialing code", "dialling code", "county"]);
  }

  function isPhoneCodeField(element, context, autocomplete) {
    const normalized = normalize(context);
    if (autocomplete === "tel-country-code" || hasAny(normalized, ["phone code", "country code", "dial code", "dialing code", "dialling code", "calling code", "phone prefix"])) {
      return true;
    }
    return element.tagName === "SELECT" &&
      Array.from(element.options || []).some(option => /\+\s*\d{1,3}/.test(`${option.text || ""} ${option.value || ""}`));
  }

  function isPhoneField(context, autocomplete, type) {
    const normalized = normalize(context);
    const peopleHrPhoneInput = normalized.split(" ").includes("txtothercontact");
    return autocomplete === "tel" || type === "tel" || peopleHrPhoneInput ||
      (hasAny(normalized, ["phone number", "phone", "mobile", "telephone"]) &&
        !hasAny(normalized, ["phone code", "country code", "dialing code", "dialling code", "phone prefix"]));
  }

  function splitInternationalPhone(phone) {
    const raw = String(phone || "").trim();
    const match = raw.match(/^\+(\d{1,3})[\s().-]+(.+)$/);
    if (!match) return { countryCode: "", country: "", nationalNumber: raw };

    const countryCode = match[1];
    const countryNames = { "353": "Ireland", "44": "United Kingdom", "1": "United States" };
    let nationalNumber = match[2].trim().replace(/\s+/g, " ");
    if (nationalNumber.startsWith("0")) nationalNumber = nationalNumber.slice(1).trim();
    return { countryCode, country: countryNames[countryCode] || "", nationalNumber };
  }

  function hasAny(text, terms) {
    return terms.some(term => text.includes(term));
  }

  function normalize(text) {
    return String(text || "").toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
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
    if (!String(value || "").trim()) return false;
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
      const text = normalize(item.text || "");
      const value = normalize(item.value || "");
      return matches.some(match => text === normalize(match) || value === normalize(match) || text.includes(normalize(match)));
    });
    return setSelectOption(select, option);
  }

  function choosePhoneCode(select, code, country) {
    const codeText = `+${code}`;
    const countryText = normalize(country);
    const option = Array.from(select.options).find(item => {
      const text = String(item.text || "").toLowerCase();
      const value = String(item.value || "").toLowerCase();
      const digits = value.replace(/\D/g, "");
      return text.includes(codeText) || digits === String(code) || (countryText && `${text} ${value}`.includes(countryText));
    });
    return setSelectOption(select, option);
  }

  function choosePhonePrefixWidget(phoneInput, code) {
    if (!phoneInput.closest || !code) return false;
    const root = phoneInput.closest(".iti, .intl-tel-input");
    if (!root) return false;

    const control = root.querySelector(".iti__selected-flag[role='combobox'], [role='combobox'][aria-haspopup='listbox'], [role='combobox']");
    if (!control || typeof control.click !== "function") return false;

    const controlText = [
      control.textContent || "",
      control.getAttribute("title") || "",
      control.getAttribute("aria-label") || "",
      root.querySelector(".iti__selected-dial-code")?.textContent || ""
    ].join(" ");
    if (new RegExp(`\\+\\s*${code}\\b`).test(controlText)) return false;

    const alreadyExpanded = control.getAttribute("aria-expanded") === "true";
    if (!alreadyExpanded) control.click();
    const optionSelector = ".iti__country[data-dial-code], [role='option'][data-dial-code]";
    const rootOptions = Array.from(root.querySelectorAll(optionSelector) || []);
    const pageOptions = rootOptions.length ? rootOptions : Array.from(document.querySelectorAll(optionSelector));
    const option = pageOptions.find(item => item.getAttribute("data-dial-code") === String(code) && isVisible(item));
    if (option && typeof option.click === "function") {
      option.click();
      return true;
    }

    // Leave the page as we found it if this widget does not expose country options.
    if (!alreadyExpanded) control.click();
    return false;
  }

  function setSelectOption(select, option) {
    if (!option || select.value === option.value) return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
    if (setter) setter.call(select, option.value);
    else select.value = option.value;
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
})();
