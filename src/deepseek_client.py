import requests
import json
import os
import re
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("Не найден API-ключ DeepSeek. Добавьте его в файл .env")

API_URL = "https://api.deepseek.com/v1/chat/completions"

def extract_json_from_response(content):
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
    return content.strip()

def extract_receipt_data(receipt_text):
    print("Отправка запроса к DeepSeek...")
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
Ты — помощник, который извлекает структурированные данные из текста кассового чека. 
Текст получен с помощью OCR и может содержать опечатки или ошибки распознавания. Постарайся интерпретировать их правильно, основываясь на типичных названиях товаров и формате чека.
Ниже представлен распознанный текст. Пожалуйста, найди и верни ТОЛЬКО JSON со следующими полями:
- "organization": название организации (ИП или ООО, как в чеке),
- "inn": ИНН (строка из 10 или 12 цифр),
- "date": дата чека в формате ГГГГ-ММ-ДД (например, 2025-09-24),
- "items": список товаров/услуг, где каждый элемент содержит:
    - "name": наименование товара,
    - "price_per_unit": цена за единицу (число),
    - "quantity": количество (число),
    - "total_price": общая стоимость (число),
    - "vat_rate": ставка НДС (например, "20%", "5%" или "без НДС"),
    - "vat_amount": сумма НДС для этого товара (число, если нет — null)
- "total": общая сумма чека (число),
- "total_vat": общая сумма НДС по всему чеку (число, если нет — null).

Если какая-то информация отсутствует, ставь null.
Вот текст чека:
{receipt_text}

Ответ должен быть только в виде валидного JSON, без пояснений и лишнего текста.
"""
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        print(f"Статус ответа: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print("Сырой ответ от DeepSeek (первые 500 символов):", content[:500])
            cleaned_content = extract_json_from_response(content)
            try:
                data = json.loads(cleaned_content)
                print("JSON успешно распарсен.")
                return data
            except json.JSONDecodeError as e:
                print(f"Ошибка парсинга JSON: {e}")
                print("Очищенный контент:", cleaned_content)
                return None
        else:
            print(f"Ошибка API: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Исключение при запросе: {e}")
        return None