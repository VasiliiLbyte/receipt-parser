"""Интеграция variant C с моками провайдеров (без сети)."""

from unittest.mock import patch

import pytest

from src.pipeline.orchestrator import process_receipt_pipeline_variant_c


def _raw_ok():
    return {
        "organization": "ООО Ромашка",
        "inn": "781603445844",
        "date": "2026-02-19",
        "receipt_number": "42",
        "total": 201.0,
        "total_vat": 33.5,
        "items": [
            {
                "name": "Товар А",
                "price_per_unit": 100.5,
                "quantity": 2.0,
                "total_price": 201.0,
                "vat_rate": "20%",
                "vat_amount": 33.5,
            }
        ],
    }


@pytest.fixture
def no_openrouter_verify(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")


def test_variant_c_primary_good_openai_not_called(no_openrouter_verify, sample_receipt_path, monkeypatch):
    monkeypatch.setattr("src.pipeline.orchestrator.ENABLE_QUALITY_GATES", True)
    monkeypatch.setattr("src.pipeline.orchestrator.ENABLE_FALLBACK", True)
    monkeypatch.setattr("src.pipeline.orchestrator.openai_key_configured", lambda: True)

    with patch("src.providers.openrouter_extract.extract_raw_openrouter_data", return_value=_raw_ok()) as m_or:
        with patch("src.providers.openai.extract_raw_openai_data", return_value=_raw_ok()) as m_oa:
            out = process_receipt_pipeline_variant_c(str(sample_receipt_path))
    assert out is not None
    m_or.assert_called_once()
    m_oa.assert_not_called()
    assert out["meta"].get("pipeline_trace", {}).get("fallback_executed") is False


def test_variant_c_triggers_fallback_on_empty_primary(no_openrouter_verify, sample_receipt_path, monkeypatch):
    monkeypatch.setattr("src.pipeline.orchestrator.ENABLE_QUALITY_GATES", True)
    monkeypatch.setattr("src.pipeline.orchestrator.ENABLE_FALLBACK", True)
    monkeypatch.setattr("src.pipeline.orchestrator.openai_key_configured", lambda: True)

    with patch("src.providers.openrouter_extract.extract_raw_openrouter_data", return_value=None):
        with patch("src.providers.openai.extract_raw_openai_data", return_value=_raw_ok()) as m_oa:
            out = process_receipt_pipeline_variant_c(str(sample_receipt_path))
    assert out is not None
    m_oa.assert_called_once()
    assert out["meta"].get("pipeline_trace", {}).get("fallback_executed") is True
