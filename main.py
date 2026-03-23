"""
CLI entry point for receipt-parser.

Usage:
    python main.py <path_to_image_or_folder>
"""

import sys
import os
from parser_core import process_receipt, save_to_excel


IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.heic', '.heif')


def collect_image_files(path: str) -> list[str]:
    """Собирает список файлов-изображений из пути (файл или папка)."""
    if os.path.isfile(path):
        return [path]
    return [
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.lower().endswith(IMAGE_EXTENSIONS)
    ]


def print_receipt_summary(results: list[dict]) -> None:
    """Выводит краткую сводку по обработанным чекам в консоль."""
    for i, r in enumerate(results, 1):
        receipt = r.get("receipt", {}) or {}
        merchant = r.get("merchant", {}) or {}
        totals = r.get("totals", {}) or {}
        taxes = r.get("taxes", {}) or {}
        receipt_number = receipt.get("receipt_number", "не указан")

        print(f"\n📄 --- Чек {i} (Номер на чеке: {receipt_number}) ---")
        print(f"Организация: {merchant.get('organization')}")
        print(f"ИНН: {merchant.get('inn')}")
        print(f"Дата: {receipt.get('date')}")
        print(f"Всего: {totals.get('total')} руб.")
        print(f"НДС всего: {taxes.get('total_vat')} руб.")
        print("Товары:")
        for item in r.get("items", []):
            print(f"  {item.get('name', '')}: {item.get('total_price', '')} руб.")


def main():
    if len(sys.argv) < 2:
        print("Использование: python main.py <путь_к_изображению_или_папке>")
        return

    path = sys.argv[1]
    files = collect_image_files(path)

    if not files:
        print(f"❌ Не найдено изображений {IMAGE_EXTENSIONS} по пути: {path}")
        print("💡 Убедитесь, что папка содержит файлы с расширением .jpg, .jpeg, .png, .heic или .heif")
        return

    results = []
    for f in files:
        res = process_receipt(f)
        if res:
            results.append(res)
            print("✅ Чек обработан успешно")
        else:
            print("❌ Не удалось обработать чек")

    if not results:
        print("❌ Нет данных для сохранения.")
        return

    print_receipt_summary(results)
    save_to_excel(results, "receipts.xlsx")


if __name__ == "__main__":
    main()
