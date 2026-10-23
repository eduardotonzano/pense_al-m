"""Resolve o CNPJ da securitizadora e do devedor pelo Informe Mensal da CVM (S-08).

O ativo so e ligado ao informe por ISIN e CETIP (``match_filings``): o nome da
securitizadora ou do devedor nunca participa, nem como chave nem como veto.
Quando a CVM nao traz um valor unico e valido, o campo continua ausente e o
relatorio diz o motivo. O CNPJ so e gravado em ``assets`` quando o campo esta
vazio; o que ja esta la nunca e sobrescrito. Cada decisao fica em
``asset_cnpj_observations`` com fonte, periodo e data da leitura.
"""

from __future__ import annotations

import re
import sqlite3
import time
import uuid
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from credit_assets.collectors.cvm_informe_mensal import (
    CvmArchive,
    CvmDataError,
    CvmFiling,
    normalize_cetip,
    normalize_isin,
    open_archive,
    read_filings,
)
from credit_assets.database.backup import create_backup
from credit_assets.database.connection import connect
from credit_assets.database.migrations import APPLY_COMMAND
from credit_assets.repositories.cnpj_observation_repository import (
    CNPJ_FIELDS,
    CnpjObservation,
    CnpjObservationRepository,
)
from credit_assets.services.category_reclassification import open_read_only, table_exists
from credit_assets.utils.validators import (
    format_cnpj,
    normalize_cnpj,
    only_digits,
)

SECURITIZADORA = "cnpj_securitizadora"
DEVEDOR = "cnpj_devedor"
RESOLVED = "resolvido"

REASONS = {
    "sem_arquivo_da_cvm": "nenhum arquivo da CVM deste tipo de ativo foi lido",
    "sem_identificador": "o ativo nao tem ISIN nem CETIP validos",
    "sem_fonte": "nenhum informe da CVM cita o ISIN ou o CETIP do ativo",
    "identificadores_discordantes": (
        "informe da CVM com ISIN, CETIP, emissao ou serie diferente do ativo"
    ),
    "conflito": "a CVM traz mais de uma securitizadora para o ativo",
    "cnpj_invalido_na_fonte": "o CNPJ informado pela CVM nao passa no digito verificador",
    "sem_devedor_informado": "a CVM nao traz devedor com CNPJ (so o marcador 0)",
    "varios_devedores": "a CVM traz mais de um devedor",
    "devedor_parcial": "o devedor da CVM nao e 100% no informe mais recente",
}
_FULL_SHARE = Decimal("0.9999")
# Como a CVM marca "sem CNPJ": vazio, "0" ou so zeros (com ou sem mascara).
_MARKER = re.compile(r"[0.\-/\s]*")


class ResolutionError(Exception):
    """Nao foi possivel gerar a previa ou gravar os CNPJ."""


@dataclass(frozen=True)
class AssetRef:
    asset_id: int
    tipo_ativo: str
    codigo_cetip: str
    isin: str
    emissao: str
    serie: str
    stored: dict


@dataclass(frozen=True)
class Match:
    """Informes da CVM que citam o ativo e o que as travas de identidade disseram."""

    isin: str
    codigo_cetip: str
    related: tuple[CvmFiling, ...]
    accepted: tuple[CvmFiling, ...]
    rejected: tuple[tuple[CvmFiling, str], ...]


@dataclass(frozen=True)
class FieldResolution:
    field: str
    status: str
    cnpj: str | None = None
    source_id: str | None = None
    reference_first: str | None = None
    reference_last: str | None = None
    filings: int = 0
    delivered_last: str | None = None
    matched_by: str | None = None
    evidence: dict | None = None
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "cnpj": self.cnpj,
            "source_id": self.source_id,
            "reference_first": self.reference_first,
            "reference_last": self.reference_last,
            "filings": self.filings,
            "delivered_last": self.delivered_last,
            "matched_by": self.matched_by,
            "evidence": self.evidence,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Decision:
    kind: str
    observation: CnpjObservation
    stored: str
    formatted: str
    already_recorded: bool

    @property
    def writes_asset(self) -> bool:
        return self.kind == "applied"

    @property
    def inserts_observation(self) -> bool:
        return not self.already_recorded


