from urllib.request import Request
from urllib.request import urlopen


URL = (
    "https://www.debentures.com.br/"
    "exploreosnd/consultaadados/"
    "emissoesdedebentures/"
    "caracteristicas_e.asp?Ativo=PETR27"
)


request = Request(
    URL,
    headers={
        "User-Agent": "debenture-search-debug/1.0",
        "Accept": "*/*",
    },
    method="GET",
)


with urlopen(
    request,
    timeout=20,
) as response:
    payload = response.read(1024 * 1024)

    print("URL solicitada:")
    print(URL)

    print()
    print("URL final:")
    print(response.geturl())

    print()
    print("Status HTTP:")
    print(response.status)

    print()
    print("Content-Type:")
    print(response.headers.get("Content-Type"))

    print()
    print("Content-Encoding:")
    print(response.headers.get("Content-Encoding"))

    print()
    print("Tamanho lido:")
    print(len(payload))

    print()
    print("Primeiros 100 bytes:")
    print(repr(payload[:100]))

    charset = (
        response.headers.get_content_charset()
        or "latin-1"
    )

    try:
        text = payload.decode(charset)
    except (LookupError, UnicodeDecodeError):
        text = payload.decode(
            "latin-1",
            errors="replace",
        )

    print()
    print("Charset utilizado:")
    print(charset)

    print()
    print("Primeiros 500 caracteres:")
    print(repr(text[:500]))

    print()
    print("Indicadores encontrados:")
    print("Contem html:", "<html" in text.lower())
    print("Contem table:", "<table" in text.lower())
    print("Contem PETR27:", "PETR27" in text.upper())
    print("Contem acesso negado:", "acesso negado" in text.lower())
    print("Contem captcha:", "captcha" in text.lower())
