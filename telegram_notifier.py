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
        keyword = html.escape(job.get("keyword", ""))
        source = job.get("source", "LinkedIn")
        salary = html.escape(job.get("salary", ""))

        if "djinni" in source.lower():
            source_badge = "🟢 <b>Источник:</b> Djinni.co"
        else:
            source_badge = "🔵 <b>Источник:</b> LinkedIn"

        if workplace_type == "remote":
            work_type_badge = "🏡 <b>Формат:</b> <b>Remote (Удалёнка)</b>"
        elif workplace_type == "hybrid":
            work_type_badge = "⚠️ <b>Формат:</b> <b>Hybrid (Дни в офисе)</b>"
        else:
            work_type_badge = "❓ <b>Формат:</b> Не подтверждён"

        region = html.escape(job.get("region", ""))
        region_badge = f"\n🌍 <b>Регион поиска:</b> {region}" if region else ""
        salary_line = f"\n💰 <b>Зарплата:</b> {salary}" if salary else ""

        msg = (
            f"🎯 <b>{title}</b>\n\n"
            f"{source_badge}\n"
            f"🏢 <b>Компания:</b> {company}\n"
            f"📍 <b>Локация:</b> {location}\n"
            f"{work_type_badge}{region_badge}{salary_line}\n"
            f"🔎 <b>Поиск:</b> #{keyword.replace(' ', '_')}\n"
        )

        if snippet:
            clean_snippet = html.escape(snippet)
            msg += f"\n📝 <b>Выжимка:</b>\n<i>{clean_snippet}</i>\n"

        link_text = "Открыть вакансию на Djinni" if "djinni" in source.lower() else "Открыть вакансию на LinkedIn"
        msg += f"\n🔗 <a href=\"{url}\">{link_text}</a>"

        return self.send_message(msg)
