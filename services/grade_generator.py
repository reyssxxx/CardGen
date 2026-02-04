"""
Генератор табелей успеваемости
"""
import os
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional
from PIL import Image, ImageDraw, ImageFont

from database.grade_repository import GradeRepository
from utils.formatters import format_date, calculate_average


# Координаты для наложения текста на шаблон
TEMPLATE_COORDS = {
    # Заголовок таблицы (даты над предметами)
    'header_dates_start_x': 391,
    'header_dates_y': 12,
    'header_date_width': 115,

    # Ячейки оценок
    'grades_start_x': 391,
    'grades_start_y': 38,
    'cell_width': 115,
    'cell_height': 24,

    # Поле для среднего балла (последняя колонка "I п/г")
    'average_x': 1110,
    'average_y': 460,
}

# Порядок предметов в шаблоне
SUBJECT_ORDER = [
    "Русский язык",
    "Литература",
    "Алгебра и начала математического анализа",
    "Геометрия",
    "Вероятность и статистика",
    "Информатика",
    "Физика",
    "Химия",
    "Биология",
    "История",
    "Обществознание",
    "География",
    "Физическая культура",
    "Основы безопасности и защиты Родины",
    "Индивидуальный проект*",
    "Иностранный язык (английский)",
    "Технологии программирования",
]

# Маппинг предметов из БД на предметы шаблона
SUBJECT_MAPPING = {
    'Иностранный язык (англ)': 'Иностранный язык (английский)',
    'Индивидуальный проект': 'Индивидуальный проект*',
}

# Цветовая индикация оценок (RGB)
GRADE_COLORS = {
    '5': (0, 150, 0),        # Зеленый
    '4': (200, 150, 0),      # Желтый/оранжевый
    '3': (200, 50, 0),       # Красный
    '2': (200, 0, 0),        # Ярко-красный
    'н': (100, 100, 100),    # Серый
    'н/н': (100, 100, 100),
    'б': (100, 100, 100),
}