def _numbers_differ(asset_value: str, cvm_value: str) -> bool:
    """Emissao ou serie: so diferem se os dois lados tem numero (nao zero) e ele e outro."""

    left, right = only_digits(asset_value), only_digits(cvm_value)
    return bool(left and right and int(left) and int(right) and int(left) != int(right))


def match_filings(
    filings: Sequence[CvmFiling],
    *,
    isin: str,
    codigo_cetip: str,
    emissao: str,
    serie: str,
) -> Match:
    """Liga os informes ao ativo so por ISIN e CETIP, com travas de emissao e serie.

    Um informe e relacionado se o ISIN ou o CETIP forem iguais. Ele so e aceito
    se nenhum identificador presente nos dois lados for diferente e se emissao
    e serie, quando numericas nos dois lados, forem iguais. Os demais ficam em
    ``rejected`` com o motivo.
    """

    isin = normalize_isin(isin)
    codigo_cetip = normalize_cetip(codigo_cetip)
    related, accepted, rejected = [], [], []

    for filing in filings:
        same_isin = bool(isin and filing.isin == isin)
        same_cetip = bool(codigo_cetip and filing.codigo_cetip == codigo_cetip)

        if not (same_isin or same_cetip):
            continue

        related.append(filing)
        reason = None

        if isin and filing.isin and filing.isin != isin:
            reason = f"ISIN {filing.isin} no informe de {filing.reference_date}"
        elif codigo_cetip and filing.codigo_cetip and filing.codigo_cetip != codigo_cetip:
            reason = f"CETIP {filing.codigo_cetip} no informe de {filing.reference_date}"
        elif _numbers_differ(emissao, filing.numero_emissao):
            reason = f"emissao {filing.numero_emissao} no informe de {filing.reference_date}"
        elif _numbers_differ(serie, filing.numero_serie):
            reason = f"serie {filing.numero_serie} no informe de {filing.reference_date}"

        if reason is None:
            accepted.append(filing)
        else:
            rejected.append((filing, reason))

    return Match(isin, codigo_cetip, tuple(related), tuple(accepted), tuple(rejected))


def _informes(filings: Sequence[CvmFiling]) -> list[CvmFiling]:
    """Um registro por informe (certificado e mes): o de maior versao, em ordem de data."""

    chosen: dict[tuple, CvmFiling] = {}

    for filing in filings:
        current = chosen.get(filing.informe_key)

        if current is None or (filing.version, filing.archive.year) > (
            current.version,
            current.archive.year,
        ):
            chosen[filing.informe_key] = filing

    return sorted(chosen.values(), key=lambda item: (item.reference_date, item.certificate))


def _matched_by(match: Match, informes: Sequence[CvmFiling]) -> str:
    by_isin = any(match.isin and item.isin == match.isin for item in informes)
    by_cetip = any(match.codigo_cetip and item.codigo_cetip == match.codigo_cetip for item in informes)

    if by_isin and by_cetip:
        return "isin+codigo_cetip"

    return "isin" if by_isin else "codigo_cetip"


def _evidence(informes: Sequence[CvmFiling]) -> dict:
    files: dict[str, dict] = {}

    for informe in informes:
        archive = informe.archive
        entry = files.setdefault(
            archive.sha256,
            {
                "name": archive.official_name,
                "url": archive.url,
                "sha256": archive.sha256,
                "reference_dates": [],
            },
        )

        if informe.reference_date not in entry["reference_dates"]:
            entry["reference_dates"].append(informe.reference_date)

    ordered = sorted(files.values(), key=lambda item: item["name"])

    for entry in ordered:
        entry["reference_dates"].sort()

    return {"files": ordered}


def _absent(field: str, status: str, detail: str = "") -> FieldResolution:
    return FieldResolution(field=field, status=status, detail=detail)


def _span(items: Sequence[CvmFiling]) -> str:
    return f"{items[0].reference_date} a {items[-1].reference_date}"


