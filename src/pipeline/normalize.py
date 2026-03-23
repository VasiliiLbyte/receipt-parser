"""
Pure normalization functions extracted from postprocess_data.

These functions are provider-agnostic and work on flat dict structures.
They should not contain any provider-specific logic or I/O operations.
"""

import re
import datetime
from typing import Any, Dict, Optional


def _inn_checksum_10(inn10: str) -> int:
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    s = sum(int(d) * w for d, w in zip(inn10[:9], weights))
    return (s % 11) % 10


def _inn_checksum_12(inn12: str) -> tuple[int, int]:
    weights11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    s11 = sum(int(d) * w for d, w in zip(inn12[:10], weights11))
    c11 = (s11 % 11) % 10

    weights12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    s12 = sum(int(d) * w for d, w in zip(inn12[:11], weights12))
    c12 = (s12 % 11) % 10
    return c11, c12


def _is_valid_inn(inn: str) -> bool:
    if not inn.isdigit():
        return False
    if len(inn) == 10:
        return _inn_checksum_10(inn) == int(inn[9])
    if len(inn) == 12:
        c11, c12 = _inn_checksum_12(inn)
        return c11 == int(inn[10]) and c12 == int(inn[11])
    return False


def _repair_inn_single_digit(inn: str) -> Optional[str]:
    """Try repairing one OCR digit if it gives a unique valid INN."""
    candidates = []
    for idx, ch in enumerate(inn):
        for repl in "0123456789":
            if repl == ch:
                continue
            candidate = inn[:idx] + repl + inn[idx + 1 :]
            if _is_valid_inn(candidate):
                candidates.append(candidate)
    unique = sorted(set(candidates))
    if len(unique) == 1:
        return unique[0]
    return None


def _repair_inn_control_digits(inn: str) -> Optional[str]:
    """Deterministically repair control digits for 10/12-digit INN."""
    if not inn.isdigit():
        return None
    if len(inn) == 10:
        return inn[:9] + str(_inn_checksum_10(inn))
    if len(inn) == 12:
        prefix10 = inn[:10]
        c11, _ = _inn_checksum_12(prefix10 + "00")
        first11 = prefix10 + str(c11)
        _, c12 = _inn_checksum_12(first11 + "0")
        return first11 + str(c12)
    return None


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
        if _is_valid_inn(inn_clean):
            return inn_clean
        repaired_control = _repair_inn_control_digits(inn_clean)
        if repaired_control and _is_valid_inn(repaired_control):
            return repaired_control
        repaired = _repair_inn_single_digit(inn_clean)
        if repaired:
            return repaired
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
            dt = _fix_ocr_year(dt)
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
                    dt = _fix_ocr_year(dt)
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    continue
    
    return None


_OCR_DIGIT_SWAPS = [
    ('3', '6'),
    ('6', '3'),
    ('8', '3'),
    ('8', '6'),
    ('5', '6'),
    ('6', '5'),
]


def _fix_ocr_year(dt: datetime.datetime) -> datetime.datetime:
    """Try common single-digit OCR swaps on the last digit of year
    when the parsed year is suspiciously old (> 2 years from now)."""
    now = datetime.datetime.now()
    diff = now.year - dt.year
    if diff <= 2:
        return dt

    year_str = str(dt.year)
    last_digit = year_str[-1]

    for wrong, right in _OCR_DIGIT_SWAPS:
        if last_digit != wrong:
            continue
        candidate_year = int(year_str[:-1] + right)
        if abs(now.year - candidate_year) <= 1:
            try:
                return dt.replace(year=candidate_year)
            except ValueError:
                continue
    return dt


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

    # Убираем частый OCR-хвост от бренда фискального регистратора.
    # Пример: "ООО Все Инструменты Ру АТОЛ" -> "ООО Все Инструменты Ру".
    org_str = re.sub(r'\s+[«"\']?АТОЛ[»"\']?\s*$', '', org_str, flags=re.IGNORECASE)

    # OCR fix for common confusion in "СДЭК ФИНАНС".
    # Example: "ООО САЗК ФИНАНС" -> 'ООО "СДЭК ФИНАНС"'
    if re.search(r'\bс[аa]зк\b', org_str, flags=re.IGNORECASE) and re.search(r'\bфинанс\b', org_str, flags=re.IGNORECASE):
        org_str = re.sub(r'\bс[аa]зк\b', 'СДЭК', org_str, flags=re.IGNORECASE)
        if org_str.upper().startswith("ООО ") and '"' not in org_str and "«" not in org_str:
            org_str = 'ООО "СДЭК ФИНАНС"'

    # OCR fix for common confusion in "СДЭК-ГЛОБАЛ".
    # Example: 'ООО "САЭК-ГЛОБАЛ"' -> 'ООО "СДЭК-ГЛОБАЛ"'
    if re.search(r'\bс[аa]эк\b', org_str, flags=re.IGNORECASE) and re.search(r'\bглобал\b', org_str, flags=re.IGNORECASE):
        org_str = re.sub(r'\bс[аa]эк\b', 'СДЭК', org_str, flags=re.IGNORECASE)
    
    return org_str if org_str else None


