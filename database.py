"""
SQLite Database manager for tracking seen LinkedIn jobs.
"""

import contextlib
import hashlib
import re
import sqlite3
import datetime
import os
from contextlib import contextmanager
from typing import Dict, Any


def compute_job_fingerprint(job: Dict[str, Any], description: str = "") -> str:
    """Compute a deterministic content hash to prevent duplicate repost/cross-source alerts."""
    def _norm(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip().lower()

    title = _norm(job.get("title", ""))
    company = _norm(job.get("company", ""))
    desc_text = _norm(description or job.get("description", ""))
    if len(desc_text) >= 60:
        payload = f"{title}\n{company}\n{desc_text}"
    else:
        location = _norm(job.get("location", ""))
        payload = f"{title}\n{company}\n{location}\n{desc_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class JobDatabase:
    def __init__(self, db_path: str = "jobs_seen.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @contextmanager
    def _session(self):
        """Open a SQLite connection, commit/rollback transaction, and always close."""
        with contextlib.closing(self._get_connection()) as conn:
            with conn:
                yield conn

    def _init_db(self):
        with self._session() as conn:
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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS source_sync_state (
                    source TEXT PRIMARY KEY,
                    last_attempt_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS rotation_state (
                    state_key TEXT PRIMARY KEY,
                    next_index INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS delivered_fingerprints (
                    fingerprint TEXT PRIMARY KEY,
                    job_id TEXT,
                    title TEXT,
                    company TEXT,
                    first_seen_at TEXT
                )
                """
            )
            conn.commit()

    def claim_next_rotation_index(self, state_key: str, item_count: int) -> int:
        """Atomically return and advance a persisted round-robin cursor."""
        if item_count <= 0:
            raise ValueError("item_count must be greater than zero")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT next_index FROM rotation_state WHERE state_key = ?", (state_key,)
            ).fetchone()
            current_index = int(row[0]) % item_count if row else 0
            next_index = (current_index + 1) % item_count
            conn.execute(
                "INSERT INTO rotation_state(state_key, next_index, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(state_key) DO UPDATE SET "
                "next_index = excluded.next_index, updated_at = excluded.updated_at",
                (state_key, next_index, now),
            )
            conn.commit()
        return current_index

    def claim_source_poll(self, source: str, min_interval_seconds: int = 3600) -> bool:
        """Atomically rate-limit a source across local and GitHub Actions runs."""
        now = datetime.datetime.now(datetime.timezone.utc)
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT last_attempt_at FROM source_sync_state WHERE source = ?", (source,)
            ).fetchone()
            if row:
                try:
                    last_attempt = datetime.datetime.fromisoformat(row[0])
                    if (now - last_attempt).total_seconds() < min_interval_seconds:
                        conn.rollback()
                        return False
                except (TypeError, ValueError):
                    pass
            conn.execute(
                "INSERT INTO source_sync_state(source, last_attempt_at) VALUES (?, ?) "
                "ON CONFLICT(source) DO UPDATE SET last_attempt_at = excluded.last_attempt_at",
                (source, now.isoformat()),
            )
            conn.commit()
        return True

    def is_seen(self, job_id: str) -> bool:
        with self._session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

    def is_duplicate_delivered(self, job: Dict[str, Any], description: str = "") -> bool:
        """Return True if an alert with the same title, company, and description was already delivered."""
        fingerprint = compute_job_fingerprint(job, description)
        with self._session() as conn:
            row = conn.execute(
                "SELECT 1 FROM delivered_fingerprints WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            return row is not None

    def mark_delivered(self, job: Dict[str, Any], description: str = "") -> None:
        """Persist the content fingerprint of a successfully delivered job alert."""
        fingerprint = compute_job_fingerprint(job, description)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._session() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO delivered_fingerprints (
                    fingerprint, job_id, title, company, first_seen_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    job.get("id", ""),
                    job.get("title", ""),
                    job.get("company", ""),
                    now,
                ),
            )
            conn.commit()

    def add_job(self, job: Dict[str, Any]):
        with self._session() as conn:
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
        with self._session() as conn:
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

        with self._session() as conn:
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
            source_tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM source_db.sqlite_master WHERE type = 'table'"
                )
            }
            if "source_sync_state" in source_tables:
                conn.execute(
                    """
                    INSERT INTO source_sync_state(source, last_attempt_at)
                    SELECT source, last_attempt_at FROM source_db.source_sync_state
                    WHERE 1
                    ON CONFLICT(source) DO UPDATE SET last_attempt_at =
                        CASE WHEN excluded.last_attempt_at > source_sync_state.last_attempt_at
                        THEN excluded.last_attempt_at ELSE source_sync_state.last_attempt_at END
                    """
                )
            if "rotation_state" in source_tables:
                conn.execute(
                    """
                    INSERT INTO rotation_state(state_key, next_index, updated_at)
                    SELECT state_key, next_index, updated_at FROM source_db.rotation_state
                    WHERE 1
                    ON CONFLICT(state_key) DO UPDATE SET
                        next_index = CASE
                            WHEN excluded.updated_at > rotation_state.updated_at
                            THEN excluded.next_index ELSE rotation_state.next_index END,
                        updated_at = CASE
                            WHEN excluded.updated_at > rotation_state.updated_at
                            THEN excluded.updated_at ELSE rotation_state.updated_at END
                    """
                )
            if "delivered_fingerprints" in source_tables:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO delivered_fingerprints (
                        fingerprint, job_id, title, company, first_seen_at
                    )
                    SELECT
                        fingerprint, job_id, title, company, first_seen_at
                    FROM source_db.delivered_fingerprints
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
