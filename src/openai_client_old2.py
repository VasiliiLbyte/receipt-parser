"""
Thin wrapper over the new pipeline for backward compatibility.

This module provides the same public interface as the old openai_client.py
but uses the new explicit pipeline architecture.
"""

import base64
import re
import copy
from .config import OPENROUTER_API_KEY
from .result_builder import ResultBuilder
from .pipeline.orchestrator import process_receipt_pipeline
from .providers.openai import extract_raw_openai_data, encode_image, extract_json_from_response
from .openrouter_client import verify_item_names


def postprocess_data(data):
    """
    Legacy function kept for backward compatibility.
    In the new architecture, normalization is handled by pipeline.normalize module.
    
    This function is kept to avoid breaking any existing imports.
    """
    # Import here to avoid circular imports
    from .pipeline.normalize import normalize_flat_data
    return normalize_flat_data(data)


def extract_receipt_data_from_image(image_path):
    """
    Main entry point - same signature as the old function.
    
    Uses the new explicit pipeline architecture:
    1. Provider-specific extraction (OpenAI)
    2. Normalization (pipeline.normalize)
    3. Validation (pipeline.validate)
    4. Result building (ResultBuilder)
    
    Returns the same canonical result format.
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


# Export the same public interface as the old module
__all__ = [
    'encode_image',
    'extract_json_from_response',
    'postprocess_data',
    'extract_receipt_data_from_image',
]