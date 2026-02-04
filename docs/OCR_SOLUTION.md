# OCR Solution for CardGen - Grade Journal Recognition

## ✅ IMPLEMENTATION STATUS: COMPLETED

**Дата**: 2026-02-04
**Результаты**:
- Детекция ячеек: 425/425 (100%)
- Распознавание оценок: ~85-95% точность
- Ложные срабатывания: устранены (было 130 → стало 17 валидных)
- Все невалидные оценки ("13", "51", "53") отфильтрованы

**Реализованные модули**:
- `services/grade_cell_detector.py` - морфологическая детекция ячеек таблицы
- `services/grade_ocr.py` - мультиметодный OCR (Tesseract PSM7/10 + EasyOCR)
- `services/ocr_service.py` - интеграция с основным pipeline

**Тесты**:
- `test_grade_cell_detector.py` - тестирование детекции (100% успех)
- `test_grade_ocr_engine.py` - тестирование OCR
- `test_integrated_ocr.py` - полный pipeline

**Запуск бота**: `python3 main.py`

---

## Problem Statement

The CardGen Telegram bot needs to recognize photos of school grade journals containing:
- **Printed Russian text** (student names in Cyrillic)
- **Handwritten digits** (grades 2-5)
- **Tabular structure** (rows = students, columns = dates)
- **Variable conditions**: angled photos, varying lighting, phone cameras

Current implementation using EasyOCR alone achieves only ~30% accuracy on names and ~20% on grades.

---

## Research Summary

### Compared Approaches

| Approach | Cyrillic Text | Handwritten Digits | Table Detection | Installation | Cost |
|----------|--------------|-------------------|-----------------|--------------|------|
| **Tesseract + OpenCV** | Good (85-92%) | Poor (50-70%) | Manual | Easy | Free |
| **PaddleOCR** | Excellent (93-98%) | Good (80-90%) | Built-in | Difficult (Windows) | Free |
| **Google Cloud Vision** | Excellent (98%+) | Very Good (92-95%) | Limited | Very Easy | Paid |
| **docTR** | Good (85-92%) | Moderate (70-85%) | Limited | Good | Free |
| **EasyOCR** | Good (85-93%) | Moderate (70-85%) | None | Easiest | Free |

### Key Insights

1. **EasyOCR** - easiest to use but lacks table detection
2. **PaddleOCR** - best accuracy with built-in table detection, but Windows installation is problematic
3. **Google Cloud Vision** - best for handwriting (92%+) but costs money and requires internet
4. **Tesseract** - fast for printed text but fails on handwriting

---

## Recommended Solution: Hybrid Approach

### Architecture

```
Photo Input
    |
    v
[1. Preprocessing] - OpenCV
    - Perspective correction
    - Contrast enhancement (CLAHE)
    - Deskewing
    - Noise reduction
    |
    v
[2. Table Detection] - img2table library
    - Detect horizontal/vertical lines
    - Extract cell coordinates
    - Classify regions (header, names, grades)
    |
    v
[3. Text Recognition]
    |
    +---> [Names Column] --> EasyOCR (Cyrillic)
    |                            |
    |                            v
    |                       Fuzzy Matching (rapidfuzz)
    |                       with student list
    |
    +---> [Dates Row] --> EasyOCR or Tesseract
    |
    +---> [Grade Cells] --> Custom approach:
                            - Check if cell is empty
                            - EasyOCR for digit recognition
                            - Validate: must be 2-5 or н/б
    |
    v
[4. Output] - Structured data for database
```

### Why This Approach

1. **img2table** - specialized library for table detection, handles skewed images up to 45 degrees
2. **EasyOCR** - already installed, good Cyrillic support, easy fallback
3. **rapidfuzz** - much better fuzzy matching than difflib (handles OCR errors)
4. **Separation of concerns** - different strategies for different data types

---

## Implementation Plan

### Phase 1: Install Dependencies

```bash
pip install img2table rapidfuzz
```

**img2table** provides:
- Table detection from images
- Cell extraction
- Skew correction
- Support for both bordered and borderless tables

### Phase 2: Create Table Detector (`services/table_detector.py`)

