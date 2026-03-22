"""Финализация receipt_number для канонического ответа."""

from src.pipeline.normalize import normalize_receipt_number
from src.pipeline.receipt_number_finalize import (
    finalize_receipt_number,
    finalize_receipt_number_with_status,
)


def test_finalize_none():
    assert finalize_receipt_number(None) == "Б/Н"
    assert finalize_receipt_number_with_status(None)[1] == "missing"


def test_finalize_empty():
    assert finalize_receipt_number("") == "Б/Н"
    assert finalize_receipt_number("   ") == "Б/Н"
    assert finalize_receipt_number_with_status("  ")[1] == "missing"


def test_finalize_junk_question_marks():
    assert finalize_receipt_number("???") == "Б/Н"
    assert finalize_receipt_number_with_status("???")[1] == "unreadable"


def test_finalize_junk_dashes():
    assert finalize_receipt_number("---") == "Б/Н"
    assert finalize_receipt_number_with_status("---_--")[1] == "unreadable"


def test_finalize_placeholder_xxx():
    assert finalize_receipt_number("XXX") == "Б/Н"
    assert finalize_receipt_number_with_status("x-x-x")[1] == "unreadable"


def test_finalize_digits():
    assert finalize_receipt_number("12345") == "12345"
    assert finalize_receipt_number_with_status("12345")[1] == "parsed"


def test_finalize_alnum_hyphen():
    assert finalize_receipt_number("AB-129") == "AB-129"
    assert finalize_receipt_number_with_status("AB-129")[1] == "parsed"


def test_after_normalize_receipt_prefix():
    raw = "Receipt # 12345"
    normalized = normalize_receipt_number(raw)
    assert normalized == "12345"
    assert finalize_receipt_number(normalized) == "12345"
    assert finalize_receipt_number_with_status(normalized)[1] == "parsed"


def test_short_numeric_ok():
    assert finalize_receipt_number("1") == "1"
    assert finalize_receipt_number_with_status("1")[1] == "parsed"


def test_int_coercion():
    assert finalize_receipt_number(42) == "42"
    assert finalize_receipt_number_with_status(42)[1] == "parsed"
