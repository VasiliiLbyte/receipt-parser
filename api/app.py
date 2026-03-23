"""
FastAPI application for receipt-parser.

Endpoints:
    GET  /health       – liveness probe
    POST /parse        – parse a receipt image (multipart upload)
    POST /export/xlsx  – export results to 1C-compatible xlsx
    POST /export/csv   – export results to 1C-compatible csv
"""

import os
import tempfile
import traceback

from fastapi import FastAPI, File, UploadFile, HTTPException
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse, Response

from api.models import ExportRequest, ParseResponse
from api.services.parser_service import parse_uploaded_file
from api.services.export_help import get_1c_export_help
from api.services.result_summary import build_receipt_summary
from api.exporters.excel_1c import build_excel_1c
from api.exporters.csv_1c import build_csv_1c_bytes

app = FastAPI(
    title="Receipt Parser API",
    version="1.0.0",
    description="API для распознавания кассовых чеков и экспорта в 1С-совместимые форматы.",
)


def _safe_remove_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/parse", response_model=ParseResponse)
async def parse_receipt(file: UploadFile = File(...)):
    """Принимает изображение чека и возвращает структурированный JSON."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не передан.")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            result = await parse_uploaded_file(file, tmp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

    result["summary"] = build_receipt_summary(result)
    return result


@app.post("/export/xlsx")
async def export_xlsx(body: ExportRequest):
    """Принимает массив результатов и возвращает xlsx-файл в формате 1С."""
    try:
        fd, out_path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        build_excel_1c(body.results, out_path)

        return FileResponse(
            out_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="receipt_export_1c.xlsx",
            background=BackgroundTask(_safe_remove_file, out_path),
        )
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Ошибка формирования xlsx.")


@app.get("/export/help")
async def export_help():
    """Короткая инструкция по загрузке выгрузки в 1С."""
    return get_1c_export_help()


@app.post("/export/csv")
async def export_csv(body: ExportRequest):
    """Принимает массив результатов и возвращает csv-файл в формате 1С."""
    try:
        csv_bytes = build_csv_1c_bytes(body.results)
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": "attachment; filename=receipt_export_1c.csv"},
        )
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Ошибка формирования csv.")
