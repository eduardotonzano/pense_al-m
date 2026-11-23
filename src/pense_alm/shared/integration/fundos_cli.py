"""Entrada operacional da importacao do cadastro de Fundos (FU7.2, ADR-009).

python -m pense_alm.shared.integration.fundos_cli --fundos-db ... --target-db ...

Le o cadastro e o CDA do banco de Fundos numa sessao so (read_all) e roda
as duas travas e as fases 1 a 4 (fundos_cadastro_import). Sem dados de CDA
(sem a migration 004 ou sem coleta), a fase 4 so informa o motivo.

Por padrao e uma simulacao: o destino e copiado para uma pasta temporaria
local, o mesmo codigo roda sobre a copia e a copia e removida no fim. Gravar
exige --commit e --backup-dir; o backup e feito antes de qualquer gravacao.
Destino novo exige tambem --create. O --commit recusa destino em caminho de
rede (UNC, ou unidade mapeada remota no Windows) antes de tocar nele.

Saida so com contagens e tipos: nunca CNPJ, nome, caminho nem mensagem de
excecao. Uma transacao por escrita: uma falha no meio do --commit deixa o
que ja foi gravado, e a saida pede para rodar de novo ou restaurar o backup.

Codigos de saida, com precedencia 2 > 3 > 4 > 0:
- 2: erro, erro contado (em qualquer das 4 fases), retrato ausente ou mais
  antigo que o aplicado, CDA mais antigo que o aplicado ou ausente com CDA
  ja aplicado, formato de data inesperado no destino, destino de rede no
  --commit, falha no backup ou execucao parcial;
- 3: id_ocupado ou cnpj_colisao maior que 0;
- 4: leitura incompleta do cadastro (nenhuma relacao do cadastro e fechada)
  ou do CDA (o detentor com competencia incompleta nao tem fechamento);
- 0: tudo certo.
"""

import argparse
import ntpath
import os
import sys
import tempfile
from dataclasses import fields
from pathlib import Path

from pense_alm.shared.entities import RelationshipType
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
    create_sqlite_backup,
)

from .fundos_cadastro_import import (
    CdaOlderThanApplied,
    CdaUnavailableButApplied,
    FundosCadastroImport,
    SnapshotOlderThanApplied,
)
from .fundos_investment_report import HOLDER_COUNTERS, PAIR_COUNTERS
from .fundos_reader import FundosDatabaseReader
from .fundos_relation_report import TYPE_COUNTERS, TYPE_FIELDS
from .fundos_target_state import FundosTargetState, FundosTargetStateError


