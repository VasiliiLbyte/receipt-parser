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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_EXTRACT_MODEL = os.getenv("OPENROUTER_EXTRACT_MODEL", "google/gemini-2.0-flash-001")
OPENROUTER_VERIFY_MODEL = os.getenv("OPENROUTER_VERIFY_MODEL", "google/gemini-2.5-flash-preview")

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

# Минимальная видимость чека (0.0-1.0) — чеки, перекрытые более чем на (1 - ratio), будут отклонены
MIN_RECEIPT_VISIBLE_RATIO = float(os.getenv("MIN_RECEIPT_VISIBLE_RATIO", "0.70"))

# === ВАЛИДАЦИЯ КОНФИГУРАЦИИ ===
def validate_config():
    """Проверяет обязательные настройки"""
    import warnings

    errors = []

    if not OPENROUTER_API_KEY:
        errors.append("Не настроен OPENROUTER_API_KEY. Добавьте его в файл .env")

    if not OPENAI_API_KEY or OPENAI_API_KEY == "sk-your-openai-api-key-here":
        warnings.warn(
            "OPENAI_API_KEY не задан — прямой OpenAI API недоступен "
            "(не требуется, если используется OpenRouter)",
            stacklevel=2,
        )
    
    if MAX_FILE_SIZE_MB > 20:
        errors.append(f"MAX_FILE_SIZE_MB ({MAX_FILE_SIZE_MB}) превышает лимит API (20 МБ)")
    
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