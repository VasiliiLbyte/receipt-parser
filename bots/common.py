"""
Shared helpers for all bot implementations (Telegram, MAX, etc.).

Uses aiohttp to talk to the FastAPI backend.
"""

from __future__ import annotations

import aiohttp


class BackendError(Exception):
    """Raised when the backend returns a non-2xx response."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Backend HTTP {status}: {detail}")


async def call_parse(file_bytes: bytes, filename: str, backend_url: str) -> dict:
    """POST /parse with multipart file upload, return parsed result dict."""
    url = f"{backend_url.rstrip('/')}/parse"
    form = aiohttp.FormData()
    form.add_field("file", file_bytes, filename=filename, content_type="application/octet-stream")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise BackendError(resp.status, text)
            return await resp.json()


async def call_export(results: list, fmt: str, backend_url: str) -> bytes:
    """POST /export/{fmt} with JSON body, return raw file bytes."""
    url = f"{backend_url.rstrip('/')}/export/{fmt}"
    payload = {"results": results}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise BackendError(resp.status, text)
            return await resp.read()


def format_summary(summary: dict) -> str:
    """Human-readable summary for a chat message."""
    date = summary.get("date") or "—"
    receipt_number = summary.get("receipt_number") or "—"
    seller = summary.get("seller") or "—"
    seller_inn = summary.get("seller_inn") or "—"
    total = summary.get("total")
    total_vat = summary.get("total_vat")
    items_count = summary.get("items_count", 0)
    status = summary.get("status", "review")
    warnings = summary.get("warnings", [])

    total_str = f"{total:.2f} ₽" if total is not None else "—"
    vat_str = f"{total_vat:.2f} ₽" if total_vat is not None else "—"

    status_line = "✅ Готово к выгрузке" if status == "ready" else "⚠️ Проверить вручную"

    lines = [
        f"📅 Дата: {date}",
        f"🧾 Номер чека: {receipt_number}",
        f"🏪 Продавец: {seller}",
        f"🆔 ИНН: {seller_inn}",
        f"💰 Сумма: {total_str}",
        f"📊 НДС: {vat_str}",
        f"📦 Позиций: {items_count}",
        "",
        status_line,
    ]

    if warnings:
        lines.append("")
        lines.append("⚠️ Предупреждения:")
        for w in warnings:
            lines.append(f"  • {w}")

    return "\n".join(lines)


def get_export_help_text() -> str:
    return (
        "📋 Как загрузить в 1С:\n"
        "1. Скачайте Excel-файл.\n"
        "2. В 1С откройте загрузку из Excel/табличного документа.\n"
        "3. Укажите лист «1C_Импорт».\n"
        "4. Сопоставьте колонки один раз и сохраните шаблон.\n"
        "5. Проверьте суммы и НДС перед проведением."
    )
