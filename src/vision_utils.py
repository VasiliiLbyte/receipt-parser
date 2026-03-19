import os
from PIL import Image
from .config import MAX_FILE_SIZE_MB

# Регистрируем поддержку HEIC через pillow-heif
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False


def prepare_image(image_path):
    """Проверяет изображение перед отправкой в OpenAI, поддерживает HEIC"""

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

    # Проверяем расширение файла
    file_ext = os.path.splitext(image_path)[1].lower()
    
    # Если файл HEIC и поддержка не установлена
    if file_ext in ['.heic', '.heif'] and not HEIC_SUPPORT:
        raise ValueError(
            f"Формат {file_ext} не поддерживается. "
            f"Установите библиотеку pillow-heif: pip install pillow-heif"
        )
    
    # Проверяем что файл читается как изображение (используем Pillow для совместимости с русскими путями)
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            print(f"📐 Размер изображения: {width}x{height} пикселей, {file_size_mb:.1f} МБ")
            
            # Если это HEIC, конвертируем в JPEG для лучшей совместимости
            if file_ext in ['.heic', '.heif']:
                print(f"🔄 Конвертируем {file_ext} в JPEG для обработки...")
                # Создаем временный файл
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"converted_{os.path.basename(image_path)}.jpg")
                
                # Конвертируем в RGB и сохраняем как JPEG
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(temp_file, 'JPEG', quality=95)
                print(f"✅ Конвертировано в: {temp_file}")
                return temp_file
            
            return image_path  # возвращаем путь к оригиналу
    except Exception as e:
        raise ValueError(f"Не удалось загрузить изображение: {image_path} - {e}")
