"""
CLI utility to view, search, and export jobs stored in jobs_seen.db.
Usage:
    python view_db.py                     # Show stats & 20 latest jobs
    python view_db.py --limit 50          # Show 50 latest jobs
    python view_db.py --search "SDET"     # Search by title, company, or location
    python view_db.py --csv               # Export to jobs_seen.csv
    python view_db.py --html              # Export to interactive jobs_seen.html
"""

import argparse
import csv
import html
import os
import sqlite3
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "encoding") and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_db_path() -> Path:
    return Path(__file__).parent / "jobs_seen.db"


def show_stats_and_latest(limit: int = 20, search_term: str = ""):
    db_path = get_db_path()
    if not db_path.exists():
        print(f"❌ Файл базы данных '{db_path.name}' не найден.")
        return

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM seen_jobs")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(first_seen_at), MAX(first_seen_at) FROM seen_jobs")
        min_date, max_date = cursor.fetchone()

        print("=" * 80)
        print(f"📊 БАЗА ДАННЫХ ВАКАНСИЙ: {db_path.name}")
        print(f" Всего вакансий в базе: {total}")
        print(f" Период сбора: с {min_date or 'N/A'} по {max_date or 'N/A'}")
        print("=" * 80)

        # Выборка
        if search_term:
            query = """
                SELECT job_id, title, company, location, url, first_seen_at
                FROM seen_jobs
                WHERE job_id LIKE ? OR title LIKE ? OR company LIKE ? OR location LIKE ?
                ORDER BY first_seen_at DESC
                LIMIT ?
            """
            wildcard = f"%{search_term}%"
            cursor.execute(query, (wildcard, wildcard, wildcard, wildcard, limit))
            print(f"🔎 Результаты поиска по запросу: '{search_term}' (макс. {limit}):\n")
        else:
            query = """
                SELECT job_id, title, company, location, url, first_seen_at
                FROM seen_jobs
                ORDER BY first_seen_at DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))
            print(f"📋 Последние {limit} вакансий (от новых к старым):\n")

        rows = cursor.fetchall()
        if not rows:
            print("Ничего не найдено.")
            return

        for idx, (job_id, title, company, location, url, first_seen_at) in enumerate(rows, 1):
            date_str = (first_seen_at or "").split("T")[0]
            print(f"[{idx}] {title or 'Без названия'} @ {company or 'Не указана'}")
            print(f"    📍 Локация: {location or 'Не указана'}")
            print(f"    🕒 Добавлена: {date_str} | ID: {job_id}")
            if url:
                print(f"    🔗 Ссылка: {url}")
            print("-" * 80)


def export_csv(output_file: str = "jobs_seen.csv"):
    db_path = get_db_path()
    if not db_path.exists():
        print(f"❌ Файл базы данных '{db_path.name}' не найден.")
        return

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, title, company, location, url, posted_date, keyword, first_seen_at
            FROM seen_jobs
            ORDER BY first_seen_at DESC
            """
        )
        rows = cursor.fetchall()

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Title", "Company", "Location", "URL", "Posted Date", "Keyword", "First Seen At"])
        writer.writerows(rows)

    print(f"✅ База ({len(rows)} вакансий) успешно выгружена в CSV: {output_file}")
    print(f"   Файл можно открыть в Excel или Google Таблицах.")


def export_html(output_file: str = "jobs_seen.html"):
    db_path = get_db_path()
    if not db_path.exists():
        print(f"❌ Файл базы данных '{db_path.name}' не найден.")
        return

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, title, company, location, url, first_seen_at
            FROM seen_jobs
            ORDER BY first_seen_at DESC
            LIMIT 500
            """
        )
        rows = cursor.fetchall()

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Seen Jobs Database (Последние 500)</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; background: #f8fafc; color: #1e293b; }}
    h1 {{ color: #0f172a; font-size: 22px; }}
    .stats {{ margin-bottom: 20px; color: #64748b; font-size: 14px; }}
    input {{ padding: 10px 14px; width: 360px; font-size: 14px; border: 1px solid #cbd5e1; border-radius: 6px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
    th {{ background: #f1f5f9; font-weight: 600; color: #475569; }}
    tr:hover {{ background: #f8fafc; }}
    a {{ color: #2563eb; text-decoration: none; word-break: break-all; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #e0f2fe; color: #0369a1; }}
</style>
</head>
<body>
    <h1>📋 База отслеженных вакансий (jobs_seen.db)</h1>
    <div class="stats">Показано последних {len(rows)} вакансий. Начните вводить текст для мгновенного поиска по таблице:</div>
    <input type="text" id="search" placeholder="Поиск по названию, компании или локации..." onkeyup="filterTable()">
    <table id="jobsTable">
        <thead>
            <tr>
                <th>#</th>
                <th>Добавлена</th>
                <th>Позиция</th>
                <th>Компания</th>
                <th>Локация</th>
                <th>Ссылка</th>
            </tr>
        </thead>
        <tbody>
    """

    for idx, (job_id, title, company, location, url, first_seen_at) in enumerate(rows, 1):
        date_str = (first_seen_at or "").split("T")[0]
        safe_title = html.escape(title or "Без названия")
        safe_company = html.escape(company or "—")
        safe_loc = html.escape(location or "—")
        url_link = f'<a href="{html.escape(url)}" target="_blank">Открыть ↗</a>' if url else "—"

        html_content += f"""
            <tr>
                <td>{idx}</td>
                <td><span class="badge">{date_str}</span></td>
                <td><strong>{safe_title}</strong></td>
                <td>{safe_company}</td>
                <td>{safe_loc}</td>
                <td>{url_link}</td>
            </tr>"""

    html_content += """
        </tbody>
    </table>
<script>
function filterTable() {
    let input = document.getElementById("search").value.toLowerCase();
    let rows = document.querySelectorAll("#jobsTable tbody tr");
    rows.forEach(row => {
        let text = row.innerText.toLowerCase();
        row.style.display = text.includes(input) ? "" : "none";
    });
}
</script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Интерактивный HTML-отчет создан: {output_file}")
    print(f"   Дважды кликните по файлу, чтобы открыть его в браузере с поиском и ссылками!")


def main():
    parser = argparse.ArgumentParser(description="Утилита просмотра базы вакансий jobs_seen.db")
    parser.add_argument("--limit", "-n", type=int, default=20, help="Количество выводимых вакансий (по умолчанию: 20)")
    parser.add_argument("--search", "-s", type=str, default="", help="Поиск по названию, компании или локации")
    parser.add_argument("--csv", action="store_true", help="Выгрузить базу в jobs_seen.csv (для Excel)")
    parser.add_argument("--html", action="store_true", help="Сгенерировать jobs_seen.html для просмотра в браузере")

    args = parser.parse_args()

    if args.csv:
        export_csv()
    elif args.html:
        export_html()
    else:
        show_stats_and_latest(limit=args.limit, search_term=args.search)


if __name__ == "__main__":
    main()
