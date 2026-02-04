"""
Тест CNN классификатора на реальных debug изображениях
"""

import cv2
import glob
from services.grade_classifier import GradeClassifier

def main():
    print("=" * 60)
    print("Тест CNN классификатора на реальных изображениях")
    print("=" * 60)

    # Инициализируем классификатор
    classifier = GradeClassifier()

    if not classifier.is_available():
        print("Модель не найдена! Сначала обучите модель:")
        print("  python3 scripts/train_classifier.py")
        return

    print("\n[OK] Модель загружена")

    # Ищем debug изображения
    debug_images = glob.glob("debug_grade_r*_c*_00_original.jpg")

    if not debug_images:
        print("\nDebug изображения не найдены.")
        print("Запустите test_integrated_ocr.py чтобы создать их.")
        return

    print(f"\n[OK] Найдено {len(debug_images)} изображений ячеек")

    # Тестируем на первых 20
    test_images = debug_images[:20]

    print("\n" + "=" * 60)
    print("Результаты классификации:")
    print("=" * 60)

    for img_path in test_images:
        # Загружаем изображение
        img = cv2.imread(img_path)

        if img is None:
            continue

        # Классифицируем
        result = classifier.classify_with_alternatives(img, top_k=3)

        # Выводим результат
        grade = result['text'] if result['text'] else 'empty'
        conf = result['confidence']
        needs_review = result['needs_review']

        status = "⚠️" if needs_review else "✓"

        print(f"{status} {img_path:50s} → {grade:5s} (conf: {conf:5.1f}%)", end="")

        # Альтернативы
        if result['alternatives']:
            alts = ", ".join([f"{alt[0]}({alt[1]:.0f}%)" for alt in result['alternatives'][:2]])
            print(f"  [alts: {alts}]")
        else:
            print()

    print("\n" + "=" * 60)
    print("Тест завершён!")
    print("=" * 60)

if __name__ == '__main__':
    main()
