"""Testes da entrada operacional do cadastro de Fundos (FU7.2): fundos_cli.

Banco de Fundos sintetico (fundos_sintetico) e destino SQLite da camada,
tudo em tmp_path; sem banco real e sem rede. O caminho UNC so aparece como
texto, com Path vigiado para provar que ele nao e tocado. So CNPJs ficticios
de cnpj_amostras e nomes marcados como ficticios. K1 a K7 e R2 do plano.
"""

import hashlib
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityType,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration import fundos_cli
from pense_alm.shared.integration.fundos_adapter import FundosAdapter
from pense_alm.shared.integration.fundos_cli import (
    DRIVE_REMOTE,
    NETWORK_MESSAGE,
    PARTIAL_MESSAGE,
    RUNNING_MESSAGE,
    _exit_code,
    _import_into,
    _is_network_path,
    build_parser,
    main,
    run_fundos_import,
)
from pense_alm.shared.integration.fundos_investment_report import (
    AtrasoEmMeses,
    FundosInvestmentReport,
)
from pense_alm.shared.integration.fundos_reader import FundosDatabaseReader
from pense_alm.shared.integration.fundos_relation_service import FundosRelationService
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara
from .cda_sintetico import COMPETENCIA_CDA, INICIO_CDA, PERIODO, BancoCda
from .fundos_sintetico import BancoFundos, criar_banco


CNPJ_FUNDO = cnpj_ficticio(1)
CNPJ_ADMIN = cnpj_ficticio(5)
CNPJ_CUSTODIANTE = cnpj_ficticio(6)
CNPJ_GESTORA = cnpj_ficticio(7)
CNPJS = (CNPJ_FUNDO, CNPJ_ADMIN, CNPJ_CUSTODIANTE, CNPJ_GESTORA)
UNC = "\\\\servidor-ficticio\\pasta\\destino.sqlite3"
ANTIGA = "2026-09-30"
INICIO_ANTIGO = "2026-09-30T12:00:00.000000+00:00"
B6_COM_BACKUP = (
    "Erro: SnapshotOlderThanApplied; nenhum dado foi gravado; o backup feito "
    "antes continua na pasta de --backup-dir."
)
B6_SEM_BACKUP = "Erro: SnapshotOlderThanApplied; nenhum dado foi gravado."

adaptador = FundosAdapter()


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def banco_de_fundos(
    pasta,
    *,
    competencia="2026-10-27",
    inicio="2026-10-27T12:00:00.000000+00:00",
    status="success",
    custodiante=True,
    gestor=True,
    tipo_pessoa="PJ",
    com_cadastro=True,
):
    """Banco de Fundos sintetico com um fundo e as prestadoras pedidas."""

    pasta.mkdir(parents=True, exist_ok=True)
    caminho = criar_banco(pasta)

    if not com_cadastro:
        return caminho

    banco = BancoFundos(caminho)
    coleta = banco.coleta(inicio=inicio, status=status)
    fundo = banco.fundo_do_cadastro(
        coleta,
        CNPJ_FUNDO,
        competencia=competencia,
        tipo_pessoa=tipo_pessoa,
    )
    banco.administrador(
        coleta,
        fundo,
        CNPJ_ADMIN,
        nome="ADMINISTRADORA FICTÍCIA",
        competencia=competencia,
    )

    if gestor:
        banco.gestor(
            coleta,
            fundo,
            CNPJ_GESTORA,
            nome="GESTORA FICTÍCIA",
            competencia=competencia,
        )

    if custodiante:
        classe = banco.classe_do_cadastro(
            coleta,
            CNPJ_FUNDO,
            fundo,
            competencia=competencia,
        )
        banco.custodiante(
            coleta,
            classe,
            CNPJ_CUSTODIANTE,
            nome="CUSTODIANTE FICTÍCIA",
            competencia=competencia,
        )

    return caminho


@pytest.fixture
def caminhos(tmp_path):
    return SimpleNamespace(
        fundos=banco_de_fundos(tmp_path / "fundos"),
        destino=tmp_path / "destino" / "camada.sqlite3",
        backups=tmp_path / "backups",
    )


def argumentos(caminhos, *extra, fundos=None, destino=None):
    return [
        "--fundos-db",
        str(fundos or caminhos.fundos),
        "--target-db",
        str(destino or caminhos.destino),
        *extra,
    ]


def gravar(caminhos, *extra, **muda):
    return argumentos(
        caminhos,
        "--commit",
        "--backup-dir",
        str(caminhos.backups),
        *extra,
        **muda,
    )


def linhas(destino):
    conexao = sqlite3.connect(destino)

    try:
        return {
            tabela: conexao.execute(f"SELECT * FROM {tabela} ORDER BY 1").fetchall()
            for tabela in (
                "entities",
                "entity_identifiers",
                "entity_relationships",
                "data_provenance",
            )
        }
    finally:
        conexao.close()


