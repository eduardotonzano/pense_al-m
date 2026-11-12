from __future__ import annotations

import zipfile
from decimal import Decimal

import pytest

from credit_assets.collectors import cvm_informe_mensal
from credit_assets.collectors.cvm_informe_mensal import (
    CvmDataError,
    archive_url,
    download_archive,
    normalize_cetip,
    normalize_isin,
    open_archive,
    read_filings,
)
from credit_assets.database.backup import file_sha256
from tests.cvm_fixtures import (
    ALMEIDA_CETIP,
    ALMEIDA_DEVEDOR,
    ALMEIDA_ISIN,
    ECO_ISIN,
    OPEA,
    classe_row,
    geral_row,
    party_row,
    write_almeida_zips,
    write_cvm_zip,
    write_eco_zip,
)


def test_open_archive_identifies_dataset_year_url_and_hash_by_the_inner_names(tmp_path):
    cri_2025, cri_2026 = write_almeida_zips(tmp_path)
    renamed = tmp_path / "webfetch-123.zip"
    cri_2026.rename(renamed)

    archive = open_archive(renamed)

    assert (archive.kind, archive.year) == ("cri", 2026)
    assert archive.source_id == "cvm_inf_mensal_cri"
    assert archive.official_name == "inf_mensal_cri_2026.zip"
    assert archive.url == (
        "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_CRI/DADOS/inf_mensal_cri_2026.zip"
    )
    assert archive.sha256 == file_sha256(renamed)
    assert open_archive(write_eco_zip(tmp_path)).source_id == "cvm_inf_mensal_cra"


def test_open_archive_rejects_what_is_not_an_informe_mensal(tmp_path):
    not_a_zip = tmp_path / "x.zip"
    not_a_zip.write_bytes(b"isto nao e um zip")
    other = tmp_path / "other.zip"

    with zipfile.ZipFile(other, "w") as target:
        target.writestr("cad_fi.csv", "CNPJ_FUNDO;DENOM_SOCIAL\n")

    mixed = tmp_path / "mixed.zip"

    with zipfile.ZipFile(mixed, "w") as target:
        target.writestr("inf_mensal_cri_classe_2025.csv", "")
        target.writestr("inf_mensal_cri_geral_2026.csv", "")

    for path in (not_a_zip, other, mixed):
        with pytest.raises(CvmDataError):
            open_archive(path)


def test_archive_url_only_exists_for_cri_and_cra():
    assert archive_url("cra", 2024).endswith("/INF_MENSAL_CRA/DADOS/inf_mensal_cra_2024.zip")

    with pytest.raises(CvmDataError):
        archive_url("debenture", 2024)


def test_read_filings_returns_the_real_almeida_informes_with_their_fields(tmp_path):
    cri_2025, cri_2026 = write_almeida_zips(tmp_path)

    filings = read_filings(open_archive(cri_2026), [ALMEIDA_ISIN], [ALMEIDA_CETIP])

    assert [item.reference_date for item in filings] == [
        f"2026-{month:02d}-01" for month in range(1, 9)
    ]
    last = filings[-1]
    assert (last.cnpj_emissora, last.certificate, last.version) == (OPEA, ALMEIDA_ISIN, 1)
    assert (last.isin, last.codigo_cetip, last.numero_serie) == (ALMEIDA_ISIN, ALMEIDA_CETIP, "1")
    assert (last.numero_emissao, last.delivered_at) == ("301", "2026-09-28")
    devedores = [
        (party.cnpj, party.percentual) for party in last.parties if party.kind == "devedor"
    ]
    assert devedores == [("0", Decimal("0")), (ALMEIDA_DEVEDOR, Decimal("1"))]
    assert [party.kind for party in filings[0].parties] == ["cedente", "devedor"]
    assert len(read_filings(open_archive(cri_2025), [ALMEIDA_ISIN], [])) == 12


