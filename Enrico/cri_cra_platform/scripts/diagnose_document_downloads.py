from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import sync_playwright

from credit_assets.download_diagnostics import detect_content, select_samples, sha256_bytes

def run(database: Path, report_path: Path) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    asset = connection.execute(
        "SELECT * FROM assets WHERE codigo_cetip = 'CRA022009VM' AND isin = 'BRECOACRABX0'"
    ).fetchone()
    asset_ids = [
        row["asset_id"] for row in connection.execute(
            "SELECT asset_id FROM assets WHERE isin = 'BRECOACRABX0'"
        ).fetchall()
    ]
    marks = ",".join("?" for _ in asset_ids)
    rows = connection.execute(
        f"SELECT * FROM documents WHERE asset_id IN ({marks}) ORDER BY document_pk",
        asset_ids,
    ).fetchall()
    samples = select_samples(rows)
    output = {
        "asset_id": asset["asset_id"] if asset else None,
        "document_count": len(rows),
        "samples": [],
        "temporary_files_removed": True,
        "database_modified": False,
        "errors": [],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(locale="pt-BR")
        page = context.new_page()
        with tempfile.TemporaryDirectory(prefix="fnet-download-") as temporary:
            for sample in samples:
                row = next(
                    row for row in rows
                    if str(row["document_pk"]) == sample["document_id"]
                )
                item = {
                    **sample,
                    "visualization": {"url": row["source_url"]},
                    "download": {"url": None, "status": "não descoberto"},
                }
                try:
                    response = page.goto(row["source_url"], wait_until="domcontentloaded", timeout=45_000)
                    content_type = response.headers.get("content-type", "") if response else ""
                    body = page.content().encode("utf-8")
                    item["visualization"].update({
                        "status": response.status if response else None,
                        "final_url": page.url,
                        "content_type": content_type,
                        "content_disposition": response.headers.get("content-disposition", "")
                        if response else "",
                        "format": detect_content(body, content_type)["format"],
                        "size_bytes": len(body),
                        "requires_session": "/login" in page.url.lower(),
                    })
                    links = page.locator("a").evaluate_all(
                        "(els) => els.map(e => e.href).filter(Boolean)"
                    )
                    candidates = [
                        url for url in links
                        if "visualizar" not in url.lower()
                        and ("download" in url.lower() or "document" in url.lower())
                    ]
                    if candidates:
                        download_url = candidates[0]
                        download_response = page.goto(
                            download_url, wait_until="commit", timeout=45_000
                        )
                        data = download_response.body() if download_response else b""
                        analysis = detect_content(
                            data, download_response.headers.get("content-type", "")
                            if download_response else ""
                        )
                        item["download"] = {
                            "url": download_url,
                            "status": download_response.status if download_response else None,
                            "final_url": page.url,
                            "content_type": download_response.headers.get("content-type", "")
                            if download_response else "",
                            "content_disposition": download_response.headers.get(
                                "content-disposition", ""
                            ) if download_response else "",
                            **analysis,
                            "sha256": sha256_bytes(data) if analysis["is_pdf"] else None,
                        }
                    else:
                        item["download"]["status"] = "nenhum link de download exposto"
                except Exception as error:
                    item["error"] = f"{type(error).__name__}: {error}"
                output["samples"].append(item)
        context.close()
        browser.close()
    report_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    result = run(
        ROOT / "data" / "cri_cra.db",
        ROOT / "reports" / "cafe_brasil_download_diagnostic.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
