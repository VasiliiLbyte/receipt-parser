"""
Telegram bot for receipt-parser.

Run:  python -m bots.tg_bot
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Dict, List

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bots.config import TG_TOKEN, TG_PROXY, BACKEND_BASE_URL
from bots.common import (
    BackendError,
    call_export,
    call_parse,
    format_summary,
    get_export_help_text,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/heic"}

router = Router()

user_results: Dict[int, List[dict]] = {}


def _export_keyboard(count: int = 0) -> types.InlineKeyboardMarkup:
    label = f" ({count} {'чек' if count == 1 else 'чека' if 2 <= count <= 4 else 'чеков'})" if count > 0 else ""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=f"📊 Скачать Excel для 1С{label}", callback_data="export_xlsx")],
            [types.InlineKeyboardButton(text=f"📄 Скачать CSV{label}", callback_data="export_csv")],
            [types.InlineKeyboardButton(text="🗑 Очистить и начать заново", callback_data="clear")],
            [types.InlineKeyboardButton(text="❓ Как загрузить в 1С", callback_data="help")],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    greeting = (
        "Привет! Я помогаю переносить кассовые чеки в 1С.\n"
        "Пришлите фото чека — я распознаю данные и подготовлю файл для загрузки.\n"
        "\n"
    )
    await message.answer(greeting + get_export_help_text())


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    """User sent an image as a compressed photo."""
    status_msg = await message.answer("⏳ Обрабатываю чек...")
    photo = message.photo[-1]  # highest resolution

    try:
        file = await bot.get_file(photo.file_id)
        data = io.BytesIO()
        await bot.download_file(file.file_path, data)
        file_bytes = data.getvalue()
    except Exception:
        logger.exception("Failed to download photo from Telegram")
        await status_msg.edit_text("❌ Не удалось загрузить фото из Telegram.")
        return

    await _process_receipt(message, status_msg, file_bytes, "photo.jpg")


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    """User sent an uncompressed image as a document attachment."""
    doc = message.document
    mime = (doc.mime_type or "").lower()
    if mime not in ALLOWED_MIME_TYPES:
        await message.answer("Пожалуйста, отправьте фото чека (JPEG, PNG или HEIC).")
        return

    status_msg = await message.answer("⏳ Обрабатываю чек...")

    try:
        file = await bot.get_file(doc.file_id)
        data = io.BytesIO()
        await bot.download_file(file.file_path, data)
        file_bytes = data.getvalue()
    except Exception:
        logger.exception("Failed to download document from Telegram")
        await status_msg.edit_text("❌ Не удалось загрузить файл из Telegram.")
        return

    await _process_receipt(message, status_msg, file_bytes, doc.file_name or "document.jpg")


async def _process_receipt(
    message: Message,
    status_msg: Message,
    file_bytes: bytes,
    filename: str,
) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]

    try:
        result = await call_parse(file_bytes, filename, BACKEND_BASE_URL)
    except BackendError as exc:
        logger.error("Backend error: %s", exc)
        await status_msg.edit_text("❌ Не удалось распознать чек. Попробуйте ещё раз или пришлите более чёткое фото.")
        return
    except Exception:
        logger.exception("Unexpected error calling backend")
        await status_msg.edit_text("❌ Не удалось распознать чек. Попробуйте ещё раз или пришлите более чёткое фото.")
        return

    summary = result.get("summary", {})
    text = format_summary(summary)

    new_result = result.get("results") or [result]
    user_results.setdefault(user_id, [])
    user_results[user_id].extend(new_result)

    count = len(user_results[user_id])
    counter_text = f"\n\n📋 Чек {count} добавлен. Всего в списке: {count} {'чек' if count == 1 else 'чека' if 2 <= count <= 4 else 'чеков'}."
    await status_msg.edit_text(text + counter_text, reply_markup=_export_keyboard(count))


@router.callback_query(F.data == "export_xlsx")
async def cb_export_xlsx(callback: CallbackQuery) -> None:
    await _handle_export(callback, "xlsx", "receipt_export_1c.xlsx")


@router.callback_query(F.data == "export_csv")
async def cb_export_csv(callback: CallbackQuery) -> None:
    await _handle_export(callback, "csv", "receipt_export_1c.csv")


async def _handle_export(callback: CallbackQuery, fmt: str, filename: str) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    results = user_results.get(user_id)
    if not results:
        await callback.message.answer("Сначала отправьте фото чека.")  # type: ignore[union-attr]
        return

    try:
        file_bytes = await call_export(results, fmt, BACKEND_BASE_URL)
    except BackendError as exc:
        logger.error("Export error: %s", exc)
        await callback.message.answer("❌ Ошибка при формировании файла. Попробуйте ещё раз.")  # type: ignore[union-attr]
        return
    except Exception:
        logger.exception("Unexpected export error")
        await callback.message.answer("❌ Ошибка при формировании файла. Попробуйте ещё раз.")  # type: ignore[union-attr]
        return

    doc = BufferedInputFile(file_bytes, filename=filename)
    await callback.message.answer_document(doc)  # type: ignore[union-attr]


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(get_export_help_text())  # type: ignore[union-attr]


@router.callback_query(F.data == "clear")
async def cb_clear(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    user_results[user_id] = []
    await callback.message.answer("🗑 Список чеков очищен. Отправьте новое фото.")


@router.message()
async def fallback(message: Message) -> None:
    """Any text or unsupported content."""
    await message.answer("Пожалуйста, отправьте фото чека.")


async def main() -> None:
    session = AiohttpSession(proxy=TG_PROXY) if TG_PROXY else None
    bot = Bot(token=TG_TOKEN, session=session)
    dp = Dispatcher()
    dp.include_router(router)
    if TG_PROXY:
        logger.info("Using proxy: %s", TG_PROXY.split("@")[-1])
    logger.info("Telegram bot started (long polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
