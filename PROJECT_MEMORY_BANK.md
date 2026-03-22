# Memory Bank - Receipt Parser Project

## 📋 Обзор проекта
Проект для парсинга кассовых чеков с использованием OpenAI Vision API и DeepSeek API.

## 🏗️ Структура проекта

### Основные файлы:
- `main.py` — CLI: изображения → `extract_receipt_data_from_image` → Excel
- `src/openai_client.py` — точка входа: `PIPELINE_VARIANT=c` (OpenRouter → fallback OpenAI) или `legacy` (только OpenAI)
- `src/providers/openai.py` — OpenAI Vision, модель из `FALLBACK_MODEL` (или `PRIMARY_MODEL` если primary=openai)
- `src/providers/openrouter_extract.py` — primary Vision через OpenRouter (`PRIMARY_MODEL`)
- `src/providers/receipt_vision_prompt.py` — общий промпт извлечения (одинаковые правила НДС/названий)
- `src/pipeline/orchestrator.py` — `process_receipt_pipeline` (legacy), `process_receipt_pipeline_variant_c` (dual-pass)
- `src/pipeline/quality_gates.py` — оценка качества, `should_run_fallback`, `choose_best_result`
- `src/pipeline/normalize.py`, `src/pipeline/validate.py` — нормализация и бизнес-валидация
- `src/schemas.py` — Pydantic `ReceiptData` / `ReceiptItem` (строгая проверка; при ошибке pipeline продолжает без этого шага)
- `src/result_builder.py` — канонический вложенный JSON для экспорта
- `src/deepseek_client.py` — альтернатива по тексту OCR (без полного pipeline)
- `src/vision_utils.py`, `src/config.py`, `src/ocr_utils.py` — утилиты и конфиг

### Тесты:
- Каталог `tests/`, фикстуры — `tests/conftest.py`, примеры чеков — `tests/test_receipts/`
- Постоянные правила для Cursor: `.cursor/rules/*.mdc`

### Виртуальное окружение (рекомендуется):
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Variant C (по умолчанию, `PIPELINE_VARIANT=c`)

**Цепочка:**
1. **Primary:** OpenRouter Vision, модель по умолчанию `google/gemini-3.1-flash-lite-preview` (`PRIMARY_MODEL`).
2. Нормализация (`normalize`) → бизнес-валидация (`validate`) → Pydantic (`schemas`).
3. **Quality gates** (`quality_gates.evaluate_quality`): organization, дата `YYYY-MM-DD`, номер чека, позиции с непустыми именами, `total`, сходимость суммы позиций с `total`, отсутствие недопустимых отрицательных значений, эвристики OCR-мусора.
4. **`should_run_fallback`:** если извлечение пустое, или Pydantic не прошёл, или (при `ENABLE_QUALITY_GATES=true`) не пройдены гейты — запускается fallback при `ENABLE_FALLBACK=true` и валидном `OPENAI_API_KEY`.
5. **Fallback:** OpenAI Vision, модель `FALLBACK_MODEL` (по умолчанию `gpt-4o`), те же шаги postprocess + schema + quality.
6. **`choose_best_result`:** приоритет — валидная схема; затем число заполненных критичных полей; затем `quality.score`; при близких score предпочтение **primary** (стабильность).
7. Опционально **verify имён** через `openrouter_client.verify_item_names` (если задан `OPENROUTER_API_KEY`).
8. Сборка `ResultBuilder`: `meta.processing_status` = `ok` или `degraded` (слабый результат / невалидная схема); детали — `meta.pipeline_trace` (без ключей).

**Переменные окружения (см. `.env.example`):** `PIPELINE_VARIANT`, `PRIMARY_PROVIDER`, `PRIMARY_MODEL`, `FALLBACK_PROVIDER`, `FALLBACK_MODEL`, `ENABLE_FALLBACK`, `ENABLE_QUALITY_GATES`.

**Legacy:** `PIPELINE_VARIANT=legacy` — один проход OpenAI + опциональный OpenRouter verify, функция `process_receipt_pipeline`.

## 🔧 Основные функции

### 1. `extract_receipt_data_from_image()` (openai_client.py)
Вызовет variant C или legacy в зависимости от `PIPELINE_VARIANT`. Публичный JSON (receipt / merchant / items / …) не менялся; расширены только `meta`.

**Ключевые особенности промпта (общие для OpenAI и OpenRouter):**
- **Точное копирование названий товаров**: без изменений и перефразирования
- **НДС считывается с чека**: явный запрет на самостоятельный расчет
- **Поддержка разных форматов**: дат, чисел, номеров чеков
- **Обработка ошибок OCR**: исправление "НАС" → "НДС" в служебных полях

### 2. `postprocess_data()` (openai_client.py)
Постобработка и нормализация извлеченных данных.

