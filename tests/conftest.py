"""Common pytest fixtures for API/CLI/export tests."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_receipt_result() -> dict:
    return {
        "receipt": {"receipt_number": "12345", "date": "2026-03-20"},
        "merchant": {"organization": "ООО Ромашка", "inn": "7701234567"},
        "totals": {"total": 1500.50},
        "taxes": {"total_vat": 250.08},
        "items": [
            {
                "name": "Товар 1",
                "price_per_unit": 500.25,
                "quantity": 3,
                "total_price": 1500.75,
                "vat_rate": "20%",
                "vat_amount": 250.12,
            }
        ],
    }


@pytest.fixture
def api_client() -> TestClient:
    from api.app import app

    return TestClient(app)
