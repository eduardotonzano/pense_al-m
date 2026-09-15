import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    message: str
    details: object = None


@dataclass(frozen=True)
class QualityReport:
    generated_at: str
    status: str
    issue_count: int
    critical_count: int
    warning_count: int
    integrity: str
    foreign_key_violations: int
    issues: tuple


class QualityReportService:
    """Consolida qualidade de dados, integridade e arquivos de relatório."""

    def __init__(
        self,
        db,
        data_quality_service,
        output_dir="logs",
        now_function=None,
        operation_log=None,
    ):
        self.db = db
        self.data_quality_service = data_quality_service
        self.output_dir = Path(output_dir)
        self.now = now_function or (lambda: datetime.now(timezone.utc))
        self.operation_log = operation_log

    @staticmethod
    def _value(source, name, default=None):
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    @classmethod
    def _issue_to_dict(cls, issue):
        if isinstance(issue, dict):
            data = dict(issue)
        elif is_dataclass(issue):
            data = asdict(issue)
        elif hasattr(issue, "__dict__"):
            data = dict(vars(issue))
        else:
            data = {"message": str(issue)}

        severity = str(data.get("severity", data.get("level", "warning"))).lower()
        if severity in {"error", "critical", "fatal"}:
            severity = "critical"
        else:
            severity = "warning"

        return {
            "code": str(data.get("code", data.get("rule", "quality_issue"))),
            "severity": severity,
            "message": str(data.get("message", data.get("description", issue))),
            "details": data.get("details"),
        }

    def _run_quality_check(self):
        checker = self.data_quality_service
        if hasattr(checker, "check"):
            return checker.check()
        if hasattr(checker, "run"):
            return checker.run()
        raise TypeError("DataQualityService não possui método check() ou run().")

    def build(self):
        raw_report = self._run_quality_check()
        raw_issues = self._value(raw_report, "issues", ()) or ()
        issues = [self._issue_to_dict(issue) for issue in raw_issues]

        integrity = str(self.db.integrity_check())
        foreign_keys = list(self.db.foreign_key_check() or [])

        if integrity != "ok":
            issues.append(
                {
                    "code": "sqlite_integrity",
                    "severity": "critical",
                    "message": "A verificação de integridade do SQLite falhou.",
                    "details": {"result": integrity},
                }
            )

        if foreign_keys:
            issues.append(
                {
                    "code": "foreign_key_violation",
                    "severity": "critical",
                    "message": "Foram encontradas violações de foreign keys.",
                    "details": {"violations": foreign_keys},
                }
            )

        critical_count = sum(item["severity"] == "critical" for item in issues)
        warning_count = sum(item["severity"] == "warning" for item in issues)

        if critical_count:
            status = "failed"
        elif warning_count:
            status = "success_with_warnings"
        else:
            status = "success"

        report = QualityReport(
            generated_at=self.now().isoformat(),
            status=status,
            issue_count=len(issues),
            critical_count=critical_count,
            warning_count=warning_count,
            integrity=integrity,
            foreign_key_violations=len(foreign_keys),
            issues=tuple(issues),
        )

        if self.operation_log is not None:
            self.operation_log.log(
                "ERROR" if status == "failed" else "WARNING" if warning_count else "INFO",
                "quality_check_completed",
                status=status,
                issue_count=report.issue_count,
                critical_count=critical_count,
                warning_count=warning_count,
                integrity=integrity,
                foreign_key_violations=len(foreign_keys),
            )

        return report

    @staticmethod
    def to_dict(report):
        data = asdict(report) if is_dataclass(report) else dict(report)
        data["issues"] = list(data.get("issues", ()))
        return data

    def write(self, report):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        latest_path = self.output_dir / "quality_last.json"
        history_path = self.output_dir / "quality_history.jsonl"
        data = self.to_dict(report)

        latest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with history_path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            file.write("\n")

        return {"latest_path": latest_path, "history_path": history_path}

    def run(self, write=True):
        report = self.build()
        paths = self.write(report) if write else {
            "latest_path": None,
            "history_path": None,
        }
        return report, paths
