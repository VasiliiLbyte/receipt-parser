from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from api.exporters.commerceml import build_commerceml
from api.exporters.csv_1c import build_csv_1c_bytes
from api.exporters.excel_1c import build_excel_1c
from src.storage.session_store import session_store

router = APIRouter()


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


def _normalize_receipt_date(receipt: dict) -> date | None:
    receipt_block = (receipt.get("receipt", {}) or {}) if isinstance(receipt, dict) else {}
    raw = receipt_block.get("date")
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return None
    return None


def _filter_by_date(receipts: list[dict], date_from: date | None, date_to: date | None) -> list[dict]:
    if date_from is None and date_to is None:
        return receipts

    filtered: list[dict] = []
    for receipt in receipts:
        value = _normalize_receipt_date(receipt if isinstance(receipt, dict) else {})
        if value is None:
            continue
        if date_from and value < date_from:
            continue
        if date_to and value > date_to:
            continue
        filtered.append(receipt)
    return filtered


def _exchange_dir() -> Path:
    base = os.getenv("EXCHANGE_DIR", "./exchange/").strip() or "./exchange/"
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.get("/exchange/drop")
async def exchange_drop(
    user_id: int = Query(...),
    fmt: str = Query(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    fmt_normalized = fmt.lower().strip()
    if fmt_normalized not in {"xml", "xlsx", "csv"}:
        raise HTTPException(status_code=422, detail="fmt должен быть одним из: xml, xlsx, csv")

    start = _parse_query_date(date_from)
    end = _parse_query_date(date_to)
    receipts = await session_store.get_receipts(user_id)
    filtered = _filter_by_date(receipts, start, end)

    exchange_path = _exchange_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"receipts_{timestamp}.{fmt_normalized}"
    out_path = exchange_path / filename

    if fmt_normalized == "xml":
        out_path.write_bytes(build_commerceml(filtered))
    elif fmt_normalized == "csv":
        out_path.write_bytes(build_csv_1c_bytes(filtered))
    else:
        fd, temp_path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            build_excel_1c(filtered, temp_path)
            out_path.write_bytes(Path(temp_path).read_bytes())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return {"file": filename, "path": str(out_path.resolve())}


@router.get("/exchange/files")
async def exchange_files():
    exchange_path = _exchange_dir()
    files = []
    for file_path in sorted(exchange_path.glob("*")):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        files.append(
            {
                "file": file_path.name,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "size": stat.st_size,
            }
        )
    return {"files": files}
