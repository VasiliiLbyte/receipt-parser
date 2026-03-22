"""
Финализация номера чека только для экспорта/канонического ответа.

Промежуточные этапы pipeline работают с None или сырым значением;
здесь — единое правило «нет надёжного номера → Б/Н».
"""

from __future__ import annotations

import re
from typing import Literal, Optional, Tuple, Union

ReceiptNumberStatus = Literal["parsed", "unreadable", "missing"]

MISSING_DISPLAY = "Б/Н"

# Только служебные символы и X (типичный плейсхолдер), без цифр и «нормальных» букв
_JUNK_ONLY_PATTERN = re.compile(r"^[\s?\-_.,:;Xx]+$", re.UNICODE)


def _coerce_to_str(value: Union[str, None, int, float]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def _has_plausible_content(s: str) -> bool:
    """
    True, если строка похожа на реальный номер:
    - есть цифра; или
    - есть буква не X/x; или
    - есть буквы/цифры в смеси, но не «только мусор» из ?, -, _, X и пунктуации.
    """
    if any(ch.isdigit() for ch in s):
        return True
    if _JUNK_ONLY_PATTERN.fullmatch(s):
        return False
    return any(ch.isalnum() for ch in s)


def finalize_receipt_number_with_status(
    value: Union[str, None, int, float],
) -> Tuple[str, ReceiptNumberStatus]:
    """
    Возвращает (строка для ответа, статус).

    Статусы:
    - missing: None или пусто после trim
    - unreadable: есть символы, но нет ни одной буквы/цифры (типичный OCR-мусор)
    - parsed: есть правдоподобное содержимое
    """
    coerced = _coerce_to_str(value)
    if coerced is None:
        return MISSING_DISPLAY, "missing"

    s = coerced.strip()
    if not s:
        return MISSING_DISPLAY, "missing"

    if not _has_plausible_content(s):
        return MISSING_DISPLAY, "unreadable"

    return s, "parsed"


def finalize_receipt_number(value: Union[str, None, int, float]) -> str:
    """Только строка для канонического поля receipt.receipt_number."""
    out, _ = finalize_receipt_number_with_status(value)
    return out
