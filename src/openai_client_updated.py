import copy
from .config import OPENROUTER_API_KEY
from .result_builder import ResultBuilder
from .pipeline.orchestrator import process_receipt_pipeline
from .providers.openai import extract_raw_openai_data
from .openrouter_client import verify_item_names


def extract_receipt_data_from_image(image_path):
    """
    Обновленная версия функции, использующая явный pipeline.
    
    Сохраняет обратную совместимость: та же сигнатура, тот же результат.
    """
    # Используем явный pipeline с provider-specific функцией
    openrouter_func = None
    if OPENROUTER_API_KEY:
        openrouter_func = verify_item_names
    
    result = process_receipt_pipeline(
        image_path=image_path,
        provider_extract_func=extract_raw_openai_data,
        openrouter_verify_func=openrouter_func,
        provider_name="openai"
    )
    
    return result