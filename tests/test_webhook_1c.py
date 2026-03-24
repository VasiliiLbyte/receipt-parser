import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services.webhook_1c import push_to_1c_webhook
from src.storage.session_store import session_store


@pytest.mark.asyncio
async def test_push_disabled_when_no_url(monkeypatch):
    monkeypatch.setenv("WEBHOOK_1C_URL", "")

    class _ShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise AssertionError("HTTP client must not be created when webhook URL is empty")

    monkeypatch.setattr("api.services.webhook_1c.aiohttp.ClientSession", _ShouldNotBeCalled)
    result = await push_to_1c_webhook({"receipt": {"date": "2026-03-24"}})
    assert result is False


def test_file_exchange_creates_file(tmp_path, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DIR", str(tmp_path / "exchange"))
    session_store.db_path = str(tmp_path / "sessions.db")

    async def _prepare() -> None:
        await session_store.close()
        await session_store.init()
        await session_store.add_receipt(
            77,
            {
                "receipt": {"receipt_number": "R-100", "date": "2026-03-24"},
                "merchant": {"organization": "ООО Ромашка", "inn": "7701234567"},
                "totals": {"total": 1500.0},
                "taxes": {"total_vat": 250.0},
                "items": [{"name": "Товар", "quantity": 1, "price_per_unit": 1500.0, "total_price": 1500.0}],
            },
        )

    import asyncio

    asyncio.run(_prepare())
    client = TestClient(app)
    response = client.get("/exchange/drop", params={"user_id": 77, "fmt": "xml"})
    assert response.status_code == 200

    payload = response.json()
    file_path = tmp_path / "exchange" / payload["file"]
    assert file_path.exists()
    assert file_path.suffix == ".xml"
