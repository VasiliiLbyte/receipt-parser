from src.pipeline.normalize import (
    is_acquirer_bank_name,
    normalize_flat_data,
    normalize_inn,
    normalize_item_name,
    normalize_organization,
    normalize_receipt_number,
    normalize_vat_rate,
)


def test_normalize_vat_rate_20_120_to_20_percent():
    assert normalize_vat_rate("20/120") == "20%"
    assert normalize_vat_rate("НДС 20/120") == "20%"


def test_normalize_organization_strips_atol_suffix():
    assert normalize_organization("ООО Все Инструменты Ру АТОЛ") == "ООО Все Инструменты Ру"


def test_normalize_receipt_number_keeps_leading_zeros():
    assert normalize_receipt_number("чек 0048") == "0048"
    assert normalize_receipt_number("N 9") == "9"
    assert normalize_receipt_number("No 9") == "9"


def test_normalize_inn_repairs_single_digit_if_unique_valid_candidate():
    # Real value from user case: OCR read ...885 instead of ...886.
    assert normalize_inn("7730208885") == "7730208886"


def test_normalize_flat_data_applies_vat_rate_normalization_for_items():
    flat = {
        "items": [
            {
                "name": "Товар",
                "price_per_unit": "100.00",
                "quantity": "1",
                "total_price": "100.00",
                "vat_rate": "20/120",
            }
        ]
    }
    normalized = normalize_flat_data(flat)
    assert normalized["items"][0]["vat_rate"] == "20%"


def test_is_acquirer_bank_name_true_for_sberbank():
    assert is_acquirer_bank_name("ПАО СБЕРБАНК")


def test_normalize_flat_data_clears_bank_acquirer_as_merchant():
    flat = {
        "organization": "ПАО СБЕРБАНК",
        "items": [{"name": "Болт", "price_per_unit": "10", "quantity": "1", "total_price": "10"}],
    }
    normalized = normalize_flat_data(flat)
    assert normalized["organization"] is None


def test_normalize_organization_fixes_sazk_to_sdek_finans():
    assert normalize_organization("ООО САЗК ФИНАНС") == 'ООО "СДЭК ФИНАНС"'


def test_normalize_organization_fixes_saek_to_sdek_global():
    assert normalize_organization('ООО "САЭК-ГЛОБАЛ"') == 'ООО "СДЭК-ГЛОБАЛ"'


def test_normalize_item_name_strips_trailing_vat_marker():
    assert normalize_item_name("DW-A9005М ЭМАЛЬ УНИВЕРСАЛЬ НАС20%") == "DW-A9005М ЭМАЛЬ УНИВЕРСАЛЬ"
    assert normalize_item_name("РАЗЬЕМ ДАТЧИКА КИСЛОРОДА А НДС 20%") == "РАЗЬЕМ ДАТЧИКА КИСЛОРОДА А"
