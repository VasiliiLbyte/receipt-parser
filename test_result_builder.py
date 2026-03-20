#!/usr/bin/env python3
"""
Тестирование ResultBuilder канонического результата.

Этот тест не влияет на поведение парсинга/валидации, а лишь фиксирует
маппинг плоского доменного dict -> канонический nested JSON.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.result_builder import ResultBuilder, CANONICAL_SCHEMA_VERSION


def test_result_builder_mapping():
    flat = {
        "receipt_number": "123456",
        "organization": "ИП ТЕСТ ТЕСТОВИЧ",
        "inn": "781603445844",
        "date": "2026-02-19",
        "total": 1234.56,
        "total_vat": 205.76,
        "items": [
            {
                "name": "Товар с НДС 20%",
                "price_per_unit": 100.5,
                "quantity": 2.0,
                "total_price": 201.0,
                "vat_rate": "20%",
                "vat_amount": 33.5,
            }
        ],
    }

    warnings = [{"code": "DATE_UNPARSABLE", "severity": "warning", "message": "x"}]
    providers_used = ["openai", "openrouter"]
    passes = [{"name": "pass1", "status": "ok"}, {"name": "pass2", "status": "ok"}]
    raw_pass1 = {"raw": True}

    canonical = ResultBuilder.build_from_flat(
        flat,
        warnings=warnings,
        raw_pass1_provider_json=raw_pass1,
        raw_pass2_provider_json=None,
        providers_used=providers_used,
        passes=passes,
    )

    assert canonical["meta"]["schema_version"] == CANONICAL_SCHEMA_VERSION
    assert canonical["receipt"]["receipt_number"] == "123456"
    assert canonical["receipt"]["date"] == "2026-02-19"
    assert canonical["merchant"]["organization"] == "ИП ТЕСТ ТЕСТОВИЧ"
    assert canonical["merchant"]["inn"] == "781603445844"
    assert canonical["totals"]["total"] == 1234.56
    assert canonical["taxes"]["total_vat"] == 205.76
    assert len(canonical["items"]) == 1
    assert canonical["items"][0]["name"] == "Товар с НДС 20%"
    assert canonical["items"][0]["total_price"] == 201.0
    assert canonical["warnings"] == warnings
    assert canonical["raw"]["pass1_provider_json"] == raw_pass1

    return True


if __name__ == "__main__":
    ok = test_result_builder_mapping()
    print("✅ test_result_builder_mapping" if ok else "❌ test_result_builder_mapping")
    sys.exit(0 if ok else 1)

