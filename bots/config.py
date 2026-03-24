"""
Bot configuration — loads tokens and backend URL from environment / .env file.
"""

import os

from dotenv import load_dotenv

load_dotenv()

TG_TOKEN: str = os.environ.get("TG_TOKEN", "")
MAX_TOKEN: str = os.environ.get("MAX_TOKEN", "")
BACKEND_BASE_URL: str = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
DB_PATH = os.getenv("DB_PATH", "./data/sessions.db")

# Прокси для Telegram API (api.telegram.org заблокирован у многих провайдеров в РФ).
# Примеры:
#   http://user:pass@proxy:8080
#   socks5://user:pass@proxy:1080   (требует pip install aiohttp-socks)
TG_PROXY: str = os.environ.get("TG_PROXY", "")

if not TG_TOKEN:
    raise RuntimeError(
        "Переменная окружения TG_TOKEN не задана.\n"
        "Укажите её в .env или экспортируйте перед запуском:\n"
        "  export TG_TOKEN=123456:ABC-DEF..."
    )