def relacoes_em(banco):
    return SQLiteRelationshipRepository(SQLiteConnectionManager(banco)).count()


def criar_destino(caminhos, capsys, **muda):
    assert main(gravar(caminhos, "--create", **muda)) == 0
    capsys.readouterr()


# --- Parser e argumentos ---


def test_parser_padrao_e_simulacao():
    parsed = build_parser().parse_args(
        ["--fundos-db", "fundos.db", "--target-db", "camada.sqlite3"]
    )

    assert parsed.fundos_db == Path("fundos.db")
    assert parsed.target_db == Path("camada.sqlite3")
    assert parsed.dry_run is False
    assert parsed.commit is False
    assert parsed.backup_dir is None
    assert parsed.create is False


@pytest.mark.parametrize(
    "extra",
    [
        ["--commit"],
        ["--backup-dir", "BACKUPS"],
        ["--create"],
        ["--dry-run", "--commit", "--backup-dir", "BACKUPS"],
        ["--commit", "--backup-dir", "BACKUPS"],
    ],
)
def test_argumentos_invalidos_saem_com_2_sem_criar_nada(caminhos, extra):
    extra = [str(caminhos.backups) if item == "BACKUPS" else item for item in extra]

    with pytest.raises(SystemExit) as erro:
        main(argumentos(caminhos, *extra))

    assert erro.value.code == 2
    assert not caminhos.destino.exists()
    assert not caminhos.backups.exists()


def test_fundos_inexistente_ou_igual_ao_destino_sai_com_2(caminhos, tmp_path):
    with pytest.raises(SystemExit) as erro:
        main(argumentos(caminhos, fundos=tmp_path / "inexistente.db"))

    assert erro.value.code == 2

    with pytest.raises(SystemExit) as erro:
        main(argumentos(caminhos, destino=caminhos.fundos))

    assert erro.value.code == 2


def test_run_recusa_combinacao_invalida(caminhos):
    with pytest.raises(ValueError):
        run_fundos_import(caminhos.fundos, caminhos.destino, commit=True)

    with pytest.raises(ValueError):
        run_fundos_import(caminhos.fundos, caminhos.destino, backup_dir=caminhos.backups)

    with pytest.raises(ValueError):
        run_fundos_import(caminhos.fundos, caminhos.destino, create=True)


# --- Destino de rede ---


def test_commit_recusa_unc_antes_de_tocar_no_destino(caminhos, monkeypatch, capsys):
    def vigia(nome):
        original = getattr(Path, nome)

        def chamada(self, *args, **kwargs):
            if str(self).startswith(("\\\\", "//")):
                raise AssertionError(nome + " chamado com o destino de rede")

            return original(self, *args, **kwargs)

        return chamada

    for nome in ("resolve", "is_file", "exists"):
        monkeypatch.setattr(Path, nome, vigia(nome))

    codigo = main(gravar(caminhos, destino=UNC))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert "use um banco em disco local" in saida
    assert saida.strip() == NETWORK_MESSAGE
    assert not caminhos.backups.exists()


def test_run_direto_tambem_recusa_unc(caminhos, capsys):
    codigo = run_fundos_import(
        caminhos.fundos,
        UNC,
        commit=True,
        backup_dir=caminhos.backups,
    )

    assert codigo == 2
    assert NETWORK_MESSAGE in capsys.readouterr().out
    assert not caminhos.backups.exists()


@pytest.mark.parametrize("texto", [UNC, "//servidor-ficticio/pasta/destino.sqlite3"])
def test_unc_e_rede(texto):
    assert _is_network_path(texto)


def test_unidade_mapeada_remota_e_rede(monkeypatch):
    chamadas = []
    monkeypatch.setattr(fundos_cli, "_on_windows", lambda: True)
    monkeypatch.setattr(
        fundos_cli,
        "_drive_type",
        lambda drive: chamadas.append(drive) or DRIVE_REMOTE,
    )

    assert _is_network_path("Z:\\pasta\\destino.sqlite3")
    assert chamadas == ["Z:"]


@pytest.mark.parametrize("tipo", [3, None])
def test_unidade_local_ou_tipo_desconhecido_nao_e_rede(monkeypatch, tipo):
    monkeypatch.setattr(fundos_cli, "_on_windows", lambda: True)
    monkeypatch.setattr(fundos_cli, "_drive_type", lambda drive: tipo)

    assert not _is_network_path("C:\\pasta\\destino.sqlite3")


