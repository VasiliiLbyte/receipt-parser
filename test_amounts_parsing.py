#!/usr/bin/env python3
"""Тестирование кросс-проверки числовых сумм"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data

def test_amounts():
    print("🧪 Тестирование кросс-проверки сумм")
    print("=" * 50)

    # Тест 1: Корректные данные — нет ошибок
    data = {
        "total": 300.00,
        "total_vat": 27.27,
        "items": [
            {"name": "Товар А", "price_per_unit": 100.0, "quantity": 2.0, "total_price": 200.0, "vat_amount": None},
            {"name": "Товар Б", "price_per_unit": 100.0, "quantity": 1.0, "total_price": 100.0, "vat_amount": None},
        ]
    }
    result = postprocess_data(data)
    assert result.get("_amounts_mismatch") == False, "Тест 1 провален: ошибка не должна быть"
    print("✅ Тест 1: корректные данные — OK")

    # Тест 2: Расхождение total с суммой позиций
    data2 = {
        "total": 500.00,  # Неверно — должно быть 300
        "total_vat": None,
        "items": [
            {"name": "Товар А", "price_per_unit": 100.0, "quantity": 2.0, "total_price": 200.0, "vat_amount": None},
            {"name": "Товар Б", "price_per_unit": 100.0, "quantity": 1.0, "total_price": 100.0, "vat_amount": None},
        ]
    }
    result2 = postprocess_data(data2)
    assert result2.get("_amounts_mismatch") == True, "Тест 2 провален: должно быть расхождение"
    print("✅ Тест 2: расхождение total — обнаружено корректно")

    # Тест 3: price * qty != total_price у позиции
    data3 = {
        "total": 250.0,
        "total_vat": None,
        "items": [
            {"name": "Товар А", "price_per_unit": 100.0, "quantity": 2.0, "total_price": 250.0, "vat_amount": None},
            # 100 * 2 = 200, но total_price = 250 — расхождение
        ]
    }
    result3 = postprocess_data(data3)
    # Итог совпадает с total, но позиция ошибочна — должно быть в логах
    print("✅ Тест 3: расхождение price×qty в позиции — проверь лог выше")

    # Тест 4: НДС больше итога — явная ошибка
    data4 = {
        "total": 100.0,
        "total_vat": 500.0,  # Больше итога — OCR ошибка
        "items": []
    }
    result4 = postprocess_data(data4)
    print("✅ Тест 4: НДС > total — предупреждение в логе выше")

    print("\n✅ Все тесты выполнены")

if __name__ == "__main__":
    test_amounts()