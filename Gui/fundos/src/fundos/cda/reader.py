"""Leitura do CDA da CVM (cda_fi_AAAAMM.zip), sem banco.

O ZIP e lido inteiro em memoria; nada e extraido em disco. Uma primeira
passada confere tudo antes de qualquer gravacao: os 12 membros (e so eles)
com o mesmo AAAAMM e o nome do ZIP coerente; no cda_fie e no
cda_fie_CONFID, cp1252 estrito, o cabecalho exato (columns.py), a largura
das linhas e o formato de cada valor usado. Os 10 membros cda_fi_* so
entram no manifesto (tamanho e SHA-256), sem ser decodificados.

So as linhas de TP_APLIC "Cotas de Fundos" sao normalizadas; as demais so
sao contadas por TP_APLIC, sem guardar nada. A competencia e o DT_COMPTC
dessas linhas, nos dois arquivos: um so valor, do mes do AAAAMM e nao
posterior a hoje (UTC). Depois, holdings() e confidential_holdings()
entregam as posicoes, lendo de novo os bytes guardados.

Detentor: CNPJ_FUNDO_CLASSE com normalize_cnpj, sem completar zeros; fora
disso a linha nao vira posicao e e contada.

Dados pessoais (decisao 3 de Fundos; guardas aprovadas na FU6.1):
- guarda (a): CPF_CNPJ_EMISSOR so vale como CNPJ do investido se
  PF_PJ_EMISSOR for PJ, se tiver 14 caracteres ou a mascara completa (sem
  completar zeros) e se o DV de CNPJ fechar. Fora disso a linha nao vira
  posicao e e contada como identificador recusado, por motivo. O CPF
  completado com zeros ate 14 caracteres numa linha PF e recusado mesmo que
  o DV de CNPJ feche por acaso;
- guarda (b): EMISSOR so entra com identificador aceito; nunca de linha PF
  nem de linha com identificador recusado.

QT_POS_FINAL e VL_MERC_POS_FINAL em decimal exato (canonical_decimal); fora
do formato, a leitura aborta. Sem VL_MERC_POS_FINAL, a linha e contada e nao
vira posicao. Nenhum objeto mostra CNPJ, nome ou valor no repr, e as
mensagens citam arquivo, linha e coluna, nunca o valor.
"""

import hashlib
import io
import re
import zipfile
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import MappingProxyType

from fundos.cda import columns as spec
from fundos.cnpj import InvalidCnpjError
from fundos.cnpj import normalize_cnpj
from fundos.cvm_csv import MAX_MEMBER_BYTES
from fundos.cvm_csv import MAX_ZIP_BYTES
from fundos.cvm_csv import CvmFormatError
from fundos.cvm_csv import MemberManifest
from fundos.cvm_csv import decode
from fundos.cvm_csv import iter_csv
from fundos.cvm_csv import location
from fundos.cvm_csv import member_manifest
from fundos.database import normalize_iso_date
from fundos.repositories.observation_repository import canonical_decimal


CdaFormatError = CvmFormatError

MEMBER = re.compile(r"(.+)_([0-9]{6})\.csv")
ZIP_NAME = re.compile(r"cda_fi_([0-9]{6})\.zip")

# Forma do identificador antes do DV: 14 caracteres ou a mascara completa.
_PLAIN = re.compile(r"[0-9A-Z]{12}[0-9]{2}")
_MASKED = re.compile(r"([0-9A-Z]{2})\.([0-9A-Z]{3})\.([0-9A-Z]{3})/([0-9A-Z]{4})-([0-9]{2})")

# Motivos da guarda (a), na ordem em que sao conferidos.
REFUSED_PF = "PF"
REFUSED_EMPTY = "vazio"
REFUSED_PERSON_TYPE = "PF_PJ_EMISSOR fora de PJ"
REFUSED_FORMAT = "formato"
REFUSED_DV = "DV"
REFUSAL_REASONS = (REFUSED_PF, REFUSED_EMPTY, REFUSED_PERSON_TYPE, REFUSED_FORMAT, REFUSED_DV)

