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

        date = receipt.get("date", "") or ""
        receipt_number = receipt.get("receipt_number", "") or ""
        inn = merchant.get("inn", "") or ""
        organization = merchant.get("organization", "") or ""

        if not items:
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

        for item in items:
            writer.writerow(
                [
                    date,
                    receipt_number,
                    organization,
                    inn,
                    "Кассовый чек",
                    item.get("name", ""),
                    "шт",
                    _fmt(item.get("quantity")),
                    _fmt(item.get("price_per_unit")),
                    _fmt(item.get("total_price")),
                    item.get("vat_rate", ""),
                    _fmt(item.get("vat_amount")),
                    "Распознано из фото чека",
                ]
            )

    return buf.getvalue()


def build_csv_1c_bytes(results: list[dict]) -> bytes:
    """Returns CSV content as bytes with utf-8-sig BOM."""
    content = build_csv_1c(results)
    return content.encode("utf-8-sig")
