"""
XML Generator for Diploma Application (CyberDiploma format).
Converts pivot tables and student data into XML format.
"""

import io
import re
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

# CyberDiploma grade codes: 2-5 are marks, 6 is "зачтено" and 7 is
# "не выполнял", a placeholder used until the real grade is known.
GRADE_CODES = {2, 3, 4, 5, 6, 7}

REQUIRED_STUDENT_COLUMNS = [
    'ФИО', 'ДатаРожд', 'НаименованиеДокПредОбр', 'ГодДокПредОбр',
    'ТемаВКР', 'НомерПротоколаГэк', 'ДатаРешенияГэк', 'ОценкаВКР',
]

# ГИА rows of the pivot template. The thesis grade comes from the student
# info file; the state exam row fills the «Государственный экзамен» entry.
THESIS_ROW_PREFIX = 'выполнение и защита выпускной квалификационной работы'
STATE_EXAM_ROW_PREFIX = 'подготовка к сдаче и сдача государственного экзамена'
STATE_EXAM_NAME = 'Государственный экзамен'

# Year of the previous document that is not known yet, like grade 7.
YEAR_PLACEHOLDER = '1111'

# Latin letters that look like Cyrillic ones. Used only to match names.
LOOKALIKES = str.maketrans('AaBCcEeHKMOoPpTXxYyËë', 'АаВСсЕеНКМОоРрТХхУуЁё')

MIXED_SCRIPT_WORD = re.compile(r'\b(?=\w*[А-Яа-яЁё])(?=\w*[A-Za-zÀ-ÿ])\w+\b')

DIRECTION_PATTERN = re.compile(r'^(\d{2}\.(\d{2})\.\d{2})\s+(\S.*)$')

# Direction code level (the middle pair of digits) and the qualification it
# implies. Specialist qualifications have program-specific names, so the
# check covers bachelor and master programs only.
QUALIFICATION_BY_LEVEL = {'03': 'бакалавр', '04': 'магистр'}


class DataValidationError(ValueError):
    """Problems in the uploaded data, reported together."""

    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__(
            f'Найдено ошибок в исходных данных: {len(problems)}\n'
            + '\n'.join(f'- {problem}' for problem in problems)
        )


def is_blank(value) -> bool:
    """True for empty cells, including pandas NaN/NaT and their text forms."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ('', 'nan', 'nat', 'none')
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def text_value(value) -> str:
    """Cell as text, without float artefacts such as '3.0'."""
    if is_blank(value):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return ' '.join(str(value).split())


def date_only(value, field_name: str) -> str:
    """Return an Excel date value without its time component."""
    if is_blank(value):
        return ''
    if pd.api.types.is_number(value) and not pd.api.types.is_bool(value):
        raise ValueError(
            f'{field_name}: дата записана числом ({text_value(value)}), '
            'установите для ячейки формат «Дата»'
        )
    parsed = pd.to_datetime(value, errors='coerce', dayfirst=True)
    if pd.isna(parsed):
        raise ValueError(f'{field_name}: не удалось распознать дату «{value}»')
    return parsed.date().isoformat()


def checked_date(value, field_name: str, first_year: int, last_year: int) -> str:
    """ISO date that lies within the given years."""
    iso = date_only(value, field_name)
    if not iso:
        raise ValueError(f'{field_name}: не заполнено')
    year = int(iso[:4])
    if not first_year <= year <= last_year:
        raise ValueError(
            f'{field_name}: год {year} вне допустимого диапазона '
            f'{first_year}–{last_year}'
        )
    return iso


def grade_code(value):
    """CyberDiploma grade code, or None when the value is not one."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not number.is_integer() or int(number) not in GRADE_CODES:
        return None
    return int(number)


def mixed_script_words(text: str) -> List[str]:
    """Words that mix Cyrillic and Latin letters, e.g. a Latin Ë in a surname."""
    return MIXED_SCRIPT_WORD.findall(text)


def name_key(text) -> str:
    """Case-, ё- and lookalike-insensitive form of a name for matching."""
    return ' '.join(
        str(text).translate(LOOKALIKES).lower().replace('ё', 'е').split()
    )