IDENTIFIED = "identificadas"
CONFIDENTIAL = "confidenciais"


@dataclass(frozen=True)
class CdaZipManifest:
    """Manifesto do ZIP: nome, tamanho, SHA-256, datas dos membros e AAAAMM."""

    file_name: str
    size_bytes: int
    sha256: str
    member_dates: tuple[str, ...]
    period: str


@dataclass(frozen=True)
class CdaHolding:
    """Posicao identificada em cotas de fundos (uma linha do cda_fie).

    holder_type e o TP_FUNDO_CLASSE como veio; holder_cnpj e o
    CNPJ_FUNDO_CLASSE sem mascara. investee_name so existe com o CNPJ do
    investido aceito. CNPJ, nome e valores nunca aparecem no repr.
    """

    line: int
    holder_type: str
    holder_cnpj: str = field(repr=False)
    competence: str
    investee_cnpj: str = field(repr=False)
    investee_name: str | None = field(repr=False)
    quantity: str | None = field(repr=False)
    market_value: str = field(repr=False)


@dataclass(frozen=True)
class CdaConfidentialHolding:
    """Consolidado confidencial de cotas de fundos (uma linha do cda_fie_CONFID).

    Sem investido e sem quantidade; confidential_until e o DT_CONFID_APLIC.
    CNPJ e valor nunca aparecem no repr.
    """

    line: int
    holder_type: str
    holder_cnpj: str = field(repr=False)
    competence: str
    market_value: str = field(repr=False)
    confidential_until: str


@dataclass(frozen=True)
class CdaFile:
    """O ZIP lido e conferido: manifestos, competencia e contagens.

    members tem os 12 CSV; os 10 cda_fi_* vem sem line_count e sem
    column_count (nao sao decodificados). Os bytes do cda_fie e do
    cda_fie_CONFID ficam em contents, fora do repr.
    """

    zip: CdaZipManifest
    members: tuple[MemberManifest, ...]
    competence: str
    counts: Counter
    contents: MappingProxyType = field(repr=False, compare=False)

    def member(self, table):
        """Manifesto do CSV da tabela."""

        name = spec.member_name(table, self.zip.period)

        for member in self.members:
            if member.file_name == name:
                return member

        raise KeyError(name)

    def holdings(self):
        """Posicoes identificadas em cotas de fundos, na ordem do arquivo."""

        return _positions(self, spec.FIE)

    def confidential_holdings(self):
        """Consolidados confidenciais de cotas de fundos, na ordem do arquivo."""

        return _positions(self, spec.FIE_CONFID)


def _format_error(member, line, column, kind):
    return CdaFormatError(
        location(member, line, column) + ": valor fora do formato " + kind + "."
    )


def _date(member, line, record, column):
    try:
        return normalize_iso_date(record[column], "A data")
    except ValueError as error:
        raise _format_error(member, line, column, "date") from error


def _decimal(member, line, record, column):
    """Decimal exato em texto, ou None se vazio; fora do formato, aborta."""

    if not record[column].strip():
        return None

    try:
        return canonical_decimal(record[column])
    except ValueError as error:
        raise _format_error(member, line, column, "numeric") from error


def _holder(record):
    """CNPJ_FUNDO_CLASSE sem mascara, sem completar zeros; None se invalido."""

    try:
        return normalize_cnpj(record[spec.HOLDER_COLUMN])
    except InvalidCnpjError:
        return None


