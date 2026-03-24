import pytest

from src.storage.session_store import SessionStore


@pytest.mark.asyncio
async def test_add_and_get_receipts():
    store = SessionStore(":memory:")
    await store.init()

    await store.add_receipt(1, {"receipt_number": "1"})
    await store.add_receipt(1, {"receipt_number": "2"})
    await store.add_receipt(1, {"receipt_number": "3"})

    receipts = await store.get_receipts(1)
    assert len(receipts) == 3
    await store.close()


@pytest.mark.asyncio
async def test_clear_receipts():
    store = SessionStore(":memory:")
    await store.init()

    await store.add_receipt(1, {"receipt_number": "1"})
    await store.add_receipt(1, {"receipt_number": "2"})
    await store.clear_receipts(1)

    receipts = await store.get_receipts(1)
    assert receipts == []
    await store.close()


@pytest.mark.asyncio
async def test_different_users_isolated():
    store = SessionStore(":memory:")
    await store.init()

    await store.add_receipt(1, {"receipt_number": "u1-1"})
    await store.add_receipt(1, {"receipt_number": "u1-2"})
    await store.add_receipt(2, {"receipt_number": "u2-1"})

    user1 = await store.get_receipts(1)
    user2 = await store.get_receipts(2)

    assert len(user1) == 2
    assert len(user2) == 1
    assert user2[0]["receipt_number"] == "u2-1"
    await store.close()


@pytest.mark.asyncio
async def test_receipts_persist_after_reinit(tmp_path):
    db_path = str(tmp_path / "sessions.db")

    store1 = SessionStore(db_path)
    await store1.init()
    await store1.add_receipt(10, {"receipt_number": "persist-1"})
    await store1.add_receipt(10, {"receipt_number": "persist-2"})

    store2 = SessionStore(db_path)
    await store2.init()
    receipts = await store2.get_receipts(10)

    assert len(receipts) == 2
    assert receipts[0]["receipt_number"] == "persist-1"
    assert receipts[1]["receipt_number"] == "persist-2"
    await store1.close()
    await store2.close()
