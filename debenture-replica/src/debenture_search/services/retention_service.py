import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class RetentionRule:
    name: str
    directory: Path
    pattern: str
    days: int
    keep_latest: bool = False


@dataclass(frozen=True)
class RetentionItem:
    rule: str
    path: Path
    size_bytes: int
    modified_at: str
    eligible: bool
    protected: bool
    reason: str
    removed: bool = False
    error: str | None = None


@dataclass(frozen=True)
class RetentionResult:
    scanned: int
    eligible: int
    removed: int
    failed: int
    bytes_eligible: int
    bytes_removed: int
    items: tuple


class RetentionService:
    """Aplica retenção segura em arquivos operacionais do projeto."""

    def __init__(self, project_root=".", now_function=None, operation_log=None):
        self.project_root = Path(project_root).resolve()
        self.now = now_function or (lambda: datetime.now(timezone.utc))
        self.operation_log = operation_log

    @staticmethod
    def load_config(path):
        candidate = Path(path)
        if not candidate.exists():
            raise ValueError("Arquivo de configuração de retenção não encontrado.")

        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as error:
            raise ValueError("O arquivo de retenção possui JSON inválido.") from error

        if not isinstance(data, dict):
            raise ValueError("A configuração de retenção deve ser um objeto JSON.")

        required_days = (
            "backup_days",
            "log_days",
            "report_days",
            "export_days",
            "temporary_days",
            "code_backup_days",
        )
        for field in required_days:
            value = int(data.get(field, 0))
            if value < 1:
                raise ValueError(field + " deve ser maior que zero.")
            data[field] = value

        protected = data.get("protected_files", [])
        if not isinstance(protected, list):
            raise ValueError("protected_files deve ser uma lista.")
        data["protected_files"] = tuple(str(value) for value in protected)
        data["keep_latest_backup"] = bool(data.get("keep_latest_backup", True))
        data["keep_latest_report"] = bool(data.get("keep_latest_report", True))
        return data

    def _safe_path(self, path):
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError("A retenção recusou um caminho fora do projeto.") from error
        return resolved

    def _rules(self, config):
        return (
            RetentionRule(
                "backups",
                self.project_root / "data" / "backups",
                "*",
                config["backup_days"],
                config["keep_latest_backup"],
            ),
            RetentionRule(
                "logs",
                self.project_root / "logs",
                "*.log.*",
                config["log_days"],
            ),
            RetentionRule(
                "jsonl_logs",
                self.project_root / "logs",
                "*.jsonl.*",
                config["log_days"],
            ),
            RetentionRule(
                "reports",
                self.project_root / "logs",
                "collection_*.json",
                config["report_days"],
                config["keep_latest_report"],
            ),
            RetentionRule(
                "exports",
                self.project_root / "exports",
                "*",
                config["export_days"],
            ),
            RetentionRule(
                "temporary",
                self.project_root / "runtime",
                "*.tmp",
                config["temporary_days"],
            ),
            RetentionRule(
                "code_backups_src",
                self.project_root / "src",
                "*.bak",
                config["code_backup_days"],
            ),
            RetentionRule(
                "code_backups_scripts",
                self.project_root / "scripts",
                "*.bak",
                config["code_backup_days"],
            ),
        )

    def _protected_paths(self, config):
        result = set()
        for value in config["protected_files"]:
            candidate = self._safe_path(self.project_root / value)
            result.add(candidate)
        return result

    def _collect_candidates(self, rule):
        directory = self._safe_path(rule.directory)
        if not directory.exists():
            return []

        candidates = []
        for path in directory.rglob(rule.pattern):
            if path.is_symlink() or not path.is_file():
                continue
            candidates.append(self._safe_path(path))
        return sorted(set(candidates), key=lambda item: str(item).casefold())

    def plan(self, config):
        protected_paths = self._protected_paths(config)
        items = []

        for rule in self._rules(config):
            candidates = self._collect_candidates(rule)
            latest = None
            if rule.keep_latest and candidates:
                latest = max(candidates, key=lambda path: path.stat().st_mtime)

            cutoff = self.now() - timedelta(days=rule.days)
            for path in candidates:
                stat = path.stat()
                modified = datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                )
                explicitly_protected = path in protected_paths
                latest_protected = latest is not None and path == latest
                is_protected = explicitly_protected or latest_protected
                expired = modified < cutoff
                eligible = expired and not is_protected

                if explicitly_protected:
                    reason = "arquivo protegido pela configuração"
                elif latest_protected:
                    reason = "arquivo mais recente preservado"
                elif expired:
                    reason = "prazo de retenção vencido"
                else:
                    reason = "arquivo dentro do prazo"

                items.append(
                    RetentionItem(
                        rule=rule.name,
                        path=path,
                        size_bytes=stat.st_size,
                        modified_at=modified.isoformat(),
                        eligible=eligible,
                        protected=is_protected,
                        reason=reason,
                    )
                )

        return tuple(sorted(items, key=lambda item: str(item.path).casefold()))

    def run(self, config, commit=False):
        planned = self.plan(config)
        result_items = []

        for item in planned:
            if not item.eligible or not commit:
                result_items.append(item)
                continue

            try:
                safe_path = self._safe_path(item.path)
                if safe_path.is_symlink():
                    raise ValueError("Links simbólicos não podem ser removidos.")
                safe_path.unlink()
                updated = RetentionItem(**{**item.__dict__, "removed": True})
                if self.operation_log is not None:
                    self.operation_log.log(
                        "INFO",
                        "retention_file_removed",
                        path=safe_path,
                        size_bytes=item.size_bytes,
                        rule=item.rule,
                    )
            except Exception as error:
                updated = RetentionItem(
                    **{
                        **item.__dict__,
                        "error": type(error).__name__ + ": " + str(error),
                    }
                )
                if self.operation_log is not None:
                    self.operation_log.log(
                        "ERROR",
                        "retention_file_failed",
                        path=item.path,
                        rule=item.rule,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
            result_items.append(updated)

        eligible_items = [item for item in result_items if item.eligible]
        removed_items = [item for item in result_items if item.removed]
        failed_items = [item for item in result_items if item.error is not None]

        return RetentionResult(
            scanned=len(result_items),
            eligible=len(eligible_items),
            removed=len(removed_items),
            failed=len(failed_items),
            bytes_eligible=sum(item.size_bytes for item in eligible_items),
            bytes_removed=sum(item.size_bytes for item in removed_items),
            items=tuple(result_items),
        )
