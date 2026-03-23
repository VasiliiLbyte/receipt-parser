"""
OpenRouter provider-specific extraction logic (Pass 1).

Uses the OpenRouter API to extract receipt data via vision models.
Prompt and response format match the OpenAI provider for drop-in replacement.
"""

import base64
import requests
import json
import re
import time
from ..config import OPENROUTER_API_KEY, OPENROUTER_EXTRACT_MODEL, MAX_RETRIES

API_URL = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_MODELS = ["google/gemini-flash-1.5", "anthropic/claude-3-haiku"]


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json_from_response(content: str) -> str:
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
    return content.strip()


def _is_region_blocked_openai(response: requests.Response) -> bool:
    if response.status_code != 403:
        return False
    try:
        data = response.json()
        metadata = data.get("error", {}).get("metadata", {})
        raw = metadata.get("raw", "")
        provider_name = metadata.get("provider_name", "")
        return (
            provider_name.lower() == "openai"
            and "unsupported_country_region_territory" in raw
        )
    except Exception:
        return "unsupported_country_region_territory" in response.text


EXTRACT_PROMPT = """
Ты — эксперт по извлечению данных из фотографий кассовых чеков. Твоя задача — максимально точно и дословно распознать все поля чека и вернуть их в строгом JSON-формате.

### 🔍 КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ДЛЯ НАЗВАНИЙ ТОВАРОВ:
1. **КОПИРУЙ БУКВАЛЬНО, НЕ ПЕРЕФРАЗИРУЙ!** Даже если текст выглядит странно, содержит очевидные опечатки или кажется бессмысленным — копируй его точно так, как он написан в чеке.
2. **НЕ ИСПРАВЛЯЙ ОШИБКИ OCR В НАЗВАНИЯХ ТОВАРОВ!** Если в чеке написано "Штуцер", а ты видишь что-то похожее на "Патрубок" — копируй "Штуцер". Если написано "Угольные шетки", а выглядит как "Угловые петли" — копируй "Угольные шетки".
3. **ВНИМАТЕЛЬНО СЧИТЫВАЙ КАЖДЫЙ СИМВОЛ:**
   - Цифры: "5х8х16" должно остаться "5х8х16", а не "5xB16"
   - Буквы: "А-86" должно остаться "А-86", а не "4-6"
   - Специальные символы: дефисы, скобки, кавычки, точки, запятые
   - Пробелы: сохраняй точное количество и расположение пробелов
4. **ЕСЛИ НЕ УВЕРЕН — КОПИРУЙ ТО, ЧТО ВИДИШЬ!** Не пытайся "понять" или "исправить" текст. Твоя задача — точное копирование.

### 📋 ОБЩИЕ ПРАВИЛА:
0. **Организация**: название юрлица или ИП точно как написано на чеке.
   - Копируй буквально: «ИП ИВАНОВ ИВАН ИВАНОВИЧ», «ООО "РОМАШКА"» и т.д.
   - Сохраняй кавычки, заглавные буквы, аббревиатуры (ИП, ООО, АО, ПАО).
   - Типичные OCR-путаницы в названиях: «О»↔«0», «З»↔«3», «В»↔«8», «l»↔«1».
   - Не сокращай и не перефразируй — копируй полностью как на чеке.
   - Если название нечитаемо — верни null.

1. **ИНН**: строка строго из 10 цифр (юрлицо/ИП) или 12 цифр (физлицо).
   - Читай каждую цифру буквально, символ за символом — не угадывай.
   - Типичные OCR-путаницы: «0»↔«О»(буква), «1»↔«l»↔«I», «8»↔«В»(буква), «3»↔«8», «5»↔«6», «7»↔«1».
   - Убери все нецифровые символы (пробелы, дефисы, точки, буквы).
   - Если после очистки не 10 и не 12 цифр — верни null, не угадывай.
   - Пример: «ИНН: 78160З44584О» → очисти буквы-похожие → «7816034458400», проверь длину → если 13 цифр, значит ошибка OCR → верни null.
2. **Дата**: приведи к формату ГГГГ-ММ-ДД.
   - На российских чеках дата обычно в формате ДД.ММ.ГГ (например, 15.10.24)
   - Двузначный год читай буквально: 22=2022, 23=2023, 24=2024, 25=2025, 26=2026
   - **КРИТИЧЕСКИ ВАЖНО**: смотри на каждую цифру года отдельно, не угадывай.
   - Типичные OCR-путаницы в цифрах года: «3»↔«8», «0»↔«8», «1»↔«7», «4»↔«9»
   - Если последняя цифра года нечитаема — верни null, не угадывай.
   - Примеры: «15.10.24» → «2024-10-15», «03.05.23» → «2023-05-03»
3. **Номер чека**: найди номер чека на самом чеке (обычно в верхней части).
   - Поля могут называться: «Чек №», «№ чека», «Receipt #», «Номер документа».
   - Копируй значение буквально, только убери сам префикс («Чек №», «№» и т.д.).
   - Сохраняй дефисы и буквы внутри номера (например «А-00123», «ФД-456789»).
   - Типичные OCR-путаницы: «О»↔«0», «l»↔«1», «З»↔«3», «В»↔«8».
   - Если номер нечитаем или отсутствует — верни null.
4. **Для каждой позиции товара** укажи:
   - `name`: точное наименование (БУКВАЛЬНАЯ КОПИЯ!),
   - `price_per_unit`: цена за единицу (число),
   - `quantity`: количество (число),
   - `total_price`: общая стоимость (число),
   - `vat_rate`: ставка НДС (например, "20%", "5%", "без НДС", "0%"),
   - `vat_amount`: сумма НДС для этой позиции (число, если нет — null).
5. **Общая сумма чека** (`total`) и **общий НДС** (`total_vat`) — числа.
6. Если каких-то данных нет — ставь `null`.

### ⚠️ ПРИМЕРЫ КАК НЕ НАДО ДЕЛАТЬ (ТИПИЧНЫЕ ОШИБКИ):
- ❌ НЕПРАВИЛЬНО: "Патрубок топливный прямой Совиньонный Сенсата D10"
- ✅ ПРАВИЛЬНО: "Штуцер топливный угловой соединитель быстросъемный D10"

- ❌ НЕПРАВИЛЬНО: "Угловые петли подходя для Bosch 4-6 5xB16 (2шт) с остерегом АНГТ"
- ✅ ПРАВИЛЬНО: "Угольные шетки подходят для Bosch А-86 5х8х16 (2шт) с отстрелом"

### ⚠️ КРИТИЧЕСКИ ВАЖНО ДЛЯ НДС:
- **НЕ РАССЧИТЫВАЙ НДС САМОСТОЯТЕЛЬНО!**
- Считывай сумму НДС (`vat_amount`) прямо с чека, как она указана.
- Если в чеке сумма НДС не указана для позиции — ставь `null`.
- Общий НДС (`total_vat`) тоже считывай с чека, как он указан в разделе "НДС всего" или аналогичном.

### 📋 Пример идеального ответа:
{
  "organization": "ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ",
  "inn": "781603445844",
  "date": "2026-02-19",
  "receipt_number": "123456",
  "items": [
    {
      "name": "08-06 Контакт Гнездовой серии АМ Р МСР 2.8 - АМР 124190-1 под РФ Общая сменная цена 1.0-2.5 ММ (К-2)",
      "price_per_unit": 30.00,
      "quantity": 10.000,
      "total_price": 300.00,
      "vat_rate": "5%",
      "vat_amount": null
    }
  ],
  "total": 3750.00,
  "total_vat": 178.57
}

### ⚠️ ФИНАЛЬНОЕ ПРЕДУПРЕЖДЕНИЕ:
- **ПОВТОРЯЮ: НЕ ПЕРЕФРАЗИРУЙ НАЗВАНИЯ ТОВАРОВ!**
- **КОПИРУЙ БУКВАЛЬНО КАЖДЫЙ СИМВОЛ!**
- **НЕ ДОГАДЫВАЙСЯ, ЧТО "ИМЕЛОСЬ В ВИДУ"!**
- **ВЕРНИ ТОЛЬКО JSON, БЕС КОММЕНТАРИЕВ!**

Анализируй изображение построчно, символ за символом. Будь предельно внимателен к деталям. Верни ТОЛЬКО JSON.
"""