def test_caminho_sem_unidade_nao_consulta_o_tipo(monkeypatch, tmp_path):
    def nao_consultar(drive):
        raise AssertionError("o tipo da unidade nao deveria ser consultado")

    # Pasta atual local: no Windows, um caminho sem unidade herda a da pasta
    # atual (e a raiz deste repositorio e um compartilhamento).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fundos_cli, "_on_windows", lambda: False)
    monkeypatch.setattr(fundos_cli, "_drive_type", nao_consultar)

    assert not _is_network_path("/pasta/destino.sqlite3")


def test_tipo_de_unidade_so_e_lido_no_windows(monkeypatch):
    monkeypatch.setattr(fundos_cli, "_on_windows", lambda: False)

    assert fundos_cli._drive_type("C:") is None


def test_relativo_em_pasta_local_nao_e_rede(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assert not _is_network_path("destino.sqlite3")
    assert not _is_network_path(tmp_path / "destino.sqlite3")


# --- Dry-run ---


def test_dry_run_nao_altera_o_destino(caminhos, capsys):
    criar_destino(caminhos, capsys)
    destino_antes = sha256_of(caminhos.destino)
    fundos_antes = sha256_of(caminhos.fundos)

    codigo = main(argumentos(caminhos))
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "Modo: dry-run" in saida
    assert RUNNING_MESSAGE in saida
    assert "mantidas: 1 | 1 | 1" in saida
    assert "Nada foi gravado no destino; a copia descartavel foi removida." in saida
    assert sha256_of(caminhos.destino) == destino_antes
    assert sha256_of(caminhos.fundos) == fundos_antes


def test_dry_run_explicito_faz_o_mesmo(caminhos, capsys):
    criar_destino(caminhos, capsys)
    destino_antes = sha256_of(caminhos.destino)

    assert main(argumentos(caminhos, "--dry-run")) == 0
    assert sha256_of(caminhos.destino) == destino_antes


def test_dry_run_sem_destino_nao_cria_nada(caminhos, capsys):
    codigo = main(argumentos(caminhos))
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "Aviso: destino inexistente; simulacao sobre um banco vazio." in saida
    assert "criadas: 1 | 1 | 1" in saida
    assert "Aviso: seria a primeira gravacao de custodied_by neste banco" in saida
    assert not caminhos.destino.exists()
    assert not caminhos.destino.parent.exists()


def test_dry_run_remove_a_copia_com_sucesso_e_com_falha(caminhos, tmp_path, monkeypatch, capsys):
    criar_destino(caminhos, capsys)
    temporaria = tmp_path / "temporaria"
    temporaria.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporaria))

    assert main(argumentos(caminhos)) == 0
    assert list(temporaria.iterdir()) == []

    def falha(self, snapshot, phase):
        raise RuntimeError("falha ficticia")

    monkeypatch.setattr(FundosRelationService, "import_relationships", falha)

    assert main(argumentos(caminhos)) == 2
    assert list(temporaria.iterdir()) == []
    assert "a simulacao falhou; o destino nao foi alterado" in capsys.readouterr().out


# --- Commit e backup ---


def test_commit_faz_backup_antes_de_gravar(caminhos, tmp_path, capsys):
    sem_custodia = banco_de_fundos(tmp_path / "sem_custodia", custodiante=False)
    criar_destino(caminhos, capsys, fundos=sem_custodia)

    codigo = main(gravar(caminhos))
    saida = capsys.readouterr().out
    (backup,) = list(caminhos.backups.iterdir())

    assert codigo == 0
    assert "Modo: commit" in saida
    assert RUNNING_MESSAGE in saida
    assert f"Backup: {backup.name}" in saida
    assert f"  tamanho: {backup.stat().st_size} bytes" in saida
    assert f"  sha256: {sha256_of(backup)}" in saida
    assert "  o backup esta na pasta de --backup-dir" in saida
    assert str(caminhos.backups) not in saida
    assert str(tmp_path) not in saida
    assert relacoes_em(backup) == 2
    assert relacoes_em(caminhos.destino) == 3


def test_commit_e_idempotente(caminhos, capsys):
    criar_destino(caminhos, capsys)

    codigo = main(gravar(caminhos))
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "criadas: 0 | 0 | 0" in saida
    assert "mantidas: 1 | 1 | 1" in saida
    assert len(list(caminhos.backups.iterdir())) == 1
    assert relacoes_em(caminhos.destino) == 3


def test_falha_no_backup_nao_grava(caminhos, monkeypatch, capsys):
    criar_destino(caminhos, capsys)
    antes = sha256_of(caminhos.destino)

    def backup_que_falha(database_path, backup_dir):
        raise OSError("disco cheio ficticio")

    monkeypatch.setattr(fundos_cli, "create_sqlite_backup", backup_que_falha)

    codigo = main(gravar(caminhos))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert "Erro: falha no backup (OSError); nada foi gravado." in saida
    assert "disco cheio" not in saida
    assert sha256_of(caminhos.destino) == antes


