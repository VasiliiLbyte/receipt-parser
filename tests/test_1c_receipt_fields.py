"""Поля для 1С (КПП, оплата, валюта, ед. изм.) — нормализация и схема."""

import pytest
from pydantic import ValidationError

from src.pipeline.normalize import (
    normalize_currency,
    normalize_flat_data,
    normalize_kpp,
    normalize_payment_method,
    normalize_unit,
)
from src.schemas import validate_receipt_data


@pytest.mark.parametrize(
    "text,expected",
    [
        ("БЕЗНАЛИЧНЫМИ", "card"),
        ("безналичными", "card"),
        ("ОПЛАТА КАРТОЙ", "card"),
        ("НАЛИЧНЫМИ", "cash"),
        ("наличные", "cash"),
        ("cash", "cash"),
    ],
)
def test_normalize_payment_method_card_cash(text, expected):
    assert normalize_payment_method(text) == expected


def test_normalize_payment_method_absent():
    assert normalize_payment_method(None) is None
    assert normalize_payment_method("") is None
    assert normalize_payment_method("   ") is None


def test_normalize_payment_method_unknown_phrase():
    assert normalize_payment_method("бонусами") is None


def test_normalize_unit_strip_dot_lower():
    assert normalize_unit("шт.") == "шт"
    assert normalize_unit("КГ") == "кг"


def test_normalize_unit_missing():
    assert normalize_unit(None) is None
    assert normalize_unit("") is None


def test_normalize_currency_default_rub():
    assert normalize_currency(None) == "RUB"
    assert normalize_currency("") == "RUB"
    assert normalize_currency("  ") == "RUB"


def test_normalize_currency_usd():
    assert normalize_currency("usd") == "USD"


def test_normalize_kpp_valid():
    assert normalize_kpp("7736010010") == "7736010010"
    assert len(normalize_kpp("7736010010") or "") == 10
    assert normalize_kpp("773601001") is None  # 9 цифр — не КПП


def test_normalize_kpp_invalid():
    assert normalize_kpp("77360100101") is None  # 11 digits
    assert normalize_kpp("12abc345xx") is None


def test_normalize_flat_data_end_to_end():
    raw = {
        "organization": "ООО Тест",
        "inn": "781603445844",
        "kpp": "7736010010",
        "date": "2026-01-15",
        "receipt_number": "1",
        "payment_method": "БЕЗНАЛИЧНЫМИ",
        "items": [
            {
                "name": "Товар",
                "unit": "шт.",
                "price_per_unit": 10.0,
                "quantity": 2.0,
                "total_price": 20.0,
            }
        ],
        "total": 20.0,
    }
    out = normalize_flat_data(raw)
    assert out["payment_method"] == "card"
    assert out["currency"] == "RUB"
    assert out["kpp"] == "7736010010"
    assert out["items"][0]["unit"] == "шт"


def test_pydantic_accepts_1c_fields():
    flat = {
        "organization": "X",
        "inn": "781603445844",
        "kpp": "7736010010",
        "date": "2026-01-01",
        "receipt_number": "1",
        "payment_method": "card",
        "currency": "RUB",
        "total": 100.0,
        "items": [
            {
                "name": "A",
                "unit": "кг",
                "price_per_unit": 50.0,
                "quantity": 2.0,
                "total_price": 100.0,
            }
        ],
    }
    m, _ = validate_receipt_data(flat)
    assert m.kpp == "7736010010"
    assert m.payment_method == "card"
    assert m.currency == "RUB"
    assert m.items[0].unit == "кг"


def test_pydantic_kpp_invalid_becomes_none():
    flat = {
        "organization": "X",
        "inn": "781603445844",
        "kpp": "12abc",
        "date": "2026-01-01",
        "receipt_number": "1",
        "total": 1.0,
        "items": [{"name": "A", "price_per_unit": 1.0, "quantity": 1.0, "total_price": 1.0}],
    }
    m, _ = validate_receipt_data(flat)
    assert m.kpp is None