class GradeCardGenerator:
    """Генератор табелей успеваемости на основе шаблона"""

    def __init__(self, template_path='./templates/grade_card_template.png'):
        """
        Инициализация генератора

        Args:
            template_path: Путь к шаблону табеля
        """
        self.template_path = template_path
        self.grade_repo = GradeRepository()

        # Создать директорию для табелей
        self.output_dir = Path('./data/grade_cards')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Загрузить шрифты
        self._load_fonts()

        print(f"[INFO] GradeCardGenerator initialized. Output dir: {self.output_dir}")

    def _load_fonts(self):
        """Загружает шрифты для русского текста"""
        try:
            # Попытка загрузить Arial
            self.font_dates = ImageFont.truetype("arial.ttf", 12)
            self.font_grades = ImageFont.truetype("arial.ttf", 18)
            self.font_title = ImageFont.truetype("arialbd.ttf", 16)
            print("[INFO] Loaded Arial fonts")
        except OSError:
            try:
                # Fallback на DejaVu
                self.font_dates = ImageFont.truetype("DejaVuSans.ttf", 12)
                self.font_grades = ImageFont.truetype("DejaVuSans.ttf", 18)
                self.font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
                print("[INFO] Loaded DejaVu fonts")
            except OSError:
                # Fallback на дефолтный
                self.font_dates = ImageFont.load_default()
                self.font_grades = ImageFont.load_default()
                self.font_title = ImageFont.load_default()
                print("[WARNING] Could not load TrueType fonts, using default")

    def generate_card(self, student_name: str, class_name: str,
                     period_start: date, period_end: date) -> str:
        """
        Генерирует табель для ученика за указанный период

        Args:
            student_name: ФИО ученика
            class_name: Класс ученика
            period_start: Начало периода
            period_end: Конец периода

        Returns:
            Путь к сгенерированному изображению

        Raises:
            Exception: Если не удалось сгенерировать табель
        """
        print(f"[INFO] Generating grade card for {student_name}, {class_name}")
        print(f"[INFO] Period: {period_start} - {period_end}")

        # 1. Загрузить шаблон
        try:
            template = Image.open(self.template_path).convert('RGB')
        except Exception as e:
            raise Exception(f"Failed to load template: {e}")

        draw = ImageDraw.Draw(template)

        # 2. Получить оценки из БД
        grades = self.grade_repo.get_student_grades(
            student_name=student_name,
            start_date=period_start.strftime('%Y-%m-%d'),
            end_date=period_end.strftime('%Y-%m-%d')
        )

        print(f"[INFO] Found {len(grades)} grades")

        if not grades:
            # Создать пустой табель с надписью
            self._draw_empty_card(draw, student_name, class_name, period_start, period_end)
        else:
            # 3. Определить уникальные даты
            all_dates = sorted(list(set(g['date'] for g in grades)))
            selected_dates = self._select_dates_for_display(all_dates, max_cols=7)

            print(f"[INFO] Selected dates: {selected_dates}")

            # 4. Сгруппировать оценки
            grades_by_subject_date = self._group_grades_by_subject_and_date(grades)

            # 5. Наложить текст на шаблон
            self._draw_header(draw, student_name, class_name, period_start, period_end)
            self._draw_dates(draw, selected_dates)
            self._draw_grades(draw, grades_by_subject_date, selected_dates)

            # 6. Средний балл
            avg = self._calculate_average_for_period(grades)
            self._draw_average(draw, avg)

        # 7. Сохранить изображение
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = student_name.replace(' ', '_')
        filename = f"{safe_name}_{timestamp}.png"
        output_path = self.output_dir / filename

        template.save(output_path)
        print(f"[INFO] Grade card saved to: {output_path}")

        return str(output_path)

    def _select_dates_for_display(self, all_dates: List[str], max_cols: int = 7) -> List[str]:
        """
        Выбирает даты для отображения в табеле

        Если дат больше max_cols, выбирает равномерно распределенные даты

        Args:
            all_dates: Список всех дат (отсортированный)
            max_cols: Максимальное количество колонок

        Returns:
            Список выбранных дат
        """
        if len(all_dates) <= max_cols:
            return all_dates

        # Равномерная выборка
        step = len(all_dates) / max_cols
        selected = [all_dates[int(i * step)] for i in range(max_cols)]
        return selected

    def _group_grades_by_subject_and_date(self, grades: List[Dict]) -> Dict:
        """
        Группирует оценки по предметам и датам

        Args:
            grades: Список оценок из БД

        Returns:
            {
                'Математика': {
                    '2026-01-15': ['5', '4'],
                    '2026-01-22': ['5'],
                },
                ...
            }
        """
        result = {}
        for grade_entry in grades:
            subject = self._normalize_subject(grade_entry['subject'])
            date = grade_entry['date']
            grade = grade_entry['grade']

            if subject not in result:
                result[subject] = {}
            if date not in result[subject]:
                result[subject][date] = []

            result[subject][date].append(grade)

        return result

    def _normalize_subject(self, subject: str) -> str:
        """
        Нормализует название предмета для сопоставления с шаблоном

        Args:
            subject: Название предмета из БД

        Returns:
            Нормализованное название предмета
        """
        return SUBJECT_MAPPING.get(subject, subject)

    def _get_grade_color(self, grade: str) -> tuple:
        """
        Возвращает RGB цвет для оценки

        Args:
            grade: Оценка

        Returns:
            Кортеж RGB (r, g, b)
        """
        return GRADE_COLORS.get(grade, (0, 0, 0))  # По умолчанию черный

    def _calculate_average_for_period(self, grades: List[Dict]) -> float:
        """
        Рассчитывает средний балл за период

        Args:
            grades: Список оценок

        Returns:
            Средний балл
        """
        numeric_grades = [g['grade'] for g in grades if g['grade'] in ['2', '3', '4', '5']]
        return calculate_average(numeric_grades)

    def _draw_header(self, draw: ImageDraw.Draw, student_name: str, class_name: str,
                    period_start: date, period_end: date):
        """
        Рисует заголовок табеля (ФИО, класс, период)

        Note: Координаты могут потребовать настройки
        """
        # Заголовок будем рисовать в верхней части (над таблицей)
        # Примерные координаты - могут потребоваться корректировки
        header_text = f"{student_name}, {class_name}"
        period_text = f"{period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}"

        # Рисуем заголовок (координаты примерные, нужна калибровка)
        # draw.text((10, 10), header_text, fill=(0, 0, 0), font=self.font_title)
        # draw.text((10, 30), period_text, fill=(0, 0, 0), font=self.font_dates)

    def _draw_dates(self, draw: ImageDraw.Draw, dates: List[str]):
        """
        Рисует даты в заголовок таблицы

        Args:
            draw: Объект для рисования
            dates: Список дат в формате YYYY-MM-DD
        """
        x = TEMPLATE_COORDS['header_dates_start_x']
        y = TEMPLATE_COORDS['header_dates_y']
        cell_width = TEMPLATE_COORDS['header_date_width']

        for i, date_str in enumerate(dates):
            # Форматировать дату в ДД.ММ
            formatted_date = format_date(date_str, '%Y-%m-%d', '%d.%m')

            # Вычислить позицию
            date_x = x + (i * cell_width)

            # Центрировать текст в ячейке
            bbox = draw.textbbox((0, 0), formatted_date, font=self.font_dates)
            text_width = bbox[2] - bbox[0]
            centered_x = date_x + (cell_width - text_width) // 2

            # Рисовать дату
            draw.text((centered_x, y), formatted_date, fill=(0, 0, 0), font=self.font_dates)

    def _draw_grades(self, draw: ImageDraw.Draw, grades_by_subject: Dict, dates: List[str]):
        """
        Рисует оценки в ячейки таблицы

        Args:
            draw: Объект для рисования
            grades_by_subject: Оценки, сгруппированные по предметам и датам
            dates: Список дат для отображения
        """
        x_start = TEMPLATE_COORDS['grades_start_x']
        y_start = TEMPLATE_COORDS['grades_start_y']
        cell_width = TEMPLATE_COORDS['cell_width']
        cell_height = TEMPLATE_COORDS['cell_height']

        for row_idx, subject in enumerate(SUBJECT_ORDER):
            if subject not in grades_by_subject:
                continue  # Предмет не найден у ученика

            subject_grades = grades_by_subject[subject]

            for col_idx, date_str in enumerate(dates):
                if date_str not in subject_grades:
                    continue  # Нет оценки на эту дату

                # Получить оценки на эту дату
                grades_list = subject_grades[date_str]

                # Если несколько оценок, взять первую (или объединить через запятую)
                if len(grades_list) == 1:
                    grade_text = grades_list[0]
                else:
                    grade_text = ', '.join(grades_list)

                # Вычислить позицию ячейки
                cell_x = x_start + (col_idx * cell_width)
                cell_y = y_start + (row_idx * cell_height)

                # Получить цвет оценки
                color = self._get_grade_color(grades_list[0])

                # Центрировать текст в ячейке
                bbox = draw.textbbox((0, 0), grade_text, font=self.font_grades)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                centered_x = cell_x + (cell_width - text_width) // 2
                centered_y = cell_y + (cell_height - text_height) // 2

                # Рисовать оценку с цветом
                draw.text((centered_x, centered_y), grade_text, fill=color, font=self.font_grades)

    def _draw_average(self, draw: ImageDraw.Draw, average: float):
        """
        Рисует средний балл в поле "I п/г"

        Args:
            draw: Объект для рисования
            average: Средний балл
        """
        if average == 0:
            return  # Не рисовать если нет оценок

        avg_text = f"{average:.2f}"

        x = TEMPLATE_COORDS['average_x']
        y = TEMPLATE_COORDS['average_y']

        # Центрировать текст
        bbox = draw.textbbox((0, 0), avg_text, font=self.font_grades)
        text_width = bbox[2] - bbox[0]
        centered_x = x - text_width // 2

        draw.text((centered_x, y), avg_text, fill=(0, 0, 0), font=self.font_grades)

    def _draw_empty_card(self, draw: ImageDraw.Draw, student_name: str, class_name: str,
                        period_start: date, period_end: date):
        """
        Рисует пустой табель с надписью "Оценок за период нет"

        Args:
            draw: Объект для рисования
            student_name: ФИО ученика
            class_name: Класс
            period_start: Начало периода
            period_end: Конец периода
        """
        # Рисуем заголовок
        self._draw_header(draw, student_name, class_name, period_start, period_end)

        # Надпись в центре таблицы
        empty_text = "Оценок за период нет"
        bbox = draw.textbbox((0, 0), empty_text, font=self.font_title)
        text_width = bbox[2] - bbox[0]

        # Центр изображения (примерно)
        img_width = 1200
        centered_x = (img_width - text_width) // 2
        centered_y = 250

        draw.text((centered_x, centered_y), empty_text, fill=(100, 100, 100), font=self.font_title)
