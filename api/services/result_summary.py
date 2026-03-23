"""Helpers for compact accountant-friendly receipt summary."""

from __future__ import annotations


def _is_present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def build_receipt_summary(result: dict) -> dict:
    """Build compact summary from canonical parser result."""
    receipt = result.get("receipt", {}) or {}
    merchant = result.get("merchant", {}) or {}
    totals = result.get("totals", {}) or {}
    taxes = result.get("taxes", {}) or {}
    items = result.get("items", []) or []

    date = receipt.get("date")
    receipt_number = receipt.get("receipt_number")
    seller = merchant.get("organization")
    seller_inn = merchant.get("inn")
    total = totals.get("total")
    total_vat = taxes.get("total_vat")
    items_count = len(items)

    warnings: list[str] = []
    if not _is_present(date):
        warnings.append("Не распознана дата")
    if not _is_present(seller):
        warnings.append("Не распознан продавец")
    if not _is_present(seller_inn):
        warnings.append("Не распознан ИНН продавца")
    if items_count == 0:
        warnings.append("Не распознаны товарные позиции")
    if not _is_present(total):
        warnings.append("Не распознана итоговая сумма")

    is_ready = (
        _is_present(date)
        and _is_present(seller)
        and items_count > 0
        and _is_present(total)
    )

    return {
        "date": date,
        "receipt_number": receipt_number,
        "seller": seller,
        "seller_inn": seller_inn,
        "total": total,
        "total_vat": total_vat,
        "items_count": items_count,
        "status": "ready" if is_ready else "review",
        "warnings": warnings,
    }
