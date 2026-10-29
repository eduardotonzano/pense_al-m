import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio import T1
from apoio import fake_sha256
from apoio import make_test_cnpj
from apoio import seed_base
from fundos.personal_data import PersonalDataError
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.raw_record_repository import RawRecordRepository


class Context:
    """Base ficticia com a migration 002 e o repositorio de papeis."""

    def __init__(self, connection):
        self.connection = connection
        self.base = seed_base(connection)
        self.parties = PartyObservationRepository(connection)

    def raw(self, label):
        record, _ = RawRecordRepository(self.connection).register_file(
            source_id=self.base["cvm"],
            collection_run_id=self.base["cvm_run"],
            file_name=label + "_ficticio.zip",
            size_bytes=100,
            sha256=fake_sha256(label),
            collected_at=T1,
        )
        return record.id

    def record(self, **overrides):
        arguments = {
            "fund_id": self.base["fund"],
            "role": "gestor",
            "field_name": "registro_fundo.CPF_CNPJ_Gestor",
            "party_cnpj": make_test_cnpj(2),
            "name_field_name": "registro_fundo.Gestor",
            "party_name": "Gestora Ficticia Ltda",
            "source_id": self.base["cvm"],
            "collection_run_id": self.base["cvm_run"],
            "raw_record_id": self.base["cvm_raw"],
            "reference_date": "2026-10-27",
        }
        arguments.update(overrides)
        return self.parties.record(**arguments)

    def count(self, table="party_observations"):
        return self.connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


@pytest.fixture
def ctx(full_connection):
    return Context(full_connection)


def test_records_with_provenance(ctx):
    result = ctx.record()
    party = result.party

    assert result.created
    assert result.conflicts == ()
    assert (party.fund_id, party.fund_class_id) == (ctx.base["fund"], None)
    assert (party.role, party.party_cnpj, party.party_name) == (
        "gestor",
        make_test_cnpj(2),
        "Gestora Ficticia Ltda",
    )
    assert party.raw_record_id == ctx.base["cvm_raw"]
    assert party.collected_at == "2026-10-27T13:00:00.000000+00:00"


def test_recording_twice_is_idempotent(ctx):
    first = ctx.record()
    second = ctx.record(raw_record_id=ctx.raw("outro"))

    assert not second.created
    assert second.party.id == first.party.id
    assert ctx.count() == 1


def test_several_parties_with_the_same_role_open_no_conflict(ctx):
    ctx.record()
    ctx.record(party_cnpj=make_test_cnpj(3), party_name="Outra Gestora Ficticia")

    assert ctx.count() == 2
    assert ctx.count("party_conflicts") == 0
    assert ctx.count("data_conflicts") == 0


def test_other_name_for_the_same_key_opens_a_conflict_and_keeps_both(ctx):
    first = ctx.record()
    second = ctx.record(party_name="Gestora Ficticia Renomeada", raw_record_id=ctx.raw("reapresentacao"))

    assert second.created
    assert len(second.conflicts) == 1
    conflict = second.conflicts[0]
    assert (conflict.party_observation_a_id, conflict.party_observation_b_id) == (
        first.party.id,
        second.party.id,
    )
    assert conflict.status == "open"
    assert ctx.count() == 2
    assert len(ctx.parties.list_open_conflicts()) == 1


def test_other_reference_date_is_history_not_conflict(ctx):
    ctx.record()
    ctx.record(party_name="Gestora Ficticia Renomeada", reference_date="2026-10-28")

    assert ctx.count() == 2
    assert ctx.count("party_conflicts") == 0


def test_party_that_disappears_in_the_same_reference_date_opens_no_conflict(ctx):
    # Limitacao conhecida: as linhas da mesma competencia se somam.
    ctx.record()
    ctx.record(
        party_cnpj=make_test_cnpj(3),
        party_name="Outra Gestora Ficticia",
        raw_record_id=ctx.raw("reapresentacao"),
    )

    assert ctx.count() == 2
    assert ctx.count("party_conflicts") == 0


def test_identifier_without_name(ctx):
    party = ctx.record(name_field_name=None, party_name=None).party

    assert (party.name_field_name, party.party_name) == (None, None)


def test_class_subject(ctx):
    party = ctx.record(
        fund_id=None,
        fund_class_id=ctx.base["fund_class"],
        role="custodiante",
        field_name="registro_classe.CNPJ_Custodiante",
        name_field_name="registro_classe.Custodiante",
        party_name="Custodiante Ficticio SA",
    ).party

    assert ctx.parties.list_by_subject(fund_class_id=ctx.base["fund_class"]) == [party]


@pytest.mark.parametrize("value", [FAKE_CPF, FAKE_CPF_MASKED])
def test_cpf_is_refused_before_any_sql(ctx, value):
    with pytest.raises(PersonalDataError, match="formato de CPF") as error:
        ctx.record(party_cnpj=value)

    assert value not in str(error.value)
    assert ctx.count() == 0


def test_cnpj_with_wrong_dv_is_refused(ctx):
    cnpj = make_test_cnpj(2)
    wrong = cnpj[:12] + ("00" if cnpj[12:] != "00" else "11")

    with pytest.raises(PersonalDataError):
        ctx.record(party_cnpj=wrong)

    assert ctx.count() == 0


@pytest.mark.parametrize(
    "changes, error",
    [
        ({"name_field_name": "registro_fundo.Diretor"}, PersonalDataError),
        ({"name_field_name": "registro_fundo.CPF_CNPJ_Gestor"}, PersonalDataError),
        ({"name_field_name": None}, ValueError),
        ({"party_name": "  "}, ValueError),
        ({"field_name": "Gestor"}, ValueError),
        ({"role": "diretor"}, ValueError),
        ({"fund_class_id": 1}, ValueError),
    ],
)
def test_invalid_arguments_write_nothing(ctx, changes, error):
    with pytest.raises(error):
        ctx.record(**changes)

    assert ctx.count() == 0
