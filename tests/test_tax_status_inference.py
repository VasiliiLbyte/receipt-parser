"""Семантика tax_status, merge налога (LOTTE-подобное), tax-exempt (Агат-подобное), quality raw-heuristic."""

from src.pipeline.normalize import normalize_flat_data
from src.pipeline.quality_gates import evaluate_quality
from src.pipeline.tax_status import (
    enrich_flat_tax_status,
    infer_tax_status,
    raw_suggests_tax_amount_omitted,
)
from src.schemas import validate_receipt_data


def test_lotte_like_gst_summary_total_vat_and_taxable():
    """Синтетика: альтернативные ключи + вложенный tax → total_vat; статус taxable."""
    raw = {
        "organization": 'АО "ЛОТТЕ РУС"',
        "date": "2026-02-05",
        "receipt_number": "CHK 1112",
        "items": [
            {
                "name": "Tea",
                "price_per_unit": 1390.0,
                "quantity": 1.0,
                "total_price": 1390.0,
                "vat_rate": None,
                "vat_amount": None,
            },
            {
                "name": "Honey",
                "price_per_unit": 280.0,
                "quantity": 1.0,
                "total_price": 280.0,
                "vat_rate": None,
                "vat_amount": None,
            },
        ],
        "total": 1670.0,
        "tax": {"vat": 301.15, "label": "VAT/incl"},
    }
    flat = normalize_flat_data(raw)
    assert flat["total_vat"] == 301.15
    enrich_flat_tax_status(flat, raw=raw)
    assert flat["tax_status"] == "taxable"
    model, _ = validate_receipt_data(flat)
    assert model.tax_status == "taxable"
    assert model.total_vat == 301.15


def test_agat_like_summa_bez_nds_tax_exempt():
    """Синтетика ООО Агат: строка «Сумма БЕЗ НДС» в notes, total_vat пуст."""
    raw = {
        "organization": 'ООО "Агат"',
        "inn": "7721791619",
        "date": "2026-02-13",
        "receipt_number": "17322",
        "notes": "Сумма БЕЗ НДС 3269.00",
        "items": [
            {
                "name": "Обед",
                "price_per_unit": 100.0,
                "quantity": 1.0,
                "total_price": 100.0,
            }
        ],
        "total": 3269.0,
        "total_vat": None,
    }
    flat = normalize_flat_data(raw)
    enrich_flat_tax_status(flat, raw=raw)
    assert flat["tax_status"] == "tax_exempt"
    assert raw_suggests_tax_amount_omitted(flat, raw) is False
    q = evaluate_quality(flat, schema_valid=True, raw_provider=raw)
    assert q.tax_summary_ok is True


def test_all_items_nds_ne_oblagaetsya_tax_exempt():
    raw = {
        "organization": "ООО ПАРК",
        "date": "2026-01-26",
        "receipt_number": "1",
        "items": [
            {
                "name": "Суп",
                "price_per_unit": 100.0,
                "quantity": 1.0,
                "total_price": 100.0,
                "vat_rate": "НДС не облагается",
            },
            {
                "name": "Чай",
                "price_per_unit": 50.0,
                "quantity": 1.0,
                "total_price": 50.0,
                "vat_rate": "НДС не облагается",
            },
        ],
        "total": 150.0,
        "total_vat": None,
    }
    flat = normalize_flat_data(raw)
    enrich_flat_tax_status(flat, raw=raw)
    assert flat["tax_status"] == "tax_exempt"


def test_raw_vat_amount_but_empty_total_vat_triggers_quality_issue():
    """В сыром JSON есть VAT+сумма, в flat нет total_vat — не tax_exempt → gate fail."""
    raw = {
        "organization": "X",
        "date": "2026-01-01",
        "receipt_number": "1",
        "items": [
            {
                "name": "A",
                "price_per_unit": 10.0,
                "quantity": 1.0,
                "total_price": 10.0,
            }
        ],
        "total": 10.0,
        "total_vat": None,
        "ocr_tail": "VAT/вкл.НДС 301.15",
    }
    flat = {
        "organization": "X",
        "inn": None,
        "date": "2026-01-01",
        "receipt_number": "1",
        "items": raw["items"],
        "total": 10.0,
        "total_vat": None,
    }
    assert infer_tax_status(flat, raw) == "unknown"
    assert raw_suggests_tax_amount_omitted(flat, raw) is True
    q = evaluate_quality(flat, schema_valid=True, raw_provider=raw)
    assert q.tax_summary_ok is False


def test_merge_top_level_tax_key_lotte_style():
    raw = {
        "organization": "R",
        "date": "2026-02-05",
        "receipt_number": "1",
        "items": [
            {
                "name": "A",
                "price_per_unit": 1.0,
                "quantity": 1.0,
                "total_price": 1.0,
            }
        ],
        "total": 10.0,
        "tax": 301.15,
    }
    flat = normalize_flat_data(raw)
    assert flat["total_vat"] == 301.15
