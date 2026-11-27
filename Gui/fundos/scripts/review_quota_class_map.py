"""Revisao de uma regra do mapa das series de FIDC (quota_class_map) por uma pessoa.

Uso (a partir da pasta do modulo de Fundos):

    python scripts/review_quota_class_map.py --database <banco> --rule-id 1 --status revisado --reviewer papel:revisor_fundos --note "<nota>" --dry-run
    python scripts/review_quota_class_map.py --database <banco> --rule-id 1 --status revisado --reviewer papel:revisor_fundos --note "<nota>" --commit

Nada vira revisado sem uma pessoa: quem roda o --commit e a pessoa que
revisou, identificada por um papel da lista fechada (papel:dono_da_frente_fundos
ou papel:revisor_fundos), nunca pelo nome. A nota e conferida antes de tudo:
so ASCII imprimivel, ate 200 caracteres, sem quebra de linha, sem sequencia
de 11 digitos ou mais e sem mascara de CPF ou CNPJ. O erro nunca repete o
texto da nota, e a saida mostra so o tamanho dela.

--dry-run confere a regra e a transicao (de proposto para revisado ou
rejeitado, ou de revisado para rejeitado) so lendo o banco, e nao escreve
nada. --commit faz o backup antes, grava a revisao e uma linha no audit_log
numa unica transacao e depois roda integrity_check e foreign_key_check. A
mesma revisao de novo diz "Nada a revisar" e nao faz backup.

O banco e o backup ficam em disco local, de caminho curto (decisao 9 de
Fundos): --database e o destino do backup (--backup-dir ou a pasta backups
ao lado do banco) em caminho de rede (UNC, relativo dentro de pasta de rede
ou unidade remota) ou longo sao recusados antes de abrir o banco, no
--dry-run tambem.
"""

import argparse
import pathlib
import sys


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_DIR / "src"

# O codigo que altera o banco vem sempre deste checkout, nunca de uma copia
# instalada num ambiente virtual.
sys.path.insert(0, str(SOURCE_DIR))

import fundos  # noqa: E402
from fundos.backup import BackupError  # noqa: E402
from fundos.backup import backup_path  # noqa: E402
from fundos.backup import check_local_paths  # noqa: E402
from fundos.backup import check_path_length  # noqa: E402
from fundos.backup import create_backup  # noqa: E402
from fundos.cadastro.loader import missing_migrations  # noqa: E402
from fundos.database import Database  # noqa: E402
from fundos.indicators.reading import IndicatorDatabaseError  # noqa: E402
from fundos.indicators.reading import open_read_only  # noqa: E402
from fundos.quota_classes.mapping import REJECTED  # noqa: E402
from fundos.quota_classes.mapping import REVIEWED  # noqa: E402
from fundos.quota_classes.review import ReviewError  # noqa: E402
from fundos.quota_classes.review import check_note  # noqa: E402
from fundos.quota_classes.review import check_reviewer  # noqa: E402
from fundos.quota_classes.review import plan_review  # noqa: E402
from fundos.quota_classes.review import review_rule  # noqa: E402


REQUIRED_MIGRATIONS = {1: "initial_schema", 6: "quota_class_map"}


class ReviewScriptError(Exception):
    """Erro com mensagem propria, sem caminho, CNPJ, nome, valor nem texto de nota."""


def say(line):
    print(line, flush=True)


def describe(plan, note):
    say("Regra #" + str(plan.rule_id) + ": " + plan.pattern)
    say("  situacao: " + plan.before + " -> " + plan.after)
    say("  nota: " + str(len(note)) + " caractere(s)")


def read_plan(database_path, rule_id, status):
    if not database_path.is_file():
        raise ReviewScriptError("Banco nao encontrado; nada foi criado.")

    connection = open_read_only(database_path)

    try:
        missing = missing_migrations(connection, REQUIRED_MIGRATIONS)

        if missing:
            raise ReviewScriptError("Banco sem as migrations: " + ", ".join(missing) + ".")

        return plan_review(connection, rule_id, status)
    finally:
        connection.close()


