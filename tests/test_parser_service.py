import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile

from api.services import parser_service


@pytest.mark.unit
def test_parse_uploaded_file_saves_file_and_returns_result(tmp_path, monkeypatch, sample_receipt_result):
    captured = {}

    def fake_process_receipt(path):
        captured["path"] = path
        return sample_receipt_result

    monkeypatch.setattr(parser_service, "process_receipt", fake_process_receipt)

    upload = UploadFile(filename="receipt.jpg", file=BytesIO(b"image-bytes"))
    result = asyncio.run(parser_service.parse_uploaded_file(upload, str(tmp_path)))

    saved_path = tmp_path / "receipt.jpg"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"image-bytes"
    assert captured["path"] == str(saved_path)
    assert result["receipt"]["receipt_number"] == "12345"


@pytest.mark.unit
def test_parse_uploaded_file_raises_when_process_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(parser_service, "process_receipt", lambda _: None)
    upload = UploadFile(filename="receipt.jpg", file=BytesIO(b"img"))

    with pytest.raises(ValueError, match="Не удалось распарсить чек"):
        asyncio.run(parser_service.parse_uploaded_file(upload, str(tmp_path)))


@pytest.mark.unit
def test_parse_uploaded_file_propagates_process_exception(tmp_path, monkeypatch):
    def boom(_):
        raise RuntimeError("process error")

    monkeypatch.setattr(parser_service, "process_receipt", boom)
    upload = UploadFile(filename="receipt.jpg", file=BytesIO(b"img"))

    with pytest.raises(RuntimeError, match="process error"):
        asyncio.run(parser_service.parse_uploaded_file(upload, str(tmp_path)))
