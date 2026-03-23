from api.app import _safe_remove_file


def test_export_xlsx_success(api_client, sample_receipt_result):
    response = api_client.post("/export/xlsx", json={"results": [sample_receipt_result]})

    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers.get(
        "content-type", ""
    )
    assert "receipt_export_1c.xlsx" in response.headers.get("content-disposition", "")
    assert len(response.content) > 0


def test_export_csv_success(api_client, sample_receipt_result):
    response = api_client.post("/export/csv", json={"results": [sample_receipt_result]})

    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "receipt_export_1c.csv" in response.headers.get("content-disposition", "")
    assert len(response.content) > 0
    body_text = response.content.decode("utf-8-sig")
    assert "Дата документа;Номер документа-основания;Продавец;ИНН продавца" in body_text


def test_export_xlsx_empty_results_validation_error(api_client):
    response = api_client.post("/export/xlsx", json={"results": []})
    assert response.status_code == 422


def test_export_csv_empty_results_validation_error(api_client):
    response = api_client.post("/export/csv", json={"results": []})
    assert response.status_code == 422


def test_export_help_returns_title_steps_notes(api_client):
    response = api_client.get("/export/help")

    assert response.status_code == 200
    payload = response.json()
    assert "title" in payload
    assert "steps" in payload
    assert "notes" in payload
    assert isinstance(payload["steps"], list)
    assert isinstance(payload["notes"], list)


def test_safe_remove_file_deletes_existing_file(tmp_path):
    file_path = tmp_path / "to_delete.xlsx"
    file_path.write_bytes(b"temp")

    assert file_path.exists()
    _safe_remove_file(str(file_path))
    assert not file_path.exists()


def test_safe_remove_file_ignores_missing_file(tmp_path):
    file_path = tmp_path / "missing.xlsx"
    _safe_remove_file(str(file_path))
    assert not file_path.exists()
