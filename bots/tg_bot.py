"""
Telegram bot for receipt-parser.

Run:  python -m bots.tg_bot
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import List

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bots.config import TG_TOKEN, TG_PROXY, BACKEND_BASE_URL
from bots.common import (
    BackendError,
    call_export,
    call_parse,
    get_export_help_text,
)
from src.storage.session_store import session_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/heic"}

router = Router()

user_controls_message_id: dict[int, int] = {}


def _export_keyboard(count: int = 0) -> types.InlineKeyboardMarkup:
    label = f" ({count})" if count > 0 else ""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=f"📊 Excel для 1С{label}", callback_data="export_xlsx")],
            [types.InlineKeyboardButton(text=f"📄 CSV{label}", callback_data="export_csv")],
            [types.InlineKeyboardButton(text="📋 Показать чеки", callback_data="show_checks")],
            [types.InlineKeyboardButton(text="🗑 Очистить", callback_data="clear")],
        ]
    )


async def _upsert_controls_message(message: Message, user_id: int, count: int) -> None:
    controls_text = "Выберите действие:"
    keyboard = _export_keyboard(count)
    msg_id = user_controls_message_id.get(user_id)
    if msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=controls_text,
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    controls_msg = await message.answer(controls_text, reply_markup=keyboard)
    user_controls_message_id[user_id] = controls_msg.message_id


def _receipt_line(index: int, r: dict) -> str:
    receipt = r.get("receipt", {}) or {}
    merchant = r.get("merchant", {}) or {}
    totals = r.get("totals", {}) or {}
    items = r.get("items", []) or []

    seller = (merchant.get("organization") or "—").strip()
    date = (receipt.get("date") or "—").strip()
    total = totals.get("total")
    total_str = f"{total:.0f}₽" if isinstance(total, (int, float)) else "—"
    items_count = len(items)
    pos_label = "поз." if items_count != 1 else "поз."
    return f"Чек {index} | {seller} | {date} | {total_str} | {items_count} {pos_label}"


def _is_valid_inn(value: str | None) -> bool:
    if not value:
        return False
    inn = re.sub(r"\D+", "", str(value))
    return len(inn) in (10, 12)


def _quality_score(r: dict) -> int:
    receipt = r.get("receipt", {}) or {}
    merchant = r.get("merchant", {}) or {}
    items = r.get("items", []) or []
    totals = r.get("totals", {}) or {}

    score = 0
    if receipt.get("date"):
        score += 2
    if isinstance(totals.get("total"), (int, float)):
        score += 2
    if _is_valid_inn(merchant.get("inn")):
        score += 3

    org = str(merchant.get("organization") or "")
    if re.search(r"[А-Яа-яЁё]", org):
        score += 2
    if org and not re.search(r"\b(ИП КРОТОВ ИГОРЬ АНАТОЛЬЕВИЧ)\b", org, flags=re.IGNORECASE):
        score += 1

    russian_items = 0
    for item in items:
        name = str((item or {}).get("name") or "")
        if re.search(r"[А-Яа-яЁё]", name):
            russian_items += 1
    score += min(russian_items, 5)

    return score


def _dedupe_results_keep_best(results: List[dict]) -> List[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    passthrough: List[dict] = []

    for r in results:
        receipt = r.get("receipt", {}) or {}
        totals = r.get("totals", {}) or {}
        date = receipt.get("date")
        total = totals.get("total")

        if not date or not isinstance(total, (int, float)):
            passthrough.append(r)
            continue

        key = (str(date), f"{float(total):.2f}")
        existing = grouped.get(key)
        if existing is None or _quality_score(r) > _quality_score(existing):
            grouped[key] = r

    return passthrough + list(grouped.values())


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

    # Keep only one final receipt result to avoid pass1/pass2 duplicates in exports.
    final_result = result.get("verified_result")
    if not final_result:
        results_list = result.get("results")
        if isinstance(results_list, list) and results_list:
            final_result = results_list[-1]
        else:
            final_result = result

    await session_store.add_receipt(user_id, final_result)
    receipts = await session_store.get_receipts(user_id)
    count = len(receipts)
    await status_msg.edit_text(f"✅ Чек №{count} добавлен. Пришлите ещё чеки или нажмите «Готово» для экспорта.")
    await _upsert_controls_message(message, user_id, count)


@router.callback_query(F.data == "export_xlsx")
async def cb_export_xlsx(callback: CallbackQuery) -> None:
    await _handle_export(callback, "xlsx", "receipt_export_1c.xlsx")


@router.callback_query(F.data == "export_csv")
async def cb_export_csv(callback: CallbackQuery) -> None:
    await _handle_export(callback, "csv", "receipt_export_1c.csv")


async def _handle_export(callback: CallbackQuery, fmt: str, filename: str) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    results = await session_store.get_receipts(user_id)
    if not results:
        await callback.message.answer("Сначала отправьте фото чека.")  # type: ignore[union-attr]
        return

    deduped_results = _dedupe_results_keep_best(results)
    await session_store.set_receipts(user_id, deduped_results)

    try:
        file_bytes = await call_export(deduped_results, fmt, BACKEND_BASE_URL)
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


@router.callback_query(F.data == "show_checks")
async def cb_show_checks(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    results = await session_store.get_receipts(user_id)
    if not results:
        await callback.message.answer("Список чеков пуст. Сначала отправьте фото чека.")  # type: ignore[union-attr]
        return

    lines = [_receipt_line(i, r) for i, r in enumerate(results, 1)]
    text = "```\n" + "\n".join(lines) + "\n```"
    await callback.message.answer(text, parse_mode="Markdown")  # type: ignore[union-attr]


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(get_export_help_text())  # type: ignore[union-attr]


@router.callback_query(F.data == "clear")
async def cb_clear(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    await session_store.clear_receipts(user_id)
    msg_id = user_controls_message_id.get(user_id)
    if msg_id:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,  # type: ignore[union-attr]
                message_id=msg_id,
                reply_markup=None,
            )
        except Exception:
            pass
        user_controls_message_id.pop(user_id, None)
    await callback.message.answer("🗑 Список чеков очищен. Отправьте новое фото.")


@router.message()
async def fallback(message: Message) -> None:
    """Any text or unsupported content."""
    await message.answer("Пожалуйста, отправьте фото чека.")


async def main() -> None:
    await session_store.init()
    session = AiohttpSession(proxy=TG_PROXY) if TG_PROXY else None
    bot = Bot(token=TG_TOKEN, session=session)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        if TG_PROXY:
            logger.info("Using proxy: %s", TG_PROXY.split("@")[-1])
        logger.info("Telegram bot started (long polling)")
        await dp.start_polling(bot)
    finally:
        await session_store.close()


if __name__ == "__main__":
    asyncio.run(main())
