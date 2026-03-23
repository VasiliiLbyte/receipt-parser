"""Нормализация GST/VAT/TAX → total_vat и item-поля (без расчётов)."""

from src.pipeline.normalize import normalize_flat_data, merge_alternate_total_tax
from src.schemas import validate_receipt_data


def test_gst_summary_only_maps_to_total_vat():
    """Синтетика: как чек с блоком GST внизу, без налога в строках."""
    raw = {
        "organization": "Cafe AU",
        "receipt_number": "INV-9001",
        "date": "2026-03-01",
        "items": [
            {
                "name": "Coffee",
                "price_per_unit": 5.0,
                "quantity": 2.0,
                "total_price": 10.0,
            }
        ],
        "total": 11.0,
        "total_gst": 1.0,
    }
    out = normalize_flat_data(raw)
    assert out["total_vat"] == 1.0
    assert out["items"][0].get("vat_rate") is None
    assert out["items"][0].get("vat_amount") is None


def test_total_vat_alias_total_tax():
    raw = {
        "receipt_number": "1",
        "organization": "X",
        "date": "2026-01-15",
        "items": [
            {
                "name": "A",
                "price_per_unit": 100.0,
                "quantity": 1.0,
                "total_price": 100.0,
            }
        ],
        "total": 115.0,
        "total_tax": "15,00",
    }
    out = normalize_flat_data(raw)
    assert out["total_vat"] == 15.0


def test_existing_total_vat_not_overwritten_by_gst():
    raw = {
        "total_vat": 7.5,
        "total_gst": 99.0,
        "items": [{"name": "n", "price_per_unit": 1, "quantity": 1, "total_price": 1}],
        "total": 10,
        "organization": "o",
        "date": "2026-01-01",
    }
    out = normalize_flat_data(raw)
    assert out["total_vat"] == 7.5


def test_item_gst_amount_maps_to_vat_amount():
    raw = {
        "organization": "S",
        "date": "2026-01-01",
        "items": [
            {
                "name": "Item",
                "price_per_unit": 50.0,
                "quantity": 1.0,
                "total_price": 50.0,
                "gst_amount": "5,00",
            }
        ],
        "total": 55.0,
    }
    out = normalize_flat_data(raw)
    assert out["items"][0]["vat_amount"] == 5.0


def test_no_vat_phrase_on_item():
    raw = {
        "organization": "S",
        "date": "2026-01-01",
        "items": [
            {
                "name": "Item",
                "price_per_unit": 10.0,
                "quantity": 1.0,
                "total_price": 10.0,
                "vat_rate": "без НДС",
            }
        ],
        "total": 10.0,
        "total_vat": None,
    }
    out = normalize_flat_data(raw)
    assert out["items"][0]["vat_rate"] == "без НДС"
    assert out.get("total_vat") is None


def test_pydantic_total_vat_without_item_vat():
    flat = {
        "organization": "Shop",
        "inn": "781603445844",
        "date": "2026-02-19",
        "receipt_number": "42",
        "total": 110.0,
        "total_vat": 10.0,
        "items": [
            {
                "name": "Goods",
                "price_per_unit": 100.0,
                "quantity": 1.0,
                "total_price": 100.0,
                "vat_rate": None,
                "vat_amount": None,
            }
        ],
    }
    model, _ = validate_receipt_data(flat)
    assert model.total_vat == 10.0
    assert model.items[0].vat_rate is None
    assert model.items[0].vat_amount is None


def test_nested_tax_dict_maps_to_total_vat():
    raw = {
        "organization": "R",
        "date": "2026-01-01",
        "receipt_number": "1",
        "items": [
            {"name": "A", "price_per_unit": 1.0, "quantity": 1.0, "total_price": 1.0},
        ],
        "total": 2.0,
        "tax": {"gst": "301,15"},
    }
    out = normalize_flat_data(raw)
    assert out["total_vat"] == 301.15


def test_merge_alternate_total_tax_respects_zero():
    result = {"total_vat": 0.0, "total_gst": 50.0}
    merge_alternate_total_tax(result)
    assert result["total_vat"] == 0.0
