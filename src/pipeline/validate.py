"""
Pure validation functions extracted from postprocess_data.

These functions are provider-agnostic and work on normalized data.
They should not contain any provider-specific logic or I/O operations.
"""

import datetime
from typing import Any, Dict, List, Optional, Tuple


def validate_receipt_date(date_str: Optional[str]) -> Tuple[Optional[str], List[str]]:
    """
    Валидация даты чека.
    
    Args:
        date_str: дата в формате ГГГГ-ММ-ДД (уже нормализованная)
        
    Returns:
        Tuple[валидная дата или None, список предупреждений]
    """
    warnings = []
    
    if not date_str:
        return None, warnings
    
    try:
        # Парсим дату из строки формата ГГГГ-ММ-ДД
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        current_date = datetime.datetime.now()
        
        # Проверяем, что дата не в будущем более чем на 1 год
        max_future_date = current_date + datetime.timedelta(days=365)
        if dt > max_future_date:
            warnings.append(f"Дата {date_str} слишком в будущем (более чем на 1 год)")
            return None, warnings
        
        # Проверяем, что дата не слишком старая (не старше 10 лет)
        min_past_date = current_date - datetime.timedelta(days=3650)  # 10 лет
        if dt < min_past_date:
            warnings.append(f"Дата {date_str} слишком старая (более 10 лет)")
            return None, warnings
        
        # Проверяем, что дата не в далеком прошлом (до 2000 года)
        if dt.year < 2000:
            warnings.append(f"Дата {date_str} слишком старая (до 2000 года)")
            return None, warnings
        
        # Эвристика: год не должен быть "подозрительно старым" для свежего чека
        current_year = datetime.datetime.now().year
        parsed_year = int(date_str[:4])
        if current_year - parsed_year > 2:
            warnings.append(
                f"Подозрительный год в дате: {date_str} "
                f"(текущий год: {current_year}, разница: {current_year - parsed_year} лет). "
                f"Возможна OCR-ошибка — проверьте чек вручную."
            )
            # Не блокируем, только предупреждение
            return date_str, warnings
        
        return date_str, warnings
    except Exception as e:
        warnings.append(f"Ошибка валидации даты {date_str}: {e}")
        return None, warnings


def validate_inn(inn: Optional[str]) -> Tuple[Optional[str], List[str]]:
    """
    Валидация ИНН.
    
    Args:
        inn: очищенный ИНН (только цифры)
        
    Returns:
        Tuple[валидный ИНН или None, список предупреждений]
    """
    warnings = []
    
    if not inn:
        return None, warnings
    
    # Проверяем длину
    if len(inn) not in [10, 12]:
        warnings.append(f"ИНН содержит {len(inn)} цифр (ожидалось 10 или 12): {inn}")
        return None, warnings
    
    # TODO: Добавить проверку контрольной суммы при необходимости
    return inn, warnings


