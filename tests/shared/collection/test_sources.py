"""Testes do catalogo compartilhado de fontes."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pense_alm.shared.collection.enums import (
    CollectionSourceType,
)
from pense_alm.shared.collection.sources import (
    CollectionSource,
)


def test_source_normalizes_code_and_name():
    source = CollectionSource(
        code="  fundos net  ",
        name="  Fundos   NET  ",
        source_type=CollectionSourceType.SCRAPER,
    )

    assert source.code == "FUNDOS_NET"
    assert source.name == "Fundos NET"


def test_source_accepts_priority_and_active():
    source = CollectionSource(
        code="SND",
        name="Sistema Nacional de Debentures",
        source_type=CollectionSourceType.API,
        priority=10,
        active=False,
    )

    assert source.priority == 10
    assert source.active is False


def test_source_generates_uuid():
    source = CollectionSource(
        code="SND",
        name="Sistema Nacional de Debentures",
        source_type=CollectionSourceType.API,
    )

    assert source.source_id is not None


def test_source_preserves_explicit_uuid():
    source_id = uuid4()

    source = CollectionSource(
        code="SND",
        name="Sistema Nacional de Debentures",
        source_type=CollectionSourceType.API,
        source_id=source_id,
    )

    assert source.source_id == source_id


def test_source_converts_created_at_to_utc():
    source = CollectionSource(
        code="SND",
        name="Sistema Nacional de Debentures",
        source_type=CollectionSourceType.API,
        created_at=datetime.fromisoformat(
            "2026-09-20T10:00:00-03:00"
        ),
    )

    assert source.created_at == datetime(
        2026,
        9,
        20,
        13,
        0,
        tzinfo=UTC,
    )


def test_source_rejects_empty_code():
    with pytest.raises(
        ValueError,
        match="code nao pode ser vazio",
    ):
        CollectionSource(
            code="   ",
            name="Fonte Valida",
            source_type=CollectionSourceType.API,
        )


def test_source_rejects_invalid_type():
    with pytest.raises(
        TypeError,
        match="CollectionSourceType",
    ):
        CollectionSource(
            code="SND",
            name="Fonte Valida",
            source_type="api",
        )


def test_source_rejects_negative_priority():
    with pytest.raises(
        ValueError,
        match="nao pode ser negativa",
    ):
        CollectionSource(
            code="SND",
            name="Fonte Valida",
            source_type=CollectionSourceType.API,
            priority=-1,
        )


def test_source_rejects_boolean_priority():
    with pytest.raises(
        TypeError,
        match="priority deve ser inteiro",
    ):
        CollectionSource(
            code="SND",
            name="Fonte Valida",
            source_type=CollectionSourceType.API,
            priority=True,
        )


def test_source_rejects_naive_created_at():
    with pytest.raises(
        ValueError,
        match="deve possuir timezone",
    ):
        CollectionSource(
            code="SND",
            name="Fonte Valida",
            source_type=CollectionSourceType.API,
            created_at=datetime(
                2026,
                9,
                20,
                10,
                0,
            ),
        )