def test_create_cria_o_destino_sem_backup(caminhos, capsys):
    codigo = main(gravar(caminhos, "--create"))
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "Banco de destino novo: nao ha o que copiar no backup." in saida
    assert "Backup:" not in saida
    assert RUNNING_MESSAGE in saida
    assert "Resultado: codigo 0" in saida
    assert caminhos.destino.exists()
    assert not caminhos.backups.exists()


def test_commit_nao_altera_o_banco_de_fundos(caminhos, capsys):
    antes = sha256_of(caminhos.fundos)

    criar_destino(caminhos, capsys)
    main(gravar(caminhos))

    assert sha256_of(caminhos.fundos) == antes


# --- Codigos de saida ---


def test_sem_retrato_sai_2(caminhos, tmp_path, capsys):
    vazio = banco_de_fundos(tmp_path / "vazio", com_cadastro=False)

    codigo = main(gravar(caminhos, "--create", fundos=vazio))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert "Erro: CadastroNotFound; nada foi gravado." in saida
    assert not caminhos.destino.exists()


def test_c7_retrato_antigo_no_commit_aborta_sem_gravar(caminhos, tmp_path, capsys):
    criar_destino(caminhos, capsys)
    antes = linhas(caminhos.destino)
    antigo = banco_de_fundos(tmp_path / "antigo", competencia=ANTIGA, inicio=INICIO_ANTIGO)

    codigo = main(gravar(caminhos, fundos=antigo))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert B6_COM_BACKUP in saida
    assert linhas(caminhos.destino) == antes
    assert len(list(caminhos.backups.iterdir())) == 1


def test_retrato_antigo_no_dry_run_so_a_primeira_parte(caminhos, tmp_path, capsys):
    criar_destino(caminhos, capsys)
    antigo = banco_de_fundos(tmp_path / "antigo", competencia=ANTIGA, inicio=INICIO_ANTIGO)

    codigo = main(argumentos(caminhos, fundos=antigo))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert B6_SEM_BACKUP in saida
    assert "o backup feito antes" not in saida


def test_retrato_antigo_sem_backup_so_a_primeira_parte(caminhos, tmp_path, capsys):
    criar_destino(caminhos, capsys)
    antigo = banco_de_fundos(tmp_path / "antigo", competencia=ANTIGA, inicio=INICIO_ANTIGO)
    snapshot, cda = FundosDatabaseReader(antigo).read_all()

    codigo = _import_into(snapshot, cda, caminhos.destino, commit=True, has_backup=False)
    saida = capsys.readouterr().out

    assert codigo == 2
    assert B6_SEM_BACKUP in saida
    assert "o backup feito antes" not in saida


def test_formato_de_data_inesperado_sai_2(caminhos, capsys):
    criar_destino(caminhos, capsys)
    proveniencia = DataProvenance(
        source_type=SourceType.CVM,
        source_name="Fundos - CVM Cadastro",
        source_reference="fundos:funds:99",
        collected_at=datetime(2026, 10, 27, 12, tzinfo=UTC),
        reference_date=datetime(2026, 10, 27, 3, tzinfo=UTC),
    )
    SQLiteEntityRepository(SQLiteConnectionManager(caminhos.destino)).save(
        Entity(
            legal_name="FUNDO FICTÍCIO 99",
            entity_type=EntityType.FIDC,
            provenance=proveniencia,
            created_at=proveniencia.collected_at,
            updated_at=proveniencia.collected_at,
        )
    )

    codigo = main(gravar(caminhos))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert (
        "Erro: FundosTargetStateError; nenhum dado foi gravado; o backup feito "
        "antes continua na pasta de --backup-dir."
    ) in saida


def test_erro_contado_sai_2_com_execucao_parcial(caminhos, monkeypatch, capsys):
    original = SQLiteRelationshipRepository.save

    def falha(self, relationship):
        if relationship.relationship_type is RelationshipType.CUSTODIED_BY:
            raise RuntimeError("falha ficticia")

        return original(self, relationship)

    monkeypatch.setattr(SQLiteRelationshipRepository, "save", falha)

    codigo = main(gravar(caminhos, "--create"))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert "Erros: 1" in saida
    assert "  relacoes custodied_by criar RuntimeError: 1" in saida
    assert PARTIAL_MESSAGE in saida
    assert "Resultado: codigo 2" in saida
    assert "falha ficticia" not in saida


