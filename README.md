# QA/SDET Job Tracker 🇮🇪🇬🇧🌍

Автоматический трекер вакансий **QA Engineer** / **SDET** (Manual, Automation, API, Python, JS/TS, Java) с поиском по **Ireland, UK, Europe, Worldwide** и умной фильтрацией формата работы. Новые вакансии отправляются в **Telegram**.

---

## ⚡ Особенности
- **Два источника:** парсит вакансии с **LinkedIn** (Guest API) и **Djinni.co** (JSON-LD).
- **Безопасно для аккаунта:** использует публичный гостевой API LinkedIn (без ввода логина и пароля, без риска банов и капчи).
- **Дедупликация:** сохраняет найденные вакансии в локальную базу SQLite (`jobs_seen.db`), чтобы не присылать одну и ту же вакансию дважды.
- **Умный фильтр формата работы:**
  - ✅ **Remote** — пропускает всегда
  - ⚠️ **Hybrid** — пропускает только если локация рядом с домом (Kerry, Cork и окрестности Cahersiveen)
  - 🚫 **On-site** — блокирует всегда
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

### Быстрый тест (один ключевик, один регион):
```powershell
python main.py --test
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
- `TARGET_LOCATIONS` — регионы поиска (по умолчанию: Ireland, United Kingdom, Europe, Worldwide).
- `SEARCH_KEYWORDS` — ключевые фразы для LinkedIn (QA Engineer, SDET, Automation QA, Test Automation).
- `DJINNI_KEYWORDS` — ключевые фразы для Djinni.co (QA Automation, SDET, QA Manual).
- `REMOTE_ONLY` — фильтр Remote на LinkedIn (`True`).
- `ALLOW_HYBRID` — глобальный допуск гибридных вакансий (`False` — заблокированы по умолчанию).
- `HYBRID_ALLOWED_LOCATIONS` — список локаций, для которых Hybrid разрешён (Kerry, Cork и т.д.).
- `FETCH_SNIPPETS` — скачивание превью описания для Telegram (`True`).
