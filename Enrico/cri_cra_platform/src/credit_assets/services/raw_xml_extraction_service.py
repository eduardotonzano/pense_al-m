"""Extração de XMLs versionados para o SQLite, guiada pela mapping_version.

Grava o texto literal de cada folha e atributo com evidência de linha. Para
caminhos ``mapped``, aplica a normalização determinística
(``xml_value_normalizer``); caminhos ``pending_decision`` ficam só com o
literal. Escala suspeita e totais divergentes geram ``warning`` em
``extraction_findings``, sem alterar valores. Nenhum relatório é marcado como
vigente: isso exige aprovação humana.
"""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.parsers import expat

from credit_assets.services.xml_value_normalizer import (
    SEMANTIC_NORMALIZER_VERSION,
    is_monetary,
    normalize,
)
from credit_assets.xml_diagnostics import (
    UnsafeXmlError,
    _FORBIDDEN,
    _mask,
    personal_data_suspected,
)

EXTRACTOR_VERSION = "0.2.0"
XSI_NIL = "http://www.w3.org/2001/XMLSchema-instance nil"
RETENTION_POLICY = "pending_definition"
MAX_EXCERPT = 200
COMPETENCIA_PATH = "/InformeMensalCRA/DadosGerais/Competencia"


def walk_values(data: bytes) -> list[dict[str, Any]]:
    """Lista folhas e atributos com caminho, ocorrência, linha e texto literal.

    ``chain`` guarda o índice de ocorrência de cada ancestral, para ligar
    valores ao bloco repetido a que pertencem.
    """
    if _FORBIDDEN.search(data):
        raise UnsafeXmlError("XML com DOCTYPE/ENTITY recusado")
    parser = expat.ParserCreate(namespace_separator=" ")
    stack: list[dict[str, Any]] = []
    counters: dict[str, int] = defaultdict(int)
    values: list[dict[str, Any]] = []

    def start(name, attributes):
        tag = name.split(" ")[-1]
        parent = stack[-1] if stack else None
        path = (parent["path"] if parent else "") + "/" + tag
        index = counters[path]
        counters[path] += 1
        chain = (parent["chain"] if parent else ()) + (index,)
        line = parser.CurrentLineNumber
        for attribute, value in attributes.items():
            if attribute == XSI_NIL:
                continue
            values.append({
                "xml_path": f"{path}/@{attribute.split(' ')[-1]}",
                "instance_index": index,
                "chain": chain,
                "line": line,
                "raw_text": value,
                "xsi_nil": False,
            })
        stack.append({
            "path": path, "index": index, "chain": chain, "line": line, "chunks": [],
            "has_children": False, "xsi_nil": attributes.get(XSI_NIL) == "true",
        })
        if parent:
            parent["has_children"] = True

    def end(_name):
        node = stack.pop()
        if not node["has_children"]:
            values.append({
                "xml_path": node["path"],
                "instance_index": node["index"],
                "chain": node["chain"],
                "line": node["line"],
                "raw_text": "".join(node["chunks"]),
                "xsi_nil": node["xsi_nil"],
            })

    def text(value):
        if stack:
            stack[-1]["chunks"].append(value)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.Parse(data, True)
    return values


def observed_field_state(raw_text: str) -> str:
    # Sem mapeamento não se sabe se o campo é numérico (ex.: RetentorRisco
    # "00000000000000" é identificador), então não existe ``zero`` aqui.
    return "present_value" if raw_text.strip() else "present_empty"


def _block_of(xml_path: str) -> str:
    return xml_path.rsplit("/", 1)[0]


def assign_instance_keys(values, decisions) -> list[dict[str, Any]]:
    """Preenche ``instance_key`` pelo campo-chave do bloco (ex.: NumeroSerie)."""
    findings = []
    keys: dict[tuple[str, tuple], str] = {}
    seen: dict[tuple[str, str], int] = defaultdict(int)
    key_fields = {
        _block_of(path) + "/" + rule["instance_key"]
        for path, rule in decisions.items() if rule.get("instance_key")
    }
    for value in values:
        if value["xml_path"] in key_fields and value["raw_text"].strip():
            block = _block_of(value["xml_path"])
            keys[(block, value["chain"][:-1])] = value["raw_text"].strip()
            seen[(block, value["raw_text"].strip())] += 1
    for value in values:
        rule = decisions.get(value["xml_path"], {})
        if not rule.get("instance_key"):
            continue
        block = _block_of(value["xml_path"])
        depth = block.count("/")
        key = keys.get((block, value["chain"][:depth]))
        if key is None or seen[(block, key)] > 1:
            value["instance_key_problem"] = (
                f"{rule['instance_key']} ausente no bloco" if key is None
                else f"{rule['instance_key']}={key} repetido no bloco"
            )
            findings.append({
                "rule": "instance_key", "severity": "invalid",
                "xml_path": value["xml_path"], "instance_index": value["instance_index"],
                "message": value["instance_key_problem"],
            })
        else:
            value["instance_key"] = key
    return findings


