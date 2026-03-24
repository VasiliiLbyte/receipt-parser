from __future__ import annotations

import os
from datetime import datetime, timezone

import aiohttp


async def push_to_1c_webhook(receipt_data: dict) -> bool:
    """
    После успешного парсинга отправляет POST-запрос на 1С-вебхук.
    URL берётся из WEBHOOK_1C_URL в .env.
    Если URL пустой — функция молча возвращает False (фича выключена).
    Returns True при успехе, False при ошибке или отключении.
    """
    url = os.getenv("WEBHOOK_1C_URL", "").strip()
    if not url:
        return False

    payload = {
        "event": "receipt.parsed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": receipt_data if isinstance(receipt_data, dict) else {},
    }
    headers = {
        "Content-Type": "application/json",
        "X-Secret": os.getenv("WEBHOOK_1C_SECRET", ""),
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return resp.status < 400
    except Exception:
        return False
