"""Testes da competencia ja aplicada no destino (trava B6, FU7.2).

O destino e um SQLite da camada em tmp_path. O teste de contrato grava pela
camada (SQLiteEntityRepository) a entidade que o adaptador de Fundos monta e
le o texto cru da data: quebra se a tabela, a coluna, o nome da fonte ou o
formato mudarem. So CNPJs ficticios de cnpj_amostras.
"""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityStatus,
    EntityType,
    IdentifierType,
    SourceType,
)
from pense_alm.shared.integration.fundos_adapter import NORMAL, FundosAdapter
from pense_alm.shared.integration.fundos_records import (
    CadastroSnapshot,
    FundosSubjectRecord,
)
from pense_alm.shared.integration.fundos_target_state import (
    FundosTargetState,
    FundosTargetStateError,
)
from pense_alm.shared.persistence import SQLiteConnectionManager, SQLiteEntityRepository
from pense_alm.shared.persistence import SQLiteRelationshipRepository

from ..cnpj_amostras import cnpj_ficticio


INICIO = datetime(2026, 10, 27, 12, tzinfo=UTC)
CADASTRO = "Fundos - CVM Cadastro"


@pytest.fixture
def destino(tmp_path):
    manager = SQLiteConnectionManager(tmp_path / "destino" / "camada.sqlite3")
    return manager, SQLiteEntityRepository(manager)


def gravar(repositorio, n, reference_date, source_type=SourceType.CVM, source_name=CADASTRO):
    """Entidade ficticia com a proveniencia pedida (grava uma linha em data_provenance)."""

    proveniencia = DataProvenance(
        source_type=source_type,
        source_name=source_name,
        source_reference=f"fundos:funds:{n}",
        collected_at=INICIO,
        reference_date=reference_date,
    )
    repositorio.save(
        Entity(
            legal_name="FUNDO FICTÍCIO " + str(n),
            entity_type=EntityType.FIDC,
            status=EntityStatus.ACTIVE,
            provenance=proveniencia,
            identifiers=(
                EntityIdentifier(
                    identifier_type=IdentifierType.CNPJ,
                    value=cnpj_ficticio(n),
                    provenance=proveniencia,
                    is_primary=True,
                ),
            ),
            created_at=INICIO,
            updated_at=INICIO,
        )
    )


def meia_noite(ano, mes, dia):
    return datetime(ano, mes, dia, tzinfo=UTC)


def test_contrato_grava_pela_camada_e_le_o_texto_cru(destino):
    manager, repositorio = destino
    subject = FundosSubjectRecord(
        cnpj=cnpj_ficticio(1),
        source_table="funds",
        source_id=1,
        names=("FUNDO FICTÍCIO",),
        situacoes=(NORMAL,),
        tipos_fundo=("FIDC",),
        tipos_classe=(),
        tipos_pessoa_gestor=("PJ",),
        parties=(),
    )
    snapshot = CadastroSnapshot(
        reference_date=date(2026, 10, 27),
        collection_run_id=1,
        started_at=INICIO,
        complete=True,
        funds_in_table=1,
        classes_in_table=0,
        funds_read=1,
        classes_read=0,
        classes_same_cnpj=0,
        classes_other_fund_cnpj=0,
        classes_only_class=0,
        classes_of_fund_without_data=0,
        subjects=(subject,),
    )
    repositorio.save(FundosAdapter().to_fund_entity(subject, snapshot))

    with manager.read_connection() as conexao:
        textos = [
            linha[0]
            for linha in conexao.execute(
                "SELECT reference_date FROM data_provenance"
                " WHERE source_type = 'cvm' AND source_name = ?",
                (CADASTRO,),
            )
        ]

    assert textos == ["2026-10-27T00:00:00+00:00"]
    assert FundosTargetState(manager).latest_applied_reference() == meia_noite(2026, 10, 27)


def test_destino_vazio_da_none(destino):
    manager, _ = destino

    assert FundosTargetState(manager).latest_applied_reference() is None


def test_vale_a_maior_de_duas_datas(destino):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 9, 30))
    gravar(repositorio, 2, meia_noite(2026, 10, 27))

    assert FundosTargetState(manager).latest_applied_reference() == meia_noite(2026, 10, 27)


def test_outras_fontes_sao_ignoradas(destino):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 9, 30))
    gravar(repositorio, 2, meia_noite(2026, 12, 31), source_type=SourceType.MANUAL)
    gravar(repositorio, 3, meia_noite(2026, 12, 31), source_name="Fundos - CVM CDA")

    assert FundosTargetState(manager).latest_applied_reference() == meia_noite(2026, 9, 30)


