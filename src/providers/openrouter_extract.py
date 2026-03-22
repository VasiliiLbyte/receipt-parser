"""
Первичное извлечение чека через OpenRouter (Vision), тот же JSON-промпт, что и у OpenAI.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from typing import Any

import requests

from ..config import API_TIMEOUT, OPENROUTER_API_KEY, PRIMARY_MODEL
from .receipt_vision_prompt import RECEIPT_VISION_PROMPT

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _extract_json_from_response(content: str) -> str:
    match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
    if match:
        return match.group(1).strip()
    return content.strip()


def extract_raw_openrouter_data(image_path: str, model: str | None = None, **_kwargs) -> dict[str, Any] | None:
    """
    Сырой JSON чека от модели OpenRouter (мультимодальный запрос).
    """
    if not OPENROUTER_API_KEY or not str(OPENROUTER_API_KEY).strip():
        print("❌ OpenRouter: OPENROUTER_API_KEY не задан")
        return None

    use_model = model or PRIMARY_MODEL

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    mime, _ = mimetypes.guess_type(image_path)
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "receipt-parser",
        "X-Title": "receipt-parser",
    }

    payload = {
        "model": use_model,
        "temperature": 0.0,
        "max_tokens": 4000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": RECEIPT_VISION_PROMPT.strip()},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
    }

    print(f"📤 OpenRouter Vision: model={use_model}")
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=API_TIMEOUT)
        if response.status_code != 200:
            print(f"❌ OpenRouter HTTP {response.status_code}: {response.text[:300]}")
            return None
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        cleaned = _extract_json_from_response(content)
        data = json.loads(cleaned)
        print("✅ OpenRouter: JSON распарсен")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ OpenRouter: ошибка JSON: {e}")
        return None
    except Exception as e:
        print(f"❌ OpenRouter: {e}")
        return None
