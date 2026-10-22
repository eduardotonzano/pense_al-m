import pathlib
import re
from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal

import pytest

from debenture_search.database import Database
from debenture_search.repositories.debenture_event_repository import (
    ALLOWED_EVENT_TYPES,
    DebentureEventRecord,
    DebentureEventRepository,
)
from debenture_search.repositories.debenture_repository import (
    DebentureRepository,
)
from debenture_search.repositories.raw_record_repository import (
    RawRecordRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATHS = (
    PROJECT_DIR / "migrations" / "001_initial_schema.sql",
    PROJECT_DIR / "migrations" / "002_debenture_events.sql",
)


@pytest.fixture
def repositories(tmp_path):
    test_database = Database(tmp_path / "debenture_event_repository.db")

    with test_database.connection() as connection:
        for path in MIGRATION_PATHS:
            connection.executescript(path.read_text(encoding="utf-8"))
        connection.commit()

    debenture_repository = DebentureRepository(test_database)
    debenture = debenture_repository.create(
        asset_code="EVT12",
        isin="BREVTDBS0012",
        status="active",
    )
    other_debenture = debenture_repository.create(
        asset_code="EVT34",
        isin="BREVTDBS0034",
        status="active",
    )

    source_row = test_database.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("SND",),
    )
    manual_source_row = test_database.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("MANUAL",),
    )

    return {
        "database": test_database,
        "debenture": debenture,
        "other_debenture": other_debenture,
        "snd_source_id": int(source_row["id"]),
        "manual_source_id": int(manual_source_row["id"]),
        "events": DebentureEventRepository(test_database),
    }


def add_event(repositories, **overrides):
    values = {
        "debenture_id": repositories["debenture"].id,
        "source_id": repositories["snd_source_id"],
        "event_type": "juros",
        "event_date": "2026-09-15",
        "observed_at": "2026-09-11T12:00:00+00:00",
    }
    values.update(overrides)

    return repositories["events"].create(**values)


def test_create_event_without_value(repositories):
    event, was_created = add_event(repositories)

    assert was_created is True
    assert isinstance(event, DebentureEventRecord)
    assert event.event_type == "juros"
    assert event.event_date == "2026-09-15"
    assert event.value is None
    assert event.unit is None
    assert event.confidence == "reported"
    assert event.source_id == repositories["snd_source_id"]
    assert event.observed_at == "2026-09-11T12:00:00+00:00"
    assert len(event.checksum) == 64


def test_create_event_with_value_and_unit(repositories):
    event, was_created = add_event(
        repositories,
        event_type="amortizacao",
        value="16.6667",
        unit="  percentual  ",
    )

    assert was_created is True
    assert event.value == Decimal("16.6667")
    assert event.unit == "percentual"


def test_create_every_event_type(repositories):
    for event_type in sorted(ALLOWED_EVENT_TYPES):
        add_event(repositories, event_type=event_type)

    assert repositories["events"].count() == len(ALLOWED_EVENT_TYPES)
    assert len(ALLOWED_EVENT_TYPES) == 10


def test_event_types_match_migration_check(repositories):
    row = repositories["database"].fetch_one(
        "SELECT sql FROM sqlite_master WHERE name = 'debenture_events'"
    )
    match = re.search(r"event_type IN \(([^)]*)\)", row["sql"])
    declared = {
        item.strip().strip("'") for item in match.group(1).split(",")
    }

    assert declared == ALLOWED_EVENT_TYPES


def test_decimal_value_is_preserved(repositories):
    nominal, _ = add_event(
        repositories,
        event_type="atualizacao",
        value=Decimal("1465.04499"),
        unit="BRL",
    )
    small, _ = add_event(
        repositories,
        event_type="premio",
        value="0.0000123",
        unit="percentual",
    )

    assert nominal.value == Decimal("1465.04499")
    assert small.value == Decimal("0.0000123")