def commit(args, database_path, note):
    try:
        check_path_length(backup_path(database_path, args.backup_dir))
        backup = create_backup(database_path, args.backup_dir)
    except Exception as error:
        raise ReviewScriptError(
            "Nao foi possivel criar o backup; o banco nao foi alterado ("
            + type(error).__name__
            + ")."
        ) from error

    say("Backup: " + str(backup.path))
    say("  tamanho: " + str(backup.size_bytes) + " bytes")
    say("  sha256: " + backup.sha256)

    database = Database(database_path)

    try:
        with database.transaction() as connection:
            result = review_rule(connection, args.rule_id, args.status, args.reviewer, note)
    except BaseException:
        print(
            "Falha: o banco foi mantido como estava. Backup: " + str(backup.path),
            file=sys.stderr,
        )
        raise

    integrity = database.integrity_check()
    foreign_key_errors = database.foreign_key_check()

    say(
        "Revisao gravada: regra #" + str(result.plan.rule_id) + " " + result.plan.before
        + " -> " + result.plan.after + "; audit_log #" + str(result.audit_id)
    )
    say("Verificacao final:")
    say("  integrity_check: " + integrity)
    say("  foreign_key_check: " + str(len(foreign_key_errors)) + " problema(s)")

    if integrity != "ok" or foreign_key_errors:
        raise ReviewScriptError(
            "Verificacao final falhou depois do COMMIT. Backup: " + str(backup.path)
        )

    return 0


def run(args):
    # A nota e o revisor sao conferidos antes de qualquer outra coisa; o
    # erro diz so o motivo, nunca o texto informado.
    note = check_note(args.note)
    check_reviewer(args.reviewer)

    say("Pacote fundos: " + str(pathlib.Path(fundos.__file__).resolve().parent))

    # Banco e backup em disco local, de caminho curto, antes de abrir
    # qualquer banco (no dry-run tambem): caminho de rede ou longo e recusado.
    try:
        database_path = check_local_paths(args.database, args.backup_dir)
    except BackupError as error:
        raise ReviewScriptError(str(error)) from error

    plan = read_plan(database_path, args.rule_id, args.status)
    describe(plan, note)

    if not plan.changes:
        say("Nada a revisar: a regra ja esta " + plan.after + ".")
        return 0

    if args.dry_run:
        say("Dry-run concluido: nenhum banco foi alterado.")
        return 0

    return commit(args, database_path, note)


def positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("use um inteiro a partir de 1") from None

    if value < 1:
        raise argparse.ArgumentTypeError("use um inteiro a partir de 1")

    return value


def build_parser():
    parser = argparse.ArgumentParser(
        description="Revisa uma regra do quota_class_map (por uma pessoa, identificada por um papel).",
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco, em disco local. Obrigatorio: nao ha banco padrao.",
    )
    parser.add_argument("--rule-id", required=True, type=positive_int, help="O id da regra.")
    parser.add_argument(
        "--status",
        required=True,
        choices=(REVIEWED, REJECTED),
        help="A situacao nova: revisado ou rejeitado.",
    )
    parser.add_argument(
        "--reviewer",
        required=True,
        help="O papel de quem revisou (papel:dono_da_frente_fundos ou papel:revisor_fundos).",
    )
    parser.add_argument(
        "--note",
        required=True,
        help="A nota da revisao: ASCII imprimivel, ate 200 caracteres, sem numero de documento.",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Confere a revisao so lendo o banco; nao escreve nada.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava a revisao e o audit_log.",
    )

    parser.add_argument(
        "--backup-dir",
        default=None,
        help=(
            "Pasta do backup (padrao: backups ao lado do banco). Use uma "
            "pasta curta se o caminho passar de 260 caracteres."
        ),
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except (ReviewScriptError, ReviewError, IndicatorDatabaseError) as error:
        print("Erro na revisao do quota_class_map: " + str(error), file=sys.stderr)
        return 1
    except Exception as error:
        # Erro inesperado: so o tipo, sem mensagem nem traceback.
        print(
            "Erro inesperado na revisao do quota_class_map: " + type(error).__name__,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
