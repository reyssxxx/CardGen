"""
Тест Tesseract на реальном изображении журнала
"""
import cv2
import sys
from services.tesseract_ocr import TesseractNameExtractor

# Путь к тестовому изображению
image_path = 'data/uploaded_photos/reysstema_20260203_234518.jpg'

print(f"Testing Tesseract on: {image_path}")
print("=" * 60)

# Загрузить изображение
image = cv2.imread(image_path)
if image is None:
    print(f"ERROR: Could not load image from {image_path}")
    sys.exit(1)

print(f"✓ Image loaded: {image.shape}")

# Создать экстрактор
extractor = TesseractNameExtractor()

if not extractor.is_available():
    print("✗ Tesseract not available!")
    print("\nTo install Tesseract:")
    print("  macOS: brew install tesseract tesseract-lang")
    print("  Linux: sudo apt-get install tesseract-ocr tesseract-ocr-rus")
    sys.exit(1)

print("✓ Tesseract available")
print()

# Извлечь имена
print("Extracting names...")
names = extractor.extract_names(image, names_region_width=0.25)

print()
print("=" * 60)
print(f"RESULTS: Found {len(names)} names")
print("=" * 60)

if names:
    for i, name in enumerate(names, 1):
        print(f"{i:2d}. {name}")
else:
    print("⚠ No names found!")
    print()
    print("Possible reasons:")
    print("  1. Image quality is too poor")
    print("  2. Text is handwritten (Tesseract works best with printed text)")
    print("  3. Image has strong perspective distortion")
    print("  4. Wrong language (need 'rus' installed)")
    print()
    print("Check if Russian language is installed:")
    print("  tesseract --list-langs | grep rus")

print()
print("=" * 60)

# Сравнение с ожидаемыми именами из фото
expected_names = [
    "Агнушевич Марк",
    "Бабичев Артем",
    "Богацкий Максим",
    "Горохов-Абубекиров Арсений",
    "Ефимов Александр",
    "Жданов Эдуард",
    "Клепалов Мирослав",
    "Колесник Владимир",
    "Костин Роман",
    "Кривоносов Никита",
    "Кузьмин Роман",
    "Лаптев Игорь",
    "Мажара Станислав",
    "Микула Анна",
    "Недайводина Ева",
    "Панасова Злата",
    "Полдубняк Михаил",
    "Ранов Владимир",
    "Синдикаева Джамиля",
    "Соколов Илья",
    "Сутягина Вероника",
    "Турикин Илья",
    "Штука Илья"
]

if names:
    print(f"\nExpected: {len(expected_names)} names")
    print(f"Found: {len(names)} names")
    print(f"Match rate: {len(names)/len(expected_names)*100:.1f}%")
    print()

    print("Expected names:")
    for name in expected_names[:5]:
        print(f"  - {name}")
    print(f"  ... and {len(expected_names)-5} more")
