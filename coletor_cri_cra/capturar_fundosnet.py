from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, Request, Response, sync_playwright

from src.fundosnet_client import sanitizar_headers, sanitizar_texto, url_relevante


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

DATA_HORA = datetime.now().strftime("%Y%m%d_%H%M%S")
ARQUIVO_REQUISICOES = LOG_DIR / f"fundosnet_requests_{DATA_HORA}.json"
ARQUIVO_RESPOSTAS = LOG_DIR / f"fundosnet_responses_{DATA_HORA}.json"
ARQUIVO_HAR = LOG_DIR / f"fundosnet_{DATA_HORA}.har"
URL_INICIAL = (
    "https://fnet.bmfbovespa.com.br/"
    "fnet/publico/abrirGerenciadorDocumentosCVM"
)


def registrar_requisicao(request: Request, requisicoes: list[dict]) -> None:
    if request.resource_type not in {"xhr", "fetch"} or not url_relevante(request.url):
        return

    requisicoes.append(
        {
            "data_hora": datetime.now().isoformat(),
            "metodo": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "headers": sanitizar_headers(request.headers),
            "post_data": sanitizar_texto(request.post_data or ""),
        }
    )
    print(f"\n[REQUISICAO CAPTURADA] {request.method} {request.url}")


def registrar_resposta(response: Response, respostas: list[dict]) -> None:
    request = response.request
    if request.resource_type not in {"xhr", "fetch"} or not url_relevante(response.url):
        return

    content_type = response.headers.get("content-type", "")
    corpo_preview = ""
    try:
        if any(tipo in content_type.lower() for tipo in ("json", "text", "javascript")):
            corpo_preview = response.text()[:5000]
    except Exception as erro:
        corpo_preview = f"[Nao foi possivel ler o corpo: {erro}]"

    respostas.append(
        {
            "data_hora": datetime.now().isoformat(),
            "status": response.status,
            "url": response.url,
            "content_type": content_type,
            "headers": sanitizar_headers(response.headers),
            "corpo_preview": sanitizar_texto(corpo_preview),
        }
    )
    print(f"\n[RESPOSTA CAPTURADA] {response.status} {response.url}")
    print("Content-Type:", content_type)


def abrir_pagina(page: Page) -> None:
    try:
        page.goto(URL_INICIAL, wait_until="domcontentloaded", timeout=120_000)
    except Exception as erro:
        print(f"Falha ao abrir diretamente a pagina: {erro}")
        print("Tentando abrir a pagina inicial do Fundos.NET.")
        page.goto(
            "https://fnet.bmfbovespa.com.br/",
            wait_until="domcontentloaded",
            timeout=120_000,
        )


def main() -> None:
    requisicoes: list[dict] = []
    respostas: list[dict] = []

    print("\n=== Captura de rede do Fundos.NET ===")
    print("Pesquise no navegador usando, quando disponivel:")
    print("  Securitizadora: Eco Securitizadora")
    print("  CNPJ: 10.753.164/0001-43")
    print("  Tipo: CRA")
    print("  Emissao: 190")
    print("  CETIP: CRA022009VM")
    print("\nQuando a grade aparecer, pressione ENTER neste terminal.\n")

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=False, slow_mo=100)
        contexto = navegador.new_context(
            locale="pt-BR",
            accept_downloads=True,
            record_har_path=str(ARQUIVO_HAR),
            record_har_content="embed",
        )
        pagina = contexto.new_page()
        pagina.on("request", lambda request: registrar_requisicao(request, requisicoes))
        pagina.on("response", lambda response: registrar_resposta(response, respostas))

        try:
            abrir_pagina(pagina)
            input("Faca a pesquisa no navegador. Quando terminar, pressione ENTER aqui...")
        finally:
            ARQUIVO_REQUISICOES.write_text(
                json.dumps(requisicoes, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            ARQUIVO_RESPOSTAS.write_text(
                json.dumps(respostas, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            contexto.close()
            navegador.close()

    print("\n=== Captura concluida ===")
    print(f"Requisicoes: {ARQUIVO_REQUISICOES}")
    print(f"Respostas:   {ARQUIVO_RESPOSTAS}")
    print(f"HAR:         {ARQUIVO_HAR}")
    print(f"Total de requisicoes relevantes: {len(requisicoes)}")
    print(f"Total de respostas relevantes: {len(respostas)}")


if __name__ == "__main__":
    main()
