from decimal import Decimal

import pytest

from apoio import T0
from apoio import T1
from apoio import T2
from apoio import fake_sha256
from apoio import make_test_cnpj
from fundos.personal_data import PersonalDataError
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.conflict_repository import ConflictRepository
from fundos.repositories.fund_class_repository import FundClassRepository
from fundos.repositories.fund_repository import FundRepository
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


FIELD = "tab_IV.TAB_IV_A_VL_PL"


class Context:
    """Fontes, coletas, manifestos, um fundo e uma classe ficticios."""

    def __init__(self, connection):
        self.connection = connection
        self.observations = ObservationRepository(connection)
        self.conflicts = ConflictRepository(connection)
        sources = SourceRepository(connection)
        self.cvm = sources.get_by_code("CVM_DADOS_ABERTOS").id
        self.manual = sources.get_by_code("MANUAL").id
        runs = CollectionRunRepository(connection)
        self.cvm_run = runs.start(self.cvm, started_at=T0).id
        self.manual_run = runs.start(self.manual, started_at=T0).id
        self.cvm_raw = self.raw(self.cvm, self.cvm_run, "cvm", T0)
        self.manual_raw = self.raw(self.manual, self.manual_run, "manual", T0)
        fund, _ = FundRepository(connection).get_or_create(make_test_cnpj(1))
        fund_class, _ = FundClassRepository(connection).get_or_create(
            make_test_cnpj(1),
            fund.id,
        )
        self.fund = fund.id
        self.fund_class = fund_class.id

    def raw(self, source, run, label, collected_at):
        record, _ = RawRecordRepository(self.connection).register_file(
            source_id=source,
            collection_run_id=run,
            file_name=label + "_ficticio.zip",
            size_bytes=100,
            sha256=fake_sha256(label),
            collected_at=collected_at,
        )
        return record.id

    def record(self, value, source="cvm", raw=None, **overrides):
        arguments = {
            "fund_class_id": self.fund_class,
            "source_id": getattr(self, source),
            "collection_run_id": getattr(self, source + "_run"),
            "raw_record_id": raw or getattr(self, source + "_raw"),
            "field_name": FIELD,
            "value_type": "numeric",
            "value": value,
            "reference_date": "2026-09-30",
        }
        arguments.update(overrides)
        return self.observations.record(**arguments)

    def count(self, table="observations"):
        return self.connection.execute(
            "SELECT COUNT(*) FROM " + table
        ).fetchone()[0]


@pytest.fixture
def ctx(connection):
    return Context(connection)


def test_records_with_full_provenance(ctx):
    result = ctx.record("1460.23387")
    observation = result.observation

    assert result.created and result.conflicts == ()
    assert observation.value == Decimal("1460.23387")
    assert observation.value_numeric == "1460.23387"
    assert (observation.source_id, observation.collection_run_id, observation.raw_record_id) == (
        ctx.cvm,
        ctx.cvm_run,
        ctx.cvm_raw,
    )
    assert (observation.reference_date, observation.collected_at) == ("2026-09-30", T0)
    assert observation.field_name == FIELD


def test_same_value_from_another_collection_is_not_duplicated(ctx):
    first = ctx.record("10.50").observation
    new_run = CollectionRunRepository(ctx.connection).start(ctx.cvm, started_at=T1).id
    new_raw = ctx.raw(ctx.cvm, new_run, "cvm-semana-seguinte", T1)

    again = ctx.record("10.5", collection_run_id=new_run, raw=new_raw)

    assert not again.created
    assert again.observation.id == first.id
    assert ctx.count() == 1


def test_another_reference_date_is_a_new_row_without_conflict(ctx):
    ctx.record("10", reference_date="2026-08-31")
    result = ctx.record("10", reference_date="2026-09-30")

    assert result.created and result.conflicts == ()
    assert ctx.count() == 2
    assert ctx.count("data_conflicts") == 0


def test_resubmission_in_the_same_source_opens_a_conflict_and_keeps_the_old_row(ctx):
    original = ctx.record("10").observation
    later_raw = ctx.raw(ctx.cvm, ctx.cvm_run, "cvm-reapresentado", T1)

    result = ctx.record("11", raw=later_raw)

    assert result.created
    assert [(c.observation_a_id, c.observation_b_id, c.status) for c in result.conflicts] == [
        (original.id, result.observation.id, "open")
    ]
    assert ctx.observations.get_by_id(original.id) == original
    assert ctx.observations.get_current(fund_class_id=ctx.fund_class, field_name=FIELD).id == result.observation.id