def test_read_filings_ignores_other_certificates_and_empty_searches(tmp_path):
    cri_2025, _ = write_almeida_zips(tmp_path)
    archive = open_archive(cri_2025)

    assert read_filings(archive, ["BRXXXXXXXX11"], ["ZZZ9999999"]) == []
    assert read_filings(archive, [], []) == []
    assert read_filings(archive, ["", "00000"], ["0"]) == []


def test_read_filings_matches_by_cetip_alone_when_the_isin_is_blank(tmp_path):
    path = write_cvm_zip(
        tmp_path / "a.zip", "cri", 2026,
        classe=[classe_row(OPEA, "CERT1", "2026-05-01", cetip=ALMEIDA_CETIP, isin="")],
    )

    filings = read_filings(open_archive(path), [], [ALMEIDA_CETIP])

    assert [(item.isin, item.codigo_cetip) for item in filings] == [("", ALMEIDA_CETIP)]
    assert filings[0].numero_emissao == "" and filings[0].delivered_at is None


def test_markers_and_malformed_identifiers_are_not_identifiers(tmp_path):
    assert normalize_isin(" brrbracrip13​ ") == ALMEIDA_ISIN
    assert normalize_isin("00000") == ""
    assert normalize_isin("Opea Securitizadora") == ""
    assert normalize_cetip(" 24g2100031 ") == ALMEIDA_CETIP
    assert normalize_cetip("0") == ""
    assert normalize_cetip("000000") == ""
    assert normalize_cetip("N/A") == ""
    path = write_cvm_zip(
        tmp_path / "a.zip", "cri", 2026,
        classe=[classe_row(OPEA, "CERT1", "2026-05-01", cetip="0", isin="00000")],
    )

    assert read_filings(open_archive(path), ["00000"], ["0"]) == []


def test_read_filings_keeps_only_the_latest_version_of_each_informe(tmp_path):
    path = write_cvm_zip(
        tmp_path / "a.zip", "cri", 2026,
        classe=[
            classe_row(OPEA, ALMEIDA_ISIN, "2026-07-01", version=1, isin=ALMEIDA_ISIN),
            classe_row(OPEA, ALMEIDA_ISIN, "2026-07-01", version=2, isin=ALMEIDA_ISIN),
            classe_row(OPEA, ALMEIDA_ISIN, "2026-08-01", version=1, isin=ALMEIDA_ISIN),
        ],
        parties=[
            party_row(OPEA, ALMEIDA_ISIN, "2026-07-01", "Devedor", "0", "0", version=1),
            party_row(OPEA, ALMEIDA_ISIN, "2026-07-01", "Devedor", ALMEIDA_DEVEDOR, "1.0", version=2),
        ],
    )

    filings = read_filings(open_archive(path), [ALMEIDA_ISIN], [])

    assert [(item.reference_date, item.version) for item in filings] == [
        ("2026-07-01", 2),
        ("2026-08-01", 1),
    ]
    assert [party.cnpj for party in filings[0].parties] == [ALMEIDA_DEVEDOR]


def test_an_older_version_is_dropped_even_if_the_newer_one_lacks_the_series(tmp_path):
    path = write_cvm_zip(
        tmp_path / "a.zip", "cri", 2026,
        classe=[
            classe_row(OPEA, "CERT1", "2026-07-01", version=1, isin=ALMEIDA_ISIN),
            classe_row(OPEA, "CERT1", "2026-07-01", version=2, isin="BRZZZZZZZZ19"),
        ],
    )

    assert read_filings(open_archive(path), [ALMEIDA_ISIN], []) == []


