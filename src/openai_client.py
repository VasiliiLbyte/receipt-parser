import base64
import requests
import json
import re
import datetime
import time
from .config import OPENAI_API_KEY, MAX_RETRIES, API_TIMEOUT

API_URL = "https://api.openai.com/v1/chat/completions"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_json_from_response(content):
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
    return content.strip()

def _validate_receipt_date(date_str):
    """
    Валидация даты чека:
    - Проверяет, что дата реалистична (не в будущем более чем на 1 год)
    - Проверяет, что дата не слишком старая (не старше 10 лет)
    - Возвращает валидную дату или None
    """
    try:
        # Парсим дату из строки формата ГГГГ-ММ-ДД
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        current_date = datetime.datetime.now()
        
        # Проверяем, что дата не в будущем более чем на 1 год
        max_future_date = current_date + datetime.timedelta(days=365)
        if dt > max_future_date:
            print(f"⚠️  Дата {date_str} слишком в будущем (более чем на 1 год)")
            return None
        
        # Проверяем, что дата не слишком старая (не старше 10 лет)
        min_past_date = current_date - datetime.timedelta(days=3650)  # 10 лет
        if dt < min_past_date:
            print(f"⚠️  Дата {date_str} слишком старая (более 10 лет)")
            return None
        
        # Проверяем, что дата не в далеком прошлом (до 2000 года)
        if dt.year < 2000:
            print(f"⚠️  Дата {date_str} слишком старая (до 2000 года)")
            return None
        
        return date_str
    except Exception as e:
        print(f"⚠️  Ошибка валидации даты {date_str}: {e}")
        return None

