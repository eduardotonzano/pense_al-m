from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from credit_assets.collectors.cvm_informe_mensal import CvmArchive, CvmFiling, CvmParty
from credit_assets.services import cnpj_resolution
from credit_assets.services.cnpj_resolution import (
    DEVEDOR,
    RESOLVED,
    SECURITIZADORA,
    decide,
    match_filings,
    resolve_devedor,
    resolve_securitizadora,
)
from tests.cvm_fixtures import (
    ALMEIDA_CETIP,
    ALMEIDA_DEVEDOR,
    ALMEIDA_ISIN,
    ECO,
    OPEA,
)

CRI_2025 = CvmArchive(Path("inf_mensal_cri_2025.zip"), "a" * 64, "cri", 2025)
CRI_2026 = CvmArchive(Path("inf_mensal_cri_2026.zip"), "b" * 64, "cri", 2026)
IDENTITY = dict(isin=ALMEIDA_ISIN, codigo_cetip=ALMEIDA_CETIP, emissao="301", serie="1")


def filing(
    reference: str,
    *,
    cnpj: str = OPEA,
    isin: str = ALMEIDA_ISIN,
    cetip: str = ALMEIDA_CETIP,
    emissao: str = "301",
    serie: str = "1",
    parties: tuple = (),
    delivered: str | None = None,
    version: int = 1,
    archive: CvmArchive = CRI_2026,
) -> CvmFiling:
    return CvmFiling(
        archive=archive,
        cnpj_emissora=cnpj,
        certificate=ALMEIDA_ISIN,
        reference_date=reference,
        version=version,
        isin=isin,
        codigo_cetip=cetip,
        numero_serie=serie,
        numero_emissao=emissao,
        delivered_at=delivered,
        parties=tuple(parties),
    )


def debtor(cnpj: str, share: str = "1") -> CvmParty:
    return CvmParty("devedor", cnpj, Decimal(share))


def months(first: int, last: int, **kwargs) -> list[CvmFiling]:
    return [filing(f"2026-{month:02d}-01", **kwargs) for month in range(first, last + 1)]


# ---------------------------------------------------------------- ligacao

def test_match_links_by_isin_or_by_cetip_and_ignores_unrelated_informes():
    by_isin = filing("2026-01-01", cetip="")
    by_cetip = filing("2026-02-01", isin="")
    unrelated = filing("2026-03-01", isin="BRZZZZZZZZ19", cetip="ZZZ9999999")

    match = match_filings([by_isin, by_cetip, unrelated], **IDENTITY)

    assert match.related == (by_isin, by_cetip)
    assert match.accepted == (by_isin, by_cetip)
    assert match.rejected == ()


def test_match_normalizes_the_asset_identifiers():
    match = match_filings(
        [filing("2026-01-01")],
        isin=" brrbracrip13 ", codigo_cetip=" 24g2100031​", emissao="301", serie="1",
    )

    assert len(match.accepted) == 1


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"isin": "BRZZZZZZZZ19"}, "ISIN BRZZZZZZZZ19"),
        ({"cetip": "ZZZ9999999"}, "CETIP ZZZ9999999"),
        ({"emissao": "302"}, "emissao 302"),
        ({"serie": "2"}, "serie 2"),
    ],
)
def test_match_rejects_an_informe_whose_identity_disagrees_with_the_asset(overrides, expected):
    # O informe cita o ISIN ou o CETIP do ativo (o outro identificador, a
    # emissao e a serie seguem iguais) mas discorda em um ponto.
    disagreeing = filing("2026-01-01", **overrides)

    match = match_filings([disagreeing], **IDENTITY)

    assert match.accepted == ()
    assert len(match.rejected) == 1 and expected in match.rejected[0][1]


@pytest.mark.parametrize(
    ("emissao", "serie"),
    [("", ""), ("0", "0"), ("301", "Única"), ("301ª", "1ª")],
)
def test_match_does_not_compare_issue_and_series_that_are_blank_zero_or_not_numeric(emissao, serie):
    informe = filing("2026-01-01", emissao=emissao, serie=serie)

    assert len(match_filings([informe], **IDENTITY).accepted) == 1


def test_the_matcher_only_receives_identifiers_never_a_name():
    parameters = set(inspect.signature(match_filings).parameters)

    assert parameters == {"filings", "isin", "codigo_cetip", "emissao", "serie"}
    assert not any(
        word in name for name in parameters for word in ("nome", "name", "securitizadora", "devedor")
    )
    for resolver in (resolve_securitizadora, resolve_devedor):
        assert set(inspect.signature(resolver).parameters) == {"match"}


