from credit_assets.utils.fundosnet_normalization import (
    equivalent_names,
    normalize_text,
    product_type_id,
)


def test_normalization_ignores_case_accents_punctuation_and_spaces():
    assert normalize_text("Opea Securitizadora S.A.") == "OPEA SECURITIZADORA SA"
    assert equivalent_names("Riza Securitizadora S.A.", "RIZA SECURITIZADORA SA")


def test_product_type_mapping_is_explicit():
    assert product_type_id("CRI") == 5
    assert product_type_id("cra") == 6
