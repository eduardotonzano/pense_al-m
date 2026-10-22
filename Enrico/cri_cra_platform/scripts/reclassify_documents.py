"""Reclassifica documentos hoje em "Outro" com o classificador estrito.

Uso (a partir de Enrico/cri_cra_platform):

    python scripts/reclassify_documents.py --database <banco> --dry-run
    python scripts/reclassify_documents.py --database <banco> --commit

--dry-run abre o banco somente para leitura e mostra, em duas secoes, o que
cada grupo de regras mudaria. --commit faz o backup, troca so linhas que estao
em "Outro" (grupo verificado; os dois grupos com --enable-unverified-rules),
registra cada troca em document_category_changes e verifica antes do COMMIT.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.services.category_reclassification import (
    build_preview,
    commit_reclassification,
    format_preview,
    load_documents,
    open_read_only,
)


def run(args) -> int:
    database_path = Path(args.database)

    if not database_path.is_file():
        raise FileNotFoundError(f"Banco nao encontrado: {database_path}")

    with closing(open_read_only(database_path)) as reader:
        rows, grid_available = load_documents(reader)

    preview = build_preview(rows, grid_available, str(database_path.resolve()))
    print(format_preview(preview, examples=args.examples))

    if args.report_path:
        Path(args.report_path).write_text(
            json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Relatorio JSON: {args.report_path}")

    if args.dry_run:
        print("\nDry-run concluido: nada foi gravado.")
        return 0

    result = commit_reclassification(
        database_path,
        include_unverified=args.enable_unverified_rules,
        backup_dir=args.backup_dir,
    )

    if result["changes"] == 0:
        print("\nNada a gravar: nenhum documento mudaria. Sem backup.")
        return 0

    backup = result["backup"]
    print(f"\nBackup: {backup.path}")
    print(f"  tamanho: {backup.size_bytes} bytes")
    print(f"  sha256: {backup.sha256}")
    print(f"Documentos reclassificados: {result['changes']} (execucao {result['run_id']})")

    for transition, total in sorted(result["by_transition"].items()):
        print(f"  {transition}: {total}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Reclassifica documentos em "Outro" com o classificador estrito.'
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco. Obrigatorio: nao ha banco padrao.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que mudaria; nao grava nada.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava as trocas.",
    )
    parser.add_argument(
        "--enable-unverified-rules",
        action="store_true",
        help=(
            "Liga as regras sem evidencia real (Aditamento, Termo de "
            "Securitizacao, Fato Relevante, Agente Fiduciario, Rating e "
            "Anuncio de Encerramento). Por padrao so valem as verificadas."
        ),
    )
    parser.add_argument("--backup-dir", default=None)
    parser.add_argument("--report-path", default=None, help="JSON da previa (opcional).")
    parser.add_argument("--examples", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except Exception as error:
        print(f"Erro ao reclassificar documentos: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
