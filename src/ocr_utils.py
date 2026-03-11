import easyocr
reader = easyocr.Reader(['ru', 'en'], gpu=False)
print("EasyOCR готов к работе")