def test_erro_contado_na_fase_de_entidades_sai_2(caminhos, monkeypatch, capsys):
    original = SQLiteEntityRepository.save

    def falha(self, entity):
        if entity.entity_type is EntityType.FIDC:
            raise RuntimeError("falha ficticia")

        return original(self, entity)

    monkeypatch.setattr(SQLiteEntityRepository, "save", falha)

    codigo = main(gravar(caminhos, "--create"))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert "Erros: 1" in saida
    assert "  fundos RuntimeError: 1" in saida
    assert PARTIAL_MESSAGE in saida
    assert "Resultado: codigo 2" in saida
    assert "falha ficticia" not in saida

    for cnpj in CNPJS:
        assert cnpj not in saida
        assert com_mascara(cnpj) not in saida


def test_falha_no_meio_sai_2_com_execucao_parcial(caminhos, monkeypatch, capsys):
    def falha(self, snapshot, phase):
        raise RuntimeError("falha ficticia")

    monkeypatch.setattr(FundosRelationService, "import_relationships", falha)

    codigo = main(gravar(caminhos, "--create"))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert "Erro: RuntimeError" in saida
    assert PARTIAL_MESSAGE in saida
    assert "falha ficticia" not in saida
    assert SQLiteEntityRepository(SQLiteConnectionManager(caminhos.destino)).count() == 4
    assert relacoes_em(caminhos.destino) == 0


def test_id_ocupado_sai_3(caminhos, capsys):
    SQLiteEntityRepository(SQLiteConnectionManager(caminhos.destino)).save(
        Entity(
            entity_id=adaptador.entity_id(CNPJ_ADMIN),
            legal_name="OCUPANTE FICTÍCIO",
            entity_type=EntityType.OTHER,
            provenance=DataProvenance(
                source_type=SourceType.MANUAL,
                source_name="Teste ficticio",
            ),
        )
    )

    codigo = main(gravar(caminhos))
    saida = capsys.readouterr().out

    assert codigo == 3
    assert "Resultado: codigo 3" in saida


def test_leitura_incompleta_sai_4(caminhos, tmp_path, capsys):
    parcial = banco_de_fundos(tmp_path / "parcial", status="partial")

    codigo = main(gravar(caminhos, "--create", fundos=parcial))
    saida = capsys.readouterr().out

    assert codigo == 4
    assert (
        "leitura completa: nao (motivo: status_nao_success); "
        "nenhuma relacao do cadastro e fechada"
    ) in saida
    assert "Resultado: codigo 4" in saida


def corrida(erros=0, id_ocupado=0, colisao=0, completa=True):
    return SimpleNamespace(
        erros_total=erros,
        id_ocupado=id_ocupado,
        cnpj_colisao=colisao,
        leitura_completa=completa,
    )


@pytest.mark.parametrize(
    ("run", "esperado"),
    [
        (corrida(), 0),
        (corrida(completa=False), 4),
        (corrida(colisao=2), 3),
        (corrida(id_ocupado=1), 3),
        (corrida(colisao=2, completa=False), 3),
        (corrida(erros=1), 2),
        (corrida(erros=1, colisao=2, id_ocupado=1, completa=False), 2),
    ],
)
def test_precedencia_dos_codigos_de_saida(run, esperado):
    assert _exit_code(run) == esperado


# --- Avisos e linhas da saida ---


def test_aviso_de_custodied_by_so_na_primeira_gravacao(caminhos, capsys):
    main(gravar(caminhos, "--create"))
    primeira = capsys.readouterr().out
    main(gravar(caminhos))
    segunda = capsys.readouterr().out

    assert "Aviso: primeira gravacao de custodied_by neste banco" in primeira
    assert "0fb907f (#49)" in primeira
    assert "custodied_by neste banco" not in segunda


def test_sem_custodiante_nao_ha_aviso(caminhos, tmp_path, capsys):
    sem_custodia = banco_de_fundos(tmp_path / "sem_custodia", custodiante=False)

    main(gravar(caminhos, "--create", fundos=sem_custodia))

    assert "custodied_by neste banco" not in capsys.readouterr().out