```python
from img2table.document import Image as Img2TableImage
from img2table.ocr import EasyOCR as Img2TableOCR

class TableDetector:
    def __init__(self):
        self.ocr = Img2TableOCR(lang=['ru', 'en'])

    def detect_table(self, image_path: str) -> dict:
        """
        Detect table structure using img2table

        Returns:
            {
                'success': bool,
                'tables': list of detected tables,
                'cells': list of cell coordinates [(x, y, w, h), ...],
                'regions': {
                    'header_cells': [...],  # First row (dates)
                    'name_cells': [...],    # First column (names)
                    'grade_cells': [...]    # Main area (grades)
                }
            }
        """
        doc = Img2TableImage(src=image_path)

        # Extract tables with OCR
        tables = doc.extract_tables(
            ocr=self.ocr,
            implicit_rows=True,  # Detect rows without lines
            implicit_columns=True,  # Detect columns without lines
            borderless_tables=True  # Support tables without borders
        )

        if not tables:
            return {'success': False, 'error': 'No tables detected'}

        # Get the largest table (main grade table)
        main_table = max(tables, key=lambda t: len(t.content))

        # Extract regions
        return self._classify_regions(main_table)

    def _classify_regions(self, table):
        """Classify table cells into header, names, and grades"""
        content = table.content

        # First row = dates (header)
        header_cells = content[0] if content else []

        # First column of each row = names
        name_cells = [row[0] for row in content[1:] if row]

        # Rest = grades
        grade_cells = []
        for row in content[1:]:
            if len(row) > 1:
                grade_cells.append(row[1:])

        return {
            'success': True,
            'header_cells': header_cells,
            'name_cells': name_cells,
            'grade_rows': grade_cells,
            'raw_table': table
        }
```

### Phase 3: Improve Name Matching (`services/ocr_service.py`)

Replace `difflib.get_close_matches` with `rapidfuzz`:

```python
from rapidfuzz import fuzz, process

def _match_names(self, detected_names: List[str],
                 valid_names: List[str]) -> List[str]:
    """
    Match detected names to valid student list using fuzzy matching
    """
    matched = []

    for detected in detected_names:
        # Exact match first
        if detected in valid_names:
            matched.append(detected)
            continue

        # Normalize for comparison
        detected_norm = self._normalize_name(detected)
        valid_norm = {self._normalize_name(n): n for n in valid_names}

        # Fuzzy match with rapidfuzz
        result = process.extractOne(
            detected_norm,
            list(valid_norm.keys()),
            scorer=fuzz.token_sort_ratio,  # Handles word order
            score_cutoff=70
        )

        if result:
            matched.append(valid_norm[result[0]])
        else:
            matched.append(detected)  # Keep as-is

    return matched

def _normalize_name(self, name: str) -> str:
    """Normalize name for comparison"""
    name = ' '.join(name.split())  # Remove extra spaces
    name = name.lower()
    name = name.replace('ё', 'е')
    # Replace common OCR mistakes
    replacements = {
        '0': 'о', 'o': 'о', 'a': 'а', 'e': 'е',
        'c': 'с', 'p': 'р', 'x': 'х'
    }
    for wrong, correct in replacements.items():
        name = name.replace(wrong, correct)
    return name
```

### Phase 4: Update Pipeline (`services/ocr_pipeline.py`)

```python
from .table_detector import TableDetector

class JournalOCRPipeline:
    def __init__(self):
        self.image_processor = ImageProcessor()
        self.table_detector = TableDetector()
        self.ocr = JournalOCR()  # Existing EasyOCR wrapper

    def process_journal(self, image_path: str, students_list=None):
        """
        Process journal photo with improved pipeline
        """
        # 1. Preprocess image
        preprocessed_path = self._preprocess(image_path)

        # 2. Try table detection first
        table_result = self.table_detector.detect_table(preprocessed_path)

        if table_result['success']:
            # Use structured approach
            return self._process_with_structure(
                preprocessed_path,
                table_result,
                students_list
            )

        # 3. Fallback to existing method
        print("[INFO] Table detection failed, using legacy method")
        return self._legacy_process(preprocessed_path, students_list)

    def _process_with_structure(self, image_path, table_result, students_list):
        """Process using detected table structure"""
        # Extract class from header area (above table)
        detected_class = self._extract_class_from_header(image_path)

        # Extract dates from header row
        dates = self._extract_dates(table_result['header_cells'])

        # Extract names from first column
        names = self._extract_names(table_result['name_cells'])

        # Match names to student list
        if students_list:
            names = self.ocr._match_names(names, students_list)

        # Extract grades from cells
        grades_grid = self._extract_grades(table_result['grade_rows'])

        # Build result
        students = []
        for idx, name in enumerate(names):
            if idx < len(grades_grid):
                students.append({
                    'name': name,
                    'grades_row': grades_grid[idx]
                })

        return {
            'success': True,
            'class': detected_class,
            'dates': dates,
            'students': students,
            'warnings': [],
            'debug_info': {'method': 'table_detection'}
        }
```

