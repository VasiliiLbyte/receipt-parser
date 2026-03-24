"""
Service layer for receipt parsing via uploaded files.
"""

import os
import shutil
import asyncio
from fastapi import UploadFile

from parser_core import process_receipt
from api.services.webhook_1c import push_to_1c_webhook


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


def _validate_extension(filename: str) -> str:
    """Returns lowered extension or raises ValueError."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Неподдерживаемый формат файла: {ext}. "
            f"Допустимые: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


async def parse_uploaded_file(upload_file: UploadFile, temp_dir: str) -> dict:
    """
    Сохраняет загруженный файл во временный каталог,
    запускает pipeline и возвращает структурированный результат.

    Raises:
        ValueError: формат файла не поддерживается или чек не распарсился.
    """
    filename = upload_file.filename or "upload.jpg"
    _validate_extension(filename)

    dest_path = os.path.join(temp_dir, filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)

    result = process_receipt(dest_path)
    if result is None:
        raise ValueError("Не удалось распарсить чек. Проверьте качество изображения.")

    # Fire-and-forget: webhook does not block parse response.
    asyncio.create_task(push_to_1c_webhook(result))

    return result