def monetary_scale_suspect(values, mapping) -> dict[str, Any] | None:
    rule = mapping.get("rules", {}).get("monetary_scale_suspect")
    if not rule:
        return None
    try:
        numerator = next(
            Decimal(v["raw_text"]) for v in values if v["xml_path"] == rule["numerator"]
        )
        denominator = sum(
            (Decimal(v["raw_text"]) for v in values
             if v["xml_path"] == rule["denominator_sum"] and v["raw_text"].strip()),
            Decimal(0),
        )
    except (StopIteration, InvalidOperation):
        return None
    if denominator <= 0 or numerator / denominator >= Decimal(rule["threshold"]):
        return None
    return {
        "rule": "monetary_scale_suspect", "severity": "warning",
        "xml_path": rule["numerator"], "instance_index": 0,
        "message": (
            f"totalVlrCertificados/VlrTotalIntegralizado = {numerator / denominator:.6f} "
            f"< {rule['threshold']}: escala monetária suspeita; valores mantidos, scale='unknown'"
        ),
    }


def totals_consistency(values) -> list[dict[str, Any]]:
    findings = []
    for total in (v for v in values if v["xml_path"].endswith("/@total")):
        container = total["xml_path"][: -len("/@total")]
        depth = container.count("/")
        leaves_sum = Decimal(0)
        for value in values:
            if (
                value["xml_path"].startswith(container + "/")
                and "/@" not in value["xml_path"]
                and value["chain"][:depth] == total["chain"]
                and value["raw_text"].strip()
            ):
                try:
                    leaves_sum += Decimal(value["raw_text"].strip())
                except InvalidOperation:
                    continue
        try:
            declared = Decimal(total["raw_text"])
        except InvalidOperation:
            continue
        if declared != leaves_sum:
            findings.append({
                "rule": "totals_consistency", "severity": "warning",
                "xml_path": total["xml_path"], "instance_index": total["instance_index"],
                "message": f"@total={declared} difere da soma das folhas={leaves_sum} ({declared - leaves_sum})",
            })
    return findings


