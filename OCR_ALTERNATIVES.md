# Альтернативы OCR для Улучшения Распознавания

## Текущая Проблема
- **EasyOCR** показывает низкий confidence (0.05-0.40) на фото журнала
- Много артефактов и неправильных символов
- Смешение латиницы и кириллицы

---

## 1. **Tesseract OCR** (РЕКОМЕНДУЕТСЯ для начала)

### Плюсы:
- ✅ **Быстрее** чем EasyOCR
- ✅ **Лучше для печатного текста** (журналы - печатный текст!)
- ✅ **Активно развивается** Google
- ✅ **Отличная поддержка русского языка** (rus.traineddata)
- ✅ **Можно тонко настроить** параметры распознавания

### Минусы:
- ❌ Требует установки системного пакета
- ❌ Хуже с рукописным текстом

### Установка:
```bash
# Windows
# Скачать https://github.com/UB-Mannheim/tesseract/wiki
# Добавить в PATH

# Python
pip install pytesseract pillow
```

### Пример кода:
```python
import pytesseract
from PIL import Image

# Конфигурация для русского языка
custom_config = r'--oem 3 --psm 6 -l rus'
text = pytesseract.image_to_string(image, config=custom_config)

# Получить confidence для каждого слова
data = pytesseract.image_to_data(image, lang='rus', output_type=pytesseract.Output.DICT)
```

### Настройки PSM (Page Segmentation Mode):
- `--psm 6` - Assume a single uniform block of text (для таблиц)
- `--psm 11` - Sparse text. Find as much text as possible in no particular order
- `--psm 4` - Assume a single column of text of variable sizes

---

## 2. **PaddleOCR** (ЛУЧШИЙ для таблиц)

### Плюсы:
- ✅ **ОТЛИЧНАЯ точность** на таблицах
- ✅ **Специально обучен** для структурированных документов
- ✅ **Быстрее** EasyOCR
- ✅ **Хорошая поддержка** русского и английского
- ✅ **Встроенная детекция таблиц**

### Минусы:
- ❌ Больше зависимостей (PaddlePaddle)
- ❌ Сложнее установка на Windows

### Установка:
```bash
pip install paddlepaddle paddleocr
```

### Пример кода:
```python
from paddleocr import PaddleOCR

# Инициализация
ocr = PaddleOCR(use_angle_cls=True, lang='ru')

# Распознавание
result = ocr.ocr(image_path, cls=True)

# Результат: [(bbox, (text, confidence))]
for line in result[0]:
    bbox, (text, conf) = line
    print(f"{text}: {conf:.2f}")
```

---

## 3. **TrOCR** (Microsoft)

### Плюсы:
- ✅ **Transformer-based** - современная архитектура
- ✅ **Отличная точность**
- ✅ Хорошо работает с искажениями

### Минусы:
- ❌ **МЕДЛЕННО** (требует GPU)
- ❌ Большая модель
- ❌ Сложнее интеграция

---

## 4. **Google Cloud Vision API** (Платно)

### Плюсы:
- ✅ **ЛУЧШАЯ точность** (коммерческое решение)
- ✅ Отличная поддержка русского
- ✅ Детекция таблиц из коробки

### Минусы:
- ❌ **ПЛАТНО** ($1.50 за 1000 запросов)
- ❌ Требует интернет
- ❌ Зависимость от внешнего сервиса

---

## 5. **Гибридный Подход** (РЕКОМЕНДУЕТСЯ)

Использовать несколько OCR движков и выбирать лучший результат:

```python
def hybrid_ocr(image):
    # Запускаем параллельно несколько OCR
    tesseract_result = run_tesseract(image)
    paddle_result = run_paddle(image)
    easy_result = run_easyocr(image)

    # Выбираем результат с наивысшим confidence
    results = [
        (tesseract_result, tesseract_confidence),
        (paddle_result, paddle_confidence),
        (easy_result, easy_confidence)
    ]

    return max(results, key=lambda x: x[1])
```

---

## 📈 Сравнение Производительности

| OCR | Скорость | Точность (печать) | Точность (рукопись) | Таблицы | Русский |
|-----|----------|-------------------|---------------------|---------|---------|
| **EasyOCR** | 🟡 Средняя | 🟡 Средняя | 🟢 Хорошая | 🟡 Средняя | 🟢 Хорошо |
| **Tesseract** | 🟢 Быстро | 🟢 Хорошая | 🔴 Плохая | 🟢 Хорошо | 🟢 Отлично |
| **PaddleOCR** | 🟢 Быстро | 🟢 Отличная | 🟢 Хорошая | 🟢 Отлично | 🟢 Хорошо |
| **TrOCR** | 🔴 Медленно | 🟢 Отличная | 🟢 Отличная | 🟡 Средняя | 🟡 Средняя |
| **Google Vision** | 🟢 Быстро | 🟢 Отличная | 🟢 Отличная | 🟢 Отлично | 🟢 Отлично |

---

## 🎯 Рекомендуемый План Действий

### Фаза 1: Попробовать Tesseract (1-2 часа)
- Самый простой в установке
- Отлично работает с печатным текстом
- Быстрее EasyOCR
- **Код готов к интеграции**

### Фаза 2: Если Tesseract не помог - PaddleOCR (2-3 часа)
- Лучший для таблиц
- Сложнее установка, но лучше результаты

### Фаза 3: Гибридный подход (3-4 часа)
- Использовать Tesseract + EasyOCR параллельно
- Выбирать лучший результат по confidence

---

## 🔧 Дополнительные Улучшения Предобработки

Независимо от выбранного OCR, можно улучшить предобработку:

### 1. Увеличение разрешения (Super-Resolution)
```python
# Используем cv2.resize с интерполяцией
upscaled = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
```

### 2. Адаптивная бинаризация для разных регионов
```python
# Разные параметры для области имён и оценок
names_region = adaptive_threshold(image[:, :250], blockSize=15, C=5)
grades_region = adaptive_threshold(image[:, 250:], blockSize=11, C=2)
```

### 3. Morphological operations
```python
# Утолщение букв
kernel = np.ones((2,2), np.uint8)
dilated = cv2.dilate(binary, kernel, iterations=1)
```

### 4. Skew correction (уже есть, но можно улучшить)
```python
# Более точная коррекция наклона
angle = detect_skew(image)
corrected = rotate_image(image, angle)
```

---

## 💡 Мой Совет

**Начни с Tesseract:**
1. Быстрая установка (5 минут)
2. Легкая интеграция (10 минут кода)
3. Если не поможет - переходи к PaddleOCR
4. Если и это не решит - делай гибридный подход

**Причина:** Журналы - это печатный текст в таблице. Tesseract создан именно для этого и будет быстрее + точнее EasyOCR на такой задаче.