def postprocess_data(data):
    """Исправляет типичные ошибки в данных и нормализует поля"""
    if not data:
        return data
    
    # 1. Нормализация ИНН: убираем лишние символы, оставляем только цифры
    if data.get("inn"):
        inn = re.sub(r'\D', '', str(data["inn"]))
        if len(inn) in [10, 12]:
            data["inn"] = inn
        else:
            # Если ИНН невалидный, устанавливаем None
            data["inn"] = None
    
    # 2. Улучшенная обработка даты с поддержкой OCR ошибок и русских названий месяцев
    if "date" in data:
        date_value = data["date"]
        
        # Если значение None или пустая строка, устанавливаем None
        if date_value is None:
            data["date"] = None
        else:
            date_str = str(date_value).strip()
            
            # Если строка пустая после strip, устанавливаем None
            if not date_str:
                data["date"] = None
                return data  # Возвращаемся, чтобы не продолжать обработку
            # Предварительная очистка строки от распространенных OCR ошибок
            # 1. Убираем лишние символы: кавычки, скобки, префиксы
            date_str = re.sub(r'[\[\]\"\'\(\)]', '', date_str)
            
            # 2. Убираем префиксы типа "Дата:", "Date:", "г.", "года", "год"
            date_str = re.sub(r'^(дата|date|d|д|года|год|г\.?)\s*[:\.]?\s*', '', date_str, flags=re.IGNORECASE)
            
            # 3. Заменяем русские названия месяцев на цифры
            russian_months = {
                'января': '01', 'янв': '01', 'янв.': '01',
                'февраля': '02', 'фев': '02', 'фев.': '02',
                'марта': '03', 'мар': '03', 'мар.': '03',
                'апреля': '04', 'апр': '04', 'апр.': '04',
                'мая': '05', 'май': '05', 'май.': '05',
                'июня': '06', 'июн': '06', 'июн.': '06',
                'июля': '07', 'июл': '07', 'июл.': '07',
                'августа': '08', 'авг': '08', 'авг.': '08',
                'сентября': '09', 'сен': '09', 'сен.': '09',
                'октября': '10', 'окт': '10', 'окт.': '10',
                'ноября': '11', 'ноя': '11', 'ноя.': '11',
                'декабря': '12', 'дек': '12', 'дек.': '12',
            }
            
            # Ищем русские названия месяцев и заменяем их на цифры
            for rus_month, num_month in russian_months.items():
                if rus_month in date_str.lower():
                    # Заменяем название месяца на цифру
                    pattern = re.compile(re.escape(rus_month), re.IGNORECASE)
                    date_str = pattern.sub(num_month, date_str)
                    break
            
            # 4. Заменяем распространенные OCR ошибки
            #    - Запятые на точки (31,12,2025 → 31.12.2025)
            #    - Пробелы на точки (31 12 2025 → 31.12.2025)
            #    - Множественные пробелы на один
            date_str = re.sub(r'\s+', ' ', date_str)
            
            # Если есть только цифры и разделители (пробелы, запятые, точки)
            if re.match(r'^[\d\s\.,\-/]+$', date_str):
                # Заменяем запятые на точки
                date_str = date_str.replace(',', '.')
                # Заменяем пробелы на точки (только между цифрами)
                date_str = re.sub(r'(\d)\s+(\d)', r'\1.\2', date_str)
                # Заменяем множественные точки на одну
                date_str = re.sub(r'\.+', '.', date_str)
            
            # 5. Убираем время, если оно есть (2025-12-31 10:30:45 → 2025-12-31)
            date_str = re.sub(r'\s+\d{1,2}[:\.]\d{1,2}([:\.]\d{1,2})?', '', date_str)
            
            # 6. Убираем лишние символы в конце (буквы, знаки препинания)
            date_str = re.sub(r'[^\d\./\-\s]+$', '', date_str)
            date_str = date_str.strip()
            
            # Если после очистки строка пустая, устанавливаем None
            if not date_str:
                data["date"] = None
            else:
                # Попытка распарсить разные форматы дат (расширенный список)
                date_formats = [
                    # Стандартные форматы
                    "%Y-%m-%d",           # 2025-12-31
                    "%d.%m.%Y",           # 31.12.2025
                    "%d.%m.%y",           # 31.12.25
                    "%Y/%m/%d",           # 2025/12/31
                    "%d/%m/%Y",           # 31/12/2025
                    "%d/%m/%y",           # 31/12/25
                    "%d-%m-%Y",           # 31-12-2025
                    "%d-%m-%y",           # 31-12-25
                    "%Y.%m.%d",           # 2025.12.31
                    
                    # Альтернативные форматы
                    "%m/%d/%Y",           # 12/31/2025 (американский)
                    "%m/%d/%y",           # 12/31/25
                    "%Y.%d.%m",           # 2025.31.12
                    "%d-%b-%Y",           # 31-Dec-2025
                    "%d-%B-%Y",           # 31-December-2025
                ]
                
                parsed_date = None
                for fmt in date_formats:
                    try:
                        dt = datetime.datetime.strptime(date_str, fmt)
                        parsed_date = dt.strftime("%Y-%m-%d")
                        break
                    except Exception:
                        continue
                
                # Если не удалось распарсить, пытаемся извлечь дату с помощью regex
                if not parsed_date:
                    # Паттерны для поиска даты в тексте (улучшенные)
                    patterns = [
                        r'(\d{1,2})[\./\-\s]+(\d{1,2})[\./\-\s]+(\d{4})',  # ДД.ММ.ГГГГ
                        r'(\d{1,2})[\./\-\s]+(\d{1,2})[\./\-\s]+(\d{2})',  # ДД.ММ.ГГ
                        r'(\d{4})[\./\-\s]+(\d{1,2})[\./\-\s]+(\d{1,2})',  # ГГГГ-ММ-ДД
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, date_str)
                        if match:
                            groups = match.groups()
                            if len(groups) == 3:
                                # Определяем порядок (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)
                                if len(groups[0]) == 4:  # Первая группа - год
                                    year, month, day = groups
                                else:  # Первая группа - день
                                    day, month, year = groups
                                
                                if len(year) == 2:
                                    year = f"20{year}"  # Преобразуем 25 в 2025
                                
                                try:
                                    # Проверяем валидность даты и реалистичность
                                    dt = datetime.datetime(int(year), int(month), int(day))
                                    # Дополнительная валидация: дата не должна быть в будущем (с запасом +1 год)
                                    current_date = datetime.datetime.now()
                                    max_future_date = current_date + datetime.timedelta(days=365)
                                    
                                    if dt <= max_future_date:
                                        parsed_date = dt.strftime("%Y-%m-%d")
                                    else:
                                        # Дата слишком в будущем, вероятно ошибка
                                        parsed_date = None
                                    break
                                except Exception:
                                    continue
                
                # Финальная валидация: проверяем реалистичность даты для чека
                if parsed_date:
                    parsed_date = _validate_receipt_date(parsed_date)
                
                # Эвристика: год не должен быть "подозрительно старым" для свежего чека
                # Если год < (текущий год - 2), логируем предупреждение
                # Это не блокирует сохранение — просто помогает отловить OCR-ошибки
                if parsed_date:
                    _current_year = datetime.datetime.now().year
                    _parsed_year = int(parsed_date[:4])
                    if _current_year - _parsed_year > 2:
                        print(
                            f"⚠️  Подозрительный год в дате: {parsed_date} "
                            f"(текущий год: {_current_year}, разница: {_current_year - _parsed_year} лет). "
                            f"Возможна OCR-ошибка — проверьте чек вручную."
                        )
                
                data["date"] = parsed_date if parsed_date else None
    
    # 3. Обработка номера чека
    if data.get("receipt_number") and isinstance(data["receipt_number"], str):
        receipt_num = data["receipt_number"].strip()
        
        # Убираем префиксы типа "Чек №", "Receipt #", "Номер:", "Номер чека:"
        # Добавляем ":" как отдельный префикс для удаления
        receipt_num = re.sub(r'^(чек|чек\s*№|receipt|receipt\s*#|номер|номер\s*чека|#|номер\s*чека\s*:|чека\s*:|чека|:|\s*:)\s*', '', receipt_num, flags=re.IGNORECASE)
        
        # Убираем лишние символы, оставляем только цифры, буквы и дефисы
        receipt_num = re.sub(r'[^\w\d\-]', '', receipt_num)
        
        # Если номер слишком длинный (возможно, содержит лишние символы), обрезаем
        if len(receipt_num) > 20:
            # Ищем последовательность цифр
            digit_match = re.search(r'\d{3,}', receipt_num)
            if digit_match:
                receipt_num = digit_match.group(0)
        
        data["receipt_number"] = receipt_num if receipt_num else None
    
    # 4. Нормализация числовых полей (финальная версия)
    numeric_fields = ["total", "total_vat"]
    for field in numeric_fields:
        if field in data and data[field] is not None:
            try:
                value_str = str(data[field])
                
                # Сначала удаляем распространенные валютные обозначения и лишние символы
                # Удаляем "руб.", "руб", "р.", "р", "RUB", "$", "€", "£" и т.д.
                # Важно: удаляем точку после валюты, если она есть
                value_str = re.sub(r'\s*(руб\.?|р\.?|RUB|USD|EUR|€|\$|£)\.?\s*', '', value_str, flags=re.IGNORECASE)
                
                # Также удаляем слово "рублей" и другие варианты
                value_str = re.sub(r'\s*(рублей|рубля|р\.|р)\s*', '', value_str, flags=re.IGNORECASE)
                
                # Удаляем все символы, кроме цифр, точек и запятых
                value_str = re.sub(r'[^\d\.,]', '', value_str)
                
                # Удаляем точку в конце строки, если она не является частью числа
                # (например, если осталась от "руб." или другой валюты)
                value_str = re.sub(r'\.$', '', value_str)
                
                # Если строка пустая, устанавливаем None
                if not value_str:
                    data[field] = None
                    continue
                
                # Определяем, есть ли десятичная часть (копейки/центы)
                # В русских чеках обычно 2 цифры после запятой
                has_decimal = False
                decimal_separator = None
                
                # Ищем последний разделитель (точку или запятую)
                last_comma = value_str.rfind(',')
                last_dot = value_str.rfind('.')
                
                if last_comma > last_dot:
                    # Запятая - последний разделитель (европейский формат)
                    decimal_separator = ','
                    digits_after = len(value_str) - last_comma - 1
                    
                    # Если после запятой 1-2 цифры, это десятичная часть
                    if 1 <= digits_after <= 2:
                        has_decimal = True
                    # Если после запятой 3 цифры, это почти всегда разделитель тысяч
                    # В контексте денег "1,190" = 1190, а не 1.190
                    elif digits_after == 3:
                        has_decimal = False
                    
                elif last_dot > last_comma:
                    # Точка - последний разделитель
                    decimal_separator = '.'
                    digits_after = len(value_str) - last_dot - 1
                    
                    # Если после точки 1-2 цифры, это десятичная часть
                    if 1 <= digits_after <= 2:
                        has_decimal = True
                    # Если после точки 3 цифры, это почти всегда разделитель тысяч
                    # В контексте денег "1.190" = 1190, а не 1.190
                    elif digits_after == 3:
                        has_decimal = False
                
                if has_decimal and decimal_separator:
                    # Есть десятичная часть, сохраняем ее
                    # Удаляем все другие разделители (разделители тысяч)
                    if decimal_separator == ',':
                        # Европейский формат: "1.234,56" -> удаляем точки
                        value_str = value_str.replace('.', '').replace(',', '.')
                    else:
                        # Американский формат: "1,234.56" -> удаляем запятые
                        value_str = value_str.replace(',', '')
                else:
                    # Нет десятичной части или неясный формат
                    # Удаляем все разделители и предполагаем целое число
                    value_str = re.sub(r'[^\d]', '', value_str)
                    if value_str:
                        value_str = value_str + '.00'
                    else:
                        data[field] = None
                        continue
                
                data[field] = float(value_str)
            except Exception:
                data[field] = None
    
    # 5. Исправление в названиях товаров
    if "items" in data:
        for item in data["items"]:
            if "name" in item and item["name"]:
                # Заменяем "НАС" на "НДС" (только если это отдельное слово, но можно и просто замену)
                item["name"] = item["name"].replace("НАС", "НДС").replace("нас", "НДС")
                # Убираем лишние пробелы (множественные пробелы заменяем на один)
                item["name"] = re.sub(r'\s+', ' ', item["name"]).strip()
            
            # Нормализация числовых полей в товарах
            for key in ["price_per_unit", "quantity", "total_price", "vat_amount"]:
                if key in item and item[key] is not None:
                    try:
                        value_str = str(item[key])
                        value_str = re.sub(r'[^\d\.\,\-]', '', value_str)
                        
                        # Аналогичная логика для форматов чисел
                        if ',' in value_str and '.' in value_str:
                            value_str = value_str.replace(',', '')
                        else:
                            value_str = value_str.replace(',', '.')
                        
                        if value_str.count('.') > 1:
                            parts = value_str.split('.')
                            value_str = '.'.join(parts[:-1]) + parts[-1]
                        
                        item[key] = float(value_str)
                    except Exception:
                        item[key] = None
    
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
1. **ИНН**: строка из 10 или 12 цифр. Убери лишние символы, если они попали (например, "ИНН: 781603445844" → "781603445844").
2. **Дата**: приведи к формату ГГГГ-ММ-ДД.
   - На российских чеках дата обычно в формате ДД.ММ.ГГ (например, 15.10.24)
   - Двузначный год читай буквально: 22=2022, 23=2023, 24=2024, 25=2025, 26=2026
   - **КРИТИЧЕСКИ ВАЖНО**: смотри на каждую цифру года отдельно, не угадывай.
   - Типичные OCR-путаницы в цифрах года: «3»↔«8», «0»↔«8», «1»↔«7», «4»↔«9»
   - Если последняя цифра года нечитаема — верни null, не угадывай.
   - Примеры: «15.10.24» → «2024-10-15», «03.05.23» → «2023-05-03»
3. **Номер чека**: найди номер чека, который указан на самом чеке (обычно в верхней части). Это может быть поле "Чек №", "Номер чека", "Receipt #" и т.д.
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
- **ВЕРНИ ТОЛЬКО JSON, БЕЗ КОММЕНТАРИЕВ!**

Анализируй изображение построчно, символ за символом. Будь предельно внимателен к деталям. Верни ТОЛЬКО JSON.
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
    
    max_retries = 3  # Максимум 3 попытки
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
                    data = json.loads(cleaned_content)
                    data = postprocess_data(data)
                    print("✅ JSON успешно распарсен и постобработан")
                    
                    # Pass 2: верификация названий товаров через OpenRouter
                    try:
                        from .openrouter_client import verify_item_names
                        data = verify_item_names(base64_image, data)
                    except Exception as e:
                        print(f"⚠️  Pass 2 пропущен: {e}")
                    
                    return data
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
