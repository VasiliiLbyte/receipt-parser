def test_parse_without_file_returns_validation_error(api_client):
    response = api_client.post("/parse")
    assert response.status_code in (400, 422)


def test_parse_with_file_returns_structured_json(api_client, monkeypatch, sample_receipt_result):
    async def fake_parse_uploaded_file(upload_file, temp_dir):
        return sample_receipt_result

    monkeypatch.setattr("api.app.parse_uploaded_file", fake_parse_uploaded_file)

    files = {"file": ("receipt.jpg", b"fake image bytes", "image/jpeg")}
    response = api_client.post("/parse", files=files)

    assert response.status_code == 200
    payload = response.json()
    for key in ("receipt", "merchant", "totals", "taxes", "items"):
        assert key in payload
    assert "summary" in payload
    assert payload["summary"]["status"] == "ready"
    assert payload["summary"]["items_count"] == 1
    assert payload["receipt"]["receipt_number"] == "12345"
