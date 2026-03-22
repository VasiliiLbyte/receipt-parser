#!/usr/bin/env python3
"""Тестирование обработки пустой даты"""

from src.openai_client import postprocess_data

# Тестируем пустую строку
data = {"date": ""}
result = postprocess_data(data)
print(f"Вход: ''")
print(f"Результат: {result.get('date')}")
print(f"Тип результата: {type(result.get('date'))}")

# Тестируем None
data2 = {"date": None}
result2 = postprocess_data(data2)
print(f"\nВход: None")
print(f"Результат: {result2.get('date')}")
print(f"Тип результата: {type(result2.get('date'))}")

# Тестируем строку с пробелами
data3 = {"date": "   "}
result3 = postprocess_data(data3)
print(f"\nВход: '   '")
print(f"Результат: {result3.get('date')}")
print(f"Тип результата: {type(result3.get('date'))}")