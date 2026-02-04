# Улучшения OCR для Рукописного Текста

## 🎯 Проблема
Рукописный текст в журнале плохо распознавался EasyOCR:
- Низкий confidence (0.05-0.40)
- Много артефактов и неправильных символов
- Смешение латиницы и кириллицы

## ✅ Реализованные Улучшения

### 1. Специальная Предобработка для Рукописи
**Файл:** `services/image_processing.py`

Добавлен метод `enhance_for_handwriting()`:

```python
def enhance_for_handwriting(self, image):
    # 1. Увеличение разрешения в 2x (super-resolution)
    upscaled = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 2. Агрессивная фильтрация шумов (h=15 вместо h=10)
    denoised = cv2.fastNlMeansDenoising(upscaled, h=15)

    # 3. Усиление контраста (clipLimit=4.0 вместо 3.0)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
    contrast_enhanced = clahe.apply(denoised)

    # 4. Морфологическое утолщение линий
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(contrast_enhanced, kernel, iterations=1)

    # 5. Адаптивная бинаризация (blockSize=15 вместо 11)
    binary = cv2.adaptiveThreshold(dilated, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 15, 3)

    # 6. Удаление мелких артефактов
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    return cleaned
```

**Ключевые изменения:**
- ✅ **Увеличение разрешения в 2x** - лучше видны детали рукописи
- ✅ **Агрессивнее шумоподавление** - h=15 вместо h=10
- ✅ **Сильнее контраст** - clipLimit=4.0 вместо 3.0
- ✅ **Утолщение линий** - помогает с тонкими линиями рукописи
- ✅ **Больший блок бинаризации** - 15 вместо 11
- ✅ **Морфологическая очистка** - убирает артефакты

### 2. Оптимизированные Параметры EasyOCR
**Файл:** `services/ocr_service.py`

Улучшены параметры `readtext()`:

```python
results = self.reader.readtext(
    image,
    detail=1,              # Получать bbox и confidence
    paragraph=False,       # Не группировать в параграфы
    min_size=10,          # Минимальный размер текста
    text_threshold=0.6,   # СНИЖЕН с 0.7 для рукописи
    low_text=0.3,         # Порог для детекции текста
    link_threshold=0.3,   # Порог для связывания символов
    canvas_size=2560,     # Размер canvas для обработки
    mag_ratio=1.5         # Увеличение для лучшей детекции
)
```

**Ключевые параметры:**
- ✅ **text_threshold=0.6** - снижен с 0.7 для рукописи
- ✅ **canvas_size=2560** - больше canvas для обработки
- ✅ **mag_ratio=1.5** - дополнительное увеличение
- ✅ **min_size=10** - минимальный размер детекции

### 3. Уже Реализованные Улучшения (из предыдущей сессии)

**Фильтр по Confidence:**
```python
if conf < 0.4:  # Отбрасываем ненадёжное распознавание
    continue
```

**Нормализация Русских Имён:**
```python
def _normalize_russian_name(text):
    # Исправление латиницы → кириллица
    replacements = {'O': 'О', 'a': 'а', 'e': 'е', 'c': 'с', ...}
    # Капитализация
    text = ' '.join(word.capitalize() for word in text.split())
    # Удаление не-кириллических символов
    return text
```

**Fuzzy Matching:**
- Порог снижен с 0.6 до 0.5
- Добавлен debug вывод совпадений

**Усиленная Предобработка:**
- CLAHE clipLimit: 2.0 → 3.0
- Включено удаление шумов

## 📊 Ожидаемые Результаты

| Параметр | До | После |
|----------|-----|-------|
| Разрешение | 1x | 2x (увеличено) |
| Контраст | 2.0 | 4.0 (усилен) |
| Шумоподавление | h=10 | h=15 (агрессивнее) |
| Бинаризация | blockSize=11 | blockSize=15 (больше) |
| Утолщение линий | Нет | Есть (dilation) |
| EasyOCR threshold | 0.7 | 0.6 (ниже) |
| Canvas size | default | 2560 (больше) |

## 🧪 Тестирование

Попробуй загрузить то же фото снова:
1. Разрешение увеличится в 2x перед OCR
2. Контраст станет сильнее
3. Линии рукописи утолщатся
4. EasyOCR будет более чувствительным

## 📈 Если Всё Равно Плохо Работает

### План Б: PaddleOCR (лучший для рукописи + таблиц)

```bash
pip install paddlepaddle paddleocr
```

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='ru')
result = ocr.ocr(image_path, cls=True)
```

**Плюсы PaddleOCR:**
- 🟢 Лучшая точность на рукописи
- 🟢 Специально обучен для таблиц
- 🟢 Быстрее EasyOCR
- 🟢 Хорошая поддержка русского

### План В: Гибридный подход

Запускать EasyOCR + PaddleOCR параллельно и выбирать лучший результат по confidence.

### План Г: Google Cloud Vision API (платно)

Самая высокая точность, но $1.50 за 1000 запросов.

## 🔧 Отладка

Если нужно посмотреть предобработанное изображение:

```python
# В ocr_pipeline.py
result = process_journal_photo(
    image_path=str(file_path),
    save_debug=True  # Сохранит _processed.jpg
)
```

Проверь файл `reysstema_TIMESTAMP_processed.jpg` чтобы увидеть что видит OCR.

## 💡 Дополнительные Советы

Для **лучшего качества фото**:
1. Хорошее освещение (естественный свет)
2. Избегать теней и бликов
3. Камера строго параллельно странице
4. Высокое разрешение (минимум 1920x1080)
5. Фокус на тексте

Для **OCR**:
1. Если EasyOCR не справляется - попробуй PaddleOCR
2. Если и PaddleOCR плохо - используй /add_grade для ручного ввода
3. Можно комбинировать: OCR для большинства + ручной ввод для проблемных
