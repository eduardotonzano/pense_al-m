import pathlib
from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal

import pytest

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import (
    DebentureRepository,
)
from debenture_search.repositories.observation_repository import (
    ObservationRecord,
    ObservationRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def repositories(tmp_path):
    database_path = tmp_path / "observation_repository.db"
    test_database = Database(database_path)

    migration_sql = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    with test_database.connection() as connection:
        connection.executescript(migration_sql)
        connection.commit()

    debenture_repository = DebentureRepository(
        test_database
    )

    observation_repository = ObservationRepository(
        test_database
    )

    debenture = debenture_repository.create(
        asset_code="TEST12",
        isin="BRTESTDBS001",
        status="active",
    )

    source_row = test_database.fetch_one(
        """
        SELECT id
        FROM sources
        WHERE code = ?
        """,
        ("SND",),
    )

    manual_source_row = test_database.fetch_one(
        """
        SELECT id
        FROM sources
        WHERE code = ?
        """,
        ("MANUAL",),
    )

    return {
        "database": test_database,
        "debenture": debenture,
        "snd_source_id": int(source_row["id"]),
        "manual_source_id": int(
            manual_source_row["id"]
        ),
        "observations": observation_repository,
    }


def test_create_text_observation(repositories):
    repository = repositories["observations"]

    observation, was_created = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="Rating",
        value_type="text",
        value="  AA-  ",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    assert was_created is True
    assert isinstance(observation, ObservationRecord)
    assert observation.field_name == "rating"
    assert observation.value_type == "text"
    assert observation.value == "AA-"
    assert len(observation.checksum) == 64


def test_create_numeric_observation(repositories):
    repository = repositories["observations"]

    observation, was_created = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="spread",
        value_type="numeric",
        value="2.3500",
        unit="percentual",
        observed_at="2026-09-10T12:01:00+00:00",
    )

    assert was_created is True
    assert Decimal(str(observation.value)) == Decimal(
        "2.35"
    )
    assert observation.unit == "percentual"


def test_create_date_observation(repositories):
    repository = repositories["observations"]

    observation, was_created = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="data de vencimento",
        value_type="date",
        value=date(2030, 8, 15),
        observed_at="2026-09-10T12:02:00+00:00",
    )

    assert was_created is True
    assert observation.field_name == "data_de_vencimento"
    assert observation.value == "2030-08-15"


def test_create_boolean_observation(repositories):
    repository = repositories["observations"]

    observation, was_created = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="incentivada",
        value_type="boolean",
        value="sim",
        observed_at="2026-09-10T12:03:00+00:00",
    )

    assert was_created is True
    assert observation.value is True
    assert observation.value_boolean == 1


def test_same_observation_is_idempotent(repositories):
    repository = repositories["observations"]
    parameters = {
        "debenture_id": repositories["debenture"].id,
        "source_id": repositories["snd_source_id"],
        "field_name": "rating",
        "value_type": "text",
        "value": "AA-",
        "observed_at": "2026-09-10T12:04:00+00:00",
    }

    first, first_created = repository.create(
        **parameters
    )
    second, second_created = repository.create(
        **parameters
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert first.checksum == second.checksum

    row = repositories["database"].fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM observations
        WHERE checksum = ?
        """,
        (first.checksum,),
    )

    assert int(row["total"]) == 1


def test_different_dates_preserve_history(repositories):
    repository = repositories["observations"]

    first, _ = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="rating",
        value_type="text",
        value="A+",
        observed_at="2026-09-01T12:00:00+00:00",
    )

    second, _ = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    assert first.id != second.id
    assert first.checksum != second.checksum

    row = repositories["database"].fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM observations
        WHERE debenture_id = ?
          AND field_name = ?
        """,
        (
            repositories["debenture"].id,
            "rating",
        ),
    )

    assert int(row["total"]) == 2


def test_get_by_id(repositories):
    repository = repositories["observations"]

    created, _ = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="indexador",
        value_type="text",
        value="CDI",
        observed_at="2026-09-10T12:05:00+00:00",
    )

    found = repository.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.value == "CDI"


