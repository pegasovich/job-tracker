import pytest


class TestJobDatabase:
    """Tests for SQLite database operations and deduplication."""

    def test_init_creates_table(self, memory_db):
        """Verifies that the seen_jobs table is properly initialized."""
        with memory_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_jobs'"
            )
            assert cursor.fetchone() is not None

    def test_is_seen_returns_false_for_unknown_job(self, memory_db):
        """Unseen job ID should return False."""
        assert memory_db.is_seen("non_existent_id") is False
        assert memory_db.count_seen() == 0

    def test_add_job_marks_as_seen(self, memory_db, sample_job):
        """Adding a job should mark it as seen and increment counter."""
        memory_db.add_job(sample_job)

        assert memory_db.is_seen(sample_job["id"]) is True
        assert memory_db.count_seen() == 1

    def test_deduplication_ignores_duplicate_inserts(self, memory_db, sample_job):
        """Inserting the same job ID multiple times must not crash and count must stay 1."""
        memory_db.add_job(sample_job)
        # Attempt to insert identical job again
        memory_db.add_job(sample_job)

        assert memory_db.count_seen() == 1
        assert memory_db.is_seen(sample_job["id"]) is True

    def test_multiple_unique_jobs(self, memory_db, sample_job):
        """Adding multiple distinct jobs increments total count properly."""
        job2 = sample_job.copy()
        job2["id"] = "linkedin_789012"
        job2["title"] = "QA Lead"

        memory_db.add_job(sample_job)
        memory_db.add_job(job2)

        assert memory_db.count_seen() == 2
        assert memory_db.is_seen("linkedin_123456") is True
        assert memory_db.is_seen("linkedin_789012") is True

    def test_merge_from_adds_new_records_and_ignores_duplicates(self, tmp_path, sample_job):
        """merge_from should safely merge records from another db file without duplicates."""
        from database import JobDatabase

        db1_path = str(tmp_path / "db1.db")
        db2_path = str(tmp_path / "db2.db")

        db1 = JobDatabase(db1_path)
        db2 = JobDatabase(db2_path)

        db1.add_job(sample_job)  # id: linkedin_123456

        job2 = sample_job.copy()
        job2["id"] = "linkedin_999999"
        job2["title"] = "SDET II"
        db2.add_job(sample_job)  # duplicate of db1
        db2.add_job(job2)        # new unique job

        added = db1.merge_from(db2_path)
        assert added == 1
        assert db1.count_seen() == 2
        assert db1.is_seen("linkedin_123456") is True
        assert db1.is_seen("linkedin_999999") is True

    def test_merge_from_non_existent_file(self, tmp_path):
        """merge_from should return 0 if source database file does not exist."""
        from database import JobDatabase

        db_path = str(tmp_path / "db.db")
        db = JobDatabase(db_path)
        added = db.merge_from(str(tmp_path / "does_not_exist.db"))
        assert added == 0