def initials(text: str) -> List[str]:
    """First letters of the words in 'И. О.', 'И.О.' or 'Иван Олегович'."""
    return [word[0] for word in re.findall(r'[^\W\d_]+', text)]


def person_key(last: str, first: str, middle: str) -> Tuple[str, str, str]:
    """Surname plus first-name and patronymic initials."""
    return (
        name_key(last),
        name_key(first)[:1],
        name_key(middle)[:1],
    )


def column_key(header) -> Tuple[str, str, str]:
    """Key of a pivot column headed 'Фамилия И. О.'."""
    words = name_key(header).split(' ', 1)
    letters = initials(words[1]) if len(words) > 1 else []
    return (
        words[0],
        letters[0] if letters else '',
        letters[1] if len(letters) > 1 else '',
    )


def keys_compatible(column: Tuple[str, str, str], person: Tuple[str, str, str]) -> bool:
    """Same surname; an initial missing on either side matches anything."""
    return column[0] == person[0] and all(
        a == b or not a or not b for a, b in zip(column[1:], person[1:])
    )


def split_full_name(full_name: str) -> Tuple[str, str, str]:
    """Split 'Фамилия Имя Отчество'; a patronymic may span words ('… оглы')."""
    parts = full_name.split()
    if len(parts) < 2:
        raise ValueError(f'ФИО «{full_name}»: нужны как минимум фамилия и имя')
    return parts[0], parts[1], ' '.join(parts[2:])


def add_element(parent: ET.Element, tag: str, value) -> ET.Element:
    """Add XML element with text value."""
    el = ET.SubElement(parent, tag)
    el.text = text_value(value)
    return el


