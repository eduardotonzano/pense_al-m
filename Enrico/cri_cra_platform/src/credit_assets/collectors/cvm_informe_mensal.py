"""Leitura do Informe Mensal de CRI e CRA que a CVM publica como dado aberto.

Le os ZIPs anuais que ja estao em disco. So ``download_archive`` acessa a rede,
e so quando chamada. Cada ZIP traz CSV ``inf_mensal_<cri|cra>_<tabela>_<ano>.csv``
em latin-1 com ``;``. Sao usadas tres tabelas (classe, geral, cedente_devedor) e
so as colunas de identificacao: nenhuma coluna de nome e lida.
"""

from __future__ import annotations

import csv
import io
import os
import re
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable, Iterator

from credit_assets.database.backup import file_sha256

DATA_HOST = "dados.cvm.gov.br"
ARCHIVE_URL = (
    "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_{upper}/DADOS/"
    "inf_mensal_{lower}_{year}.zip"
)
SOURCE_IDS = {"cri": "cvm_inf_mensal_cri", "cra": "cvm_inf_mensal_cra"}
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024

_MEMBER = re.compile(
    r"^inf_mensal_(cri|cra)_(classe|geral|cedente_devedor)_(\d{4})\.csv$"
)
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
_CETIP = re.compile(r"[A-Z0-9]{6,15}")
_FIELD_LIMIT = 16 * 1024 * 1024

CLASSE_COLUMNS = (
    "CNPJ_Emissora", "Codigo_Identificacao_Certificado", "Data_Referencia",
    "Versao", "Numero_Serie", "Codigo_CETIP", "Codigo_ISIN",
)
GERAL_COLUMNS = (
    "CNPJ_Emissora", "Codigo_Identificacao_Certificado", "Data_Referencia",
    "Versao", "Data_Entrega", "Numero_Emissao",
)
PARTY_COLUMNS = (
    "CNPJ_Emissora", "Codigo_Identificacao_Certificado", "Data_Referencia",
    "Versao", "Tipo", "CNPJ", "Percentual",
)


class CvmDataError(Exception):
    """O arquivo da CVM nao e o esperado ou nao pode ser lido."""


@dataclass(frozen=True)
class CvmArchive:
    path: Path
    sha256: str
    kind: str
    year: int

    @property
    def source_id(self) -> str:
        return SOURCE_IDS[self.kind]

    @property
    def official_name(self) -> str:
        return f"inf_mensal_{self.kind}_{self.year}.zip"

    @property
    def url(self) -> str:
        return archive_url(self.kind, self.year)


@dataclass(frozen=True)
class CvmParty:
    kind: str
    cnpj: str
    percentual: Decimal | None


@dataclass(frozen=True)
class CvmFiling:
    """Um informe mensal (certificado, mes de referencia e versao) que cita o ativo."""

    archive: CvmArchive
    cnpj_emissora: str
    certificate: str
    reference_date: str
    version: int
    isin: str
    codigo_cetip: str
    numero_serie: str
    numero_emissao: str
    delivered_at: str | None
    parties: tuple[CvmParty, ...]

    @property
    def informe_key(self) -> tuple[str, str, str]:
        return (self.cnpj_emissora, self.certificate, self.reference_date)


def archive_url(kind: str, year: int) -> str:
    if kind not in SOURCE_IDS:
        raise CvmDataError(f"Tipo de ativo sem dado da CVM: {kind!r}")
    return ARCHIVE_URL.format(upper=kind.upper(), lower=kind, year=year)


def _clean(value: str | None) -> str:
    return "".join(
        character
        for character in (value or "")
        if not character.isspace()
        and unicodedata.category(character) not in {"Cf", "Cc"}
    ).upper()


def normalize_isin(value: str | None) -> str:
    """O ISIN sem espacos e em maiusculas, ou "" se nao tem formato de ISIN."""

    text = _clean(value)
    return text if _ISIN.fullmatch(text) else ""


def normalize_cetip(value: str | None) -> str:
    """O CETIP sem espacos e em maiusculas, ou "" se for marcador (ex.: "0")."""

    text = _clean(value)
    return text if _CETIP.fullmatch(text) and set(text) != {"0"} else ""


def _members(source: zipfile.ZipFile) -> tuple[str, int, dict[str, str]]:
    found: dict[str, str] = {}
    identities = set()

    for name in source.namelist():
        match = _MEMBER.match(name)

        if match is not None:
            identities.add((match.group(1), int(match.group(3))))
            found[match.group(2)] = name

    if len(identities) != 1 or "classe" not in found:
        raise CvmDataError(
            "O ZIP nao e um Informe Mensal de CRI ou CRA da CVM "
            "(esperado: inf_mensal_<cri|cra>_classe_<ano>.csv)."
        )

    kind, year = next(iter(identities))
    return kind, year, found


def open_archive(path: str | Path) -> CvmArchive:
    """Identifica o ZIP (CRI ou CRA, ano) pelos nomes internos e calcula o SHA-256."""

    zip_path = Path(path)

    try:
        with zipfile.ZipFile(zip_path) as source:
            kind, year, _ = _members(source)
    except zipfile.BadZipFile as error:
        raise CvmDataError(f"{zip_path.name}: nao e um ZIP valido.") from error

    return CvmArchive(zip_path, file_sha256(zip_path), kind, year)


@contextmanager
def _field_limit():
    previous = csv.field_size_limit(_FIELD_LIMIT)

    try:
        yield
    finally:
        csv.field_size_limit(previous)