def _resolved(
    field: str,
    cnpj: str,
    informes: Sequence[CvmFiling],
    match: Match,
    detail: str = "",
) -> FieldResolution:
    informes = sorted(informes, key=lambda item: item.reference_date)
    delivered = [item.delivered_at for item in informes if item.delivered_at]
    return FieldResolution(
        field=field,
        status=RESOLVED,
        cnpj=cnpj,
        source_id=informes[0].archive.source_id,
        reference_first=informes[0].reference_date,
        reference_last=informes[-1].reference_date,
        filings=len(informes),
        delivered_last=max(delivered) if delivered else None,
        matched_by=_matched_by(match, informes),
        evidence=_evidence(informes),
        detail=detail,
    )


def _blocked(field: str, match: Match) -> FieldResolution | None:
    if not match.related:
        return _absent(field, "sem_fonte")

    if match.rejected:
        reasons = "; ".join(sorted({reason for _, reason in match.rejected}))
        return _absent(field, "identificadores_discordantes", reasons)

    return None


def resolve_securitizadora(match: Match) -> FieldResolution:
    """CNPJ_Emissora unico e valido em todos os informes que citam o ativo."""

    blocked = _blocked(SECURITIZADORA, match)

    if blocked is not None:
        return blocked

    by_cnpj = defaultdict(list)

    for informe in _informes(match.accepted):
        by_cnpj[normalize_cnpj(informe.cnpj_emissora)].append(informe)

    if None in by_cnpj:
        invalid = sorted({item.cnpj_emissora for item in by_cnpj[None]})
        return _absent(
            SECURITIZADORA, "cnpj_invalido_na_fonte", f"CNPJ_Emissora: {', '.join(invalid)}"
        )

    if len(by_cnpj) > 1:
        parts = [
            f"{format_cnpj(cnpj)} em {_span(items)}" for cnpj, items in sorted(by_cnpj.items())
        ]
        return _absent(SECURITIZADORA, "conflito", "; ".join(parts))

    ((cnpj, items),) = by_cnpj.items()
    return _resolved(SECURITIZADORA, cnpj, items, match)


def _real_debtors(informe: CvmFiling) -> tuple[list[tuple[str, Decimal]], list[str]]:
    """Devedores com parcela no informe: (CNPJ validos com a parcela, valores que nao sao CNPJ).

    O marcador "0" e a parcela zero ou ausente nao contam como devedor.
    """

    valid, invalid = [], []

    for party in informe.parties:
        if party.kind != "devedor" or _MARKER.fullmatch(party.cnpj):
            continue

        if party.percentual is None or party.percentual <= 0:
            continue

        cnpj = normalize_cnpj(party.cnpj)

        if cnpj is None:
            invalid.append(party.cnpj)
        else:
            valid.append((cnpj, party.percentual))

    return valid, invalid


def resolve_devedor(match: Match) -> FieldResolution:
    """Um unico devedor, com CNPJ valido e 100% no informe mais recente."""

    blocked = _blocked(DEVEDOR, match)

    if blocked is not None:
        return blocked

    informes = _informes(match.accepted)
    by_cnpj: dict[str, dict[tuple, CvmFiling]] = defaultdict(dict)
    invalid_seen = set()

    for informe in informes:
        valid, invalid = _real_debtors(informe)
        invalid_seen.update(invalid)

        for cnpj, _ in valid:
            by_cnpj[cnpj][informe.informe_key] = informe

    if not by_cnpj:
        if invalid_seen:
            return _absent(
                DEVEDOR, "cnpj_invalido_na_fonte", f"valores: {', '.join(sorted(invalid_seen))}"
            )

        return _absent(DEVEDOR, "sem_devedor_informado")

    ordered = {
        cnpj: sorted(items.values(), key=lambda item: item.reference_date)
        for cnpj, items in by_cnpj.items()
    }

    if len(ordered) > 1:
        parts = [f"{format_cnpj(cnpj)} em {_span(items)}" for cnpj, items in sorted(ordered.items())]
        return _absent(DEVEDOR, "varios_devedores", "; ".join(parts))

    ((cnpj, items),) = ordered.items()
    latest = informes[-1]
    latest_valid, latest_invalid = _real_debtors(latest)

    if not latest_valid and not latest_invalid:
        return _absent(
            DEVEDOR,
            "sem_devedor_informado",
            f"o informe de {latest.reference_date} nao traz devedor, embora "
            f"informes anteriores tragam {format_cnpj(cnpj)}",
        )

    shares = dict(latest_valid)

    if latest_invalid or set(shares) != {cnpj} or shares[cnpj] < _FULL_SHARE:
        others = f", valores que nao sao CNPJ: {', '.join(latest_invalid)}" if latest_invalid else ""
        return _absent(
            DEVEDOR,
            "devedor_parcial",
            f"informe de {latest.reference_date}: parcela {shares.get(cnpj)}{others}",
        )

    return _resolved(DEVEDOR, cnpj, items, match, "100% no informe mais recente")


