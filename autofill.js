// Bookmarklet Autofill Script for Oleg Kryvokobylskyi
(function() {
    const data = {
        firstName: "Oleg",
        lastName: "Kryvokobylskyi",
        fullName: "Oleg Kryvokobylskyi",
        email: "pegasovich@gmail.com",
        phone: "+353833959693",
        phoneLocal: "833959693",
        linkedin: "https://www.linkedin.com/in/oleg-krivokobylskiy",
        country: "Ireland",
        addressLine1: "Apartment 1, 5 O'Connell Street",
        addressLine2: "Apartment 1",
        street: "5 O'Connell Street",
        city: "Caherciveen",
        county: "Kerry",
        postalCode: "V23 DP40",
        noticePeriod: "Immediately",
        workAuth: "Stamp 4",
    };

    function setVal(el, val) {
        if (!el || el.disabled || el.readOnly) return false;
        el.focus();
        const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (setter) {
            setter.call(el, val);
        } else {
            el.value = val;
        }
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.dispatchEvent(new Event("blur", { bubbles: true }));
        el.style.backgroundColor = "#e8f5e9";
        el.style.borderColor = "#2e7d32";
        return true;
    }

    function selectOption(el, matchFn) {
        if (!el || el.tagName.toLowerCase() !== "select") return false;
        for (let opt of el.options) {
            if (matchFn(opt.text.toLowerCase(), (opt.value || "").toLowerCase())) {
                el.value = opt.value;
                el.dispatchEvent(new Event("change", { bubbles: true }));
                el.style.backgroundColor = "#e8f5e9";
                el.style.borderColor = "#2e7d32";
                return true;
            }
        }
        return false;
    }

    function getLabelText(el) {
        let text = "";
        if (el.id) {
            const lbl = document.querySelector(`label[for="${el.id}"]`);
            if (lbl) text += " " + lbl.innerText;
        }
        const parentLbl = el.closest("label");
        if (parentLbl) text += " " + parentLbl.innerText;
        if (el.getAttribute("aria-label")) text += " " + el.getAttribute("aria-label");
        if (el.getAttribute("placeholder")) text += " " + el.getAttribute("placeholder");
        if (el.name) text += " " + el.name;
        if (el.id) text += " " + el.id;
        const fieldset = el.closest("fieldset");
        if (fieldset) {
            const legend = fieldset.querySelector("legend");
            if (legend) text += " " + legend.innerText;
        }
        const container = el.closest(".form-field, .field, [class*='question'], [class*='section'], [class*='form-group'], [class*='formItem']");
        if (container) {
            const header = container.querySelector("label, .label, h3, h4, span, p");
            if (header) text += " " + header.innerText;
        }
        return text.toLowerCase();
    }

    let filledCount = 0;
    const inputs = Array.from(document.querySelectorAll("input, textarea, select"));

    // Check if separate country phone code dropdown exists on page
    const hasSeparatePhoneCode = inputs.some(i => i.tagName.toLowerCase() === "select" && getLabelText(i).includes("country phone code"));

    inputs.forEach(el => {
        const type = (el.type || "").toLowerCase();
        const tag = el.tagName.toLowerCase();
        const text = getLabelText(el);

        // 1. Country Selection
        if (text.includes("country") && !text.includes("phone code") && !text.includes("county")) {
            if (tag === "select") {
                if (selectOption(el, (t, v) => t === "ireland" || t.includes("ireland") || v === "ie" || v === "irl")) filledCount++;
            } else if (tag === "input" && !el.value) {
                if (setVal(el, data.country)) filledCount++;
            }
            return;
        }

        // 2. Preferred Name -> Select "No"
        if (text.includes("preferred name")) {
            if (tag === "select") {
                if (selectOption(el, (t, v) => t === "no" || v === "no" || v === "false")) filledCount++;
            } else if (type === "radio") {
                if (text.includes("no") || el.value.toLowerCase() === "no") {
                    el.checked = true;
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    filledCount++;
                }
            }
            return;
        }

        // 3. First / Given Name
        if ((text.includes("first name") || text.includes("given name") || text.includes("firstname") || text.includes("first_name")) && !text.includes("last") && !text.includes("family")) {
            if (setVal(el, data.firstName)) filledCount++;
            return;
        }

        // 4. Last / Family Name / Surname
        if (text.includes("last name") || text.includes("family name") || text.includes("surname") || text.includes("lastname") || text.includes("last_name")) {
            if (setVal(el, data.lastName)) filledCount++;
            return;
        }

        // 5. Full Name (only if single input)
        if (text.includes("full name") || text === "name" || text.includes("your name")) {
            if (!document.querySelector("input[name*='first'], input[id*='first'], input[name*='given']")) {
                if (setVal(el, data.fullName)) filledCount++;
                return;
            }
        }

        // 6. Address Line 1 / Street Address
        if (text.includes("address line 1") || text.includes("address 1") || text.includes("address_1") || text.includes("street address") || text === "address") {
            if (setVal(el, data.addressLine1)) filledCount++;
            return;
        }

        // 7. Address Line 2 / Apartment
        if (text.includes("address line 2") || text.includes("address 2") || text.includes("address_2") || text.includes("apartment") || text.includes("suite") || text.includes("unit")) {
            if (setVal(el, data.addressLine2)) filledCount++;
            return;
        }

        // 8. City / Town
        if ((text.includes("city") || text.includes("town")) && !text.includes("county")) {
            if (setVal(el, data.city)) filledCount++;
            return;
        }

        // 9. County (e.g. Co. Kerry / Kerry)
        if (text.includes("county")) {
            if (tag === "select") {
                if (selectOption(el, (t, v) => t.includes("kerry") || v.includes("kerry"))) filledCount++;
            } else if (tag === "input") {
                if (setVal(el, data.county)) filledCount++;
            }
            return;
        }

        // 10. Postal Code / Eircode / ZIP
        if (text.includes("postal code") || text.includes("postal_code") || text.includes("postcode") || text.includes("post code") || text.includes("zip") || text.includes("eircode")) {
            if (setVal(el, data.postalCode)) filledCount++;
            return;
        }

        // 11. Email
        if (type === "email" || (text.includes("email") && !text.includes("confirm"))) {
            if (setVal(el, data.email)) filledCount++;
            return;
        }

        // 12. Phone Device Type -> Select "Mobile"
        if (text.includes("device type") || text.includes("phone type") || text.includes("phone device")) {
            if (tag === "select") {
                if (selectOption(el, (t, v) => t.includes("mobile") || t.includes("cell") || v.includes("mobile"))) filledCount++;
            }
            return;
        }

        // 13. Country Phone Code -> Select "Ireland (+353)"
        if (text.includes("country phone code") || text.includes("phone code") || text.includes("dialing code")) {
            if (tag === "select") {
                if (selectOption(el, (t, v) => t.includes("353") || t.includes("ireland") || v.includes("353"))) filledCount++;
            }
            return;
        }

        // 14. Phone Number
        if (type === "tel" || ((text.includes("phone") || text.includes("mobile")) && !text.includes("type") && !text.includes("code"))) {
            const phoneToSet = hasSeparatePhoneCode ? data.phoneLocal : data.phone;
            if (setVal(el, phoneToSet)) filledCount++;
            return;
        }

        // 15. LinkedIn
        if (text.includes("linkedin") || text.includes("linked in")) {
            if (setVal(el, data.linkedin)) filledCount++;
            return;
        }

        // 16. Notice Period
        if (text.includes("notice period") || text.includes("notice") || text.includes("how soon can you start") || text.includes("availability")) {
            if (setVal(el, data.noticePeriod)) filledCount++;
            return;
        }

        // 17. Work Authorization / Visa / Stamp 4
        const isVisaOrAuth = text.includes("visa") ||
                             text.includes("work authorization") ||
                             text.includes("work_authorization") ||
                             text.includes("authorized to work") ||
                             text.includes("legally authorized") ||
                             text.includes("right to work") ||
                             text.includes("eligible to work") ||
                             text.includes("permit") ||
                             text.includes("immigration status") ||
                             text.includes("stamp");

        if (isVisaOrAuth) {
            const isSponsorship = text.includes("sponsorship") || text.includes("require sponsor");

            if (isSponsorship) {
                // "Do you require sponsorship?" -> NO
                if (type === "radio" || type === "checkbox") {
                    const label = getLabelText(el);
                    if (label.includes("no") || el.value.toLowerCase() === "no" || el.value === "0") {
                        el.checked = true;
                        el.dispatchEvent(new Event("change", { bubbles: true }));
                        filledCount++;
                    }
                } else if (tag === "select") {
                    selectOption(el, (t, v) => t === "no" || v === "no");
                    filledCount++;
                }
            } else {
                // General Work Authorization / Visa Status / Type -> "Stamp 4"
                if (tag === "textarea" || type === "text" || type === "") {
                    if (setVal(el, data.workAuth)) filledCount++;
                } else if (type === "radio" || type === "checkbox") {
                    const label = getLabelText(el);
                    if (label.includes("yes") || label.includes("stamp 4") || label.includes("authorized") || el.value.toLowerCase() === "yes" || el.value === "1") {
                        el.checked = true;
                        el.dispatchEvent(new Event("change", { bubbles: true }));
                        filledCount++;
                    }
                } else if (tag === "select") {
                    selectOption(el, (t, v) => t.includes("stamp 4") || t.includes("stamp") || t.includes("authorized") || t === "yes");
                    filledCount++;
                }
            }
            return;
        }

        // 18. AI / Terms / Privacy Consent Checkbox
        if (type === "checkbox") {
            if (text.includes("consent") || text.includes("acknowledge") || text.includes("privacy notice") || text.includes("artificial intelligence") || text.includes("recruitment privacy")) {
                el.checked = true;
                el.dispatchEvent(new Event("change", { bubbles: true }));
                el.style.outline = "2px solid #2e7d32";
                filledCount++;
                return;
            }
        }
    });

    // Notification toast
    const toast = document.createElement("div");
    toast.style.position = "fixed";
    toast.style.top = "20px";
    toast.style.right = "20px";
    toast.style.backgroundColor = "#1b5e20";
    toast.style.color = "#ffffff";
    toast.style.padding = "16px 24px";
    toast.style.borderRadius = "8px";
    toast.style.boxShadow = "0 4px 14px rgba(0,0,0,0.3)";
    toast.style.zIndex = "999999999";
    toast.style.fontSize = "15px";
    toast.style.fontFamily = "system-ui, -apple-system, sans-serif";
    toast.style.fontWeight = "bold";
    toast.innerHTML = `⚡ Автозаполнено полей: ${filledCount}<br><span style="font-size:12px;font-weight:normal;opacity:0.9;">Олег Кривокобыльский | Caherciveen, Co. Kerry | Stamp 4</span>`;
    document.body.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4500);
})();