def test_divergence_between_sources_opens_a_conflict(ctx):
    ctx.record("10")
    agreeing = ctx.record("10", source="manual")
    diverging = ctx.record("12", source="manual", reference_date="2026-09-30", unit="BRL")

    assert agreeing.conflicts == ()
    assert len(diverging.conflicts) == 2
    assert ctx.conflicts.count(status="open") == 2


def test_third_value_conflicts_with_both_previous_without_duplicates(ctx):
    a = ctx.record("1").observation
    b = ctx.record("2", raw=ctx.raw(ctx.cvm, ctx.cvm_run, "v2", T1)).observation
    c = ctx.record("3", raw=ctx.raw(ctx.cvm, ctx.cvm_run, "v3", T2))

    pairs = {(x.observation_a_id, x.observation_b_id) for x in ctx.conflicts.list_open()}

    assert pairs == {(a.id, b.id), (a.id, c.observation.id), (b.id, c.observation.id)}
    assert not ctx.record("3").created
    assert ctx.conflicts.count() == 3


def test_returning_to_an_old_value_creates_no_row_and_keeps_the_conflict(ctx):
    # Limitacao documentada: A, depois B, depois A de novo.
    a = ctx.record("1").observation
    b = ctx.record("2", raw=ctx.raw(ctx.cvm, ctx.cvm_run, "v2", T1)).observation
    back = ctx.record("1", raw=ctx.raw(ctx.cvm, ctx.cvm_run, "v3", T2))

    assert not back.created
    assert back.observation.id == a.id
    assert ctx.conflicts.count(status="open") == 1
    assert ctx.observations.get_current(fund_class_id=ctx.fund_class, field_name=FIELD).id == b.id


def collection(ctx, label, started_at):
    """Coleta e manifesto novos da CVM (outra semana do mesmo ZIP)."""

    run = CollectionRunRepository(ctx.connection).start(ctx.cvm, started_at=started_at).id
    return {"collection_run_id": run, "raw": ctx.raw(ctx.cvm, run, label, started_at)}


def test_checksum_of_existing_rows_is_the_same_as_before_fu42():
    # Hex calculado pelo codigo da main (5a4226f), com os mesmos dados.
    pl = ObservationRepository.checksum(
        "fund_class_id", 7, 1, "tab_IV.TAB_IV_A_VL_PL", "2026-09-30", "numeric", "1000.5", None,
    )
    quota = ObservationRepository.checksum(
        "quota_series_id", 3, 1, "tab_X_2.TAB_X_VL_COTA", "2026-09-30", "numeric", "1.234567", "BRL",
    )
    restated = ObservationRepository.checksum(
        "fund_class_id", 7, 1, "tab_IV.TAB_IV_A_VL_PL", "2026-09-30", "numeric", "1000.5", None,
        restated_in_run=4,
    )

    assert pl == "c5cf43842f48ece61892a0f2df5a5e3764afb98093bc7601c87d262fbe389e41"
    assert quota == "a69fa9c377a63989176a8927d1e9af91218d57ffadccbc8cb5dd7dcce6eefffb"
    assert restated != pl


def test_value_that_returns_is_restated_and_becomes_current(ctx):
    a = ctx.record("1").observation
    b = ctx.record("2", **collection(ctx, "v2", T1)).observation
    back = ctx.record("1", restatement=True, **collection(ctx, "v3", T2))

    assert back.created
    assert back.conflicts == ()
    assert back.observation.id not in (a.id, b.id)
    assert back.observation.value_numeric == "1"
    assert back.observation.checksum != a.checksum
    assert back.observation.collected_at == T2
    assert ctx.observations.get_current(fund_class_id=ctx.fund_class, field_name=FIELD).id == back.observation.id
    assert ctx.conflicts.count() == 1
    assert ctx.observations.get_by_id(a.id) == a


def test_value_that_returns_again_keeps_a_single_conflict(ctx):
    ctx.record("1")
    b = ctx.record("2", **collection(ctx, "v2", T1)).observation
    ctx.record("1", restatement=True, **collection(ctx, "v3", T2))
    again = ctx.record("2", restatement=True, **collection(ctx, "v4", "2026-10-27T16:00:00+00:00"))

    assert again.created and again.conflicts == ()
    assert again.observation.id != b.id
    assert ctx.count() == 4
    assert ctx.conflicts.count() == 1
    assert ctx.observations.get_current(fund_class_id=ctx.fund_class, field_name=FIELD).id == again.observation.id


