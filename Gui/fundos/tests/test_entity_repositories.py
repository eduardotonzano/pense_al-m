import pytest

from apoio import make_test_cnpj
from fundos.cnpj import InvalidCnpjError
from fundos.repositories import IdentityConflictError
from fundos.repositories.fund_class_repository import FundClassRepository
from fundos.repositories.fund_repository import FundRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


NUMERIC = make_test_cnpj(1)
ALPHANUMERIC = make_test_cnpj(2, alphanumeric=True)


def masked(cnpj):
    return cnpj[:2] + "." + cnpj[2:5] + "." + cnpj[5:8] + "/" + cnpj[8:12] + "-" + cnpj[12:]


@pytest.fixture
def repos(connection):
    return {
        "funds": FundRepository(connection),
        "classes": FundClassRepository(connection),
        "series": QuotaSeriesRepository(connection),
    }


def test_fund_cnpj_is_normalized_and_idempotent(repos):
    fund, created = repos["funds"].get_or_create(masked(NUMERIC))
    again, created_again = repos["funds"].get_or_create(NUMERIC)

    assert created and not created_again
    assert fund.cnpj == NUMERIC
    assert again.id == fund.id


def test_fund_with_invalid_check_digit_is_refused(repos, connection):
    wrong = NUMERIC[:13] + str((int(NUMERIC[13]) + 1) % 10)

    with pytest.raises(InvalidCnpjError):
        repos["funds"].get_or_create(wrong)

    assert connection.execute("SELECT COUNT(*) FROM funds").fetchone()[0] == 0


@pytest.mark.parametrize(
    "first, second",
    [
        (masked(ALPHANUMERIC).lower(), ALPHANUMERIC),
        (ALPHANUMERIC.lower(), masked(ALPHANUMERIC)),
    ],
    ids=["mascara-minuscula", "minuscula"],
)
def test_alphanumeric_fund_and_class_share_one_uppercase_row(repos, first, second):
    fund, _ = repos["funds"].get_or_create(first)
    same_fund, created = repos["funds"].get_or_create(second)
    fund_class, _ = repos["classes"].get_or_create(first, fund.id)
    same_class, class_created = repos["classes"].get_or_create(second, fund.id)

    assert not created and not class_created
    assert fund.cnpj == fund_class.cnpj == ALPHANUMERIC
    assert (same_fund.id, same_class.id) == (fund.id, fund_class.id)


def test_class_is_idempotent_and_listed_by_fund(repos):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    fund_class, created = repos["classes"].get_or_create(NUMERIC, fund.id)
    again, created_again = repos["classes"].get_or_create(masked(NUMERIC), fund.id)

    assert created and not created_again
    assert again == fund_class
    assert repos["classes"].list_by_fund(fund.id) == [fund_class]


def test_class_linked_to_another_fund_is_blocked(repos, connection):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    other, _ = repos["funds"].get_or_create(make_test_cnpj(3))
    repos["classes"].get_or_create(make_test_cnpj(4), fund.id)

    with pytest.raises(IdentityConflictError, match="outro fundo"):
        repos["classes"].get_or_create(make_test_cnpj(4), other.id)

    rows = connection.execute("SELECT fund_id FROM fund_classes").fetchall()
    assert [row[0] for row in rows] == [fund.id]

    with pytest.raises(ValueError, match="fundo informado"):
        repos["classes"].get_or_create(make_test_cnpj(5), 999)


def test_series_labels_match_by_normalized_form(repos):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    fund_class, _ = repos["classes"].get_or_create(NUMERIC, fund.id)

    first, created = repos["series"].get_or_create(
        fund_class_id=fund_class.id,
        label="Subclasse Senior Série 1 |",
    )
    again, created_again = repos["series"].get_or_create(
        fund_class_id=fund_class.id,
        label="subclasse  senior serie 1",
    )

    assert created and not created_again
    assert again.id == first.id
    assert first.series_label_key == "subclasse senior serie 1"


def test_series_can_hang_from_the_fund(repos):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    fund_class, _ = repos["classes"].get_or_create(NUMERIC, fund.id)

    on_fund, _ = repos["series"].get_or_create(fund_id=fund.id, label="Subclasse Senior")
    on_class, _ = repos["series"].get_or_create(fund_class_id=fund_class.id, label="Subclasse Senior")

    assert on_fund.id != on_class.id
    assert (on_fund.fund_id, on_fund.fund_class_id) == (fund.id, None)


def test_missing_subclass_id_is_filled_but_never_changed(repos):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    fund_class, _ = repos["classes"].get_or_create(NUMERIC, fund.id)
    series, _ = repos["series"].get_or_create(fund_class_id=fund_class.id, label="Subclasse Senior")

    filled, created = repos["series"].get_or_create(
        fund_class_id=fund_class.id,
        label="Subclasse Senior",
        cvm_subclass_id="SUBFICTICIA001",
    )

    assert not created
    assert (filled.id, filled.cvm_subclass_id) == (series.id, "SUBFICTICIA001")

    with pytest.raises(IdentityConflictError, match="nunca e trocada"):
        repos["series"].get_or_create(
            fund_class_id=fund_class.id,
            label="Subclasse Senior",
            cvm_subclass_id="SUBFICTICIA002",
        )


def test_crossed_series_keys_are_blocked(repos):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    fund_class, _ = repos["classes"].get_or_create(NUMERIC, fund.id)
    other_fund, _ = repos["funds"].get_or_create(make_test_cnpj(3))
    repos["series"].get_or_create(fund_class_id=fund_class.id, label="Subclasse Senior")
    repos["series"].get_or_create(fund_class_id=fund_class.id, cvm_subclass_id="SUBFICTICIA003")

    with pytest.raises(IdentityConflictError, match="series diferentes"):
        repos["series"].get_or_create(
            fund_class_id=fund_class.id,
            label="Subclasse Senior",
            cvm_subclass_id="SUBFICTICIA003",
        )

    with pytest.raises(IdentityConflictError, match="outro fundo ou classe"):
        repos["series"].get_or_create(fund_id=other_fund.id, cvm_subclass_id="SUBFICTICIA003")


def test_series_needs_one_parent_and_one_key(repos):
    fund, _ = repos["funds"].get_or_create(NUMERIC)
    fund_class, _ = repos["classes"].get_or_create(NUMERIC, fund.id)

    with pytest.raises(ValueError, match="exatamente um pai"):
        repos["series"].get_or_create(fund_id=fund.id, fund_class_id=fund_class.id, label="x")

    with pytest.raises(ValueError, match="rotulo"):
        repos["series"].get_or_create(fund_id=fund.id)

    with pytest.raises(ValueError, match="vazio"):
        repos["series"].get_or_create(fund_id=fund.id, label=" | ")
