from __future__ import annotations

import os
import tempfile
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from api.auth import verify_api_key
from api.exporters.commerceml import build_commerceml
from api.exporters.excel_1c import build_excel_1c
from src.storage.session_store import session_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _safe_remove_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def _normalize_date(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            try:
                return datetime.fromisoformat(raw).date().isoformat()
            except ValueError:
                return None
    return None


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return parsed


def _prepare_receipt_for_1c(payload: dict) -> dict:
    receipt = payload.get("receipt", {}) or {}
    merchant = payload.get("merchant", {}) or {}
    totals = payload.get("totals", {}) or {}
    taxes = payload.get("taxes", {}) or {}
    items = payload.get("items", []) or []

    mapped_items = []
    for item in items:
        line = item if isinstance(item, dict) else {}
        mapped_items.append(
            {
                "name": str(line.get("name") or ""),
                "quantity": _safe_float(line.get("quantity"), default=1.0) or 1.0,
                "price": _safe_float(line.get("price") if line.get("price") is not None else line.get("price_per_unit")),
                "amount": _safe_float(line.get("amount") if line.get("amount") is not None else line.get("total_price")),
                "vat_rate": line.get("vat_rate") if line.get("vat_rate") is not None else "Без НДС",
                "vat_amount": _safe_float(line.get("vat_amount")),
            }
        )

    return {
        "id": str(payload.get("id") or ""),
        "date": _normalize_date(receipt.get("date")),
        "organization": str(merchant.get("organization") or ""),
        "inn": str(merchant.get("inn") or ""),
        "total": _safe_float(totals.get("total")),
        "total_vat": _safe_float(totals.get("total_vat") if totals.get("total_vat") is not None else taxes.get("total_vat")),
        "items_count": len(mapped_items),
        "items": mapped_items,
    }


def _parse_query_date(date_raw: str | None) -> date | None:
    if date_raw is None:
        return None
    value = date_raw.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Некорректная дата: {date_raw}") from exc


def _filter_by_date(receipts: list[dict], date_from: date | None, date_to: date | None) -> list[dict]:
    if date_from is None and date_to is None:
        return receipts

    filtered = []
    for item in receipts:
        date_str = _normalize_date((item.get("receipt", {}) or {}).get("date"))
        if not date_str:
            continue
        try:
            value = date.fromisoformat(date_str)
        except ValueError:
            continue
        if date_from and value < date_from:
            continue
        if date_to and value > date_to:
            continue
        filtered.append(item)
    return filtered


@router.get("/receipts")
async def get_receipts(
    user_id: int = Query(...),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    start = _parse_query_date(date_from)
    end = _parse_query_date(date_to)

    receipts = await session_store.get_receipts(user_id)
    filtered = _filter_by_date(receipts, start, end)
    total = len(filtered)
    page = filtered[offset : offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "receipts": [_prepare_receipt_for_1c(item if isinstance(item, dict) else {}) for item in page],
    }


@router.get("/receipts/{receipt_id}")
async def get_receipt(receipt_id: str):
    receipt = await session_store.get_receipt_by_id(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Чек не найден")
    return _prepare_receipt_for_1c(receipt if isinstance(receipt, dict) else {})


@router.get("/receipts/export/xml")
async def export_receipts_xml(
    user_id: int = Query(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    start = _parse_query_date(date_from)
    end = _parse_query_date(date_to)
    receipts = await session_store.get_receipts(user_id)
    filtered = _filter_by_date(receipts, start, end)
    xml_bytes = build_commerceml(filtered)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=receipt_export_1c.xml"},
    )


@router.get("/receipts/export/xlsx")
async def export_receipts_xlsx(
    user_id: int = Query(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    start = _parse_query_date(date_from)
    end = _parse_query_date(date_to)
    receipts = await session_store.get_receipts(user_id)
    filtered = _filter_by_date(receipts, start, end)

    fd, out_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    build_excel_1c(filtered, out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="receipt_export_1c.xlsx",
        background=BackgroundTask(_safe_remove_file, out_path),
    )
