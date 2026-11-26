const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_RESUME_PROFILE,
  detectTextLanguage,
  buildCoverLetterPrompt,
  buildScreeningQuestionPrompt,
  cleanCoverLetterResponse
} = require("../background.js");

test("detectTextLanguage identifies English, Ukrainian, and Russian accurately", () => {
  assert.equal(
    detectTextLanguage("General QA Engineer\nRequirements: 4+ years in QA, Playwright + TypeScript, Postman, SQL."),
    "en"
  );
  assert.equal(
    detectTextLanguage("Шукаємо досвідченого QA Automation інженера для тестування веб-додатків та API."),
    "uk"
  );
  assert.equal(
    detectTextLanguage("Ищем опытного QA Automation инженера для тестирования веб-приложений и API."),
    "ru"
  );
});

test("buildCoverLetterPrompt enforces English for English vacancies in auto mode", () => {
  const prompt = buildCoverLetterPrompt({
    vacancyTitle: "General QA Engineer (Web3 / Blockchain)",
    company: "Devico",
    vacancyText: "Requirements: 4+ years of professional experience in QA; Playwright + TypeScript; API testing (Postman, Swagger); SQL.",
    userProfile: DEFAULT_RESUME_PROFILE,
    language: "auto",
    tone: "concise"
  });

  assert.match(prompt, /STRICTLY in English/i);
  assert.match(prompt, /Devico/);
  assert.match(prompt, /Playwright \+ TypeScript/);
  assert.match(prompt, /Barclays Capital/);
  assert.match(prompt, /Quest Software/);
});

test("buildCoverLetterPrompt enforces Ukrainian for Ukrainian vacancies in auto mode", () => {
  const prompt = buildCoverLetterPrompt({
    vacancyTitle: "QA Automation Engineer",
    company: "ExampleTech",
    vacancyText: "Потрібен досвідчений тестувальник для автоматизації тестування на Python та Playwright, робота з REST API і SQL.",
    userProfile: DEFAULT_RESUME_PROFILE,
    language: "auto",
    tone: "concise"
  });

  assert.match(prompt, /STRICTLY in Ukrainian/i);
});

test("buildScreeningQuestionPrompt includes open job posting and matches question language", () => {
  const prompt = buildScreeningQuestionPrompt({
    questionText: "Describe your experience with Playwright and API testing.",
    vacancyTitle: "Senior QA Engineer",
    company: "Devico",
    vacancyText: "We use Playwright, Postman, Swagger, and PostgreSQL for Web3 compliance workflows.",
    userProfile: DEFAULT_RESUME_PROFILE,
    language: "auto"
  });

  assert.match(prompt, /STRICTLY in English/i);
  assert.match(prompt, /Web3 compliance workflows/);
  assert.match(prompt, /Oleg Kryvokobylskyi/);
});

test("cleanCoverLetterResponse strips markdown fences and draft headings", () => {
  assert.equal(cleanCoverLetterResponse("```text\nFinal Answer:\nHello world\n```"), "Hello world");
});
