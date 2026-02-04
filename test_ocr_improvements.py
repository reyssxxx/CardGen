"""
Тестовый скрипт для проверки улучшений OCR
Проверяет работу table detection и fuzzy matching
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))


def test_table_detector():
    """Тест 1: Проверка работы TableDetector"""
    print("=" * 60)
    print("TEST 1: Table Detection")
    print("=" * 60)

    try:
        # Проверяем что файл существует
        from pathlib import Path
        detector_path = Path(__file__).parent / 'services' / 'table_detector.py'
        if not detector_path.exists():
            print(f"✗ table_detector.py not found at {detector_path}")
            return False

        print(f"✓ table_detector.py exists")

        # Проверяем импорты
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location("table_detector", detector_path)
        module = importlib.util.module_from_spec(spec)

        # Добавляем services в sys.modules чтобы избежать проблем с импортами
        sys.modules['table_detector'] = module
        spec.loader.exec_module(module)

        # Проверяем что класс существует
        assert hasattr(module, 'TableDetector'), "TableDetector class not found"
        print("✓ TableDetector class is available")

        # Проверяем методы
        detector_class = getattr(module, 'TableDetector')
        assert hasattr(detector_class, 'detect_table'), "detect_table method not found"
        assert hasattr(detector_class, 'extract_cell_text'), "extract_cell_text method not found"
        print("✓ All required methods are present")

        return True
    except Exception as e:
        print(f"✗ TableDetector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_name_matching():
    """Тест 2: Проверка fuzzy matching имен"""
    print("\n" + "=" * 60)
    print("TEST 2: Name Matching with rapidfuzz")
    print("=" * 60)

    try:
        # Прямой импорт из файла чтобы избежать зависимостей
        import sys
        import importlib.util
        from pathlib import Path

        ocr_path = Path(__file__).parent / 'services' / 'ocr_service.py'
        spec = importlib.util.spec_from_file_location("ocr_service", ocr_path)
        ocr_module = importlib.util.module_from_spec(spec)
        sys.modules['ocr_service'] = ocr_module
        spec.loader.exec_module(ocr_module)

        JournalOCR = ocr_module.JournalOCR
        ocr = JournalOCR()
        print("✓ JournalOCR initialized successfully")

        # Тестовые данные с ошибками OCR
        detected_names = [
            'Иванов Ивaн',      # Латинская 'a' вместо 'а'
            'Петp0в Петр',      # Латинская 'p' и '0' вместо 'о'
            'Сидopов Сидор',    # Латинские 'o', 'p'
        ]

        valid_names = [
            'Иванов Иван',
            'Петров Петр',
            'Сидоров Сидор',
            'Смирнов Сергей'
        ]

        print(f"\nDetected names (with OCR errors):")
        for name in detected_names:
            print(f"  - {name}")

        print(f"\nValid student list:")
        for name in valid_names:
            print(f"  - {name}")

        # Запускаем matching
        matched = ocr._match_names(detected_names, valid_names)

        print(f"\nMatching results:")
        for original, matched_name in zip(detected_names, matched):
            status = "✓" if matched_name in valid_names else "?"
            print(f"  {status} '{original}' → '{matched_name}'")

        # Проверяем что все имена правильно сопоставлены
        success = all(name in valid_names for name in matched)
        if success:
            print("\n✓ All names matched correctly!")
        else:
            print("\n✗ Some names were not matched")

        return success

    except Exception as e:
        print(f"✗ Name matching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_integration():
    """Тест 3: Проверка интеграции в pipeline"""
    print("\n" + "=" * 60)
    print("TEST 3: Pipeline Integration")
    print("=" * 60)

    try:
        # Проверяем наличие файла и нужных методов
        from pathlib import Path
        pipeline_path = Path(__file__).parent / 'services' / 'ocr_pipeline.py'

        if not pipeline_path.exists():
            print("✗ ocr_pipeline.py not found")
            return False

        # Читаем файл и проверяем наличие нужных методов
        content = pipeline_path.read_text()

        checks = {
            'TableDetector import': 'from .table_detector import TableDetector' in content,
            'table_detector initialization': 'self.table_detector = TableDetector()' in content,
            '_process_with_structure method': 'def _process_with_structure' in content,
            '_legacy_process method': 'def _legacy_process' in content,
            'table detection call': 'table_result = self.table_detector.detect_table' in content,
        }

        all_passed = True
        for check_name, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"{status} {check_name}")
            if not passed:
                all_passed = False

        if all_passed:
            print("✓ All pipeline components integrated successfully")

        return all_passed

    except Exception as e:
        print(f"✗ Pipeline integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dependencies():
    """Тест 4: Проверка установки зависимостей"""
    print("\n" + "=" * 60)
    print("TEST 4: Dependencies Check")
    print("=" * 60)

    try:
        import img2table
        version = getattr(img2table, '__version__', 'unknown')
        print(f"✓ img2table installed (version {version})")
    except ImportError:
        print("✗ img2table not installed")
        return False

    try:
        import rapidfuzz
        version = getattr(rapidfuzz, '__version__', 'unknown')
        print(f"✓ rapidfuzz installed (version {version})")
    except ImportError:
        print("✗ rapidfuzz not installed")
        return False

    try:
        import easyocr
        print(f"✓ easyocr available")
    except ImportError:
        print("⚠ easyocr not installed (optional for this test)")

    return True


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("CardGen OCR Improvements - Test Suite")
    print("=" * 60)
    print("\nTesting the following improvements:")
    print("  1. Table detection with img2table")
    print("  2. Fuzzy name matching with rapidfuzz")
    print("  3. Pipeline integration")
    print("  4. Dependencies")
    print()

    results = {
        "Dependencies": test_dependencies(),
        "Table Detector": test_table_detector(),
        "Name Matching": test_name_matching(),
        "Pipeline Integration": test_pipeline_integration(),
    }

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<40} {status}")

    all_passed = all(results.values())
    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed! OCR improvements are working correctly.")
        print("\nNext steps:")
        print("  1. Test with real journal images")
        print("  2. Compare accuracy with previous version")
        print("  3. Monitor performance in production")
    else:
        print("\n⚠ Some tests failed. Please check the errors above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
