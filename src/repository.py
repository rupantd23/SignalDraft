import json
import sqlite3
from pathlib import Path
from typing import Protocol

from src.config import Settings, settings
from src.models import ResearchRun


class RunRepository(Protocol):
    def save(self, run: ResearchRun) -> None: ...

    def get(self, run_id: str, owner_id: str | None = None) -> ResearchRun | None: ...

    def list_recent(
        self, limit: int = 50, owner_id: str | None = None
    ) -> list[ResearchRun]: ...


class SQLiteRepository:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_runs (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT,
                    created_at TEXT NOT NULL,
                    prospect_name TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(research_runs)")
            }
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE research_runs ADD COLUMN owner_id TEXT")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def save(self, run: ResearchRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO research_runs
                    (id, created_at, prospect_name, company_name, outcome,
                     review_status, owner_id, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    outcome = excluded.outcome,
                    review_status = excluded.review_status,
                    owner_id = excluded.owner_id,
                    payload = excluded.payload
                """,
                (
                    run.id,
                    run.created_at.isoformat(),
                    run.prospect.full_name,
                    run.prospect.company_name,
                    run.outcome,
                    run.review_status,
                    run.owner_id,
                    run.model_dump_json(),
                ),
            )

    def get(self, run_id: str, owner_id: str | None = None) -> ResearchRun | None:
        with self._connect() as connection:
            if owner_id:
                row = connection.execute(
                    "SELECT payload FROM research_runs WHERE id = ? AND owner_id = ?",
                    (run_id, owner_id),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT payload FROM research_runs WHERE id = ?", (run_id,)
                ).fetchone()
        return ResearchRun.model_validate_json(row[0]) if row else None

    def list_recent(
        self, limit: int = 50, owner_id: str | None = None
    ) -> list[ResearchRun]:
        with self._connect() as connection:
            if owner_id:
                rows = connection.execute(
                    """
                    SELECT payload FROM research_runs
                    WHERE owner_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (owner_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT payload FROM research_runs
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [ResearchRun.model_validate_json(row[0]) for row in rows]


class SupabaseRepository:
    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self.client = create_client(url, key)
        self.table_name = "research_runs"

    def save(self, run: ResearchRun) -> None:
        self.client.table(self.table_name).upsert(
            {
                "id": run.id,
                "owner_id": run.owner_id,
                "created_at": run.created_at.isoformat(),
                "prospect_name": run.prospect.full_name,
                "company_name": run.prospect.company_name,
                "outcome": run.outcome,
                "review_status": run.review_status,
                "payload": run.model_dump(mode="json"),
            }
        ).execute()

    def get(self, run_id: str, owner_id: str | None = None) -> ResearchRun | None:
        query = self.client.table(self.table_name).select("payload").eq("id", run_id)
        if owner_id:
            query = query.eq("owner_id", owner_id)
        response = query.limit(1).execute()
        if not response.data:
            return None
        payload = response.data[0]["payload"]
        return ResearchRun.model_validate(payload)

    def list_recent(
        self, limit: int = 50, owner_id: str | None = None
    ) -> list[ResearchRun]:
        query = self.client.table(self.table_name).select("payload")
        if owner_id:
            query = query.eq("owner_id", owner_id)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return [ResearchRun.model_validate(row["payload"]) for row in response.data]


def create_repository(config: Settings = settings) -> RunRepository:
    if config.supabase_configured:
        return SupabaseRepository(config.supabase_url, config.supabase_key)
    return SQLiteRepository(config.sqlite_path)
