"""
Статус налога по чеку: taxable / tax_exempt / unknown.
Только эвристики по явным полям и тексту (без расчёта налога).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Literal, Optional

TaxStatus = Literal["taxable", "tax_exempt", "unknown"]

def _doc_level_exempt_from_text(text: str) -> bool:
    t = text.lower()
    # «Сумма без НДС» (ООО Агат и аналоги)
    if re.search(r"сумм[аы]\s+без\s+ндс", t):
        return True
    if re.search(r"ндс\s+не\s+облагается|не\s+облагается\s+ндс|ндс\s*:\s*не\s+облагается", t):
        return True
    if re.search(r"(итог|total|сумм[аы]|amount)\s+без\s+ндс", t):
        return True
    if re.search(r"no\s+vat|tax\s*exempt|zero[\s-]*rated|vat\s*exempt", t, re.I):
        return True
    return False

_ITEM_EXEMPT_RATE = re.compile(
    r"(без\s+ндс|не\s+облагается|no\s+vat|exempt|0\s*%|ндс\s*0|gst\s*0|vat\s*0)",
    re.I,
)


def _text_blob_from_flat(flat: Dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("organization", "receipt_number", "notes", "footer", "summary", "tax_note"):
        v = flat.get(key)
        if v is not None:
            parts.append(str(v))
    for it in flat.get("items") or []:
        if not isinstance(it, dict):
            continue
        for k in ("name", "vat_rate", "description"):
            v = it.get(k)
            if v is not None:
                parts.append(str(v))
    return " ".join(parts)


def _all_items_exempt_rates(flat: Dict[str, Any]) -> bool:
    items = flat.get("items") or []
    if not items:
        return False
    for it in items:
        if not isinstance(it, dict):
            return False
        vr = it.get("vat_rate")
        if vr is None or (isinstance(vr, str) and not str(vr).strip()):
            return False
        if not _ITEM_EXEMPT_RATE.search(str(vr)):
            return False
    return True


def infer_tax_status(flat: Dict[str, Any], raw: Optional[Dict[str, Any]] = None) -> TaxStatus:
    """
    Определяет tax_status без изменения flat.

    Приоритет:
    1) total_vat > 0 -> taxable
    2) явные маркеры tax-exempt в тексте flat/raw
    3) все позиции с явной освобождённой ставкой и нет положительного total_vat
    4) поле tax_status от модели: принимаются только tax_exempt и unknown (taxable без суммы — игнорируем)
    5) unknown
    """
    tv = flat.get("total_vat")
    try:
        tv_num = float(tv) if tv is not None else None
    except (TypeError, ValueError):
        tv_num = None

    if tv_num is not None and tv_num > 0:
        return "taxable"

    blob = _text_blob_from_flat(flat)
    if raw is not None:
        try:
            blob = blob + " " + json.dumps(raw, ensure_ascii=False)
        except (TypeError, ValueError):
            pass

    if _doc_level_exempt_from_text(blob):
        return "tax_exempt"

    if _all_items_exempt_rates(flat) and (tv_num is None or tv_num == 0):
        return "tax_exempt"

    # Подсказка модели: tax_exempt / unknown принимаем; «taxable» без суммы налога — нет.
    hint = flat.get("tax_status")
    if hint == "tax_exempt":
        if tv_num is not None and tv_num > 0:
            return "taxable"
        return "tax_exempt"
    if hint == "unknown":
        return "unknown"

    return "unknown"


def enrich_flat_tax_status(flat: Dict[str, Any], raw: Optional[Dict[str, Any]] = None) -> TaxStatus:
    """Записывает flat['tax_status'] по правилам infer."""
    status = infer_tax_status(flat, raw)
    flat["tax_status"] = status
    return status


def raw_suggests_tax_amount_omitted(flat: Dict[str, Any], raw: Optional[Dict[str, Any]]) -> bool:
    """
    True, если в сыром JSON есть признаки итоговой суммы налога (VAT/GST/НДС + число),
    а в flat нет положительного total_vat и статус не tax-exempt.
    Используется для quality gate / fallback (variant C).
    """
    if not raw:
        return False
    status = infer_tax_status(flat, raw)
    if status == "tax_exempt":
        return False
    tv = flat.get("total_vat")
    try:
        if tv is not None and float(tv) > 0:
            return False
    except (TypeError, ValueError):
        pass

    try:
        blob = json.dumps(raw, ensure_ascii=False)
    except (TypeError, ValueError):
        return False
    blob_l = blob.lower()
    if re.search(r"сумм[аы]\s+без\s+ндс|ндс\s+не\s+облагается|не\s+облагается", blob_l):
        return False

    # Число с копейками рядом с налоговой меткой (как VAT/вкл.НДС 301.15)
    if re.search(
        r"(vat|gst|tax|ндс|вкл\.?\s*ндс|total\s+gst|total\s+vat)[^\"\d]{0,60}\d{2,}[.,]\d{2}",
        blob_l,
        re.I,
    ):
        return True
    if re.search(
        r"\d{2,}[.,]\d{2}[^\"\w]{0,40}(vat|gst|tax|ндс)(?![a-zа-яё])",
        blob_l,
        re.I,
    ):
        return True
    return False
