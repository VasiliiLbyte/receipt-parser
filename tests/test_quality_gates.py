"""Юнит-тесты quality gates, should_run_fallback, choose_best_result (без сети)."""

from dataclasses import replace

from src.pipeline.quality_gates import (
    PassData,
    choose_best_result,
    evaluate_quality,
    is_degraded,
    should_run_fallback,
)


def _good_flat():
    return {
        "organization": "ООО Ромашка",
        "inn": "781603445844",
        "date": "2026-02-19",
        "receipt_number": "42",
        "total": 201.0,
        "total_vat": 33.5,
        "items": [
            {
                "name": "Товар А",
                "price_per_unit": 100.5,
                "quantity": 2.0,
                "total_price": 201.0,
                "vat_rate": "20%",
                "vat_amount": 33.5,
            }
        ],
    }


def test_evaluate_quality_good_passes_gates():
    flat = _good_flat()
    q = evaluate_quality(flat, schema_valid=True)
    assert q.passed_quality_gates()
    assert q.score >= 55
    assert not q.ocr_junk_detected


def test_should_run_fallback_primary_ok_no_fallback():
    q = evaluate_quality(_good_flat(), schema_valid=True)
    run, reason = should_run_fallback(
        primary_extract_ok=True,
        schema_valid=True,
        quality_report=q,
        enable_fallback=True,
        enable_quality_gates=True,
        has_openai_key=True,
    )
    assert not run
    assert "достаточен" in reason


def test_should_run_fallback_schema_invalid():
    q = evaluate_quality({}, schema_valid=False, schema_error="x")
    run, _ = should_run_fallback(
        primary_extract_ok=True,
        schema_valid=False,
        quality_report=q,
        enable_fallback=True,
        enable_quality_gates=True,
        has_openai_key=True,
    )
    assert run


def test_should_run_fallback_quality_gate_items_total_mismatch():
    flat = _good_flat()
    flat["total"] = 999.0
    q = evaluate_quality(flat, schema_valid=True)
    assert not q.items_total_matches
    assert not q.passed_quality_gates()
    run, reason = should_run_fallback(
        primary_extract_ok=True,
        schema_valid=True,
        quality_report=q,
        enable_fallback=True,
        enable_quality_gates=True,
        has_openai_key=True,
    )
    assert run
    assert "quality gates" in reason


def test_should_run_fallback_disabled():
    q = evaluate_quality({}, schema_valid=False)
    run, _ = should_run_fallback(
        primary_extract_ok=False,
        schema_valid=False,
        quality_report=q,
        enable_fallback=False,
        enable_quality_gates=True,
        has_openai_key=True,
    )
    assert not run


def test_should_run_fallback_gates_off_schema_ok():
    q = evaluate_quality({}, schema_valid=False)
    run, _ = should_run_fallback(
        primary_extract_ok=True,
        schema_valid=True,
        quality_report=q,
        enable_fallback=True,
        enable_quality_gates=False,
        has_openai_key=True,
    )
    assert not run


def _pass(label, flat, schema_valid, score_override=None):
    q = evaluate_quality(flat, schema_valid=schema_valid)
    if score_override is not None:
        q = replace(q, score=score_override)
    return PassData(
        label=label,
        provider="x",
        model="m",
        raw={},
        flat=flat,
        validation_warnings=[],
        schema_valid=schema_valid,
        schema_error=None if schema_valid else "err",
        quality=q,
    )


def test_choose_best_fallback_wins_on_schema():
    primary = _pass("primary", {}, schema_valid=False)
    fallback = _pass("fallback", _good_flat(), schema_valid=True)
    chosen, reason = choose_best_result(primary, fallback)
    assert chosen.label == "fallback"
    assert "схеме" in reason


def test_choose_best_primary_wins_on_schema():
    primary = _pass("primary", _good_flat(), schema_valid=True)
    fallback = _pass("fallback", {}, schema_valid=False)
    chosen, _ = choose_best_result(primary, fallback)
    assert chosen.label == "primary"


def test_choose_best_tie_prefers_primary():
    primary = _pass("primary", _good_flat(), schema_valid=True, score_override=70)
    fallback = _pass("fallback", _good_flat(), schema_valid=True, score_override=72)
    chosen, reason = choose_best_result(primary, fallback, tie_prefer_primary=True)
    assert chosen.label == "primary"
    assert "несущественная" in reason


def test_choose_best_fallback_higher_score():
    primary = _pass("primary", _good_flat(), schema_valid=True, score_override=40)
    fallback = _pass("fallback", _good_flat(), schema_valid=True, score_override=95)
    chosen, _ = choose_best_result(primary, fallback)
    assert chosen.label == "fallback"


def test_choose_best_no_fallback_returns_primary():
    primary = _pass("primary", _good_flat(), schema_valid=True)
    chosen, _ = choose_best_result(primary, None)
    assert chosen.label == "primary"


def test_both_bad_still_pick_one_degraded():
    primary = _pass("primary", {}, schema_valid=False, score_override=5)
    fallback = _pass("fallback", {"items": []}, schema_valid=False, score_override=8)
    chosen, _ = choose_best_result(primary, fallback)
    assert is_degraded(chosen)
