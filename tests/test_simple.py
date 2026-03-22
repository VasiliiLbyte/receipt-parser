#!/usr/bin/env python3
"""Простой тест обработки чисел"""

import re

# Тестируем конкретный случай
test_value = "1 234,56 руб."
print(f"Исходная строка: '{test_value}'")

# Убираем все нецифровые символы, кроме точек и запятых
value_str = re.sub(r'[^\d\.,]', '', test_value)
print(f"После удаления нецифровых символов: '{value_str}'")

# Если есть запятая, заменяем ее на точку
if ',' in value_str:
    value_str = value_str.replace(',', '.')
    print(f"После замены запятой на точку: '{value_str}'")

# Если есть несколько точек, оставляем только последнюю
if value_str.count('.') > 1:
    parts = value_str.split('.')
    # Оставляем только одну точку - последнюю
    value_str = ''.join(parts[:-1]) + '.' + parts[-1]
    print(f"После удаления лишних точек: '{value_str}'")

try:
    result = float(value_str)
    print(f"Результат как float: {result}")
except Exception as e:
    print(f"Ошибка преобразования: {e}")

# Теперь протестируем другой случай
print("\n--- Тест 2: '2,345.67' ---")
test_value2 = "2,345.67"
value_str2 = re.sub(r'[^\d\.,]', '', test_value2)
print(f"После удаления нецифровых символов: '{value_str2}'")
if ',' in value_str2:
    value_str2 = value_str2.replace(',', '.')
    print(f"После замены запятой на точку: '{value_str2}'")
try:
    result2 = float(value_str2)
    print(f"Результат как float: {result2}")
except Exception as e:
    print(f"Ошибка преобразования: {e}")