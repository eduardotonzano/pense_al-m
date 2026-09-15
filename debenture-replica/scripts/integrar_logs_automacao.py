from pathlib import Path
import py_compile
import shutil

SERVICE = Path('src/debenture_search/services/collection_automation_service.py')
SCRIPT = Path('scripts/run_collection.py')

for path in (SERVICE, SCRIPT):
    if not path.exists():
        raise SystemExit(f'Arquivo nao encontrado: {path}')
    shutil.copy2(path, path.with_suffix(path.suffix + '.before_logging.bak'))

service = SERVICE.read_text(encoding='utf-8-sig')
if 'operation_log_service=None' not in service:
    service = service.replace(
        '        now_function=None,\n    ):',
        '        now_function=None,\n        operation_log_service=None,\n    ):',
        1,
    )
    service = service.replace(
        '        self.now = now_function or (lambda: datetime.now(timezone.utc))',
        '        self.now = now_function or (lambda: datetime.now(timezone.utc))\n'
        '        self.operation_log = operation_log_service',
        1,
    )

if 'automation_started(' not in service:
    service = service.replace(
        '    def run(self, config, commit=False):\n',
        '    def run(self, config, commit=False):\n'
        '        automation_started_at = time.perf_counter()\n'
        '        if self.operation_log is not None:\n'
        '            self.operation_log.automation_started(\n'
        '                len(config.asset_codes),\n'
        '                commit,\n'
        '            )\n',
        1,
    )
    service = service.replace(
        '        if commit and config.create_backup:\n'
        '            backup_path = self.backup_service.create_backup().path\n',
        '        if commit and config.create_backup:\n'
        '            backup_record = self.backup_service.create_backup()\n'
        '            backup_path = backup_record.path\n'
        '            if self.operation_log is not None:\n'
        '                self.operation_log.backup_created(\n'
        '                    backup_record.path,\n'
        '                    getattr(backup_record, "size_bytes", None),\n'
        '                    getattr(backup_record, "sha256", None),\n'
        '                )\n',
        1,
    )
    service = service.replace(
        '        for index, code in enumerate(config.asset_codes):\n'
        '            try:\n',
        '        for index, code in enumerate(config.asset_codes):\n'
        '            asset_started_at = time.perf_counter()\n'
        '            if self.operation_log is not None:\n'
        '                self.operation_log.asset_started(code, attempt=1)\n'
        '            try:\n',
        1,
    )
    service = service.replace(
        '            except Exception as error:\n'
        '                items.append(\n',
        '                if self.operation_log is not None:\n'
        '                    self.operation_log.asset_succeeded(\n'
        '                        code,\n'
        '                        time.perf_counter() - asset_started_at,\n'
        '                        attempt=1,\n'
        '                    )\n'
        '            except Exception as error:\n'
        '                if self.operation_log is not None:\n'
        '                    self.operation_log.asset_failed(\n'
        '                        code,\n'
        '                        error,\n'
        '                        time.perf_counter() - asset_started_at,\n'
        '                        attempt=1,\n'
        '                    )\n'
        '                items.append(\n',
        1,
    )
    service = service.replace(
        '        failures = sum(item["status"] == "failed" for item in items)\n'
        '        return AutomationResult(\n',
        '        failures = sum(item["status"] == "failed" for item in items)\n'
        '        if self.operation_log is not None:\n'
        '            self.operation_log.integrity_checked(\n'
        '                self.db.integrity_check(),\n'
        '                self.db.foreign_key_check(),\n'
        '            )\n'
        '            self.operation_log.automation_finished(\n'
        '                len(items) - failures,\n'
        '                failures,\n'
        '                time.perf_counter() - automation_started_at,\n'
        '            )\n'
        '        return AutomationResult(\n',
        1,
    )

script = SCRIPT.read_text(encoding='utf-8-sig')
if 'configure_operational_logging' not in script:
    script = script.replace(
        'from debenture_search.database import database\n',
        'from debenture_search.database import database\n'
        'from debenture_search.logging_config import (\n'
        '    close_operational_logging,\n'
        '    configure_operational_logging,\n'
        ')\n'
        'from debenture_search.services.operation_log_service import (\n'
        '    OperationLogService,\n'
        ')\n',
        1,
    )
    script = script.replace(
        '        result = CollectionAutomationService(database).run(\n'
        '            config,\n'
        '            commit=arguments.commit,\n'
        '        )\n',
        '        logging_state = configure_operational_logging("logs")\n'
        '        try:\n'
        '            operation_log = OperationLogService(logging_state["logger"])\n'
        '            result = CollectionAutomationService(\n'
        '                database,\n'
        '                operation_log_service=operation_log,\n'
        '            ).run(\n'
        '                config,\n'
        '                commit=arguments.commit,\n'
        '            )\n'
        '        finally:\n'
        '            close_operational_logging(logging_state["logger"])\n',
        1,
    )

SERVICE.write_text(service, encoding='utf-8')
SCRIPT.write_text(script, encoding='utf-8')
try:
    py_compile.compile(str(SERVICE), doraise=True)
    py_compile.compile(str(SCRIPT), doraise=True)
except Exception:
    shutil.copy2(SERVICE.with_suffix(SERVICE.suffix + '.before_logging.bak'), SERVICE)
    shutil.copy2(SCRIPT.with_suffix(SCRIPT.suffix + '.before_logging.bak'), SCRIPT)
    raise

print('Integracao de logs aplicada.')
print('Servico:', SERVICE)
print('Script:', SCRIPT)
print('Backups locais criados.')
print('Sintaxe: OK')
