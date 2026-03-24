import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.app import app
from src.storage.session_store import session_store


@pytest_asyncio.fixture
async def async_client(tmp_path):
    session_store.db_path = str(tmp_path / "sessions.db")
    await session_store.close()
    await session_store.init()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await session_store.close()


def _make_receipt(date_value: str, org: str = "ООО Ромашка") -> dict:
    return {
        "receipt": {"receipt_number": "R-1", "date": date_value},
        "merchant": {"organization": org, "inn": "7701234567"},
        "totals": {"total": 1500.0},
        "taxes": {"total_vat": 250.0},
        "items": [
            {
                "name": "Товар 1",
                "quantity": 2,
                "price": 500.0,
                "amount": 1000.0,
                "vat_rate": "20%",
                "vat_amount": 166.67,
            }
        ],
    }


@pytest.mark.asyncio
async def test_get_receipts_empty(async_client):
    response = await async_client.get("/api/v1/receipts", params={"user_id": 101})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["receipts"] == []


@pytest.mark.asyncio
async def test_get_receipts_with_data(async_client):
    await session_store.add_receipt(101, _make_receipt("2026-03-20", "ООО Первая"))
    await session_store.add_receipt(101, _make_receipt("2026-03-21", "ООО Вторая"))

    response = await async_client.get("/api/v1/receipts", params={"user_id": 101})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["receipts"]) == 2


@pytest.mark.asyncio
async def test_get_receipts_date_filter(async_client):
    await session_store.add_receipt(101, _make_receipt("2026-03-20"))
    await session_store.add_receipt(101, _make_receipt("2026-03-24"))
    await session_store.add_receipt(101, _make_receipt("2026-03-28"))

    response = await async_client.get(
        "/api/v1/receipts",
        params={
            "user_id": 101,
            "date_from": "2026-03-21",
            "date_to": "2026-03-27",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["receipts"][0]["date"] == "2026-03-24"


@pytest.mark.asyncio
async def test_api_key_required(async_client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-key")
    response = await async_client.get("/api/v1/receipts", params={"user_id": 101})
    assert response.status_code == 403

    response_ok = await async_client.get(
        "/api/v1/receipts",
        params={"user_id": 101},
        headers={"X-API-Key": "secret-key"},
    )
    assert response_ok.status_code == 200


@pytest.mark.asyncio
async def test_export_xml_returns_xml(async_client):
    await session_store.add_receipt(101, _make_receipt("2026-03-20"))
    response = await async_client.get("/api/v1/receipts/export/xml", params={"user_id": 101})
    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    assert "КоммерческаяИнформация" in response.text
