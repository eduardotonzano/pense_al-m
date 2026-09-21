from __future__ import annotations

import logging
import json
import re
import time
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import sync_playwright

from credit_assets.collectors.base_collector import BaseCollector
from credit_assets.models.asset import Asset
from credit_assets.models.document import Document
from credit_assets.utils.document_classifier import classify_document
from credit_assets.utils.fundosnet_normalization import normalize_text, product_type_id

logger = logging.getLogger(__name__)


@dataclass
class FundosNetMatch:
    id_fundo: int
    text: str
    isin: str | None = None
    raw: dict[str, Any] | None = None


@dataclass
class CollectionResult:
    documents: list[Document]
    administrator_id: int | None
    id_fundo: int | None
    total_reported: int
    pages_queried: int
    rejected: list[dict[str, str]]
    errors: list[str]
    diagnostics: dict[str, Any] | None = None


class FundosNetCollector(BaseCollector):
    BASE_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/"

    def __init__(
        self,
        browser_channel: str | None = "msedge",
        headless: bool = True,
        timeout_ms: int = 120_000,
    ):
        self.browser_channel = browser_channel
        self.headless = headless
        self.timeout_ms = timeout_ms

    def collect_documents(self, asset: Asset) -> list[Document]:
        return self.collect_with_metrics(asset).documents

    def collect_with_metrics(self, asset: Asset) -> CollectionResult:
        return self._collect_browser_ui_native(asset)

    def _collect_browser_ui_native(self, asset: Asset) -> CollectionResult:
        with sync_playwright() as playwright:
            browser = self._launch_browser(playwright)
            context = browser.new_context(locale="pt-BR")
            page = context.new_page()
            diagnostics: dict[str, Any] = {
                "strategy": "browser_ui_native",
                "browser_context": True,
                "cookies": [],
                "page_status": None,
                "page_title": None,
                "selectors": {},
                "native_xhr": [],
                "captcha": None,
                "errors": [],
                "ui_events": [],
                "select2": {},
                "attempts": [],
                "html_diagnostics": [],
                "json_probe": None,
            }
            administrator_id = None
            id_fundo = None
            try:
                response = page.goto(
                    self.BASE_URL + "abrirGerenciadorDocumentosCertificadosCVM",
                    timeout=self.timeout_ms,
                    wait_until="commit",
                )
                page.wait_for_timeout(1500)
                diagnostics["page_status"] = response.status if response else None
                page.wait_for_selector("#tipoFundo", state="attached", timeout=self.timeout_ms)
                diagnostics["page_title"] = page.title()
                diagnostics["cookies"] = [
                    {"name": cookie["name"], "domain": cookie["domain"]}
                    for cookie in context.cookies()
                ]
                page.locator("#tipoFundo").select_option(
                    str(product_type_id(asset.tipo_ativo)), force=True
                )
                page.locator("#tipoFundo").evaluate(
                    """el => { $(el).trigger('change'); }"""
                )
                diagnostics["selectors"]["tipoFundo"] = "#tipoFundo"
                administrator = self._find_administrador(
                    page, context, asset.securitizadora, diagnostics
                )
                if administrator is None:
                    raise RuntimeError("securitizadora não localizada")
                administrator_id = self._ui_select_administrator(
                    page, asset, administrator, diagnostics
                )
                validated_matches = self._search_fundos(
                    page, context, asset, administrator_id,
                    product_type_id(asset.tipo_ativo), diagnostics
                )
                selected = self._select_match(asset, validated_matches)
                if selected is None or not selected.raw:
                    raise RuntimeError("listarFundos não retornou certificado único compatível")
                id_fundo = self._ui_select_fund(page, asset, selected, diagnostics)
                response_data = self._capture_native_document_xhr(
                    page, asset, administrator_id, id_fundo, diagnostics
                )
                rows = response_data.get("data", [])
                total = int(response_data.get("recordsFiltered") or 0)
                if total <= 0:
                    raise RuntimeError("resposta documental sem recordsFiltered positivo")
                if any(asset.isin.upper() not in str(row.get("descricaoFundo", "")).upper() for row in rows):
                    raise RuntimeError("documento de certificado incompatível")
                documents = [self._to_document(asset, row) for row in rows]
                pages = 1
                seen_ids = {
                    str(row.get("id") or row.get("idDocumento") or row.get("id_documento"))
                    for row in rows
                    if row.get("id") or row.get("idDocumento") or row.get("id_documento")
                }
                while len(documents) < total:
                    next_button = page.locator("#tblDocumentosEnviados_next")
                    if not next_button.count() or "disabled" in (next_button.get_attribute("class") or ""):
                        raise RuntimeError("paginação nativa terminou antes de recordsFiltered")
                    with page.expect_response(
                        lambda item: "pesquisarGerenciadorDocumentosDados" in item.url,
                        timeout=self.timeout_ms,
                    ) as response_info:
                        next_button.click()
                    page_response = response_info.value
                    page_payload = self._parse_native_response(page_response, diagnostics)
                    page_rows = page_payload.get("data", [])
                    if not page_rows:
                        raise RuntimeError("página nativa sem documentos")
                    for row in page_rows:
                        row_id = str(row.get("id") or row.get("idDocumento") or row.get("id_documento"))
                        if row_id and row_id in seen_ids:
                            continue
                        if asset.isin.upper() not in str(row.get("descricaoFundo", "")).upper():
                            raise RuntimeError("documento de certificado incompatível")
                        if row_id:
                            seen_ids.add(row_id)
                        documents.append(self._to_document(asset, row))
                    pages += 1
                return CollectionResult(
                    documents[:total],
                    administrator_id,
                    id_fundo,
                    total,
                    pages,
                    [],
                    [],
                    diagnostics,
                )
            except Exception as error:
                diagnostics["errors"].append(f"{type(error).__name__}: {error}")
                logger.exception("Falha na coleta nativa Fundos.NET para %s", asset.codigo_cetip)
                return CollectionResult(
                    [], administrator_id, id_fundo, 0, 0, [], diagnostics["errors"], diagnostics
                )
            finally:
                self._write_diagnostics(diagnostics, "fundosnet_native_ui_diagnostic.json")
                browser.close()

    def _ui_select_administrator(
        self, page, asset: Asset, administrator: dict[str, Any], diagnostics: dict[str, Any]
    ) -> int:
        page.locator("#administrador").evaluate(
            """el => { $(el).select2('open'); }"""
        )
        search = page.locator(".select2-drop-active input.select2-input")
        search.fill(asset.securitizadora.split()[0], force=True)
        options = page.locator(
            ".select2-drop-active .select2-results li.select2-result-selectable"
        )
        options.first.wait_for(state="attached", timeout=min(self.timeout_ms, 10_000))
        diagnostics["administrator_options"] = options.all_text_contents()[:20]
        expected_name = normalize_text(administrator["nome"])
        candidate = None
        for index in range(options.count()):
            text = options.nth(index).inner_text()
            normalized = normalize_text(text)
            if expected_name in normalized or normalized.startswith(expected_name):
                candidate = options.nth(index)
                break
        if candidate is None:
            raise RuntimeError("opção visual da securitizadora não corresponde ao administrador validado")
        candidate.click(force=True)
        selected = page.locator("#administrador").input_value()
        if selected != str(administrator["id"]):
            raise RuntimeError(f"securitizadora selecionada inesperada: {selected}")
        page.locator("#administrador").dispatch_event("change")
        page.wait_for_timeout(1000)
        diagnostics["selectors"]["administrador"] = "#administrador + Select2"
        diagnostics["administrator_text"] = page.locator("#administrador").get_attribute("data-nome")
        return int(selected)

    def _install_ui_listeners(self, page, diagnostics: dict[str, Any]) -> None:
        def record(kind, url, method, details=None):
            if any(endpoint in url for endpoint in (
                "listarFundos", "buscarAdministrador",
                "pesquisarGerenciadorDocumentosDados",
            )):
                event = {"kind": kind, "url_path": url.split("?", 1)[0], "method": method}
                if details:
                    event.update(details)
                diagnostics["ui_events"].append(event)

        page.on("request", lambda request: record("request", request.url, request.method))
        page.on("response", lambda response: record(
            "response", response.url, response.request.method,
            {"status": response.status, "content_type": response.headers.get("content-type", "")},
        ))
        page.on("requestfailed", lambda request: record(
            "requestfailed", request.url, request.method, {"failure": request.failure},
        ))
        page.on("console", lambda message: diagnostics["ui_events"].append({
            "kind": "console", "type": message.type, "text": message.text[:500],
        }))
        page.on("pageerror", lambda error: diagnostics["ui_events"].append({
            "kind": "pageerror", "text": str(error)[:500],
        }))

    def _ui_select_fund(
        self, page, asset: Asset, selected: FundosNetMatch, diagnostics: dict[str, Any]
    ) -> int:
        self._install_ui_listeners(page, diagnostics)
        started = time.monotonic()
        diagnostics["idFundo_dom_before"] = self._inspect_id_fundo(page)
        page.locator("#idFundo").evaluate(
            """el => { $('#idFundo').select2('open'); }"""
        )
        search = page.locator(".select2-drop-active input.select2-input")
        search.fill(asset.isin, force=True)
        try:
            page.locator(".select2-results li").filter(has_text=asset.isin).last.wait_for(
                state="attached", timeout=min(self.timeout_ms, 5000)
            )
            ajax_option_found = True
        except Exception:
            ajax_option_found = False
        validated_id = str(selected.id_fundo)
        validated_text = selected.text
        expected_debtor = normalize_text(asset.devedor).split()[:2]
        normalized_certificate = normalize_text(validated_text)
        if (
            str(asset.emissao) not in validated_text
            or any(token not in normalized_certificate for token in expected_debtor)
        ):
            raise RuntimeError("certificado validado não corresponde à emissão/devedor esperados")
        diagnostics["validated_match"] = {
            "id_fundo": validated_id,
            "text": validated_text,
            "isin": selected.isin,
        }
        diagnostics["select2"] = {
            "term": asset.isin,
            "ajax_option_found": ajax_option_found,
            "error": None if ajax_option_found else "select2_timeout",
            "duration_ms": round((time.monotonic() - started) * 1000),
            "disabled": page.locator("#idFundo").is_disabled(),
            "value_before_injection": page.locator("#idFundo").input_value(),
            "options_before_injection": page.locator("#idFundo option").count(),
            "tag_name": page.locator("#idFundo").evaluate("el => el.tagName"),
            "input_type": page.locator("#idFundo").get_attribute("type"),
            "hidden_accessible": "select2-hidden-accessible" in (
                page.locator("#idFundo").get_attribute("class") or ""
            ),
            "search_text": page.locator(".select2-results").all_text_contents()[:10],
        }
        page.locator("#idFundo").evaluate(
            """(el, {id, text}) => {
                const data = {id: String(id), text: String(text)};
                $(el).select2('data', [data]);
                $(el).trigger('change');
                $(el).trigger({
                    type: 'select2:select',
                    params: {data}
                });
            }""",
            {"id": validated_id, "text": validated_text},
        )
        selected_value = page.locator("#idFundo").input_value()
        if selected_value != validated_id:
            raise RuntimeError(f"certificado selecionado inesperado: {selected_value}")
        displayed = page.locator("#s2id_idFundo").inner_text()
        if asset.isin.upper() not in f"{displayed} {validated_text}".upper():
            raise RuntimeError("Select2 não exibiu o certificado validado")
        diagnostics["selectors"]["idFundo"] = "#idFundo + Select2"
        diagnostics["certificate_text"] = validated_text
        diagnostics["select2"]["injected"] = True
        diagnostics["select2"]["value_after_injection"] = selected_value
        diagnostics["select2"]["selected_count"] = 1
        diagnostics["idFundo_dom_after"] = self._inspect_id_fundo(page)
        return int(selected_value)

    @staticmethod
    def _inspect_id_fundo(page) -> dict[str, Any]:
        return page.locator("#idFundo").evaluate(
            """el => {
                const attrs = {};
                for (const attr of el.attributes) attrs[attr.name] = attr.value;
                const jq = window.jQuery;
                const events = jq && jq._data ? jq._data(el, 'events') : null;
                const eventNames = events ? Object.keys(events) : [];
                let select2Data = null;
                if (jq) {
                    try {
                        const value = jq(el).data('select2');
                        select2Data = value ? {
                            keys: Object.keys(value),
                            containerId: value.container && value.container.id || null,
                            dropdownId: value.dropdown && value.dropdown.id || null,
                            sourceUrl: value.opts && value.opts.ajax && value.opts.ajax.url || null
                        } : null;
                    } catch (_) {}
                }
                return {
                    tag: el.tagName,
                    type: el.getAttribute('type'),
                    value: el.value,
                    attributes: attrs,
                    classList: Array.from(el.classList),
                    eventNames,
                    select2Data,
                    optionCount: el.options ? el.options.length : null,
                    parentTag: el.parentElement && el.parentElement.tagName,
                    parentClass: el.parentElement && el.parentElement.className
                };
            }"""
        )

    def _capture_native_document_xhr(
        self,
        page,
        asset: Asset,
        administrator_id: int,
        id_fundo: int,
        diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        if page.locator(".quadroCaptcha:visible").count():
            diagnostics["captcha"] = "captcha_required_before_document_query"
            raise RuntimeError("captcha_required")
        with page.expect_response(
            lambda response: "pesquisarGerenciadorDocumentosDados" in response.url,
            timeout=self.timeout_ms,
        ) as response_info:
            filter_button = page.locator("#filtrar")
            diagnostics["filter_state"] = {
                "count": filter_button.count(),
                "visible": filter_button.is_visible(),
                "enabled": filter_button.is_enabled(),
                "value": filter_button.get_attribute("value"),
                "id_fundo": page.locator("#idFundo").input_value(),
                "administrator": page.locator("#administrador").input_value(),
                "tipo_fundo": page.locator("#tipoFundo").input_value(),
            }
            filter_button.evaluate("el => el.click()")
        response = response_info.value
        payload = self._parse_native_response(response, diagnostics)
        if int(payload.get("recordsFiltered") or 0) <= 0:
            raise RuntimeError("resposta documental sem recordsFiltered positivo")
        rows = payload.get("data", [])
        if any(asset.isin.upper() not in str(row.get("descricaoFundo", "")).upper() for row in rows):
            raise RuntimeError("documento de certificado incompatível")
        diagnostics["native_xhr"].append(
            {
                "url": response.url,
                "url_path": response.url.split("?", 1)[0],
                "status": response.status,
                "content_type": response.headers.get("content-type", ""),
                "parameters": {
                    key: values[-1]
                    for key, values in parse_qs(
                        urlsplit(response.request.url).query,
                        keep_blank_values=True,
                    ).items()
                    if key not in {"token", "csrf", "_csrf"}
                },
                "administrator_id": administrator_id,
                "id_fundo": id_fundo,
                "tipo_fundo": page.locator("#tipoFundo").input_value(),
                "is_session": payload.get("isSession"),
                "recordsFiltered": payload.get("recordsFiltered"),
                "recordsTotal": payload.get("recordsTotal"),
                "row_count": len(rows),
                "certificate_descriptions": sorted({
                    str(row.get("descricaoFundo", "")) for row in rows
                }),
                "row_keys": sorted(rows[0].keys()) if rows else [],
                "sample_rows": rows[:2],
            }
        )
        return payload

    def _parse_native_response(self, response, diagnostics: dict[str, Any]) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "").lower()
        if response.status != 200 or "application/json" not in content_type:
            diagnostics["native_xhr"].append(
                {
                    "url_path": response.url.split("?", 1)[0],
                    "status": response.status,
                    "content_type": content_type,
                    "classification": "sessao_invalida_ou_bloqueio"
                    if "text/html" in content_type
                    else "resposta_invalida",
                }
            )
            if "text/html" in content_type:
                raise RuntimeError("sessao_invalida_ou_bloqueio")
            raise RuntimeError("resposta documental inválida")
        return response.json()

    def _collect_context_request(self, asset: Asset) -> CollectionResult:
        with sync_playwright() as playwright:
            browser = self._launch_browser(playwright)
            context = browser.new_context(locale="pt-BR")
            page = context.new_page()
            diagnostics: dict[str, Any] = {
                "browser_context": True,
                "cookies": [],
                "page_status": None,
                "page_title": None,
                "json_probe": None,
                "attempts": [],
                "html_diagnostics": [],
            }
            administrator_id = None
            id_fundo = None
            try:
                try:
                    response = page.goto(
                        self.BASE_URL + "abrirGerenciadorDocumentosCertificadosCVM",
                        timeout=self.timeout_ms,
                        wait_until="commit",
                    )
                    page.wait_for_timeout(1500)
                    diagnostics["page_status"] = response.status if response else None
                except Exception as error:
                    diagnostics["page_navigation_error"] = f"{type(error).__name__}: {error}"
                diagnostics["page_title"] = page.title()
                diagnostics["cookies"] = [
                    {"name": cookie["name"], "domain": cookie["domain"]}
                    for cookie in context.cookies()
                ]
                administrator = self._find_administrador(page, context, asset.securitizadora, diagnostics)
                if administrator is None:
                    return CollectionResult([], None, None, 0, 0, [], ["administrador não encontrado"], diagnostics)
                administrator_id = int(administrator["id"])
                matches = self._search_fundos(
                    page, context, asset, administrator_id, product_type_id(asset.tipo_ativo), diagnostics
                )
                selected = self._select_match(asset, matches)
                if selected is None:
                    return CollectionResult([], administrator_id, None, 0, 0, [], ["certificado ambíguo ou incompatível"], diagnostics)
                id_fundo = selected.id_fundo
                rows, total, pages = self._fetch_documentos(page, context, selected.id_fundo, diagnostics)
                documents = [self._to_document(asset, row) for row in rows]
                rejected = [
                    {"reason": "id do documento ausente", "row": repr(row)}
                    for row, document in zip(rows, documents)
                    if not document.source_document_id
                ]
                documents = [document for document in documents if document.source_document_id]
                return CollectionResult(
                    documents,
                    administrator_id,
                    id_fundo,
                    total,
                    pages,
                    rejected,
                    [],
                    diagnostics,
                )
            except Exception as error:
                logger.exception("Falha na coleta Fundos.NET para %s", asset.codigo_cetip)
                return CollectionResult([], administrator_id, id_fundo, 0, 0, [], [f"{type(error).__name__}: {error}"], diagnostics)
            finally:
                self._write_diagnostics(diagnostics)
                browser.close()

    def _launch_browser(self, playwright):
        try:
            return playwright.chromium.launch(channel=self.browser_channel, headless=self.headless)
        except Exception as error:
            logger.warning("Edge indisponível (%s); usando Chromium", type(error).__name__)
            return playwright.chromium.launch(headless=self.headless)

    def _find_administrador(self, page, context, name: str, diagnostics) -> dict[str, Any] | None:
        first_token = name.strip().split()[0] if name.strip() else ""
        candidates = [
            first_token,
            name,
            f"{name} Securitizadora",
            f"{name} Securitizadora S.A.",
        ]
        for term in candidates:
            payload = self._request_json(
                page, context,
                "buscarAdministrador",
                {"term": term, "page": 1, "paginaCertificados": "true"},
                diagnostics,
            )
            if diagnostics["json_probe"] is None:
                diagnostics["json_probe"] = "buscarAdministrador"
            rows, _, _ = self._extract_rows(payload)
            matches = []
            expected = normalize_text(name)
            for row in rows:
                text = row.get("text") or row.get("nome") or row.get("descricao") or ""
                identifier = row.get("id") or row.get("idAdm") or row.get("administrador_id")
                normalized_text = normalize_text(text)
                alias_match = (
                    normalize_text(name).startswith("ECO SECURITIZADORA")
                    and normalized_text.startswith("ECO SECURITIZADORA")
                )
                first_token_match = (
                    term.casefold() == first_token.casefold()
                    and normalized_text.startswith(normalize_text(first_token))
                )
                if identifier and (expected in normalized_text or alias_match or first_token_match):
                    matches.append({"id": identifier, "nome": text})
            if len(matches) == 1:
                return matches[0]
        return None

    def _search_fundos(self, page, context, asset: Asset, administrator_id: int, type_id: int, diagnostics) -> list[FundosNetMatch]:
        terms = [term for term in (asset.isin, asset.emissao, asset.devedor) if term]
        seen: set[str] = set()
        matches: list[FundosNetMatch] = []
        diagnostics.setdefault("listar_fundos_payloads", [])
        for term in terms:
            if term in seen:
                continue
            seen.add(term)
            payload = self._request_json(
                page, context,
                "listarFundos",
                {
                    "term": term,
                    "page": 1,
                    "idTipoFundo": type_id,
                    "idAdm": administrator_id,
                    "paraCerts": "true",
                },
                diagnostics,
            )
            diagnostics["listar_fundos_payloads"].append(
                {"term": term, "payload": payload}
            )
            rows, _, _ = self._extract_rows(payload)
            for row in rows:
                identifier = row.get("idFundo") or row.get("id") or row.get("id_fundo")
                text = row.get("text") or row.get("texto") or row.get("descricao") or row.get("nome") or ""
                if identifier:
                    matches.append(FundosNetMatch(int(identifier), str(text), row.get("isin") or row.get("ISIN"), row))
        return matches

    def _select_match(self, asset: Asset, matches: list[FundosNetMatch]) -> FundosNetMatch | None:
        unique = {match.id_fundo: match for match in matches}
        if asset.isin:
            isin_matches = [
                match for match in unique.values()
                if asset.isin.upper() in (match.isin or match.text).upper()
            ]
            return isin_matches[0] if len(isin_matches) == 1 else None
        compatible = [
            match for match in unique.values()
            if str(asset.emissao) in match.text
            and (not asset.devedor or normalize_text(asset.devedor) in normalize_text(match.text))
        ]
        return compatible[0] if len(compatible) == 1 else None

    def _fetch_documentos(self, page, context, id_fundo: int, diagnostics) -> tuple[list[dict[str, Any]], int, int]:
        all_rows: list[dict[str, Any]] = []
        page_number = 1
        total = 0
        while True:
            payload = self._request_json(
                page, context,
                "pesquisarGerenciadorDocumentosDados",
                {
                    "draw": page_number,
                    "start": (page_number - 1) * 100,
                    "length": 100,
                    "tipoFundo": 0,
                    "administrador": "",
                    "idFundo": id_fundo,
                    "idCategoriaDocumento": 0,
                    "idTipoDocumento": 0,
                    "idEspecieDocumento": 0,
                    "situacao": "",
                    "paginaCertificados": "true",
                    "isSession": "true",
                },
                diagnostics,
            )
            rows, total, _ = self._extract_rows(payload)
            all_rows.extend(rows)
            if not rows or len(all_rows) >= total or len(rows) < 100:
                return all_rows, total or len(all_rows), page_number
            page_number += 1

    def _request_json(self, page, context, endpoint: str, params: dict[str, Any], diagnostics):
        query = {key: str(value) for key, value in params.items() if value is not None}
        last_error = None
        for attempt, delay in enumerate((0, 2, 5), start=1):
            if delay:
                time.sleep(delay)
            try:
                diagnostics["attempts"].append({"endpoint": endpoint, "attempt": attempt})
                response = context.request.get(
                    self.BASE_URL + endpoint,
                    params=query,
                    headers={
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": self.BASE_URL + "abrirGerenciadorDocumentosCertificadosCVM",
                    },
                    timeout=self.timeout_ms,
                )
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    body = response.text()
                    diagnostics["html_diagnostics"].append(
                        self._classify_html(endpoint, response.status, response.url, body)
                    )
                    fallback = self._page_fetch_json(page, endpoint, query)
                    if fallback is not None:
                        return fallback
                    raise RuntimeError("sessao_invalida_ou_bloqueio")
                if not response.ok:
                    raise RuntimeError(f"{endpoint} retornou HTTP {response.status}")
                return response.json()
            except Exception as error:
                last_error = error
                if "Timeout" not in type(error).__name__:
                    break
        raise last_error

    def _page_fetch_json(self, page, endpoint: str, params: dict[str, str]):
        try:
            result = page.evaluate(
                """async ({url, params}) => {
                    const query = new URLSearchParams(params);
                    const response = await fetch(url + '?' + query.toString(), {
                        credentials: 'include',
                        headers: {
                            'Accept': 'application/json, text/javascript, */*; q=0.01',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                    const contentType = response.headers.get('content-type') || '';
                    const text = await response.text();
                    return {status: response.status, contentType, text};
                }""",
                {"url": self.BASE_URL + endpoint, "params": params},
            )
            if "application/json" not in result["contentType"].lower():
                return None
            return json.loads(result["text"])
        except Exception:
            return None

    @staticmethod
    def _classify_html(endpoint: str, status: int, url: str, body: str) -> dict[str, Any]:
        compact = re.sub(r"<script\b[^>]*>.*?</script>", " ", body, flags=re.IGNORECASE | re.DOTALL)
        compact = re.sub(r"<style\b[^>]*>.*?</style>", " ", compact, flags=re.IGNORECASE | re.DOTALL)
        compact = re.sub(r"\s+", " ", compact)
        compact = re.sub(r"\b(rid|rpid|cf_clearance|token|captcha)[^,; ]*", "[REMOVIDO]", compact, flags=re.IGNORECASE)
        lowered = compact.casefold()
        classification = "redirecionamento_ou_sessao"
        if "captcha" in lowered or "challenge" in lowered:
            classification = "protecao"
        return {
            "endpoint": endpoint,
            "status": status,
            "url": url,
            "size": len(body),
            "classification": classification,
            "preview": compact[:1000],
        }

    @staticmethod
    def _write_diagnostics(
        diagnostics: dict[str, Any],
        filename: str = "fundosnet_session_diagnostics.json",
    ) -> None:
        path = Path("reports") / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _extract_rows(payload) -> tuple[list[dict[str, Any]], int, int]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)], len(payload), 1
        if not isinstance(payload, dict):
            return [], 0, 1
        for key in ("data", "results", "rows", "aaData", "documentos"):
            rows = payload.get(key)
            if isinstance(rows, list):
                total = int(payload.get("total") or payload.get("recordsTotal") or len(rows))
                return [row for row in rows if isinstance(row, dict)], total, 1
        return [], 0, 1

    @staticmethod
    def _to_document(asset: Asset, item: dict[str, Any]) -> Document:
        return Document(
            asset_id=asset.asset_id or 0,
            source_document_id=str(item.get("id") or item.get("document_id") or item.get("codigo") or ""),
            category=classify_document(item),
            document_name=str(
                item.get("titulo")
                or item.get("nome")
                or item.get("descricao")
                or item.get("tipoDocumento")
                or "Documento"
            ),
            source="Fundos.NET",
            source_url=str(
                item.get("url")
                or item.get("link")
                or item.get("linkDocumento")
                or item.get("urlDocumento")
                or item.get("urlDownload")
                or item.get("href")
                or (
                    f"https://fnet.bmfbovespa.com.br/fnet/publico/visualizarDocumento"
                    f"?id={item.get('id')}"
                    if item.get("id")
                    else ""
                )
                or ""
            ),
            reference_date=str(item.get("data_referencia") or item.get("ref_date") or "") or None,
            publication_date=str(item.get("data_publicacao") or item.get("dataEntrega") or "") or None,
            file_hash=item.get("hash_arquivo") or item.get("file_hash") or item.get("sha256"),
            download_status="pending",
            collected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
