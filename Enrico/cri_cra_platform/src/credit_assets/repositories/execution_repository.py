from __future__ import annotations
from datetime import datetime, timezone
import sqlite3

class ExecutionRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def start(self, run_id: str) -> None:
        self.connection.execute("INSERT INTO executions (run_id,started_at,status) VALUES (?,?,?)", (run_id, datetime.now(timezone.utc).isoformat(), "running"))
        self.connection.commit()

    def finish(self, run_id: str, status: str, duration: float, assets: int, documents: int, warnings: int, errors: int) -> None:
        self.connection.execute("""UPDATE executions SET finished_at=?,status=?,duration_seconds=?,assets_processed=?,documents_found=?,warning_count=?,error_count=? WHERE run_id=?""", (datetime.now(timezone.utc).isoformat(),status,duration,assets,documents,warnings,errors,run_id))
        self.connection.commit()
