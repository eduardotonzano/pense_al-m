import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio import T1
from apoio import fake_sha256
from apoio import make_test_cnpj
from apoio import seed_base
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_schema
from fundos.personal_data import PersonalDataError
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.raw_record_repository import RawRecordRepository


MIGRATION_002 = MIGRATIONS_DIR / "002_party_observations.sql"


class Context:
    """Base ficticia com as migrations e o repositorio de papeis."""

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


CEDENTE_FIELD = "tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1"
SHARE_FIELD = "tab_I.TAB_I2A12_PR_CEDENTE_1"


def cedente(ctx, **overrides):
    arguments = {
        "fund_id": None,
        "fund_class_id": ctx.base["fund_class"],
        "role": "cedente",
        "field_name": CEDENTE_FIELD,
        "name_field_name": None,
        "party_name": None,
        "share_field_name": SHARE_FIELD,
        "share_value": "37.125",
        "reference_date": "2026-09-30",
    }
    arguments.update(overrides)
    return ctx.record(**arguments)


def test_checksum_without_share_is_the_same_as_before_migration_003():
    # Hex calculado pelo codigo anterior a migration 003, com os mesmos dados.
    admin = PartyObservationRepository.checksum(
        "fund_class_id", 7, 1, "administrador", "tab_I.CNPJ_ADMIN", make_test_cnpj(2),
        "tab_I.ADMIN", "Administradora Ficticia SA", "2026-09-30",
    )
    without_share = PartyObservationRepository.checksum(
        "fund_id", 3, 1, "cedente", CEDENTE_FIELD, make_test_cnpj(2), None, None, "2026-09-30",
    )
    with_share = PartyObservationRepository.checksum(
        "fund_id", 3, 1, "cedente", CEDENTE_FIELD, make_test_cnpj(2), None, None, "2026-09-30",
        SHARE_FIELD, "37.125",
    )

    assert admin == "655f00b693332dcdf23752dbdf81b22ddea5d019046a7a37f54a93937feea753"
    assert without_share == "d2bcc4eedd425ac50bdd6661943ae51951dfeded691a9b5318dc53890cc5cf2e"
    assert with_share != without_share


def test_cedente_with_share_is_recorded_and_read_back(ctx):
    result = cedente(ctx, share_value="17521903.58")
    party = result.party

    assert result.created
    assert (party.role, party.field_name, party.party_cnpj) == ("cedente", CEDENTE_FIELD, make_test_cnpj(2))
    assert (party.name_field_name, party.party_name) == (None, None)
    assert (party.share_field_name, party.share_value) == (SHARE_FIELD, "17521903.58")
    assert ctx.parties.get_by_id(party.id) == party
    assert ctx.parties.list_by_subject(fund_class_id=ctx.base["fund_class"], role="cedente") == [party]
    assert ctx.count("party_observation_shares") == 1


def test_share_is_stored_in_canonical_form(ctx):
    party = cedente(ctx, share_value=" 037.1250 ").party

    assert party.share_value == "37.125"


def test_cedente_without_share(ctx):
    party = cedente(ctx, share_field_name=None, share_value=None).party

    assert (party.share_field_name, party.share_value) == (None, None)
    assert ctx.count("party_observation_shares") == 0


def test_same_share_is_idempotent(ctx):
    first = cedente(ctx)
    second = cedente(ctx, raw_record_id=ctx.raw("outro"))

    assert not second.created
    assert second.party == first.party
    assert (ctx.count(), ctx.count("party_observation_shares")) == (1, 1)


def test_other_share_for_the_same_key_opens_a_conflict_and_keeps_both(ctx):
    first = cedente(ctx)
    second = cedente(ctx, share_value="40", raw_record_id=ctx.raw("reapresentacao"))

    assert second.created
    assert [(c.party_observation_a_id, c.party_observation_b_id) for c in second.conflicts] == [
        (first.party.id, second.party.id)
    ]
    assert second.conflicts[0].field_name == CEDENTE_FIELD
    assert (ctx.count(), ctx.count("party_observation_shares")) == (2, 2)


def test_share_and_no_share_for_the_same_key_open_a_conflict(ctx):
    cedente(ctx, share_field_name=None, share_value=None)
    second = cedente(ctx, raw_record_id=ctx.raw("reapresentacao"))

    assert second.created
    assert len(second.conflicts) == 1


def test_same_cnpj_in_other_position_or_group_is_another_key(ctx):
    cedente(ctx)
    cedente(ctx, field_name="tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_2", share_field_name="tab_I.TAB_I2A12_PR_CEDENTE_2")
    cedente(ctx, field_name="tab_I.TAB_I2B12_CPF_CNPJ_CEDENTE_1", share_field_name="tab_I.TAB_I2B12_PR_CEDENTE_1")

    assert ctx.count() == 3
    assert ctx.count("party_conflicts") == 0


@pytest.mark.parametrize(
    "changes, error",
    [
        ({"role": "gestor", "field_name": "registro_fundo.CPF_CNPJ_Gestor"}, ValueError),
        ({"name_field_name": "tab_I.ADMIN", "party_name": "Nome Ficticio"}, ValueError),
        ({"share_field_name": None}, ValueError),
        ({"share_value": None}, ValueError),
        ({"share_field_name": "PR_CEDENTE_1"}, ValueError),
        ({"share_field_name": CEDENTE_FIELD}, PersonalDataError),
        ({"share_field_name": "registro_fundo.Diretor"}, PersonalDataError),
        ({"share_value": "1e3"}, ValueError),
        ({"share_value": "abc"}, ValueError),
    ],
)
def test_invalid_shares_write_nothing(ctx, changes, error):
    with pytest.raises(error) as raised:
        cedente(ctx, **changes)

    assert "1e3" not in str(raised.value)
    assert (ctx.count(), ctx.count("party_observation_shares")) == (0, 0)


def test_database_without_migration_003(tmp_path):
    db = create_schema(tmp_path / "fundos.db", (MIGRATION_001, MIGRATION_002))

    with db.connection() as connection:
        context = Context(connection)

        assert not context.parties.has_shares

        party = context.record().party

        assert (party.share_field_name, party.share_value) == (None, None)
        assert context.parties.list_by_subject(fund_id=context.base["fund"]) == [party]

        with pytest.raises(ValueError, match="migration 003"):
            cedente(context)

        assert context.count() == 1
