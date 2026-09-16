from playwright.sync_api import sync_playwright

URL = "".join([
    "https:",
    "//fnet.bmfbovespa.com.br/",
    "fnet/publico/",
    "abrirGerenciadorDocumentosCertificadosCVM",
])

with sync_playwright() as playwright:
    print("Abrindo o Fundos.NET...")

    try:
        browser = playwright.chromium.launch(
            channel="msedge",
            headless=False,
        )
        browser_name = "Microsoft Edge"
    except Exception:
        browser = playwright.chromium.launch(headless=False)
        browser_name = "Chromium"

    page = browser.new_page()

    try:
        response = page.goto(
            URL,
            timeout=120000,
            wait_until="domcontentloaded",
        )

        print("Navegador:", browser_name)
        print("Titulo:", page.title())
        print("URL:", page.url)
        print(
            "Status:",
            response.status if response else "sem resposta",
        )

        page.screenshot(
            path="reports/fundosnet_teste.png",
            full_page=True,
        )

        input(
            "Confira a pagina e pressione ENTER para fechar..."
        )

    except Exception as error:
        print("Falha ao carregar o Fundos.NET:")
        print(error)
        input("Pressione ENTER para fechar...")

    finally:
        browser.close()
