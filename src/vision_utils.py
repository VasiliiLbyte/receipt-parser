import cv2
import os

MAX_FILE_SIZE_MB = 20  # OpenAI не принимает файлы больше 20 МБ


def prepare_image(image_path):
    """Проверяет изображение перед отправкой в OpenAI"""

    # Проверяем что файл существует
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Файл не найден: {image_path}")

    # Проверяем размер файла
    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"Файл слишком большой: {file_size_mb:.1f} МБ "
            f"(максимум {MAX_FILE_SIZE_MB} МБ). "
            f"Сожмите изображение перед обработкой."
        )

    # Проверяем что файл читается как изображение
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Не удалось загрузить изображение: {image_path}")

    height, width = img.shape[:2]
    print(f"📐 Размер изображения: {width}x{height} пикселей, {file_size_mb:.1f} МБ")

    return image_path  # возвращаем путь к оригиналу
