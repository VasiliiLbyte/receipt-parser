from src.pipeline.normalize import normalize_flat_data, distribute_vat_to_items, merge_orphan_items
from src.pipeline.validate import validate_flat_data


def _run_pipeline_like_steps(flat: dict) -> dict:
    normalized = normalize_flat_data(flat)
    validated, _warnings = validate_flat_data(normalized)
    return validated


def test_vat_service_line_is_not_item_and_updates_total_vat():
    data = {
        "organization": 'Акционерное общество "ЛОТТЕ РУС"',
        "inn": "7721791619",
        "date": "05-02-2026",
        "items": [
            {
                "name": "Buckwheet tea Гречишный чай",
                "price_per_unit": "1390.00",
                "quantity": "1",
                "total_price": "1390.00",
                "vat_amount": None,
            },
            {
                "name": "Honey Мед",
                "price_per_unit": "280.00",
                "quantity": "1",
                "total_price": "280.00",
                "vat_amount": None,
            },
            {
                "name": "VAT/вкл.НДС",
                "price_per_unit": None,
                "quantity": None,
                "total_price": "301.15",
                "vat_amount": None,
            },
            {
                "name": "TOTAL/ИТОГО",
                "price_per_unit": None,
                "quantity": None,
                "total_price": "1670.00",
                "vat_amount": None,
            },
        ],
        "total": "1670.00",
        "total_vat": None,
    }

    result = _run_pipeline_like_steps(data)

    assert len(result["items"]) == 2
    assert all("НДС" not in (i.get("name") or "") for i in result["items"])
    assert all("TOTAL" not in (i.get("name") or "").upper() for i in result["items"])
    assert result["total"] == 1670.0
    assert result["total_vat"] == 301.15


def test_multiple_vat_lines_are_summed_into_total_vat():
    data = {
        "items": [
            {"name": "Товар A", "price_per_unit": "100.00", "quantity": "1", "total_price": "100.00"},
            {"name": "НДС 10%", "total_price": "10.00"},
            {"name": "VAT 20%", "total_price": "20.50"},
            {"name": "ИТОГО", "total_price": "130.50"},
        ],
        "total": "130.50",
        "total_vat": None,
    }

    result = _run_pipeline_like_steps(data)

    assert len(result["items"]) == 1
    assert result["items"][0]["name"] == "Товар A"
    assert result["total"] == 130.5
    assert result["total_vat"] == 30.5


def test_misclassified_vat_item_without_marker_is_removed_by_totals_consistency():
    data = {
        "items": [
            {"name": "Buckwheet tea", "quantity": 1, "total_price": 1390.0, "vat_amount": None},
            {"name": "Мед", "quantity": 1, "total_price": 280.0, "vat_amount": None},
            # VAT line was mistranscribed as normal item name.
            {"name": "Honey", "quantity": 1, "total_price": 301.15, "vat_amount": None},
        ],
        "total": 1670.0,
        "total_vat": 301.15,
    }

    result = _run_pipeline_like_steps(data)

    assert len(result["items"]) == 2
    assert [i["name"] for i in result["items"]] == ["Buckwheet tea", "Мед"]
    assert result["total"] == 1670.0
    assert result["total_vat"] == 301.15


def test_heuristic_removal_sets_total_vat_when_missing():
    """When heuristic removes a suspicious item and total_vat is None,
    it should transfer the removed amount to total_vat."""
    data = {
        "items": [
            {"name": "Buckwheet tea", "quantity": 1, "total_price": 1390.0, "vat_amount": None},
            {"name": "Мед", "quantity": 1, "total_price": 280.0, "vat_amount": None},
            {"name": "Honey", "quantity": 1, "total_price": 301.15, "vat_amount": None},
        ],
        "total": 1670.0,
        "total_vat": None,
    }

    result = _run_pipeline_like_steps(data)

    assert len(result["items"]) == 2
    assert result["total_vat"] == 301.15


def test_distribute_vat_to_items_proportional():
    data = {
        "items": [
            {"name": "Tea", "total_price": 1390.0, "vat_amount": None},
            {"name": "Honey", "total_price": 280.0, "vat_amount": None},
        ],
        "total": 1670.0,
        "total_vat": 301.15,
    }

    result = distribute_vat_to_items(data)

    assert result["items"][0]["vat_amount"] is not None
    assert result["items"][1]["vat_amount"] is not None
    total_distributed = sum(i["vat_amount"] for i in result["items"])
    assert abs(total_distributed - 301.15) < 0.01


def test_distribute_vat_infers_rate_20():
    data = {
        "items": [
            {"name": "A", "total_price": 600.0, "vat_amount": None},
            {"name": "B", "total_price": 400.0, "vat_amount": None},
        ],
        "total": 1000.0,
        "total_vat": 166.67,
    }

    result = distribute_vat_to_items(data)

    assert result["items"][0].get("vat_rate") == "20%"
    assert result["items"][1].get("vat_rate") == "20%"


def test_distribute_vat_skips_when_items_already_have_vat():
    data = {
        "items": [
            {"name": "A", "total_price": 600.0, "vat_amount": 100.0},
            {"name": "B", "total_price": 400.0, "vat_amount": None},
        ],
        "total": 1000.0,
        "total_vat": 166.67,
    }

    result = distribute_vat_to_items(data)

    assert result["items"][0]["vat_amount"] == 100.0
    assert result["items"][1]["vat_amount"] is None


def test_distribute_vat_skips_when_no_total_vat():
    data = {
        "items": [
            {"name": "A", "total_price": 600.0, "vat_amount": None},
        ],
        "total": 600.0,
        "total_vat": None,
    }

    result = distribute_vat_to_items(data)

    assert result["items"][0]["vat_amount"] is None


def test_merge_orphan_items_bilingual():
    """Bilingual receipt: translation lines without price merge into previous item."""
    items = [
        {"name": "Buckwheat tea", "price_per_unit": 1390.0, "quantity": 1, "total_price": 1390.0},
        {"name": "Гречишный чай", "price_per_unit": None, "quantity": None, "total_price": None},
        {"name": "Honey", "price_per_unit": 280.0, "quantity": 1, "total_price": 280.0},
        {"name": "Мед", "price_per_unit": None, "quantity": None, "total_price": None},
    ]

    result = merge_orphan_items(items)

    assert len(result) == 2
    assert result[0]["name"] == "Buckwheat tea Гречишный чай"
    assert result[0]["total_price"] == 1390.0
    assert result[1]["name"] == "Honey Мед"
    assert result[1]["total_price"] == 280.0


def test_merge_orphan_items_no_orphans():
    items = [
        {"name": "A", "price_per_unit": 100.0, "quantity": 1, "total_price": 100.0},
        {"name": "B", "price_per_unit": 200.0, "quantity": 1, "total_price": 200.0},
    ]

    result = merge_orphan_items(items)

    assert len(result) == 2


def test_merge_orphan_first_item_no_price_kept():
    """If the very first item has no price, it can't be merged — keep as-is."""
    items = [
        {"name": "Orphan", "price_per_unit": None, "quantity": None, "total_price": None},
        {"name": "Real", "price_per_unit": 100.0, "quantity": 1, "total_price": 100.0},
    ]

    result = merge_orphan_items(items)

    assert len(result) == 2


def test_distribute_vat_infers_rate_22():
    """22% VAT rate (new for 2025-2026 in Russia) should be detected."""
    total = 1000.0
    total_vat = round(total * 22 / 122, 2)
    data = {
        "items": [
            {"name": "A", "total_price": 600.0, "vat_amount": None},
            {"name": "B", "total_price": 400.0, "vat_amount": None},
        ],
        "total": total,
        "total_vat": total_vat,
    }

    result = distribute_vat_to_items(data)

    assert result["items"][0].get("vat_rate") == "22%"
    assert result["items"][1].get("vat_rate") == "22%"


def test_distribute_vat_skips_explicit_without_vat_items():
    data = {
        "items": [
            {"name": "Товар без НДС", "total_price": 426.0, "vat_amount": None, "vat_rate": "без НДС"},
            {"name": "Сервисный сбор", "total_price": 20.0, "vat_amount": None, "vat_rate": "20%"},
        ],
        "total": 446.0,
        "total_vat": 3.33,
    }

    result = distribute_vat_to_items(data)

    assert result["items"][0]["vat_amount"] is None
    assert result["items"][1]["vat_amount"] == 3.33


def test_full_pipeline_bilingual_lotte_receipt():
    """End-to-end: bilingual Lotte receipt with VAT line → 2 items, total_vat filled."""
    data = {
        "organization": 'Акционерное общество "ЛОТТЕ РУС"',
        "date": "05-02-2026",
        "receipt_number": "1112",
        "items": [
            {"name": "Buckwheat tea", "price_per_unit": "1390.00", "quantity": "1", "total_price": "1390.00"},
            {"name": "Гречишный чай", "price_per_unit": None, "quantity": None, "total_price": None},
            {"name": "Honey", "price_per_unit": "280.00", "quantity": "1", "total_price": "280.00"},
            {"name": "Мед", "price_per_unit": None, "quantity": None, "total_price": None},
            {"name": "VAT/вкл.НДС", "price_per_unit": None, "quantity": None, "total_price": "301.15"},
            {"name": "TOTAL/ИТОГО", "price_per_unit": None, "quantity": None, "total_price": "1670.00"},
        ],
        "total": "1670.00",
        "total_vat": None,
    }

    result = _run_pipeline_like_steps(data)

    assert len(result["items"]) == 2
    assert result["items"][0]["name"] == "Buckwheat tea Гречишный чай"
    assert result["items"][0]["total_price"] == 1390.0
    assert result["items"][1]["name"] == "Honey Мед"
    assert result["items"][1]["total_price"] == 280.0
    assert result["total"] == 1670.0
    assert result["total_vat"] == 301.15