def test_same_event_is_idempotent(repositories):
    first, first_created = add_event(
        repositories,
        value="3.9",
        unit="percentual",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    second, second_created = add_event(
        repositories,
        value="3.9",
        unit="percentual",
        observed_at="2026-09-12T12:00:00+00:00",
    )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert second.observed_at == "2026-09-11T12:00:00+00:00"
    assert repositories["events"].count() == 1


def test_equivalent_decimal_representations_are_the_same_event(repositories):
    first, _ = add_event(repositories, value="1.50", unit="percentual")
    second, second_created = add_event(
        repositories,
        value=Decimal("1.5"),
        unit="percentual",
    )
    third, third_created = add_event(
        repositories,
        value=1.5,
        unit="percentual",
    )

    assert second_created is False
    assert third_created is False
    assert second.id == first.id
    assert third.id == first.id


def test_changed_value_preserves_history(repositories):
    first, _ = add_event(
        repositories,
        value="10",
        unit="percentual",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    second, second_created = add_event(
        repositories,
        value="12",
        unit="percentual",
        observed_at="2026-09-12T12:00:00+00:00",
    )

    assert second_created is True
    assert second.id != first.id
    assert repositories["events"].count() == 2


def test_different_source_is_not_reused(repositories):
    first, _ = add_event(repositories)
    second, second_created = add_event(
        repositories,
        source_id=repositories["manual_source_id"],
    )

    assert second_created is True
    assert second.id != first.id


def test_different_unit_is_not_reused(repositories):
    first, _ = add_event(repositories, value="100", unit="percentual")
    second, second_created = add_event(repositories, value="100", unit="BRL")

    assert second_created is True
    assert second.id != first.id


def test_different_type_or_date_is_a_new_event(repositories):
    first, _ = add_event(repositories)
    other_type, other_type_created = add_event(
        repositories,
        event_type="premio",
    )
    other_date, other_date_created = add_event(
        repositories,
        event_date="2026-10-15",
    )

    assert other_type_created is True
    assert other_date_created is True
    assert len({first.id, other_type.id, other_date.id}) == 3


def test_get_by_id(repositories):
    event, _ = add_event(repositories)

    found = repositories["events"].get_by_id(event.id)

    assert found == event


def test_get_by_checksum(repositories):
    event, _ = add_event(repositories)

    found = repositories["events"].get_by_checksum(event.checksum)

    assert found == event


def test_get_missing_event_returns_none(repositories):
    assert repositories["events"].get_by_id(999999) is None
    assert repositories["events"].get_by_checksum("0" * 64) is None


def test_rejects_unknown_debenture(repositories):
    with pytest.raises(ValueError, match="debenture informada nao existe"):
        add_event(repositories, debenture_id=999999)


def test_rejects_unknown_source(repositories):
    with pytest.raises(ValueError, match="fonte informada nao existe"):
        add_event(repositories, source_id=999999)


def test_rejects_unknown_raw_record(repositories):
    with pytest.raises(
        ValueError,
        match="registro bruto informado nao existe",
    ):
        add_event(repositories, raw_record_id=999999)


def test_rejects_empty_event_type(repositories):
    for event_type in (None, "", "   "):
        with pytest.raises(ValueError, match="tipo do evento e obrigatorio"):
            add_event(repositories, event_type=event_type)


def test_rejects_invalid_event_type(repositories):
    with pytest.raises(ValueError, match="Tipo de evento invalido"):
        add_event(repositories, event_type="cupom")


def test_rejects_missing_event_date(repositories):
    for event_date in (None, "", "   "):
        with pytest.raises(ValueError, match="data do evento e obrigatoria"):
            add_event(repositories, event_date=event_date)


def test_rejects_invalid_event_date(repositories):
    for event_date in ("2026-02-30", "15/09/2026", "abc"):
        with pytest.raises(ValueError, match="Data do evento invalida"):
            add_event(repositories, event_date=event_date)


def test_rejects_invalid_numeric_value(repositories):
    for value in ("abc", True, "NaN", "Infinity"):
        with pytest.raises(ValueError, match="Valor numerico invalido"):
            add_event(repositories, value=value)


def test_rejects_unit_without_value(repositories):
    with pytest.raises(ValueError, match="unidade exige um valor"):
        add_event(repositories, unit="percentual")


def test_blank_unit_is_ignored(repositories):
    event, _ = add_event(repositories, unit="   ")

    assert event.unit is None


def test_rejects_invalid_confidence(repositories):
    with pytest.raises(ValueError, match="Nivel de confianca invalido"):
        add_event(repositories, confidence="guess")


def test_rejects_invalid_observed_at(repositories):
    with pytest.raises(ValueError, match="Data de observacao invalida"):
        add_event(repositories, observed_at="xx")


def test_event_type_is_normalized(repositories):
    event, _ = add_event(repositories, event_type="  Opcao Venda ")

    assert event.event_type == "opcao_venda"


def test_date_and_datetime_objects_are_accepted(repositories):
    event, _ = add_event(
        repositories,
        event_date=date(2026, 9, 15),
        observed_at=datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc),
    )

    assert event.event_date == "2026-09-15"
    assert event.observed_at == "2026-09-11T12:00:00+00:00"


def test_manual_source_and_confidence(repositories):
    event, _ = add_event(
        repositories,
        source_id=repositories["manual_source_id"],
        confidence="manual",
    )

    assert event.source_id == repositories["manual_source_id"]
    assert event.confidence == "manual"


def test_links_raw_record(repositories):
    raw_record, _ = RawRecordRepository(repositories["database"]).create(
        source_id=repositories["snd_source_id"],
        payload="agenda de eventos",
    )

    event, _ = add_event(repositories, raw_record_id=raw_record.id)

    assert event.raw_record_id == raw_record.id


def test_checksum_is_deterministic(repositories):
    generate = repositories["events"].generate_checksum

    def checksum(**overrides):
        values = {
            "debenture_id": 1,
            "source_id": 1,
            "event_type": "juros",
            "event_date": "2026-09-15",
            "value": Decimal("1.5"),
            "unit": "percentual",
        }
        values.update(overrides)
        return generate(**values)

    base = checksum()

    assert checksum() == base
    assert checksum(value=Decimal("1.50")) == base
    assert checksum(value=Decimal("0.00"), unit=None) == checksum(
        value=Decimal("0"),
        unit=None,
    )
    assert checksum(debenture_id=2) != base
    assert checksum(source_id=2) != base
    assert checksum(event_type="premio") != base
    assert checksum(event_date="2026-09-16") != base
    assert checksum(value=Decimal("2")) != base
    assert checksum(unit="BRL") != base


def test_checksum_ignores_observation_time_and_confidence(repositories):
    first, _ = add_event(
        repositories,
        observed_at="2026-09-11T12:00:00+00:00",
        confidence="reported",
    )
    expected = repositories["events"].generate_checksum(
        repositories["debenture"].id,
        repositories["snd_source_id"],
        "juros",
        "2026-09-15",
        None,
        None,
    )

    assert first.checksum == expected


def test_list_is_ordered_by_event_date(repositories):
    for event_date in ("2027-03-15", "2026-09-15", "2026-12-15"):
        add_event(repositories, event_date=event_date)

    events = repositories["events"].list_by_debenture(
        repositories["debenture"].id
    )

    assert [event.event_date for event in events] == [
        "2026-09-15",
        "2026-12-15",
        "2027-03-15",
    ]


def test_list_orders_same_date_by_type(repositories):
    add_event(repositories, event_type="premio")
    add_event(repositories, event_type="juros")
    add_event(repositories, event_type="amortizacao")

    events = repositories["events"].list_by_debenture(
        repositories["debenture"].id
    )

    assert [event.event_type for event in events] == [
        "amortizacao",
        "juros",
        "premio",
    ]


def test_list_filters_by_type(repositories):
    add_event(repositories, event_type="juros")
    add_event(repositories, event_type="premio")

    events = repositories["events"].list_by_debenture(
        repositories["debenture"].id,
        event_type="Premio",
    )

    assert [event.event_type for event in events] == ["premio"]


def test_list_filters_by_date_range_inclusive(repositories):
    for event_date in (
        "2026-09-15",
        "2026-12-15",
        "2027-03-15",
        "2027-06-15",
    ):
        add_event(repositories, event_date=event_date)

    events = repositories["events"].list_by_debenture(
        repositories["debenture"].id,
        date_from="2026-12-15",
        date_until=date(2027, 3, 15),
    )

    assert [event.event_date for event in events] == [
        "2026-12-15",
        "2027-03-15",
    ]


def test_list_rejects_inverted_range(repositories):
    with pytest.raises(ValueError, match="data final nao pode ser anterior"):
        repositories["events"].list_by_debenture(
            repositories["debenture"].id,
            date_from="2027-01-01",
            date_until="2026-01-01",
        )


def test_list_is_isolated_by_debenture(repositories):
    add_event(repositories)
    add_event(
        repositories,
        debenture_id=repositories["other_debenture"].id,
        event_date="2026-10-15",
    )

    events = repositories["events"].list_by_debenture(
        repositories["other_debenture"].id
    )

    assert [event.event_date for event in events] == ["2026-10-15"]


def test_list_supports_pagination(repositories):
    dates = [
        "2026-09-15",
        "2026-10-15",
        "2026-11-15",
        "2026-12-15",
        "2027-01-15",
    ]
    for event_date in dates:
        add_event(repositories, event_date=event_date)

    debenture_id = repositories["debenture"].id
    pages = [
        [
            event.event_date
            for event in repositories["events"].list_by_debenture(
                debenture_id,
                limit=2,
                offset=offset,
            )
        ]
        for offset in (0, 2, 4)
    ]

    assert pages == [
        ["2026-09-15", "2026-10-15"],
        ["2026-11-15", "2026-12-15"],
        ["2027-01-15"],
    ]


def test_list_clamps_limit_and_offset(repositories):
    for event_date in ("2026-09-15", "2026-10-15"):
        add_event(repositories, event_date=event_date)

    debenture_id = repositories["debenture"].id
    one_row = repositories["events"].list_by_debenture(
        debenture_id,
        limit=0,
    )
    negative_offset = repositories["events"].list_by_debenture(
        debenture_id,
        offset=-5,
    )

    assert [event.event_date for event in one_row] == ["2026-09-15"]
    assert [event.event_date for event in negative_offset] == [
        "2026-09-15",
        "2026-10-15",
    ]


def test_list_rejects_unknown_debenture(repositories):
    with pytest.raises(ValueError, match="debenture informada nao existe"):
        repositories["events"].list_by_debenture(999999)


def test_count_with_filters(repositories):
    add_event(repositories, event_type="juros")
    add_event(repositories, event_type="juros", event_date="2026-10-15")
    add_event(repositories, event_type="premio")
    add_event(
        repositories,
        debenture_id=repositories["other_debenture"].id,
        event_type="juros",
    )

    events = repositories["events"]

    assert events.count() == 4
    assert events.count(debenture_id=repositories["debenture"].id) == 3
    assert events.count(event_type="juros") == 3
    assert events.count(
        debenture_id=repositories["debenture"].id,
        event_type="premio",
    ) == 1

    with pytest.raises(ValueError, match="Tipo de evento invalido"):
        events.count(event_type="cupom")


def test_database_integrity_is_preserved(repositories):
    add_event(repositories, value="1", unit="percentual")
    add_event(repositories, event_type="vencimento", event_date="2034-09-15")

    assert repositories["database"].integrity_check() == "ok"
    assert repositories["database"].foreign_key_check() == []
