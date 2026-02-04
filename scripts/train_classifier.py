"""
Обучение CNN классификатора для распознавания оценок
Классы: 1, 2, 3, 4, 5, empty (позже добавим н, б)
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from PIL import Image
import numpy as np
from pathlib import Path

# Классы (порядок важен!)
CLASSES = ['1', '2', '3', '4', '5', 'empty']
NUM_CLASSES = len(CLASSES)
IMG_SIZE = 28


class GradeDataset(Dataset):
    """Датасет для оценок"""

    def __init__(self, root_dir, transform=None):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.samples = []

        # Загружаем все изображения
        for class_idx, class_name in enumerate(CLASSES):
            class_dir = self.root_dir / class_name
            if class_dir.exists():
                for img_path in class_dir.glob('*.png'):
                    self.samples.append((str(img_path), class_idx))

        print(f"Загружено {len(self.samples)} образцов из {root_dir}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert('L')  # Grayscale

        if self.transform:
            image = self.transform(image)

        return image, label


class GradeCNN(nn.Module):
    """
    Простая CNN для классификации оценок
    Архитектура похожа на LeNet, но адаптирована под нашу задачу
    """

    def __init__(self, num_classes=NUM_CLASSES):
        super(GradeCNN, self).__init__()

        # Сверточные слои
        self.conv_layers = nn.Sequential(
            # Conv1: 1x28x28 -> 32x26x26 -> 32x13x13
            nn.Conv2d(1, 32, kernel_size=3, padding=0),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),

            # Conv2: 32x13x13 -> 64x11x11 -> 64x5x5
            nn.Conv2d(32, 64, kernel_size=3, padding=0),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),

            # Conv3: 64x5x5 -> 128x3x3
            nn.Conv2d(64, 128, kernel_size=3, padding=0),
            nn.BatchNorm2d(128),
            nn.ReLU(),
        )

        # Полносвязные слои
        self.fc_layers = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 3 * 3, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        x = self.conv_layers(x)
        x = self.fc_layers(x)
        return x


def get_transforms(train=True):
    """Трансформации для обучения и тестирования"""
    if train:
        return transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.RandomRotation(15),
            transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])
    else:
        return transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])


def train_epoch(model, dataloader, criterion, optimizer, device):
    """Одна эпоха обучения"""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in dataloader:
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    accuracy = 100.0 * correct / total
    avg_loss = running_loss / len(dataloader)
    return avg_loss, accuracy


def evaluate(model, dataloader, criterion, device):
    """Оценка модели"""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in dataloader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

    accuracy = 100.0 * correct / total
    avg_loss = running_loss / len(dataloader)
    return avg_loss, accuracy


def export_to_onnx(model, output_path, device):
    """Экспорт модели в ONNX формат"""
    model.eval()
    dummy_input = torch.randn(1, 1, IMG_SIZE, IMG_SIZE).to(device)

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={
            'input': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        }
    )
    print(f"Модель экспортирована в {output_path}")


def main():
    # Параметры
    dataset_dir = './data/grade_dataset'
    model_dir = './models'
    batch_size = 64
    num_epochs = 20
    learning_rate = 0.001

    # Создаём директорию для моделей
    os.makedirs(model_dir, exist_ok=True)

    # Устройство
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Устройство: {device}")

    # Датасеты
    print("\nЗагрузка датасетов...")
    train_dataset = GradeDataset(
        os.path.join(dataset_dir, 'train'),
        transform=get_transforms(train=True)
    )
    test_dataset = GradeDataset(
        os.path.join(dataset_dir, 'test'),
        transform=get_transforms(train=False)
    )

    if len(train_dataset) == 0:
        print("Ошибка: датасет пуст. Сначала запустите prepare_dataset.py")
        return

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    # Модель
    print("\nСоздание модели...")
    model = GradeCNN(num_classes=NUM_CLASSES).to(device)
    print(model)

    # Подсчёт параметров
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Всего параметров: {total_params:,}")

    # Loss и оптимизатор
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=3, factor=0.5)

    # Обучение
    print("\n" + "=" * 50)
    print("Начинаем обучение...")
    print("=" * 50)

    best_accuracy = 0.0

    for epoch in range(num_epochs):
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        test_loss, test_acc = evaluate(model, test_loader, criterion, device)

        scheduler.step(test_loss)

        print(f"Epoch {epoch + 1:2d}/{num_epochs}: "
              f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}% | "
              f"Test Loss: {test_loss:.4f}, Test Acc: {test_acc:.2f}%")

        # Сохраняем лучшую модель
        if test_acc > best_accuracy:
            best_accuracy = test_acc
            torch.save(model.state_dict(), os.path.join(model_dir, 'grade_classifier_best.pth'))

    # Сохраняем финальную модель
    torch.save(model.state_dict(), os.path.join(model_dir, 'grade_classifier_final.pth'))

    print("\n" + "=" * 50)
    print(f"Обучение завершено! Лучшая точность: {best_accuracy:.2f}%")
    print("=" * 50)

    # Экспорт в ONNX
    print("\nЭкспорт в ONNX...")
    model.load_state_dict(torch.load(os.path.join(model_dir, 'grade_classifier_best.pth')))
    export_to_onnx(model, os.path.join(model_dir, 'grade_classifier.onnx'), device)

    # Сохраняем метаданные
    metadata = {
        'classes': CLASSES,
        'img_size': IMG_SIZE,
        'best_accuracy': best_accuracy
    }
    import json
    with open(os.path.join(model_dir, 'grade_classifier_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)

    print("\nГотово! Файлы сохранены в ./models/:")
    print("  - grade_classifier_best.pth (PyTorch)")
    print("  - grade_classifier.onnx (ONNX для inference)")
    print("  - grade_classifier_metadata.json (метаданные)")


if __name__ == '__main__':
    main()
