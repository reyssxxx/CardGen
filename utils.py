from data_manage import *
import sqlite3
import json
from datetime import datetime, timedelta
from collections import defaultdict
from playwright.sync_api import sync_playwright


def get_greeting(user_id: int, username: str = None) -> str:
    user = get_user(user_id)
    name = user[0].split()[-1]
    
    if str(user_id) in ADMINS:
        return f'Здравствуйте, {name}.\nВы — администратор бота.\n\nПидорович соси'
    elif user[-1]:
        subject = get_teacher(username)[1]
        return f'Здравствуйте, {name}.\nВаш предмет — {subject}.\n\n/photo — внести фотографию журнала'
    else:
        return f'Здравствуй, {name}.\n\n/getcard — получить табель текущей успеваемости'


def generate_html(full_name: str, class_name: str, subjects: list, 
                   periods: list, grades_by_subject: dict) -> str:
    """Генерирует HTML-код табеля успеваемости."""
    
    html = f"""<!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Arial', sans-serif;
                background: #ffffff;
                width: 1200px;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            
            .container {{
                width: 1200px;
                background: white;
                border: 3px solid #1e40af;
                overflow: hidden;
            }}
            
            .header {{
                background: #1e40af;
                color: white;
                padding: 25px 40px;
                border-bottom: 3px solid #1e3a8a;
            }}
            
            .header-top {{
                text-align: center;
                margin-bottom: 15px;
            }}
            
            .lyceum {{
                font-size: 28px;
                font-weight: bold;
                letter-spacing: 1px;
                margin-bottom: 5px;
            }}
            
            .header h1 {{
                font-size: 24px;
                font-weight: normal;
                margin-top: 5px;
            }}
            
            .student-info {{
                display: flex;
                justify-content: space-between;
                font-size: 18px;
                margin-top: 15px;
                padding-top: 15px;
                border-top: 1px solid rgba(255,255,255,0.3);
            }}
            
            .student-info .name {{
                font-weight: bold;
            }}
            
            .student-info .class {{
                font-weight: bold;
            }}
            
            .content {{
                padding: 0;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 16px;
            }}
            
            th {{
                background: #3b82f6;
                color: white;
                padding: 12px 8px;
                text-align: center;
                font-weight: 600;
                border: 1px solid #2563eb;
                font-size: 16px;
            }}
            
            th:first-child {{
                text-align: left;
                padding-left: 15px;
                width: 280px;
            }}
            
            td {{
                padding: 10px 8px;
                text-align: center;
                border: 1px solid #bfdbfe;
                font-size: 16px;
            }}
            
            td:first-child {{
                text-align: left;
                padding-left: 15px;
                font-weight: 500;
                background: #eff6ff;
                color: #1e40af;
                border-right: 2px solid #93c5fd;
                font-size: 17px;
            }}
            
            tr:nth-child(even) td:not(:first-child) {{
                background-color: #f8fafc;
            }}
            
            .grade {{
                display: inline-block;
                font-weight: 600;
                color: #1e40af;
                letter-spacing: 3px;
                font-size: 18px;
            }}
            
            .average {{
                display: inline-block;
                font-weight: 700;
                color: #1e40af;
                font-size: 18px;
            }}
            
            .empty-cell {{
                color: #cbd5e0;
                font-size: 16px;
            }}
            
            .footer {{
                text-align: center;
                padding: 10px;
                margin-top: -1px;
                color: #64748b;
                font-size: 13px;
                background: #f1f5f9;
                border-top: 2px solid #1e40af;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-top">
                    <div class="lyceum">ЛИЦЕЙ ЮФУ</div>
                    <h1>Табель успеваемости</h1>
                </div>
                <div class="student-info">
                    <div class="name">Ученик: {full_name}</div>
                    <div class="class">Класс: {class_name}</div>
                </div>
            </div>
            
            <div class="content">
                <table>
                    <thead>
                        <tr>
                            <th>Предмет</th>"""
        
    for period in periods:
        period_str = period.strftime("%d.%m")
        html += f"\n                        <th>{period_str}</th>"
    
    html += "\n                        <th>Ср. балл</th>"
    
    html += """
                    </tr>
                </thead>
                <tbody>"""
    
    for subject in subjects:
        html += f"\n                    <tr>\n                        <td>{subject}</td>"
        
        for period in periods:
            period_key = period.strftime("%d.%m")
            grades = grades_by_subject[subject].get(period_key, [])
            
            if grades:
                # Разбиваем оценки на отдельные цифры для отображения
                all_digits = []
                for grade_str in grades:
                    all_digits.extend(list(grade_str))
                grades_str = ' '.join(all_digits)
                html += f"\n                        <td><span class=\"grade\">{grades_str}</span></td>"
            else:
                html += "\n                        <td><span class=\"empty-cell\">—</span></td>"
        
        # Добавляем средний балл
        all_grades = []
        for period_grades in grades_by_subject[subject].values():
            for grade_str in period_grades:
                for digit in grade_str:
                    if digit.isdigit():
                        all_grades.append(int(digit))
        
        if all_grades:
            average = round(sum(all_grades) / len(all_grades), 2)
            html += f"\n                        <td><span class=\"average\">{average}</span></td>"
        else:
            html += "\n                        <td><span class=\"empty-cell\">—</span></td>"
        
        html += "\n                    </tr>"
    
    html += """
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            Сгенерировано: """ + datetime.now().strftime("%d.%m.%Y %H:%M") + """
        </div>
    </div>
</body>
</html>""" 
    return html


def generate_grade(telegram_id: int, db_path: str = "data/database.db", config_path: str = "data/config.json", students_path: str = "data/students.json", output_file: str = "табель.png") -> str:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT full_name, class_name FROM users WHERE id = ?", (telegram_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        print(f"Ученик с ID {telegram_id} не найден")
    full_name, class_name = result

    cursor.execute("""
        SELECT subject, date, grade 
        FROM grades 
        WHERE student = ?
        ORDER BY date
    """, (full_name,))

    grades_data = cursor.fetchall()
    conn.close()
    if not grades_data:
        print(f"Оценки для ученика {full_name} не найдены")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        subjects = config['subjects']
    
    now = datetime.now()
    start_year = now.year if now.month >= 9 else now.year - 1
    start_date = datetime(start_year, 9, 1)
    
    periods = []
    current_period = start_date
    end_date = datetime.now()
    while current_period <= end_date:
        periods.append(current_period)
        current_period += timedelta(weeks=2)
    
    grades_by_subject = defaultdict(lambda: defaultdict(list))
    for subject, date_str, grade in grades_data:
        grade_date = None
        for i in ("%d.%m.%y", "%d.%m.%Y"):
            grade_date = datetime.strptime(date_str, i)
            break
        if not grade_date:
            continue
        for i, period_start in enumerate(periods):
            period_end = periods[i + 1] if i < len(periods) - 1 else datetime.now()
            if period_start <= grade_date < period_end:
                period_key = period_start.strftime("%d.%m")
                grades_by_subject[subject][period_key].append(str(grade))
                break
    
    html = generate_html(full_name, class_name, subjects, periods, grades_by_subject)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1200, 'height': 800})
        page.set_content(html)
        page.screenshot(path=output_file, full_page=True)
        browser.close()
    print(f"Табель успешно создан: {output_file}")
    return output_file


generate_grade(telegram_id=12345, output_file = f"табель_{full_name}.png") 