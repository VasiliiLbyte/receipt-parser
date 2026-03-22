#!/usr/bin/env python3
"""
Тестовый скрипт для проверки нового pipeline.
Сравнивает результаты старой и новой реализации.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.openai_client import extract_receipt_data_from_image as old_extract
from src.openai_client_updated import extract_receipt_data_from_image as new_extract
from src.vision_utils import prepare_image


def test_pipeline(image_path):
    """Сравнивает результаты старой и новой реализации."""
    print(f"🧪 Тестирование pipeline на {image_path}")
    
    try:
        # Подготавливаем изображение
        prepared_path = prepare_image(image_path)
        print(f"✅ Изображение подготовлено: {prepared_path}")
        
        # Старая реализация
        print("\n🔍 Запуск старой реализации...")
        old_result = old_extract(prepared_path)
        
        # Новая реализация
        print("\n🔍 Запуск новой реализации...")
        new_result = new_extract(prepared_path)
        
        # Сравниваем результаты
        print("\n📊 Сравнение результатов:")
        
        if old_result is None and new_result is None:
            print("✅ Обе реализации вернули None")
            return True
        
        if old_result is None or new_result is None:
            print(f"❌ Расхождение: старая={old_result is not None}, новая={new_result is not None}")
            return False
        
        # Сравниваем ключевые поля
        fields_to_compare = [
            ("receipt", "receipt_number"),
            ("receipt", "date"),
            ("merchant", "organization"),
            ("merchant", "inn"),
            ("totals", "total"),
            ("taxes", "total_vat"),
        ]
        
        all_match = True
        for section, field in fields_to_compare:
            old_value = old_result.get(section, {}).get(field)
            new_value = new_result.get(section, {}).get(field)
            
            if old_value != new_value:
                print(f"❌ Расхождение в {section}.{field}: старая='{old_value}', новая='{new_value}'")
                all_match = False
            else:
                print(f"✅ {section}.{field}: '{old_value}'")
        
        # Сравниваем количество товаров
        old_items = old_result.get("items", [])
        new_items = new_result.get("items", [])
        
        if len(old_items) != len(new_items):
            print(f"❌ Расхождение в количестве товаров: старая={len(old_items)}, новая={len(new_items)}")
            all_match = False
        else:
            print(f"✅ Количество товаров: {len(old_items)}")
        
        # Сравниваем метаданные
        old_providers = old_result.get("meta", {}).get("providers_used", [])
        new_providers = new_result.get("meta", {}).get("providers_used", [])
        
        if set(old_providers) != set(new_providers):
            print(f"⚠️  Расхождение в providers_used: старая={old_providers}, новая={new_providers}")
        else:
            print(f"✅ Providers used: {old_providers}")
        
        return all_match
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    if len(sys.argv) < 2:
        print("Использование: python test_pipeline.py <путь_к_изображению>")
        return
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"❌ Файл не найден: {image_path}")
        return
    
    success = test_pipeline(image_path)
    
    if success:
        print("\n🎉 Тест пройден успешно! Новый pipeline работает корректно.")
    else:
        print("\n⚠️  Тест выявил расхождения. Проверьте логи выше.")


if __name__ == "__main__":
    main()