def check_investee(person_type, identifier):
    """Guarda (a): (CNPJ do investido, None) ou (None, motivo da recusa)."""

    if person_type.strip() == spec.NATURAL_PERSON:
        return None, REFUSED_PF

    if not identifier.strip():
        return None, REFUSED_EMPTY

    if person_type.strip() != spec.LEGAL_PERSON:
        return None, REFUSED_PERSON_TYPE

    candidate = identifier.strip().upper()

    if not candidate.isascii():
        return None, REFUSED_FORMAT

    masked = _MASKED.fullmatch(candidate)

    if masked is not None:
        candidate = "".join(masked.groups())

    if _PLAIN.fullmatch(candidate) is None:
        return None, REFUSED_FORMAT

    try:
        return normalize_cnpj(identifier), None
    except InvalidCnpjError:
        return None, REFUSED_DV


def parse_holding(member, line, record, counts=None):
    """Normaliza uma linha de cotas do cda_fie: (competencia, posicao ou None)."""

    holder_type = record[spec.HOLDER_TYPE_COLUMN].strip()
    competence = _date(member, line, record, spec.COMPETENCE_COLUMN)
    quantity = _decimal(member, line, record, spec.QUANTITY_COLUMN)
    market_value = _decimal(member, line, record, spec.VALUE_COLUMN)
    holder = _holder(record)
    investee, reason = check_investee(
        record[spec.PERSON_TYPE_COLUMN], record[spec.INVESTEE_COLUMN]
    )
    name = record[spec.INVESTEE_NAME_COLUMN]
    name = name if name.strip() else None

    if counts is not None:
        counts[(IDENTIFIED, "linhas")] += 1
        counts[(IDENTIFIED, "tipo_detentor", holder_type)] += 1

        if reason is None:
            counts[(IDENTIFIED, "identificador_aceito")] += 1
        else:
            counts[(IDENTIFIED, "identificador_recusado", reason)] += 1

            if name is not None:
                counts[(IDENTIFIED, "emissor_descartado")] += 1

        if holder is None:
            counts[(IDENTIFIED, "detentor_invalido")] += 1

    if reason is not None or holder is None:
        return competence, None

    if market_value is None:
        if counts is not None:
            counts[(IDENTIFIED, "sem_valor_de_mercado")] += 1

        return competence, None

    return competence, CdaHolding(
        line=line,
        holder_type=holder_type,
        holder_cnpj=holder,
        competence=competence,
        investee_cnpj=investee,
        investee_name=name,
        quantity=quantity,
        market_value=market_value,
    )


def parse_confidential(member, line, record, counts=None):
    """Normaliza uma linha de cotas do cda_fie_CONFID: (competencia, posicao ou None)."""

    holder_type = record[spec.HOLDER_TYPE_COLUMN].strip()
    competence = _date(member, line, record, spec.COMPETENCE_COLUMN)
    market_value = _decimal(member, line, record, spec.VALUE_COLUMN)
    until = None

    if record[spec.CONFIDENTIAL_UNTIL_COLUMN].strip():
        until = _date(member, line, record, spec.CONFIDENTIAL_UNTIL_COLUMN)

    holder = _holder(record)

    if counts is not None:
        counts[(CONFIDENTIAL, "linhas")] += 1
        counts[(CONFIDENTIAL, "tipo_detentor", holder_type)] += 1

        if holder is None:
            counts[(CONFIDENTIAL, "detentor_invalido")] += 1

        if until is None:
            counts[(CONFIDENTIAL, "sem_data_confidencial")] += 1
        else:
            counts[(CONFIDENTIAL, "mes_confidencial", until[:7])] += 1

    if holder is None or until is None:
        return competence, None

    if market_value is None:
        if counts is not None:
            counts[(CONFIDENTIAL, "sem_valor_de_mercado")] += 1

        return competence, None

    return competence, CdaConfidentialHolding(
        line=line,
        holder_type=holder_type,
        holder_cnpj=holder,
        competence=competence,
        market_value=market_value,
        confidential_until=until,
    )


PARSERS = {spec.FIE: parse_holding, spec.FIE_CONFID: parse_confidential}