def extract_via_openrouter(image_path: str, **kwargs) -> dict | None:
    """
    Extract receipt data via OpenRouter vision API.

    Reads the image, encodes it to base64, sends to OpenRouter with
    the extraction prompt. Returns parsed dict or None on failure.
    """
    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY не задан — невозможно выполнить извлечение")
        return None

    print("🔍 Кодирование изображения в base64...")
    base64_image = encode_image(image_path)
    print("✅ Изображение закодировано")

    models_to_try = [OPENROUTER_EXTRACT_MODEL]
    for fallback in FALLBACK_MODELS:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "receipt-parser",
        "X-Title": "receipt-parser",
    }

    payload = {
        "model": "",
        "temperature": 0.0,
        "max_tokens": 4000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACT_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
    }

    max_retries = MAX_RETRIES or 3

    for model in models_to_try:
        print(f"🤖 Модель извлечения: {model}")
        payload["model"] = model

        for attempt in range(1, max_retries + 1):
            print(f"📤 Отправка запроса к OpenRouter ({model}, попытка {attempt}/{max_retries})...")
            try:
                response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
                print(f"📊 Статус ответа: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    print("📝 Получен ответ от модели")

                    cleaned = extract_json_from_response(content)
                    try:
                        provider_data = json.loads(cleaned)
                        print("✅ JSON успешно распарсен")
                        return provider_data
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON: {e}")
                        print("Содержимое ответа:", content)
                        return None

                if response.status_code == 429:
                    wait = 10 * attempt
                    print(f"⏳ Превышен лимит запросов. Ждём {wait} секунд...")
                    time.sleep(wait)
                    continue

                if _is_region_blocked_openai(response):
                    print("⚠️ Модель OpenAI недоступна по региону, переключаемся на fallback-модель...")
                    break

                print(f"❌ Ошибка API: {response.status_code}")
                print(response.text[:500])
                return None

            except requests.exceptions.Timeout:
                print(f"⏳ Таймаут запроса (попытка {attempt})")
                if attempt < max_retries:
                    time.sleep(5)
            except Exception as e:
                print(f"❌ Исключение при запросе (попытка {attempt}): {e}")
                if attempt < max_retries:
                    print("🔄 Повторяем через 5 секунд...")
                    time.sleep(5)
                else:
                    return None

    print("❌ Все попытки исчерпаны. Не удалось получить ответ от OpenRouter.")
    return None
