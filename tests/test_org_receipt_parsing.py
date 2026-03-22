#!/usr/bin/env python3
"""Тестирование парсинга организации и номера чека"""

from src.openai_client import postprocess_data

def test_organization_parsing():
    print("🧪 Тестирование парсинга организации")
    print("=" * 50)

    test_cases = [
        # Валидные названия
        ('ИП ИВАНОВ ИВАН ИВАНОВИЧ',     'ИП ИВАНОВ ИВАН ИВАНОВИЧ',  'ИП — корректное'),
        ('ООО "РОМАШКА"',               'ООО "РОМАШКА"',             'ООО с кавычками'),
        ('АО ПЯТЁРОЧКА',                'АО ПЯТЁРОЧКА',              'АО без кавычек'),

        # С лишними символами по краям
        ('ИП ИВАНОВ ИВАН ИВАНОВИЧ.',    'ИП ИВАНОВ ИВАН ИВАНОВИЧ',  'Точка в конце'),
        ('  ООО "РОМАШКА"  ',           'ООО "РОМАШКА"',             'Пробелы по краям'),

        # Множественные пробелы внутри
        ('ИП  ИВАНОВ   ИВАН',           'ИП ИВАНОВ ИВАН',            'Двойные пробелы'),

        # Некорректные — должны вернуть None
        ('',    None, 'Пустая строка'),
        (None,  None, 'None значение'),
    ]

    all_passed = True
    for input_val, expected, description in test_cases:
        data = {"organization": input_val}
        result = postprocess_data(data)
        actual = result.get("organization")
        ok = actual == expected
        if not ok:
            all_passed = False
        status = "✅ OK" if ok else "❌ ОШИБКА"
        print(f"{status} | {description}")
        print(f"       Вход: '{input_val}' → Ожидалось: '{expected}' → Получено: '{actual}'")

    return all_passed


def test_receipt_number_parsing():
    print("\n🧪 Тестирование парсинга номера чека")
    print("=" * 50)

    test_cases = [
        # Чистые номера
        ('123456',          '123456',   'Чистый номер'),
        ('А-00123',         'А-00123',  'Номер с буквой и дефисом'),
        ('ФД-456789',       'ФД-456789','Номер с ФД'),

        # С префиксами (должны убираться)
        ('Чек № 123456',    '123456',   'Префикс "Чек №"'),
        ('№ 123456',        '123456',   'Префикс "№"'),
        ('Receipt # 123456','123456',   'Английский префикс'),
        ('Номер чека: 456', '456',      'Префикс "Номер чека:"'),
        ('ФД 123456',       '123456',   'Префикс ФД'),

        # OCR-артефакты в номере
        ('12З456',          '123456',   'Буква З → 3'),
        ('12О456',          '120456',   'Буква О → 0'),
        ('l23456',          '123456',   'Буква l → 1'),

        # Некорректные — должны вернуть None
        ('',    None, 'Пустая строка'),
        (None,  None, 'None значение'),
    ]

    all_passed = True
    for input_val, expected, description in test_cases:
        data = {"receipt_number": input_val}
        result = postprocess_data(data)
        actual = result.get("receipt_number")
        ok = actual == expected
        if not ok:
            all_passed = False
        status = "✅ OK" if ok else "❌ ОШИБКА"
        print(f"{status} | {description}")
        print(f"       Вход: '{input_val}' → Ожидалось: '{expected}' → Получено: '{actual}'")

    return all_passed


if __name__ == "__main__":
    ok1 = test_organization_parsing()
    ok2 = test_receipt_number_parsing()
    print("\n" + "=" * 50)
    if ok1 and ok2:
        print("✅ Все тесты прошли успешно")
    else:
        print("⚠️  Некоторые тесты не прошли — нужна доработка")