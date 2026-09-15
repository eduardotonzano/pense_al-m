from __future__ import annotations
import csv, json, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.execution_repository import ExecutionRepository
from credit_assets.monitoring.logger import configure_logging
from credit_assets.monitoring.health_monitor import HealthReport
from credit_assets.utils.validators import validate_asset_type

def main():
    configure_logging(str(ROOT / "logs"))
    started = time.perf_counter()
    run_id = uuid.uuid4().hex
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    executions = ExecutionRepository(connection)
    assets_repo = AssetRepository(connection)
    executions.start(run_id)
    processed = 0
    errors = 0
    with open(ROOT / "config" / "ativos_piloto.csv", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("ativo", "").lower() != "true":
                continue
            try:
                asset = Asset(row["codigo_cetip"], validate_asset_type(row["tipo_ativo"]), row["securitizadora"], row["cnpj_securitizadora"], row["emissao"], row["serie"], row.get("devedor", ""), row.get("cnpj_devedor", ""))
                assets_repo.upsert(asset)
                processed += 1
            except Exception:
                errors += 1
    duration = round(time.perf_counter() - started, 4)
    status = "success" if errors == 0 else "partial"
    executions.finish(run_id, status, duration, processed, 0, 0, errors)
    report = HealthReport(run_id, "healthy" if errors == 0 else "warning", processed, 0, 0, 0, errors, duration)
    output = ROOT / "reports" / f"health_{run_id}.json"
    output.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
