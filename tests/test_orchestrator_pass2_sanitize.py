from src.pipeline.orchestrator import process_receipt_pipeline


def test_pass2_output_is_sanitized_before_result_build(tmp_path):
    image_path = tmp_path / "img.jpg"
    image_path.write_bytes(b"fake")

    def fake_extract(_image_path: str):
        return {
            "organization": 'Акционерное общество "ЛОТТЕ РУС"',
            "inn": "7721791619",
            "date": "05-02-2026",
            "receipt_number": "1112",
            "items": [
                {"name": "Buckwheet tea", "price_per_unit": "1390", "quantity": "1", "total_price": "1390"},
                {"name": "Honey", "price_per_unit": "280", "quantity": "1", "total_price": "280"},
            ],
            "total": "1670",
            "total_vat": None,
        }

    def fake_pass2(_base64_image: str, validated_data: dict):
        # Reintroduce a service-like VAT line without marker in name.
        data = dict(validated_data)
        data["items"] = list(validated_data.get("items") or []) + [
            {"name": "Honey", "quantity": 1, "total_price": 301.15, "vat_amount": None}
        ]
        data["total"] = 1670.0
        data["total_vat"] = 301.15
        return data

    result = process_receipt_pipeline(
        image_path=str(image_path),
        provider_extract_func=fake_extract,
        openrouter_verify_func=fake_pass2,
    )

    assert result is not None
    items = result.get("items") or []
    assert len(items) == 2
    assert [i.get("name") for i in items] == ["Buckwheet tea", "Honey"]
    assert result.get("taxes", {}).get("total_vat") == 301.15
    # VAT should be distributed to items
    assert all(i.get("vat_amount") is not None for i in items)
    total_distributed = sum(i["vat_amount"] for i in items)
    assert abs(total_distributed - 301.15) < 0.01


def test_pipeline_distributes_vat_when_model_provides_total_vat(tmp_path):
    """When model extracts total_vat but no per-item vat, distribution fills items."""
    image_path = tmp_path / "img.jpg"
    image_path.write_bytes(b"fake")

    def fake_extract(_image_path: str):
        return {
            "organization": "Test Org",
            "inn": "7721791619",
            "date": "05-02-2026",
            "receipt_number": "100",
            "items": [
                {"name": "Item A", "price_per_unit": "600", "quantity": "1", "total_price": "600"},
                {"name": "Item B", "price_per_unit": "400", "quantity": "1", "total_price": "400"},
            ],
            "total": "1000",
            "total_vat": "166.67",
        }

    result = process_receipt_pipeline(
        image_path=str(image_path),
        provider_extract_func=fake_extract,
    )

    assert result is not None
    items = result.get("items") or []
    assert len(items) == 2
    assert all(i.get("vat_amount") is not None for i in items)
    total_distributed = sum(i["vat_amount"] for i in items)
    assert abs(total_distributed - 166.67) < 0.01
    assert result.get("taxes", {}).get("total_vat") == 166.67
    assert items[0].get("vat_rate") == "20%"


def test_pass2_vat_rate_20120_is_normalized_to_percent(tmp_path):
    image_path = tmp_path / "img.jpg"
    image_path.write_bytes(b"fake")

    def fake_extract(_image_path: str):
        return {
            "organization": "ООО Тест",
            "inn": "7721791619",
            "date": "15-10-2024",
            "receipt_number": "N176",
            "items": [
                {"name": "Товар A", "price_per_unit": "10", "quantity": "1", "total_price": "10", "vat_rate": "20/120"},
            ],
            "total": "10",
            "total_vat": "1.67",
        }

    def fake_pass2(_base64_image: str, validated_data: dict):
        data = dict(validated_data)
        data["items"] = [
            {"name": "Товар A", "price_per_unit": 10.0, "quantity": 1.0, "total_price": 10.0, "vat_rate": "20/120"}
        ]
        return data

    result = process_receipt_pipeline(
        image_path=str(image_path),
        provider_extract_func=fake_extract,
        openrouter_verify_func=fake_pass2,
    )

    assert result is not None
    items = result.get("items") or []
    assert len(items) == 1
    assert items[0].get("vat_rate") == "20%"


def test_pass2_date_is_renormalized_after_verify(tmp_path):
    image_path = tmp_path / "img.jpg"
    image_path.write_bytes(b"fake")

    def fake_extract(_image_path: str):
        return {
            "organization": "ООО Тест",
            "inn": "7721791619",
            "date": "13.02.26",
            "receipt_number": "1112",
            "items": [
                {"name": "Товар A", "price_per_unit": "100", "quantity": "1", "total_price": "100"},
            ],
            "total": "100",
            "total_vat": None,
        }

    def fake_pass2(_base64_image: str, validated_data: dict):
        data = dict(validated_data)
        # Simulate verifier overwriting date with suspicious OCR variant.
        data["date"] = "26.02.2023"
        return data

    result = process_receipt_pipeline(
        image_path=str(image_path),
        provider_extract_func=fake_extract,
        openrouter_verify_func=fake_pass2,
    )

    assert result is not None
    assert result.get("receipt", {}).get("date") == "2026-02-26"
