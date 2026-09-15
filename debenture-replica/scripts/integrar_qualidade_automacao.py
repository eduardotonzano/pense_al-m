from pathlib import Path
import py_compile
import shutil

SCRIPT = Path("scripts/run_collection.py")
BACKUP = SCRIPT.with_suffix(SCRIPT.suffix + ".before_quality.bak")

if not SCRIPT.exists():
    raise SystemExit(f"Arquivo nao encontrado: {SCRIPT}")

shutil.copy2(SCRIPT, BACKUP)
code = SCRIPT.read_text(encoding="utf-8-sig")

imports = '''from debenture_search.services.data_quality_service import DataQualityService
from debenture_search.services.quality_report_service import QualityReportService
'''

if "QualityReportService" not in code:
    anchor = "from debenture_search.services.operation_log_service import (\n    OperationLogService,\n)\n"
    if anchor not in code:
        raise SystemExit("Ponto de insercao dos imports nao encontrado.")
    code = code.replace(anchor, anchor + imports, 1)

old_signature = "def result_to_dict(result, committed):"
new_signature = "def result_to_dict(result, committed, quality_report=None, quality_paths=None):"
if old_signature in code:
    code = code.replace(old_signature, new_signature, 1)

if '"quality": (' not in code:
    anchor = '        "items": list(result.items),\n'
    addition = '''        "quality": (
            None
            if quality_report is None
            else QualityReportService.to_dict(quality_report)
        ),
        "quality_files": {
            key: None if value is None else str(value)
            for key, value in (quality_paths or {}).items()
        },
'''
    if anchor not in code:
        raise SystemExit("Ponto de insercao do relatorio nao encontrado.")
    code = code.replace(anchor, anchor + addition, 1)

old_report = '''            report_path = write_report(
                arguments.report,
                result_to_dict(
                    result,
                    arguments.commit,
                ),
            )
'''
new_report = '''            quality_report, quality_paths = QualityReportService(
                database,
                DataQualityService(database),
                output_dir="logs",
                operation_log=operation_log,
            ).run(write=True)

            report_path = write_report(
                arguments.report,
                result_to_dict(
                    result,
                    arguments.commit,
                    quality_report=quality_report,
                    quality_paths=quality_paths,
                ),
            )
'''

if old_report in code:
    code = code.replace(old_report, new_report, 1)
elif "quality_report, quality_paths = QualityReportService(" not in code:
    compact = '''        report_path = write_report(
            arguments.report,
            result_to_dict(result, arguments.commit),
        )
'''
    compact_new = '''        quality_report, quality_paths = QualityReportService(
            database,
            DataQualityService(database),
            output_dir="logs",
            operation_log=operation_log,
        ).run(write=True)

        report_path = write_report(
            arguments.report,
            result_to_dict(
                result,
                arguments.commit,
                quality_report=quality_report,
                quality_paths=quality_paths,
            ),
        )
'''
    if compact not in code:
        raise SystemExit("Bloco de gravacao do relatorio nao encontrado.")
    code = code.replace(compact, compact_new, 1)

if 'print("Qualidade:",' not in code:
    anchor = '    print("Foreign keys:", database.foreign_key_check())\n'
    addition = '''    if quality_report is not None:
        print("Qualidade:", quality_report.status)
        print("Problemas de qualidade:", quality_report.issue_count)
        print("Criticos:", quality_report.critical_count)
        print("Alertas:", quality_report.warning_count)
'''
    if anchor in code:
        code = code.replace(anchor, anchor + addition, 1)

old_print_signature = '''def print_result(
    result,
    report_path,
    committed,
):'''
new_print_signature = '''def print_result(
    result,
    report_path,
    committed,
    quality_report=None,
):'''
if old_print_signature in code:
    code = code.replace(old_print_signature, new_print_signature, 1)
elif "def print_result(result, report_path, committed):" in code:
    code = code.replace(
        "def print_result(result, report_path, committed):",
        "def print_result(result, report_path, committed, quality_report=None):",
        1,
    )

old_print_call = '''    print_result(
        result,
        report_path,
        arguments.commit,
    )
'''
new_print_call = '''    print_result(
        result,
        report_path,
        arguments.commit,
        quality_report=quality_report,
    )
'''
if old_print_call in code:
    code = code.replace(old_print_call, new_print_call, 1)
elif "print_result(result, report_path, arguments.commit)" in code:
    code = code.replace(
        "print_result(result, report_path, arguments.commit)",
        "print_result(result, report_path, arguments.commit, quality_report=quality_report)",
        1,
    )

if "quality_report = None" not in code:
    marker = "    report_path = None\n"
    if marker in code:
        code = code.replace(marker, marker + "    quality_report = None\n    quality_paths = {}\n", 1)

SCRIPT.write_text(code, encoding="utf-8")

try:
    py_compile.compile(str(SCRIPT), doraise=True)
except Exception:
    shutil.copy2(BACKUP, SCRIPT)
    raise

print("Integracao de qualidade aplicada com sucesso.")
print("Script:", SCRIPT)
print("Backup:", BACKUP)
print("Sintaxe: OK")
