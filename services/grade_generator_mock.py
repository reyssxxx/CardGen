"""
Временный mock для GradeCardGenerator
Используется для тестирования инфраструктуры рассылки до готовности реального генератора
"""
from datetime import date
from typing import Optional


class MockGradeCardGenerator:
    """
    Временный mock для тестирования инфраструктуры рассылки
    После завершения Агента 1 (генерация табелей) этот файл будет удалён
    """

    def __init__(self, template_path='./templates/grade_card_template.png'):
        """
        Инициализация mock генератора

        Args:
            template_path: путь к шаблону (не используется в mock)
        """
        self.template_path = template_path
        print("[MOCK] MockGradeCardGenerator initialized")

    def generate_card(self, student_name: str, class_name: str,
                     period_start: date, period_end: date) -> Optional[str]:
        """
        Mock генерации табеля
        Возвращает None (имитация отсутствия табеля)

        Args:
            student_name: ФИО ученика
            class_name: класс
            period_start: начало периода
            period_end: конец периода

        Returns:
            None (mock не создаёт реальных файлов)
        """
        print(f"[MOCK] Would generate card for {student_name} ({class_name}) "
              f"from {period_start} to {period_end}")
        return None