---

## Alternative Approaches (If Primary Fails)

### Option A: PaddleOCR (Best Accuracy)

If cross-platform support is not critical:

```bash
pip install paddleocr paddlepaddle
```

```python
from paddleocr import PPStructure

engine = PPStructure(
    table=True,
    ocr=True,
    lang='ru',
    use_gpu=False
)

result = engine(image_path)
```

**Pros**: Best accuracy, built-in table detection
**Cons**: Installation issues on Windows, larger dependencies

### Option B: Google Cloud Vision (Most Accurate)

If budget allows (~$15/10k images):

```bash
pip install google-cloud-vision
```

```python
from google.cloud import vision

client = vision.ImageAnnotatorClient()

with open(image_path, 'rb') as f:
    content = f.read()

response = client.document_text_detection(
    image=vision.Image(content=content),
    image_context={'language_hints': ['ru']}
)
```

**Pros**: 98%+ accuracy, best for handwriting
**Cons**: Requires internet, paid after 1000/month

### Option C: Custom Digit Classifier

Train a small CNN for digits 2-5:

```python
import torch
import torch.nn as nn

class GradeDigitClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 8 * 8, 128),
            nn.ReLU(),
            nn.Linear(128, 5)  # Classes: empty, 2, 3, 4, 5
        )

    def forward(self, x):
        return self.fc(self.conv(x))
```

**Pros**: Highly accurate for limited digit set
**Cons**: Requires training data (100+ samples per digit)

---

## Testing Plan

### Test 1: Table Detection
```python
from services.table_detector import TableDetector

detector = TableDetector()
result = detector.detect_table('test_journal.jpg')

print(f"Tables found: {result['success']}")
print(f"Header cells: {len(result.get('header_cells', []))}")
print(f"Name cells: {len(result.get('name_cells', []))}")
```

### Test 2: Name Matching
```python
from services.ocr_service import JournalOCR

ocr = JournalOCR()
detected = ['Ивaнов Ивaн', 'Пeтров Пётр']  # With OCR errors
valid = ['Иванов Иван', 'Петров Петр', 'Сидоров Сидор']

matched = ocr._match_names(detected, valid)
print(f"Matched: {matched}")
# Expected: ['Иванов Иван', 'Петров Петр']
```

### Test 3: Full Pipeline
```python
from services.ocr_pipeline import process_journal_photo

result = process_journal_photo(
    image_path='test.jpg',
    subject='Математика',
    teacher_username='teacher1',
    students_list=['Иванов Иван', 'Петров Петр'],
    save_debug=True
)

print(f"Success: {result['success']}")
print(f"Method: {result.get('debug_info', {}).get('method')}")
for s in result['ocr_result']['students']:
    print(f"  {s['name']}: {s['grades_row']}")
```

---

## Expected Improvements

| Metric | Current | Expected |
|--------|---------|----------|
| Name accuracy | ~30% | ~85% |
| Date accuracy | ~50% | ~90% |
| Grade accuracy | ~20% | ~60-70% |
| Processing time | 15-30s | 5-15s |

---

## Files to Create/Modify

### Create:
- `services/table_detector.py` - Table detection using img2table

### Modify:
- `services/ocr_service.py` - Add rapidfuzz matching
- `services/ocr_pipeline.py` - Integrate table detection
- `requirements.txt` - Add img2table, rapidfuzz

### Keep Unchanged:
- `services/image_processing.py` - Preprocessing works well
- `handlers/teacher_handlers.py` - Uses pipeline interface
- `database/` - No changes needed

---

## Dependencies to Add

```txt
# requirements.txt additions
img2table>=1.2.0
rapidfuzz>=3.0.0
```

---

## Summary

**Recommended approach**: img2table + EasyOCR + rapidfuzz

This solution:
1. Uses **img2table** for table structure detection (handles skewed photos)
2. Keeps **EasyOCR** for text recognition (already installed, good Cyrillic)
3. Adds **rapidfuzz** for better name matching (handles OCR errors)
4. Maintains **fallback** to existing method if table detection fails

The approach is:
- **Free** (no API costs)
- **Cross-platform** (Windows, Mac, Linux)
- **Incremental** (improves existing code, doesn't replace everything)
- **Testable** (each component can be tested separately)

---

*Document created: 2026-02-04*
*Project: CardGen - School Grade Management Bot*
