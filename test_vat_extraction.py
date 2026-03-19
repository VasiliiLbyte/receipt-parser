#!/usr/bin/env python3
"""Тестирование извлечения НДС с чека (не расчета)"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_vat_prompt_changes():
    """Тестирование изменений в промпте для НДС"""
    print("🧪 Тестирование извлечения НДС с чека")
    print("=" * 50)
    
    # Читаем обновленный промпт
    with open('src/openai_client.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем промпт
    import re
    prompt_match = re.search(r'prompt = """(.*?)"""', content, re.DOTALL)
    
    if prompt_match:
        prompt = prompt_match.group(1)
        
        print("📋 Проверка ключевых изменений в промпте:")
        
        # Проверяем наличие критически важных фраз
        critical_phrases = [
            ("НЕ РАССЧИТЫВАЙ НДС САМОСТОЯТЕЛЬНО!", "✅ Явный запрет расчета НДС"),
            ("Считывай сумму НДС", "✅ Указание считывать НДС с чека"),
            ("Если в чеке сумма НДС не указана", "✅ Указание ставить null при отсутствии"),
            ("НЕ пытайся рассчитать НДС", "✅ Повторный запрет расчета"),
            ("Только считывай то, что написано в чеке", "✅ Финальное подтверждение"),
        ]
        
        all_present = True
        for phrase, description in critical_phrases:
            if phrase in prompt:
                print(f"  {description}: найдено")
            else:
                print(f"  ❌ {description}: не найдено")
                all_present = False
        
        print("\n📄 Проверка примера в промпте:")
        
        # Проверяем пример
        if '"vat_amount": null' in prompt:
            print("  ✅ В примере vat_amount установлен в null (как должно быть)")
        else:
            print("  ❌ В примере vat_amount не null (возможно, расчетные значения)")
        
        if '// Если в чеке не указана сумма НДС' in prompt:
            print("  ✅ В примере есть комментарий про отсутствие НДС")
        else:
            print("  ⚠️ В примере нет комментария про отсутствие НДС")
        
        if '// Только если эта сумма явно указана в чеке' in prompt:
            print("  ✅ В примере есть комментарий про total_vat")
        else:
            print("  ⚠️ В примере нет комментария про total_vat")
        
        print("\n" + "=" * 50)
        print("📋 Итоги изменений:")
        
        if all_present:
            print("✅ Промпт успешно обновлен:")
            print("   1. Добавлен явный запрет на расчет НДС")
            print("   2. Указание считывать НДС прямо с чека")
            print("   3. Обновлен пример с null значениями")
            print("   4. Добавлены повторные предупреждения")
        else:
            print("❌ Не все необходимые изменения внесены")
        
        return all_present
    else:
        print("❌ Не удалось найти промпт в файле")
        return False

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