def validate_totals(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Валидация итоговых сумм.
    
    Args:
        data: словарь с данными (уже нормализованными)
        
    Returns:
        Tuple[обновленные данные, список предупреждений]
    """
    warnings = []
    result = data.copy()
    
    # Проверяем, что общая сумма не отрицательная
    total = result.get("total")
    if total is not None and total < 0:
        warnings.append(f"Общая сумма отрицательная: {total}")
        # Не исправляем автоматически
    
    # Проверяем, что НДС не больше общей суммы
    total_vat = result.get("total_vat")
    if total is not None and total_vat is not None:
        if total_vat > total:
            warnings.append(f"НДС ({total_vat}) больше общей суммы ({total})")
    
    # Проверяем суммы по товарам
    if "items" in result:
        for i, item in enumerate(result["items"]):
            price_per_unit = item.get("price_per_unit")
            quantity = item.get("quantity")
            total_price = item.get("total_price")
            
            if price_per_unit is not None and quantity is not None and total_price is not None:
                # Проверяем расчет: price_per_unit * quantity ≈ total_price
                calculated = price_per_unit * quantity
                tolerance = 0.01  # Допуск 1 копейка
                if abs(calculated - total_price) > tolerance:
                    warnings.append(
                        f"Товар {i+1}: расхождение в расчетах "
                        f"({price_per_unit} * {quantity} = {calculated:.2f}, "
                        f"указано {total_price})"
                    )
    
    return result, warnings


def validate_items_consistency(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Проверка согласованности данных товаров.
    
    Args:
        data: словарь с данми (уже нормализованными)
        
    Returns:
        Tuple[обновленные данные, список предупреждений]
    """
    warnings = []
    result = data.copy()
    
    if "items" not in result:
        return result, warnings
    
    # Проверяем, что у всех товаров есть названия
    for i, item in enumerate(result["items"]):
        if not item.get("name"):
            warnings.append(f"Товар {i+1}: отсутствует название")
    
    # Проверяем, что количество положительное
    for i, item in enumerate(result["items"]):
        quantity = item.get("quantity")
        if quantity is not None and quantity <= 0:
            warnings.append(f"Товар {i+1}: некорректное количество ({quantity})")
    
    return result, warnings


def _is_service_line(name: str) -> bool:
    upper = name.upper()
    service_markers = (
        "VAT", "НДС", "TAX", "ВКЛ.НДС", "INCL.VAT", "НАЛОГ",
        "TOTAL", "ИТОГО", "ИТОГО К ОПЛАТЕ", "СУММА",
        "ЧАЕВЫЕ", "TIPS", "SERVICE CHARGE",
    )
    return any(marker in upper for marker in service_markers)


def _extract_explicit_vat_amount(item: Dict[str, Any]) -> Optional[float]:
    # Do not calculate VAT. Only use explicit numeric amount from service line fields.
    for key in ("vat_amount", "total_price", "price_per_unit"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            amount = float(value)
            if amount >= 0:
                return amount
    return None


def sanitize_items_and_totals(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    warnings = []
    result = data.copy()
    items = result.get("items") or []
    if not isinstance(items, list):
        return result, warnings

    clean_items: List[Dict[str, Any]] = []
    vat_from_service_lines = 0.0
    has_vat_service_lines = False

    for idx, item in enumerate(items, 1):
        if not isinstance(item, dict):
            warnings.append(f"Товар {idx}: пропущена некорректная запись")
            continue
        name = str(item.get("name") or "").strip()
        if _is_service_line(name):
            is_vat_line = any(
                marker in name.upper() for marker in ("VAT", "НДС", "TAX", "ВКЛ.НДС", "INCL.VAT", "НАЛОГ")
            )
            has_vat_service_lines = has_vat_service_lines or is_vat_line
            amount = _extract_explicit_vat_amount(item)
            if amount is not None and is_vat_line:
                vat_from_service_lines += amount
            warnings.append(f"Строка '{name}' исключена из товаров как служебная")
            continue
        clean_items.append(item)

    result["items"] = clean_items

    if has_vat_service_lines:
        current_total_vat = result.get("total_vat")
        if isinstance(current_total_vat, (int, float)):
            # Keep the larger explicit value to avoid undercount when OCR captured both aggregate and split VAT lines.
            result["total_vat"] = max(float(current_total_vat), vat_from_service_lines)
        else:
            result["total_vat"] = vat_from_service_lines if vat_from_service_lines > 0 else current_total_vat

    # Heuristic fallback: sometimes VAT line is misclassified as a normal item without VAT/TOTAL markers.
    # If removing one suspicious item improves consistency with total, drop it.
    total = result.get("total")
    if isinstance(total, (int, float)) and isinstance(result.get("items"), list):
        priced_items: List[Tuple[int, float]] = []
        for idx, item in enumerate(result["items"]):
            if not isinstance(item, dict):
                continue
            amount = item.get("total_price")
            if isinstance(amount, (int, float)):
                priced_items.append((idx, float(amount)))

        if len(priced_items) >= 2:
            sum_items = sum(v for _, v in priced_items)
            base_diff = abs(sum_items - float(total))
            if base_diff > 0.01:
                best_idx = None
                best_new_diff = base_diff
                total_vat = result.get("total_vat")

                for idx, amount in priced_items:
                    item = result["items"][idx]
                    quantity = item.get("quantity")
                    vat_amount = item.get("vat_amount")
                    is_single = quantity in (None, 1, 1.0)
                    no_item_vat = vat_amount is None
                    matches_total_vat = isinstance(total_vat, (int, float)) and abs(amount - float(total_vat)) <= 0.01
                    suspicious = is_single and no_item_vat and (matches_total_vat or amount > 0)
                    if not suspicious:
                        continue

                    new_diff = abs((sum_items - amount) - float(total))
                    if new_diff + 1e-9 < best_new_diff:
                        best_new_diff = new_diff
                        best_idx = idx

                if best_idx is not None and best_new_diff + 1e-9 < base_diff:
                    removed = result["items"].pop(best_idx)
                    removed_amount = _extract_explicit_vat_amount(removed)
                    current_total_vat = result.get("total_vat")
                    if removed_amount is not None and not isinstance(current_total_vat, (int, float)):
                        result["total_vat"] = removed_amount
                    warnings.append(
                        f"Строка '{removed.get('name')}' исключена как вероятная служебная (НДС/итог), "
                        f"чтобы согласовать сумму позиций с итогом чека"
                    )

    return result, warnings


def validate_flat_data(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Полная валидация плоских данных.
    
    Args:
        data: нормализованные данные
        
    Returns:
        Tuple[валидированные данные, список предупреждений]
    """
    if not data:
        return data, []
    
    warnings = []
    result = data.copy()
    
    # Валидация отдельных полей
    if "date" in result:
        validated_date, date_warnings = validate_receipt_date(result["date"])
        result["date"] = validated_date
        warnings.extend(date_warnings)
    
    if "inn" in result:
        validated_inn, inn_warnings = validate_inn(result["inn"])
        result["inn"] = validated_inn
        warnings.extend(inn_warnings)
    
    # Валидация итогов
    validated_totals, totals_warnings = validate_totals(result)
    result.update(validated_totals)
    warnings.extend(totals_warnings)
    
    # Валидация товаров
    validated_items, items_warnings = validate_items_consistency(result)
    result.update(validated_items)
    warnings.extend(items_warnings)

    # Очистка служебных строк (VAT/TOTAL/Tips), которые не должны быть товарами.
    sanitized, sanitize_warnings = sanitize_items_and_totals(result)
    result.update(sanitized)
    warnings.extend(sanitize_warnings)
    
    return result, warnings