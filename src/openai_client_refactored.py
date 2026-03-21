import base64
import requests
import json
import re
import datetime
import time
import copy
from .config import OPENAI_API_KEY, OPENROUTER_API_KEY, MAX_RETRIES, API_TIMEOUT
from .result_builder import ResultBuilder
from .pipeline.orchestrator import process_receipt_pipeline

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
    
    # 1. Нормализация и валидация ИНН
    if data.get("inn"):
        inn_raw = str(data["inn"])

        # Заменяем визуально похожие буквы на цифры (OCR-артефакты)
        ocr_map = {
            'О': '0', 'о': '0', 'O': '0', 'o': '0',  # буква О → цифра 0
            'З': '3', 'з': '3',                         # буква З → цифра 3
            'l': '1', 'I': '1', 'i': '1',              # буква l/I → цифра 1
            'В': '8', 'в': '8', 'B': '8', 'b': '8',   # буква В/B → цифра 8
            'S': '5', 's': '5',                         # буква S → цифра 5
            'G': '6', 'g': '9',                         # буква G → цифра 6
        }
        for char, digit in ocr_map.items():
            inn_raw = inn_raw.replace(char, digit)

        # Оставляем только цифры
        inn = re.sub(r'\D', '', inn_raw)

        if len(inn) in [10, 12]:
            # Базовая контрольная сумма для ИНН (опциональная проверка)
            data["inn"] = inn
            print(f"✅ ИНН нормализован: {inn} ({len(inn)} цифр)")
        elif len(inn) == 11:
            # Вероятно одна лишняя цифра из-за OCR — логируем, но не сохраняем
            print(f"⚠️  ИНН содержит {len(inn)} цифр (ожидалось 10 или 12): {inn} — установлен null")
            data["inn"] = None
        elif len(inn) == 9 or len(inn) == 13:
            print(f"⚠️  ИНН содержит {len(inn)} цифр (ожидалось 10 или 12): {inn} — установлен null")
            data["inn"] = None
        else:
            print(f"⚠️  ИНН некорректен ({len(inn)} цифр): {inn} — установлен null")
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
    
    # 2.5. Нормализация названия организации
    if data.get("organization"):
        org = str(data["organization"]).strip()

        # Заменяем визуально похожие OCR-артефакты
        ocr_map = {
            '0': 'О',  # НЕ применяем — в названиях могут быть цифры
        }
        # Убираем множественные пробелы
        org = re.sub(r'\s+', ' ', org)

        # Убираем мусорные символы по краям (но не внутри)
        org = org.strip('.,;:!?')

        # Если после очистки пусто — null
        data["organization"] = org if org else None
        if org:
            print(f"✅ Организация нормализована: {org}")

    # 3. Нормализация номера чека
    if data.get("receipt_number") and isinstance(data["receipt_number"], str):
        receipt_num = str(data["receipt_number"]).strip()

        # Убираем префиксы
        receipt_num = re.sub(
            r'^(чек\s*№?|№|receipt\s*#?|#|номер\s*(чека)?|фд|фд\s*№?|документ\s*№?)[:\s]*',
            '', receipt_num, flags=re.IGNORECASE
        ).strip()

        # Заменяем визуально похожие OCR-артефакты в номере чека
        ocr_num_map = {
            'О': '0', 'о': '0', 'O': '0', 'o': '0',
            'З': '3', 'з': '3',
            'l': '1', 'I': '1',
            'В': '8', 'B': '8',
            'S': '5',
        }
        receipt_num_clean = receipt_num
        for char, digit in ocr_num_map.items():
            receipt_num_clean = receipt_num_clean.replace(char, digit)

        # Оставляем цифры, буквы и дефисы
        receipt_num_clean = re.sub(r'[^\w\d\-]', '', receipt_num_clean)

        # Если номер слишком длинный — ищем цифровую последовательность
        if len(receipt_num_clean) > 20:
            digit_match = re.search(r'\d{4,}', receipt_num_clean)
            if digit_match:
                receipt_num_clean = digit_match.group(0)

        if receipt_num_clean:
            print(f"✅ Номер чека нормализован: {receipt_num_clean}")
        else:
            print(f"⚠️  Номер чека не удалось распознать: '{receipt_num}'")

        data["receipt_number"] = receipt_num_clean if receipt_num_clean else None
    
    # 4. Нормализация числовых полей (финальная версия)
    numeric_fields = ["total", "total_vat"]
    for field in numeric_fields:
        if