@pytest.mark.parametrize(
    "reference_date",
    [
        datetime(2026, 10, 27, 3, tzinfo=UTC),
        datetime(2026, 10, 27, tzinfo=timezone(timedelta(hours=-3))),
        None,
    ],
)
def test_formato_inesperado_ou_data_nula_da_erro_sem_dado(destino, reference_date):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 9, 30))
    gravar(repositorio, 2, reference_date)

    with pytest.raises(FundosTargetStateError) as erro:
        FundosTargetState(manager).latest_applied_reference()

    assert "2026" not in str(erro.value)
    assert cnpj_ficticio(2) not in str(erro.value)


def test_formato_inesperado_de_outra_fonte_nao_conta(destino):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 9, 30))
    gravar(
        repositorio,
        2,
        datetime(2026, 10, 27, 3, tzinfo=UTC),
        source_type=SourceType.MANUAL,
    )

    assert FundosTargetState(manager).latest_applied_reference() == meia_noite(2026, 9, 30)


def test_manager_de_tipo_errado_e_recusado(tmp_path):
    with pytest.raises(TypeError):
        FundosTargetState(tmp_path / "camada.sqlite3")


# --- PR C2: competencia do CDA ja aplicada (trava do CDA) ---


CDA = "Fundos - CVM CDA"
INICIO_CDA = datetime(2026, 11, 28, 12, tzinfo=UTC)


def test_contrato_da_invests_in_grava_pela_camada_e_le_o_texto_cru(destino):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 10, 27))
    gravar(repositorio, 2, meia_noite(2026, 10, 27))
    origem, alvo = (
        repositorio.get_by_identifier(IdentifierType.CNPJ, cnpj_ficticio(n)) for n in (1, 2)
    )
    adaptador = FundosAdapter()
    competencia = date(2026, 10, 31)
    SQLiteRelationshipRepository(manager).save(
        adaptador.build_investment(
            origem.entity_id,
            alvo.entity_id,
            adaptador.holding_provenance(competencia, INICIO_CDA, 7),
            competencia,
            INICIO_CDA,
        )
    )

    with manager.read_connection() as conexao:
        textos = [
            linha[0]
            for linha in conexao.execute(
                "SELECT reference_date FROM data_provenance"
                " WHERE source_type = 'cvm' AND source_name = ?",
                (CDA,),
            )
        ]

    estado = FundosTargetState(manager)
    assert textos == ["2026-10-31T00:00:00+00:00"]
    assert estado.latest_applied_cda_reference() == meia_noite(2026, 10, 31)
    assert estado.latest_applied_reference() == meia_noite(2026, 10, 27)


def test_cda_destino_vazio_da_none(destino):
    manager, _ = destino

    assert FundosTargetState(manager).latest_applied_cda_reference() is None


def test_cda_vale_a_maior_de_duas_datas(destino):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 10, 31), source_name=CDA)
    gravar(repositorio, 2, meia_noite(2026, 9, 30), source_name=CDA)

    assert FundosTargetState(manager).latest_applied_cda_reference() == meia_noite(2026, 10, 31)


def test_cadastro_e_cda_nao_se_misturam(destino):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 12, 31))
    gravar(repositorio, 2, meia_noite(2026, 9, 30), source_name=CDA)
    gravar(repositorio, 3, meia_noite(2026, 12, 31), source_type=SourceType.MANUAL, source_name=CDA)
    estado = FundosTargetState(manager)

    assert estado.latest_applied_cda_reference() == meia_noite(2026, 9, 30)
    assert estado.latest_applied_reference() == meia_noite(2026, 12, 31)


@pytest.mark.parametrize("reference_date", [datetime(2026, 10, 31, 3, tzinfo=UTC), None])
def test_cda_formato_inesperado_da_erro_sem_dado(destino, reference_date):
    manager, repositorio = destino
    gravar(repositorio, 1, meia_noite(2026, 9, 30), source_name=CDA)
    gravar(repositorio, 2, reference_date, source_name=CDA)
    estado = FundosTargetState(manager)

    with pytest.raises(FundosTargetStateError, match="do CDA") as erro:
        estado.latest_applied_cda_reference()

    assert "2026" not in str(erro.value)
    assert cnpj_ficticio(2) not in str(erro.value)
    # A trava B6 nao le as linhas do CDA.
    assert estado.latest_applied_reference() is None
