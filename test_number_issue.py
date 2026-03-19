#!/usr/bin/env python3
"""Тестирование проблемы с числами: 119 → 1190"""

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data

def test_number_parsing():
    """Тестирование парсинга чисел"""
    print("🧪 Тестирование парсинга чисел")
    print("=" * 50)
    
    test_cases = [
        ("119", "119.0", "Простое целое число"),
        ("119.00", "119.0", "Число с десятичной частью"),
        ("119,00", "119.0", "Число с запятой как десятичным разделителем"),
        ("1.19", "1.19", "Число с точкой как десятичным разделителем"),
        ("1,19", "1.19", "Число с запятой как десятичным разделителем"),
        ("1 190", "1190.0", "Число с пробелом как разделителем тысяч"),
        ("1.190", "1190.0", "Число с точкой как разделителем тысяч"),
        ("1,190", "1190.0", "Число с запятой как разделителем тысяч"),
        ("119 руб.", "119.0", "Число с символом валюты"),
        ("119,0", "119.0", "Число с одной цифрой после запятой"),
        ("119.0", "119.0", "Число с одной цифрой после точки"),
    ]
    
    for input_val, expected, description in test_cases:
        print(f"\n📊 Тест: {description}")
        print(f"   Вход: '{input_val}'")
        
        # Имитируем данные
        data = {"total": input_val}
        result = postprocess_data(data)
        
        actual = result.get("total")
        print(f"   Ожидалось: {expected}")
        print(f"   Получено: {actual}")
        
        if actual == float(expected) if expected != "None" else actual is None:
            print("   ✅ OK")
        else:
            print("   ❌ ОШИБКА")
    
    print("\n" + "=" * 50)
    print("📋 Анализ проблемы:")
    print("Проблема: '119' → '1190.0' (умножает на 10)")
    print("Причина: вероятно, точка от 'руб.' или другая точка мешает")
    print("Решение: нужно лучше очищать входные данные")

if __name__ == "__main__":
    test_number_parsing()