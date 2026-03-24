"""
Persistent async store for user receipt sessions.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import List

import aiosqlite


class SessionStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("DB_PATH", "./data/sessions.db")
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        self._ensure_parent_dir()
        conn = await self._get_connection()
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                receipt_id TEXT,
                receipt_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Backward-compatible migration for existing databases.
        await self._ensure_column_exists(conn, "user_receipts", "receipt_id", "TEXT")
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_receipts_user_created
            ON user_receipts(user_id, id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_receipts_receipt_id
            ON user_receipts(receipt_id)
            """
        )
        await conn.commit()

    async def add_receipt(self, user_id: int, receipt: dict) -> str:
        receipt_id = str(uuid.uuid4())
        payload = dict(receipt) if isinstance(receipt, dict) else {}
        payload["id"] = receipt_id
        async with self._lock:
            conn = await self._get_connection()
            await conn.execute(
                """
                INSERT INTO user_receipts (user_id, receipt_id, receipt_json)
                VALUES (?, ?, ?)
                """,
                (user_id, receipt_id, json.dumps(payload, ensure_ascii=False)),
            )
            await conn.commit()
        return receipt_id

    async def get_receipts(self, user_id: int) -> List[dict]:
        conn = await self._get_connection()
        cursor = await conn.execute(
            """
            SELECT receipt_id, receipt_json
            FROM user_receipts
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        receipts: List[dict] = []
        for receipt_id, receipt_json in rows:
            payload = json.loads(receipt_json)
            if isinstance(payload, dict):
                payload.setdefault("id", receipt_id or "")
            receipts.append(payload)
        return receipts

    async def get_receipt_by_id(self, receipt_id: str) -> dict | None:
        conn = await self._get_connection()
        cursor = await conn.execute(
            """
            SELECT receipt_id, receipt_json
            FROM user_receipts
            WHERE receipt_id = ?
            LIMIT 1
            """,
            (receipt_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        stored_receipt_id, receipt_json = row
        payload = json.loads(receipt_json)
        if isinstance(payload, dict):
            payload.setdefault("id", stored_receipt_id or "")
        return payload

    async def clear_receipts(self, user_id: int) -> None:
        async with self._lock:
            conn = await self._get_connection()
            await conn.execute(
                """
                DELETE FROM user_receipts
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await conn.commit()

    async def set_receipts(self, user_id: int, receipts: List[dict]) -> None:
        async with self._lock:
            conn = await self._get_connection()
            await conn.execute(
                """
                DELETE FROM user_receipts
                WHERE user_id = ?
                """,
                (user_id,),
            )
            for receipt in receipts:
                receipt_id = (
                    receipt.get("id")
                    if isinstance(receipt, dict) and receipt.get("id")
                    else str(uuid.uuid4())
                )
                payload = dict(receipt) if isinstance(receipt, dict) else {}
                payload["id"] = receipt_id
                await conn.execute(
                    """
                    INSERT INTO user_receipts (user_id, receipt_id, receipt_json)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, receipt_id, json.dumps(payload, ensure_ascii=False)),
                )
            await conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _get_connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
        return self._conn

    def _ensure_parent_dir(self) -> None:
        # sqlite in-memory path should not create directories.
        if self.db_path == ":memory:":
            return
        dir_path = os.path.dirname(self.db_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

    async def _ensure_column_exists(
        self,
        conn: aiosqlite.Connection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        cursor = await conn.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        existing_columns = {row[1] for row in columns}
        if column_name not in existing_columns:
            await conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


session_store = SessionStore()