def _stored_text(value) -> str:
    return (value or "").strip()


def decide(resolution: FieldResolution, stored: str, *, apply_allowed: bool) -> str | None:
    """applied, confirmed, candidate ou conflict; None se nao ha CNPJ resolvido."""

    if resolution.status != RESOLVED:
        return None

    if not _stored_text(stored):
        return "applied" if apply_allowed else "candidate"

    return "confirmed" if normalize_cnpj(stored) == resolution.cnpj else "conflict"


def load_archives(cvm_dir: str | Path) -> tuple[list[CvmArchive], list[tuple[str, str]]]:
    """Os ZIPs da pasta que sao Informe Mensal de CRI/CRA, e os que foram ignorados."""

    folder = Path(cvm_dir)

    if not folder.is_dir():
        raise ResolutionError(
            f"Pasta dos dados da CVM nao encontrada: {folder}. Copie para ela os ZIPs "
            "inf_mensal_cri_<ano>.zip e inf_mensal_cra_<ano>.zip ou use --download."
        )

    archives, ignored, seen, opened = [], [], {}, []

    for path in sorted(folder.glob("*.zip")):
        try:
            opened.append(open_archive(path))
        except CvmDataError as error:
            ignored.append((path.name, str(error)))

    # O arquivo com o nome oficial vem primeiro: uma copia renomeada e que e ignorada.
    opened.sort(key=lambda item: (item.path.name != item.official_name, item.path.name))

    for archive in opened:
        path = archive.path
        key = (archive.kind, archive.year)

        if key in seen:
            if seen[key].sha256 == archive.sha256:
                ignored.append((path.name, f"copia de {seen[key].path.name}"))
                continue

            raise ResolutionError(
                f"Dois arquivos diferentes para {archive.kind.upper()} {archive.year}: "
                f"{seen[key].path.name} e {path.name}. Deixe so um."
            )

        seen[key] = archive
        archives.append(archive)

    return archives, ignored


def load_assets(connection: sqlite3.Connection, only: str | None = None) -> list[AssetRef]:
    wanted = ""

    if only:
        wanted = normalize_isin(only) or normalize_cetip(only)

        if not wanted:
            raise ResolutionError(f"--only precisa de um ISIN ou CETIP validos: {only!r}")

    assets = []

    for row in connection.execute(
        """SELECT asset_id, tipo_ativo, codigo_cetip, isin, emissao, serie,
                  cnpj_securitizadora, cnpj_devedor
           FROM assets WHERE active = 1 ORDER BY asset_id"""
    ):
        isin, cetip = normalize_isin(row["isin"]), normalize_cetip(row["codigo_cetip"])

        if wanted and wanted not in {isin, cetip}:
            continue

        assets.append(
            AssetRef(
                asset_id=int(row["asset_id"]),
                tipo_ativo=row["tipo_ativo"],
                codigo_cetip=cetip,
                isin=isin,
                emissao=row["emissao"] or "",
                serie=row["serie"] or "",
                stored={
                    SECURITIZADORA: _stored_text(row["cnpj_securitizadora"]),
                    DEVEDOR: _stored_text(row["cnpj_devedor"]),
                },
            )
        )

    return assets


def _observation(asset: AssetRef, resolution: FieldResolution, kind: str) -> CnpjObservation:
    evidence = dict(resolution.evidence or {})

    if kind == "conflict":
        evidence["stored"] = asset.stored[resolution.field]

    return CnpjObservation(
        asset_id=asset.asset_id,
        field=resolution.field,
        cnpj=resolution.cnpj,
        decision=kind,
        source_id=resolution.source_id,
        matched_by=resolution.matched_by,
        reference_first=resolution.reference_first,
        reference_last=resolution.reference_last,
        filings=resolution.filings,
        evidence=evidence,
        delivered_last=resolution.delivered_last,
    )


