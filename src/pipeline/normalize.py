"""
Pure normalization functions extracted from postprocess_data.

These functions are provider-agnostic and work on flat dict structures.
They should not contain any provider-specific logic or I/O operations.
"""

import re
import datetime
from typing import Any, Dict, Literal, Optional

PaymentMethod = Literal["cash", "card", "mixed"]

_UNIT_ALIASES: Dict[str, str] = {
    "шт": "шт",
    "штук": "шт",
    "штуки": "шт",
    "кг": "кг",
    "г": "г",
    "л": "л",
    "литр": "л",
    "литра": "л",
    "литров": "л",
    "мл": "мл",
    "порц": "порц",
    "порция": "порц",
    "порций": "порц",
    "упак": "упак",
    "уп": "упак",
    "упаковка": "упак",
    "компл": "компл",
    "комплект": "компл",
}


def normalize_kpp(kpp: Any) -> Optional[str]:
    """КПП: ровно 10 цифр или None (OCR-замены как у ИНН)."""
    if not kpp:
        return None
    raw = str(kpp)
    ocr_map = {
        "О": "0",
        "о": "0",
        "O": "0",
        "o": "0",
        "З": "3",
        "з": "3",
        "l": "1",
        "I": "1",
        "i": "1",
        "В": "8",
        "в": "8",
        "B": "8",
        "b": "8",
        "S": "5",
        "s": "5",
    }
    for char, digit in ocr_map.items():
        raw = raw.replace(char, digit)
    clean = re.sub(r"\D", "", raw)
    if len(clean) == 10:
        return clean
    return None


def normalize_payment_method(value: Any) -> Optional[PaymentMethod]:
    """
    Форма оплаты: cash | card | mixed | None.
    Только по явному тексту на чеке, без угадывания.
    """
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    if re.search(r"смешанн|часть\s+нал|наличн.*карт|карт.*наличн|split\s+pay|mixed\s+pay", s):
        return "mixed"
    if re.search(
        r"безнал|без\s*наличн|карт(ой|а)?\b|card\b|эквайринг|"
        r"non-?cash|электронн|по\s+карте|оплат[аы]\s+карт",
        s,
    ):
        return "card"
    if re.search(r"наличн|cash\b", s):
        return "cash"
    return None


def normalize_currency(value: Any) -> str:
    """Валюта ISO 4217; пусто → RUB."""
    if value is None:
        return "RUB"
    s = str(value).strip().upper()
    if not s:
        return "RUB"
    if s in ("RUR", "₽", "РУБ.", "РУБ"):
        return "RUB"
    if re.fullmatch(r"[A-Z]{3}", s):
        return s
    low = str(value).strip().lower()
    if re.search(r"руб|₽|rub", low):
        return "RUB"
    return "RUB"


def normalize_unit(value: Any) -> Optional[str]:
    """Единица измерения: нижний регистр, без точки в конце; без выдумывания."""
    if value is None:
        return None
    s = str(value).strip().lower().rstrip(".")
    if not s:
        return None
    return _UNIT_ALIASES.get(s, s)


def normalize_inn(inn: Any) -> Optional[str]:
    """
    Нормализация ИНН: очистка от OCR-артефактов, проверка длины.
    
    Args:
        inn: сырое значение ИНН (может быть строкой с мусором)
        
    Returns:
        Очищенный ИНН (10 или 12 цифр) или None если некорректен
    """
    if not inn:
        return None
    
    inn_raw = str(inn)
    
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
    inn_clean = re.sub(r'\D', '', inn_raw)
    
    if len(inn_clean) in [10, 12]:
        return inn_clean
    else:
        # Некорректная длина
        return None


