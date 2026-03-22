"""
Базовые фикстуры и конфигурация pytest для тестов.
"""

import os
import sys
from pathlib import Path

import pytest

# Добавляем корень проекта в sys.path для импортов из src/
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Путь к тестовым чекам
TEST_RECEIPTS_DIR = Path(__file__).parent / "test_receipts"


@pytest.fixture
def test_receipts_path() -> Path:
    """Возвращает путь к директории с тестовыми чеками."""
    return TEST_RECEIPTS_DIR


@pytest.fixture
def sample_receipt_path(test_receipts_path: Path) -> Path:
    """Возвращает путь к первому доступному тестовому чеку."""
    receipts = list(test_receipts_path.glob("*.jpg")) + list(test_receipts_path.glob("*.png"))
    if receipts:
        return receipts[0]
    pytest.skip("Нет доступных тестовых изображений чеков")


@pytest.fixture
def sample_flat_receipt_data() -> dict:
    """Пример плоских данных чека для тестирования."""
    return {
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


@pytest.fixture
def sample_raw_receipt_data() -> dict:
    """Пример сырых данных чека (до постобработки)."""
    return {
        "organization": "ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ",
        "inn": "ИНН: 781603445844",
        "date": "19.02.2026",
        "receipt_number": "Чек № 123456",
        "items": [
            {
                "name": "Товар 1",
                "price_per_unit": "119.0",
                "quantity": "1.000",
                "total_price": "119.0",
                "vat_rate": "20%",
                "vat_amount": "19.83"
            }
        ],
        "total": "238.0",
        "total_vat": "39.66"
    }
