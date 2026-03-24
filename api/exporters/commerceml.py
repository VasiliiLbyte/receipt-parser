"""
CommerceML 2.09 exporter for 1C-compatible XML import.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime
import xml.etree.ElementTree as ET


DEFAULT_COMMERCEML_VERSION = "2.09"


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value)


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


def _format_money(value) -> str:
    return f"{_safe_float(value):.2f}"


def _format_quantity(value) -> str:
    qty = _safe_float(value, default=1.0)
    if qty == 0:
        qty = 1.0
    return f"{qty:g}"


def _normalize_inn(inn_raw) -> str:
    raw = _safe_text(inn_raw).strip()
    digits_only = "".join(ch for ch in raw if ch.isdigit())
    if len(digits_only) in (10, 12):
        return digits_only
    return ""


def _normalize_date(date_raw) -> str:
    if date_raw in (None, ""):
        return ""
    if isinstance(date_raw, datetime):
        return date_raw.date().isoformat()
    if isinstance(date_raw, date):
        return date_raw.isoformat()
    if isinstance(date_raw, str):
        candidate = date_raw.strip()
        if not candidate:
            return ""
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            try:
                return datetime.fromisoformat(candidate).date().isoformat()
            except ValueError:
                return ""
    return ""


def _pick(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _add_text_node(parent: ET.Element, tag: str, value: str) -> ET.Element:
    node = ET.SubElement(parent, tag)
    node.text = value
    return node


def build_commerceml(results: list[dict]) -> bytes:
    """
    Принимает список результатов парсинга чеков.
    Возвращает bytes — UTF-8 XML в формате CommerceML 2.09.
    Каждый чек -> отдельный <Документ>.
    """
    version = os.getenv("COMMERCEML_VERSION", DEFAULT_COMMERCEML_VERSION)
    today = date.today().isoformat()

    root = ET.Element(
        "КоммерческаяИнформация",
        {
            "ВерсияСхемы": _safe_text(version) or DEFAULT_COMMERCEML_VERSION,
            "ДатаФормирования": today,
        },
    )

    for index, result in enumerate(results, start=1):
        payload = result if isinstance(result, dict) else {}
        receipt = payload.get("receipt", {}) or {}
        merchant = payload.get("merchant", {}) or {}
        items = payload.get("items", []) or []
        totals = payload.get("totals", {}) or {}
        taxes = payload.get("taxes", {}) or {}

        document = ET.SubElement(root, "Документ")
        _add_text_node(document, "Ид", str(uuid.uuid4()))
        _add_text_node(document, "Номер", str(index))
        _add_text_node(document, "Дата", _normalize_date(receipt.get("date")))
        _add_text_node(document, "ХозяйственнаяОперация", "Авансовый отчет")
        _add_text_node(document, "Роль", "Продавец")
        _add_text_node(document, "Валюта", "RUB")

        counterparties = ET.SubElement(document, "Контрагенты")
        counterparty = ET.SubElement(counterparties, "Контрагент")
        _add_text_node(counterparty, "Наименование", _safe_text(merchant.get("organization")))
        _add_text_node(counterparty, "ИНН", _normalize_inn(merchant.get("inn")))
        _add_text_node(counterparty, "Роль", "Продавец")

        goods = ET.SubElement(document, "Товары")
        for item in items:
            line = item if isinstance(item, dict) else {}
            product = ET.SubElement(goods, "Товар")
            _add_text_node(product, "Наименование", _safe_text(line.get("name")))
            _add_text_node(
                product,
                "Количество",
                _format_quantity(_pick(line.get("quantity"), line.get("qty"), line.get("count"))),
            )
            _add_text_node(
                product,
                "ЦенаЗаЕдиницу",
                _format_money(_pick(line.get("price"), line.get("price_per_unit"), line.get("unit_price"))),
            )
            _add_text_node(
                product,
                "Сумма",
                _format_money(_pick(line.get("amount"), line.get("total_price"), line.get("total"))),
            )
            _add_text_node(product, "СтавкаНДС", _safe_text(line.get("vat_rate")) or "Без НДС")
            _add_text_node(
                product,
                "СуммаНДС",
                _format_money(_pick(line.get("vat_amount"), line.get("tax_amount"), line.get("nds_amount"))),
            )

        _add_text_node(document, "Сумма", _format_money(totals.get("total")))
        _add_text_node(document, "СуммаНДС", _format_money(_pick(totals.get("total_vat"), taxes.get("total_vat"))))

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes
