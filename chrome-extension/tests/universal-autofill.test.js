const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "..", "universal-autofill.js"), "utf8");

function createHarness(profile, elements, extraElements = []) {
  const listeners = [];
  const attributes = new Set();

  class HTMLInputElement {}
  class HTMLTextAreaElement {}
  class HTMLSelectElement {}
  class TestEvent {
    constructor(type) {
      this.type = type;
    }
  }

  Object.defineProperty(HTMLInputElement.prototype, "value", {
    get() { return this._value || ""; },
    set(value) { this._value = String(value); }
  });
  Object.defineProperty(HTMLTextAreaElement.prototype, "value", {
    get() { return this._value || ""; },
    set(value) { this._value = String(value); }
  });
  Object.defineProperty(HTMLSelectElement.prototype, "value", {
    get() { return this.options[this.selectedIndex]?.value || ""; },
    set(value) {
      const index = this.options.findIndex(option => String(option.value) === String(value));
      if (index >= 0) this.selectedIndex = index;
    }
  });

  const context = {
    chrome: {
      runtime: { onMessage: { addListener: listener => listeners.push(listener) } },
      storage: { sync: { get: async () => profile } }
    },
    document: {
      documentElement: {
        hasAttribute: name => attributes.has(name),
        setAttribute: name => attributes.add(name)
      },
      querySelectorAll: selector => selector === "input, textarea, select" ? elements : extraElements,
      getElementById: () => null
    },
    window: { getComputedStyle: () => ({ display: "block", visibility: "visible" }) },
    HTMLInputElement,
    HTMLTextAreaElement,
    HTMLSelectElement,
    Event: TestEvent
  };

  vm.runInNewContext(script, context, { filename: "universal-autofill.js" });

  return {
    async fill() {
      return new Promise(resolve => {
        const keepChannelOpen = listeners[0]({ action: "job_apply_autofill_contact" }, {}, resolve);
        assert.equal(keepChannelOpen, true);
      });
    }
  };
}

function createField({ tag = "INPUT", label, id = "", value = "", type = "text", autocomplete = "", options = [] }) {
  const field = {
    tagName: tag,
    type,
    labels: label ? [{ innerText: label }] : [],
    options,
    selectedIndex: Math.max(0, options.findIndex(option => String(option.value) === String(value))),
    _value: value,
    disabled: false,
    readOnly: false,
    events: [],
    name: "",
    id,
    getAttribute(name) {
      return name === "autocomplete" ? autocomplete : "";
    },
    getClientRects() { return [1]; },
    closest() { return null; },
    matches(selector) {
      if (tag !== "INPUT") return false;
      return ["hidden", "file", "checkbox", "radio", "submit", "button", "password"]
        .some(excludedType => selector.includes(`input[type=\"${excludedType}\"]`) && type === excludedType);
    },
    dispatchEvent(event) { this.events.push(event.type); }
  };
  Object.defineProperty(field, "value", {
    get() { return tag === "SELECT" ? (this.options[this.selectedIndex]?.value || "") : this._value; },
    set(value) {
      if (tag === "SELECT") {
        const index = this.options.findIndex(option => String(option.value) === String(value));
        if (index >= 0) this.selectedIndex = index;
      } else {
        this._value = String(value);
      }
    }
  });

  const prototype = tag === "SELECT" ? HTMLSelectElementPrototype :
    tag === "TEXTAREA" ? HTMLTextAreaElementPrototype : HTMLInputElementPrototype;
  Object.setPrototypeOf(field, prototype);
  return field;
}

// Keep references to the same prototype objects used by the isolated harness.
const HTMLInputElementPrototype = {};
const HTMLTextAreaElementPrototype = {};
const HTMLSelectElementPrototype = {};

