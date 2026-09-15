from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class HealthReport:
    timestamp: str
    health: str
    collection_status: str
    quality_status: str
    critical_count: int
    warning_count: int
    open_alerts: list[str]


class HealthMonitorService:

    def __init__(
        self,
        logs_directory="logs",
        runtime_directory="runtime",
    ):
        self.logs_directory = Path(logs_directory)
        self.runtime_directory = Path(runtime_directory)

    def build_report(self):

        collection = self._load_json(
            self.logs_directory / "collection_last.json"
        )

        quality = self._load_json(
            self.logs_directory / "quality_last.json"
        )

        alerts = []

        lock_file = (
            self.runtime_directory
            / "collection.lock"
        )

        if lock_file.exists():
            alerts.append("STALE_LOCK")

        critical_count = int(
            quality.get(
                "critical_count",
                0,
            )
        )

        warning_count = int(
            quality.get(
                "warning_count",
                0,
            )
        )

        health = "healthy"

        if warning_count > 0:
            health = "warning"

        if critical_count > 0:
            health = "critical"

        if alerts and health == "healthy":
            health = "warning"

        return HealthReport(
            timestamp=datetime.now().isoformat(),
            health=health,
            collection_status=collection.get(
                "status",
                "unknown",
            ),
            quality_status=quality.get(
                "status",
                "unknown",
            ),
            critical_count=critical_count,
            warning_count=warning_count,
            open_alerts=alerts,
        )

    def save_report(self):

        report = self.build_report()

        self.logs_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        latest_file = (
            self.logs_directory
            / "health_last.json"
        )

        history_file = (
            self.logs_directory
            / "health_history.jsonl"
        )

        data = asdict(report)

        latest_file.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with history_file.open(
            "a",
            encoding="utf-8",
        ) as file:

            file.write(
                json.dumps(
                    data,
                    ensure_ascii=False,
                )
            )

            file.write("\n")

        return report

    @staticmethod
    def _load_json(path):

        if not Path(path).exists():
            return {}

        return json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )