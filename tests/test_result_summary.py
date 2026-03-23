from api.services.result_summary import build_receipt_summary


def test_build_receipt_summary_ready(sample_receipt_result):
    summary = build_receipt_summary(sample_receipt_result)

    assert summary["status"] == "ready"
    assert summary["date"] == "2026-03-20"
    assert summary["receipt_number"] == "12345"
    assert summary["seller"] == "ООО Ромашка"
    assert summary["seller_inn"] == "7701234567"
    assert summary["total"] == 1500.50
    assert summary["total_vat"] == 250.08
    assert summary["items_count"] == 1
    assert summary["warnings"] == []


def test_build_receipt_summary_review(sample_receipt_result):
    sample_receipt_result["receipt"]["date"] = None
    sample_receipt_result["merchant"]["organization"] = ""
    sample_receipt_result["totals"]["total"] = None
    sample_receipt_result["items"] = []

    summary = build_receipt_summary(sample_receipt_result)

    assert summary["status"] == "review"
    assert summary["items_count"] == 0


def test_build_receipt_summary_warnings(sample_receipt_result):
    sample_receipt_result["receipt"]["date"] = None
    sample_receipt_result["merchant"]["organization"] = None
    sample_receipt_result["merchant"]["inn"] = None
    sample_receipt_result["items"] = []
    sample_receipt_result["totals"]["total"] = None

    summary = build_receipt_summary(sample_receipt_result)

    assert summary["warnings"] == [
        "Не распознана дата",
        "Не распознан продавец",
        "Не распознан ИНН продавца",
        "Не распознаны товарные позиции",
        "Не распознана итоговая сумма",
    ]