def test_linha_da_gestora_pessoa_fisica(caminhos, tmp_path, capsys):
    pf = banco_de_fundos(tmp_path / "pf", tipo_pessoa="PF", gestor=False)

    main(argumentos(caminhos, fundos=pf))

    assert (
        "fundos com gestora pessoa fisica (todas as situacoes): 1"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize("modo", ["dry-run", "commit"])
def test_linha_de_execucao_antes_das_fases(caminhos, capsys, modo):
    extra = ["--commit", "--backup-dir", str(caminhos.backups), "--create"]
    main(argumentos(caminhos, *(extra if modo == "commit" else [])))
    saida = capsys.readouterr().out

    assert RUNNING_MESSAGE in saida
    assert saida.index(RUNNING_MESSAGE) < saida.index("Entidades")


@pytest.mark.parametrize(
    "modo",
    ["dry-run", "commit", "falha no backup", "falha no meio", "erro contado"],
)
def test_saida_sem_cnpj_nome_caminho_nem_mensagem(caminhos, tmp_path, monkeypatch, capsys, modo):
    if modo == "falha no backup":
        criar_destino(caminhos, capsys)

        def backup_que_falha(database_path, backup_dir):
            raise OSError("disco cheio ficticio")

        monkeypatch.setattr(fundos_cli, "create_sqlite_backup", backup_que_falha)

    if modo == "falha no meio":

        def falha(self, snapshot, phase):
            raise RuntimeError("falha ficticia")

        monkeypatch.setattr(FundosRelationService, "import_relationships", falha)

    if modo == "erro contado":
        original = SQLiteRelationshipRepository.save

        def falha_no_save(self, relationship):
            if relationship.relationship_type is RelationshipType.MANAGES:
                raise RuntimeError("falha ficticia")

            return original(self, relationship)

        monkeypatch.setattr(SQLiteRelationshipRepository, "save", falha_no_save)

    if modo == "dry-run":
        main(argumentos(caminhos))
    elif modo == "falha no backup":
        main(gravar(caminhos))
    else:
        main(gravar(caminhos, "--create"))

    saida = capsys.readouterr().out
    proibidos = [
        *CNPJS,
        *(com_mascara(cnpj) for cnpj in CNPJS),
        "FICTÍCI",
        str(tmp_path),
        str(caminhos.backups),
        str(caminhos.destino),
        "falha ficticia",
        "disco cheio",
    ]

    for proibido in proibidos:
        assert proibido not in saida


# --- PR C2: fase 4 (CDA) na CLI, IC2 a IC7 ---


CNPJ_INVESTIDO = cnpj_ficticio(2)
CNPJS_CDA = (*CNPJS, CNPJ_INVESTIDO)
SEM_CDA_LINHA = "Investe em (CDA): sem dados de CDA (motivo: sem_migration_004)"
CDA_SETEMBRO = dict(
    periodo="202609",
    competencia="2026-09-30",
    inicio="2026-10-29T12:00:00.000000+00:00",
)
CDA_MAIS_ANTIGO = (
    "Erro: CdaOlderThanApplied; nenhum dado foi gravado; o backup feito antes "
    "continua na pasta de --backup-dir."
)


def banco_com_cda(
    pasta,
    *,
    status="success",
    posicao=True,
    periodo=PERIODO,
    competencia=COMPETENCIA_CDA,
    inicio=INICIO_CDA,
):
    """Banco de Fundos com a 004: dois fundos no cadastro e uma coleta de CDA.

    CNPJ_FUNDO investe em CNPJ_INVESTIDO; posicao=False deixa a coleta do CDA
    sem nenhuma posicao.
    """

    pasta.mkdir(parents=True, exist_ok=True)
    banco = BancoCda(criar_banco(pasta, versoes=(1, 2, 3, 4)))
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_FUNDO)
    banco.administrador(coleta, fundo, CNPJ_ADMIN, nome="ADMINISTRADORA FICTICIA")
    banco.fundo_do_cadastro(coleta, CNPJ_INVESTIDO)
    coleta_cda = banco.coleta_cda(periodo=periodo, status=status, inicio=inicio)

    if posicao:
        banco.posicao(coleta_cda, CNPJ_INVESTIDO, fundo_id=fundo, competencia=competencia)

    return banco.caminho


def bloco_cda(saida):
    """As linhas do bloco Investe em (CDA), ate antes de Erros."""

    linhas_saida = saida.splitlines()
    inicio = [linha.startswith("Investe em (CDA)") for linha in linhas_saida].index(True)
    fim = [linha.startswith("Erros: ") for linha in linhas_saida].index(True)
    return linhas_saida[inicio:fim]


def falhar_invests_in(monkeypatch):
    original = SQLiteRelationshipRepository.save

    def falha(self, relationship):
        if relationship.relationship_type is RelationshipType.INVESTS_IN:
            raise RuntimeError("falha ficticia")

        return original(self, relationship)

    monkeypatch.setattr(SQLiteRelationshipRepository, "save", falha)


def test_ic5_banco_sem_004_e_a_saida_do_b2_com_uma_linha_a_mais(caminhos, monkeypatch, capsys):
    main(argumentos(caminhos))
    saida = capsys.readouterr().out.splitlines()
    monkeypatch.setattr(fundos_cli, "_print_investments", lambda report: None)
    main(argumentos(caminhos))
    sem_bloco = capsys.readouterr().out.splitlines()
    posicao = saida.index(SEM_CDA_LINHA)

    assert saida[posicao - 1] == "  ausentes do retrato (informativo): 0"
    assert saida[posicao + 1] == "Erros: 0"
    assert saida[:posicao] + saida[posicao + 1 :] == sem_bloco
    assert sum(linha.startswith("Investe em") for linha in saida) == 1


