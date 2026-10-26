# LinkedIn Remote QA/SDET Job Tracker (Ireland 🇮🇪)

Автоматический трекер вакансий **QA Engineer** / **SDET** (Manual, Automation, API, Python, JS/TS, Java) с фильтром **Remote в Ирландии** и отправкой новых предложений в **Telegram**.

---

## ⚡ Особенности
- **Безопасно для аккаунта:** использует публичный гостевой API LinkedIn (без ввода вашего логина и пароля, без риска банов и капчи).
- **Дедупликация:** сохраняет найденные вакансии в локальную базу SQLite (`jobs_seen.db`), чтобы не присылать одну и ту же вакансию дважды.
- **Детектор формата работы:** анализирует описание вакансии и предупреждает, если компания под видом Remote требует гибрид (например, "Hybrid: 2 days in office").
- **Краткая выжимка:** извлекает превью описания вакансии прямо в карточку Telegram.

---

## 🚀 Быстрый старт

### 1. Настройка Telegram (1 минута)
1. Откройте в Telegram бота **[@BotFather](https://t.me/BotFather)** и отправьте команду `/newbot`.
2. Следуйте инструкциям и скопируйте выданный **HTTP API Token**.
3. Напишите вашему созданному боту любое сообщение (например, `/start`).
4. Узнайте свой цифровой ID: напишите боту **[@userinfobot](https://t.me/userinfobot)** — он пришлет ваш `Id`.
5. Создайте файл `.env` (или скопируйте `.env.example` в `.env`) и укажите полученные данные:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_CHAT_ID=987654321
```

---

## 💻 Запуск

### Тестовый прогон (без отправки в Telegram, вывод в консоль):
```powershell
python main.py --dry-run
```

### Боевой запуск (разовая проверка и отправка в Telegram):
```powershell
python main.py
```

### Фоновый мониторинг (проверка каждые N минут):
```powershell
# Например, проверка каждые 60 минут:
python main.py --interval 60
```

---

## ⚙️ Настройки поиска (`config.py`)
В файле [`config.py`](config.py) вы можете отредактировать:
- `SEARCH_KEYWORDS` — список ключевых фраз (по умолчанию: QA Engineer, SDET, Quality Assurance Engineer, Automation QA, Test Automation Engineer).
- `TARGET_LOCATION` — страна/регион поиска (по умолчанию: `Ireland`).
- `REMOTE_ONLY` — включение удаленного режима (`True`).
- `FETCH_SNIPPETS` — скачивание превью описания для Telegram (`True`).
