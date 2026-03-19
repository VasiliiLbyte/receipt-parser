"""
Быстрый тест receipt-parser
"""
import sys
import os

print("🚀 Быстрый тест receipt-parser")
print("=" * 50)

# 1. Проверка конфигурации
print("1. Проверка конфигурации...")
try:
    from src.config import validate_config, OPENAI_API_KEY
    validate_config()
    print("   ✅ Конфигурация загружена")
    
    if OPENAI_API_KEY and OPENAI_API_KEY != "sk-your-openai-api-key-here":
        print("   ✅ API ключ OpenAI настроен")
    else:
        print("   ⚠️  API ключ OpenAI не настроен (используйте тестовый ключ)")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# 2. Проверка модулей
print("\n2. Проверка модулей...")
modules = [
    ("src.vision_utils", "prepare_image"),
    ("src.openai_client", "extract_receipt_data_from_image"),
    ("src.deepseek_client", "extract_receipt_data"),
    ("main", "main")
]

for module_name, func_name in modules:
    try:
        if module_name == "main":
            import main
        else:
            __import__(module_name)
        print(f"   ✅ {module_name} доступен")
    except ImportError as e:
        print(f"   ❌ {module_name}: {e}")

# 3. Проверка тестовых файлов
print("\n3. Проверка тестовых файлов...")
test_files = [
    "test_receipts/ТестЧек1.jpg",
    "test_receipts/ТестЧек2.jpg", 
    "test_receipts/ТестЧек3.jpg"
]

for file_path in test_files:
    if os.path.exists(file_path):
        size_kb = os.path.getsize(file_path) / 1024
        print(f"   ✅ {file_path} ({size_kb:.1f} KB)")
    else:
        print(f"   ❌ {file_path} не найден")

# 4. Проверка подготовки изображения
print("\n4. Тест подготовки изображения...")
try:
    from src.vision_utils import prepare_image
    test_file = "test_receipts/ТестЧек1.jpg"
    if os.path.exists(test_file):
        result = prepare_image(test_file)
        print(f"   ✅ Изображение готово: {result}")
    else:
        print(f"   ⚠️  Тестовый файл не найден: {test_file}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# 5. Инструкции
print("\n" + "=" * 50)
print("📋 ИНСТРУКЦИИ ПО ТЕСТИРОВАНИЮ:")
print("=" * 50)
print("\n1. Настройка API ключей:")
print("   - Откройте файл .env")
print("   - Замените 'sk-your-openai-api-key-here' на реальный ключ OpenAI")
print("   - (Опционально) настройте DeepSeek API ключ")

print("\n2. Запуск приложения:")
print("   - Для одного файла: python main.py test_receipts/ТестЧек1.jpg")
print("   - Для папки: python main.py test_receipts/")
print("   - Результаты сохранятся в receipts.xlsx")

print("\n3. Тестирование без API ключей:")
print("   - Приложение проверит конфигурацию и файлы")
print("   - Для реальной обработки нужен OpenAI API ключ")

print("\n4. Устранение проблем:")
print("   - Убедитесь, что все зависимости установлены:")
print("     pip install -r requirements.txt")
print("   - Проверьте наличие файла .env")
print("   - Убедитесь, что тестовые изображения существуют")

print("\n5. Дополнительные возможности:")
print("   - Использование DeepSeek API (требуется ключ)")
print("   - Настройка формата вывода в .env")
print("   - Изменение лимитов размера файлов")

print("\n" + "=" * 50)
print("✅ Тест завершен. Проверьте вывод выше на наличие ошибок.")
print("💡 Для реального тестирования настройте API ключи в .env")