def _rows(source: zipfile.ZipFile, member: str, required: Iterable[str]) -> Iterator[dict]:
    with source.open(member) as raw:
        reader = csv.DictReader(
            io.TextIOWrapper(raw, encoding="latin-1", newline=""),
            delimiter=";",
        )
        missing = [name for name in required if name not in (reader.fieldnames or [])]

        if missing:
            raise CvmDataError(f"{member}: coluna(s) ausente(s): {', '.join(missing)}.")

        yield from reader


def _text(row: dict, name: str) -> str:
    return (row.get(name) or "").strip()


def _version(value: str | None) -> int | None:
    try:
        return int((value or "").strip())
    except ValueError:
        return None


def _key(row: dict) -> tuple[str, str, str]:
    return (
        _text(row, "CNPJ_Emissora"),
        _text(row, "Codigo_Identificacao_Certificado"),
        _text(row, "Data_Referencia"),
    )


def _percentual(value: str | None) -> Decimal | None:
    try:
        return Decimal((value or "").strip().replace(",", "."))
    except InvalidOperation:
        return None


def _iso_date(value: str, member: str, what: str) -> str:
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError as error:
        raise CvmDataError(f"{member}: {what} invalida: {value!r}.") from error


def read_filings(
    archive: CvmArchive,
    isins: Iterable[str],
    cetips: Iterable[str],
) -> list[CvmFiling]:
    """Informes do arquivo que citam um dos ISIN ou CETIP, na versao mais recente.

    A ligacao e so por identificador. De cada informe (certificado e mes) fica
    a maior ``Versao``, que e a retificacao mais nova entregue a CVM.
    """

    wanted_isins = {normalize_isin(value) for value in isins} - {""}
    wanted_cetips = {normalize_cetip(value) for value in cetips} - {""}

    if not wanted_isins and not wanted_cetips:
        return []

    with _field_limit(), zipfile.ZipFile(archive.path) as source:
        _, _, members = _members(source)
        latest: dict[tuple[str, str, str], int] = {}
        candidates = []

        for row in _rows(source, members["classe"], CLASSE_COLUMNS):
            key = _key(row)
            version = _version(row["Versao"])
            isin = normalize_isin(row["Codigo_ISIN"])
            cetip = normalize_cetip(row["Codigo_CETIP"])

            if version is not None:
                latest[key] = max(latest.get(key, 0), version)

            if (isin and isin in wanted_isins) or (cetip and cetip in wanted_cetips):
                if version is None:
                    raise CvmDataError(
                        f"{members['classe']}: Versao invalida: {row['Versao']!r}."
                    )

                candidates.append((key, version, isin, cetip, _text(row, "Numero_Serie")))

        chosen = [item for item in candidates if item[1] == latest[item[0]]]
        wanted = {(item[0], item[1]) for item in chosen}
        general: dict[tuple, tuple[str, str | None]] = {}
        parties = defaultdict(list)

        if "geral" in members:
            for row in _rows(source, members["geral"], GERAL_COLUMNS):
                identity = (_key(row), _version(row["Versao"]))

                if identity in wanted:
                    delivered = _text(row, "Data_Entrega")
                    general[identity] = (
                        _text(row, "Numero_Emissao"),
                        _iso_date(delivered, members["geral"], "Data_Entrega") if delivered else None,
                    )

        if "cedente_devedor" in members:
            for row in _rows(source, members["cedente_devedor"], PARTY_COLUMNS):
                identity = (_key(row), _version(row["Versao"]))

                if identity in wanted:
                    kind = _text(row, "Tipo").casefold()
                    parties[identity].append(
                        CvmParty(
                            kind if kind in {"devedor", "cedente"} else "outro",
                            _text(row, "CNPJ"),
                            _percentual(row.get("Percentual")),
                        )
                    )

    filings = []

    for key, version, isin, cetip, serie in chosen:
        emission, delivered = general.get((key, version), ("", None))
        filings.append(
            CvmFiling(
                archive=archive,
                cnpj_emissora=key[0],
                certificate=key[1],
                reference_date=_iso_date(key[2], members["classe"], "Data_Referencia"),
                version=version,
                isin=isin,
                codigo_cetip=cetip,
                numero_serie=serie,
                numero_emissao=emission,
                delivered_at=delivered,
                parties=tuple(parties.get((key, version), ())),
            )
        )

    return filings


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read(MAX_ARCHIVE_BYTES + 1)

    if len(data) > MAX_ARCHIVE_BYTES:
        raise CvmDataError(f"{url}: arquivo maior que o limite de {MAX_ARCHIVE_BYTES} bytes.")

    return data


def download_archive(
    kind: str,
    year: int,
    directory: str | Path,
    *,
    refresh: bool = False,
    fetch: Callable[[str], bytes] = _fetch,
) -> tuple[Path, bool]:
    """Baixa o ZIP oficial do ano para a pasta. Devolve (caminho, baixou).

    So aceita https em dados.cvm.gov.br. Um arquivo que ja existe so e trocado
    com ``refresh``. O ZIP so entra na pasta depois de reconhecido.
    """

    url = archive_url(kind, year)
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme != "https" or parsed.hostname != DATA_HOST:
        raise CvmDataError(f"Endereco fora de https://{DATA_HOST}: {url}")

    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"inf_mensal_{kind}_{year}.zip"

    if target.exists() and not refresh:
        return target, False

    partial = target.with_suffix(".zip.part")
    partial.write_bytes(fetch(url))

    try:
        downloaded = open_archive(partial)
    except CvmDataError:
        partial.unlink(missing_ok=True)
        raise

    if (downloaded.kind, downloaded.year) != (kind, year):
        partial.unlink(missing_ok=True)
        raise CvmDataError(f"{url}: o ZIP baixado e de outro tipo ou ano.")

    os.replace(partial, target)
    return target, True
