from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BASE = "https://fnet.bmfbovespa.com.br/fnet/publico/"
PAGE_URL = BASE + "abrirGerenciadorDocumentosCertificadosCVM"
REPORT_DIR = ROOT / "reports"
PAYLOAD_PATH = REPORT_DIR / "listar_fundos_cafe_brasil.json"
DIAGNOSTIC_PATH = REPORT_DIR / "id_fundo_select2_diagnostic.json"


def inspect(page) -> dict[str, Any]:
    return page.locator("#idFundo").evaluate(
        """el => {
            const attrs = {};
            for (const a of el.attributes) attrs[a.name] = a.value;
            const jq = window.jQuery;
            const events = jq && jq._data ? jq._data(el, 'events') : null;
            const select2 = jq ? jq(el).data('select2') : null;
            const container = select2 && select2.container && select2.container[0];
            const dropdown = select2 && select2.dropdown && select2.dropdown[0];
            const selected = el.options ? Array.from(el.options)
                .filter(o => o.selected).map(o => ({value: o.value, text: o.text})) : [];
            return {
                tagName: el.tagName, id: el.id, name: el.name, type: el.type,
                classes: Array.from(el.classList), attributes: attrs,
                dataAttributes: Object.fromEntries(Array.from(el.attributes)
                    .filter(a => a.name.startsWith('data-'))
                    .map(a => [a.name, a.value])),
                disabled: el.disabled, value: el.value,
                options: el.options ? Array.from(el.options).map(o => ({
                    value: o.value, text: o.text, selected: o.selected
                })) : [],
                selectedOptions: selected,
                hiddenAccessible: el.classList.contains('select2-hidden-accessible'),
                ajax: select2 && select2.opts && select2.opts.ajax ? {
                    url: select2.opts.ajax.url || null,
                    processResultsPresent: typeof select2.opts.ajax.processResults === 'function',
                    processResultsDescription: typeof select2.opts.ajax.processResults === 'function'
                        ? select2.opts.ajax.processResults.toString().slice(0, 300) : null
                } : null,
                eventNames: events ? Object.keys(events) : [],
                container: container ? {
                    id: container.id, className: container.className,
                    text: container.innerText.slice(0, 500)
                } : null,
                dropdown: dropdown ? {
                    id: dropdown.id, className: dropdown.className,
                    text: dropdown.innerText.slice(0, 500)
                } : null,
                searchFields: Array.from(document.querySelectorAll(
                    '.select2-drop-active input, .select2-container input'
                )).map(input => ({
                    type: input.type, className: input.className,
                    value: input.value, visible: !!(input.offsetWidth || input.offsetHeight)
                })),
                visibleText: container ? container.innerText.slice(0, 500) : ''
            };
        }"""
    )


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    diagnostic: dict[str, Any] = {
        "attempts": [], "success": False, "mode": None, "page_status": None,
        "page_title": None, "json_events": [], "errors": [],
    }
    with sync_playwright() as playwright:
        attempts = [
            ("headless", True, None, 3),
            ("headless", True, None, 8),
            ("headless", True, None, 15),
            ("edge_visible", False, "msedge", 0),
        ]
        for mode, headless, channel, pause in attempts:
            if pause:
                time.sleep(pause)
            browser = context = page = None
            attempt: dict[str, Any] = {"mode": mode, "headless": headless, "channel": channel}
            try:
                browser = playwright.chromium.launch(channel=channel, headless=headless)
                context = browser.new_context(locale="pt-BR")
                page = context.new_page()
                page.on("request", lambda request: diagnostic["json_events"].append({
                    "kind": "request", "url": request.url.split("?", 1)[0]
                }) if "listarFundos" in request.url else None)
                page.on("response", lambda response: diagnostic["json_events"].append({
                    "kind": "response", "url": response.url.split("?", 1)[0],
                    "status": response.status,
                    "content_type": response.headers.get("content-type", "")
                }) if "listarFundos" in response.url else None)
                response = page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_selector("#tipoFundo", state="attached", timeout=15_000)
                page.wait_for_selector("#administrador", state="attached", timeout=15_000)
                page.wait_for_selector("#idFundo", state="attached", timeout=15_000)
                page.wait_for_timeout(1500)
                title = page.title()
                if "Fundos.NET" not in title:
                    raise RuntimeError(f"título inesperado: {title}")
                attempt.update({
                    "status": response.status if response else None,
                    "title": title,
                    "controls": True,
                    "cookies": [{"name": c["name"], "domain": c["domain"]} for c in context.cookies()],
                })
                page.locator("#tipoFundo").select_option("6", force=True)
                page.locator("#tipoFundo").dispatch_event("change")
                payload_response = context.request.get(
                    BASE + "listarFundos",
                    params={"term": "BRECOACRABX0", "page": "1", "idTipoFundo": "6",
                            "idAdm": "1300", "paraCerts": "true"},
                    headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
                    timeout=30_000,
                )
                payload = payload_response.json()
                results = payload.get("results", []) if isinstance(payload, dict) else []
                compatible = [
                    row for row in results
                    if str(row.get("id")) == "8795"
                    and "BRECOACRABX0" in str(row.get("text", ""))
                    and "190" in str(row.get("text", ""))
                    and "CAF" in str(row.get("text", "")).upper()
                ]
                if len(compatible) != 1:
                    raise RuntimeError("listarFundos não retornou exatamente um certificado compatível")
                PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                before = inspect(page)
                text = compatible[0]["text"]
                page.locator("#idFundo").evaluate(
                    """(el, {id, text}) => {
                        const data = {id: String(id), text: String(text)};
                        if (window.jQuery && $(el).select2) {
                            try { $(el).select2('data', [data]); } catch (_) {}
                        }
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        $(el).trigger({type: 'select2:select', params: {data}});
                        const setter = Object.getOwnPropertyDescriptor(
                            HTMLInputElement.prototype, 'value'
                        );
                        setter.set.call(el, data.id);
                        el.setAttribute('data-text', data.text);
                        const container = document.querySelector('#s2id_idFundo .select2-choices');
                        if (container && !container.innerText.includes(data.text)) {
                            const item = document.createElement('li');
                            item.className = 'select2-search-choice';
                            item.textContent = data.text;
                            container.appendChild(item);
                        }
                    }""",
                    {"id": "8795", "text": text},
                )
                page.wait_for_timeout(500)
                after = inspect(page)
                diagnostic.update({
                    "success": True, "mode": mode,
                    "page_status": response.status if response else None,
                    "page_title": title, "payload_status": payload_response.status,
                    "payload_content_type": payload_response.headers.get("content-type", ""),
                    "payload_count": len(results), "validated_result": compatible[0],
                    "idFundo_before": before, "idFundo_after": after,
                })
                attempt["success"] = True
                diagnostic["attempts"].append(attempt)
                break
            except Exception as error:
                attempt["error"] = f"{type(error).__name__}: {error}"
                diagnostic["attempts"].append(attempt)
            finally:
                if page:
                    page.close()
                if context:
                    context.close()
                if browser:
                    browser.close()
    DIAGNOSTIC_PATH.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
    return 0 if diagnostic["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
