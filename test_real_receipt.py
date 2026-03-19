#!/usr/bin/env python3
"""Тестирование на реальных данных чека"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data

def test_real_receipt_data():
    """Тестирование с данными, похожими на реальный чек"""
    print("🧪 Тестирование на реальных данных чека")
    print("=" * 50)
    
    # Пример данных, которые могут прийти от OpenAI
    test_data = {
        "organization": "ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ",
        "inn": "781603445844",
        "date": "19.02.2026",
        "receipt_number": "Чек № 123456",
        "items": [
            {
                "name": "Товар 1",
                "price_per_unit": "119.0",
                "quantity": "1.000",
                "total_price": "119.0",
                "vat_rate": "20%",
                "vat_amount": "19.83"
            },
            {
                "name": "Товар 2",
                "price_per_unit": "59.50",
                "quantity": "2.000",
                "total_price": "119.0",
                "vat_rate": "20%",
                "vat_amount": "19.83"
            }
        ],
        "total": "238.0",
        "total_vat": "39.66"
    }
    
    print("📄 Исходные данные:")
    print(f"  Организация: {test_data['organization']}")
    print(f"  ИНН: {test_data['inn']}")
    print(f"  Дата: {test_data['date']}")
    print(f"  Номер чека: {test_data['receipt_number']}")
    print(f"  Общая сумма: {test_data['total']}")
    print(f"  НДС всего: {test_data['total_vat']}")
    print(f"  Товары: {len(test_data['items'])} позиций")
    
    print("\n🔄 Обработка данных...")
    result = postprocess_data(test_data)
    
    print("\n✅ Результаты обработки:")
    print(f"  Организация: {result['organization']}")
    print(f"  ИНН: {result['inn']}")
    print(f"  Дата: {result['date']}")
    print(f"  Номер чека: {result['receipt_number']}")
    print(f"  Общая сумма: {result['total']}")
    print(f"  НДС всего: {result['total_vat']}")
    
    print("\n📦 Товары после обработки:")
    for i, item in enumerate(result['items'], 1):
        print(f"  {i}. {item['name']}")
        print(f"     Цена за ед.: {item['price_per_unit']}")
        print(f"     Количество: {item['quantity']}")
        print(f"     Стоимость: {item['total_price']}")
        print(f"     НДС: {item['vat_rate']} ({item['vat_amount']})")
    
    print("\n" + "=" * 50)
    print("📋 Проверка исправления проблемы:")
    
    # Проверяем, что 119.0 не превратилось в 1190.0
    total_correct = result['total'] == 238.0
    item1_price_correct = result['items'][0]['price_per_unit'] == 119.0
    item1_total_correct = result['items'][0]['total_price'] == 119.0
    
    if total_correct and item1_price_correct and item1_total_correct:
        print("✅ Проблема исправлена: числа не умножаются на 10")
    else:
        print("❌ Проблема не исправлена!")
        print(f"   Общая сумма: ожидалось 238.0, получено {result['total']}")
        print(f"   Цена товара 1: ожидалось 119.0, получено {result['items'][0]['price_per_unit']}")
    
    return True

if __name__ == "__main__":
    test_real_receipt_data()