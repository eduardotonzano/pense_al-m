from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "".join(
    [
        "https:",
        "//fnet.bmfbovespa.com.br/",
        "fnet/publico/",
        "abrirGerenciadorDocumentosCertificadosCVM",
    ]
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SCREENSHOT_PATH = REPORTS_DIR / "fundosnet_headless.png"


def main() -> None:
    print("Iniciando teste automático do Fundos.NET...")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
        )

        page = browser.new_page(
            locale="pt-BR",
        )

        try:
            response = page.goto(
                URL,
                timeout=120_000,
                wait_until="domcontentloaded",
            )

            status = response.status if response else None

            page.screenshot(
                path=str(SCREENSHOT_PATH),
                full_page=True,
            )

            print("Teste concluído.")
            print("Status HTTP:", status)
            print("Título:", page.title())
            print("URL final:", page.url)
            print("Imagem salva em:", SCREENSHOT_PATH)

            if status == 200:
                print("Resultado: acesso automático funcionando.")
            else:
                print("Resultado: acesso aconteceu, mas precisa de análise.")

        except Exception as error:
            print("Resultado: falha no acesso automático.")
            print("Tipo do erro:", type(error).__name__)
            print("Detalhes:", error)

        finally:
            browser.close()


if __name__ == "__main__":
    main()