def test_read_filings_reads_names_with_accents_and_ignores_them(tmp_path):
    path = write_cvm_zip(
        tmp_path / "a.zip", "cri", 2026,
        classe=[classe_row(OPEA, ALMEIDA_ISIN, "2026-07-01", isin=ALMEIDA_ISIN)],
        geral=[geral_row(
            OPEA, ALMEIDA_ISIN, "2026-07-01", delivered="2026-08-26", emissao="301",
            name="Securitização de Direitos Creditórios do Agronegócio",
        )],
    )

    filing = read_filings(open_archive(path), [ALMEIDA_ISIN], [])[0]

    assert filing.numero_emissao == "301"
    assert not any("nome" in field.lower() or "name" in field.lower() for field in vars(filing))


def test_read_filings_fails_loudly_on_a_missing_column_or_a_bad_date(tmp_path):
    missing = tmp_path / "missing.zip"

    with zipfile.ZipFile(missing, "w") as target:
        target.writestr("inf_mensal_cri_classe_2026.csv", "CNPJ_Emissora;Codigo_ISIN\n")

    with pytest.raises(CvmDataError, match="coluna"):
        read_filings(open_archive(missing), [ALMEIDA_ISIN], [])

    bad_date = write_cvm_zip(
        tmp_path / "bad.zip", "cri", 2026,
        classe=[classe_row(OPEA, ALMEIDA_ISIN, "agosto/2026", isin=ALMEIDA_ISIN)],
    )

    with pytest.raises(CvmDataError, match="Data_Referencia"):
        read_filings(open_archive(bad_date), [ALMEIDA_ISIN], [])


def test_read_filings_reads_the_cra_dataset_with_unmasked_cnpj(tmp_path):
    archive = open_archive(write_eco_zip(tmp_path))

    filings = read_filings(archive, [ECO_ISIN], [])

    assert len(filings) == 8
    assert {(party.kind, party.cnpj) for party in filings[0].parties} == {
        ("cedente", "23357072000181"),
        ("devedor", "31943818000171"),
    }
    assert filings[0].numero_emissao == "190"


def fake_zip_bytes(tmp_path, kind="cri", year=2026) -> bytes:
    path = write_cvm_zip(tmp_path / "source.zip", kind, year)
    return path.read_bytes()


def test_download_saves_the_official_zip_once_and_refresh_replaces_it(tmp_path):
    calls = []
    payload = fake_zip_bytes(tmp_path)

    def fetch(url):
        calls.append(url)
        return payload

    folder = tmp_path / "cvm"

    first = download_archive("cri", 2026, folder, fetch=fetch)
    second = download_archive("cri", 2026, folder, fetch=fetch)
    third = download_archive("cri", 2026, folder, refresh=True, fetch=fetch)

    assert first == (folder / "inf_mensal_cri_2026.zip", True)
    assert second == (folder / "inf_mensal_cri_2026.zip", False)
    assert third[1] is True
    assert calls == [archive_url("cri", 2026)] * 2
    assert not list(folder.glob("*.part"))


def test_download_refuses_other_hosts_and_zips_that_are_not_the_requested_one(tmp_path, monkeypatch):
    folder = tmp_path / "cvm"

    with pytest.raises(CvmDataError, match="reconhecido|ZIP|Informe"):
        download_archive("cri", 2026, folder, fetch=lambda url: b"<html>erro</html>")

    with pytest.raises(CvmDataError, match="outro tipo ou ano"):
        download_archive("cri", 2026, folder, fetch=lambda url: fake_zip_bytes(tmp_path, "cra", 2026))

    assert not list(folder.glob("*"))

    monkeypatch.setattr(cvm_informe_mensal, "ARCHIVE_URL", "https://example.com/{lower}_{year}_{upper}.zip")

    with pytest.raises(CvmDataError, match="dados.cvm.gov.br"):
        download_archive("cri", 2026, folder, fetch=lambda url: b"")

    monkeypatch.setattr(cvm_informe_mensal, "ARCHIVE_URL", "http://dados.cvm.gov.br/{lower}_{year}_{upper}.zip")

    with pytest.raises(CvmDataError, match="dados.cvm.gov.br"):
        download_archive("cri", 2026, folder, fetch=lambda url: b"")