def test_the_model_of_a_cvm_informe_has_no_name_field():
    fields = set(CvmFiling.__dataclass_fields__) | set(CvmParty.__dataclass_fields__)

    assert not any("nome" in name or "name" in name for name in fields)
    assert "Companhia_Emissora" not in inspect.getsource(cnpj_resolution)


# ----------------------------------------------------------- securitizadora

def test_securitizadora_is_resolved_with_period_delivery_and_files():
    informes = [
        filing("2025-11-01", archive=CRI_2025, delivered="2025-12-26"),
        filing("2025-12-01", archive=CRI_2025, delivered="2026-01-26"),
        *months(1, 8, delivered="2026-09-28"),
    ]

    result = resolve_securitizadora(match_filings(informes, **IDENTITY))

    assert result.status == RESOLVED
    assert result.cnpj == "02773542000122"
    assert result.source_id == "cvm_inf_mensal_cri"
    assert (result.reference_first, result.reference_last, result.filings) == (
        "2025-11-01", "2026-08-01", 10,
    )
    assert result.delivered_last == "2026-09-28"
    assert result.matched_by == "isin+codigo_cetip"
    assert [item["name"] for item in result.evidence["files"]] == [
        "inf_mensal_cri_2025.zip", "inf_mensal_cri_2026.zip",
    ]
    assert result.evidence["files"][0]["reference_dates"] == ["2025-11-01", "2025-12-01"]
    assert result.evidence["files"][1]["sha256"] == "b" * 64


def test_securitizadora_records_how_the_asset_was_linked():
    by_isin = resolve_securitizadora(match_filings(months(1, 2, cetip=""), **IDENTITY))
    by_cetip = resolve_securitizadora(match_filings(months(1, 2, isin=""), **IDENTITY))

    assert (by_isin.matched_by, by_cetip.matched_by) == ("isin", "codigo_cetip")


def test_securitizadora_with_two_different_cnpj_is_a_conflict_and_stays_absent():
    informes = [*months(1, 3, cnpj="12.130.744/0001-00"), *months(4, 8)]

    result = resolve_securitizadora(match_filings(informes, **IDENTITY))

    assert result.status == "conflito" and result.cnpj is None
    assert "02.773.542/0001-22 em 2026-04-01 a 2026-08-01" in result.detail
    assert "12.130.744/0001-00 em 2026-01-01 a 2026-03-01" in result.detail


def test_securitizadora_with_one_invalid_cnpj_among_valid_ones_stays_absent():
    informes = [*months(1, 7), filing("2026-08-01", cnpj="02.773.542/0001-23")]

    result = resolve_securitizadora(match_filings(informes, **IDENTITY))

    assert (result.status, result.cnpj) == ("cnpj_invalido_na_fonte", None)
    assert "02.773.542/0001-23" in result.detail


def test_securitizadora_without_informe_or_with_a_disagreeing_one_stays_absent():
    nothing = resolve_securitizadora(match_filings([], **IDENTITY))
    disagreeing = resolve_securitizadora(
        match_filings([*months(1, 3), filing("2026-04-01", cetip="ZZZ9999999")], **IDENTITY)
    )

    assert nothing.status == "sem_fonte"
    assert disagreeing.status == "identificadores_discordantes"
    assert "CETIP ZZZ9999999" in disagreeing.detail


def test_a_later_version_of_the_same_informe_replaces_the_earlier_one():
    informes = [
        filing("2026-05-01", version=1, archive=CRI_2025, delivered="2026-06-01"),
        filing("2026-05-01", version=2, archive=CRI_2026, delivered="2026-06-20"),
        *months(6, 8),
    ]

    result = resolve_securitizadora(match_filings(informes, **IDENTITY))

    assert (result.status, result.cnpj, result.filings) == (RESOLVED, "02773542000122", 4)
    assert result.delivered_last == "2026-06-20"
    assert [item["name"] for item in result.evidence["files"]] == ["inf_mensal_cri_2026.zip"]


def test_the_same_month_with_two_different_emissoras_is_not_a_correction_but_a_conflict():
    informes = [filing("2026-05-01", cnpj=ECO, version=1), filing("2026-05-01", cnpj=OPEA, version=2)]

    result = resolve_securitizadora(match_filings(informes, **IDENTITY))

    assert (result.status, result.cnpj) == ("conflito", None)


# ------------------------------------------------------------------ devedor

ALMEIDA_PARTIES = (debtor("0", "0"), debtor(ALMEIDA_DEVEDOR))
PLACEHOLDERS = (debtor("0", "0"),)