def _rows(table, period, data, counts=None):
    """Para cada linha de dados: None (outro TP_APLIC) ou (competencia, posicao ou None).

    Com counts, conta toda linha por TP_APLIC.
    """

    member = spec.member_name(table, period)
    header = spec.HEADERS[table]

    for line, fields in iter_csv(member, decode(member, data), header):
        record = dict(zip(header, fields))
        application = record[spec.APPLICATION_COLUMN].strip()

        if counts is not None:
            counts[("tp_aplic", table, application)] += 1

        if application != spec.FUND_QUOTAS:
            yield None
            continue

        yield PARSERS[table](member, line, record, counts)


def _positions(cda, table):
    for parsed in _rows(table, cda.zip.period, cda.contents[table]):
        if parsed is not None and parsed[1] is not None:
            yield parsed[1]


def _check_members(archive, file_name, max_member_bytes):
    """Exatamente os 12 membros, com o mesmo AAAAMM; devolve (AAAAMM, infos)."""

    found = defaultdict(list)
    unexpected = 0

    for info in archive.infolist():
        match = MEMBER.fullmatch(info.filename)

        if match is None or match.group(1) not in spec.TABLES:
            unexpected += 1
            continue

        found[match.group(1)].append((match.group(2), info))

    missing = [table for table in spec.TABLES if table not in found]
    repeated = [table for table, entries in found.items() if len(entries) > 1]
    periods = sorted({period for entries in found.values() for period, _ in entries})
    problems = []

    if missing:
        problems.append("faltam " + ", ".join(missing))

    if unexpected:
        problems.append(str(unexpected) + " membro(s) inesperado(s)")

    if repeated:
        problems.append("tabela repetida: " + ", ".join(repeated))

    if len(periods) > 1:
        problems.append("AAAAMM diferente entre os membros (" + ", ".join(periods) + ")")

    if problems:
        raise CdaFormatError(
            "O ZIP nao tem exatamente os 12 arquivos do CDA ("
            + "; ".join(problems)
            + "). Nada foi lido."
        )

    period = periods[0]
    zip_match = ZIP_NAME.fullmatch(file_name)

    if zip_match is not None and zip_match.group(1) != period:
        raise CdaFormatError(
            "O nome do ZIP ("
            + zip_match.group(1)
            + ") nao bate com o AAAAMM dos membros ("
            + period
            + "). Nada foi lido."
        )

    infos = {table: entries[0][1] for table, entries in found.items()}

    for info in infos.values():
        if info.file_size > max_member_bytes:
            raise CdaFormatError(
                info.filename
                + " passa do limite de "
                + str(max_member_bytes)
                + " bytes descomprimidos."
            )

    return period, infos


def _check_competence(competences, period):
    """Um so DT_COMPTC nas linhas de cotas, do mes do AAAAMM, nao posterior a hoje (UTC)."""

    if len(competences) != 1:
        raise CdaFormatError(
            "DT_COMPTC das linhas de cotas com "
            + str(len(competences))
            + " valores diferentes ("
            + ", ".join(sorted(competences))
            + "); o CDA deve ter uma so competencia. Nada foi lido."
        )

    competence = next(iter(competences))

    if competence[:4] + competence[5:7] != period:
        raise CdaFormatError(
            "DT_COMPTC "
            + competence
            + " nao e do mes do AAAAMM dos membros ("
            + period
            + "). Nada foi lido."
        )

    today = datetime.now(timezone.utc).date().isoformat()

    if competence > today:
        raise CdaFormatError(
            "DT_COMPTC " + competence + " e posterior a hoje (" + today + ", UTC)."
        )

    return competence


