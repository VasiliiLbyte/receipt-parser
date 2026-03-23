"""
OpenRouter клиент для верификации названий товаров (Pass 2)
Использует Gemini Flash через OpenRouter API
"""
import requests
import json
import re
from src.config import OPENROUTER_API_KEY, OPENROUTER_VERIFY_MODEL

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def extract_json_from_response(content):
    """Извлекает JSON из ответа модели, удаляя markdown-обёртку если есть"""
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
    return content.strip()


def verify_item_names(image_base64: str, pass1_data: dict, force: bool = False) -> dict:
    """
    Верификация названий товаров через OpenRouter (Gemini Flash).
    
    Сравнивает названия из pass1_data с тем, что реально написано на чеке,
    и исправляет расхождения.
    
    Args:
        image_base64: изображение чека в base64
        pass1_data: результат первичного распознавания (Pass 1)
        force: принудительный запуск Pass 2 даже если нет расхождений
        
    Returns:
        Обновлённый dict с исправленными названиями товаров
    """
    # Проверяем наличие API ключа
    if not OPENROUTER_API_KEY:
        print("⚠️ Pass 2 пропущен: OPENROUTER_API_KEY не задан")
        return pass1_data
    
    # Запускаем Pass 2 всегда если force=True,
    # или если есть расхождение сумм, или если есть items
    amounts_mismatch = pass1_data.get("_amounts_mismatch", False)
    if not force and not amounts_mismatch and not pass1_data.get("items"):
        print("⏭️  Pass 2 пропущен: нет позиций и расхождений сумм")
        return pass1_data
    
    print(f"🔍 Pass 2: верификация через OpenRouter ({OPENROUTER_VERIFY_MODEL})...")
    
    # Формируем JSON для промпта
    pass1_json = json.dumps(pass1_data, ensure_ascii=False, indent=2)
    
    prompt = f"""Ты — эксперт по верификации OCR-распознавания кассовых чеков.

Тебе дано:
1. Фотография чека (изображение выше)
2. Результат первичного распознавания (JSON ниже)

Твоя ЕДИНСТВЕННАЯ задача — проверить и при необходимости исправить поле "name"
у каждого товара в списке "items".

ПРАВИЛА ВЕРИФИКАЦИИ:
- Сравни каждое название из JSON с тем, что реально написано на чеке, символ за символом
- Если название в JSON точно совпадает с чеком — оставь как есть
- Если есть расхождение — исправь на то, что буквально написано на чеке
- НЕ исправляй опечатки, сокращения и странные слова — копируй как есть с чека
- НЕ меняй другие поля (цены, количество, даты и т.д.) — только "name"
- Если название товара занимает несколько строк на чеке — объедини в одну строку через пробел
- Сохраняй оригинальный регистр букв, цифры, дефисы, скобки, спецсимволы
- Также проверь поле "date": сравни дату в JSON с тем, что написано на чеке.
  Если год отличается — исправь на то, что буквально видишь на чеке.
  Формат ответа: ГГГГ-ММ-ДД. Если дата нечитаема — оставь как есть из JSON.
- Также проверь поле "inn": сравни ИНН в JSON с тем, что написано на чеке
  символ за символом. ИНН — это последовательность из 10 или 12 цифр рядом
  со словом "ИНН" на чеке. Если видишь расхождение — исправь. Если нечитаемо
  — оставь как есть из JSON.
- Также проверь поле "organization": сравни название организации/ИП в JSON
  с тем, что написано на чеке. Копируй буквально включая ИП/ООО/АО, кавычки,
  заглавные буквы. Если нечитаемо — оставь как есть из JSON.
- Также проверь поле "receipt_number": найди номер чека на изображении и
  сравни с JSON. Копируй только само число/код без префиксов (Чек №, ФД и т.д.).
  Сохраняй дефисы и буквы внутри номера. Если нечитаемо — оставь как есть.
- Проверь все числовые суммы: `total`, `total_vat`, а также для каждого товара
  `price_per_unit`, `quantity`, `total_price`, `vat_amount`.
  Сравни каждое число с тем, что написано на чеке буквально.
  Типичные OCR-путаницы: «0»↔«8», «1»↔«7», «3»↔«8», «5»↔«6».
  Обращай внимание на разделитель копеек (запятая или точка) и разделитель тысяч.
  Если видишь расхождение — исправь на то, что написано на чеке.
  Если нечитаемо — оставь как есть из JSON.

Результат первичного распознавания:
{pass1_json}

Верни ТОЛЬКО валидный JSON в том же формате что и входной, без пояснений и комментариев."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "receipt-parser",
        "X-Title": "receipt-parser"
    }
    
    payload = {
        "model": OPENROUTER_VERIFY_MODEL,
        "temperature": 0.0,
        "max_tokens": 3000,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }]
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"⚠️ Pass 2 ошибка: HTTP {response.status_code} - {response.text[:200]}")
            return pass1_data
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Извлекаем JSON из ответа
        cleaned_content = extract_json_from_response(content)
        pass2_data = json.loads(cleaned_content)
        
        # Берём ТОЛЬКО поле items из ответа, остальное — из pass1_data
        if "items" in pass2_data and pass2_data["items"]:
            pass1_data["items"] = pass2_data["items"]
            items_count = len(pass2_data["items"])
            print(f"✅ Pass 2 завершён, проверено {items_count} товаров")
        else:
            print("⚠️ Pass 2: не удалось получить items из ответа")
        
        # Верифицируем дату если OpenRouter вернул отличающуюся
        verified_date = pass2_data.get("date")
        original_date = pass1_data.get("date")
        if verified_date and verified_date != original_date:
            print(f"📅 Pass 2 исправил дату: {original_date} → {verified_date}")
            pass1_data["date"] = verified_date
        
        # Верифицируем ИНН если OpenRouter вернул отличающийся
        verified_inn = pass2_data.get("inn")
        original_inn = pass1_data.get("inn")
        if verified_inn and verified_inn != original_inn:
            # Очищаем до цифр перед сравнением
            verified_inn_clean = re.sub(r'\D', '', str(verified_inn))
            if len(verified_inn_clean) in [10, 12]:
                print(f"🔢 Pass 2 исправил ИНН: {original_inn} → {verified_inn_clean}")
                pass1_data["inn"] = verified_inn_clean
            else:
                print(f"⚠️  Pass 2 вернул некорректный ИНН ({verified_inn}), оставляем оригинал")
        
        # Верифицируем название организации
        verified_org = pass2_data.get("organization")
        original_org = pass1_data.get("organization")
        if verified_org and verified_org != original_org:
            print(f"🏢 Pass 2 исправил организацию: '{original_org}' → '{verified_org}'")
            pass1_data["organization"] = verified_org.strip()

        # Верифицируем номер чека
        verified_receipt = pass2_data.get("receipt_number")
        original_receipt = pass1_data.get("receipt_number")
        if verified_receipt and verified_receipt != original_receipt:
            # Очищаем от префиксов
            verified_receipt_clean = re.sub(
                r'^(чек\s*№?|№|receipt\s*#?|#|номер\s*(чека)?|фд)[:\s]*',
                '', str(verified_receipt), flags=re.IGNORECASE
            ).strip()
            verified_receipt_clean = re.sub(r'[^\w\d\-]', '', verified_receipt_clean)
            if verified_receipt_clean:
                print(f"🧾 Pass 2 исправил номер чека: '{original_receipt}' → '{verified_receipt_clean}'")
                pass1_data["receipt_number"] = verified_receipt_clean

        # Верифицируем итоговые суммы
        for field in ["total", "total_vat"]:
            verified_val = pass2_data.get(field)
            original_val = pass1_data.get(field)
            if verified_val is not None and verified_val != original_val:
                try:
                    verified_float = float(str(verified_val).replace(',', '.'))
                    print(f"💰 Pass 2 исправил {field}: {original_val} → {verified_float}")
                    pass1_data[field] = verified_float
                except Exception:
                    print(f"⚠️  Pass 2 вернул некорректное значение {field}: {verified_val}")

        # Верифицируем числа в позициях товаров
        verified_items = pass2_data.get("items", [])
        original_items = pass1_data.get("items", [])
        if verified_items and len(verified_items) == len(original_items):
            for idx, (v_item, o_item) in enumerate(zip(verified_items, original_items)):
                for key in ["price_per_unit", "quantity", "total_price", "vat_amount"]:
                    v_val = v_item.get(key)
                    o_val = o_item.get(key)
                    if v_val is not None and v_val != o_val:
                        try:
                            v_float = float(str(v_val).replace(',', '.'))
                            name = o_item.get("name", f"товар #{idx+1}")
                            print(f"💰 Pass 2 исправил {key} у '{name}': {o_val} → {v_float}")
                            pass1_data["items"][idx][key] = v_float
                        except Exception:
                            pass
        elif verified_items and len(verified_items) != len(original_items):
            print(f"⚠️  Pass 2 вернул {len(verified_items)} позиций вместо {len(original_items)} — числа не обновляем")

        # Убираем служебный флаг перед возвратом
        pass1_data.pop("_amounts_mismatch", None)
        
        return pass1_data
        
    except json.JSONDecodeError as e:
        print(f"⚠️ Pass 2 ошибка: невалидный JSON в ответе - {e}")
        return pass1_data
    except KeyError as e:
        print(f"⚠️ Pass 2 ошибка: отсутствует ключ {e}")
        return pass1_data
    except requests.exceptions.Timeout:
        print("⚠️ Pass 2 ошибка: таймаут запроса (60с)")
        return pass1_data
    except Exception as e:
        print(f"⚠️ Pass 2 ошибка: {e}")
        return pass1_data
