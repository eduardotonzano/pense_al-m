from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
import uuid
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.collectors.fundosnet_collector import FundosNetCollector
from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import ensure_schema_current
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_repository import DocumentRepository
from credit_assets.repositories.execution_repository import ExecutionRepository
from credit_assets.services.catalog_service import CatalogService


def load_assets(path: Path, only: str | None = None) -> list[Asset]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return [
            Asset(
                codigo_cetip=row["codigo_cetip"],
                isin=row.get("isin", ""),
                tipo_ativo=row["tipo_ativo"].strip().upper(),
                securitizadora=row["securitizadora"],
                cnpj_securitizadora=row["cnpj_securitizadora"],
                emissao=row["emissao"],
                serie=row["serie"],
                devedor=row.get("devedor", ""),
                cnpj_devedor=row.get("cnpj_devedor", ""),
            )
            for row in csv.DictReader(source)
            if row.get("ativo", "").strip().lower() == "true"
            and row.get("isin", "").strip()
            and (
                only is None
                or only.strip().upper()
                in {
                    row["codigo_cetip"].strip().upper(),
                    row["isin"].strip().upper(),
                }
            )
        ]


def fixture_documents(asset: Asset) -> list[dict]:
    prefix = "cafe" if asset.isin == "BRECOACRABX0" else "almeida"
    return [
        {
            "id": f"{prefix}-001",
            "tipo": "Informe Mensal de CRI",
            "nome": f"Informe {prefix}",
            "url": f"https://fnet.example/{prefix}/001",
            "data_referencia": "2026-08-01",
        },
        {
            "id": f"{prefix}-002",
            "tipo": "Termo de Securitização",
            "nome": f"Termo {prefix}",
            "url": f"https://fnet.example/{prefix}/002",
            "data_referencia": "2026-08-02",
        },
    ]


