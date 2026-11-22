import os
import sqlite3
import pytest
from pathlib import Path
import view_db


def test_view_db_stats(tmp_path, monkeypatch, capsys):
    db_file = tmp_path / "test_jobs.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE seen_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            posted_date TEXT,
            keyword TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        INSERT INTO seen_jobs (job_id, title, company, location, url, first_seen_at)
        VALUES ('test_1', 'Senior QA Engineer', 'Acme Corp', 'Remote Ireland', 'https://example.com/1', '2026-11-22T20:00:00')
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(view_db, "get_db_path", lambda: db_file)

    view_db.show_stats_and_latest(limit=5)
    captured = capsys.readouterr().out
    assert "Всего вакансий в базе: 1" in captured
    assert "Senior QA Engineer @ Acme Corp" in captured

    # Test search
    view_db.show_stats_and_latest(limit=5, search_term="Acme")
    captured_search = capsys.readouterr().out
    assert "Результаты поиска по запросу: 'Acme'" in captured_search
    assert "Acme Corp" in captured_search


def test_view_db_exports(tmp_path, monkeypatch):
    db_file = tmp_path / "test_jobs.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE seen_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            posted_date TEXT,
            keyword TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        INSERT INTO seen_jobs (job_id, title, company, location, url, first_seen_at)
        VALUES ('test_1', 'SDET Lead', 'Beta Ltd', 'Remote UK', 'https://example.com/2', '2026-11-22T20:00:00')
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(view_db, "get_db_path", lambda: db_file)

    csv_path = tmp_path / "output.csv"
    html_path = tmp_path / "output.html"

    view_db.export_csv(str(csv_path))
    assert csv_path.exists()
    assert "SDET Lead" in csv_path.read_text(encoding="utf-8-sig")

    view_db.export_html(str(html_path))
    assert html_path.exists()
    assert "SDET Lead" in html_path.read_text(encoding="utf-8")
