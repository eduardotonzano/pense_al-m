"""Extração bruta (v0) de XMLs versionados para o SQLite.

Grava o texto literal de cada folha e atributo, com evidência de linha e o
estado observável do campo. Não converte números, não aplica escala, unidade
nem moeda e não decide ``zero``: essas regras dependem de uma mapping_version
aprovada (golden set completo e revisado). Por isso ``normalized_value`` fica
NULL e nenhum relatório é marcado como vigente.
"""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.parsers import expat

from credit_assets.xml_diagnostics import (
    UnsafeXmlError,
    _FORBIDDEN,
    _mask,
    personal_data_suspected,
)

EXTRACTOR_VERSION = "raw-0.1.0"
XSI_NIL = "http://www.w3.org/2001/XMLSchema-instance nil"
RETENTION_POLICY = "pending_definition"
MAX_EXCERPT = 200
COMPETENCIA_PATH = "/InformeMensalCRA/DadosGerais/Competencia"


def walk_values(data: bytes) -> list[dict[str, Any]]:
    """Lista folhas e atributos com caminho, ocorrência, linha e texto literal."""
    if _FORBIDDEN.search(data):
        raise UnsafeXmlError("XML com DOCTYPE/ENTITY recusado")
    parser = expat.ParserCreate(namespace_separator=" ")
    stack: list[dict[str, Any]] = []
    counters: dict[str, int] = defaultdict(int)
    values: list[dict[str, Any]] = []

    def start(name, attributes):
        tag = name.split(" ")[-1]
        path = (stack[-1]["path"] if stack else "") + "/" + tag
        index = counters[path]
        counters[path] += 1
        line = parser.CurrentLineNumber
        for attribute, value in attributes.items():
            if attribute == XSI_NIL:
                continue
            attribute_path = f"{path}/@{attribute.split(' ')[-1]}"
            values.append({
                "xml_path": attribute_path,
                "instance_index": index,
                "line": line,
                "raw_text": value,
                "xsi_nil": False,
            })
        stack.append({
            "path": path, "index": index, "line": line, "chunks": [],
            "has_children": False, "xsi_nil": attributes.get(XSI_NIL) == "true",
        })
        if len(stack) > 1:
            stack[-2]["has_children"] = True

    def end(_name):
        node = stack.pop()
        if not node["has_children"]:
            values.append({
                "xml_path": node["path"],
                "instance_index": node["index"],
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
    # ``zero`` exige saber que o campo é numérico (ex.: RetentorRisco
    # "00000000000000" é identificador), então fica para a mapping_version.
    return "present_value" if raw_text.strip() else "present_empty"


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
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.execute(
                """INSERT INTO extraction_runs (
                    extraction_run_id, document_version_id, extractor_version,
                    mapping_version, layout_version, layout_validation_status,
                    started_at, status, raw_file_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)""",
                (
                    run_id, document_version_id, EXTRACTOR_VERSION,
                    mapping["mapping_version"], mapping.get("layout_version"),
                    mapping.get("layout_validation_status", "structural_only"),
                    started_at, version["file_hash"],
                ),
            )
        try:
            data = (self.project_root / version["local_file_path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != version["file_hash"]:
                raise ValueError("hash do arquivo diverge de document_versions")
            values = walk_values(data)
            lines = data.decode("utf-8").splitlines()
            decisions = mapping.get("paths", {})
            with self.connection:
                report_id = self._insert_report(run_id, version, values)
                unmapped = 0
                for value in values:
                    status = decisions.get(value["xml_path"], {}).get("status", "pending_decision")
                    unmapped += status == "pending_decision"
                    self._insert_value(report_id, document_version_id, value, status, lines)
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

    def _insert_value(self, report_id, version_id, value, mapping_status, lines) -> None:
        cursor = self.connection.execute(
            """INSERT INTO extracted_values (
                report_id, field_name, original_value, field_state, xsi_nil,
                xml_path, instance_index, mapping_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id, value["xml_path"], value["raw_text"],
                observed_field_state(value["raw_text"]), int(value["xsi_nil"]),
                value["xml_path"], value["instance_index"], mapping_status,
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
