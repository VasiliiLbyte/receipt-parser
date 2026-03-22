#!/usr/bin/env python3
"""Тестирование извлечения НДС с чека (не расчета)"""

from pathlib import Path


def test_vat_prompt_changes():
    """Проверка актуального vision-промпта (receipt_vision_prompt) на запрет расчёта налога и GST/VAT."""
    from src.providers.receipt_vision_prompt import RECEIPT_VISION_PROMPT

    prompt = RECEIPT_VISION_PROMPT
    print("🧪 Проверка промпта извлечения налога (НДС/VAT/GST)")
    print("=" * 50)

    critical_phrases = [
        ("НЕ РАССЧИТЫВАЙ НАЛОГ САМОСТОЯТЕЛЬНО", "запрет расчёта налога"),
        ("GST", "поддержка GST"),
        ("total_vat", "поле total_vat"),
        ("Не распределяй", "запрет распределения по строкам"),
    ]
    all_present = True
    for phrase, description in critical_phrases:
        if phrase in prompt:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ нет: {description}")
            all_present = False

    assert '"vat_amount": null' in prompt
    assert all_present

def test_vat_logic():
    """Тестирование логики обработки НДС"""
    print("\n🧪 Тестирование логики обработки НДС")
    print("=" * 50)
    
    # Имитируем данные с разными сценариями НДС
    test_cases = [
        {
            "name": "НДС указан в чеке",
            "input": {"vat_amount": "19.83"},
            "expected": 19.83,
            "description": "Сумма НДС явно указана в чеке"
        },
        {
            "name": "НДС не указан (null)",
            "input": {"vat_amount": None},
            "expected": None,
            "description": "НДС не указан в чеке"
        },
        {
            "name": "НДС пустая строка",
            "input": {"vat_amount": ""},
            "expected": None,
            "description": "Пустая строка должна стать None"
        },
        {
            "name": "НДС с запятой",
            "input": {"vat_amount": "19,83"},
            "expected": 19.83,
            "description": "НДС с запятой как десятичным разделителем"
        },
    ]
    
    from src.openai_client import postprocess_data
    
    for test in test_cases:
        print(f"\n📊 Тест: {test['name']}")
        print(f"   Описание: {test['description']}")
        print(f"   Вход: {test['input']}")
        
        # Создаем тестовые данные
        data = {
            "items": [{"name": "Товар", "vat_amount": test['input']['vat_amount']}]
        }
        
        result = postprocess_data(data)
        actual = result['items'][0]['vat_amount']
        
        print(f"   Ожидалось: {test['expected']}")
        print(f"   Получено: {actual}")
        
        if actual == test['expected']:
            print("   ✅ OK")
        else:
            print("   ❌ ОШИБКА")
    
    return True

if __name__ == "__main__":
    test_vat_prompt_changes()
    test_vat_logic()