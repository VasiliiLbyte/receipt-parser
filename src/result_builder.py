"""
Canonical internal result schema builder.

This module must be provider-agnostic: it only maps already-normalized/validated
flat fields (produced by domain post-processing) into the canonical nested
JSON structure.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.normalize import normalize_currency


CANONICAL_SCHEMA_VERSION = "1.0"


class ResultBuilder:
    """
    Builds the canonical receipt-processing result.

    Input: a provider-agnostic "flat" dict shape currently used across the repo
    (see `src/openai_client.postprocess_data()` and `src/openrouter_client.verify_item_names()`).
    Output: canonical nested JSON shape suitable for JSON serialization and
    export-only mapping (Excel/CSV/console).
    """

    @staticmethod
    def build_from_flat(
        flat: dict[str, Any],
        *,
        warnings: list[dict[str, Any]] | None = None,
        raw_pass1_provider_json: dict[str, Any] | None = None,
        raw_pass2_provider_json: dict[str, Any] | None = None,
        providers_used: list[str] | None = None,
        passes: list[dict[str, Any]] | None = None,
        confidence_fields: dict[str, Any] | None = None,
        processing_status: str | None = None,
        pipeline_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        warnings = warnings or []
        providers_used = providers_used or []
        passes = passes or []
        confidence_fields = confidence_fields or {}

        flat_items = flat.get("items") or []
        items: list[dict[str, Any]] = []
        for item in flat_items:
            # Keep values as-is: postprocess_data already converts to numbers/None.
            items.append(
                {
                    "name": item.get("name"),
                    "price_per_unit": item.get("price_per_unit"),
                    "quantity": item.get("quantity"),
                    "total_price": item.get("total_price"),
                    "vat_rate": item.get("vat_rate"),
                    "vat_amount": item.get("vat_amount"),
                    "unit": item.get("unit"),
                }
            )

        meta: dict[str, Any] = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "processing_status": processing_status or "ok",
            "providers_used": providers_used,
            "passes": passes,
            "confidence": {
                "fields": confidence_fields,
            },
        }
        if pipeline_trace:
            meta["pipeline_trace"] = pipeline_trace

        from src.pipeline.receipt_number_finalize import finalize_receipt_number_with_status

        receipt_num_final, receipt_num_status = finalize_receipt_number_with_status(
            flat.get("receipt_number")
        )
        meta["receipt_number_status"] = receipt_num_status

        ts = flat.get("tax_status")
        if ts not in ("taxable", "tax_exempt", "unknown"):
            ts = "unknown"
        meta["tax_status"] = ts

        canonical = {
            "receipt": {
                "receipt_number": receipt_num_final,
                "date": flat.get("date"),
                "payment_method": flat.get("payment_method"),
                "currency": normalize_currency(flat.get("currency")),
            },
            "merchant": {
                "organization": flat.get("organization"),
                "inn": flat.get("inn"),
                "kpp": flat.get("kpp"),
            },
            "items": items,
            "totals": {
                "total": flat.get("total"),
            },
            "taxes": {
                # No VAT calculation in domain post-processing: keep provider/postprocess value.
                "total_vat": flat.get("total_vat"),
            },
            "meta": meta,
            "warnings": warnings,
            "raw": {
                "pass1_provider_json": raw_pass1_provider_json,
                "pass2_provider_json": raw_pass2_provider_json,
            },
        }

        return canonical

