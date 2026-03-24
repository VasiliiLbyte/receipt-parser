# receipt-parser

Парсер кассовых чеков с FastAPI backend, Telegram-ботом и интеграциями для 1С.

## Что умеет

- Принимает фото чека и извлекает структурированные данные.
- Прогоняет нормализацию и валидацию полей.
- Экспортирует результаты в форматы для 1С (`xlsx`, `csv`, CommerceML `xml`).
- Отдает данные чеков через REST API для 1С.
- Поддерживает push-вебхук в 1С после успешного распознавания.
- Поддерживает файловый обмен с 1С через drop-папку.
- Сохраняет пользовательские сессии в SQLite.

## Интеграции с 1С

### 1) CommerceML / экспорт

- `POST /export/xlsx`
- `POST /export/csv`
- `POST /export/xml` (CommerceML 2.09)

### 2) REST API для HTTP-сервисов 1С

- `GET /api/v1/receipts`
- `GET /api/v1/receipts/{receipt_id}`
- `GET /api/v1/receipts/export/xml`
- `GET /api/v1/receipts/export/xlsx`

Для защиты используется заголовок `X-API-Key` (см. `API_KEY` в `.env`).

### 3) Push-вебхук в 1С

После успешного парсинга backend может отправлять событие `receipt.parsed` на URL 1С.

Переменные:
- `WEBHOOK_1C_URL` — URL вебхука 1С
- `WEBHOOK_1C_SECRET` — секрет в заголовке `X-Secret`

### 4) Файловый обмен

- `GET /exchange/drop?user_id=...&fmt=xml|xlsx|csv`
- `GET /exchange/files`

Файлы сохраняются в директорию `EXCHANGE_DIR` (по умолчанию `./exchange/`).

### 5) Внешняя обработка 1С

Исходники лежат в `integrations/1c/`:
- `ReceiptParserLoader.bsl`
- `README.md` (инструкция по подключению в 1С)
- `settings_template.json`

## Структура проекта

- `api/` — FastAPI API
- `api/routes/v1_receipts.py` — REST API для 1С
- `api/routes/file_exchange.py` — файловый обмен
- `api/services/webhook_1c.py` — push-вебхук
- `integrations/1c/` — внешняя обработка для 1С
- `bots/` — Telegram-бот
- `src/` — ядро pipeline и бизнес-логика
- `tests/` — тесты
- `data/` — SQLite база (`sessions.db`)
- `exchange/` — drop-папка для файлового обмена

## Быстрый старт

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Создать `.env` из шаблона:

```bash
cp .env.example .env
```

3. Заполнить минимум:

- `OPENROUTER_API_KEY`
- `TG_TOKEN` (если нужен бот)
- `BACKEND_BASE_URL` (обычно `http://localhost:8000`)
- `DB_PATH` (по умолчанию `./data/sessions.db`)
- `API_KEY` (для `/api/v1/*`, можно оставить пустым в dev)
- `EXCHANGE_DIR` (по умолчанию `./exchange/`)
- `WEBHOOK_1C_URL` (опционально, для push-интеграции)

## Запуск

### API

```bash
uvicorn api.app:app --reload
```

API будет доступен на `http://127.0.0.1:8000`.

Проверка:

```bash
curl http://127.0.0.1:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Swagger UI: `http://127.0.0.1:8000/docs`

### Telegram-бот

```bash
python -m bots.tg_bot
```

## Тесты

Запустить все тесты:

```bash
pytest -q
```

Запустить только тесты хранилища сессий:

```bash
pytest -q tests/test_session_store.py
```

## Персистентность сессий

Сессии Telegram-бота хранятся в SQLite через `src/storage/session_store.py`.

- Путь к базе задается переменной `DB_PATH`.
- По умолчанию: `./data/sessions.db`.
- После перезапуска бота добавленные чеки не теряются.
