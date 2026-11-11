"""Resolve o CNPJ da securitizadora e do devedor pelo Informe Mensal da CVM (S-08).

Uso (a partir de Enrico/cri_cra_platform):

    python scripts/resolve_cnpj.py --database <banco> --dry-run
    python scripts/resolve_cnpj.py --database <banco> --commit

--dry-run abre o banco somente para leitura e mostra, por ativo, o CNPJ que a
CVM informa, a fonte, o periodo e o que seria feito; nao grava nada. --commit
faz o backup e grava numa transacao, so em campo vazio, com fonte e data em
asset_cnpj_observations. O ativo e ligado ao informe so por ISIN e CETIP: o
nome nunca e usado. Sem valor unico e valido da CVM, o campo continua ausente.

Os ZIPs da CVM ficam em --cvm-dir (padrao data/raw/cvm, fora do Git).
--download baixa os ZIPs do ano para essa pasta; use so com aprovacao.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.collectors.cvm_informe_mensal import download_archive
from credit_assets.services.category_reclassification import open_read_only
from credit_assets.services.cnpj_resolution import (
    build_preview,
    commit_resolution,
    format_preview,
    load_archives,
    load_assets,
)


def download_missing(args, fetch) -> None:
    """Baixa os ZIPs dos anos pedidos para os tipos de ativo que estao no banco."""

    with closing(open_read_only(args.database)) as reader:
        kinds = sorted({item.tipo_ativo.lower() for item in load_assets(reader, args.only)})

    for kind in kinds:
        for year in args.years:
            kwargs = {"refresh": args.refresh}

            if fetch is not None:
                kwargs["fetch"] = fetch

            path, downloaded = download_archive(kind, year, args.cvm_dir, **kwargs)
            print(("Baixado: " if downloaded else "Ja existe, mantido: ") + str(path))


def run(args, fetch=None) -> int:
    database_path = Path(args.database)

    if not database_path.is_file():
        raise FileNotFoundError(f"Banco nao encontrado: {database_path}")

    if args.download:
        download_missing(args, fetch)

    if args.dry_run:
        archives, ignored = load_archives(args.cvm_dir)

        with closing(open_read_only(database_path)) as reader:
            preview, _ = build_preview(
                reader, archives, ignored, database=str(database_path.resolve()),
                only=args.only, apply_devedor=args.apply_devedor,
            )

        print(format_preview(preview))
        write_report(args, preview)
        print("\nDry-run concluido: nada foi gravado.")
        return 0

    result = commit_resolution(
        database_path,
        args.cvm_dir,
        only=args.only,
        apply_devedor=args.apply_devedor,
        backup_dir=args.backup_dir,
    )
    print(format_preview(result["preview"]))
    write_report(args, result["preview"])

    if result["backup"] is None:
        print("\nNada a gravar: o banco ja tem estas observacoes. Sem backup.")
        return 0

    backup = result["backup"]
    print(f"\nBackup: {backup.path}")
    print(f"  tamanho: {backup.size_bytes} bytes")
    print(f"  sha256: {backup.sha256}")
    print(f"Campos gravados em assets: {result['fields_written']}")
    print(f"Observacoes registradas: {result['observations_added']} (execucao {result['run_id']})")
    return 0


def write_report(args, preview: dict) -> None:
    if args.report_path:
        Path(args.report_path).write_text(
            json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Relatorio JSON: {args.report_path}")


def parse_years(text: str) -> list[int]:
    try:
        return [int(item) for item in text.split(",") if item.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"--years espera anos separados por virgula: {text!r}")


def build_parser() -> argparse.ArgumentParser:
    today = date.today().year
    parser = argparse.ArgumentParser(
        description=(
            "Resolve o CNPJ da securitizadora e do devedor pelo Informe Mensal da "
            "CVM, ligando o ativo so por ISIN e CETIP."
        )
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
        help="Mostra o que seria feito; nao grava nada.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava os CNPJ resolvidos.",
    )
    parser.add_argument(
        "--cvm-dir",
        default=str(ROOT / "data" / "raw" / "cvm"),
        help="Pasta com os ZIPs inf_mensal_cri_<ano>.zip e inf_mensal_cra_<ano>.zip.",
    )
    parser.add_argument("--only", default=None, help="Resolve so o ativo com este ISIN ou CETIP.")
    parser.add_argument(
        "--apply-devedor",
        action="store_true",
        help=(
            "Grava o devedor em cnpj_devedor. Por padrao ele so e registrado como "
            "candidato e o campo continua vazio."
        ),
    )
    parser.add_argument("--backup-dir", default=None)
    parser.add_argument("--report-path", default=None, help="JSON da previa (opcional).")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Baixa os ZIPs dos anos de --years para --cvm-dir (usa a rede).",
    )
    parser.add_argument(
        "--years",
        type=parse_years,
        default=[today - 1, today],
        help="Anos a baixar com --download, separados por virgula (padrao: anterior e atual).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Com --download, troca os ZIPs que ja existem.",
    )
    return parser


def main(argv: list[str] | None = None, fetch=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        return run(args, fetch)
    except Exception as error:
        print(f"Erro ao resolver CNPJ: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
