import pytest

from fundos.repositories.source_repository import SourceRepository


def test_seeded_sources_by_code(connection):
    repository = SourceRepository(connection)

    cvm = repository.get_by_code("cvm_dados_abertos")
    manual = repository.get_by_code("MANUAL")

    assert (cvm.code, cvm.source_type, cvm.priority, cvm.active) == (
        "CVM_DADOS_ABERTOS",
        "open_data",
        200,
        True,
    )
    assert (manual.priority, manual.source_type) == (1000, "manual")
    assert repository.get_by_id(cvm.id) == cvm
    assert repository.get_by_code("ANBIMA_API") is None

    with pytest.raises(ValueError):
        repository.get_by_code(" ")


def test_list_all_orders_by_priority_and_filters(connection):
    repository = SourceRepository(connection)
    connection.execute("UPDATE sources SET active = 0 WHERE code = 'MANUAL'")

    assert [s.code for s in repository.list_all()] == ["MANUAL", "CVM_DADOS_ABERTOS"]
    assert [s.code for s in repository.list_all(active=True)] == ["CVM_DADOS_ABERTOS"]
    assert [s.code for s in repository.list_all(active=False)] == ["MANUAL"]


def test_unknown_id_returns_none(connection):
    assert SourceRepository(connection).get_by_id(999) is None