def test_devedor_is_resolved_from_the_months_that_actually_list_it():
    informes = [
        *months(1, 6, parties=PLACEHOLDERS),
        *months(7, 8, parties=ALMEIDA_PARTIES, delivered="2026-09-28"),
    ]

    result = resolve_devedor(match_filings(informes, **IDENTITY))

    assert result.status == RESOLVED and result.cnpj == "82120676000183"
    assert (result.reference_first, result.reference_last, result.filings) == (
        "2026-07-01", "2026-08-01", 2,
    )
    assert result.delivered_last == "2026-09-28"
    assert result.evidence["files"][0]["reference_dates"] == ["2026-07-01", "2026-08-01"]


def test_devedor_with_only_the_zero_marker_stays_absent():
    result = resolve_devedor(match_filings(months(1, 8, parties=PLACEHOLDERS), **IDENTITY))

    assert (result.status, result.cnpj) == ("sem_devedor_informado", None)


def test_devedor_ignores_cedente_rows():
    cedente_only = (CvmParty("cedente", ALMEIDA_DEVEDOR, Decimal("1")),)

    result = resolve_devedor(match_filings(months(7, 8, parties=cedente_only), **IDENTITY))

    assert result.status == "sem_devedor_informado"


@pytest.mark.parametrize("garbage", ["011.615.038-62", ",", "00000072068981", "02.773.542/0001-23", "ABC"])
def test_devedor_that_is_not_a_valid_cnpj_is_never_resolved(garbage):
    result = resolve_devedor(match_filings(months(7, 8, parties=(debtor(garbage),)), **IDENTITY))

    assert (result.status, result.cnpj) == ("cnpj_invalido_na_fonte", None)
    assert garbage in result.detail


def test_devedor_with_two_different_cnpj_stays_absent():
    informes = [*months(1, 3, parties=(debtor(ECO),)), *months(4, 8, parties=(debtor(ALMEIDA_DEVEDOR),))]

    result = resolve_devedor(match_filings(informes, **IDENTITY))

    assert (result.status, result.cnpj) == ("varios_devedores", None)
    assert ECO in result.detail and ALMEIDA_DEVEDOR in result.detail


@pytest.mark.parametrize(
    "parties",
    [
        (debtor(ALMEIDA_DEVEDOR, "0.6"),),
        (debtor(ALMEIDA_DEVEDOR, "0.6"), debtor("011.615.038-62", "0.4")),
        (debtor(ALMEIDA_DEVEDOR), debtor("011.615.038-62", "0.1")),
    ],
)
def test_devedor_that_is_not_the_whole_debt_in_the_latest_informe_stays_absent(parties):
    result = resolve_devedor(match_filings(months(7, 8, parties=parties), **IDENTITY))

    assert (result.status, result.cnpj) == ("devedor_parcial", None)


def test_devedor_missing_from_the_latest_informe_stays_absent():
    informes = [*months(7, 8, parties=ALMEIDA_PARTIES), filing("2026-09-01", parties=PLACEHOLDERS)]

    result = resolve_devedor(match_filings(informes, **IDENTITY))

    assert result.status == "sem_devedor_informado"
    assert "2026-09-01" in result.detail


def test_devedor_without_informe_or_with_a_disagreeing_one_stays_absent():
    assert resolve_devedor(match_filings([], **IDENTITY)).status == "sem_fonte"
    assert resolve_devedor(
        match_filings([filing("2026-01-01", serie="9", parties=ALMEIDA_PARTIES)], **IDENTITY)
    ).status == "identificadores_discordantes"


# ------------------------------------------------------------------ decisao

def resolution(cnpj: str = "02773542000122"):
    informes = months(1, 2, cnpj=OPEA if cnpj == "02773542000122" else cnpj)
    return resolve_securitizadora(match_filings(informes, **IDENTITY))


@pytest.mark.parametrize(
    ("stored", "apply_allowed", "expected"),
    [
        ("", True, "applied"),
        ("   ", True, "applied"),
        ("", False, "candidate"),
        ("02.773.542/0001-22", True, "confirmed"),
        ("02773542000122", False, "confirmed"),
        (" 02.773.542/0001-22 ", True, "confirmed"),
        ("10.753.164/0001-43", True, "conflict"),
        ("10.753.164/0001-43", False, "conflict"),
        ("n/d", True, "conflict"),
    ],
)
def test_decide_never_overwrites_a_value_that_is_already_there(stored, apply_allowed, expected):
    assert decide(resolution(), stored, apply_allowed=apply_allowed) == expected


def test_decide_has_nothing_to_say_when_the_cvm_gave_no_single_valid_cnpj():
    absent = resolve_securitizadora(match_filings([], **IDENTITY))

    assert decide(absent, "", apply_allowed=True) is None
    assert decide(absent, "10.753.164/0001-43", apply_allowed=True) is None
    assert SECURITIZADORA != DEVEDOR
