"""Юнит-тесты Pydantic-схемы чека (без API)."""

import pytest
from pydantic import ValidationError

from src.schemas import ReceiptData, ReceiptItem, receipt_data_to_dict, validate_receipt_data


def test_receipt_item_rejects_negative_price():
    with pytest.raises(ValidationError):
        ReceiptItem(
            name="x",
            price_per_unit=-1.0,
            quantity=1.0,
            total_price=1.0,
        )


def test_receipt_data_inn_digits_and_length():
    m = ReceiptData(inn="781603445844", items=[])
    assert m.inn == "781603445844"
    with pytest.raises(ValidationError):
        ReceiptData(inn="78160344584", items=[])  # 11 digits
    with pytest.raises(ValidationError):
        ReceiptData(inn="78a1603445844", items=[])


def test_receipt_data_date_format():
    ReceiptData(date="2026-02-19", items=[])
    with pytest.raises(ValidationError):
        ReceiptData(date="19.02.2026", items=[])


def test_validate_receipt_data_roundtrip():
    flat = {
        "organization": "ООО Тест",
        "inn": "781603445844",
        "date": "2026-02-19",
        "receipt_number": "42",
        "total": 100.0,
        "total_vat": 20.0,
        "items": [
            {
                "name": "Товар",
                "price_per_unit": 50.0,
                "quantity": 2.0,
                "total_price": 100.0,
                "vat_rate": "20%",
                "vat_amount": 16.67,
            }
        ],
    }
    model, warnings = validate_receipt_data(flat)
    assert not warnings
    back = receipt_data_to_dict(model)
    assert back["inn"] == flat["inn"]
    assert back["items"][0]["name"] == "Товар"


def test_validate_receipt_data_invalid_inn_raises():
    flat = {
        "inn": "not-digits",
        "items": [],
    }
    with pytest.raises(ValidationError):
        validate_receipt_data(flat)