class RawXmlExtractionService:
    def __init__(self, connection: sqlite3.Connection, project_root: str | Path):
        self.connection = connection
        self.project_root = Path(project_root).resolve()

    def extract_version(
        self, document_version_id: int, mapping: dict[str, Any]
    ) -> dict[str, Any]:
        version = self.connection.execute(
            """SELECT v.version_id, v.document_id, v.local_file_path, v.file_hash,
                      v.source_version, d.asset_id, d.publication_date
               FROM document_versions v
               JOIN documents d ON d.document_pk = v.document_id
               WHERE v.version_id = ? AND v.validation_status = 'valid'""",
            (document_version_id,),
        ).fetchone()
        if version is None:
            raise ValueError(f"document_version {document_version_id} inexistente ou inválida")
        decisions = mapping.get("paths", {})
        uses_mapping = any(rule.get("status") == "mapped" for rule in decisions.values())
        run_id = uuid.uuid4().hex
        with self.connection:
            self.connection.execute(
                """INSERT INTO extraction_runs (
                    extraction_run_id, document_version_id, extractor_version,
                    mapping_version, layout_version, layout_validation_status,
                    semantic_normalizer_version, started_at, status, raw_file_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)""",
                (
                    run_id, document_version_id, EXTRACTOR_VERSION,
                    mapping["mapping_version"], mapping.get("layout_version"),
                    mapping.get("layout_validation_status", "structural_only"),
                    SEMANTIC_NORMALIZER_VERSION if uses_mapping else None,
                    datetime.now(timezone.utc).isoformat(), version["file_hash"],
                ),
            )
        try:
            data = (self.project_root / version["local_file_path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != version["file_hash"]:
                raise ValueError("hash do arquivo diverge de document_versions")
            values = walk_values(data)
            lines = data.decode("utf-8").splitlines()
            findings = []
            scale_finding = None
            if uses_mapping:
                findings += assign_instance_keys(values, decisions)
                scale_finding = monetary_scale_suspect(values, mapping)
                findings += [scale_finding] if scale_finding else []
                findings += totals_consistency(values)
            with self.connection:
                report_id = self._insert_report(run_id, version, values)
                unmapped = 0
                statuses = []
                present_paths = {value["xml_path"] for value in values}
                for value in values:
                    rule = decisions.get(value["xml_path"], {})
                    status = rule.get("status", "pending_decision")
                    unmapped += status == "pending_decision"
                    statuses.append(self._insert_value(
                        report_id, document_version_id, value, rule, status, lines,
                        scale_unknown=scale_finding is not None,
                    ))
                for path, rule in decisions.items():
                    if rule.get("status") == "mapped" and path not in present_paths:
                        self._insert_absent(report_id, document_version_id, path, rule, version["file_hash"])
                for finding in findings:
                    self.connection.execute(
                        """INSERT INTO extraction_findings
                           (report_id, rule, severity, xml_path, instance_index, message)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (report_id, finding["rule"], finding["severity"], finding["xml_path"],
                         finding["instance_index"], finding["message"]),
                    )
                report_status = "pending"
                if uses_mapping:
                    severities = set(statuses) | {f["severity"] for f in findings}
                    report_status = (
                        "invalid" if "invalid" in severities
                        else "warning" if "warning" in severities
                        else "valid"
                    )
                self.connection.execute(
                    "UPDATE extracted_reports SET automatic_validation_status = ? WHERE report_id = ?",
                    (report_status, report_id),
                )
                self.connection.execute(
                    """UPDATE extraction_runs
                       SET status = 'success', finished_at = ?, unmapped_fields_count = ?
                       WHERE extraction_run_id = ?""",
                    (datetime.now(timezone.utc).isoformat(), unmapped, run_id),
                )
        except Exception as error:
            with self.connection:
                self.connection.execute(
                    """UPDATE extraction_runs
                       SET status = 'failed', finished_at = ?, error_message = ?
                       WHERE extraction_run_id = ?""",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        f"{type(error).__name__}: {error}"[:500],
                        run_id,
                    ),
                )
            return {"extraction_run_id": run_id, "status": "failed", "error": str(error)}
        return {
            "extraction_run_id": run_id,
            "status": "success",
            "report_id": report_id,
            "values": len(values),
            "unmapped_fields_count": unmapped,
            "automatic_validation_status": report_status,
            "findings": len(findings),
        }

    def _insert_report(self, run_id, version, values) -> int:
        competencia = next(
            (v["raw_text"] for v in values if v["xml_path"] == COMPETENCIA_PATH), None
        )
        cursor = self.connection.execute(
            """INSERT INTO extracted_reports (
                extraction_run_id, asset_id, document_id, document_version_id,
                reference_date, publication_date, source_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, version["asset_id"], version["document_id"],
                version["version_id"], competencia, version["publication_date"],
                version["source_version"],
            ),
        )
        return int(cursor.lastrowid)

    def _insert_value(
        self, report_id, version_id, value, rule, mapping_status, lines, scale_unknown
    ) -> str:
        if mapping_status == "mapped":
            normalized = normalize(value["raw_text"], rule)
            if is_monetary(rule) and scale_unknown:
                normalized["scale"] = "unknown"
                if normalized["automatic_validation_status"] == "valid":
                    normalized["automatic_validation_status"] = "warning"
            if value.get("instance_key_problem"):
                normalized["automatic_validation_status"] = "invalid"
        else:
            normalized = {
                "normalized_value": None, "data_type": None, "unit": None,
                "currency": None, "scale": None,
                "field_state": observed_field_state(value["raw_text"]),
                "automatic_validation_status": "pending",
            }
        cursor = self.connection.execute(
            """INSERT INTO extracted_values (
                report_id, field_name, original_value, normalized_value, data_type,
                field_state, xsi_nil, unit, currency, scale, xml_path, instance_index,
                instance_key, mapping_status, automatic_validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id, value["xml_path"], value["raw_text"],
                normalized["normalized_value"], normalized["data_type"],
                normalized["field_state"], int(value["xsi_nil"]), normalized["unit"],
                normalized["currency"], normalized["scale"], value["xml_path"],
                value["instance_index"], value.get("instance_key"), mapping_status,
                normalized["automatic_validation_status"],
            ),
        )
        excerpt = lines[value["line"] - 1].strip()
        tag = value["xml_path"].rsplit("/", 1)[-1]
        personal = personal_data_suspected(tag, value["raw_text"])
        shown = _mask(excerpt) if personal else excerpt
        self.connection.execute(
            """INSERT INTO evidences (
                extracted_value_id, document_version_id, xml_path, line_number,
                evidence_excerpt, evidence_excerpt_truncated, evidence_full_hash,
                contains_personal_data, masking_applied, retention_policy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cursor.lastrowid, version_id, value["xml_path"], value["line"],
                shown[:MAX_EXCERPT], int(len(shown) > MAX_EXCERPT),
                hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                int(personal), int(personal), RETENTION_POLICY,
            ),
        )
        return normalized["automatic_validation_status"]

    def _insert_absent(self, report_id, version_id, path, rule, file_hash) -> None:
        normalized = normalize(None, rule)
        cursor = self.connection.execute(
            """INSERT INTO extracted_values (
                report_id, field_name, original_value, data_type, field_state,
                unit, currency, scale, xml_path, instance_index, mapping_status,
                automatic_validation_status
            ) VALUES (?, ?, NULL, ?, 'absent', ?, ?, ?, ?, 0, 'mapped', 'valid')""",
            (report_id, path, normalized["data_type"], normalized["unit"],
             normalized["currency"], normalized["scale"], path),
        )
        # A evidência da ausência é o arquivo inteiro, identificado pelo hash físico.
        self.connection.execute(
            """INSERT INTO evidences (
                extracted_value_id, document_version_id, xml_path, line_number,
                evidence_excerpt, evidence_full_hash, retention_policy
            ) VALUES (?, ?, ?, NULL, NULL, ?, ?)""",
            (cursor.lastrowid, version_id, path, file_hash, RETENTION_POLICY),
        )