**Что делает:**
- **Обработка даты**: преобразует различные форматы дат в ГГГГ-ММ-ДД
- **Обработка номера чека**: удаляет префиксы ("Чек №", "Receipt #", "Номер чека:")
- **Нормализация чисел**: поддерживает разные форматы:
  - Европейский: "1.234,56" → 1234.56
  - Американский: "1,234.56" → 1234.56
  - Русский: "1 234,56 руб." → 1234.56
- **Валидация ИНН**: оставляет только цифры, проверяет длину (10 или 12)
- **Исправление опечаток**: "НАС" → "НДС" в названиях

### 3. `extract_receipt_data_deepseek()` (deepseek_client.py)
Альтернативная реализация с использованием DeepSeek API.

## 📊 Формат данных

### Входные данные (изображение чека)
- Форматы: JPG, PNG
- Рекомендуемое качество: высокое, читаемый текст

### Выходные данные (JSON)
```json
{
  "organization": "Название организации",
  "inn": "ИНН (10 или 12 цифр)",
  "date": "2025-12-31",
  "receipt_number": "12345",
  "items": [
    {
      "name": "Точное название товара",
      "price_per_unit": 100.50,
      "quantity": 2.0,
      "total_price": 201.0,
      "vat_rate": "20%",
      "vat_amount": 33.5
    }
  ],
  "total": 1234.56,
  "total_vat": 205.76
}
```

## 🚀 Как использовать

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

**Поддержка HEIC:** Требуется дополнительная библиотека:
```bash
pip install pillow-heif
```
(уже включена в requirements.txt)

### 2. Настройка API ключей
Создать файл `.env` на основе `.env.example`:
```
OPENAI_API_KEY=your_openai_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### 3. Запуск парсера
```bash
python main.py путь_к_изображению.jpg
```
**Поддерживаемые форматы:** .jpg, .jpeg, .png, .heic, .heif

### 4. Тестирование
```bash
pytest                        # быстрые тесты (без маркера slow)
pytest -m slow                # интеграция с реальным OpenAI API
```
Таймаут и маркеры заданы в `pytest.ini`.

## 🔍 Особенности обработки

### Номер чека
- Извлекается номер, указанный на самом чеке
- Удаляются префиксы: "Чек №", "Receipt #", "Номер:", "Номер чека:"
- Сохраняются дефисы и буквы: "ABC-123" остается "ABC-123"

### Обработка чисел
- **"1 234,56 руб."** → 1234.56 (русский формат с пробелом как разделителем тысяч)
- **"1.234,56"** → 1234.56 (европейский формат)
- **"1,234.56"** → 1234.56 (американский формат)
- **"invalid"** → None (некорректные значения)

### Обработка дат
- **"2025-12-31"** → "2025-12-31"
- **"31.12.2025"** → "2025-12-31"
- **"31.12.25"** → "2025-12-31"
- **"[31/12/2025]"** → "2025-12-31"
- **"неверная дата"** → None

## 🐛 Известные проблемы (исправлены)

1. **Умножение чисел на 10**: "119.0" → "1190.0" - **ИСПРАВЛЕНО**
   - Причина: логика считала точку с одной цифрой после нее разделителем тысяч
   - Решение: теперь 1-2 цифры после точки/запятой считаются десятичной частью
   
2. **НДС рассчитывается вместо считывания** - **ИСПРАВЛЕНО**
   - Причина: модель OpenAI пыталась рассчитать НДС самостоятельно
   - Решение: добавлен явный запрет в промпт и инструкции считывать НДС с чека
   
3. **Ошибки распознавания дат** - **ИСПРАВЛЕНО**
   - Причина: ограниченное количество поддерживаемых форматов дат
   - Решение: улучшена логика обработки дат с поддержкой:
     - Русских названий месяцев ("31 декабря 2025")
     - OCR ошибок (запятые вместо точек, пробелы вместо точек)
     - Разных форматов разделителей
     - Валидации реалистичных дат (не в будущем)
   
4. **Точка от "руб."**: может мешать обработке чисел
5. **Сложные названия товаров**: требуют точного копирования
6. **Разные форматы чеков**: могут потребовать адаптации промпта

## 📈 Планы улучшений

1. Добавить поддержку большего количества форматов чеков
2. Улучшить обработку товаров с НДС
3. ~~Добавить валидацию данных~~ — базовая Pydantic-валидация в pipeline (`src/schemas.py`)
4. Создать веб-интерфейс
5. Добавить базу данных для хранения результатов

## 🔗 Зависимости
- requests, python-dotenv, pillow, pydantic
- torch / easyocr / opencv — по `requirements.txt` (Vision и локальный OCR при необходимости)

## 📝 Примечания
Проект активно развивается. Текущая версия фокусируется на точности извлечения данных и надежности постобработки.