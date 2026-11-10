"""OCR das páginas de PDFs que saem sem texto (PDF em imagem).

Opcional: exige ``pip install pymupdf rapidocr-onnxruntime`` (não fazem parte das dependências do
projeto). O texto de OCR é gravado em ``document_text_pages`` com o extrator ``ocr: ...`` e convive
com a linha vazia do pdftotext; os carregadores usam o nativo quando ele existe e o OCR só quando o
nativo vem vazio. OCR pode errar números: todo fato tirado dele precisa de conferência visual no PDF.

    python scripts/ocr_document_pages.py --source-id 892072 --cetip 24G2100031 --dry-run
    python scripts/ocr_document_pages.py --source-id 892072 --cetip 24G2100031
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.database.migrations import ensure_schema_current

DPI = 150


def lines_from_boxes(result) -> tuple[str, float]:
    """Reagrupa as caixas do OCR em linhas pela posição vertical; devolve texto e confiança média."""
    boxes = []
    for box, text, score in result or []:
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        boxes.append({"x": min(xs), "y": (min(ys) + max(ys)) / 2, "h": max(ys) - min(ys),
                      "text": text, "score": float(score)})
    boxes.sort(key=lambda item: item["y"])
    rows: list[list[dict]] = []
    for item in boxes:
        if rows and abs(item["y"] - rows[-1][0]["y"]) <= 0.5 * max(item["h"], rows[-1][0]["h"]):
            rows[-1].append(item)
        else:
            rows.append([item])
    text = "\n".join("   ".join(i["text"] for i in sorted(row, key=lambda i: i["x"])) for row in rows)
    mean = sum(i["score"] for i in boxes) / len(boxes) if boxes else 0.0
    return text, mean


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--last-page", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        import pymupdf
        from importlib.metadata import version as package_version
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as error:
        raise SystemExit(f"OCR indisponível ({error}); instale: pip install pymupdf rapidocr-onnxruntime")
    extractor = (f"ocr: pymupdf {package_version('pymupdf')} dpi{DPI} + "
                 f"rapidocr-onnxruntime {package_version('rapidocr-onnxruntime')}")
    connection = connect(args.database)
    try:
        ensure_schema_current(connection)
        version = connection.execute(
            """SELECT v.version_id, v.local_file_path, v.file_hash FROM document_versions v
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE a.codigo_cetip = ? AND d.source_document_id = ? AND v.is_current = 1
                 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'""",
            (args.cetip, args.source_id),
        ).fetchone()
        if version is None:
            raise SystemExit("documento PDF vigente não encontrado")
        native = connection.execute(
            """SELECT COUNT(*), SUM(length(trim(text)) > 0) FROM document_text_pages
               WHERE document_version_id = ? AND extractor NOT LIKE 'ocr%'""",
            (version["version_id"],),
        ).fetchone()
        if native[0] and native[1]:
            raise SystemExit("o PDF tem texto nativo em parte das páginas; OCR só para PDF totalmente em imagem")
        path = ROOT / version["local_file_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != version["file_hash"]:
            raise SystemExit("hash do PDF diverge de document_versions")
        document = pymupdf.open(path)
        last = min(args.last_page or document.page_count, document.page_count)
        print(json.dumps({"pages": document.page_count, "range": [args.first_page, last],
                          "extractor": extractor, "dry_run": args.dry_run}, ensure_ascii=False))
        if args.dry_run:
            return 0
        engine = RapidOCR()
        now = datetime.now(timezone.utc).isoformat()
        low = []
        for number in range(args.first_page, last + 1):
            document[number - 1].get_pixmap(dpi=DPI).save(ROOT / "data" / "_ocr_page.png")
            result, _ = engine(str(ROOT / "data" / "_ocr_page.png"))
            text, mean = lines_from_boxes(result)
            if mean < 0.85:
                low.append({"page": number, "mean_confidence": round(mean, 3)})
            with connection:
                connection.execute(
                    """INSERT OR IGNORE INTO document_text_pages
                       (document_version_id, page_number, text, text_sha256, extractor, extracted_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (version["version_id"], number, text,
                     hashlib.sha256(text.encode("utf-8")).hexdigest(), extractor, now),
                )
        (ROOT / "data" / "_ocr_page.png").unlink(missing_ok=True)
        print(json.dumps({"done": last - args.first_page + 1, "low_confidence_pages": low},
                         ensure_ascii=False))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
