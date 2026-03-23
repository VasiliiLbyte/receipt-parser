# Memory Bank - Receipt Parser Project

## Обзор проекта (актуально на 23.03.2026)
Проект для парсинга кассовых чеков с двухэтапным извлечением через OpenRouter:
- Pass 1: первичное извлечение данных из изображения (`src/providers/openrouter.py`)
- Pass 2: верификация/уточнение (`src/openrouter_client.py`)

Модели для обоих этапов берутся из `.env` (`OPENROUTER_MODEL`, `OPENROUTER_VERIFY_MODEL`).
Прямой OpenAI и DeepSeek присутствуют в кодовой базе как совместимость/наследие, но не являются основным рабочим провайдером.

## Структура проекта

### Основные директории
- `api/` — FastAPI backend (эндпоинты парсинга и экспорта)
- `bots/` — боты (в т.ч. Telegram-бот)
- `src/pipeline/` — основной pipeline: extract -> normalize -> validate -> result build

### Ключевые файлы
- `api/app.py` — HTTP API (`/parse`, `/export/xlsx`, `/export/csv`)
- `api/services/parser_service.py` — связка API с pipeline
- `src/pipeline/orchestrator.py` — оркестрация этапов, включая optional Pass 2
- `src/providers/openrouter.py` — Pass 1 (извлечение через OpenRouter)
- `src/openrouter_client.py` — Pass 2 (верификация через OpenRouter)
- `bots/tg_bot.py` — Telegram-бот

## Что сейчас работает
- `POST /parse` — загрузка изображения и разбор чека
- `POST /export/xlsx` — экспорт результатов в xlsx (1C-friendly)
- `POST /export/csv` — экспорт результатов в csv (1C-friendly)
- Telegram-бот (`bots/tg_bot.py`) с отправкой фото/документов и получением результата парсинга

## Конфигурация моделей и ключей
Основной runtime использует OpenRouter:
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (Pass 1)
- `OPENROUTER_VERIFY_MODEL` (Pass 2)

Дополнительные переменные (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`) не являются обязательными для основного потока.

## Текущие правила и ограничения домена
- НДС не вычисляется "из головы", только считывается с чека
- Дата после нормализации: `YYYY-MM-DD` или `None`
- ИНН в финальных данных: только цифры, длина 10 или 12 (либо пусто)
- Названия товаров копируются максимально дословно

## Известные проблемы
- Накопление чеков в боте: `user_results` может перезаписываться, из-за чего история/набор результатов пользователя ведет себя некорректно (теряются ранее добавленные чеки).

## Обновления за 23.03.2026 (сегодня)
- Проведен полный аудит batch-экспорта по 23 чекам (`r01-r24`, кроме исключенного `r05`).
- В `src/pipeline/orchestrator.py` добавлена повторная нормализация `date` после Pass 2, чтобы верификация не возвращала "сырую" OCR-дату поверх нормализованной.
- В `src/pipeline/normalize.py` улучшено распределение НДС:
  - при смешанных ставках НДС распределение `total_vat` выполняется только по позициям, явно облагаемым НДС;
  - позиции с `без НДС`/`0%` не получают искусственный `vat_amount`.
- В `src/pipeline/normalize.py` добавена очистка хвостов НДС в наименовании товара (например: `НАС20%`, `НДС 20%`, `НДС20/120`) с сохранением ставки в `vat_rate`.
- В `src/pipeline/normalize.py` добавлен OCR-fix для названия организации: `САЭК-ГЛОБАЛ` -> `СДЭК-ГЛОБАЛ`.

## Тестовое покрытие (добавлено сегодня)
- `tests/test_orchestrator_pass2_sanitize.py`
  - `test_pass2_date_is_renormalized_after_verify`
- `tests/test_service_lines_filtering.py`
  - `test_distribute_vat_skips_explicit_without_vat_items`
- `tests/test_normalize_rules.py`
  - `test_normalize_organization_fixes_saek_to_sdek_global`
  - `test_normalize_item_name_strips_trailing_vat_marker`

## Проверка
- Локальный запуск: `pytest tests/test_normalize_rules.py tests/test_service_lines_filtering.py tests/test_orchestrator_pass2_sanitize.py -q`
- Результат: `28 passed`