def test_restatement_in_the_same_collection_is_idempotent(ctx):
    ctx.record("1")
    ctx.record("2", **collection(ctx, "v2", T1))
    third = collection(ctx, "v3", T2)
    first = ctx.record("1", restatement=True, **third)
    second = ctx.record("1", restatement=True, **third)

    assert not second.created
    assert second.observation.id == first.observation.id
    assert ctx.count() == 3


def test_restatement_needs_the_value_already_recorded(ctx):
    ctx.record("1")

    with pytest.raises(ValueError, match="Linha reapresentada"):
        ctx.record("2", restatement=True, **collection(ctx, "v2", T1))

    assert ctx.count() == 1
    assert ctx.count("data_conflicts") == 0


@pytest.mark.parametrize(
    "value_type, value",
    [("numeric", None), ("text", ""), ("text", "   "), ("text", None), ("date", None)],
)
def test_absent_value_is_not_recorded(ctx, value_type, value):
    with pytest.raises(ValueError, match="ausente"):
        ctx.record(value, value_type=value_type, field_name="registro_classe.Situacao")

    assert ctx.count() == 0


@pytest.mark.parametrize("value", ["1,5", "1e5", "NaN", float("inf"), True, "1.234.567"])
def test_invalid_numeric_values_are_refused(ctx, value):
    with pytest.raises(ValueError):
        ctx.record(value)


def test_field_name_is_table_dot_column_with_case_preserved(ctx):
    result = ctx.record("Em Funcionamento Normal", value_type="text", field_name="registro_classe.Situacao")

    assert result.observation.field_name == "registro_classe.Situacao"

    for bad in ("TAB_IV_A_VL_PL", "tab IV.X", "tab_IV.VL_Ç", "a.b.c"):
        with pytest.raises(ValueError, match="tabela.coluna"):
            ctx.record("1", field_name=bad)


def test_text_is_stored_exactly_as_received(ctx):
    original = "Subclasse Senior Série 1 |"

    result = ctx.record(original, value_type="text", field_name="tab_X_2.TAB_X_CLASSE_SERIE")

    assert result.observation.value_text == original


def test_collection_and_manifest_must_belong_to_the_source(ctx):
    with pytest.raises(ValueError, match="coleta informada e de outra fonte"):
        ctx.record("1", collection_run_id=ctx.manual_run)

    with pytest.raises(ValueError, match="manifesto informado e de outra fonte"):
        ctx.record("1", raw=ctx.manual_raw)

    with pytest.raises(ValueError, match="exatamente um assunto"):
        ctx.record("1", fund_id=ctx.fund)

    with pytest.raises(ValueError, match="assunto informado nao existe"):
        ctx.record("1", fund_class_id=999)

    assert ctx.count() == 0


def test_failure_while_opening_conflicts_rolls_back_the_observation(ctx, monkeypatch):
    ctx.record("10")

    def broken(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(ObservationRepository, "_open_conflicts", broken)

    with pytest.raises(RuntimeError, match="falha simulada"):
        ctx.record("11")

    assert ctx.count() == 1
    assert ctx.count("data_conflicts") == 0


def test_personal_data_is_refused_before_any_write(ctx):
    with pytest.raises(PersonalDataError):
        ctx.record("Nome Generico", value_type="text", field_name="registro_fundo.Diretor")

    with pytest.raises(PersonalDataError):
        ctx.record("99999999999", value_type="text", field_name="registro_fundo.CPF_CNPJ_Gestor")

    assert ctx.count() == 0


def test_history_and_current_values(ctx):
    older = ctx.record("10", reference_date="2026-08-31").observation
    newer = ctx.record("20", reference_date="2026-09-30").observation
    status = ctx.record("Em Funcionamento Normal", value_type="text", field_name="registro_classe.Situacao").observation

    history = ctx.observations.list_history(fund_class_id=ctx.fund_class, field_name=FIELD)
    current = ctx.observations.list_current(fund_class_id=ctx.fund_class)

    assert [o.id for o in history] == [newer.id, older.id]
    assert [o.id for o in current] == [status.id, newer.id]
    assert ctx.observations.get_current(fund_id=ctx.fund, field_name=FIELD) is None
