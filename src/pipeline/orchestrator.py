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
from .quality_gates import (
    PassData,
    choose_best_result,
    evaluate_quality,
    is_degraded,
    should_run_fallback,
)
from .tax_status import enrich_flat_tax_status
from src.config import (
    ENABLE_FALLBACK,
    ENABLE_QUALITY_GATES,
    FALLBACK_MODEL,
    FALLBACK_PROVIDER,
    OPENROUTER_API_KEY,
    PRIMARY_MODEL,
    PRIMARY_PROVIDER,
    openai_key_configured,
)
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

    enrich_flat_tax_status(validated_data, raw=raw_provider_data)

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

    enrich_flat_tax_status(validated_data, raw=raw_pass1)

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


def _ingest_raw_to_pass(
    raw: Optional[Dict[str, Any]],
    *,
    label: str,
    provider: str,
    model: str,
) -> PassData:
    """Нормализация → бизнес-валидация → Pydantic → quality report."""
    validation_warnings: list[str] = []
    schema_valid = False
    schema_error: Optional[str] = None
    flat: Dict[str, Any] = {}

    if not raw:
        q = evaluate_quality(
            flat, schema_valid=False, schema_error="extraction_empty", raw_provider=None
        )
        return PassData(
            label=label,
            provider=provider,
            model=model,
            raw=None,
            flat=flat,
            validation_warnings=validation_warnings,
            schema_valid=False,
            schema_error="extraction_empty",
            quality=q,
        )

    try:
        normalized = normalize.normalize_flat_data(raw)
    except Exception as e:
        print(f"⚠️  Нормализация ({label}): {e}")
        normalized = raw

    try:
        validated_data, vw = validate.validate_flat_data(normalized)
        validation_warnings.extend(vw)
    except Exception as e:
        print(f"⚠️  Бизнес-валидация ({label}): {e}")
        validated_data = normalized

    enrich_flat_tax_status(validated_data, raw=raw)

    try:
        receipt_model, pydantic_warnings = validate_receipt_data(validated_data)
        flat = receipt_data_to_dict(receipt_model)
        validation_warnings.extend(pydantic_warnings)
        schema_valid = True
        print(f"✅ [{label}] Pydantic OK")
    except Exception as e:
        flat = validated_data
        schema_error = str(e)
        validation_warnings.append(f"Pydantic validation error: {e}")
        print(f"⚠️  [{label}] Pydantic: {e}")

    quality = evaluate_quality(
        flat, schema_valid=schema_valid, schema_error=schema_error, raw_provider=raw
    )
    return PassData(
        label=label,
        provider=provider,
        model=model,
        raw=raw,
        flat=flat,
        validation_warnings=validation_warnings,
        schema_valid=schema_valid,
        schema_error=schema_error,
        quality=quality,
    )