def test_bloco_do_cda_linha_a_linha(capsys):
    report = FundosInvestmentReport(
        cda_disponivel=True,
        leitura_completa=True,
        competencia_mais_nova_completa=datetime.fromisoformat(COMPETENCIA_CDA).date(),
        detentores_lidos=2,
        detentores_na_camada=2,
        pares_lidos=2,
        gravadas=1,
        criadas=1,
        mantidas=1,
        detentores_atrasados=2,
        relacoes_de_detentor_atrasado=1,
        atraso=(AtrasoEmMeses(1, 1, 0), AtrasoEmMeses(2, 1, 1)),
    )

    fundos_cli._print_investments(report)

    assert capsys.readouterr().out.splitlines() == [
        "Investe em (CDA): competencia mais nova completa 2026-10-31; leitura completa: sim",
        "  detentores: lidos 2; na camada 2; fora do normal na camada 0; fora da camada 0;"
        " fora do retrato 0; cnpj recusado 0; em cda incompleto 0",
        "  pares lidos: 2",
        "  gravadas: 1",
        "  criadas: 1",
        "  mantidas: 1",
        "  reabertas: 0",
        "  outra fonte presente: 0",
        "  status inesperado presente: 0",
        "  vigencia posterior presente: 0",
        "  fechadas: 0",
        "  fechamento suspenso: 0",
        "  suspensa por confidencial: 0",
        "  inativa ausente: 0",
        "  outra fonte ausente: 0",
        "  status inesperado ausente: 0",
        "  vigencia posterior ausente: 0",
        "  nao criadas: 0 (investido fora da camada 0; investido de outro tipo 0;"
        " autorrelacao 0; cnpj recusado 0)",
        "  fora do normal: detentores com relacao 0; relacoes intactas 0",
        "  pares com investido fora do normal (informativo): 0",
        "  relacoes de detentor ausente do cda (informativo): 0",
        "  atraso (informativo): detentores 2; relacoes 1",
        "    1 mes: detentores 1; relacoes 0",
        "    2 meses: detentores 1; relacoes 1",
    ]


def test_ic2_cda_incompleto_com_cadastro_completo_sai_4(caminhos, tmp_path, capsys):
    parcial = banco_com_cda(tmp_path / "parcial", status="partial")

    codigo = main(gravar(caminhos, "--create", fundos=parcial))
    saida = capsys.readouterr().out
    bloco = bloco_cda(saida)

    assert codigo == 4
    assert "Retrato: competencia 2026-10-27; leitura completa: sim" in saida
    assert bloco[0] == (
        "Investe em (CDA): competencia mais nova completa nenhuma; leitura "
        "completa: nao (motivo: status_nao_success); o detentor com competencia "
        "incompleta nao tem fechamento"
    )
    assert bloco[1].endswith("; em cda incompleto 1")
    assert "  criadas: 1" in bloco
    assert "Resultado: codigo 4" in saida


@pytest.mark.parametrize(("modo", "esperado"), [("id ocupado", 3), ("erro contado", 2)])
def test_ic2_precedencia_com_cda_incompleto(caminhos, tmp_path, monkeypatch, capsys, modo, esperado):
    parcial = banco_com_cda(tmp_path / "parcial", status="partial")

    if modo == "id ocupado":
        SQLiteEntityRepository(SQLiteConnectionManager(caminhos.destino)).save(
            Entity(
                entity_id=adaptador.entity_id(CNPJ_ADMIN),
                legal_name="OCUPANTE FICTICIO",
                entity_type=EntityType.OTHER,
                provenance=DataProvenance(
                    source_type=SourceType.MANUAL,
                    source_name="Teste ficticio",
                ),
            )
        )
        codigo = main(gravar(caminhos, fundos=parcial))
    else:
        falhar_invests_in(monkeypatch)
        codigo = main(gravar(caminhos, "--create", fundos=parcial))

    saida = capsys.readouterr().out

    assert codigo == esperado
    assert f"Resultado: codigo {esperado}" in saida


def test_ic3_aviso_de_invests_in_so_na_primeira_gravacao(caminhos, tmp_path, capsys):
    com_cda = banco_com_cda(tmp_path / "cda")

    main(argumentos(caminhos, fundos=com_cda))
    simulada = capsys.readouterr().out
    main(gravar(caminhos, "--create", fundos=com_cda))
    primeira = capsys.readouterr().out
    main(gravar(caminhos, fundos=com_cda))
    segunda = capsys.readouterr().out

    assert "Aviso: seria a primeira gravacao de invests_in neste banco" in simulada
    assert (
        "Aviso: primeira gravacao de invests_in neste banco; quem ler este banco "
        "precisa da main a partir de 0fb907f (#49)."
    ) in primeira
    assert "invests_in neste banco" not in segunda
    assert "  criadas: 1" in bloco_cda(primeira)
    assert "  mantidas: 1" in bloco_cda(segunda)


