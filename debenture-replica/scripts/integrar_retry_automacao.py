from pathlib import Path
import py_compile
import shutil

SERVICE = Path('src/debenture_search/services/collection_automation_service.py')
LOG_SERVICE = Path('src/debenture_search/services/operation_log_service.py')

for path in (SERVICE, LOG_SERVICE):
    if not path.exists():
        raise SystemExit(f'Arquivo nao encontrado: {path}')
    shutil.copy2(path, path.with_suffix(path.suffix + '.before_retry.bak'))

service = SERVICE.read_text(encoding='utf-8-sig')
log_service = LOG_SERVICE.read_text(encoding='utf-8-sig')

if 'from debenture_search.services.retry_policy import RetryPolicy' not in service:
    anchor = 'from debenture_search.services.debenture_export_service import DebentureExportService\n'
    replacement = anchor + 'from debenture_search.services.retry_policy import RetryPolicy\n'
    if anchor not in service:
        raise SystemExit('Import anchor nao encontrado no servico de automacao.')
    service = service.replace(anchor, replacement, 1)

old_method = '''    def _collect_with_attempts(self, provider, code, max_attempts):
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return provider.collect(code)
            except Exception as error:
                last_error = error
                if attempt >= max_attempts:
                    raise
        raise last_error
'''

new_method = '''    def _collect_with_attempts(self, provider, code, max_attempts):
        policy = RetryPolicy(max_attempts=max_attempts)

        for attempt in range(1, policy.max_attempts + 1):
            try:
                return provider.collect(code)
            except Exception as error:
                decision = policy.classify(error)

                if not policy.should_retry(error, attempt):
                    raise

                delay = policy.delay_for_attempt(attempt)

                if self.operation_log is not None:
                    self.operation_log.retry_scheduled(
                        asset_code=code,
                        attempt=attempt,
                        max_attempts=policy.max_attempts,
                        delay_seconds=delay,
                        category=decision.category,
                        http_status=decision.http_status,
                        error=error,
                    )

                self.sleep(delay)

        raise RuntimeError("Fluxo de retry terminou sem resultado.")
'''

if old_method in service:
    service = service.replace(old_method, new_method, 1)
elif 'policy = RetryPolicy(max_attempts=max_attempts)' not in service:
    raise SystemExit('Metodo _collect_with_attempts esperado nao foi encontrado.')

retry_method = '''    def retry_scheduled(
        self,
        asset_code,
        attempt,
        max_attempts,
        delay_seconds,
        category,
        error,
        http_status=None,
    ):
        """Registra uma nova tentativa permitida pela politica de retry."""

        self.log(
            "WARNING",
            "retry_scheduled",
            asset_code=str(asset_code),
            attempt=int(attempt),
            max_attempts=int(max_attempts),
            retry_delay_seconds=round(float(delay_seconds), 6),
            error_category=str(category),
            retryable=True,
            http_status=http_status,
            error_type=type(error).__name__,
            error_message=str(error),
        )

'''

if 'def retry_scheduled(' not in log_service:
    anchor = '    def backup_created(self, path, size_bytes=None, sha256=None):\n'
    if anchor not in log_service:
        raise SystemExit('Anchor de backup_created nao encontrado no servico de log.')
    log_service = log_service.replace(anchor, retry_method + anchor, 1)

SERVICE.write_text(service, encoding='utf-8')
LOG_SERVICE.write_text(log_service, encoding='utf-8')

try:
    py_compile.compile(str(SERVICE), doraise=True)
    py_compile.compile(str(LOG_SERVICE), doraise=True)
except Exception:
    shutil.copy2(SERVICE.with_suffix(SERVICE.suffix + '.before_retry.bak'), SERVICE)
    shutil.copy2(LOG_SERVICE.with_suffix(LOG_SERVICE.suffix + '.before_retry.bak'), LOG_SERVICE)
    raise

print('Integracao de retry aplicada com sucesso.')
print('Servico de automacao:', SERVICE)
print('Servico de log:', LOG_SERVICE)
print('Backups locais criados.')
print('Sintaxe: OK')
