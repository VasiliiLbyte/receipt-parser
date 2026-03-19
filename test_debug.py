#!/usr/bin/env python3
"""Отладочный тест для проверки обработки чисел"""

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data

# Тестируем конкретный случай
test_data = {"total": "1 234,56 руб."}
print(f"Входные данные: {test_data}")

# Вручную пройдем по логике
value_str = str(test_data["total"])
print(f"1. Исходная строка: '{value_str}'")

# Убираем пробелы, символы валюты (но сохраняем точку и запятую)
value_str = re.sub(r'[^\d\.\,\-\s]', '', value_str)
print(f"2. После удаления нечисловых символов: '{value_str}'")

# Убираем пробелы (разделители тысяч в европейском формате)
value_str = value_str.replace(' ', '')
print(f"3. После удаления пробелов: '{value_str}'")

# Определяем формат числа
if ',' in value_str and '.' in value_str:
    print("4. Есть и запятая, и точка")
    last_comma = value_str.rfind(',')
    last_dot = value_str.rfind('.')
    print(f"   Последняя запятая: {last_comma}, последняя точка: {last_dot}")
    if last_comma > last_dot:
        print("   Европейский формат: точка как разделитель тысяч")
        value_str = value_str.replace('.', '').replace(',', '.')
    else:
        print("   Американский формат: запятая как разделитель тысяч")
        value_str = value_str.replace(',', '')
elif ',' in value_str:
    print("4. Только запятая - европейский/русский формат")
    value_str = value_str.replace(',', '.')
elif '.' in value_str:
    print("4. Только точка")
    parts = value_str.split('.')
    if len(parts) == 2 and len(parts[1]) <= 3:
        print(f"   Вероятно десятичный разделитель: {parts[1]} цифр после точки")
    else:
        print(f"   Вероятно разделитель тысяч: {len(parts)} частей")
        value_str = value_str.replace('.', '')

print(f"5. После обработки формата: '{value_str}'")

# Если есть несколько точек, оставляем только последнюю
if value_str.count('.') > 1:
    parts = value_str.split('.')
    value_str = '.'.join(parts[:-1]) + parts[-1]
    print(f"6. После удаления лишних точек: '{value_str}'")

try:
    result = float(value_str)
    print(f"7. Результат как float: {result}")
except Exception as e:
    print(f"7. Ошибка преобразования: {e}")

# Теперь протестируем через функцию
print("\n--- Тестирование через postprocess_data ---")
result = postprocess_data(test_data.copy())
print(f"Результат: {result}")