@pytest.mark.parametrize("modo", ["dry-run", "commit", "erro contado", "trava"])
def test_ic4_saida_com_cda_sem_cnpj_nome_caminho_nem_mensagem(
    caminhos, tmp_path, monkeypatch, capsys, modo
):
    com_cda = banco_com_cda(tmp_path / "cda")

    if modo == "erro contado":
        falhar_invests_in(monkeypatch)

    if modo == "trava":
        main(gravar(caminhos, "--create", fundos=com_cda))
        com_cda = banco_com_cda(tmp_path / "antigo", **CDA_SETEMBRO)
        capsys.readouterr()
        codigo = main(gravar(caminhos, fundos=com_cda))
    elif modo == "dry-run":
        codigo = main(argumentos(caminhos, fundos=com_cda))
    else:
        codigo = main(gravar(caminhos, "--create", fundos=com_cda))

    saida = capsys.readouterr().out
    proibidos = [
        *CNPJS_CDA,
        *(com_mascara(cnpj) for cnpj in CNPJS_CDA),
        "FICTICI",
        "FICT\xcdCI",
        str(tmp_path),
        str(caminhos.backups),
        str(caminhos.destino),
        "falha ficticia",
    ]

    assert codigo == {"dry-run": 0, "commit": 0, "erro contado": 2, "trava": 2}[modo]
    assert ("  investe em criar RuntimeError: 1" in saida) is (modo == "erro contado")

    for proibido in proibidos:
        assert proibido not in saida


def test_ic6_dry_run_com_cda_nao_altera_o_destino_nem_o_banco_de_fundos(caminhos, tmp_path, capsys):
    com_cda = banco_com_cda(tmp_path / "cda")
    criar_destino(caminhos, capsys)
    destino_antes = sha256_of(caminhos.destino)
    fundos_antes = sha256_of(com_cda)

    codigo = main(argumentos(caminhos, fundos=com_cda))
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "  criadas: 1" in bloco_cda(saida)
    assert "Aviso: seria a primeira gravacao de invests_in neste banco" in saida
    assert "Nada foi gravado no destino; a copia descartavel foi removida." in saida
    assert sha256_of(caminhos.destino) == destino_antes
    assert sha256_of(com_cda) == fundos_antes


def test_ic7_cda_mais_antigo_no_commit_aborta_sem_gravar(caminhos, tmp_path, capsys):
    main(gravar(caminhos, "--create", fundos=banco_com_cda(tmp_path / "cda")))
    capsys.readouterr()
    antes = linhas(caminhos.destino)
    antigo = banco_com_cda(tmp_path / "antigo", **CDA_SETEMBRO)

    codigo = main(gravar(caminhos, fundos=antigo))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert CDA_MAIS_ANTIGO in saida
    assert linhas(caminhos.destino) == antes
    assert len(list(caminhos.backups.iterdir())) == 1


@pytest.mark.parametrize(
    ("modo", "excecao"),
    [("sem 004", "CdaUnavailableButApplied"), ("sem posicao", "CdaOlderThanApplied")],
)
def test_ic7_sem_cda_ou_sem_posicao_com_cda_aplicado_aborta(caminhos, tmp_path, capsys, modo, excecao):
    main(gravar(caminhos, "--create", fundos=banco_com_cda(tmp_path / "cda")))
    capsys.readouterr()
    antes = linhas(caminhos.destino)
    fundos = (
        caminhos.fundos
        if modo == "sem 004"
        else banco_com_cda(tmp_path / "vazio", posicao=False)
    )

    codigo = main(argumentos(caminhos, fundos=fundos))
    saida = capsys.readouterr().out

    assert codigo == 2
    assert f"Erro: {excecao}; nenhum dado foi gravado." in saida
    assert "o backup feito antes" not in saida
    assert linhas(caminhos.destino) == antes


def test_ic7_aplicado_de_competencia_incompleta_a_reexecucao_passa(caminhos, tmp_path, capsys):
    parcial = banco_com_cda(tmp_path / "parcial", status="partial")

    primeira = main(gravar(caminhos, "--create", fundos=parcial))
    capsys.readouterr()
    segunda = main(gravar(caminhos, fundos=parcial))
    saida = capsys.readouterr().out

    assert (primeira, segunda) == (4, 4)
    assert "CdaOlderThanApplied" not in saida
    assert "  mantidas: 1" in bloco_cda(saida)