def _resolutions(asset: AssetRef, filings_by_kind: dict, archived_kinds: set) -> dict:
    kind = asset.tipo_ativo.lower()

    if not (asset.isin or asset.codigo_cetip):
        return {name: _absent(name, "sem_identificador") for name in CNPJ_FIELDS}

    if kind not in archived_kinds:
        return {name: _absent(name, "sem_arquivo_da_cvm") for name in CNPJ_FIELDS}

    match = match_filings(
        filings_by_kind[kind],
        isin=asset.isin,
        codigo_cetip=asset.codigo_cetip,
        emissao=asset.emissao,
        serie=asset.serie,
    )
    return {
        SECURITIZADORA: resolve_securitizadora(match),
        DEVEDOR: resolve_devedor(match),
    }


def build_preview(
    connection: sqlite3.Connection,
    archives: Sequence[CvmArchive],
    ignored: Sequence[tuple[str, str]] = (),
    *,
    database: str = "",
    only: str | None = None,
    apply_devedor: bool = False,
) -> tuple[dict, list[Decision]]:
    """O que o --commit faria, lendo so o banco aberto e os ZIPs da CVM.

    Devolve a previa (serializavel em JSON) e as decisoes que o --commit gravaria.
    """

    assets = load_assets(connection, only)
    has_table = table_exists(connection, "asset_cnpj_observations")
    repository = CnpjObservationRepository(connection) if has_table else None
    archives_by_kind = defaultdict(list)

    for archive in archives:
        archives_by_kind[archive.kind].append(archive)

    filings_by_kind = {}

    for kind, kind_archives in archives_by_kind.items():
        of_kind = [item for item in assets if item.tipo_ativo.lower() == kind]
        isins = [item.isin for item in of_kind]
        cetips = [item.codigo_cetip for item in of_kind]
        filings_by_kind[kind] = [
            filing
            for archive in sorted(kind_archives, key=lambda item: item.year)
            for filing in read_filings(archive, isins, cetips)
        ]

    allowed = {SECURITIZADORA: True, DEVEDOR: apply_devedor}
    result_assets, decisions = [], []
    summary = {"applied": 0, "confirmed": 0, "candidate": 0, "conflict": 0, "absent": {}}

    for asset in assets:
        fields = {}

        for name, resolution in _resolutions(asset, filings_by_kind, set(archives_by_kind)).items():
            kind = decide(resolution, asset.stored[name], apply_allowed=allowed[name])
            entry = {
                "stored": asset.stored[name],
                "resolution": resolution.as_dict(),
                "decision": kind,
                "reason": REASONS.get(resolution.status),
            }

            if kind is None:
                absent = summary["absent"]
                absent[resolution.status] = absent.get(resolution.status, 0) + 1
            else:
                observation = _observation(asset, resolution, kind)
                recorded = repository is not None and connection.execute(
                    "SELECT 1 FROM asset_cnpj_observations WHERE checksum = ?",
                    (observation.checksum(),),
                ).fetchone() is not None
                decisions.append(
                    Decision(kind, observation, asset.stored[name], format_cnpj(resolution.cnpj), recorded)
                )
                summary[kind] += 1
                entry["already_recorded"] = recorded

            fields[name] = entry

        result_assets.append({
            "asset_id": asset.asset_id,
            "tipo_ativo": asset.tipo_ativo,
            "codigo_cetip": asset.codigo_cetip,
            "isin": asset.isin,
            "emissao": asset.emissao,
            "serie": asset.serie,
            "fields": fields,
        })

    preview = {
        "database": database,
        "migration_002": has_table,
        "apply_devedor": apply_devedor,
        "archives": [
            {"kind": item.kind, "year": item.year, "name": item.path.name, "sha256": item.sha256}
            for item in sorted(archives, key=lambda item: (item.kind, item.year))
        ],
        "ignored_files": [{"name": name, "reason": reason} for name, reason in ignored],
        "assets": result_assets,
        "summary": summary,
        "writes": len(pending_writes(decisions)),
    }
    return preview, decisions