class DiplomaXMLGenerator:
    """Generator for CyberDiploma XML files."""

    def __init__(self, config: Dict):
        """
        Initialize generator with configuration.

        Args:
            config: Dictionary with parameters like edu_term, qualification, etc.
        """
        self.config = config
        self.validate_config()

    def validate_config(self):
        """Validate required configuration parameters."""
        required = [
            'edu_term', 'qualification', 'edu_form', 'direction', 'profile',
            'edu_progr_vol', 'edu_progr_vol_contact',
            'pract_total_z_e', 'gia_z_e', 'gek_chairman',
            'state_exam_credits'  # Manual value for state exam
        ]

        missing = [k for k in required if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config parameters: {missing}")

        problems = []
        direction = ' '.join(str(self.config['direction'] or '').split())
        profile = ' '.join(str(self.config['profile'] or '').split())
        match = DIRECTION_PATTERN.match(direction)
        if not match:
            problems.append(
                'Направление подготовки: нужен код вида 09.03.02 и через пробел '
                f'наименование из шапки учебного плана, получено «{direction}»'
            )
        else:
            self.direction_code, level, self.direction_name = match.groups()
            expected = QUALIFICATION_BY_LEVEL.get(level)
            qualification = str(self.config['qualification']).strip().lower()
            if expected and qualification != expected:
                problems.append(
                    f'Направление {self.direction_code} относится к уровню '
                    f'«{expected}», а выбрана квалификация «{qualification}»'
                )
            if name_key(profile) == name_key(self.direction_name):
                problems.append(
                    'Профиль совпадает с наименованием направления подготовки. '
                    'В поле направления укажите наименование из шапки учебного '
                    'плана (например, «09.03.02 ИНФОРМАЦИОННЫЕ СИСТЕМЫ И '
                    'ТЕХНОЛОГИИ»), а профиль — в отдельном поле'
                )
        if not profile:
            problems.append('Профиль (направленность) образовательной программы не указан')
        elif DIRECTION_PATTERN.match(profile):
            problems.append(
                f'Профиль «{profile}» указан с кодом направления: '
                'в поле профиля нужно только его наименование'
            )
        if problems:
            raise DataValidationError(problems)
        self.profile = profile

    def match_students(
        self,
        people: List[Tuple[int, str, Tuple[str, str, str]]],
        columns: List,
        problems: List[str],
    ) -> Dict[int, object]:
        """
        Map each student to exactly one pivot column.

        A student without a column, a student with several candidate columns
        and a column claimed by several students are all reported as problems,
        so no student is silently dropped or given another student's grades.
        """
        keys = {column: column_key(column) for column in columns}
        mapping = {}
        for row, label, person in people:
            exact = [c for c, k in keys.items() if k == person]
            candidates = exact or [c for c, k in keys.items() if keys_compatible(k, person)]
            if len(candidates) == 1:
                mapping[row] = candidates[0]
            elif not candidates:
                problems.append(f'{label}: нет колонки с оценками в сводной таблице')
            else:
                names = ', '.join(f'«{c}»' for c in candidates)
                problems.append(f'{label}: подходит несколько колонок сводной — {names}')
        claimed = {}
        for row, column in mapping.items():
            claimed.setdefault(column, []).append(row)
        labels = {row: label for row, label, _ in people}
        for column, rows in claimed.items():
            if len(rows) > 1:
                who = ', '.join(labels[r] for r in rows)
                problems.append(
                    f'Колонка «{column}» сводной подходит нескольким студентам: {who}'
                )
                for r in rows:
                    del mapping[r]
        unused = [c for c in columns if c not in claimed]
        if unused:
            logger.warning(
                'Pivot columns without a student in the info file: %s', unused
            )
        return mapping

    def generate_xml(
        self,
        df_disciplines: pd.DataFrame,
        df_students: pd.DataFrame
    ) -> str:
        """
        Generate XML file for diploma application.

        Args:
            df_disciplines: DataFrame with disciplines and scores
            df_students: DataFrame with student information

        Returns:
            XML string

        Raises:
            DataValidationError: listing every problem found in the input
        """
        problems: List[str] = []
        missing_columns = [
            c for c in REQUIRED_STUDENT_COLUMNS if c not in df_students.columns
        ]
        if missing_columns:
            raise DataValidationError(
                [f'В файле сведений о студентах нет колонок: {", ".join(missing_columns)}']
            )

        this_year = date.today().year
        students = []
        people = []
        for index, row in df_students.iterrows():
            if all(is_blank(value) for value in row.values):
                continue
            line = f'строка {index + 2} файла сведений'
            full_name = text_value(row['ФИО'])
            if not full_name:
                problems.append(f'{line}: не заполнено ФИО')
                continue
            label = f'{full_name} ({line})'
            mixed = mixed_script_words(full_name)
            if mixed:
                problems.append(
                    f'{label}: в ФИО смешаны латинские и русские буквы '
                    f'({", ".join(mixed)}), исправьте файл'
                )
            try:
                last, first, middle = split_full_name(full_name)
            except ValueError as err:
                problems.append(f'{label}: {err}')
                continue
            student = {
                'label': label,
                'Фамилия': last,
                'Имя': first,
                'Отчество': middle,
            }
            for field, first_year, last_year in (
                ('ДатаРожд', 1920, this_year - 14),
                ('ДатаРешенияГэк', 2000, this_year + 1),
            ):
                try:
                    student[field] = checked_date(row[field], field, first_year, last_year)
                except ValueError as err:
                    problems.append(f'{label}: {err}')
            year = text_value(row['ГодДокПредОбр'])
            if year == YEAR_PLACEHOLDER:
                logger.info('ГодДокПредОбр is the placeholder %s', YEAR_PLACEHOLDER)
            elif not re.fullmatch(r'\d{4}', year) or not 1950 <= int(year) <= this_year:
                problems.append(
                    f'{label}: ГодДокПредОбр должен быть годом из четырёх цифр '
                    f'не позже {this_year} или заглушкой {YEAR_PLACEHOLDER}, '
                    f'получено «{year}»'
                )
            student['ГодДокПредОбр'] = year
            for field in ('НаименованиеДокПредОбр', 'НомерПротоколаГэк', 'ТемаВКР'):
                student[field] = text_value(row[field])
                if not student[field]:
                    problems.append(f'{label}: не заполнено поле {field}')
            thesis_grade = grade_code(row['ОценкаВКР'])
            if thesis_grade is None:
                problems.append(
                    f'{label}: ОценкаВКР «{text_value(row["ОценкаВКР"])}» — '
                    'допустимы коды 2–7'
                )
            student['ОценкаВКР'] = thesis_grade
            students.append((index, student))
            people.append((index, label, person_key(last, first, middle)))

        mapping = self.match_students(people, list(df_disciplines.columns), problems)

        root = ET.Element("ФайлОбменаКиберДиплом", Версия="3.5.1")
        students_el = ET.SubElement(root, "Студенты")
        row_problems = []

        for index, student in students:
            if index not in mapping:
                continue
            disciplines = df_disciplines[mapping[index]]
            label = student['label']
            student_el = ET.SubElement(students_el, "Студент")
            logger.info("1. Parse student: %s", student['Фамилия'])

            # Add student info
            for col in ['Фамилия', 'Имя', 'Отчество', 'ДатаРожд',
                        'НаименованиеДокПредОбр', 'ГодДокПредОбр',
                        'ДатаРешенияГэк', 'НомерПротоколаГэк']:
                add_element(student_el, col, student.get(col, ''))
            logger.info("2. Added student info for: %s", student['Фамилия'])
            # Add state exams
            exams_el = ET.SubElement(student_el, "Госэкзамены")
            exams_head = ET.SubElement(exams_el, "Заголовок")
            add_element(exams_head, 'ЗачЕд', self.config['gia_z_e'])

            # The state exam goes before the thesis, as on the supplement
            for row_name, rate in disciplines.items():
                if is_blank(rate) or not text_value(row_name).lower().startswith(
                    STATE_EXAM_ROW_PREFIX
                ):
                    continue
                grade = grade_code(rate)
                if grade is None:
                    problems.append(
                        f'{label}: «{STATE_EXAM_NAME}» — недопустимая оценка '
                        f'«{text_value(rate)}», допустимы коды 2–7'
                    )
                    continue
                state_exam_el = ET.SubElement(exams_el, "Госэкзамен")
                add_element(state_exam_el, 'Наименование', STATE_EXAM_NAME)
                add_element(state_exam_el, 'Оценка', grade)

            # Add thesis exam
            exam_el = ET.SubElement(exams_el, "Госэкзамен")
            add_element(
                exam_el,
                'Наименование',
                f'Выпускная квалификационная работа "{student["ТемаВКР"]}"'
            )
            add_element(exam_el, 'Оценка', student['ОценкаВКР'])
            logger.info("3. Added state exam info for: %s", student['Фамилия'])
            # Add program volume
            vol_el = ET.SubElement(student_el, 'ОбъемОбрПрограммы')
            add_element(vol_el, 'ЗачЕд', self.config['edu_progr_vol'])

            vol_el_hours = ET.SubElement(student_el, 'ОбъемАудиторныхЧасов')
            add_element(vol_el_hours, 'ЧасНед', self.config['edu_progr_vol_contact'])
            logger.info("4. Added program volume info for: %s", student['Фамилия'])
            # Add qualification and other info
            add_element(student_el, 'Квалификация', self.config['qualification'])
            add_element(student_el, 'СрокОбучения', self.config['edu_term'])
            add_element(student_el, 'ПредседательГэк', self.config['gek_chairman'])
            add_element(student_el, 'НаименованиеСпец', self.direction_name)
            add_element(student_el, 'КодСпец', self.direction_code)
            logger.info("5. Added qualification and program info for: %s", student['Фамилия'])
            # Add extra info
            extra_info_element = ET.SubElement(student_el, "ДополнительныеСведения")
            add_element(
                extra_info_element,
                'ДопСвед',
                f'Направленность (профиль) образовательной программы: "{self.profile}"'
            )
            add_element(
                extra_info_element,
                'ДопСвед',
                f'Форма обучения: {self.config["edu_form"]}'
            )

            # Add disciplines, practices, courseworks, electives
            courseworks_el = ET.SubElement(student_el, "Курсовые")
            practics_el = ET.SubElement(student_el, "Практики")
            practics_head_el = ET.SubElement(practics_el, "Заголовок")
            add_element(practics_head_el, 'ЗачЕд', self.config['pract_total_z_e'])

            facults_el = ET.SubElement(student_el, "Факультативы")
            disciplines_el = ET.SubElement(student_el, "Дисциплины")

            logger.info("6. Processing disciplines for: %s", student['Фамилия'])

            graded = 0
            # Process each discipline
            for discipline_full, rate in disciplines.items():
                if is_blank(rate):
                    continue
                discipline_full = text_value(discipline_full)
                if discipline_full.lower().startswith(
                    (THESIS_ROW_PREFIX, STATE_EXAM_ROW_PREFIX)
                ):
                    continue  # ГИА rows are handled above

                # Parse discipline info
                parts = discipline_full.split('_')
                if len(parts) < 3:
                    row_problems.append(
                        f'Строка сводной «{discipline_full}» содержит оценки, '
                        'но в названии нет типа и з.е. (ожидается '
                        '«Название_дисциплина_3»), оценки не попадут в XML'
                    )
                    continue

                discipline_name = parts[0]
                discipline_type = parts[1]
                graded += 1

                raw_rate, rate = rate, grade_code(rate)
                if rate is None:
                    problems.append(
                        f'{label}: «{discipline_name}» — недопустимая оценка '
                        f'«{text_value(raw_rate)}», допустимы коды 2–7'
                    )
                    continue

                try:
                    r_units = int(parts[2])
                except (ValueError, IndexError):
                    row_problems.append(
                        f'Строка сводной «{discipline_full}»: з.е. должны быть целым числом'
                    )
                    continue

                mixed = mixed_script_words(discipline_name)
                if mixed:
                    row_problems.append(
                        f'Строка сводной «{discipline_full}»: в названии смешаны '
                        f'латинские и русские буквы ({", ".join(mixed)})'
                    )

                # Add to appropriate section
                if discipline_type == 'дисциплина':
                    discipline_el = ET.SubElement(disciplines_el, "Дисциплина")
                    add_element(discipline_el, 'Наименование', discipline_name)
                    add_element(discipline_el, 'Оценка', rate)
                    add_element(discipline_el, 'ЗачЕд', r_units)

                elif discipline_type == 'практика':
                    practic_el = ET.SubElement(practics_el, "Практика")
                    add_element(practic_el, 'Наименование', discipline_name)
                    add_element(practic_el, 'Оценка', rate)
                    add_element(practic_el, 'ЗачЕд', r_units)

                elif discipline_type == 'курсовая':
                    coursework_el = ET.SubElement(courseworks_el, "КурсоваяРабота")
                    add_element(coursework_el, 'Наименование', discipline_name)
                    add_element(coursework_el, 'Оценка', rate)

                elif discipline_type == 'факультатив':
                    facult_el = ET.SubElement(facults_el, "Факультатив")
                    add_element(facult_el, 'Наименование', discipline_name)
                    add_element(facult_el, 'Оценка', rate)
                    add_element(facult_el, 'ЗачЕд', r_units)

                elif discipline_type == 'госэкзамен':
                    exam_el2 = ET.SubElement(exams_el, "Госэкзамен")
                    add_element(exam_el2, 'Наименование', discipline_name)
                    add_element(exam_el2, 'Оценка', rate)

                else:
                    row_problems.append(
                        f'Строка сводной «{discipline_full}»: неизвестный тип '
                        f'«{discipline_type}» (ожидается дисциплина, практика, '
                        'курсовая, факультатив или госэкзамен)'
                    )

            if not graded:
                problems.append(f'{label}: в сводной нет ни одной оценки')
            logger.info("Finished processing disciplines for: %s", student['Фамилия'])

        problems.extend(dict.fromkeys(row_problems))
        if problems:
            raise DataValidationError(problems)

        # Convert to string
        tree = ET.ElementTree(root)
        output = io.BytesIO()
        tree.write(output, encoding='utf-8', xml_declaration=True)
        return output.getvalue().decode('utf-8')
