"""
Pipeline modules for receipt processing.

This package contains the explicit processing pipeline:
1. load_image (in vision_utils)
2. extract (provider-specific)
3. normalize (field normalization)
4. validate (business rules validation)
5. build_result (canonical result building)
6. export (output formatting)

Each stage should be provider-agnostic where possible.
"""

from . import normalize
from . import validate
from .orchestrator import process_receipt_pipeline

__all__ = [
    "normalize",
    "validate",
    "process_receipt_pipeline",
]