from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    issue_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS issues (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    external_id TEXT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    issue_url TEXT,
                    raw_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id)
                );

                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id)
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    issue_id TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    requires_human INTEGER NOT NULL,
                    diagnosis_json TEXT NOT NULL,
                    html_report TEXT NOT NULL,
                    rerun_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id),
                    FOREIGN KEY(issue_id) REFERENCES issues(id)
                );

                CREATE TABLE IF NOT EXISTS human_feedback (
                    id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    human_note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(report_id) REFERENCES reports(id),
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id)
                );
                '''
            )
