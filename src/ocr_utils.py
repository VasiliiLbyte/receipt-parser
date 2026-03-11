import cv2
import pytesseract
import numpy as np
import os

def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Не удалось загрузить изображение: {image_path}")
    
    # Увеличение размера для лучшего распознавания
    scale_percent = 200
    width = int(img.shape[1] * scale_percent / 100)
    height = int(img.shape[0] * scale_percent / 100)
    img = cv2.resize(img, (width, height), interpolation=cv2.INTER_CUBIC)
    
    # Конвертация в оттенки серого
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Применяем CLAHE для улучшения контраста (локальный контраст)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Используем метод Оцу для автоматического порога
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Убираем шум
    kernel = np.ones((1,1), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Сохраняем отладочное изображение
    base = os.path.splitext(os.path.basename(image_path))[0]
    cv2.imwrite(f"debug_{base}_final.jpg", cleaned)
    
    return cleaned

def image_to_text(image_path):
    processed = preprocess_image(image_path)
    custom_config = r'--psm 4 --oem 3 -c tessedit_char_whitelist="абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789.,:;()-/\+ "'
    text = pytesseract.image_to_string(processed, lang='rus', config=custom_config)
    return text