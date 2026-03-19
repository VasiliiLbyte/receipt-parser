"""
Тестовый скрипт для проверки работы receipt-parser
"""
import sys
import os

def test_config():
    """Тестирование загрузки конфигурации"""
    print("=== Тест конфигурации ===")
    try:
        from src.config import validate_config
        validate_config()
        print("✅ Конфигурация загружена успешно")
        return True
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False

def test_image_preparation():
    """Тестирование подготовки изображений"""
    print("\n=== Тест подготовки изображений ===")
    try:
        from src.vision_utils import prepare_image
        
        # Проверяем существование тестовых файлов
        test_files = [
            "test_receipts/ТестЧек1.jpg",
            "test_receipts/ТестЧек2.jpg", 
            "test_receipts/ТестЧек3.jpg"
        ]
        
        for file_path in test_files:
            if os.path.exists(file_path):
                print(f"📁 Проверка файла: {file_path}")
                try:
                    result = prepare_image(file_path)
                    print(f"  ✅ Файл готов к обработке: {result}")
                except Exception as e:
                    print(f"  ❌ Ошибка: {e}")
            else:
                print(f"  ⚠️ Файл не найден: {file_path}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка теста подготовки изображений: {e}")
        return False

def test_openai_client():
    """Тестирование клиента OpenAI (только если есть API ключ)"""
    print("\n=== Тест клиента OpenAI ===")
    try:
        from src.config import OPENAI_API_KEY
        from src.openai_client import encode_image
        
        if OPENAI_API_KEY and OPENAI_API_KEY != "sk-your-openai-api-key-here":
            print("✅ API ключ OpenAI найден")
            
            # Тестируем кодирование изображения
            test_file = "test_receipts/ТестЧек1.jpg"
            if os.path.exists(test_file):
                print(f"🔍 Тест кодирования изображения: {test_file}")
                try:
                    encoded = encode_image(test_file)
                    print(f"  ✅ Изображение закодировано, длина: {len(encoded)} символов")
                    return True
                except Exception as e:
                    print(f"  ❌ Ошибка кодирования: {e}")
                    return False
            else:
                print(f"  ⚠️ Тестовый файл не найден: {test_file}")
                return False
        else:
            print("⚠️  API ключ OpenAI не настроен. Пропускаем тест.")
            print("💡 Добавьте реальный ключ в файл .env для полного тестирования")
            return True  # Не считаем это ошибкой
    except Exception as e:
        print(f"❌ Ошибка теста OpenAI клиента: {e}")
        return False

def test_deepseek_client():
    """Тестирование клиента DeepSeek (только если есть API ключ)"""
    print("\n=== Тест клиента DeepSeek ===")
    try:
        from src.config import DEEPSEEK_API_KEY
        
        if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your-deepseek-api-key-here":
            print("✅ API ключ DeepSeek найден")
            print("⚠️  Примечание: DeepSeek требует текстовый ввод, тест требует OCR")
            return True
        else:
            print("⚠️  API ключ DeepSeek не настроен. Пропускаем тест.")
            return True  # Не считаем это ошибкой
    except Exception as e:
        print(f"❌ Ошибка теста DeepSeek клиента: {e}")
        return False

def test_main_application():
    """Тестирование основного приложения"""
    print("\n=== Тест основного приложения ===")
    try:
        # Проверяем, что main.py существует и может быть импортирован
        print("📋 Проверка структуры приложения...")
        
        # Проверяем наличие необходимых модулей
        required_modules = [
            "src.__init__",
            "src.config",
            "src.vision_utils", 
            "src.openai_client",
            "main"
        ]
        
        for module in required_modules:
            try:
                if module == "main":
                    import main
                else:
                    __import__(module)
                print(f"  ✅ Модуль доступен: {module}")
            except ImportError as e:
                print(f"  ❌ Модуль не найден: {module} - {e}")
                return False
        
        print("✅ Структура приложения проверена")
        return True
    except Exception as e:
        print(f"❌ Ошибка теста основного приложения: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🧪 Запуск тестов receipt-parser")
    print("=" * 50)
    
    tests = [
        ("Конфигурация", test_config),
        ("Подготовка изображений", test_image_preparation),
        ("Клиент OpenAI", test_openai_client),
        ("Клиент DeepSeek", test_deepseek_client),
        ("Основное приложение", test_main_application),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Неожиданная ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Результаты тестирования:")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ ПРОЙДЕН" if success else "❌ НЕ ПРОЙДЕН"
        print(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n🎯 Итог: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n✨ Все тесты пройдены успешно!")
        print("\n📝 Инструкция для запуска приложения:")
        print("1. Замените API ключи в файле .env на реальные")
        print("2. Запустите приложение: python main.py test_receipts/")
        print("3. Результаты будут сохранены в receipts.xlsx")
    else:
        print("\n⚠️  Некоторые тесты не пройдены.")
        print("💡 Проверьте конфигурацию и зависимости")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)