NETWORK_MESSAGE = "Erro: destino em caminho de rede; use um banco em disco local."
RUNNING_MESSAGE = "Executando as fases 1 a 4; pode levar alguns minutos"
PARTIAL_MESSAGE = "execucao parcial: rode de novo ou restaure o backup"
DRIVE_REMOTE = 4
_ABORTS = (
    SnapshotOlderThanApplied,
    CdaOlderThanApplied,
    CdaUnavailableButApplied,
    FundosTargetStateError,
)


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da entrada operacional."""

    parser = argparse.ArgumentParser(
        description=(
            "Importa o cadastro de Fundos (fundos, classes, prestadoras e "
            "relacoes) e as relacoes investe em do CDA para a Shared Entity "
            "Layer. Sem --commit apenas simula, em uma copia descartavel do "
            "destino."
        )
    )
    parser.add_argument(
        "--fundos-db",
        required=True,
        type=Path,
        help="Banco SQLite do modulo de Fundos (aberto so para leitura).",
    )
    parser.add_argument(
        "--target-db",
        required=True,
        type=Path,
        help="Banco SQLite de destino da camada.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula sobre uma copia descartavel do destino (padrao).",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava no banco de destino.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Pasta do backup. Obrigatoria com --commit.",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Cria o banco de destino se ele nao existir (so com --commit).",
    )
    return parser


def _on_windows() -> bool:
    return sys.platform == "win32"


def _drive_type(drive: str) -> int | None:
    """GetDriveTypeW da unidade, so no Windows; None se nao der para saber."""

    if not _on_windows():
        return None

    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetDriveTypeW(drive + "\\"))
    except Exception:
        return None


def _is_network_path(path) -> bool:
    """Caminho de rede: UNC, ou unidade mapeada remota no Windows.

    So olha o texto do caminho (completado com a pasta atual quando relativo)
    e, no Windows, o tipo da unidade. Nunca chama resolve, is_file nem exists
    sobre o caminho.
    """

    text = os.fspath(path)

    if text.startswith(("\\\\", "//")):
        return True

    absolute = str(Path(text).absolute())

    if absolute.startswith(("\\\\", "//")):
        return True

    if not _on_windows():
        return False

    drive = ntpath.splitdrive(text)[0] or ntpath.splitdrive(absolute)[0]

    if len(drive) == 2 and drive[1] == ":":
        return _drive_type(drive) == DRIVE_REMOTE

    return False


def _parts(instance) -> str:
    return "; ".join(
        f"{item.name.replace('_', ' ')} {getattr(instance, item.name)}"
        for item in fields(instance)
    )


def _print_snapshot(snapshot) -> None:
    if snapshot.complete:
        completa = "sim"
    else:
        completa = (
            f"nao (motivo: {snapshot.incomplete_reason.value}); "
            "nenhuma relacao do cadastro e fechada"
        )

    print(
        f"Retrato: competencia {snapshot.reference_date.isoformat()}; "
        f"leitura completa: {completa}"
    )


def _label(name: str) -> str:
    return name.replace("_", " ")


def _print_investments(report) -> None:
    """Bloco da fase 4; sem dados de CDA, uma linha so."""

    if not report.cda_disponivel:
        print(
            "Investe em (CDA): sem dados de CDA "
            f"(motivo: {report.motivo_sem_cda.value})"
        )
        return

    latest = report.competencia_mais_nova_completa

    if report.leitura_completa:
        completa = "sim"
    else:
        completa = (
            f"nao (motivo: {report.motivo_incompleto.value}); o detentor com "
            "competencia incompleta nao tem fechamento"
        )

    print(
        "Investe em (CDA): competencia mais nova completa "
        f"{latest.isoformat() if latest is not None else 'nenhuma'}; "
        f"leitura completa: {completa}"
    )
    print(
        "  detentores: "
        + "; ".join(
            f"{_label(name.removeprefix('detentores_'))} {getattr(report, name)}"
            for name in HOLDER_COUNTERS
        )
    )

    for name in PAIR_COUNTERS:
        print(f"  {_label(name)}: {getattr(report, name)}")

    print(f"  nao criadas: {report.nao_criadas.total} ({_parts(report.nao_criadas)})")
    print(
        "  fora do normal: detentores com relacao "
        f"{report.detentores_fora_do_normal_com_relacao}; relacoes intactas "
        f"{report.relacoes_de_detentor_fora_do_normal_intactas}"
    )
    print(
        "  pares com investido fora do normal (informativo): "
        f"{report.pares_com_investido_fora_do_normal}"
    )
    print(
        "  relacoes de detentor ausente do cda (informativo): "
        f"{report.relacoes_de_detentor_ausente_do_cda}"
    )
    print(
        f"  atraso (informativo): detentores {report.detentores_atrasados}; "
        f"relacoes {report.relacoes_de_detentor_atrasado}"
    )

    for item in report.atraso:
        meses = "1 mes" if item.meses == 1 else f"{item.meses} meses"
        print(f"    {meses}: detentores {item.detentores}; relacoes {item.relacoes}")


def _print_run(run) -> None:
    entities = run.entities
    relations = run.relations
    types = [getattr(relations, name) for name in TYPE_FIELDS.values()]

    print("Entidades")
    print(f"  cnpjs lidos: {entities.cnpjs_lidos}")
    print(f"  em funcionamento normal: {entities.em_funcionamento_normal}")
    print(f"  backlog: {_parts(entities.backlog)}")
    print(f"  fora do normal ja na camada: {entities.fora_do_normal_ja_na_camada}")
    print(
        "  fundos com gestora pessoa fisica (todas as situacoes): "
        f"{entities.gestor_pessoa_fisica}"
    )
    print(
        f"  fundos: criados {entities.fundos_criados}; reutilizados "
        f"{entities.fundos_reutilizados}; nao criados "
        f"{entities.fundos_nao_criados.total} ({_parts(entities.fundos_nao_criados)})"
    )
    print(
        f"  prestadoras: candidatas {entities.prestadoras_candidatas}; ligadas "
        f"{entities.prestadoras_ligadas}; so de fundo nao resolvido "
        f"{entities.prestadoras_so_de_fundo_nao_resolvido}; criadas "
        f"{entities.prestadoras_criadas}; reutilizadas "
        f"{entities.prestadoras_reutilizadas}; nao criadas "
        f"{entities.prestadoras_nao_criadas.total} "
        f"({_parts(entities.prestadoras_nao_criadas)})"
    )
    print("Relacoes (" + " | ".join(TYPE_FIELDS.values()) + ")")

    for name in TYPE_COUNTERS:
        values = " | ".join(str(getattr(counts, name)) for counts in types)
        print(f"  {name.replace('_', ' ')}: {values}")

    for name in ("prestadora_sem_entidade", "autorrelacao"):
        values = " | ".join(str(getattr(counts.nao_criadas, name)) for counts in types)
        print(f"  nao criadas, {name.replace('_', ' ')}: {values}")

    print(f"  pares de fundo nao resolvido: {relations.pares_de_fundo_nao_resolvido}")
    print(
        "  fora do normal: fundos com relacao "
        f"{relations.fundos_fora_do_normal_com_relacao}; relacoes intactas "
        f"{relations.relacoes_de_fundo_fora_do_normal_intactas}"
    )
    print(
        "  ausentes do retrato (informativo): "
        f"{relations.relacoes_de_fundo_ausente_do_retrato}"
    )
    _print_investments(run.investments)
    print(f"Erros: {run.erros_total}")

    for erro in entities.erros:
        print(f"  {erro.fase} {erro.tipo}: {erro.quantidade}")

    for erro in relations.erros:
        print(
            f"  relacoes {erro.tipo_relacao.value} {erro.operacao.value} "
            f"{erro.tipo}: {erro.quantidade}"
        )

    for erro in run.investments.erros:
        print(f"  investe em {erro.operacao.value} {erro.tipo}: {erro.quantidade}")


def _exit_code(run) -> int:
    """2 > 3 > 4 > 0: erro contado, id ocupado ou colisao, leitura incompleta.

    A leitura incompleta e a do cadastro ou a do CDA (C6).
    """

    if run.erros_total > 0:
        return 2

    if run.id_ocupado > 0 or run.cnpj_colisao > 0:
        return 3

    if not run.leitura_completa:
        return 4

    return 0


def _import_into(snapshot, cda, database_path, commit: bool, has_backup: bool) -> int:
    try:
        manager = SQLiteConnectionManager(database_path)
        entities = SQLiteEntityRepository(manager)
        relationships = SQLiteRelationshipRepository(manager)
        custodied_before = relationships.count(RelationshipType.CUSTODIED_BY)
        invests_before = relationships.count(RelationshipType.INVESTS_IN)
    except Exception as error:
        print(f"Erro: {type(error).__name__}; nenhum dado foi gravado.")
        return 2

    print(RUNNING_MESSAGE)

    try:
        run = FundosCadastroImport(
            entities,
            relationships,
            FundosTargetState(manager),
        ).run(snapshot, cda)
    except _ABORTS as error:
        message = f"Erro: {type(error).__name__}; nenhum dado foi gravado"

        if commit and has_backup:
            message += "; o backup feito antes continua na pasta de --backup-dir"

        print(message + ".")
        return 2
    except Exception as error:
        print(f"Erro: {type(error).__name__}")
        print(PARTIAL_MESSAGE if commit else "a simulacao falhou; o destino nao foi alterado")
        return 2

    _print_run(run)
    first = "primeira gravacao" if commit else "seria a primeira gravacao"

    for name, before, created in (
        ("custodied_by", custodied_before, run.relations.custodied_by.criadas),
        ("invests_in", invests_before, run.investments.criadas),
    ):
        if before == 0 and created > 0:
            print(
                f"Aviso: {first} de {name} neste banco; quem ler este banco "
                "precisa da main a partir de 0fb907f (#49)."
            )

    if run.erros_total > 0:
        print(
            PARTIAL_MESSAGE
            if commit
            else "a simulacao teve erros; o destino nao foi alterado"
        )

    code = _exit_code(run)
    print(f"Resultado: codigo {code}")
    return code


def _dry_run(snapshot, cda, target: Path) -> int:
    with tempfile.TemporaryDirectory(
        prefix="fundos_import_",
        ignore_cleanup_errors=True,
    ) as temp_dir:
        if target.is_file():
            try:
                working = create_sqlite_backup(target, temp_dir).path
            except Exception as error:
                print(
                    f"Erro: falha ao copiar o destino ({type(error).__name__}); "
                    "nada foi gravado."
                )
                return 2
        else:
            print("Aviso: destino inexistente; simulacao sobre um banco vazio.")
            working = Path(temp_dir) / "vazio.sqlite3"

        code = _import_into(snapshot, cda, working, commit=False, has_backup=False)

    print("Nada foi gravado no destino; a copia descartavel foi removida.")
    return code


def _commit(snapshot, cda, target: Path, backup_dir: Path, create: bool) -> int:
    if target.is_file():
        try:
            backup = create_sqlite_backup(target, backup_dir)
        except Exception as error:
            print(f"Erro: falha no backup ({type(error).__name__}); nada foi gravado.")
            return 2

        print(f"Backup: {backup.path.name}")
        print(f"  tamanho: {backup.size_bytes} bytes")
        print(f"  sha256: {backup.sha256}")
        print("  o backup esta na pasta de --backup-dir")
        return _import_into(snapshot, cda, target, commit=True, has_backup=True)

    if not create:
        print("Erro: banco de destino inexistente; use --create para criar um novo.")
        return 2

    print("Banco de destino novo: nao ha o que copiar no backup.")
    return _import_into(snapshot, cda, target, commit=True, has_backup=False)


def run_fundos_import(
    fundos_db: Path,
    target_db: Path,
    commit: bool = False,
    backup_dir: Path | None = None,
    create: bool = False,
) -> int:
    """Executa a importacao com caminhos explicitos."""

    if commit and backup_dir is None:
        raise ValueError("--commit exige --backup-dir.")

    if not commit and (create or backup_dir is not None):
        raise ValueError("--create e --backup-dir so valem com --commit.")

    if commit and _is_network_path(target_db):
        print(NETWORK_MESSAGE)
        return 2

    if commit:
        print("Modo: commit")
    else:
        print("Modo: dry-run (simulacao em copia descartavel; o destino nao e alterado)")

    try:
        snapshot, cda = FundosDatabaseReader(fundos_db).read_all()
    except Exception as error:
        print(f"Erro: {type(error).__name__}; nada foi gravado.")
        return 2

    _print_snapshot(snapshot)

    if not commit:
        return _dry_run(snapshot, cda, Path(target_db))

    return _commit(snapshot, cda, Path(target_db), Path(backup_dir), create)


def main(argv: list[str] | None = None) -> int:
    """Processa argumentos e executa a importacao."""

    parser = build_parser()
    arguments = parser.parse_args(argv)

    # Primeira validacao sobre o destino: antes de qualquer resolve, is_file
    # ou exists dele.
    if arguments.commit and _is_network_path(arguments.target_db):
        print(NETWORK_MESSAGE)
        return 2

    if arguments.commit and arguments.backup_dir is None:
        parser.error("--commit exige --backup-dir.")

    if not arguments.commit and arguments.backup_dir is not None:
        parser.error("--backup-dir so pode ser usado com --commit.")

    if not arguments.commit and arguments.create:
        parser.error("--create so pode ser usado com --commit.")

    if not arguments.fundos_db.is_file():
        parser.error("--fundos-db deve apontar para um arquivo existente.")

    if arguments.fundos_db.resolve() == arguments.target_db.resolve():
        parser.error("--fundos-db e --target-db devem ser diferentes.")

    if (
        arguments.commit
        and not arguments.create
        and not arguments.target_db.is_file()
    ):
        parser.error("--target-db nao existe; use --create para criar um novo.")

    try:
        return run_fundos_import(
            fundos_db=arguments.fundos_db,
            target_db=arguments.target_db,
            commit=arguments.commit,
            backup_dir=arguments.backup_dir,
            create=arguments.create,
        )
    except Exception as error:
        print(f"Erro: {type(error).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
