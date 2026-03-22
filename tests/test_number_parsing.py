#!/usr/bin/env python3
"""Тестирование парсинга чисел"""

import re

def test_number_parsing():
    """Тестирование логики парсинга чисел из postprocess_data"""
    print("🧪 Тестирование парсинга чисел")
    print("=" * 50)
    
    test_cases = [
        ('1 234,56 руб.', 1234.56, "Русский формат с пробелом"),
        ('1.234,56', 1234.56, "Европейский формат"),
        ('1,234.56', 1234.56, "Американский формат"),
        ('1234,56', 1234.56, "Только запятая как разделитель"),
        ('1234.56', 1234.56, "Только точка как разделитель"),
        ('100,50', 100.5, "Цена с запятой"),
        ('201,00', 201.0, "Сумма с двумя нулями после запятой"),
        ('205,76', 205.76, "НДС с запятой"),
        ('33,50', 33.5, "Сумма НДС"),
    ]
    
    for input_str, expected, description in test_cases:
        print(f"\n📊 Тест: {description}")
        print(f"  Вход: '{input_str}'")
        
        # Шаг 1: Удаляем все символы, кроме цифр, точек и запятых
        value_str = re.sub(r'[^\d\.,]', '', input_str)
        print(f"  После очистки: '{value_str}'")
        
        # Если строка пустая, устанавливаем None
        if not value_str:
            print(f"  Результат: None")
            continue
        
        # Определяем, есть ли десятичная часть (копейки/центы)
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
            elif digits_after == 3:
                has_decimal = False
        
        print(f"  last_comma: {last_comma}, last_dot: {last_dot}")
        print(f"  decimal_separator: {decimal_separator}, has_decimal: {has_decimal}")
        
        if has_decimal and decimal_separator:
            # Есть десятичная часть, сохраняем ее
            # Удаляем все другие разделители (разделители тысяч)
            if decimal_separator == ',':
                # Европейский формат: "1.234,56" -> удаляем точки
                result_str = value_str.replace('.', '').replace(',', '.')
                print(f"  Европейский формат -> '{result_str}'")
            else:
                # Американский формат: "1,234.56" -> удаляем запятые
                result_str = value_str.replace(',', '')
                print(f"  Американский формат -> '{result_str}'")
        else:
            # Нет десятичной части или неясный формат
            # Удаляем все разделители и предполагаем целое число
            result_str = re.sub(r'[^\d]', '', value_str)
            if result_str:
                result_str = result_str + '.00'
                print(f"  Без десятичной части -> '{result_str}'")
            else:
                print(f"  Пустая строка -> None")
                continue
        
        try:
            result = float(result_str)
            print(f"  Результат: {result} (ожидается {expected})")
            if abs(result - expected) < 0.01:
                print("  ✅ OK")
            else:
                print(f"  ❌ ОШИБКА: разница {abs(result - expected)}")
        except Exception as e:
            print(f"  ❌ Ошибка преобразования: {e}")

def test_actual_postprocess():
    """Тестирование фактической функции postprocess_data"""
    print("\n🧪 Тестирование фактической функции postprocess_data")
    print("=" * 50)
    
    from src.openai_client import postprocess_data
    
    # Тест с полным чеком
    data = {
        'total': '1 234,56 руб.',
        'total_vat': '205,76'
    }
    
    print(f"Входные данные: {data}")
    result = postprocess_data(data.copy())
    print(f"Результат: total={result.get('total')}, total_vat={result.get('total_vat')}")
    
    # Проверяем
    total_ok = abs(result.get('total', 0) - 1234.56) < 0.01
    vat_ok = abs(result.get('total_vat', 0) - 205.76) < 0.01
    
    if total_ok and vat_ok:
        print("✅ Все числа распарсены правильно")
    else:
        print("❌ Ошибка в парсинге чисел")
        if not total_ok:
            print(f"  total: ожидалось 1234.56, получено {result.get('total')}")
        if not vat_ok:
            print(f"  total_vat: ожидалось 205.76, получено {result.get('total_vat')}")

if __name__ == "__main__":
    test_number_parsing()
    test_actual_postprocess()