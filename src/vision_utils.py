import os
import tempfile
from PIL import Image, ImageOps, ImageFilter
from .config import MAX_FILE_SIZE_MB

# Регистрируем поддержку HEIC через pillow-heif
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False


def enhance_receipt_image(image_path: str) -> str:
    """
    Улучшает качество изображения чека для лучшего распознавания.
    
    Применяет:
    1. Конвертация в grayscale
    2. Автоконтраст
    3. Повышение резкости (2 раза)
    4. Deskew (выравнивание угла наклона)
    
    Args:
        image_path: путь к исходному изображению
        
    Returns:
        путь к улучшенному изображению (временный файл) или оригинальный путь при ошибке
    """
    try:
        # 1. Открываем изображение через Pillow
        img = Image.open(image_path)
        
        # 2. Конвертируем в grayscale
        img = img.convert('L')
        
        # 3. Применяем автоконтраст
        img = ImageOps.autocontrast(img, cutoff=2)
        
        # 4. Повышаем резкость через ImageFilter.SHARPEN — применяем 2 раза подряд
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
        
        # 5. Применяем deskew (выравнивание угла наклона)
        try:
            import cv2
            import numpy as np
            
            # Конвертируем PIL Image в numpy array для OpenCV
            img_array = np.array(img)
            
            # Бинаризуем изображение через Otsu threshold
            _, binary = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Находим контуры
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Объединяем все контуры в один массив точек
                all_points = np.vstack(contours)
                
                # Применяем minAreaRect для определения угла наклона
                rect = cv2.minAreaRect(all_points)
                angle = rect[2]
                
                # Нормализуем угол (minAreaRect возвращает угол от -90 до 0)
                if angle < -45:
                    angle = 90 + angle
                
                # Если угол отклонения от горизонтали больше 1° и меньше 45° — поворачиваем
                if 1 < abs(angle) < 45:
                    print(f"🔄 Выравнивание угла наклона: {angle:.1f}°")
                    img = img.rotate(angle, expand=True, fillcolor=255)
        except Exception:
            # Молча пропускаем deskew при любой ошибке
            pass
        
        # 6. Сохраняем результат во временный файл
        fd, temp_path = tempfile.mkstemp(suffix='_enhanced.jpg')
        os.close(fd)
        
        # Конвертируем обратно в RGB для сохранения в JPEG (grayscale сохраняется как L)
        if img.mode == 'L':
            img = img.convert('RGB')
        
        img.save(temp_path, 'JPEG', quality=95)
        print(f"✨ Изображение улучшено: {temp_path}")
        
        return temp_path
        
    except Exception as e:
        print(f"⚠️ enhance_receipt_image failed: {e}")
        return image_path


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
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"converted_{os.path.basename(image_path)}.jpg")
                
                # Конвертируем в RGB и сохраняем как JPEG
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(temp_file, 'JPEG', quality=95)
                print(f"✅ Конвертировано в: {temp_file}")
                
                # Применяем улучшение к конвертированному файлу
                image_path = enhance_receipt_image(temp_file)
                return image_path
            
            # Применяем улучшение изображения перед возвратом
            image_path = enhance_receipt_image(image_path)
            return image_path
    except Exception as e:
        raise ValueError(f"Не удалось загрузить изображение: {image_path} - {e}")