test("fills address and contact fields and corrects the phone country prefix", async () => {
  const fields = [
    createField({ label: "First Name", value: "Oleg" }),
    createField({ label: "Last Name" }),
    createField({ label: "Email", value: "oleg@example.com", type: "email" }),
    createField({ label: "Find Address" }),
    createField({ autocomplete: "street-address" }),
    createField({ label: "Address line 1" }),
    createField({ label: "Address line 2" }),
    createField({ label: "Town/City" }),
    createField({ label: "County/State" }),
    createField({ label: "Country", value: "Ireland" }),
    createField({ label: "Post Code" }),
    createField({
      tag: "SELECT",
      value: "+44",
      options: [
        { value: "+44", text: "United Kingdom +44" },
        { value: "+353", text: "Ireland +353" }
      ]
    }),
    createField({ label: "Phone Numbers", type: "tel" }),
    createField({ tag: "TEXTAREA", label: "Other Contact Details" })
  ];
  const harness = createHarness({
    firstName: "Oleg",
    lastName: "Kryvokobylskyi",
    candidateEmail: "oleg@example.com",
    candidatePhone: "+353 83 395 9693",
    candidateCountry: "Ireland",
    candidateFindAddress: "Cahersiveen, County Kerry, Ireland",
    candidateAddressLine1: "12 Example Road",
    candidateAddressLine2: "Apartment 4",
    candidateCity: "Cahersiveen",
    candidateCounty: "Kerry",
    candidatePostcode: "V23 AB12",
    candidateOtherContactDetails: "LinkedIn: https://linkedin.example/oleg"
  }, fields);

  const result = await harness.fill();

  assert.equal(result.filledCount, 11);
  assert.equal(fields[0].value, "Oleg", "existing first name must remain untouched");
  assert.equal(fields[1].value, "Kryvokobylskyi");
  assert.equal(fields[2].value, "oleg@example.com", "existing email must remain untouched");
  assert.equal(fields[3].value, "Cahersiveen, County Kerry, Ireland");
  assert.equal(fields[4].value, "12 Example Road, Apartment 4", "street-address autocomplete should combine the address lines");
  assert.equal(fields[5].value, "12 Example Road");
  assert.equal(fields[6].value, "Apartment 4");
  assert.equal(fields[7].value, "Cahersiveen");
  assert.equal(fields[8].value, "Kerry");
  assert.equal(fields[9].value, "Ireland", "existing country must remain untouched");
  assert.equal(fields[10].value, "V23 AB12");
  assert.equal(fields[11].value, "+353", "phone prefix should match the profile number");
  assert.equal(fields[12].value, "83 395 9693", "national number should omit the prefix already selected above");
  assert.equal(fields[13].value, "LinkedIn: https://linkedin.example/oleg");
});

test("leaves unknown street and postal fields empty instead of guessing", async () => {
  const fields = [
    createField({ label: "Address line 1" }),
    createField({ label: "Address line 2" }),
    createField({ label: "Post Code" })
  ];
  const harness = createHarness({ candidateCountry: "Ireland" }, fields);

  const result = await harness.fill();

  assert.equal(result.filledCount, 0);
  assert.deepEqual(fields.map(field => field.value), ["", "", ""]);
});

test("maps PeopleHR address field IDs to the matching profile values", async () => {
  const fields = [
    createField({ id: "ucSection_txtAddressline1" }),
    createField({ id: "ucSection_txtAddressline2" }),
    createField({ id: "ucSection_txtAddressline3" }),
    createField({ id: "ucSection_txtState" }),
    createField({ id: "ucSection_txtAddressPostCode" })
  ];
  const harness = createHarness({
    candidateAddressLine1: "O'Connell 5",
    candidateAddressLine2: "Apartment 1",
    candidateCity: "Cahersiveen",
    candidateCounty: "Kerry",
    candidatePostcode: "V23 DP40"
  }, fields);

  await harness.fill();

  assert.deepEqual(fields.map(field => field.value), [
    "O'Connell 5", "Apartment 1", "Cahersiveen", "Kerry", "V23 DP40"
  ]);
});

test("uses the visible Find Address label before the ambiguous PeopleHR postcode ID", async () => {
  const findAddress = createField({ id: "txtPostcode" });
  const labelNode = { innerText: "Find Address", querySelector: () => null };
  const wrapper = { children: [findAddress], parentElement: null, querySelector: () => null };
  const row = { children: [labelNode, wrapper], parentElement: null };
  findAddress.parentElement = wrapper;
  wrapper.parentElement = row;

  const harness = createHarness({ candidatePostcode: "V23 DP40" }, [findAddress]);

  const result = await harness.fill();

  assert.equal(result.filledCount, 0);
  assert.equal(findAddress.value, "", "the Eircode must not be typed into the address-search field");
});

test("selects the international prefix in PeopleHR's custom phone widget", async () => {
  const phoneInput = createField({ id: "txtOtherContact", value: "83 395 9693" });
  const widgetState = { open: false, dialCode: "44" };
  const control = {
    textContent: "United Kingdom +44",
    getAttribute: name => name === "title" ? "United Kingdom: +44" : "",
    click() { widgetState.open = !widgetState.open; }
  };
  const irelandOption = {
    getAttribute: name => name === "data-dial-code" ? "353" : "",
    getClientRects: () => widgetState.open ? [1] : [],
    click() {
      widgetState.dialCode = "353";
      widgetState.open = false;
      control.textContent = "Ireland +353";
    }
  };
  const dialCode = { get textContent() { return widgetState.dialCode; } };
  const widget = {
    querySelector(selector) {
      if (selector.includes("iti__selected-flag")) return control;
      if (selector === ".iti__selected-dial-code") return dialCode;
      return null;
    },
    querySelectorAll: () => [irelandOption]
  };
  phoneInput.closest = selector => selector.includes(".iti") ? widget : null;
  const harness = createHarness({ candidatePhone: "+353 83 395 9693" }, [phoneInput], [irelandOption]);

  const result = await harness.fill();

  assert.equal(widgetState.dialCode, "353");
  assert.equal(control.textContent, "Ireland +353");
  assert.equal(phoneInput.value, "83 395 9693", "the existing national number should stay unchanged");
  assert.equal(result.filledCount, 1);
});
