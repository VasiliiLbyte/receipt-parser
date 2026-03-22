"""
OpenAI provider-specific extraction logic.

This module contains only provider-specific code for OpenAI API.
It should not contain any orchestration, normalization, or validation logic.
"""

from __future__ import annotations

import base64
import requests
import json
import re
import time
from ..config import OPENAI_API_KEY, MAX_RETRIES, FALLBACK_MODEL
from .receipt_vision_prompt import RECEIPT_VISION_PROMPT

API_URL = "https://api.openai.com/v1/chat/completions"

def encode_image(image_path):
    """Provider-specific image encoding for OpenAI."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_json_from_response(content):
    """Provider-specific JSON extraction from OpenAI response."""
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
    return content.strip()

def extract_raw_openai_data(image_path, model: str | None = None, **_kwargs):
    """
    Provider-specific extraction function for OpenAI.
    Returns raw data from OpenAI API without any post-processing.

    Args:
        image_path: путь к изображению
        model: имя модели OpenAI (по умолчанию FALLBACK_MODEL из конфига)
    """
    print("🔍 Кодирование изображения в base64...")
    base64_image = encode_image(image_path)
    print("✅ Изображение закодировано")

    use_model = model or FALLBACK_MODEL

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    prompt = RECEIPT_VISION_PROMPT

    payload = {
        "model": use_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.0,
        "seed": 42
    }
    
    max_retries = MAX_RETRIES or 3
    
    for attempt in range(1, max_retries + 1):
        print(f"📤 Отправка запроса к OpenAI Vision API (попытка {attempt}/{max_retries})...")
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            print(f"📊 Статус ответа: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print("📝 Получен ответ от модели")

                cleaned_content = extract_json_from_response(content)
                try:
                    provider_data = json.loads(cleaned_content)
                    print("✅ JSON успешно распарсен")
                    return provider_data
                except json.JSONDecodeError as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
                    print("Содержимое ответа:", content)
                    return None

            elif response.status_code == 429:
                # Превышен лимит — ждём и пробуем снова
                wait = 10 * attempt
                print(f"⏳ Превышен лимит запросов. Ждём {wait} секунд...")
                time.sleep(wait)

            else:
                print(f"❌ Ошибка API: {response.status_code}")
                print(response.text)
                return None

        except Exception as e:
            print(f"❌ Исключение при запросе (попытка {attempt}): {e}")
            if attempt < max_retries:
                print(f"🔄 Повторяем через 5 секунд...")
                time.sleep(5)

    print("❌ Все попытки исчерпаны. Не удалось получить ответ от API.")
    return None