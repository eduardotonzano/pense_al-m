from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import ensure_schema_current
from credit_assets.repositories.document_version_repository import (
    DocumentVersionRepository,
)
from credit_assets.services.document_download_service import (
    MAX_SAMPLE_DOCUMENTS,
    SAMPLE_CATEGORIES,
    DocumentDownloadService,
)


def write_reports(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Execução de download da amostra",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Ativo: `{report['asset']['codigo_cetip']}` / `{report['asset']['isin']}`",
        f"- Dry run: **{report['dry_run']}**",
        f"- Categorias encontradas: {', '.join(report['found_categories']) or 'nenhuma'}",
        f"- Categorias ausentes: {', '.join(report['missing_categories']) or 'nenhuma'}",
        f"- Observação de categorias: {report['category_classification_note']}",
        f"- Linhas da grade verificadas para ISIN: "
        f"{report['description_validation']['live_grade_rows_isin_verified']}",
        f"- Todas as linhas selecionadas verificadas: "
        f"{report['description_validation']['all_selected_rows_verified']}",
        "",
        "## Documentos selecionados",
        "",
    ]
    for document in report["selected_documents"]:
        lines.append(
            f"- `{document['source_document_id']}` — {document['category']} — "
            f"{document['document_name']} — "
            f"`{document.get('planned_directory', '')}/"
            f"{document.get('planned_filename', '')}`"
        )
    lines.extend(["", "## Arquivos", ""])
    for item in report["files_downloaded"]:
        lines.append(
            f"- `{item['source_document_id']}`: {item['result']}, "
            f"{item.get('format')} / {item.get('size_bytes')} bytes, "
            f"SHA-256 `{item.get('file_hash')}`, `{item.get('local_file_path')}`"
        )
    lines.extend([
        "",
        "## Métricas",
        "",
        f"- inserted: {report['inserted']}",
        f"- updated: {report['updated']}",
        f"- unchanged: {report['unchanged']}",
        f"- new_version: {report['new_version']}",
        f"- duplicate_content: {report['duplicate_content']}",
        f"- failed: {report['failed']}",
        f"- tentativas operacionais registradas: {report['attempts_recorded']}",
        f"- temporários removidos: {report['files_removed']}",
        f"- diretório temporário removido: {report.get('temporary_directory_removed')}",
        f"- duração: {report['duration_seconds']}s",
        "",
        "## Erros",
        "",
    ])
    lines.extend(
        [f"- `{error.get('source_document_id', '')}`: {error['error']}" for error in report["errors"]]
        or ["- Nenhum."]
    )
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-documents",
        type=int,
        default=MAX_SAMPLE_DOCUMENTS,
        choices=range(1, MAX_SAMPLE_DOCUMENTS + 1),
    )
    parser.add_argument("--category", choices=SAMPLE_CATEGORIES)
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        help="source_document_id explícito (repetível ou separado por vírgula)",
    )
    parser.add_argument(
        "--allow-other", action="store_true",
        help="com --source-id, aceita documentos da categoria Outro (ex.: comunicados)",
    )
    parser.add_argument(
        "--max-megabytes", type=int, default=25, choices=range(1, 201), metavar="1-200",
        help="limite de tamanho por arquivo (padrão 25); acima dele o download é recusado",
    )
    args = parser.parse_args()
    source_ids = (
        [part for value in args.source_ids for part in value.split(",")]
        if args.source_ids else None
    )
    if source_ids and args.category:
        parser.error("--source-id não pode ser combinado com --category")
    report_stem = (
        f"{args.cetip.lower()}_sample_download_by_id_latest"
        if source_ids else "cafe_brasil_sample_download_latest"
    )

    database = ROOT / "data" / "cri_cra.db"
    connection = connect(database)
    initialize_database(connection)
    ensure_schema_current(connection)
    try:
        service = DocumentDownloadService(
            connection,
            DocumentVersionRepository(connection),
            ROOT,
            max_bytes=args.max_megabytes * 1_000_000,
        )
        categories = [args.category] if args.category else None
        report = service.run(
            args.cetip,
            args.isin,
            dry_run=args.dry_run,
            max_documents=args.max_documents,
            categories=categories,
            source_document_ids=source_ids,
            allow_other=args.allow_other,
        )
        write_reports(
            report,
            ROOT / "reports" / f"{report_stem}.json",
            ROOT / "reports" / f"{report_stem}.md",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["failed"] == 0 else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