def is_acquirer_bank_name(org: Any) -> bool:
    if not org:
        return False
    v = str(org).strip().lower()
    bank_markers = (
        "сбербанк",
        "пао сбербанк",
        "sberbank",
        "тинькофф",
        "tinkoff",
        "втб",
        "альфа-банк",
        "альфабанк",
        "альфа банк",
    )
    return any(marker in v for marker in bank_markers)


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
        r'^(чек\s*№?|№|receipt\s*#?|#|номер\s*(чека)?|фд|фд\s*№?|документ\s*№?|n[oо]|no|n)\b[:\s]*',
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

    # Remove trailing VAT markers accidentally glued to item name
    # (e.g. "... НДС20%", "... НДС 5%", "... НДС20/120").
    name_str = re.sub(r'[\s,;:\-]+НДС\s*\d{1,2}(?:\s*%|/\s*\d{2,3})\s*$', '', name_str, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы
    name_str = re.sub(r'\s+', ' ', name_str).strip()
    
    return name_str


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

    if "vat_rate" in result and result["vat_rate"] is not None:
        result["vat_rate"] = normalize_vat_rate(result["vat_rate"])
    
    return result


def normalize_vat_rate(vat_rate: Any) -> Optional[str]:
    if vat_rate is None:
        return None
    raw = str(vat_rate).strip().lower()
    if not raw:
        return None

    if "не облага" in raw or "без ндс" in raw:
        return "без НДС"

    collapsed = re.sub(r"\s+", "", raw)
    # Normalize forms like "20/120", "ндс20/120", "20 / 120", "20\120".
    if "20/120" in collapsed or re.search(r"20[/\\]120", collapsed):
        return "20%"
    if "10/110" in collapsed or re.search(r"10[/\\]110", collapsed):
        return "10%"

    m = re.search(r'(\d{1,2})\s*%', raw)
    if m:
        return f"{m.group(1)}%"
    return str(vat_rate).strip()


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
            
            normalized_item = normalize_item_numbers(normalized_item)
            normalized_items.append(normalized_item)
        
        result["items"] = normalized_items

    # If organization looks like acquiring bank while the document contains goods,
    # prefer empty merchant to avoid false "seller = Sberbank" in mixed/covered slips.
    if is_acquirer_bank_name(result.get("organization")) and (result.get("items") or []):
        result["organization"] = None
    
    result["items"] = merge_orphan_items(result.get("items") or [])

    return result


def merge_orphan_items(items: list) -> list:
    """Merge items that have a name but no price/quantity into the previous item.

    Bilingual menus (hotel/restaurant receipts) often print:
        1 Buckwheat tea          1390.00
        Гречишный чай                       ← orphan: name only, no price
    The model may create a separate entry for the second line.
    """
    if not items:
        return items

    merged: list = []
    for item in items:
        if not isinstance(item, dict):
            merged.append(item)
            continue

        has_price = (
            isinstance(item.get("total_price"), (int, float)) and item["total_price"] > 0
        ) or (
            isinstance(item.get("price_per_unit"), (int, float)) and item["price_per_unit"] > 0
        )

        name = str(item.get("name") or "").strip()

        if not has_price and name and merged:
            prev = merged[-1]
            prev_name = str(prev.get("name") or "").strip()
            prev["name"] = f"{prev_name} {name}".strip()
            continue

        merged.append(item)

    return merged


def distribute_vat_to_items(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    If total_vat is known but per-item vat_amount is missing,
    distribute total_vat proportionally across items by total_price
    and infer vat_rate from common Russian rates (20%, 10%, 5%).
    """
    result = data.copy()
    total_vat = result.get("total_vat")
    if not isinstance(total_vat, (int, float)) or total_vat <= 0:
        return result

    items = result.get("items")
    if not items or not isinstance(items, list):
        return result

    if not all(item.get("vat_amount") is None for item in items if isinstance(item, dict)):
        return result

    def _is_explicitly_non_vat(item: Dict[str, Any]) -> bool:
        rate = str(item.get("vat_rate") or "").strip().lower()
        return rate in {"без ндс", "0%", "0.0%"} or "без ндс" in rate or "не облага" in rate

    # If receipt has mixed VAT markers, distribute only among taxable items.
    # Otherwise keep legacy behavior (all priced items).
    item_dicts = [i for i in items if isinstance(i, dict)]
    has_any_rate = any(str(i.get("vat_rate") or "").strip() for i in item_dicts)
    has_explicit_non_vat = any(_is_explicitly_non_vat(i) for i in item_dicts)

    eligible_items = []
    for item in item_dicts:
        price = item.get("total_price")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        if has_any_rate and has_explicit_non_vat:
            if _is_explicitly_non_vat(item):
                continue
            if not str(item.get("vat_rate") or "").strip():
                continue
        eligible_items.append(item)

    eligible_ids = {id(item) for item in eligible_items}
    total_items_price = sum(float(item.get("total_price") or 0) for item in eligible_items)
    if total_items_price <= 0:
        return result

    total = result.get("total")
    vat_rate_str: Optional[str] = None
    if isinstance(total, (int, float)) and total > 0:
        for rate in (22, 20, 10, 5):
            expected = float(total) * rate / (100 + rate)
            if abs(expected - float(total_vat)) / float(total_vat) < 0.05:
                vat_rate_str = f"{rate}%"
                break

    distributed_sum = 0.0
    updated_items = []
    remaining_eligible = len(eligible_items)
    for i, item in enumerate(items):
        raw_item = item
        item = item.copy() if isinstance(item, dict) else item
        if not isinstance(item, dict):
            updated_items.append(item)
            continue
        if id(raw_item) in eligible_ids:
            item_total = float(item.get("total_price") or 0)
            if remaining_eligible == 1:
                item_vat = round(float(total_vat) - distributed_sum, 2)
            else:
                item_vat = round(float(total_vat) * item_total / total_items_price, 2)
                distributed_sum += item_vat
            item["vat_amount"] = item_vat
            if vat_rate_str and not item.get("vat_rate"):
                item["vat_rate"] = vat_rate_str
            remaining_eligible -= 1
        updated_items.append(item)

    result["items"] = updated_items
    return result