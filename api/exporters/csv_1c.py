"""
CSV exporter in 1C-compatible format.

Same columns as "1C_Импорт" sheet in excel_1c.
Semicolon-delimited, utf-8-sig encoding.
"""

import csv
import io

IMPORT_COLUMNS_1C = [
    "Дата документа",
    "Номер документа-основания",
    "Продавец",
    "ИНН продавца",
    "Вид документа",
    "Номенклатура",
    "Ед. изм.",
    "Количество",
    "Цена",
    "Сумма",
    "Ставка НДС",
    "Сумма НДС",
    "Комментарий",
]


def _fmt(value) -> str:
    if value is None:
        return ""
    return str(value)


def _pick(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_inn(inn_raw):
    if inn_raw is None:
        return None
    if isinstance(inn_raw, str):
        return inn_raw
    if isinstance(inn_raw, (int, float)):
        try:
            return str(int(float(inn_raw)))
        except (TypeError, ValueError, OverflowError):
            return str(inn_raw)
    return str(inn_raw)


def _is_exportable_item(item: dict) -> bool:
    name = str(item.get("name") or "").strip()
    return bool(name)


def build_csv_1c(results: list[dict]) -> str:
    """
    Формирует CSV-строку в формате для импорта в 1С.

    Returns:
        Содержимое CSV файла как строка (utf-8-sig).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(IMPORT_COLUMNS_1C)

    for r in results:
        receipt = r.get("receipt", {}) or {}
        merchant = r.get("merchant", {}) or {}
        items = r.get("items", []) or []
        export_items = [item for item in items if isinstance(item, dict) and _is_exportable_item(item)]

        date = receipt.get("date", "") or ""
        receipt_number = _pick(
            receipt.get("receipt_number"),
            r.get("receipt_number"),
        ) or ""
        inn = _normalize_inn(merchant.get("inn")) or ""
        organization = merchant.get("organization", "") or ""

        if not export_items:
            writer.writerow(
                [
                    date,
                    receipt_number,
                    organization,
                    inn,
                    "Кассовый чек",
                    "Нет данных",
                    "шт",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "Распознано из фото чека",
                ]
            )
            continue

        for item in export_items:
            writer.writerow(
                [
                    date,
                    receipt_number,
                    organization,
                    inn,
                    "Кассовый чек",
                    item.get("name", ""),
                    "шт",
                    _fmt(_pick(item.get("quantity"), item.get("qty"), item.get("count"))),
                    _fmt(_pick(item.get("price_per_unit"), item.get("price"), item.get("unit_price"))),
                    _fmt(_pick(item.get("total_price"), item.get("total"), item.get("amount"))),
                    _pick(item.get("vat_rate"), item.get("tax_rate"), item.get("nds_rate")) or "",
                    _fmt(_pick(item.get("vat_amount"), item.get("tax_amount"), item.get("nds_amount"))),
                    "Распознано из фото чека",
                ]
            )

    return buf.getvalue()


def build_csv_1c_bytes(results: list[dict]) -> bytes:
    """Returns CSV content as bytes with utf-8-sig BOM."""
    content = build_csv_1c(results)
    return content.encode("utf-8-sig")
