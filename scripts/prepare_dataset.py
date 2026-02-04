"""
Подготовка датасета для обучения классификатора оценок
Используем MNIST для цифр 1-5, позже добавим "н" и "б"
"""

import os
import numpy as np
from PIL import Image
import random

# Классы: цифры 1-5 + empty (пустая ячейка)
# Позже добавим "н" и "б" когда соберём данные
CLASSES = ['1', '2', '3', '4', '5', 'empty']
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}
IDX_TO_CLASS = {i: c for i, c in enumerate(CLASSES)}

# Размер изображения для модели
IMG_SIZE = 28  # Как в MNIST


def load_mnist_digits():
    """Загрузить MNIST и отфильтровать цифры 1-5"""
    try:
        from torchvision.datasets import MNIST
        import torchvision.transforms as transforms
    except ImportError:
        print("Установите torchvision: pip install torchvision")
        return None

    # Загружаем MNIST
    mnist_train = MNIST(root='./data/mnist', train=True, download=True)
    mnist_test = MNIST(root='./data/mnist', train=False, download=True)

    # Фильтруем только цифры 1-5
    digits = {1: [], 2: [], 3: [], 4: [], 5: []}

    for dataset in [mnist_train, mnist_test]:
        for img, label in dataset:
            if label in digits:
                # Конвертируем PIL Image в numpy array
                img_array = np.array(img)
                digits[label].append(img_array)

    print("Загружено из MNIST:")
    for digit, images in digits.items():
        print(f"  Цифра {digit}: {len(images)} образцов")

    return digits


def generate_empty_cells(count=5000):
    """Генерируем пустые ячейки (белый фон с небольшим шумом)"""
    empty_cells = []

    for _ in range(count):
        # Белый фон (255) с небольшим шумом
        noise_level = random.randint(5, 20)
        img = np.ones((IMG_SIZE, IMG_SIZE), dtype=np.uint8) * 255
        noise = np.random.randint(-noise_level, noise_level, (IMG_SIZE, IMG_SIZE))
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Иногда добавляем горизонтальную или вертикальную линию (как в таблице)
        if random.random() < 0.3:
            line_y = random.randint(0, IMG_SIZE - 1)
            img[line_y, :] = random.randint(180, 220)

        if random.random() < 0.3:
            line_x = random.randint(0, IMG_SIZE - 1)
            img[:, line_x] = random.randint(180, 220)

        empty_cells.append(img)

    return empty_cells


def augment_image(img):
    """Аугментации для увеличения датасета"""
    from PIL import Image
    import PIL.ImageOps

    pil_img = Image.fromarray(img)
    augmented = []

    # Оригинал
    augmented.append(img)

    # Небольшой поворот (-15 до +15 градусов)
    for angle in [-10, -5, 5, 10]:
        rotated = pil_img.rotate(angle, fillcolor=255)
        augmented.append(np.array(rotated))

    # Небольшой сдвиг
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        shifted = np.roll(np.roll(img, dx, axis=1), dy, axis=0)
        augmented.append(shifted)

    return augmented


def save_dataset(digits, empty_cells, output_dir='./data/grade_dataset'):
    """Сохраняем датасет в папки по классам"""
    os.makedirs(output_dir, exist_ok=True)

    # Создаём папки train и test
    for split in ['train', 'test']:
        for cls in CLASSES:
            os.makedirs(os.path.join(output_dir, split, cls), exist_ok=True)

    # Сохраняем цифры 1-5
    for digit, images in digits.items():
        cls_name = str(digit)

        # Перемешиваем
        random.shuffle(images)

        # 80% train, 20% test
        split_idx = int(len(images) * 0.8)
        train_images = images[:split_idx]
        test_images = images[split_idx:]

        # Сохраняем train
        for i, img in enumerate(train_images):
            path = os.path.join(output_dir, 'train', cls_name, f'{i:05d}.png')
            Image.fromarray(img).save(path)

        # Сохраняем test
        for i, img in enumerate(test_images):
            path = os.path.join(output_dir, 'test', cls_name, f'{i:05d}.png')
            Image.fromarray(img).save(path)

        print(f"Класс '{cls_name}': {len(train_images)} train, {len(test_images)} test")

    # Сохраняем empty
    random.shuffle(empty_cells)
    split_idx = int(len(empty_cells) * 0.8)
    train_empty = empty_cells[:split_idx]
    test_empty = empty_cells[split_idx:]

    for i, img in enumerate(train_empty):
        path = os.path.join(output_dir, 'train', 'empty', f'{i:05d}.png')
        Image.fromarray(img).save(path)

    for i, img in enumerate(test_empty):
        path = os.path.join(output_dir, 'test', 'empty', f'{i:05d}.png')
        Image.fromarray(img).save(path)

    print(f"Класс 'empty': {len(train_empty)} train, {len(test_empty)} test")

    print(f"\nДатасет сохранён в {output_dir}")


def main():
    print("=" * 50)
    print("Подготовка датасета для классификатора оценок")
    print("Классы:", CLASSES)
    print("=" * 50)

    # 1. Загружаем MNIST
    print("\n1. Загружаем MNIST...")
    digits = load_mnist_digits()

    if digits is None:
        return

    # 2. Генерируем пустые ячейки
    print("\n2. Генерируем пустые ячейки...")
    empty_cells = generate_empty_cells(count=5000)
    print(f"  Сгенерировано: {len(empty_cells)} пустых ячеек")

    # 3. Сохраняем датасет
    print("\n3. Сохраняем датасет...")
    save_dataset(digits, empty_cells)

    print("\n" + "=" * 50)
    print("Готово! Теперь запустите scripts/train_classifier.py")
    print("=" * 50)


if __name__ == '__main__':
    main()
