import base64
import requests
import json
import os
import re
import datetime
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OpenAI API ключ. Добавьте его в файл .env")

API_URL = "https://api.openai.com/v1/chat/completions"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_json_from_response(content):
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
    return content.strip()

def postprocess_data(data):
    """Исправляет типичные ошибки в данных"""
    if not data:
        return data
    
    # Исправляем ИНН: убираем лишние символы, оставляем только цифры
    if data.get("inn"):
        inn = re.sub(r'\D', '', str(data["inn"]))
        if len(inn) in [10, 12]:
            data["inn"] = inn
    
    # Исправляем дату: если пришла в формате ДД.ММ.ГГ, преобразуем
    if data.get("date") and isinstance(data["date"], str):
        # Попытка распарсить разные форматы
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%Y/%m/%d"):
            try:
                dt = datetime.datetime.strptime(data["date"], fmt)
                data["date"] = dt.strftime("%Y-%m-%d")
                break
            except:
                pass
    
    # Исправляем в названиях товаров: замена "НАС" на "НДС"
    if "items" in data:
        for item in data["items"]:
            if "name" in item:
                # Заменяем "НАС" на "НДС" (только если это отдельное слово, но можно и просто замену)
                item["name"] = item["name"].replace("НАС", "НДС").replace("нас", "НДС")
                # Убираем лишние пробелы (множественные пробелы заменяем на один) — ЭТА СТРОКА УЖЕ ЕСТЬ
                item["name"] = re.sub(r'\s+', ' ', item["name"]).strip()
            # Приводим числа к float
            for key in ["price_per_unit", "quantity", "total_price", "vat_amount"]:
                if key in item and item[key] is not None:
                    try:
                        item[key] = float(item[key])
                    except:
                        pass
    return data

def extract_receipt_data_from_image(image_path):
    print("🔍 Кодирование изображения в base64...")
    base64_image = encode_image(image_path)
    print("✅ Изображение закодировано")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    prompt = """
Ты — эксперт по извлечению данных из фотографий кассовых чеков. Твоя задача — максимально точно и дословно распознать все поля чека и вернуть их в строгом JSON-формате.

### 🔍 Основные правила:
1. **Названия товаров**: копируй их **абсолютно точно**, как в чеке, включая:
   - все цифры, буквы, дефисы, кавычки, скобки, слэши, точки, запятые;
   - пробелы между словами и внутри аббревиатур;
   - даже если название выглядит странно или содержит очевидные опечатки — не исправляй его, оставляй как есть.
2. **Исправлять можно только**:
   - явные ошибки OCR в служебных словах (например, "НАС" → "НДС", "СУММА НАС" → "СУММА НДС") — но это касается только служебных полей, не названий товаров.
3. **ИНН**: строка из 10 или 12 цифр. Убери лишние символы, если они попали (например, "ИНН: 781603445844" → "781603445844").
4. **Дата**: приведи к формату ГГГГ-ММ-ДД. Если год двузначный (24.09.25), преобразуй в 2025-09-24.
5. **Для каждой позиции товара** укажи:
   - `name`: точное наименование,
   - `price_per_unit`: цена за единицу (число),
   - `quantity`: количество (число),
   - `total_price`: общая стоимость (число),
   - `vat_rate`: ставка НДС (например, "20%", "5%", "без НДС", "0%"),
   - `vat_amount`: сумма НДС для этой позиции (число, если нет — null).
6. **Общая сумма чека** (`total`) и **общий НДС** (`total_vat`) — числа.
7. Если каких-то данных нет — ставь `null`.

### 📋 Пример идеального ответа (обрати внимание, как скопировано длинное название):
{
  "organization": "ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ",
  "inn": "781603445844",
  "date": "2026-02-19",
  "items": [
    {
      "name": "08-06 Контакт Гнездовой серии АМ Р МСР 2.8 - АМР 124190-1 под РФ Общая сменная цена 1.0-2.5 ММ (К-2)",
      "price_per_unit": 30.00,
      "quantity": 10.000,
      "total_price": 300.00,
      "vat_rate": "5%",
      "vat_amount": 14.29
    },
    {
      "name": "S11-02, \"АМР 1418847-1\", Контакт Гнездовой МСМ 1.2 Series.Clean Воду (СВ)",
      "price_per_unit": 30.00,
      "quantity": 30.000,
      "total_price": 900.00,
      "vat_rate": "5%",
      "vat_amount": 42.86
    }
  ],
  "total": 3750.00,
  "total_vat": 178.57
}

### ⚠️ ВАЖНО:
- Никогда не перефразируй названия товаров. Копируй их один в один.
- Не добавляй свои комментарии, только JSON.
- Если в чеке есть позиции с одинаковыми названиями, но разными ценами или количеством — выведи их отдельно, как в чеке.
- Проверь, что все товары из чека попали в `items`, ничего не пропущено.

Анализируй изображение построчно. Будь внимателен к длинным и сложным наименованиям. Верни ТОЛЬКО JSON.
"""
    
    payload = {
        "model": "gpt-4o",
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
    
    print("📤 Отправка запроса к OpenAI Vision API...")
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        print(f"📊 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print("📝 Получен ответ от модели")
            
            cleaned_content = extract_json_from_response(content)
            try:
                data = json.loads(cleaned_content)
                data = postprocess_data(data)
                print("✅ JSON успешно распарсен и постобработан")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                print("Содержимое ответа:", content)
                return None
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Исключение при запросе: {e}")
        return None