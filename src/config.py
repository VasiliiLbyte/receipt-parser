"""
Конфигурационный модуль для загрузки настроек из .env файла
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# === API КЛЮЧИ ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# === НАСТРОЙКИ ПРИЛОЖЕНИЯ ===
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "5"))
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "excel")
OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "receipts.xlsx")

# === РАСШИРЕННЫЕ НАСТРОЙКИ ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SAVE_INTERMEDIATE_FILES = os.getenv("SAVE_INTERMEDIATE_FILES", "false").lower() == "true"
INTERMEDIATE_FILES_PATH = os.getenv("INTERMEDIATE_FILES_PATH", "./temp")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "60"))

# === ВАЛИДАЦИЯ КОНФИГУРАЦИИ ===
def validate_config():
    """Проверяет обязательные настройки"""
    errors = []
    
    if not OPENAI_API_KEY or OPENAI_API_KEY == "sk-your-openai-api-key-here":
        errors.append("Не настроен OpenAI API ключ. Добавьте его в файл .env")
    
    if MAX_FILE_SIZE_MB > 20:
        errors.append(f"MAX_FILE_SIZE_MB ({MAX_FILE_SIZE_MB}) превышает лимит OpenAI (20 МБ)")
    
    if MAX_RETRIES < 1 or MAX_RETRIES > 10:
        errors.append(f"MAX_RETRIES ({MAX_RETRIES}) должен быть между 1 и 10")
    
    if OUTPUT_FORMAT not in ["excel", "csv", "json"]:
        errors.append(f"Неподдерживаемый OUTPUT_FORMAT: {OUTPUT_FORMAT}. Доступные: excel, csv, json")
    
    if errors:
        raise ValueError("\n".join(errors))
    
    return True

# Автоматическая валидация при импорте
try:
    validate_config()
    print("✅ Конфигурация загружена и проверена")
except ValueError as e:
    print(f"⚠️  Внимание: {e}")
    print("💡 Проверьте файл .env или используйте .env.example как шаблон")