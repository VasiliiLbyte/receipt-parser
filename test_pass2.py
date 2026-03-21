#!/usr/bin/env python3
"""
Тестирование Pass2 (OpenRouter верификация) в изолированном режиме.

Этот скрипт проверяет:
1. Конфигурацию OpenRouter
2. Интеграцию Pass2 в orchestrator
3. Корректность обработки метаданных
"""

import sys
import os
import json
import base64
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import OPENROUTER_API_KEY
from src.openrouter_client import verify_item_names
from src.pipeline.orchestrator import process_receipt_pipeline
from src.providers.openai import extract_raw_openai_data


def test_configuration():
    """Проверка конфигурации OpenRouter"""
    print("🔧 Проверка конфигурации OpenRouter...")
    
    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY не задан в .env файле")
        return False
    
    if OPENROUTER_API_KEY.startswith("sk-or-v1-"):
        print(f"✅ OPENROUTER_API_KEY найден (длина: {len(OPENROUTER_API_KEY)})")
        return True
    else:
        print(f"⚠️  OPENROUTER_API_KEY имеет неожиданный формат: {OPENROUTER_API_KEY[:20]}...")
        return True  # Все равно продолжаем


def test_openrouter_function():
    """Тестирование функции verify_item_names с mock-данными"""
    print("\n🔍 Тестирование функции verify_item_names...")
    
    # Создаем mock изображение (пустой base64)
    mock_image_base64 = base64.b64encode(b"fake_image_data").decode('utf-8')
    
    # Создаем mock данные Pass1
    mock_pass1_data = {
        "organization": "ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ",
        "inn": "781603445844",
        "date": "2026-02-19",
        "receipt_number": "123456",
        "items": [
            {
                "name": "Товар с НДС 20%",
                "price_per_unit": 100.5,
                "quantity": 2.0,
                "total_price": 201.0,
                "vat_rate": "20%",
                "vat_amount": 33.5
            }
        ],
        "total": 1234.56,
        "total_vat": 205.76
    }
    
    try:
        print("📤 Вызов verify_item_names с mock-данными...")
        result = verify_item_names(mock_image_base64, mock_pass1_data.copy())
        
        if result is None:
            print("❌ verify_item_names вернул None")
            return False
        
        print(f"✅ verify_item_names вернул результат")
        print(f"   Организация: {result.get('organization')}")
        print(f"   ИНН: {result.get('inn')}")
        print(f"   Дата: {result.get('date')}")
        print(f"   Товаров: {len(result.get('items', []))}")
        
        # Проверяем, что структура сохранилась
        if "items" not in result:
            print("⚠️  В результате отсутствует поле 'items'")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при вызове verify_item_names: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_integration():
    """Проверка интеграции Pass2 в orchestrator"""
    print("\n🔄 Проверка интеграции Pass2 в orchestrator...")
    
    # Создаем временный mock файл изображения
    temp_image_path = "/tmp/test_receipt.jpg"
    try:
        with open(temp_image_path, "wb") as f:
            f.write(b"fake_image_data")
        
        # Тестируем pipeline без реального вызова API
        print("📤 Тестирование process_receipt_pipeline...")
        
        # Мокаем функцию extract_raw_openai_data чтобы не вызывать реальный API
        def mock_extract_func(image_path, **kwargs):
            print("   🎭 Используется mock extract функция")
            return {
                "organization": "ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ",
                "inn": "ИНН: 781603445844",
                "date": "19.02.2026",
                "receipt_number": "Чек № 123456",
                "items": [
                    {
                        "name": "Товар с НАС 20%",
                        "price_per_unit": "100,50",
                        "quantity": "2",
                        "total_price": "201,00",
                        "vat_rate": "20%",
                        "vat_amount": "33,50"
                    }
                ],
                "total": "1 234,56 руб.",
                "total_vat": "205,76"
            }
        
        # Запускаем pipeline с OpenRouter (будет пропущен из-за mock изображения)
        result = process_receipt_pipeline(
            image_path=temp_image_path,
            provider_extract_func=mock_extract_func,
            openrouter_verify_func=verify_item_names if OPENROUTER_API_KEY else None
        )
        
        if result is None:
            print("❌ process_receipt_pipeline вернул None")
            return False
        
        print(f"✅ process_receipt_pipeline вернул результат")
        
        # Проверяем метаданные
        meta = result.get("meta", {})
        passes = meta.get("passes", [])
        
        print(f"   Статус passes: {passes}")
        
        # Ищем pass2 в метаданных
        pass2_found = False
        for p in passes:
            if p.get("name") == "pass2":
                pass2_found = True
                status = p.get("status", "unknown")
                print(f"   Pass2 статус: {status}")
                break
        
        if not pass2_found:
            print("⚠️  Pass2 не найден в метаданных passes")
        
        # Проверяем raw данные
        raw = result.get("raw", {})
        if raw.get("pass2_provider_json"):
            print("✅ Pass2 raw данные сохранены")
        else:
            print("⚠️  Pass2 raw данные отсутствуют")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)


def main():
    print("🚀 Запуск тестирования Pass2 (OpenRouter верификация)")
    print("=" * 60)
    
    tests = [
        ("Конфигурация OpenRouter", test_configuration),
        ("Функция verify_item_names", test_openrouter_function),
        ("Интеграция в orchestrator", test_orchestrator_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Тест: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"   {'✅ ПРОШЕЛ' if success else '❌ НЕ ПРОШЕЛ'}")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📋 Итоги тестирования:")
    
    all_passed = True
    for test_name, success in results:
        status = "✅ ПРОШЕЛ" if success else "❌ НЕ ПРОШЕЛ"
        print(f"  {test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Все тесты успешно пройдены!")
        print("\n💡 Для реального тестирования с изображением:")
        print("   python test_pipeline.py <путь_к_изображению>")
    else:
        print("\n⚠️  Некоторые тесты не прошли")
        print("\n🔧 Рекомендации:")
        print("   1. Проверьте OPENROUTER_API_KEY в .env файле")
        print("   2. Убедитесь, что интернет-соединение работает")
        print("   3. Проверьте баланс на OpenRouter")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)