def _field_lines(name: str, entry: dict) -> list[str]:
    resolution = entry["resolution"]
    label = "securitizadora" if name == SECURITIZADORA else "devedor"
    current = entry["stored"] or "(vazio)"

    if resolution["status"] != RESOLVED:
        extra = f" ({resolution['detail']})" if resolution["detail"] else ""
        return [
            f"  {label}: atual {current} | CVM sem valor unico: {resolution['status']} - "
            f"{entry['reason']}{extra} | continua ausente"
        ]

    action = {
        "applied": "gravaria no campo",
        "confirmed": "confirma o valor atual",
        "candidate": "registra como candidato; o campo continua vazio",
        "conflict": "CONFLITO com o valor atual; nada e gravado no campo",
    }[entry["decision"]]
    recorded = " (observacao ja registrada)" if entry.get("already_recorded") else ""
    delivered = f", entrega ate {resolution['delivered_last']}" if resolution["delivered_last"] else ""
    return [
        f"  {label}: atual {current} | CVM {format_cnpj(resolution['cnpj'])} | "
        f"{resolution['filings']} informe(s), ref. {resolution['reference_first']} a "
        f"{resolution['reference_last']}{delivered} | ligado por {resolution['matched_by']} "
        f"-> {action}{recorded}"
    ]


def format_preview(preview: dict) -> str:
    summary = preview["summary"]
    lines = [
        f"Banco: {preview['database']} (aberto somente para leitura)",
        "Migration 002 (asset_cnpj_observations): "
        + ("aplicada" if preview["migration_002"] else "PENDENTE: o --commit exige aplica-la"),
        f"Arquivos da CVM lidos: {len(preview['archives'])}",
    ]
    lines += [
        f"  {item['kind'].upper()} {item['year']} {item['name']} sha256={item['sha256']}"
        for item in preview["archives"]
    ]
    lines += [
        f"Arquivo ignorado: {item['name']} ({item['reason']})" for item in preview["ignored_files"]
    ]
    lines.append(
        "Devedor: grava no campo (--apply-devedor)"
        if preview["apply_devedor"]
        else "Devedor: so candidato; o campo nao e preenchido (sem --apply-devedor)"
    )

    for asset in preview["assets"]:
        lines += [
            "",
            f"Ativo {asset['codigo_cetip'] or '-'} / {asset['isin'] or '-'} "
            f"({asset['tipo_ativo']}, emissao {asset['emissao']}, serie {asset['serie']})",
        ]

        for name, entry in asset["fields"].items():
            lines += _field_lines(name, entry)

    absent = ", ".join(
        f"{reason}: {total}" for reason, total in sorted(summary["absent"].items())
    ) or "nenhum"
    lines += [
        "",
        "== Resumo ==",
        f"Gravaria no campo (applied): {summary['applied']}",
        f"Confirma o valor atual (confirmed): {summary['confirmed']}",
        f"Candidatos, campo vazio (candidate): {summary['candidate']}",
        f"Conflitos, nada gravado (conflict): {summary['conflict']}",
        f"Sem valor unico, campo ausente: {absent}",
        f"Gravacoes que o --commit faria: {preview['writes']}",
    ]
    return "\n".join(lines)


def pending_writes(decisions: Sequence[Decision]) -> list[Decision]:
    return [item for item in decisions if item.writes_asset or item.inserts_observation]


def _asset_snapshot(connection: sqlite3.Connection) -> dict[int, dict]:
    return {
        int(row["asset_id"]): dict(row)
        for row in connection.execute("SELECT * FROM assets")
    }


