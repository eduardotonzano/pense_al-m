"""Monta a fila de revisão priorizada (só leitura do SQLite).

Gera reports/fila_revisao_priorizada.{md,csv} e, para cada ativo, os arquivos de ids do nível 4
em reports/fila_revisao_ids/ (usáveis em review_reported_facts.py --ids-file). Não aprova nada.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.contract_fields import load_catalog, match_field
from credit_assets.cross_checks import load_checks, run_checks
from credit_assets.review_queue import (
    TIER_LABELS, classify_fact, classify_parameter, fact_names_in_rules,
)


def squash(text) -> str:
    return " ".join(str(text).split())


def load_notes() -> dict[tuple, str]:
    notes: dict[tuple, str] = {}
    for path in sorted((ROOT / "config" / "reported_facts").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["facts"]:
            if item.get("note"):
                key = (item["source_document_id"], item["fact_name"], item["reference_date"],
                       item["page_number"], squash(item["excerpt"]))
                notes[key] = item["note"]
    return notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    catalog = load_catalog(ROOT / "config" / "contract_terms" / "standard_fields.json")
    core_ids = {f["id"] for f in catalog["fields"] if f["importance"] == "core"}
    feeding = fact_names_in_rules(ROOT / "config" / "alert_rules")
    notes = load_notes()
    try:
        divergent = {"fato": set(), "parâmetro": set()}
        for result in run_checks(connection, load_checks(ROOT / "config" / "contract_terms" / "cross_checks.json")):
            if result["verdict"] == "divergem":
                # marca só quem destoa da maioria; sem maioria única, marca todos os comparáveis
                values = Counter(e["normalized"] for e in result["entries"] if e["normalized"] is not None)
                ranked = values.most_common(2)
                majority = ranked[0][0] if len(ranked) == 1 or ranked[0][1] > ranked[1][1] else None
                for entry in result["entries"]:
                    if entry["normalized"] is None or entry["origin"] not in divergent:
                        continue
                    if majority is None or entry["normalized"] != majority:
                        divergent[entry["origin"]].add(entry["id"])
        visual = {}
        for path in ROOT.joinpath("reports").glob("*_conferencia_visual.json"):
            for item in json.loads(path.read_text(encoding="utf-8")):
                visual[item["fact_id"]] = item
        items = []
        for row in connection.execute(
            """SELECT f.fact_id, f.fact_name, f.reference_date, f.value, f.unit, f.excerpt, f.page_number,
                      f.extraction_method, a.codigo_cetip, d.source_document_id, d.document_name
               FROM reported_facts f
               JOIN document_versions v ON v.version_id = f.document_version_id
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = f.asset_id WHERE f.review_status = 'pending'"""
        ):
            note = notes.get((row["source_document_id"], row["fact_name"], row["reference_date"],
                              row["page_number"], squash(row["excerpt"])))
            tier, reasons = classify_fact(
                dict(row), note, visual.get(row["fact_id"]),
                row["fact_id"] in divergent["fato"], row["fact_name"] in feeding,
            )
            items.append({"tier": tier, "tipo": "fato", "id": row["fact_id"], "ativo": row["codigo_cetip"],
                          "nome": row["fact_name"], "valor": row["value"],
                          "motivo": "; ".join(reasons),
                          "fonte": f"{row['document_name']} {row['source_document_id']}, p.{row['page_number']}"})
        for row in connection.execute(
            """SELECT p.parameter_id, p.parameter_name, p.parameter_value, p.justification, p.source_reference,
                      a.codigo_cetip FROM contract_parameters p JOIN assets a ON a.asset_id = p.asset_id
               WHERE p.review_status = 'pending'"""
        ):
            fields = set(match_field(row["parameter_name"], catalog))
            tier, reasons = classify_parameter(
                dict(row), {row["parameter_name"]} if fields & core_ids else set(),
                row["parameter_id"] in divergent["parâmetro"],
            )
            items.append({"tier": tier, "tipo": "parâmetro", "id": row["parameter_id"], "ativo": row["codigo_cetip"],
                          "nome": row["parameter_name"], "valor": row["parameter_value"],
                          "motivo": "; ".join(reasons), "fonte": row["source_reference"]})
    finally:
        connection.close()

    # decisões de configuração e itens de golden set pendentes
    for path in sorted((ROOT / "config" / "golden_sets").glob("*.json")):
        golden = json.loads(path.read_text(encoding="utf-8"))
        for item in golden["items"]:
            if item["human_review_status"] == "pending":
                items.append({"tier": 4, "tipo": "golden set", "id": item["item_id"],
                              "ativo": golden["asset"]["codigo_cetip"], "nome": item["xml_path"].split("/", 2)[-1],
                              "valor": (item.get("observed") or {}).get("raw_text", ""),
                              "motivo": "caso de cobertura proposto", "fonte": f"Informe doc {item['source_document_id']}"})
    for path in sorted((ROOT / "config" / "alert_rules").glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        if config.get("approval_status") == "pending":
            items.append({"tier": 2, "tipo": "regra de alerta", "id": path.name,
                          "ativo": config.get("asset", {}).get("codigo_cetip", "-"), "nome": path.stem,
                          "valor": "pendente", "motivo": "regra proposta; só roda com --preview", "fonte": str(path.relative_to(ROOT))})
    for path, label in (("config/contract_terms/standard_fields.json", "catálogo de campos padrão"),
                        ("config/contract_terms/cross_checks.json", "verificações entre documentos")):
        status = json.loads((ROOT / path).read_text(encoding="utf-8")).get("status")
        if status == "proposed":
            items.append({"tier": 2, "tipo": "configuração", "id": Path(path).name, "ativo": "todos", "nome": label,
                          "valor": "proposto", "motivo": "define o que será extraído/comparado em todo ativo", "fonte": path})
    na = json.loads((ROOT / "config" / "contract_terms" / "not_applicable.json").read_text(encoding="utf-8"))
    for entry in na["entries"]:
        if entry["status"] == "pending":
            items.append({"tier": 2, "tipo": "não se aplica", "id": entry["field_id"], "ativo": entry["codigo_cetip"],
                          "nome": entry["field_id"], "valor": "não se aplica", "motivo": entry["reason"],
                          "fonte": f"parâmetro {entry['evidence_parameter']}"})

    items.sort(key=lambda i: (i["tier"], i["ativo"], i["tipo"], str(i["id"])))
    out = ROOT / "reports"
    ids_dir = out / "fila_revisao_ids"
    ids_dir.mkdir(exist_ok=True)
    for stale in ids_dir.glob("*.json"):
        stale.unlink()
    block: dict[str, list[int]] = defaultdict(list)
    for item in items:
        if item["tier"] == 4 and item["tipo"] == "fato":
            block[item["ativo"]].append(item["id"])
    for cetip, ids in block.items():
        (ids_dir / f"{cetip.lower()}_nivel4_fatos.json").write_text(json.dumps(sorted(ids)) + "\n", encoding="utf-8")

    with (out / "fila_revisao_priorizada.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tier", "tipo", "id", "ativo", "nome", "valor", "motivo", "fonte"],
                                delimiter=";")
        writer.writeheader()
        writer.writerows(items)

    count = Counter((i["tier"], i["ativo"]) for i in items)
    assets = sorted({i["ativo"] for i in items})
    lines = ["# Fila de revisão priorizada", "",
             "Só leitura: nada aqui aprova item. Começar pelo nível 1; o nível 4 pode ser aprovado em bloco depois de você decidir o escopo.", "",
             "| Nível | " + " | ".join(assets) + " | Total |", "|---|" + "---|" * (len(assets) + 1)]
    for tier, label in TIER_LABELS.items():
        row = [count.get((tier, a), 0) for a in assets]
        lines.append(f"| {tier}. {label} | " + " | ".join(map(str, row)) + f" | {sum(row)} |")
    for tier in (1, 2, 3, 5):
        selected = [i for i in items if i["tier"] == tier]
        lines += ["", f"## Nível {tier}: {TIER_LABELS[tier]} ({len(selected)})", "",
                  "| Ativo | Tipo | Id | Nome | Valor | Por quê | Fonte |", "|---|---|---|---|---|---|---|"]
        for i in selected:
            value = str(i["valor"]).replace("|", "/").replace("\n", " ")[:70]
            lines.append(f"| {i['ativo']} | {i['tipo']} | {i['id']} | `{i['nome']}` | {value} | {i['motivo']} | {i['fonte']} |")
    lines += ["", f"## Nível 4: {TIER_LABELS[4]}", ""]
    lines += [f"- {i['ativo']}: {i['tipo']} `{i['id']}` ({i['nome']})" for i in items
              if i["tier"] == 4 and i["tipo"] != "fato"]
    for cetip in sorted(block):
        lines.append(f"- {cetip}: **{len(block[cetip])} fatos** (ids em `reports/fila_revisao_ids/{cetip.lower()}_nivel4_fatos.json`)")
    lines += ["", "Para aprovar um bloco depois da sua decisão (exemplo):", "",
              "```powershell",
              "python scripts/review_reported_facts.py --cetip CRA02500C1D --status approved --by \"Enrico Suman Marques\" --ids-file reports/fila_revisao_ids/cra02500c1d_nivel4_fatos.json",
              "```"]
    (out / "fila_revisao_priorizada.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
