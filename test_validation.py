#!/usr/bin/env python3
"""Тестирование валидации дат в postprocess_data"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data, _validate_receipt_date

def test_validation_function():
    """Тестирование функции _validate_receipt_date"""
    print("🧪 Тестирование функции _validate_receipt_date")
    print("=" * 50)
    
    test_cases = [
        ("2025-12-31", "2025-12-31", "Нормальная дата"),
        ("2030-01-01", None, "Дата слишком в будущем"),
        ("1999-01-01", None, "Дата до 2000 года"),
        ("2015-01-01", None, "Дата слишком старая (более 10 лет)"),
    ]
    
    all_passed = True
    for input_date, expected, description in test_cases:
        result = _validate_receipt_date(input_date)
        status = "✅ OK" if result == expected else "❌ ОШИБКА"
        print(f"{description}: {input_date} -> {result} {status}")
        if result != expected:
            all_passed = False
    
    return all_passed

def test_postprocess_with_validation():
    """Тестирование postprocess_data с валидацией дат"""
    print("\n🧪 Тестирование postprocess_data с валидацией дат")
    print("=" * 50)
    
    test_cases = [
        {
            "input": {"date": "19.02.2026"},
            "expected_date": "2026-02-19",
            "description": "Нормальная дата в русском формате"
        },
        {
            "input": {"date": "2030-12-31"},
            "expected_date": None,
            "description": "Дата в будущем"
        },
        {
            "input": {"date": "1999-01-01"},
            "expected_date": None,
            "description": "Слишком старая дата"
        },
        {
            "input": {"date": ""},
            "expected_date": None,
            "description": "Пустая строка"
        },
        {
            "input": {"date": None},
            "expected_date": None,
            "description": "None значение"
        },
    ]
    
    all_passed = True
    for test in test_cases:
        print(f"\n📊 Тест: {test['description']}")
        print(f"Вход: {test['input']}")
        
        result = postprocess_data(test['input'].copy())
        actual_date = result.get("date")
        
        print(f"Ожидалось: {test['expected_date']}")
        print(f"Получено: {actual_date}")
        
        if actual_date == test['expected_date']:
            print("✅ OK")
        else:
            print("❌ ОШИБКА")
            all_passed = False
    
    return all_passed

def test_complete_receipt():
    """Тестирование полного чека с валидацией"""
    print("\n🧪 Тестирование полного чека")
    print("=" * 50)
    
    data = {
        'organization': 'ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ',
        'inn': 'ИНН: 781603445844',
        'date': '19.02.2026',
        'receipt_number': 'Чек № 123456',
        'items': [
            {
                'name': 'Товар с НАС 20%',
                'price_per_unit': '100,50',
                'quantity': '2',
                'total_price': '201,00',
                'vat_rate': '20%',
                'vat_amount': '33,50'
            }
        ],
        'total': '1 234,56 руб.',
        'total_vat': '205,76'
    }
    
    print("Входные данные:")
    for key, value in data.items():
        if key == 'items':
            print(f"  {key}: {len(value)} товар(ов)")
        else:
            print(f"  {key}: {value}")
    
    result = postprocess_data(data.copy())
    
    print("\nРезультат:")
    print(f"  Дата: {result.get('date')} (ожидается 2026-02-19)")
    print(f"  ИНН: {result.get('inn')} (ожидается 781603445844)")
    print(f"  Номер чека: {result.get('receipt_number')} (ожидается 123456)")
    print(f"  Общая сумма: {result.get('total')} (ожидается 1234.56)")
    print(f"  Общий НДС: {result.get('total_vat')} (ожидается 205.76)")
    
    if result.get('items'):
        item = result['items'][0]
        print(f"  Название товара: {item.get('name')} (должно быть 'Товар с НДС 20%')")
        print(f"  Цена за единицу: {item.get('price_per_unit')} (ожидается 100.5)")
        print(f"  Количество: {item.get('quantity')} (ожидается 2.0)")
        print(f"  Общая цена: {item.get('total_price')} (ожидается 201.0)")
        print(f"  Сумма НДС: {item.get('vat_amount')} (ожидается 33.5)")
    
    # Проверяем ключевые поля
    checks = [
        (result.get('date') == '2026-02-19', "Дата"),
        (result.get('inn') == '781603445844', "ИНН"),
        (result.get('receipt_number') == '123456', "Номер чека"),
        (abs(result.get('total', 0) - 1234.56) < 0.01, "Общая сумма"),
        (result.get('items') and result['items'][0].get('name') == 'Товар с НДС 20%', "Название товара"),
    ]
    
    all_ok = True
    for check_passed, field in checks:
        if check_passed:
            print(f"✅ {field}: OK")
        else:
            print(f"❌ {field}: ОШИБКА")
            all_ok = False
    
    return all_ok

if __name__ == "__main__":
    print("🚀 Запуск тестов валидации дат")
    print("=" * 50)
    
    test1_passed = test_validation_function()
    test2_passed = test_postprocess_with_validation()
    test3_passed = test_complete_receipt()
    
    print("\n" + "=" * 50)
    print("📋 Итоги тестирования:")
    print(f"  Тест 1 (функция валидации): {'✅ ПРОШЕЛ' if test1_passed else '❌ НЕ ПРОШЕЛ'}")
    print(f"  Тест 2 (postprocess_data): {'✅ ПРОШЕЛ' if test2_passed else '❌ НЕ ПРОШЕЛ'}")
    print(f"  Тест 3 (полный чек): {'✅ ПРОШЕЛ' if test3_passed else '❌ НЕ ПРОШЕЛ'}")
    
    all_passed = test1_passed and test2_passed and test3_passed
    if all_passed:
        print("\n🎉 Все тесты успешно пройдены!")
    else:
        print("\n⚠️  Некоторые тесты не прошли")