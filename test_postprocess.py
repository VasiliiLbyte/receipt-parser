#!/usr/bin/env python3
"""Тестирование улучшенной функции postprocess_data"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data

def test_postprocess_data():
    """Тестирование различных сценариев обработки данных"""
    
    print("🧪 Тестирование улучшенной функции postprocess_data")
    print("=" * 60)
    
    # Тест 1: Нормальная дата в разных форматах
    test_cases = [
        {
            "name": "Тест 1: Дата в формате ГГГГ-ММ-ДД",
            "input": {"date": "2025-12-31", "receipt_number": "Чек № 12345", "total": "1 234,56 руб."},
            "expected_date": "2025-12-31",
            "expected_receipt": "12345",
            "expected_total": 1234.56
        },
        {
            "name": "Тест 2: Дата в формате ДД.ММ.ГГГГ",
            "input": {"date": "31.12.2025", "receipt_number": "Receipt # 67890", "total": "2,345.67"},
            "expected_date": "2025-12-31",
            "expected_receipt": "67890",
            "expected_total": 2345.67
        },
        {
            "name": "Тест 3: Дата в формате ДД.ММ.ГГ",
            "input": {"date": "31.12.25", "receipt_number": "Номер чека: ABC-123", "total": "3 456.78"},
            "expected_date": "2025-12-31",
            "expected_receipt": "ABC-123",
            "expected_total": 3456.78
        },
        {
            "name": "Тест 4: Дата с лишними символами",
            "input": {"date": "[31/12/2025]", "receipt_number": "Чек№98765", "total": "4.567,89"},
            "expected_date": "2025-12-31",
            "expected_receipt": "98765",
            "expected_total": 4567.89
        },
        {
            "name": "Тест 5: Некорректная дата",
            "input": {"date": "неверная дата", "receipt_number": "Test-456", "total": "invalid"},
            "expected_date": None,
            "expected_receipt": "Test-456",
            "expected_total": None
        },
        {
            "name": "Тест 6: ИНН с лишними символами",
            "input": {"inn": "ИНН: 781603445844", "date": "2025-01-15", "receipt_number": "123-456-789"},
            "expected_inn": "781603445844",
            "expected_receipt": "123-456-789"
        },
        {
            "name": "Тест 7: Товары с числовыми полями",
            "input": {
                "items": [
                    {"name": "Товар 1", "price_per_unit": "100,50", "quantity": "2", "total_price": "201,00"},
                    {"name": "Товар 2", "price_per_unit": "50.25", "quantity": "3", "total_price": "150.75"}
                ]
            },
            "expected_items": [
                {"name": "Товар 1", "price_per_unit": 100.5, "quantity": 2.0, "total_price": 201.0},
                {"name": "Товар 2", "price_per_unit": 50.25, "quantity": 3.0, "total_price": 150.75}
            ]
        },
        {
            "name": "Тест 8: Обработка НДС в названиях",
            "input": {
                "items": [
                    {"name": "Товар с НАС 20%", "price_per_unit": "100", "quantity": "1", "total_price": "100"}
                ]
            },
            "expected_items": [
                {"name": "Товар с НДС 20%", "price_per_unit": 100.0, "quantity": 1.0, "total_price": 100.0}
            ]
        }
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}")
        print(f"Входные данные: {test_case['input']}")
        
        result = postprocess_data(test_case['input'].copy())
        print(f"Результат: {result}")
        
        # Проверяем ожидаемые результаты
        success = True
        
        if 'expected_date' in test_case:
            if result.get('date') != test_case['expected_date']:
                print(f"❌ Ошибка даты: ожидалось '{test_case['expected_date']}', получено '{result.get('date')}'")
                success = False
        
        if 'expected_receipt' in test_case:
            if result.get('receipt_number') != test_case['expected_receipt']:
                print(f"❌ Ошибка номера чека: ожидалось '{test_case['expected_receipt']}', получено '{result.get('receipt_number')}'")
                success = False
        
        if 'expected_total' in test_case:
            if result.get('total') != test_case['expected_total']:
                print(f"❌ Ошибка общей суммы: ожидалось {test_case['expected_total']}, получено {result.get('total')}")
                success = False
        
        if 'expected_inn' in test_case:
            if result.get('inn') != test_case['expected_inn']:
                print(f"❌ Ошибка ИНН: ожидалось '{test_case['expected_inn']}', получено '{result.get('inn')}'")
                success = False
        
        if 'expected_items' in test_case:
            if 'items' in result:
                for i, (actual, expected) in enumerate(zip(result['items'], test_case['expected_items'])):
                    for key in expected:
                        if actual.get(key) != expected[key]:
                            print(f"❌ Ошибка в товаре {i}, поле {key}: ожидалось {expected[key]}, получено {actual.get(key)}")
                            success = False
        
        if success:
            print("✅ Тест пройден")
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"📊 Итоги тестирования:")
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Не пройдено: {failed}")
    print(f"🎯 Успешность: {passed/(passed+failed)*100:.1f}%")
    
    return failed == 0

if __name__ == "__main__":
    success = test_postprocess_data()
    sys.exit(0 if success else 1)