from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, Response, sync_playwright

URL = (
    "https://fnet.bmfbovespa.com.br/"
    "fnet/publico/abrirGerenciadorDocumentosCertificadosCVM"
)

INTERESTING_TERMS = (
    "pesquisar",
    "listar",
    "documento",
    "gerenciador",
    "certificado",
    "grid",
    "cvm",
    "consulta",
)

MAX_WAIT_SECONDS = 10 * 60
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "fundosnet_capturas.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove credenciais antes de persistir a captura."""
    sensitive = {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
        "x-api-key",
    }
    return {
        key: "[REMOVIDO]" if key.lower() in sensitive else value
        for key, value in headers.items()
    }


def mark_interesting(url: str) -> bool:
    normalized = url.lower()
    return any(term in normalized for term in INTERESTING_TERMS)


def safe_response_preview(response: Response, limit: int = 5000) -> str:
    """Lê somente respostas textuais e nunca interrompe a execução por erro."""
    content_type = response.headers.get("content-type", "").lower()
    textual = any(
        marker in content_type
        for marker in ("json", "text", "javascript", "xml", "html")
    )
    if not textual:
        return ""

    try:
        return response.text()[:limit]
    except Exception as error:  # diagnóstico não pode derrubar o script
        return f"[CORPO INDISPONIVEL: {type(error).__name__}: {error}]"[:limit]


def build_capture(response: Response) -> dict[str, Any] | None:
    request = response.request
    content_type = response.headers.get("content-type", "")
    resource_type = request.resource_type
    should_capture = resource_type in {"xhr", "fetch"} or "json" in content_type.lower()

    if not should_capture:
        return None

    return {
        "timestamp": utc_now(),
        "interesting": mark_interesting(response.url),
        "method": request.method,
        "url": response.url,
        "resource_type": resource_type,
        "status": response.status,
        "content_type": content_type,
        "request_headers": redact_headers(request.headers),
        "post_data": request.post_data or "",
        "response_preview": safe_response_preview(response),
    }


def launch_browser(playwright: Playwright) -> tuple[Browser, str]:
    try:
        return (
            playwright.chromium.launch(channel="msedge", headless=False),
            "Microsoft Edge",
        )
    except Exception as edge_error:
        print(f"Edge indisponível ({type(edge_error).__name__}). Usando Chromium.")
        return playwright.chromium.launch(headless=False), "Chromium"


def wait_for_enter_or_timeout(page: Page, timeout_seconds: int) -> str:
    finished = threading.Event()

    def wait_for_input() -> None:
        try:
            input("\nQuando a lista de documentos aparecer, pressione ENTER aqui...\n")
            finished.set()
        except (EOFError, KeyboardInterrupt):
            finished.set()

    threading.Thread(target=wait_for_input, daemon=True).start()
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if finished.is_set():
            return "enter"
        if page.is_closed():
            return "browser_closed"
        page.wait_for_timeout(500)

    return "timeout"


def save_jsonl(captures: list[dict[str, Any]]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as output:
        for capture in captures:
            output.write(json.dumps(capture, ensure_ascii=False) + "\n")


def main() -> int:
    captures: list[dict[str, Any]] = []
    browser: Browser | None = None
    page: Page | None = None
    end_reason = "unknown"

    # Garante a existência do arquivo até quando o navegador falhar cedo.
    save_jsonl(captures)

    try:
        with sync_playwright() as playwright:
            browser, browser_name = launch_browser(playwright)
            page = browser.new_page(locale="pt-BR")

            def on_response(response: Response) -> None:
                try:
                    capture = build_capture(response)
                    if capture is None:
                        return
                    captures.append(capture)
                    star = "⭐ " if capture["interesting"] else ""
                    print(
                        f'{star}{capture["status"]} {capture["method"]} '
                        f'{capture["resource_type"]} {capture["url"]}'
                    )
                except Exception as error:
                    print(
                        "Aviso: não foi possível registrar uma resposta: "
                        f"{type(error).__name__}: {error}"
                    )

            page.on("response", on_response)

            print("=" * 72)
            print("CAPTURA TÉCNICA DO FUNDOS.NET")
            print(f"Navegador: {browser_name}")
            print("1. No site, selecione CRA.")
            print("2. Pesquise Eco Securitizadora (CNPJ 10.753.164/0001-43).")
            print("3. Filtre a emissão 190 ou o código CRA022009VM.")
            print("4. Abra a lista de documentos.")
            print("Não é necessário abrir o DevTools.")
            print("O processo encerra sozinho após 10 minutos.")
            print("=" * 72)

            try:
                response = page.goto(
                    URL,
                    timeout=120_000,
                    wait_until="domcontentloaded",
                )
                status = response.status if response else "sem resposta"
                print(f"Página carregada. Status HTTP: {status}")
            except Exception as navigation_error:
                print(
                    "O site não carregou completamente: "
                    f"{type(navigation_error).__name__}: {navigation_error}"
                )

            end_reason = wait_for_enter_or_timeout(page, MAX_WAIT_SECONDS)

    except Exception as error:
        end_reason = "unhandled_guarded_error"
        print(f"Falha protegida: {type(error).__name__}: {error}")
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

        save_jsonl(captures)
        interesting_count = sum(1 for item in captures if item["interesting"])
        print("\n" + "=" * 72)
        print("CAPTURA FINALIZADA")
        print(f"Motivo do encerramento: {end_reason}")
        print(f"Total de chamadas capturadas: {len(captures)}")
        print(f"Chamadas marcadas com ⭐: {interesting_count}")
        print(f"Arquivo salvo em: {OUTPUT_PATH}")
        print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