def normalize_date(date_str: Any) -> Optional[str]:
    """
    Нормализация даты: парсинг разных форматов, очистка OCR-артефактов.
    
    Args:
        date_str: сырая строка с датой (может содержать мусор)
        
    Returns:
        Дата в формате ГГГГ-ММ-ДД или None если не удалось распарсить
    """
    if date_str is None:
        return None
    
    date_str = str(date_str).strip()
    if not date_str:
        return None
    
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
    
    for rus_month, num_month in russian_months.items():
        if rus_month in date_str.lower():
            pattern = re.compile(re.escape(rus_month), re.IGNORECASE)
            date_str = pattern.sub(num_month, date_str)
            break
    
    # 4. Заменяем распространенные OCR ошибки
    date_str = re.sub(r'\s+', ' ', date_str)
    
    # Если есть только цифры и разделители
    if re.match(r'^[\d\s\.,\-/]+$', date_str):
        date_str = date_str.replace(',', '.')
        date_str = re.sub(r'(\d)\s+(\d)', r'\1.\2', date_str)
        date_str = re.sub(r'\.+', '.', date_str)
    
    # 5. Убираем время, если оно есть
    date_str = re.sub(r'\s+\d{1,2}[:\.]\d{1,2}([:\.]\d{1,2})?', '', date_str)
    
    # 6. Убираем лишние символы в конце
    date_str = re.sub(r'[^\d\./\-\s]+$', '', date_str)
    date_str = date_str.strip()
    
    if not date_str:
        return None
    
    # Попытка распарсить разные форматы дат
    date_formats = [
        "%Y-%m-%d",           # 2025-12-31
        "%d.%m.%Y",           # 31.12.2025
        "%d.%m.%y",           # 31.12.25
        "%Y/%m/%d",           # 2025/12/31
        "%d/%m/%Y",           # 31/12/2025
        "%d/%m/%y",           # 31/12/25
        "%d-%m-%Y",           # 31-12-2025
        "%d-%m-%y",           # 31-12-25
        "%Y.%m.%d",           # 2025.12.31
        "%m/%d/%Y",           # 12/31/2025 (американский)
        "%m/%d/%y",           # 12/31/25
        "%Y.%d.%m",           # 2025.31.12
        "%d-%b-%Y",           # 31-Dec-2025
        "%d-%B-%Y",           # 31-December-2025
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    
    # Если не удалось распарсить, пытаемся извлечь дату с помощью regex
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
                if len(groups[0]) == 4:  # Первая группа - год
                    year, month, day = groups
                else:  # Первая группа - день
                    day, month, year = groups
                
                if len(year) == 2:
                    year = f"20{year}"
                
                try:
                    dt = datetime.datetime(int(year), int(month), int(day))
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    continue
    
    return None


def normalize_number(value: Any) -> Optional[float]:
    """
    Нормализация числового поля (денежные суммы).
    
    Args:
        value: сырое значение (строка с валютой, разделителями и т.д.)
        
    Returns:
        Число с плавающей точкой или None если не удалось распарсить
    """
    if value is None:
        return None
    
    try:
        value_str = str(value)
        
        # Удаляем валютные обозначения
        value_str = re.sub(r'\s*(руб\.?|р\.?|RUB|USD|EUR|€|\$|£)\.?\s*', '', value_str, flags=re.IGNORECASE)
        value_str = re.sub(r'\s*(рублей|рубля|р\.|р)\s*', '', value_str, flags=re.IGNORECASE)
        
        # Удаляем все символы, кроме цифр, точек и запятых
        value_str = re.sub(r'[^\d\.,]', '', value_str)
        value_str = re.sub(r'\.$', '', value_str)
        
        if not value_str:
            return None
        
        # Определяем десятичный разделитель
        last_comma = value_str.rfind(',')
        last_dot = value_str.rfind('.')
        
        if last_comma > last_dot:
            # Европейский формат: "1.234,56"
            decimal_separator = ','
            digits_after = len(value_str) - last_comma - 1
            
            if 1 <= digits_after <= 2:
                # Десятичная часть
                value_str = value_str.replace('.', '').replace(',', '.')
            elif digits_after == 3:
                # Разделитель тысяч
                value_str = value_str.replace(',', '')
            else:
                value_str = value_str.replace(',', '.')
                
        elif last_dot > last_comma:
            # Американский формат: "1,234.56"
            decimal_separator = '.'
            digits_after = len(value_str) - last_dot - 1
            
            if 1 <= digits_after <= 2:
                # Десятичная часть
                value_str = value_str.replace(',', '')
            elif digits_after == 3:
                # Разделитель тысяч
                value_str = value_str.replace('.', '')
        else:
            # Нет разделителей или оба на одной позиции
            value_str = re.sub(r'[^\d]', '', value_str)
            if value_str:
                value_str = value_str + '.00'
            else:
                return None
        
        # Если остались лишние точки (после преобразований)
        if value_str.count('.') > 1:
            parts = value_str.split('.')
            value_str = '.'.join(parts[:-1]) + parts[-1]
        
        return float(value_str)
    except Exception:
        return None


def normalize_organization(org: Any) -> Optional[str]:
    """
    Нормализация названия организации.
    
    Args:
        org: сырое название организации
        
    Returns:
        Очищенное название или None если пустое
    """
    if not org:
        return None
    
    org_str = str(org).strip()
    
    # Убираем множественные пробелы
    org_str = re.sub(r'\s+', ' ', org_str)
    
    # Убираем мусорные символы по краям
    org_str = org_str.strip('.,;:!?')
    
    return org_str if org_str else None


def normalize_receipt_number(receipt_num: Any) -> Optional[str]:
    """
    Нормализация номера чека.
    
    Args:
        receipt_num: сырой номер чека (может содержать префиксы)
        
    Returns:
        Очищенный номер чека или None если пустой
    """
    if not receipt_num or not isinstance(receipt_num, str):
        return None
    
    receipt_num = receipt_num.strip()
    
    # Убираем префиксы
    receipt_num = re.sub(
        r'^(чек\s*№?|№|receipt\s*#?|#|номер\s*(чека)?|фд|фд\s*№?|документ\s*№?)[:\s]*',
        '', receipt_num, flags=re.IGNORECASE
    ).strip()
    
    # Заменяем визуально похожие OCR-артефакты
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
    
    return receipt_num_clean if receipt_num_clean else None


def normalize_item_name(name: Any) -> Optional[str]:
    """
    Нормализация названия товара.
    
    Args:
        name: сырое название товара
        
    Returns:
        Очищенное название товара
    """
    if not name:
        return None
    
    name_str = str(name)
    
    # Исправляем распространенную OCR-ошибку "НАС" -> "НДС"
    name_str = name_str.replace("НАС", "НДС").replace("нас", "НДС")
    
    # Убираем лишние пробелы
    name_str = re.sub(r'\s+', ' ', name_str).strip()
    
    return name_str


def apply_item_tax_aliases(item: Dict[str, Any]) -> None:
    """Явные gst/tax поля строки чека → vat_amount / vat_rate (без распределения с total)."""
    if item.get("vat_amount") is None or item.get("vat_amount") == "":
        for key in ("gst_amount", "tax_amount", "tps_amount"):
            if key in item and item[key] is not None and item[key] != "":
                item["vat_amount"] = item[key]
                break
    vr = item.get("vat_rate")
    if vr is None or (isinstance(vr, str) and not str(vr).strip()):
        for key in ("gst_rate", "tax_rate", "gst_percent", "tax_percent"):
            if key in item and item[key] is not None and str(item[key]).strip():
                item["vat_rate"] = str(item[key]).strip()
                break


def merge_alternate_total_tax(result: Dict[str, Any]) -> None:
    """
    Если total_vat пустой, подставить сумму из явных полей GST/VAT/TAX (как вернула модель).
    Не перезаписывает уже заданный total_vat (включая 0).
    """
    if result.get("total_vat") is not None:
        return
    for key in (
        "total_gst",
        "gst_total",
        "total_tax",
        "tax_total",
        "vat_total",
        "vat_amount_total",
        "gst_amount_total",
        "summary_vat",
        "summary_gst",
        "included_vat",
        "vat_included",
        "total_vat_amount",
        # верхний уровень «tax» часто = сумма; «gst» без префикса может быть «GST 1» (стол) — не берём
        "tax",
    ):
        if key not in result:
            continue
        raw = result[key]
        if isinstance(raw, (dict, list)):
            continue
        if raw is None or raw == "":
            continue
        parsed = normalize_number(raw)
        if parsed is not None:
            result["total_vat"] = parsed
            return

    tax_obj = result.get("tax")
    if isinstance(tax_obj, dict):
        for nk in ("total_vat", "vat", "gst", "amount", "vat_amount", "total", "value"):
            if nk not in tax_obj:
                continue
            raw = tax_obj[nk]
            if raw is None or raw == "":
                continue
            parsed = normalize_number(raw)
            if parsed is not None:
                result["total_vat"] = parsed
                return


def normalize_item_numbers(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализация числовых полей товара.
    
    Args:
        item: словарь с данными товара
        
    Returns:
        Обновленный словарь с нормализованными числами
    """
    result = item.copy()
    
    for key in ["price_per_unit", "quantity", "total_price", "vat_amount"]:
        if key in result and result[key] is not None:
            result[key] = normalize_number(result[key])
    
    return result


def normalize_flat_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Полная нормализация плоских данных (обертка для обратной совместимости).
    
    Args:
        data: сырые данные от провайдера
        
    Returns:
        Нормализованные данные
    """
    if not data:
        return data
    
    result = data.copy()
    
    # Нормализация полей верхнего уровня
    if "inn" in result:
        result["inn"] = normalize_inn(result["inn"])

    if "kpp" in result:
        result["kpp"] = normalize_kpp(result["kpp"])

    result["payment_method"] = normalize_payment_method(result.get("payment_method"))
    result["currency"] = normalize_currency(result.get("currency"))

    if "date" in result:
        result["date"] = normalize_date(result["date"])
    
    if "organization" in result:
        result["organization"] = normalize_organization(result["organization"])
    
    if "receipt_number" in result and isinstance(result["receipt_number"], str):
        result["receipt_number"] = normalize_receipt_number(result["receipt_number"])
    
    # Нормализация числовых полей верхнего уровня
    for field in ["total", "total_vat"]:
        if field in result and result[field] is not None:
            result[field] = normalize_number(result[field])

    # Нормализация товаров
    if "items" in result:
        normalized_items = []
        for item in result["items"]:
            normalized_item = item.copy()

            if "name" in normalized_item:
                normalized_item["name"] = normalize_item_name(normalized_item["name"])

            apply_item_tax_aliases(normalized_item)
            normalized_item = normalize_item_numbers(normalized_item)
            normalized_item["unit"] = normalize_unit(normalized_item.get("unit"))
            normalized_items.append(normalized_item)

        result["items"] = normalized_items

    # Итог GST/VAT/TAX из альтернативных ключей верхнего уровня
    merge_alternate_total_tax(result)
    if result.get("total_vat") is not None:
        result["total_vat"] = normalize_number(result["total_vat"])

    return result