"""
Pydantic request/response models for the API layer.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ---------- Shared item model ----------

class ItemOut(BaseModel):
    name: Optional[str] = None
    price_per_unit: Optional[float] = None
    quantity: Optional[float] = None
    total_price: Optional[float] = None
    vat_rate: Optional[str] = None
    vat_amount: Optional[float] = None


# ---------- /parse response ----------

class ReceiptBlock(BaseModel):
    receipt_number: Optional[str] = None
    date: Optional[str] = None

class MerchantBlock(BaseModel):
    organization: Optional[str] = None
    inn: Optional[str] = None

class TotalsBlock(BaseModel):
    total: Optional[float] = None

class TaxesBlock(BaseModel):
    total_vat: Optional[float] = None


class SummaryOut(BaseModel):
    date: Optional[str] = None
    receipt_number: Optional[str] = None
    seller: Optional[str] = None
    seller_inn: Optional[str] = None
    total: Optional[float] = None
    total_vat: Optional[float] = None
    items_count: int = 0
    status: str = "review"
    warnings: list[str] = Field(default_factory=list)


class ParseResponse(BaseModel):
    receipt: ReceiptBlock = Field(default_factory=ReceiptBlock)
    merchant: MerchantBlock = Field(default_factory=MerchantBlock)
    items: list[ItemOut] = Field(default_factory=list)
    totals: TotalsBlock = Field(default_factory=TotalsBlock)
    taxes: TaxesBlock = Field(default_factory=TaxesBlock)
    summary: SummaryOut = Field(default_factory=SummaryOut)
    meta: dict = Field(default_factory=dict)
    warnings: list[dict] = Field(default_factory=list)


# ---------- /export request ----------

class ExportRequest(BaseModel):
    """Body for POST /export/xlsx and POST /export/csv."""
    results: list[dict] = Field(..., min_length=1, description="Список канонических результатов чеков")
