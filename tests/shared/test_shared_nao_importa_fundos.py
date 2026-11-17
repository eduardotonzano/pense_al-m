"""A camada compartilhada nunca importa o pacote fundos (FU7.2, L8 e L9).

A camada le o banco do modulo de Fundos direto (SQLite), sem depender do
codigo do modulo. Os modulos pense_alm.shared.integration.fundos_* sao da
camada e nao contam: a regra pega so o pacote de topo fundos.
"""

import ast
import subprocess
import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src"
SHARED = SRC / "pense_alm" / "shared"


def imports_de_fundos(codigo):
    """Imports absolutos do pacote de topo fundos (level == 0)."""

    achados = []

    for no in ast.walk(ast.parse(codigo)):
        if isinstance(no, ast.Import):
            achados.extend(
                alias.name
                for alias in no.names
                if alias.name == "fundos" or alias.name.startswith("fundos.")
            )
        elif (
            isinstance(no, ast.ImportFrom)
            and no.level == 0
            and no.module is not None
            and (no.module == "fundos" or no.module.startswith("fundos."))
        ):
            achados.append(no.module)

    return achados


def test_l8_camada_nao_importa_o_pacote_fundos():
    arquivos = sorted(SHARED.rglob("*.py"))

    assert arquivos

    achados = {
        str(arquivo.relative_to(SHARED)): imports_de_fundos(
            arquivo.read_text(encoding="utf-8-sig")
        )
        for arquivo in arquivos
    }

    assert {arquivo: nomes for arquivo, nomes in achados.items() if nomes} == {}


def test_l8_regra_pega_so_o_pacote_de_topo_fundos():
    nao_contam = "\n".join(
        [
            "from .fundos_reader import FundosDatabaseReader",
            "from . import fundos_records",
            "from ..fundos import qualquer",
            "import fundos_reader",
            "import pense_alm.shared.integration.fundos_reader",
            "from pense_alm.shared.integration import fundos_records",
            "from pense_alm.shared.integration.fundos_reader import build_read_only_uri",
        ]
    )
    contam = "\n".join(
        [
            "import fundos",
            "import fundos.cnpj",
            "from fundos import cnpj",
            "from fundos.cadastro import loader",
            "import os, fundos as pacote",
        ]
    )

    assert imports_de_fundos(nao_contam) == []
    assert sorted(imports_de_fundos(contam)) == sorted(
        ["fundos", "fundos.cnpj", "fundos", "fundos.cadastro", "fundos"]
    )


def test_l9_importar_o_leitor_nao_carrega_o_pacote_fundos():
    # O -I ignora o PYTHONPATH: o src vai por argumento, e nada grava
    # __pycache__.
    codigo = "\n".join(
        [
            "import sys",
            "sys.dont_write_bytecode = True",
            "sys.path.insert(0, sys.argv[1])",
            "import pense_alm.shared.integration.fundos_reader",
            "print('pense_alm.shared.integration.fundos_reader' in sys.modules)",
            "print(sorted(m for m in sys.modules"
            " if m == 'fundos' or m.startswith('fundos.')))",
        ]
    )

    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo, str(SRC)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.split() == ["True", "[]"]
