"""Arquivos no formato do dado aberto da CVM para os testes (sem rede).

Os informes do Almeida Junior (CRI) e do Eco/Cafe Brasil (CRA) reproduzem o que
a CVM publica em inf_mensal_cri_2025/2026.zip e inf_mensal_cra_2026.zip (lidos em
23/10/2026): chaves, Data_Entrega, numero da emissao e as linhas de
cedente_devedor, inclusive o marcador "0". Os CSV usam latin-1 e ``;``, como os
da CVM, e as colunas de nome ficam preenchidas de proposito: o resolvedor nao
pode depender delas.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

OPEA = "02.773.542/0001-22"
ALMEIDA_DEVEDOR = "82.120.676/0001-83"
ALMEIDA_ISIN = "BRRBRACRIP13"
ALMEIDA_CETIP = "24G2100031"
ECO = "10.753.164/0001-43"
ECO_ISIN = "BRECOACRABX0"
ECO_CETIP = "CRA022009VM"
CAFE_DEVEDOR_IN_CSV = "01.486.546/0001-67"
CAFE_DEVEDOR_IN_CVM = "31943818000171"
CAFE_CEDENTE_IN_CVM = "23357072000181"
PLACEHOLDER_SHARE = "0.00000000000000000000"
FULL_SHARE = "1.00000000000000000000"

CLASSE_HEADER = [
    "CNPJ_Emissora", "Codigo_Identificacao_Certificado", "Data_Referencia", "Versao",
    "Classe", "Numero_Serie", "Tipo_Oferta", "Codigo_CETIP", "Codigo_ISIN",
    "Quantidade", "Valor", "Data_Vencimento", "Situacao",
]
GERAL_HEADER = [
    "CNPJ_Emissora", "Codigo_Identificacao_Certificado", "Data_Referencia", "Versao",
    "Data_Entrega", "Numero_Emissao", "Nome_Emissao", "Companhia_Emissora",
    "Agente_Fiduciario",
]
PARTY_HEADER = [
    "CNPJ_Emissora", "Codigo_Identificacao_Certificado", "Data_Referencia", "Versao",
    "Tipo", "CNPJ", "Percentual",
]

# Data_Entrega de cada informe do Almeida Junior, como a CVM publica.
ALMEIDA_DELIVERED = {
    "2025-01-01": "2025-02-28", "2025-02-01": "2025-03-31", "2025-03-01": "2025-04-30",
    "2025-04-01": "2025-05-28", "2025-05-01": "2025-06-26", "2025-06-01": "2025-07-28",
    "2025-07-01": "2025-08-22", "2025-08-01": "2025-09-23", "2025-09-01": "2025-10-27",
    "2025-10-01": "2025-11-27", "2025-11-01": "2025-12-26", "2025-12-01": "2026-01-26",
    "2026-01-01": "2026-02-27", "2026-02-01": "2026-03-26", "2026-03-01": "2026-04-27",
    "2026-04-01": "2026-05-26", "2026-05-01": "2026-06-26", "2026-06-01": "2026-07-27",
    "2026-07-01": "2026-08-26", "2026-08-01": "2026-09-28",
}
# A CVM so traz o CNPJ do devedor e do cedente do Almeida a partir de jul/2026.
ALMEIDA_PARTIES_FROM = "2026-07-01"
ECO_DELIVERED = {
    "2026-01-01": "2026-02-24", "2026-02-01": "2026-03-26", "2026-03-01": "2026-04-29",
    "2026-04-01": "2026-05-27", "2026-05-01": "2026-06-26", "2026-06-01": "2026-07-28",
    "2026-07-01": "2026-08-26", "2026-08-01": "2026-09-25",
}


def classe_row(cnpj_emissora, certificate, reference, *, version=1, serie="1", cetip="", isin=""):
    return {
        "CNPJ_Emissora": cnpj_emissora,
        "Codigo_Identificacao_Certificado": certificate,
        "Data_Referencia": reference,
        "Versao": str(version),
        "Numero_Serie": serie,
        "Codigo_CETIP": cetip,
        "Codigo_ISIN": isin,
    }


def geral_row(cnpj_emissora, certificate, reference, *, version=1, delivered="", emissao="", name=""):
    return {
        "CNPJ_Emissora": cnpj_emissora,
        "Codigo_Identificacao_Certificado": certificate,
        "Data_Referencia": reference,
        "Versao": str(version),
        "Data_Entrega": delivered,
        "Numero_Emissao": emissao,
        "Companhia_Emissora": name,
    }


def party_row(cnpj_emissora, certificate, reference, tipo, cnpj, share, *, version=1):
    return {
        "CNPJ_Emissora": cnpj_emissora,
        "Codigo_Identificacao_Certificado": certificate,
        "Data_Referencia": reference,
        "Versao": str(version),
        "Tipo": tipo,
        "CNPJ": cnpj,
        "Percentual": share,
    }


def write_cvm_zip(path, kind, year, *, classe=(), geral=(), parties=()) -> Path:
    """ZIP no layout da CVM: tres CSV latin-1 separados por ';' com o cabecalho real."""

    tables = {
        f"inf_mensal_{kind}_classe_{year}.csv": (CLASSE_HEADER, classe),
        f"inf_mensal_{kind}_geral_{year}.csv": (GERAL_HEADER, geral),
        f"inf_mensal_{kind}_cedente_devedor_{year}.csv": (PARTY_HEADER, parties),
    }

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for name, (header, rows) in tables.items():
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=header, delimiter=";", lineterminator="\r\n")
            writer.writeheader()
            writer.writerows(rows)
            target.writestr(name, buffer.getvalue().encode("latin-1"))

    return Path(path)


def almeida_rows(year: int):
    classe, geral, parties = [], [], []

    for reference, delivered in ALMEIDA_DELIVERED.items():
        if not reference.startswith(str(year)):
            continue

        classe.append(classe_row(OPEA, ALMEIDA_ISIN, reference, cetip=ALMEIDA_CETIP, isin=ALMEIDA_ISIN))
        geral.append(geral_row(
            OPEA, ALMEIDA_ISIN, reference, delivered=delivered, emissao="301",
            name="Opea Securtizadora",
        ))

        for tipo in ("Cedente", "Devedor"):
            parties.append(party_row(OPEA, ALMEIDA_ISIN, reference, tipo, "0", PLACEHOLDER_SHARE))

            if reference >= ALMEIDA_PARTIES_FROM:
                parties.append(
                    party_row(OPEA, ALMEIDA_ISIN, reference, tipo, ALMEIDA_DEVEDOR, FULL_SHARE)
                )

    return classe, geral, parties


def eco_rows(year: int = 2026):
    classe, geral, parties = [], [], []

    for reference, delivered in ECO_DELIVERED.items():
        classe.append(classe_row(ECO, ECO_ISIN, reference, cetip=ECO_CETIP, isin=ECO_ISIN))
        geral.append(geral_row(
            ECO, ECO_ISIN, reference, delivered=delivered, emissao="190",
            name="Eco Securitizdora de Direitos Creditórios do Agronegócio",
        ))
        parties.append(party_row(ECO, ECO_ISIN, reference, "Cedente", CAFE_CEDENTE_IN_CVM, FULL_SHARE))
        parties.append(party_row(ECO, ECO_ISIN, reference, "Devedor", CAFE_DEVEDOR_IN_CVM, FULL_SHARE))

    return classe, geral, parties


def write_almeida_zips(directory) -> list[Path]:
    """inf_mensal_cri_2025.zip e inf_mensal_cri_2026.zip com os informes do Almeida Junior."""

    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []

    for year in (2025, 2026):
        classe, geral, parties = almeida_rows(year)
        paths.append(write_cvm_zip(
            folder / f"inf_mensal_cri_{year}.zip", "cri", year,
            classe=classe, geral=geral, parties=parties,
        ))

    return paths


def write_eco_zip(directory) -> Path:
    """inf_mensal_cra_2026.zip com os informes do Eco/Cafe Brasil."""

    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    classe, geral, parties = eco_rows()
    return write_cvm_zip(
        folder / "inf_mensal_cra_2026.zip", "cra", 2026,
        classe=classe, geral=geral, parties=parties,
    )
