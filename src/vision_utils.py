import cv2
import os

def prepare_image(image_path):
    """Проверяет изображение и создаёт отладочную копию"""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Не удалось загрузить изображение: {image_path}")
    
    # Сохраняем копию для отладки
    base = os.path.splitext(os.path.basename(image_path))[0]
    debug_path = f"debug_{base}_original.jpg"
    cv2.imwrite(debug_path, img)
    print(f"📸 Отладочное изображение сохранено: {debug_path}")
    
    return image_path  # возвращаем путь к оригиналу