def _count_positions(counts, holdings, confidential):
    """Detentores, investidos, chaves repetidas e sobreposicao das duas listas."""

    keys = defaultdict(list)

    for holding in holdings:
        keys[(holding.holder_cnpj, holding.investee_cnpj, holding.competence)].append(
            (holding.quantity, holding.market_value)
        )

    repeated = {key: values for key, values in keys.items() if len(values) > 1}
    holders = {holding.holder_cnpj for holding in holdings}
    confidential_holders = Counter(position.holder_cnpj for position in confidential)

    counts[(IDENTIFIED, "posicoes")] = len(holdings)
    counts[(IDENTIFIED, "sem_quantidade")] = sum(1 for h in holdings if h.quantity is None)
    counts[(IDENTIFIED, "sem_emissor")] = sum(1 for h in holdings if h.investee_name is None)
    counts[(IDENTIFIED, "detentores")] = len(holders)
    counts[(IDENTIFIED, "investidos")] = len({holding.investee_cnpj for holding in holdings})
    counts[(IDENTIFIED, "chave_repetida", "linhas")] = sum(len(v) for v in repeated.values())
    counts[(IDENTIFIED, "chave_repetida", "chaves")] = len(repeated)
    counts[(IDENTIFIED, "chave_repetida", "valores_diferentes")] = sum(
        1 for values in repeated.values() if len(set(values)) > 1
    )
    counts[(CONFIDENTIAL, "posicoes")] = len(confidential)
    counts[(CONFIDENTIAL, "detentores")] = len(confidential_holders)
    counts[(CONFIDENTIAL, "detentor_repetido")] = sum(
        1 for total in confidential_holders.values() if total > 1
    )
    counts[("detentores_nas_duas",)] = len(holders & set(confidential_holders))


def read_cda_bytes(data, file_name, *, max_member_bytes=MAX_MEMBER_BYTES):
    """Le e confere o ZIP ja carregado em memoria; devolve CdaFile."""

    zip_hash = hashlib.sha256(data).hexdigest()

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise CdaFormatError(file_name + " nao e um ZIP valido.") from error

    counts = Counter()
    manifests = {}
    contents = {}
    competences = set()
    positions = {spec.FIE: [], spec.FIE_CONFID: []}

    with archive:
        period, infos = _check_members(archive, file_name, max_member_bytes)
        member_dates = tuple(
            sorted({"%04d-%02d-%02d" % info.date_time[:3] for info in infos.values()})
        )

        for table in spec.TABLES:
            member = spec.member_name(table, period)
            raw = archive.read(infos[table])

            if len(raw) > max_member_bytes:
                raise CdaFormatError(
                    member + " passa do limite de " + str(max_member_bytes) + " bytes descomprimidos."
                )

            if table in spec.IGNORED_TABLES:
                manifests[table] = member_manifest(member, raw, None, None)
                continue

            line_count = 0

            for parsed in _rows(table, period, raw, counts):
                line_count += 1

                if parsed is None:
                    continue

                competence, position = parsed
                competences.add(competence)

                if position is not None:
                    positions[table].append(position)

            manifests[table] = member_manifest(member, raw, line_count, len(spec.HEADERS[table]))
            contents[table] = raw

    competence = _check_competence(competences, period)
    _count_positions(counts, positions[spec.FIE], positions[spec.FIE_CONFID])

    return CdaFile(
        zip=CdaZipManifest(
            file_name=file_name,
            size_bytes=len(data),
            sha256=zip_hash,
            member_dates=member_dates,
            period=period,
        ),
        members=tuple(manifests[table] for table in spec.TABLES),
        competence=competence,
        counts=counts,
        contents=MappingProxyType(contents),
    )


def read_cda_zip(path, *, max_member_bytes=MAX_MEMBER_BYTES):
    """Le e confere o cda_fi_AAAAMM.zip do disco, sem extrair nada."""

    zip_path = Path(path)

    if not zip_path.is_file():
        raise FileNotFoundError("ZIP nao encontrado: " + str(zip_path))

    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise CdaFormatError(
            zip_path.name + " passa do limite de " + str(MAX_ZIP_BYTES) + " bytes."
        )

    return read_cda_bytes(
        zip_path.read_bytes(),
        zip_path.name,
        max_member_bytes=max_member_bytes,
    )