def test_get_by_checksum(repositories):
    repository = repositories["observations"]

    created, _ = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="garantia",
        value_type="text",
        value="Quirografaria",
        observed_at="2026-09-10T12:06:00+00:00",
    )

    found = repository.get_by_checksum(
        created.checksum
    )

    assert found is not None
    assert found.id == created.id
    assert found.value == "Quirografaria"


def test_rejects_unknown_debenture(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="debenture informada nao existe",
    ):
        repository.create(
            debenture_id=999999,
            source_id=repositories["snd_source_id"],
            field_name="rating",
            value_type="text",
            value="AA-",
        )


def test_rejects_unknown_source(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="fonte informada nao existe",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=999999,
            field_name="rating",
            value_type="text",
            value="AA-",
        )


def test_rejects_unknown_raw_record(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="registro bruto informado nao existe",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            raw_record_id=999999,
            field_name="rating",
            value_type="text",
            value="AA-",
        )


def test_rejects_empty_field_name(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="nome do campo e obrigatorio",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="   ",
            value_type="text",
            value="AA-",
        )


def test_rejects_invalid_value_type(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="Tipo de valor invalido",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="rating",
            value_type="arquivo",
            value="AA-",
        )


def test_rejects_empty_text_value(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="valor textual nao pode ficar vazio",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="rating",
            value_type="text",
            value="   ",
        )


def test_rejects_invalid_numeric_value(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="Valor numerico invalido",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="spread",
            value_type="numeric",
            value="dois virgula cinco",
        )


def test_rejects_invalid_date_value(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="Valor de data invalido",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="vencimento",
            value_type="date",
            value="31/02/2030",
        )


def test_rejects_invalid_boolean_value(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="Valor booleano invalido",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="incentivada",
            value_type="boolean",
            value="talvez",
        )


def test_rejects_invalid_confidence(repositories):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="Nivel de confianca invalido",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="rating",
            value_type="text",
            value="AA-",
            confidence="inventado",
        )


def test_rejects_invalid_validity_interval(
    repositories,
):
    repository = repositories["observations"]

    with pytest.raises(
        ValueError,
        match="data final nao pode ser anterior",
    ):
        repository.create(
            debenture_id=repositories["debenture"].id,
            source_id=repositories["snd_source_id"],
            field_name="rating",
            value_type="text",
            value="AA-",
            valid_from="2026-09-10T12:00:00+00:00",
            valid_until="2026-09-01T12:00:00+00:00",
        )


def test_manual_source_and_confidence(repositories):
    repository = repositories["observations"]

    observation, was_created = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["manual_source_id"],
        field_name="rating",
        value_type="text",
        value="AA-",
        confidence="manual",
        observed_at="2026-09-10T12:07:00+00:00",
    )

    assert was_created is True
    assert observation.confidence == "manual"
    assert observation.source_id == repositories[
        "manual_source_id"
    ]


def test_datetime_object_is_accepted(repositories):
    repository = repositories["observations"]
    observed_at = datetime(
        2026,
        9,
        10,
        12,
        8,
        tzinfo=timezone.utc,
    )

    observation, was_created = repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="situacao",
        value_type="text",
        value="Ativa",
        observed_at=observed_at,
    )

    assert was_created is True
    assert observation.observed_at.startswith(
        "2026-09-10T12:08:00"
    )


def test_checksum_is_deterministic(repositories):
    repository = repositories["observations"]

    first = repository.generate_checksum(
        1,
        2,
        "rating",
        "text",
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )

    second = repository.generate_checksum(
        1,
        2,
        "rating",
        "text",
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )

    assert first == second
    assert len(first) == 64


def test_database_integrity_is_preserved(repositories):
    repository = repositories["observations"]

    repository.create(
        debenture_id=repositories["debenture"].id,
        source_id=repositories["snd_source_id"],
        field_name="valor nominal",
        value_type="numeric",
        value="1000.00",
        unit="BRL",
        observed_at="2026-09-10T12:09:00+00:00",
    )

    assert repositories["database"].integrity_check() == "ok"
    assert repositories["database"].foreign_key_check() == []
