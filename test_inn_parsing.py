#!/usr/bin/env python3
"""Тестирование парсинга и валидации ИНН"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import postprocess_data

def test_inn_parsing():
    print("🧪 Тестирование парсинга ИНН")
    print("=" * 50)

    test_cases = [
        # Валидные ИНН
        ("7816034458",   "7816034458",   "ИП — 10 цифр, корректный"),
        ("781603445844", "781603445844", "Физлицо — 12 цифр, корректный"),

        # OCR-артефакты: буквы вместо цифр
        ("781603445О44", "781603445044", "Буква О вместо цифры 0"),
        ("7816О3445844", "7816034458**", "Буква О внутри ИНН"),
        ("78160З445844", "781603445844", "Буква З вместо цифры 3"),
        ("7816034458В4", "7816034458**", "Буква В вместо цифры 8"),
        ("78l603445844", "781603445844", "Буква l вместо цифры 1"),

        # С лишними символами
        ("ИНН: 7816034458",   "7816034458", "Префикс ИНН:"),
        ("7816-0344-58",       "7816034458", "С дефисами"),
        ("7816 034458",        "7816034458", "С пробелом"),

        # Некорректные — должны вернуть None
        ("123456789",    None, "9 цифр — слишком мало"),
        ("12345678901",  None, "11 цифр — лишняя цифра"),
        ("1234567890123", None, "13 цифр — слишком много"),
        ("абвгдеёжзи",   None, "Только буквы"),
        ("",             None, "Пустая строка"),
        (None,           None, "None значение"),
    ]

    all_passed = True
    for input_inn, expected, description in test_cases:
        data = {"inn": input_inn}
        result = postprocess_data(data)
        actual = result.get("inn")

        # Для тест-кейсов с ** — просто проверяем что не None и длина 10 или 12
        if expected and expected.endswith("**"):
            ok = actual is not None and len(actual) in [10, 12]
        else:
            ok = actual == expected

        status = "✅ OK" if ok else "❌ ОШИБКА"
        if not ok:
            all_passed = False
        print(f"{status} | {description}")
        print(f"       Вход: '{input_inn}' → Ожидалось: {expected} → Получено: {actual}")

    print("\n" + "=" * 50)
    if all_passed:
        print("✅ Все тесты прошли успешно")
    else:
        print("⚠️  Некоторые тесты не прошли — нужна доработка")

if __name__ == "__main__":
    test_inn_parsing()