from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import sync_playwright

from credit_assets.collectors.fundosnet_collector import FundosNetCollector
from credit_assets.download_diagnostics import (
    detect_content,
    find_row_by_document_id,
    identify_download_action,
    identify_view_action,
    sha256_bytes,
    validate_download,
)
from credit_assets.models.asset import Asset
from credit_assets.utils.fundosnet_normalization import product_type_id


def load_asset() -> Asset:
    with (ROOT / "config" / "ativos_piloto.csv").open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("codigo_cetip") == "BRECOACRABX0":
                return Asset(
                    codigo_cetip=row["codigo_cetip"], isin=row["isin"],
                    tipo_ativo=row["tipo_ativo"].strip().upper(),
                    securitizadora=row["securitizadora"],
                    cnpj_securitizadora=row["cnpj_securitizadora"],
                    emissao=row["emissao"], serie=row["serie"],
                    devedor=row.get("devedor", ""), cnpj_devedor=row.get("cnpj_devedor", ""),
                )
    raise RuntimeError("Café Brasil não encontrado na configuração")


def choose_document(connection: sqlite3.Connection) -> dict:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """SELECT * FROM documents
           WHERE asset_id IN (SELECT asset_id FROM assets WHERE isin = 'BRECOACRABX0')
             AND lower(document_name) LIKE '%informe mensal%'
           ORDER BY publication_date DESC, document_pk DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        raise RuntimeError("nenhum Informe Mensal real encontrado")
    return dict(row)


def request_record(request):
    query = parse_qs(urlsplit(request.url).query, keep_blank_values=True)
    return {
        "method": request.method,
        "url": request.url,
        "parameters": {key: values[-1] for key, values in query.items()
                       if key not in {"token", "csrf", "_csrf"}},
    }


def run_attempt(asset: Asset, document: dict, attempt: int, max_bytes: int = 25_000_000) -> dict:
    collector = FundosNetCollector(browser_channel="msedge", headless=True, timeout_ms=120_000)
    result = {
        "attempt": attempt,
        "document": {
            key: document.get(key)
            for key in (
                "document_pk", "source_document_id", "category", "document_name",
                "reference_date", "publication_date", "source_url",
            )
        },
        "grade_loaded": False,
        "line_found": False,
        "actions": [],
        "events": {"requests": [], "responses": [], "requestfailed": [], "downloads": [], "popups": [], "pages": []},
        "response": None,
        "requires_browser_session": True,
        "temporary_files_removed": True,
        "database_modified": False,
        "ui_events": [],
        "native_xhr": [],
        "selectors": {},
        "json_probe": None,
        "listar_fundos_payloads": [],
        "attempts": [],
    }
    download_objects = []
    with sync_playwright() as playwright:
        browser = collector._launch_browser(playwright)
        context = browser.new_context(locale="pt-BR")
        page = context.new_page()
        def attach_page(observed_page):
            observed_page.on("request", lambda request: result["events"]["requests"].append(request_record(request)))
            observed_page.on("response", lambda response: result["events"]["responses"].append({
                "method": response.request.method, "url": response.url, "status": response.status,
                "content_type": response.headers.get("content-type", ""),
                "content_disposition": response.headers.get("content-disposition", ""),
            }))
            observed_page.on("requestfailed", lambda request: result["events"]["requestfailed"].append({
                **request_record(request), "failure": request.failure,
            }))
            observed_page.on("download", lambda download: (
                download_objects.append(download),
                result["events"]["downloads"].append({
                    "suggested_filename": download.suggested_filename, "url": download.url,
                }),
            ))

        context.on("page", lambda child: (result["events"]["pages"].append(child.url), attach_page(child)))
        attach_page(page)
        try:
            response = page.goto(
                collector.BASE_URL + "abrirGerenciadorDocumentosCertificadosCVM",
                timeout=collector.timeout_ms, wait_until="commit",
            )
            page.wait_for_selector("#tipoFundo", state="attached", timeout=collector.timeout_ms)
            page.locator("#tipoFundo").select_option(str(product_type_id(asset.tipo_ativo)), force=True)
            page.locator("#tipoFundo").evaluate("el => { $(el).trigger('change'); }")
            administrator = collector._find_administrador(page, context, asset.securitizadora, result)
            if administrator is None:
                raise RuntimeError("securitizadora não localizada")
            administrator_id = collector._ui_select_administrator(page, asset, administrator, result)
            matches = collector._search_fundos(
                page, context, asset, administrator_id, product_type_id(asset.tipo_ativo), result
            )
            selected = collector._select_match(asset, matches)
            if selected is None or not selected.raw:
                raise RuntimeError("certificado único não localizado")
            id_fundo = collector._ui_select_fund(page, asset, selected, result)
            payload = collector._capture_native_document_xhr(
                page, asset, administrator_id, id_fundo, result
            )
            result["grade_loaded"] = True
            rows = payload.get("data", [])
            target = find_row_by_document_id(rows, document["source_document_id"])
            page_number = 1
            while target is None and page_number < 20:
                next_button = page.locator("#tblDocumentosEnviados_next")
                if not next_button.count() or "disabled" in (next_button.get_attribute("class") or ""):
                    break
                with page.expect_response(
                    lambda item: "pesquisarGerenciadorDocumentosDados" in item.url,
                    timeout=collector.timeout_ms,
                ) as page_response:
                    next_button.click(force=True)
                next_payload = collector._parse_native_response(page_response.value, result)
                rows = next_payload.get("data", [])
                target = find_row_by_document_id(rows, document["source_document_id"])
                page_number += 1
            result["grade_page"] = page_number
            result["line_found"] = target is not None
            if target is None:
                raise RuntimeError("documento não encontrado na página atual")
            # DataTables may render the row outside the response payload; locate by real ID, not position.
            row_candidates = page.locator("tr")
            row_index = None
            for index in range(row_candidates.count()):
                html = row_candidates.nth(index).evaluate("el => el.outerHTML")
                if document["source_document_id"] in html:
                    row_index = index
                    break
            if row_index is None:
                raise RuntimeError("linha do documento não encontrada no DOM")
            row_locator = row_candidates.nth(row_index)
            elements = row_locator.locator("a,button,[onclick]").evaluate_all(
                """els => els.map(el => {
                    const attrs = {};
                    for (const attr of el.attributes) attrs[attr.name] = attr.value;
                    return {tag: el.tagName, text: el.innerText || '', href: el.href || '',
                            onclick: el.getAttribute('onclick') || '', title: el.title || '',
                            aria_label: el.getAttribute('aria-label') || '',
                            data: Object.fromEntries(Array.from(el.attributes)
                              .filter(a => a.name.startsWith('data-')).map(a => [a.name, a.value])),
                            attributes: attrs};
                })"""
            )
            result["actions"] = elements
            action = identify_download_action(elements)
            if action is None:
                raise RuntimeError("link oficial de download não identificado")
            result["official_action"] = action
            action_candidates = row_locator.locator("a,button,[onclick]")
            selector = None
            for action_index in range(action_candidates.count()):
                candidate = action_candidates.nth(action_index)
                candidate_href = candidate.get_attribute("href") or ""
                action_href = action.get("href") or ""
                if candidate.get_attribute("title") == action.get("title") and (
                    candidate_href == action_href
                    or candidate_href.rstrip("/").endswith(action_href.split("/")[-1])
                ):
                    selector = candidate
                    break
            if selector is None:
                raise RuntimeError("elemento oficial de download não localizado na linha")
            with tempfile.TemporaryDirectory(prefix="fnet-action-") as temporary:
                target_path = Path(temporary) / "documento_981509.bin"
                before_pages = len(context.pages)
                response_holder = {}
                with page.expect_download(timeout=30_000) as download_info:
                    with page.expect_response(
                        lambda item: "downloadDocumento" in item.url,
                        timeout=30_000,
                    ) as download_response_info:
                        selector.click(force=True, timeout=15_000)
                download_response = download_response_info.value
                downloaded_file = download_info.value
                response_holder["response"] = download_response
                result["download_response"] = {
                    "method": download_response.request.method,
                    "url": download_response.url,
                    "status": download_response.status,
                    "content_type": download_response.headers.get("content-type", ""),
                    "content_disposition": download_response.headers.get("content-disposition", ""),
                    "redirect_count": sum(
                        1 for _ in iter_redirects(download_response.request)
                    ),
                }
                target_path = Path(temporary) / downloaded_file.suggested_filename
                downloaded_file.save_as(str(target_path))
                data = target_path.read_bytes()
                result["mechanism"] = "event_download"
                validation = validate_download(data, result["download_response"]["content_type"], max_bytes)
                result["download_response"].update(validation)
                if validation["within_limit"] and not validation["is_html"] and data:
                    result["temporary_file"] = {
                        "path": str(target_path),
                        "exists_during_diagnostic": target_path.exists(),
                    }
                elif not data:
                    result["download_response"]["classification"] = "resposta_vazia"
                elif validation["is_html"]:
                    result["download_response"]["classification"] = "html_em_vez_de_arquivo"
                    result["download_response"]["preview"] = (
                        data[:300].decode("utf-8", errors="replace")
                        .replace("\r", " ").replace("\n", " ")[:300]
                    )
                result["events"]["popups"] = [item.url for item in context.pages if item is not page]
                result["last_url"] = page.url
                result["new_page_count"] = len(context.pages) - before_pages
                for item in result["events"]["downloads"]:
                    result["download_url"] = item["url"]
                for download in context.pages:
                    if download is not page:
                        try:
                            download.wait_for_load_state("domcontentloaded", timeout=5_000)
                            result["popup_url"] = download.url
                            result["popup_content"] = validate_download(
                                download.content().encode("utf-8"), "text/html", max_bytes
                            )
                            result["popup_elements"] = download.locator(
                                "a,iframe,embed,object,form"
                            ).evaluate_all(
                                """els => els.map(el => {
                                    const attrs = {};
                                    for (const attr of el.attributes) attrs[attr.name] = attr.value;
                                    return {tag: el.tagName, href: el.href || '',
                                            src: el.src || '', action: el.action || '',
                                            attributes: attrs};
                                })"""
                            )
                            result["protocol_links"] = [
                                item["href"] for item in result["popup_elements"] if item["href"]
                            ]
                        except Exception:
                            pass
                relevant = [
                    event for event in result["events"]["responses"]
                    if any(path in event["url"] for path in (
                        "exibirDocumento", "visualizarProtocoloDocumentoCVM",
                        "downloadDocumento",
                    ))
                ]
                if relevant:
                    result["response"] = relevant[-1]
                result["temporary_file_removed"] = not any(
                    Path(item).exists() for item in [result.get("temporary_file", {}).get("path", "")]
                    if item
                )
            result["temporary_file_removed"] = not any(
                Path(item).exists() for item in [result.get("temporary_file", {}).get("path", "")]
                if item
            )
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
            result["last_url"] = page.url
        finally:
            context.close()
            browser.close()
    return result


def iter_redirects(request):
    current = request.redirected_from
    while current is not None:
        yield current
        current = current.redirected_from


def run() -> dict:
    connection = sqlite3.connect(ROOT / "data" / "cri_cra.db")
    document = choose_document(connection)
    asset = load_asset()
    report = {"document": document, "attempts": [], "recommendation": None}
    for attempt, delay in enumerate((0, 3, 8), 1):
        if delay:
            time.sleep(delay)
        outcome = run_attempt(asset, document, attempt)
        report["attempts"].append(outcome)
        if outcome.get("response") or outcome.get("events", {}).get("downloads"):
            break
    if report["attempts"][-1].get("response") or report["attempts"][-1].get("events", {}).get("downloads"):
        report["recommendation"] = "reproduzir a ação oficial capturada no mesmo BrowserContext e validar a assinatura do arquivo"
    else:
        report["recommendation"] = "endpoint oficial não foi capturado; investigar a ação renderizada sem presumir URL"
    path = ROOT / "reports" / "cafe_brasil_download_action_diagnostic.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Diagnóstico da ação oficial de documento",
        "",
        f"- Documento: `{document['source_document_id']}` — {document['document_name']}",
        f"- Tentativas: **{len(report['attempts'])}**",
        "",
        "## Resultado",
        "",
    ]
    for item in report["attempts"]:
        lines.append(
            f"- Tentativa {item['attempt']}: grade carregada={item['grade_loaded']}, "
            f"linha encontrada={item['line_found']}, página={item.get('grade_page')}, "
            f"erro={item.get('error', 'nenhum')}."
        )
        for action in item.get("actions", []):
            lines.append(f"  - `{action['tag']}` {action.get('title') or action.get('href')}")
        if item.get("official_action"):
            lines.append(f"  - ação oficial usada: `{item['official_action'].get('href')}`")
        if item.get("mechanism"):
            lines.append(f"  - mecanismo: **{item['mechanism']}**")
        download = item.get("download_response")
        if download:
            lines.append(
                f"  - download: HTTP **{download.get('status')}**, "
                f"`{download.get('content_type')}`, formato **{download.get('format')}**, "
                f"{download.get('size_bytes')} bytes, SHA-256 `{download.get('sha256')}`"
            )
            lines.append(
                f"  - content-disposition: `{download.get('content_disposition')}`, "
                f"redirecionamentos: {download.get('redirect_count', 0)}"
            )
        lines.append(f"  - arquivo temporário removido: **{item.get('temporary_file_removed')}**")
        if item.get("popup_url"):
            lines.append(f"  - popup: `{item['popup_url']}`")
        for event in item.get("events", {}).get("responses", []):
            if "documento" in event["url"].lower() or "visualizar" in event["url"].lower():
                lines.append(f"  - resposta: `{event['status']}` `{event['content_type']}` `{event['url']}`")
    lines.extend(["", "## Recomendação", "", report["recommendation"], ""])
    (ROOT / "reports" / "cafe_brasil_download_action_diagnostic.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    run()
