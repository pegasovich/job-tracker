"""
Telegram notification module for LinkedIn Job Tracker.
Sends formatted alerts via Telegram Bot API.
"""

import urllib.request
import urllib.parse
import json
import html
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


_SOURCE_PRESENTATIONS = (
    ("djinni", "🟢 <b>Источник:</b> Djinni.co", "Открыть вакансию на Djinni"),
    ("dou", "🟡 <b>Источник:</b> DOU (jobs.dou.ua)", "Открыть вакансию на DOU"),
    ("nofluff", "🔴 <b>Источник:</b> No Fluff Jobs (nofluffjobs.com)", "Открыть вакансию на No Fluff Jobs"),
    ("justjoin", "🟣 <b>Источник:</b> JustJoin.it", "Открыть вакансию на JustJoin.it"),
    ("adzuna", "🟧 <b>Источник:</b> Adzuna (api.adzuna.com)", "Открыть вакансию на Adzuna"),
    ("arbeitnow", "🌐 <b>Источник:</b> Arbeitnow (arbeitnow.com)", "Открыть вакансию на Arbeitnow"),
    ("greenhouse", "🌱 <b>Источник:</b> Greenhouse (Direct ATS)", "Открыть вакансию на Greenhouse"),
    ("lever", "⚡ <b>Источник:</b> Lever (Direct ATS)", "Открыть вакансию на Lever"),
    ("ashby", "🪐 <b>Источник:</b> Ashby (Direct ATS)", "Открыть вакансию на Ashby"),
    ("himalayas", "🏔️ <b>Источник:</b> Himalayas (himalayas.app)", "Открыть вакансию на Himalayas"),
    ("remotive", "🚀 <b>Источник:</b> Remotive (remotive.com)", "Открыть вакансию на Remotive"),
    ("weworkremotely", "💼 <b>Источник:</b> WeWorkRemotely (weworkremotely.com)", "Открыть вакансию на WeWorkRemotely"),
    ("workremotely.eu", "🌍 <b>Источник:</b> WorkRemotely.eu", "Открыть вакансию на WorkRemotely.eu"),
    ("jobicy", "🟠 <b>Источник:</b> Jobicy", "Открыть вакансию на Jobicy"),
    ("remote ok", "🌍 <b>Источник:</b> Remote OK", "Открыть вакансию на Remote OK"),
    ("techjobs", "🇮🇪 <b>Источник:</b> TechJobs.ie", "Открыть вакансию на TechJobs.ie"),
)
_DEFAULT_SOURCE_PRESENTATION = ("🔵 <b>Источник:</b> LinkedIn", "Открыть вакансию на LinkedIn")


def _resolve_source_presentation(source: str) -> tuple[str, str]:
    """Return (badge_html, link_text) for a job source name."""
    normalized = (source or "").lower()
    for token, badge, link_text in _SOURCE_PRESENTATIONS:
        if token in normalized:
            return badge, link_text
    return _DEFAULT_SOURCE_PRESENTATION


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured:
            logger.warning("Telegram notifier is not configured (missing token or chat_id).")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                logger.error(f"Telegram API error status: {resp.status}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
        return False

    def send_job_alert(self, job: Dict[str, Any], snippet: str = "", workplace_type: str = "remote") -> bool:
        """Formats and sends a single job alert."""
        title = html.escape(job.get("title", "Untitled"))
        company = html.escape(job.get("company", "Unknown Company"))
        location = html.escape(job.get("location", "Remote"))
        url = job.get("url", "")
        raw_keyword = job.get("keyword", "")
        keyword = html.escape(raw_keyword)
        source = job.get("source", "LinkedIn")
        salary = html.escape(job.get("salary", ""))

        source_badge, link_text = _resolve_source_presentation(source)

        if workplace_type == "remote":
            work_type_badge = "🏡 <b>Формат:</b> <b>Remote (Удалёнка)</b>"
        elif workplace_type == "hybrid":
            work_type_badge = "⚠️ <b>Формат:</b> <b>Hybrid (Дни в офисе)</b>"
        else:
            work_type_badge = "❓ <b>Формат:</b> Не подтверждён"

        region = html.escape(job.get("region", ""))
        region_badge = f"\n🌍 <b>Регион поиска:</b> {region}" if region else ""
        salary_line = f"\n💰 <b>Зарплата:</b> {salary}" if salary else ""
        employment_type = html.escape(job.get("employment_type", ""))
        employment_line = f"\n🧾 <b>Тип:</b> {employment_type}" if employment_type else ""
        if not raw_keyword:
            keyword_line = ""
        elif "(" in raw_keyword or '"' in raw_keyword:
            keyword_line = f"\n🔎 <b>Поиск:</b> <code>{keyword}</code>"
        else:
            keyword_line = f"\n🔎 <b>Поиск:</b> #{keyword.replace(' ', '_')}"

        screening_reminder = ""
        if "linkedin" in source.lower():
            screening_reminder = (
                "\n\n⚠️ <b>Перед Easy Apply:</b> проверь вопросы работодателя "
                "и укажи реальный стаж. Screening-требования LinkedIn могут "
                "не отображаться в этой карточке."
            )

        msg = (
            f"🎯 <b>{title}</b>\n\n"
            f"{source_badge}\n"
            f"🏢 <b>Компания:</b> {company}\n"
            f"📍 <b>Локация:</b> {location}\n"
            f"{work_type_badge}{region_badge}{salary_line}{employment_line}{keyword_line}"
            f"{screening_reminder}\n"
        )

        if snippet:
            clean_snippet = html.escape(snippet)
            msg += f"\n📝 <b>Выжимка:</b>\n<i>{clean_snippet}</i>\n"

        safe_url = html.escape(url, quote=True)
        if safe_url:
            msg += f'\n🔗 <a href="{safe_url}">{link_text}</a>'

        return self.send_message(msg)
