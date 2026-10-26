"""Texto de PDFs por página e localização de cláusulas contratuais candidatas.

O texto vem do ``pdftotext -layout`` (Xpdf), com versão registrada. A
localização é determinística (expressões regulares versionadas em
config/contract_terms) e devolve trechos literais com página e linhas. Nada
aqui interpreta valores: parâmetros estruturados são propostos à parte e só
valem após revisão humana.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pdftotext_identity() -> tuple[str, str]:
    binary = shutil.which("pdftotext")
    if not binary:
        raise RuntimeError("pdftotext (Xpdf/Poppler) não encontrado no PATH")
    banner = subprocess.run([binary, "-v"], capture_output=True, text=True)
    version = (banner.stdout or banner.stderr).splitlines()[0].strip()
    return binary, version


def extract_pdf_pages(pdf_path: Path) -> tuple[list[str], str]:
    binary, version = pdftotext_identity()
    with tempfile.TemporaryDirectory(prefix="cri-cra-pdftext-") as temporary:
        output = Path(temporary) / "out.txt"
        subprocess.run(
            [binary, "-layout", "-enc", "UTF-8", str(pdf_path), str(output)],
            check=True, capture_output=True,
        )
        text = output.read_text(encoding="utf-8")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages, f"{version} -layout -enc UTF-8"


def store_pages(connection, project_root: Path, document_version_id: int) -> dict[str, Any]:
    version = connection.execute(
        """SELECT local_file_path, file_hash, file_format FROM document_versions
           WHERE version_id = ? AND validation_status = 'valid'""",
        (document_version_id,),
    ).fetchone()
    if version is None or version["file_format"].lower() != "pdf":
        raise ValueError("document_version inexistente, inválida ou não-PDF")
    path = project_root / version["local_file_path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != version["file_hash"]:
        raise ValueError("hash do PDF diverge de document_versions")
    pages, extractor = extract_pdf_pages(path)
    now = datetime.now(timezone.utc).isoformat()
    with connection:
        for number, text in enumerate(pages, start=1):
            connection.execute(
                """INSERT OR IGNORE INTO document_text_pages
                   (document_version_id, page_number, text, text_sha256, extractor, extracted_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (document_version_id, number, text, _sha256(text), extractor, now),
            )
    empty = sum(1 for text in pages if not text.strip())
    return {"pages": len(pages), "empty_pages": empty, "extractor": extractor}


def find_candidates(pages: list[tuple[int, str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """``pages``: (número, texto, sha256). Devolve um candidato por ocorrência de tema."""
    window = int(config["window_lines"])
    value_patterns = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in config["value_patterns"].items()}
    candidates = []
    for topic, patterns in config["topics"].items():
        compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        for number, text, text_hash in pages:
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if not any(pattern.search(line) for pattern in compiled):
                    continue
                start, end = index, min(len(lines), index + window)
                excerpt = "\n".join(item.rstrip() for item in lines[start:end]).strip("\n")
                values = {
                    name: list(dict.fromkeys(match.group(0).strip() for match in pattern.finditer(excerpt)))
                    for name, pattern in value_patterns.items()
                }
                candidates.append({
                    "topic": topic, "page_number": number,
                    "line_start": start + 1, "line_end": end,
                    "excerpt": excerpt, "excerpt_sha256": _sha256(excerpt),
                    "page_text_sha256": text_hash,
                    "values_found": {name: found for name, found in values.items() if found},
                })
    return candidates


def store_candidates(connection, document_version_id: int, config: dict[str, Any]) -> dict[str, Any]:
    pages = [
        (row["page_number"], row["text"], row["text_sha256"])
        for row in connection.execute(
            """SELECT page_number, text, text_sha256 FROM document_text_pages
               WHERE document_version_id = ? ORDER BY page_number""",
            (document_version_id,),
        )
    ]
    if not pages:
        raise ValueError("texto do documento não extraído")
    candidates = find_candidates(pages, config)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with connection:
        for candidate in candidates:
            inserted += connection.execute(
                """INSERT OR IGNORE INTO contract_parameter_candidates (
                    document_version_id, finder_version, topic, page_number, line_start,
                    line_end, excerpt, excerpt_sha256, page_text_sha256, values_found_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document_version_id, config["finder_version"], candidate["topic"],
                 candidate["page_number"], candidate["line_start"], candidate["line_end"],
                 candidate["excerpt"], candidate["excerpt_sha256"], candidate["page_text_sha256"],
                 json.dumps(candidate["values_found"], ensure_ascii=False), now),
            ).rowcount
    by_topic: dict[str, int] = {}
    for candidate in candidates:
        by_topic[candidate["topic"]] = by_topic.get(candidate["topic"], 0) + 1
    return {"candidates": len(candidates), "inserted": inserted, "by_topic": by_topic}
