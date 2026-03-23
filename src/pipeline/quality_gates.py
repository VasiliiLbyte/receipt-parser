"""
Оценка качества распознанного чека и решения: fallback / выбор лучшего прохода.

Логика вынесена из оркестратора для юнит-тестов и A/B.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.pipeline.tax_status import raw_suggests_tax_amount_omitted

# Допуск суммы позиций к total (руб. или доля от total)
ITEMS_TOTAL_ABS_TOLERANCE = 1.0
ITEMS_TOTAL_REL_TOLERANCE = 0.02
# Минимум «баллов» quality, чтобы не дергать fallback при включённых гейтах
QUALITY_GATE_MIN_SCORE = 55
# Ниже этого считаем результат деградированным в meta
DEGRADED_QUALITY_THRESHOLD = 40
# Если разница score меньше — предпочитаем primary (стабильность)
TIE_BREAK_SCORE_DELTA = 5


@dataclass
class QualityReport:
    """Итог проверок качества по уже нормализованному flat-словарю."""

    schema_valid: bool
    score: int
    has_organization: bool
    inn_ok: bool
    has_date: bool
    has_receipt_number: bool
    has_items: bool
    items_non_empty_names: bool
    has_total: bool
    items_total_matches: bool
    no_disallowed_negatives: bool
    ocr_junk_detected: bool
    tax_summary_ok: bool = True
    issues: list[str] = field(default_factory=list)

    def passed_quality_gates(self) -> bool:
        """Все обязательные гейты для «хорошего» primary без fallback."""
        return (
            self.schema_valid
            and self.has_organization
            and self.inn_ok
            and self.has_date
            and self.has_receipt_number
            and self.has_items
            and self.items_non_empty_names
            and self.has_total
            and self.items_total_matches
            and self.no_disallowed_negatives
            and not self.ocr_junk_detected
            and self.tax_summary_ok
            and self.score >= QUALITY_GATE_MIN_SCORE
        )

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "score": self.score,
            "has_organization": self.has_organization,
            "inn_ok": self.inn_ok,
            "has_date": self.has_date,
            "has_receipt_number": self.has_receipt_number,
            "has_items": self.has_items,
            "items_non_empty_names": self.items_non_empty_names,
            "has_total": self.has_total,
            "items_total_matches": self.items_total_matches,
            "no_disallowed_negatives": self.no_disallowed_negatives,
            "ocr_junk_detected": self.ocr_junk_detected,
            "tax_summary_ok": self.tax_summary_ok,
            "issues_count": len(self.issues),
        }


@dataclass
class PassData:
    """Результат одного прохода (primary или fallback)."""

    label: str
    provider: str
    model: str
    raw: dict[str, Any] | None
    flat: dict[str, Any]
    validation_warnings: list[str]
    schema_valid: bool
    schema_error: str | None
    quality: QualityReport


_JUNK_PATTERNS = (
    re.compile(r"\?\?\?+"),
    re.compile(r"\[illegible\]", re.I),
    re.compile(r"\bundefined\b", re.I),
    re.compile(r"XXXX+"),
)


def _has_ocr_junk(text: str | None) -> bool:
    if not text or not str(text).strip():
        return False
    s = str(text)
    for pat in _JUNK_PATTERNS:
        if pat.search(s):
            return True
    return False


def _inn_valid(inn: Any) -> bool:
    if inn is None:
        return False
    s = str(inn).strip()
    return len(s) in (10, 12) and s.isdigit()


def _date_ok(d: Any) -> bool:
    if d is None:
        return False
    s = str(d).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return False
    return True


def evaluate_quality(
    flat: dict[str, Any],
    *,
    schema_valid: bool,
    schema_error: str | None = None,
    raw_provider: dict[str, Any] | None = None,
) -> QualityReport:
    """Строит QualityReport и числовой score (0–100).

    Отсутствие КПП и формы оплаты не ухудшает качество. Валюта в нормализации
    по умолчанию RUB — не ошибка.
    """
    issues: list[str] = []
    org = flat.get("organization")
    has_organization = bool(org and str(org).strip())
    if not has_organization:
        issues.append("нет organization")

    inn_raw = flat.get("inn")
    inn_absent = inn_raw is None or (isinstance(inn_raw, str) and not inn_raw.strip())
    inn_ok = inn_absent or _inn_valid(inn_raw)
    if not inn_absent and not _inn_valid(inn_raw):
        issues.append("ИНН не 10/12 цифр")

    has_date = _date_ok(flat.get("date"))
    if not has_date:
        issues.append("нет даты YYYY-MM-DD")

    rn = flat.get("receipt_number")
    has_receipt_number = bool(rn is not None and str(rn).strip())
    if not has_receipt_number:
        issues.append("нет receipt_number")

    items = flat.get("items") or []
    has_items = isinstance(items, list) and len(items) >= 1
    if not has_items:
        issues.append("нет позиций items")

    items_non_empty_names = False
    if has_items:
        items_non_empty_names = all(
            it.get("name") is not None and str(it.get("name", "")).strip() for it in items
        )
        if not items_non_empty_names:
            issues.append("пустое name у позиции")

    total = flat.get("total")
    has_total = total is not None
    if not has_total:
        issues.append("нет total")

    items_total_matches = True
    if has_total and has_items:
        try:
            ssum = sum(float(it.get("total_price") or 0) for it in items)
            t = float(total)
            tol = max(ITEMS_TOTAL_ABS_TOLERANCE, ITEMS_TOTAL_REL_TOLERANCE * max(t, 1.0))
            if abs(ssum - t) > tol:
                items_total_matches = False
                issues.append(f"сумма позиций {ssum:.2f} не близка к total {t:.2f}")
        except (TypeError, ValueError):
            items_total_matches = False
            issues.append("не удалось сверить суммы позиций с total")

    no_disallowed_negatives = True
    if total is not None:
        try:
            if float(total) < 0:
                no_disallowed_negatives = False
                issues.append("отрицательный total")
        except (TypeError, ValueError):
            pass
    tv = flat.get("total_vat")
    if tv is not None:
        try:
            if float(tv) < 0:
                no_disallowed_negatives = False
                issues.append("отрицательный total_vat")
        except (TypeError, ValueError):
            pass
    for i, it in enumerate(items or []):
        for key in ("price_per_unit", "quantity", "total_price"):
            v = it.get(key)
            if v is not None:
                try:
                    if float(v) < 0:
                        no_disallowed_negatives = False
                        issues.append(f"отрицательное {key} в позиции {i + 1}")
                except (TypeError, ValueError):
                    pass

    ocr_junk = False
    if _has_ocr_junk(org):
        ocr_junk = True
        issues.append("мусор/OCR-маркеры в organization")
    for it in items or []:
        if _has_ocr_junk(it.get("name")):
            ocr_junk = True
            issues.append("мусор/OCR в названии товара")
            break

    if not schema_valid and schema_error:
        issues.append(f"schema: {schema_error[:120]}")

    tax_summary_ok = not raw_suggests_tax_amount_omitted(flat, raw_provider)
    if not tax_summary_ok:
        issues.append("в сыром JSON есть итоговый налог (VAT/GST/НДС+сумма), а total_vat пуст — возможен пропуск")

    # Score: веса по важности
    w = 0
    if schema_valid:
        w += 25
    if has_organization:
        w += 10
    if inn_absent:
        w += 5
    elif _inn_valid(inn_raw):
        w += 10
    if has_date:
        w += 10
    if has_receipt_number:
        w += 8
    if has_items:
        w += 12
    if items_non_empty_names:
        w += 8
    if has_total:
        w += 7
    if items_total_matches:
        w += 5
    if no_disallowed_negatives:
        w += 3
    if not ocr_junk:
        w += 2
    score = min(100, w)

    return QualityReport(
        schema_valid=schema_valid,
        score=score,
        has_organization=has_organization,
        inn_ok=inn_ok,
        has_date=has_date,
        has_receipt_number=has_receipt_number,
        has_items=has_items,
        items_non_empty_names=items_non_empty_names,
        has_total=has_total,
        items_total_matches=items_total_matches,
        no_disallowed_negatives=no_disallowed_negatives,
        ocr_junk_detected=ocr_junk,
        tax_summary_ok=tax_summary_ok,
        issues=issues,
    )


def should_run_fallback(
    *,
    primary_extract_ok: bool,
    schema_valid: bool,
    quality_report: QualityReport,
    enable_fallback: bool,
    enable_quality_gates: bool,
    has_openai_key: bool,
) -> tuple[bool, str]:
    """
    Нужен ли fallback OpenAI.

    Returns:
        (да/нет, короткая причина для логов)
    """
    if not enable_fallback:
        return False, "fallback отключён (ENABLE_FALLBACK=false)"
    if not has_openai_key:
        return False, "нет OPENAI_API_KEY для fallback"

    if not primary_extract_ok:
        return True, "primary extraction вернул пусто/ошибку"

    if not schema_valid:
        return True, "primary не прошёл Pydantic schema"

    if enable_quality_gates and not quality_report.passed_quality_gates():
        return True, f"primary не прошёл quality gates (score={quality_report.score})"

    return False, "primary достаточен"


def _count_filled_critical(flat: dict[str, Any]) -> int:
    n = 0
    if flat.get("organization"):
        n += 1
    ir = flat.get("inn")
    if ir is not None and str(ir).strip() and _inn_valid(ir):
        n += 1
    if _date_ok(flat.get("date")):
        n += 1
    if flat.get("receipt_number"):
        n += 1
    items = flat.get("items") or []
    if items:
        n += 1
    if flat.get("total") is not None:
        n += 1
    return n


def choose_best_result(
    primary: PassData,
    fallback: PassData | None,
    *,
    tie_prefer_primary: bool = True,
) -> tuple[PassData, str]:
    """
    Выбирает лучший проход.

    Returns:
        (выбранный PassData, причина выбора для логов)
    """
    if fallback is None or fallback.raw is None:
        return primary, "fallback отсутствует или пустой — primary"

    # Валидная схема важнее
    if primary.schema_valid and not fallback.schema_valid:
        return primary, "только primary валиден по схеме"
    if fallback.schema_valid and not primary.schema_valid:
        return fallback, "только fallback валиден по схеме"

    pf = _count_filled_critical(primary.flat)
    ff = _count_filled_critical(fallback.flat)
    if ff > pf + 1:
        return fallback, "fallback заполнил больше критичных полей"
    if pf > ff + 1:
        return primary, "primary заполнил больше критичных полей"

    ps, fs = primary.quality.score, fallback.quality.score
    if fs > ps + TIE_BREAK_SCORE_DELTA:
        return fallback, f"fallback score выше ({fs} vs {ps})"
    if ps > fs + TIE_BREAK_SCORE_DELTA:
        return primary, f"primary score выше ({ps} vs {fs})"

    if tie_prefer_primary:
        return primary, f"разница score несущественная ({ps} vs {fs}) — primary"
    return fallback, f"разница score несущественная ({ps} vs {fs}) — fallback"


def is_degraded(chosen: PassData) -> bool:
    """Признак деградации для meta.processing_status."""
    return (not chosen.schema_valid) or (chosen.quality.score < DEGRADED_QUALITY_THRESHOLD)
