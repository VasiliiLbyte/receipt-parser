"""
Explicit receipt processing pipeline orchestrator.

This module orchestrates the processing pipeline:
1. load_image (in vision_utils)
2. extract (provider-specific)
3. normalize (field normalization)
4. validate (business rules validation)
5. pydantic_validate (schema validation via Pydantic)
6. build_result (canonical result building)

Each stage is provider-agnostic where possible.
"""

import copy
import json
from typing import Any, Dict, Optional

from . import normalize
from . import validate
from src.result_builder import ResultBuilder
from src.schemas import validate_receipt_data, receipt_data_to_dict


def process_receipt_pipeline(
    image_path: str,
    provider_extract_func,
    openrouter_verify_func=None,
    **provider_kwargs
) -> Optional[Dict[str, Any]]:
    """
    Явный pipeline обработки чека.
    
    Args:
        image_path: путь к изображению чека
        provider_extract_func: функция извлечения данных от провайдера
        openrouter_verify_func: optional функция верификации через OpenRouter
        **provider_kwargs: дополнительные параметры для провайдера
        
    Returns:
        Канонический результат или None при ошибке
    """
    print(f"🔄 Запуск pipeline для {image_path}")
    
    # Этап 1: Extract (provider-specific)
    print("🔍 Этап 1: Извлечение данных через провайдера...")
    try:
        raw_provider_data = provider_extract_func(image_path, **provider_kwargs)
        if not raw_provider_data:
            print("❌ Не удалось извлечь данные через провайдера")
            return None
        
        # Сохраняем сырые данные для traceability
        raw_pass1 = copy.deepcopy(raw_provider_data)
        print("✅ Данные извлечены успешно")
    except Exception as e:
        print(f"❌ Ошибка на этапе извлечения: {e}")
        return None
    
    # Этап 2: Normalize
    print("🔄 Этап 2: Нормализация полей...")
    try:
        normalized_data = normalize.normalize_flat_data(raw_provider_data)
        print("✅ Поля нормализованы")
    except Exception as e:
        print(f"❌ Ошибка на этапе нормализации: {e}")
        normalized_data = raw_provider_data  # Продолжаем с сырыми данными
    
    # Этап 3: Validate (business rules)
    print("✅ Этап 3: Валидация бизнес-правил...")
    try:
        validated_data, validation_warnings = validate.validate_flat_data(normalized_data)
        
        # Логируем предупреждения
        for warning in validation_warnings:
            print(f"⚠️  {warning}")
        
        print("✅ Валидация завершена")
    except Exception as e:
        print(f"❌ Ошибка на этапе валидации: {e}")
        validated_data = normalized_data
        validation_warnings = []
    
    # Этап 3.5: Pydantic schema validation
    print("🔍 Этап 3.5: Валидация через Pydantic схему...")
    try:
        receipt_model, pydantic_warnings = validate_receipt_data(validated_data)
        validated_data = receipt_data_to_dict(receipt_model)
        validation_warnings.extend(pydantic_warnings)
        print("✅ Pydantic валидация успешна")
    except Exception as e:
        print(f"⚠️  Pydantic валидация не пройдена: {e}")
        validation_warnings.append(f"Pydantic validation error: {e}")
        # Продолжаем с данными до Pydantic валидации
    
    # Optional: Pass 2 через OpenRouter
    pass2_status = "skipped"
    raw_pass2 = None
    if openrouter_verify_func:
        print("🔍 Optional этап: верификация через OpenRouter...")
        try:
            # Для OpenRouter нужен base64 изображения
            import base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            verified_data = openrouter_verify_func(base64_image, validated_data)
            if verified_data and verified_data.get("items"):
                # Проверяем, изменились ли данные (сравниваем с оригиналом)
                original_json = json.dumps(validated_data, sort_keys=True)
                verified_json = json.dumps(verified_data, sort_keys=True)
                
                if original_json != verified_json:
                    validated_data = verified_data
                    pass2_status = "ok"
                    raw_pass2 = copy.deepcopy(verified_data)
                    print("✅ OpenRouter верификация завершена (данные обновлены)")
                else:
                    pass2_status = "skipped"
                    print("✅ OpenRouter верификация завершена (данные не изменились)")
            else:
                print("⚠️  OpenRouter не вернул данные")
        except Exception as e:
            print(f"⚠️  Ошибка OpenRouter верификации: {e}")
            pass2_status = "error"

    # Pass 2 can reintroduce service lines into items.
    # Re-apply sanitization to keep only real items and proper total_vat mapping.
    try:
        sanitized_after_pass2, sanitize_warnings = validate.sanitize_items_and_totals(validated_data)
        validated_data = sanitized_after_pass2
        validation_warnings.extend(sanitize_warnings)
    except Exception as e:
        print(f"⚠️  Ошибка финальной санитизации товаров: {e}")

    # Re-apply date normalization after Pass2 because verifier can overwrite
    # normalized date with a raw OCR variant.
    try:
        if "date" in validated_data:
            validated_data["date"] = normalize.normalize_date(validated_data.get("date"))
    except Exception as e:
        print(f"⚠️  Ошибка финальной нормализации даты после Pass2: {e}")

    # Pass2 may bring back non-normalized vat_rate strings (e.g. "20/120").
    try:
        if isinstance(validated_data.get("items"), list):
            for item in validated_data["items"]:
                if isinstance(item, dict) and item.get("vat_rate") is not None:
                    item["vat_rate"] = normalize.normalize_vat_rate(item.get("vat_rate"))
    except Exception as e:
        print(f"⚠️  Ошибка нормализации ставок НДС после Pass2: {e}")

    # Distribute total_vat to items proportionally if per-item vat is missing.
    try:
        validated_data = normalize.distribute_vat_to_items(validated_data)
    except Exception as e:
        print(f"⚠️  Ошибка распределения НДС по позициям: {e}")

    # Этап 4: Build canonical result
    print("🏗️  Этап 4: Сборка канонического результата...")
    try:
        # Подготавливаем метаданные для ResultBuilder
        providers_used = ["openai"]  # TODO: сделать динамическим
        if pass2_status == "ok":
            providers_used.append("openrouter")
        
        passes = [
            {"name": "pass1", "status": "ok"},
            {"name": "pass2", "status": pass2_status}
        ]
        
        # Преобразуем warnings в формат для ResultBuilder
        warnings_list = [{"message": w, "level": "warning"} for w in validation_warnings]
        
        canonical_result = ResultBuilder.build_from_flat(
            flat=validated_data,
            warnings=warnings_list,
            raw_pass1_provider_json=raw_pass1,
            raw_pass2_provider_json=raw_pass2,
            providers_used=providers_used,
            passes=passes,
        )
        
        print("✅ Канонический результат собран")
        return canonical_result
        
    except Exception as e:
        print(f"❌ Ошибка на этапе сборки результата: {e}")
        return None