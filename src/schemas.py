"""
Pydantic models for receipt data validation.

Используется в pipeline после normalize/validate: при ошибке валидации
оркестратор сохраняет предыдущий словарь без потери позиций чека.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal, Optional

from src.pipeline.normalize import normalize_currency, normalize_kpp, normalize_payment_method, normalize_unit

from pydantic import BaseModel, Field, field_validator, model_validator

PaymentMethod = Literal["cash", "card", "mixed"]


class ReceiptItem(BaseModel):
    """Позиция чека."""

    name: str = Field(default="", description="Название товара/услуги")
    price_per_unit: float = Field(..., description="Цена за единицу")
    quantity: float = Field(..., description="Количество")
    total_price: float = Field(..., description="Итоговая цена позиции")
    vat_rate: Optional[str] = Field(
        None, description="Ставка налога с чека: НДС/VAT/GST/TAX (например '20%', 'без НДС', 'no VAT')"
    )
    vat_amount: Optional[float] = Field(None, description="Сумма НДС")
    unit: Optional[str] = Field(
        None,
        description="Единица измерения с чека (шт, кг, л, порц, …), только если напечатана",
        max_length=32,
    )

    @field_validator("unit", mode="before")
    @classmethod
    def coerce_unit(cls, v: Any) -> Optional[str]:
        return normalize_unit(v)

    @field_validator("price_per_unit", "quantity", "total_price")
    @classmethod
    def validate_non_negative(cls, v: float, info) -> float:
        if v < 0:
            raise ValueError(f"Поле {info.field_name} не может быть отрицательным: {v}")
        return v

    @field_validator("vat_amount")
    @classmethod
    def validate_vat_amount_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError(f"vat_amount не может быть отрицательным: {v}")
        return v


class ReceiptData(BaseModel):
    """Плоская модель данных чека (как после normalize)."""

    organization: Optional[str] = Field(None, description="Название организации")
    inn: Optional[str] = Field(None, description="ИНН (10 или 12 цифр)")
    date: Optional[str] = Field(None, description="Дата YYYY-MM-DD")
    receipt_number: Optional[str] = Field(None, description="Номер чека")
    items: list[ReceiptItem] = Field(default_factory=list, description="Позиции")
    total: Optional[float] = Field(None, description="Итог чека")
    total_vat: Optional[float] = Field(
        None, description="Итоговый налог с чека (НДС/VAT/GST/TAX), только напечатанная сумма"
    )
    tax_status: Optional[Literal["taxable", "tax_exempt", "unknown"]] = Field(
        None,
        description="Семантика налога: taxable / tax_exempt / unknown (без расчёта налога)",
    )
    kpp: Optional[str] = Field(None, description="КПП контрагента (10 цифр), только если на чеке")
    payment_method: Optional[PaymentMethod] = Field(
        None, description="Форма оплаты: cash | card | mixed"
    )
    currency: str = Field(
        default="RUB",
        description="Валюта ISO 4217; по умолчанию RUB",
        min_length=3,
        max_length=3,
    )

    @field_validator("kpp", mode="before")
    @classmethod
    def coerce_kpp(cls, v: Any) -> Optional[str]:
        return normalize_kpp(v)

    @field_validator("payment_method", mode="before")
    @classmethod
    def coerce_payment_method(cls, v: Any) -> Optional[PaymentMethod]:
        return normalize_payment_method(v)

    @field_validator("currency", mode="before")
    @classmethod
    def coerce_currency(cls, v: Any) -> str:
        return normalize_currency(v)

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not v.isdigit():
            raise ValueError(f"ИНН должен содержать только цифры: {v}")
        if len(v) not in (10, 12):
            raise ValueError(f"ИНН должен содержать 10 или 12 цифр, получено {len(v)}: {v}")
        return v

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"Дата должна быть в формате YYYY-MM-DD: {v}")
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Некорректная дата: {v}") from e
        return v

    @field_validator("total", "total_vat")
    @classmethod
    def validate_totals_non_negative(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError(f"Поле {info.field_name} не может быть отрицательным: {v}")
        return v

    @model_validator(mode="after")
    def warn_items_total_mismatch(self) -> ReceiptData:
        """Мягкая эвристика: не ломает валидацию, только для будущих предупреждений."""
        if self.total is not None and self.items:
            items_sum = sum(item.total_price for item in self.items)
            if abs(items_sum - self.total) > 1.0:
                pass
        return self


def _flat_item_to_mapping(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"items[{index}] должен быть словарём")
    return {
        "name": raw.get("name") if raw.get("name") is not None else "",
        "price_per_unit": raw.get("price_per_unit", 0.0),
        "quantity": raw.get("quantity", 1.0),
        "total_price": raw.get("total_price", 0.0),
        "vat_rate": raw.get("vat_rate"),
        "vat_amount": raw.get("vat_amount"),
        "unit": raw.get("unit"),
    }


def validate_receipt_data(data: dict[str, Any]) -> tuple[ReceiptData, list[str]]:
    """
    Строгая валидация всего чека.

    При любой ошибке Pydantic выбрасывает ValidationError — оркестратор
    перехватывает и продолжает без шага Pydantic, чтобы не терять позиции.
    """
    warnings: list[str] = []
    items_in = data.get("items") or []
    items: list[ReceiptItem] = []
    for i, raw in enumerate(items_in):
        items.append(ReceiptItem.model_validate(_flat_item_to_mapping(raw, i)))

    ts = data.get("tax_status")
    if ts is not None and ts not in ("taxable", "tax_exempt", "unknown"):
        ts = None
    payload = {
        "organization": data.get("organization"),
        "inn": data.get("inn"),
        "kpp": data.get("kpp"),
        "date": data.get("date"),
        "receipt_number": data.get("receipt_number"),
        "items": items,
        "total": data.get("total"),
        "total_vat": data.get("total_vat"),
        "tax_status": ts,
        "payment_method": data.get("payment_method"),
        "currency": data.get("currency"),
    }
    validated = ReceiptData.model_validate(payload)
    return validated, warnings


def receipt_data_to_dict(receipt: ReceiptData) -> dict[str, Any]:
    """Канонический плоский dict для ResultBuilder и экспорта."""
    return {
        "organization": receipt.organization,
        "inn": receipt.inn,
        "kpp": receipt.kpp,
        "date": receipt.date,
        "receipt_number": receipt.receipt_number,
        "total": receipt.total,
        "total_vat": receipt.total_vat,
        "tax_status": receipt.tax_status,
        "payment_method": receipt.payment_method,
        "currency": receipt.currency,
        "items": [
            {
                "name": item.name,
                "price_per_unit": item.price_per_unit,
                "quantity": item.quantity,
                "total_price": item.total_price,
                "vat_rate": item.vat_rate,
                "vat_amount": item.vat_amount,
                "unit": item.unit,
            }
            for item in receipt.items
        ],
    }