def existing_document_keys(
    database_path: Path,
) -> tuple[set[tuple[str, str]], str | None]:
    """Chaves (source_document_id, source) ja gravadas, so em leitura."""
    if not database_path.is_file():
        return set(), None
    try:
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA query_only = ON")
            rows = connection.execute(
                "SELECT source_document_id, source FROM documents"
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        return set(), f"{type(error).__name__}: {error}"
    return {(str(key), str(source)) for key, source in rows}, None


def dry_run_catalog(
    offline: bool,
    only: str | None,
    database_path: Path,
    config_path: Path,
) -> dict:
    """Le o catalogo e mostra o que mudaria. Nao grava banco, CSV nem relatorio."""
    existing, warning = existing_document_keys(database_path)
    collector = None if offline else FundosNetCollector()
    catalog_service = None if offline else CatalogService(collector)
    run_id = "dry-run"
    result: dict = {
        "dry_run": True,
        "database": str(database_path),
        "database_existe": database_path.is_file(),
        "avisos": [warning] if warning else [],
        "assets": [],
        "documents_found": 0,
        "errors": 0,
    }
    for source_asset in load_assets(config_path, only):
        entry: dict = {
            "codigo_cetip": source_asset.codigo_cetip,
            "isin": source_asset.isin,
        }
        try:
            asset = replace(source_asset, asset_id=0)
            if offline:
                rows = fixture_documents(asset)
                documents = [
                    FundosNetCollector._to_document(asset, row, run_id)
                    for row in rows
                ]
                metrics = {
                    "total_reported": len(rows),
                    "pages_queried": 1,
                    "rejected": [],
                    "errors": [],
                }
            else:
                collected = catalog_service.catalog_with_metrics(asset, run_id)
                documents = collected.documents
                metrics = {
                    "total_reported": collected.total_reported,
                    "pages_queried": collected.pages_queried,
                    "rejected": collected.rejected,
                    "errors": collected.errors,
                }
            raw_rows = [
                json.loads(document.source_row_json)
                for document in documents
                if document.source_row_json
            ]
            new = [
                document
                for document in documents
                if (str(document.source_document_id), document.source) not in existing
            ]
            entry.update({
                "total_informado": metrics["total_reported"],
                "paginas_consultadas": metrics["pages_queried"],
                "documentos_recebidos": len(documents),
                "documentos_novos": len(new),
                "documentos_existentes": len(documents) - len(new),
                "categorias_pelo_classificador_atual": dict(
                    Counter(document.category for document in documents)
                ),
                "chaves_json_vistas": dict(
                    Counter(key for row in raw_rows for key in row)
                ),
                "campos_da_grade_preenchidos": {
                    column: sum(
                        1 for document in documents if getattr(document, column)
                    )
                    for column in (
                        "source_category",
                        "source_type",
                        "source_species",
                        "grid_version",
                        "source_description",
                        "reference_date",
                    )
                },
                "exemplos": raw_rows[:3],
                "documentos_rejeitados": metrics["rejected"],
                "erros": metrics["errors"],
            })
            result["documents_found"] += len(documents)
            result["errors"] += len(metrics["errors"])
        except Exception as error:
            result["errors"] += 1
            entry["erros"] = [f"{type(error).__name__}: {error}"]
        result["assets"].append(entry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run(
    offline: bool = False,
    only: str | None = None,
    database_path: Path | None = None,
    config_path: Path | None = None,
    output_path: Path | None = None,
    report_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    database_path = database_path or ROOT / "data" / "cri_cra.db"
    config_path = config_path or ROOT / "config" / "ativos_piloto.csv"
    if dry_run:
        return dry_run_catalog(offline, only, database_path, config_path)
    output_path = output_path or ROOT / "data" / "catalogo_documentos.csv"
    report_path = report_path or ROOT / "reports" / "document_catalog_latest.json"
    connection = connect(database_path)
    initialize_database(connection)
    ensure_schema_current(connection)
    assets_repo = AssetRepository(connection)
    documents_repo = DocumentRepository(connection)
    collector = None if offline else FundosNetCollector()
    catalog_service = None if offline else CatalogService(collector)
    execution = ExecutionRepository(connection)
    run_id = uuid.uuid4().hex
    execution.start(run_id)
    result = {
        "run_id": run_id,
        "assets": [],
        "before_documents": documents_repo.count(),
        "after_documents": 0,
    }
    inserted = updated = unchanged = rejected = errors = 0
    documents_found = assets_processed = 0
    started = time.perf_counter()
    try:
        for source_asset in load_assets(config_path, only):
            assets_processed += 1
            asset_id = None
            before = documents_repo.count()
            try:
                asset_id = assets_repo.upsert(source_asset)
                asset = replace(source_asset, asset_id=asset_id)
                before = documents_repo.count_by_asset_id(asset_id)
                if offline:
                    rows = fixture_documents(asset)
                    documents = [
                        FundosNetCollector._to_document(asset, row, run_id)
                        for row in rows
                    ]
                    metrics = {
                        "administrator_id": None,
                        "id_fundo": None,
                        "total_reported": len(rows),
                        "pages_queried": 1,
                        "rejected": [],
                        "errors": [],
                    }
                else:
                    collected = catalog_service.catalog_with_metrics(asset, run_id)
                    documents = collected.documents
                    metrics = {
                        "administrator_id": collected.administrator_id,
                        "id_fundo": collected.id_fundo,
                        "total_reported": collected.total_reported,
                        "pages_queried": collected.pages_queried,
                        "rejected": collected.rejected,
                        "errors": collected.errors,
                    }
                if any(document.run_id != run_id for document in documents):
                    raise ValueError(
                        "todos os documentos coletados devem usar o run_id da execução"
                    )
                documents_found += len(documents)
                inserted_asset = updated_asset = unchanged_asset = 0
                for document in documents:
                    _, upsert_status = documents_repo.upsert_with_status(document)
                    if upsert_status == "inserted":
                        inserted += 1
                        inserted_asset += 1
                    elif upsert_status == "updated":
                        updated += 1
                        updated_asset += 1
                    else:
                        unchanged += 1
                        unchanged_asset += 1
                rejected += len(metrics["rejected"])
                errors += len(metrics["errors"])
                result["assets"].append({
                    "codigo_cetip": asset.codigo_cetip,
                    "isin": asset.isin,
                    "run_id": run_id,
                    "administrator_id": metrics["administrator_id"],
                    "idFundo": metrics["id_fundo"],
                    "total_informado": metrics["total_reported"],
                    "paginas_consultadas": metrics["pages_queried"],
                    "documentos_recebidos": len(documents),
                    "documentos_inseridos": inserted_asset,
                    "documentos_atualizados": updated_asset,
                    "documentos_inalterados": unchanged_asset,
                    "documentos_rejeitados": metrics["rejected"],
                    "erros": metrics["errors"],
                    "linhas_antes_do_ativo": before,
                    "linhas_depois_do_ativo": documents_repo.count_by_asset_id(asset_id),
                })
            except Exception as error:
                errors += 1
                result["assets"].append({
                    "codigo_cetip": source_asset.codigo_cetip,
                    "isin": source_asset.isin,
                    "run_id": run_id,
                    "documentos_recebidos": 0,
                    "documentos_inseridos": 0,
                    "documentos_atualizados": 0,
                    "documentos_inalterados": 0,
                    "documentos_rejeitados": [],
                    "erros": [f"{type(error).__name__}: {error}"],
                    "linhas_antes_do_ativo": before,
                    "linhas_depois_do_ativo": (
                        documents_repo.count_by_asset_id(asset_id)
                        if asset_id is not None
                        else 0
                    ),
                })
    finally:
        result["after_documents"] = documents_repo.count()
        result["inserted"] = inserted
        result["updated"] = updated
        result["unchanged"] = unchanged
        result["rejected"] = rejected
        result["errors"] = errors
        result["duration_seconds"] = round(time.perf_counter() - started, 4)
        documents_repo.export_csv(output_path)
        execution.finish(
            run_id,
            "success" if errors == 0 else "partial",
            result["duration_seconds"],
            assets_processed,
            documents_found,
            rejected,
            errors,
        )
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    history_path = report_path.parent / "document_catalog_runs.json"
    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    history.append(result)
    history_path.write_text(json.dumps(history[-20:], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-fixtures", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Le o catalogo e mostra o que mudaria; nao grava nada.",
    )
    parser.add_argument("--only", help="CETIP ou ISIN de um unico ativo")
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--config-path", type=Path)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args(argv)
    result = run(
        offline=args.offline_fixtures,
        only=args.only,
        database_path=args.database_path,
        config_path=args.config_path,
        output_path=args.output_path,
        report_path=args.report_path,
        dry_run=args.dry_run,
    )
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
