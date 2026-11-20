"""
SQLite Database manager for tracking seen LinkedIn jobs.
"""

import sqlite3
import datetime
import os
from typing import Dict, Any


class JobDatabase:
    def __init__(self, db_path: str = "jobs_seen.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_jobs (
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
            conn.commit()

    def is_seen(self, job_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

    def add_job(self, job: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO seen_jobs (
                    job_id, title, company, location, url, posted_date, keyword, first_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["id"],
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("url", ""),
                    job.get("posted_date", ""),
                    job.get("keyword", ""),
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def count_seen(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_jobs")
            row = cursor.fetchone()
            return row[0] if row else 0

    def merge_from(self, source_db_path: str) -> int:
        """
        Merge seen jobs from another SQLite database file into this database.
        Uses INSERT OR IGNORE to safely deduplicate records.
        Returns the count of newly inserted records.
        """
        if not os.path.exists(source_db_path):
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_jobs")
            count_before = cursor.fetchone()[0]

            conn.execute("ATTACH DATABASE ? AS source_db", (source_db_path,))
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_jobs (
                    job_id, title, company, location, url, posted_date, keyword, first_seen_at
                )
                SELECT
                    job_id, title, company, location, url, posted_date, keyword, first_seen_at
                FROM source_db.seen_jobs
                """
            )
            conn.commit()
            try:
                conn.execute("DETACH DATABASE source_db")
            except Exception:
                pass

            cursor.execute("SELECT COUNT(*) FROM seen_jobs")
            count_after = cursor.fetchone()[0]
            return count_after - count_before