def process_receipt_pipeline_variant_c(image_path: str) -> Optional[Dict[str, Any]]:
    """
    Variant C: primary OpenRouter (Gemini Flash Lite) → quality/schema → optional OpenAI fallback.
    """
    from src.providers.openai import extract_raw_openai_data
    from src.providers.openrouter_extract import extract_raw_openrouter_data
    from src.openrouter_client import verify_item_names

    print(f"🔄 Pipeline variant=C, primary={PRIMARY_PROVIDER}/{PRIMARY_MODEL}")

    # --- Primary extraction ---
    primary_raw: Optional[Dict[str, Any]] = None
    if PRIMARY_PROVIDER == "openrouter":
        primary_raw = extract_raw_openrouter_data(image_path, model=PRIMARY_MODEL)
    elif PRIMARY_PROVIDER == "openai":
        primary_raw = extract_raw_openai_data(image_path, model=PRIMARY_MODEL)
    else:
        print(f"❌ Неизвестный PRIMARY_PROVIDER={PRIMARY_PROVIDER}")
        return None

    primary_pass = _ingest_raw_to_pass(
        primary_raw,
        label="primary",
        provider=PRIMARY_PROVIDER,
        model=PRIMARY_MODEL,
    )

    run_fb, fb_reason = should_run_fallback(
        primary_extract_ok=primary_raw is not None,
        schema_valid=primary_pass.schema_valid,
        quality_report=primary_pass.quality,
        enable_fallback=ENABLE_FALLBACK,
        enable_quality_gates=ENABLE_QUALITY_GATES,
        has_openai_key=openai_key_configured(),
    )

    fallback_pass: Optional[PassData] = None
    fallback_raw: Optional[Dict[str, Any]] = None

    if run_fb and FALLBACK_PROVIDER == "openai" and openai_key_configured():
        print(f"🔁 Fallback запуск: {fb_reason}")
        fallback_raw = extract_raw_openai_data(image_path, model=FALLBACK_MODEL)
        fallback_pass = _ingest_raw_to_pass(
            fallback_raw,
            label="fallback",
            provider=FALLBACK_PROVIDER,
            model=FALLBACK_MODEL,
        )
    elif run_fb:
        print(f"⚠️  Fallback запрошен ({fb_reason}), но недоступен (ключ/provider)")

    chosen, choice_reason = choose_best_result(primary_pass, fallback_pass, tie_prefer_primary=True)
    degraded = is_degraded(chosen)

    print(
        f"📌 Выбран результат: {chosen.label} ({chosen.provider} / {chosen.model}) — {choice_reason}"
    )
    print(
        f"📊 Quality [{chosen.label}]: score={chosen.quality.score}, "
        f"schema_valid={chosen.schema_valid}, degraded={degraded}"
    )
    if chosen.quality.issues[:3]:
        print(f"📋 Issues (до 3): {chosen.quality.issues[:3]}")

    flat_work = copy.deepcopy(chosen.flat)
    validation_warnings = list(chosen.validation_warnings)

    # Опциональная верификация имён (OpenRouter), как в legacy — один раз на финальный flat
    pass2_status = "skipped"
    raw_verify_out: Optional[Dict[str, Any]] = None
    verify_fn = verify_item_names if (OPENROUTER_API_KEY and str(OPENROUTER_API_KEY).strip()) else None
    if verify_fn:
        print("🔍 Post-merge: верификация названий (OpenRouter)...")
        try:
            import base64

            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
            verified = verify_fn(base64_image, flat_work)
            if verified and verified.get("items"):
                if json.dumps(verified, sort_keys=True) != json.dumps(flat_work, sort_keys=True):
                    flat_work = verified
                    pass2_status = "ok"
                    raw_verify_out = copy.deepcopy(verified)
                    try:
                        receipt_model, pw = validate_receipt_data(flat_work)
                        flat_work = receipt_data_to_dict(receipt_model)
                        validation_warnings.extend(pw)
                    except Exception as e:
                        validation_warnings.append(f"После verify_item_names: {e}")
                else:
                    pass2_status = "skipped"
        except Exception as e:
            print(f"⚠️  verify_item_names: {e}")
            pass2_status = "error"

    # raw.pass2: приоритет JSON верификации имён; иначе сырой fallback OpenAI (для отладки)
    if raw_verify_out is not None:
        raw_pass2_slot = raw_verify_out
    elif fallback_raw is not None:
        raw_pass2_slot = copy.deepcopy(fallback_raw)
    else:
        raw_pass2_slot = None

    providers_used: list[str] = []
    if PRIMARY_PROVIDER == "openrouter":
        providers_used.append("openrouter")
    else:
        providers_used.append("openai")
    if fallback_pass and fallback_pass.raw is not None:
        providers_used.append("openai")
    if pass2_status == "ok":
        providers_used.append("openrouter_verify")
    providers_used = list(dict.fromkeys(providers_used))

    passes = [
        {
            "name": "primary",
            "status": "ok" if primary_raw else "error",
            "provider": PRIMARY_PROVIDER,
            "model": PRIMARY_MODEL,
        },
        {
            "name": "fallback",
            "status": (
                "ok"
                if fallback_pass and fallback_pass.raw is not None
                else ("skipped" if not run_fb else "error")
            ),
            "provider": FALLBACK_PROVIDER if run_fb else None,
            "model": FALLBACK_MODEL if run_fb else None,
            "reason_if_run": fb_reason if run_fb else None,
        },
        {"name": "name_verify", "status": pass2_status},
    ]

    warnings_list = [{"message": w, "level": "warning"} for w in validation_warnings]
    proc_status = "degraded" if degraded else "ok"

    enrich_flat_tax_status(flat_work, raw=chosen.raw)

    pipeline_trace = {
        "variant": "c",
        "fallback_trigger_reason": fb_reason if run_fb else None,
        "fallback_executed": bool(fallback_pass and fallback_pass.raw is not None),
        "chosen_pass": chosen.label,
        "choice_reason": choice_reason,
        "degraded": degraded,
        "quality_primary": primary_pass.quality.to_summary_dict(),
        "quality_fallback": (
            fallback_pass.quality.to_summary_dict()
            if fallback_pass and fallback_pass.raw is not None
            else None
        ),
        "quality_chosen": chosen.quality.to_summary_dict(),
        "raw_pass2_is": "name_verify" if raw_verify_out is not None else ("fallback_openai" if fallback_raw else None),
    }

    try:
        canonical = ResultBuilder.build_from_flat(
            flat=flat_work,
            warnings=warnings_list,
            raw_pass1_provider_json=primary_raw,
            raw_pass2_provider_json=raw_pass2_slot,
            providers_used=providers_used,
            passes=passes,
            processing_status=proc_status,
            pipeline_trace=pipeline_trace,
        )
        print("✅ Канонический результат (variant C) собран")
        return canonical
    except Exception as e:
        print(f"❌ Ошибка сборки результата (variant C): {e}")
        return None