def apply_decisions(
    connection: sqlite3.Connection,
    decisions: Sequence[Decision],
    run_id: str,
    assets_processed: int,
) -> dict:
    """Grava numa transacao e so confirma se a verificacao passar."""

    started = time.perf_counter()
    before = _asset_snapshot(connection)
    observations_before = connection.execute(
        "SELECT COUNT(*) FROM asset_cnpj_observations"
    ).fetchone()[0]
    now = datetime.now(timezone.utc).isoformat()
    repository = CnpjObservationRepository(connection)
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")

    try:
        connection.execute(
            "INSERT INTO executions (run_id, started_at, status) VALUES (?, ?, 'running')",
            (run_id, now),
        )
        written, inserted = {}, 0

        for decision in decisions:
            observation = decision.observation

            if observation.field not in CNPJ_FIELDS:
                raise ResolutionError(f"Campo invalido: {observation.field!r}")

            if decision.writes_asset:
                updated = connection.execute(
                    f"UPDATE assets SET {observation.field} = ?, updated_at = ? "
                    f"WHERE asset_id = ? AND ({observation.field} IS NULL "
                    f"OR TRIM({observation.field}) = '')",
                    (decision.formatted, now, observation.asset_id),
                ).rowcount

                if updated != 1:
                    raise ResolutionError(
                        f"O ativo {observation.asset_id} mudou durante a gravacao "
                        f"({observation.field}); nada foi gravado."
                    )

                written[(observation.asset_id, observation.field)] = decision.formatted

            if repository.add(observation, run_id, now):
                inserted += 1

        problems = []
        after = _asset_snapshot(connection)

        if set(after) != set(before):
            problems.append("o conjunto de ativos mudou")

        for asset_id, old in before.items():
            new = after.get(asset_id, {})

            for column, value in old.items():
                if column != "updated_at" and new.get(column) != written.get((asset_id, column), value):
                    problems.append(f"{column} do ativo {asset_id} diferente do previsto")

        expected_inserted = sum(1 for item in decisions if item.inserts_observation)
        observations_after = connection.execute(
            "SELECT COUNT(*) FROM asset_cnpj_observations"
        ).fetchone()[0]

        if inserted != expected_inserted:
            problems.append("o numero de observacoes novas nao bate com a previa")

        if observations_after - observations_before != inserted:
            problems.append("a contagem de observacoes nao cresceu como previsto")

        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            problems.append("integrity_check falhou")

        if connection.execute("PRAGMA foreign_key_check").fetchall():
            problems.append("foreign_key_check encontrou problemas")

        if problems:
            raise ResolutionError(
                "Verificacao antes do COMMIT falhou: " + "; ".join(sorted(set(problems))) + "."
            )

        connection.execute(
            """UPDATE executions SET finished_at = ?, status = 'success',
               duration_seconds = ?, assets_processed = ?, warning_count = ?
               WHERE run_id = ?""",
            (
                datetime.now(timezone.utc).isoformat(),
                round(time.perf_counter() - started, 4),
                assets_processed,
                sum(1 for item in decisions if item.kind == "conflict"),
                run_id,
            ),
        )
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")

        raise

    return {"fields_written": len(written), "observations_added": inserted}


def commit_resolution(
    database_path: str | Path,
    cvm_dir: str | Path,
    *,
    only: str | None = None,
    apply_devedor: bool = False,
    backup_dir: str | Path | None = None,
) -> dict:
    """Backup, gravacao e verificacao. Sem nada a gravar, nao faz backup."""

    path = Path(database_path)
    archives, ignored = load_archives(cvm_dir)

    with closing(open_read_only(path)) as reader:
        if not table_exists(reader, "asset_cnpj_observations"):
            raise ResolutionError(
                "A tabela asset_cnpj_observations nao existe: aplique a migration 002 "
                f"com {APPLY_COMMAND} antes de gravar."
            )

        preview, decisions = build_preview(
            reader, archives, ignored, database=str(path), only=only,
            apply_devedor=apply_devedor,
        )

    if not pending_writes(decisions):
        return {"preview": preview, "backup": None, "run_id": None}

    try:
        backup = create_backup(path, backup_dir)
    except Exception as error:
        raise ResolutionError(
            f"Nao foi possivel criar o backup; o banco nao foi alterado: {error}"
        ) from error

    run_id = uuid.uuid4().hex
    connection = connect(path)

    try:
        outcome = apply_decisions(connection, decisions, run_id, len(preview["assets"]))
    finally:
        connection.close()

    return {"preview": preview, "backup": backup, "run_id": run_id, **outcome}
