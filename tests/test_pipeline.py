#!/usr/bin/env python3
"""
Интеграционный тест полного pipeline (OpenAI Vision + нормализация + валидация).

Делает реальный API-вызов. Запуск: pytest -m slow tests/test_pipeline.py
"""

from __future__ import annotations

import os
import sys

import pytest

from src.config import OPENAI_API_KEY
from src.openai_client import extract_receipt_data_from_image
from src.vision_utils import prepare_image


def _api_configured() -> bool:
    return bool(OPENAI_API_KEY and OPENAI_API_KEY != "sk-your-openai-api-key-here")


@pytest.mark.slow
def test_pipeline_end_to_end(sample_receipt_path):
    """Один проход pipeline; проверяется форма канонического ответа."""
    if not _api_configured():
        pytest.skip("OPENAI_API_KEY не задан или плейсхолдер из .env.example")

    image_path = str(sample_receipt_path)
    print(f"🧪 Pipeline: {image_path}")

    prepared_path = prepare_image(image_path)
    print(f"✅ Подготовлено: {prepared_path}")

    result = extract_receipt_data_from_image(prepared_path)

    assert result is not None, "pipeline вернул None при валидном ключе и изображении"
    assert "receipt" in result and "merchant" in result
    assert "items" in result and isinstance(result["items"], list)
    assert "totals" in result and "taxes" in result
    assert "meta" in result
    assert result["meta"].get("schema_version")


def main():
    if len(sys.argv) < 2:
        print("Использование: python -m pytest -m slow tests/test_pipeline.py")
        print("Или: python tests/test_pipeline.py <путь_к_изображению>")
        return 1

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"❌ Файл не найден: {path}")
        return 1

    if not _api_configured():
        print("❌ Задайте OPENAI_API_KEY в .env")
        return 1

    prepared = prepare_image(path)
    result = extract_receipt_data_from_image(prepared)
    if result is None:
        print("❌ Pipeline вернул None")
        return 1
    print("✅ Ключи результата:", sorted(result.keys()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
