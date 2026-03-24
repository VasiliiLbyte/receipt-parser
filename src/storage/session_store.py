"""
Persistent async store for user receipt sessions.
"""

from __future__ import annotations

import asyncio
import json
import os
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
                receipt_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.commit()

    async def add_receipt(self, user_id: int, receipt: dict) -> None:
        async with self._lock:
            conn = await self._get_connection()
            await conn.execute(
                """
                INSERT INTO user_receipts (user_id, receipt_json)
                VALUES (?, ?)
                """,
                (user_id, json.dumps(receipt, ensure_ascii=False)),
            )
            await conn.commit()

    async def get_receipts(self, user_id: int) -> List[dict]:
        conn = await self._get_connection()
        cursor = await conn.execute(
            """
            SELECT receipt_json
            FROM user_receipts
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

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
                await conn.execute(
                    """
                    INSERT INTO user_receipts (user_id, receipt_json)
                    VALUES (?, ?)
                    """,
                    (user_id, json.dumps(receipt, ensure_ascii=False)),
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


session_store = SessionStore()
