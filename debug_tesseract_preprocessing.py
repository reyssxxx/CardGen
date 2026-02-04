"""
Отладка предобработки для Tesseract
Сохраняет промежуточные изображения чтобы увидеть что не так
"""
import cv2
import numpy as np
from services.document_scanner import DocumentScanner
from services.tesseract_ocr import TesseractNameExtractor

# Загрузить тестовое изображение
image_path = 'data/uploaded_photos/reysstema_20260203_234518.jpg'
image = cv2.imread(image_path)

print(f"Original image shape: {image.shape}")

# 1. Document scanning
scanner = DocumentScanner()
scanned, found = scanner.scan_document(image)
print(f"Document found: {found}")

if found:
    cv2.imwrite('debug_01_scanned.jpg', scanned)
    print("✓ Saved: debug_01_scanned.jpg")
else:
    scanned = image

# 2. Extract names region (left 25%)
height, width = scanned.shape[:2]
names_region = scanned[:, 0:int(width * 0.25)]
cv2.imwrite('debug_02_names_region.jpg', names_region)
print("✓ Saved: debug_02_names_region.jpg")

# 3. Apply Tesseract preprocessing
extractor = TesseractNameExtractor()
preprocessed = extractor._preprocess_for_names(names_region)
cv2.imwrite('debug_03_preprocessed.jpg', preprocessed)
print("✓ Saved: debug_03_preprocessed.jpg")

# 4. Try different preprocessing params
print("\n" + "=" * 60)
print("Testing different preprocessing parameters...")
print("=" * 60)

# Вариант 1: Менее агрессивная бинаризация
gray = cv2.cvtColor(names_region, cv2.COLOR_BGR2GRAY)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
enhanced = clahe.apply(gray)
binary1 = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)
cv2.imwrite('debug_04_variant1_simple.jpg', binary1)
print("✓ Saved: debug_04_variant1_simple.jpg (simple threshold)")

# Вариант 2: Otsu thresholding
_, binary2 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
cv2.imwrite('debug_05_variant2_otsu.jpg', binary2)
print("✓ Saved: debug_05_variant2_otsu.jpg (Otsu)")

# Вариант 3: Просто увеличенное и улучшенное
scale = 2.0
scaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
clahe2 = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
enhanced2 = clahe2.apply(scaled)
cv2.imwrite('debug_06_variant3_scaled_only.jpg', enhanced2)
print("✓ Saved: debug_06_variant3_scaled_only.jpg (scaled+CLAHE only)")

print("\n" + "=" * 60)
print("Debug images saved! Check them:")
print("  1. debug_01_scanned.jpg - Document after perspective correction")
print("  2. debug_02_names_region.jpg - Left 25% with names")
print("  3. debug_03_preprocessed.jpg - Current preprocessing (not working)")
print("  4. debug_04_variant1_simple.jpg - Simple threshold")
print("  5. debug_05_variant2_otsu.jpg - Otsu threshold")
print("  6. debug_06_variant3_scaled_only.jpg - Just scaled+CLAHE")
print("=" * 60)
