"""
Core parsing logic for student score XLSX files.
Handles data extraction, normalization, and discipline matching.
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

from .curriculum import find_credits, plan_credits
from .excel import WorkbookError, open_workbook

logger = logging.getLogger(__name__)

# Layout of a statement sheet exported from «Деканат» (0-based, pandas rows
# start after the first sheet row): the student name is the header of column E,
# column titles are on sheet row 7.
STUDENT_NAME_COLUMN = 4
TITLES_ROW = 5
REQUIRED_TITLES = ('наименование предмета', 'часы учр')

# Pivot row label: «Название_тип_з.е.»
LABEL = re.compile(r'^(.*)_(дисциплина|практика|факультатив|курсовая)_(\d+)$')
HOURS_PER_CREDIT = 36


def clean_text(text) -> str:
    """
    Cleans input text by keeping only letters (Latin and Cyrillic) and spaces.
    Collapses multiple spaces and strips leading/trailing spaces.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text string
    """
    if not isinstance(text, str):
        return text
    # Keep only letters (Latin, Cyrillic) and spaces
    cleaned = re.sub(r'[^a-zA-Zа-яА-ЯёЁ\s]', '', text)
    # Collapse multiple spaces and strip
    return ' '.join(cleaned.split())

def credits_of(hours: float) -> int:
    """Credits for hours; 106 h of a 3-credit discipline round to 3."""
    return int(hours / HOURS_PER_CREDIT + 0.5)


def row_kind(row) -> Optional[str]:
    """Form of control of a statement row, as the pivot has always read it."""
    if pd.notna(row.get('зачет')):
        return 'зачет'
    if 'практика' in str(row['наименование предмета']).lower():
        return 'практика'  # a practice row may still wait for its grade
    if pd.notna(row.get('экзамен')):
        return 'экзамен'
    if pd.notna(row.get('курсовой')):
        return 'курсовой'
    return None


def semester_records(df: pd.DataFrame) -> List[dict]:
    """
    One record per discipline and kind of work for one student's statement.

    A discipline taught over several semesters has a row per semester (B-31).
    Its credits are the hours of all its rows, course work included, over 36;
    its grade is the last exam grade, or the last grade if there was no exam.
    Course work keeps its own record.

    Returns:
        Dicts with the pivot label, grade, hours and number of ungraded rows
    """
    rows_by_subject: Dict[str, list] = {}
    for _, row in df.iterrows():
        rows_by_subject.setdefault(row['наименование предмета'], []).append(row)

    records = []
    for subject, rows in rows_by_subject.items():
        kinds = [row_kind(r) for r in rows]
        study = [r for r, k in zip(rows, kinds) if k in ('зачет', 'экзамен', 'практика')]
        works = [r for r, k in zip(rows, kinds) if k == 'курсовой']
        ungraded = kinds.count(None)
        if study:
            exams = [r['экзамен'] for r in study if pd.notna(r.get('экзамен'))]
            tests = [r['зачет'] for r in study if pd.notna(r.get('зачет'))]
            hours = sum(float(r['часы учр']) for r in rows)
            suffix = '_практика_' if 'практика' in str(subject).lower() else '_дисциплина_'
            records.append({
                'label': f'{subject}{suffix}{credits_of(hours)}',
                'grade': exams[-1] if exams else (tests[-1] if tests else np.nan),
                'hours': hours,
                'ungraded': ungraded,
            })
        if works:
            hours = sum(float(r['часы учр']) for r in works)
            records.append({
                'label': f'{subject}_курсовая_{credits_of(hours)}',
                'grade': works[-1]['курсовой'],
                'hours': hours,
                'ungraded': 0,
            })
        if not study and not works:
            # Kept without a type, as before: shows the subject has no grade yet
            records.append({'label': subject, 'grade': np.nan, 'hours': 0, 'ungraded': 0})
    return records


def replace_index_occurrence(df: pd.DataFrame, old: str, new: str, occurrence: int = 0) -> pd.DataFrame:
    """
    Replace a specific occurrence of an index label.
    
    Args:
        df: DataFrame to modify
        old: Index value to replace
        new: New index value
        occurrence: Zero-based occurrence of `old` to replace
        
    Returns:
        Modified DataFrame
        
    Raises:
        ValueError: If the specified occurrence is not found
    """
    idx = df.index.to_list()
    count = 0
    
    for i, v in enumerate(idx):
        if v == old:
            if count == occurrence:
                idx[i] = new
                break
            count += 1
    else:
        raise ValueError(f"Index value {old!r} with occurrence {occurrence} not found")
    
    df.index = idx
    return df

def remove_index_occurrence(obj: pd.DataFrame, value: str, occurrence: int = 0) -> pd.DataFrame:
    """
    Remove exactly one row whose index label equals `value`,
    selecting the `occurrence`-th match (0-based), even if index has duplicates.
    
    Args:
        obj: DataFrame to modify
        value: Index value to remove
        occurrence: Which occurrence to remove among duplicates (0-based)
        
    Returns:
        DataFrame with row removed
        
    Raises:
        ValueError: If the specified occurrence is not found
    """
    if not isinstance(obj, (pd.DataFrame, pd.Series)):
        raise TypeError("obj must be a pandas DataFrame or Series")
    
    # Find positional index of the desired occurrence
    count = 0
    pos_to_drop = None
    for pos, v in enumerate(obj.index):
        if v == value:
            if count == occurrence:
                pos_to_drop = pos
                break
            count += 1
    
    if pos_to_drop is None:
        raise ValueError(f"Index value {value!r} with occurrence {occurrence} not found")
    
    # Drop by position (safe with duplicates)
    result = pd.concat([obj.iloc[:pos_to_drop], obj.iloc[pos_to_drop + 1:]])
    return result

def match_row(orig_name: str, row_name: str) -> Optional[str]:
    """
    Determines if a row from student scores matches an original discipline name.
    
    Args:
        orig_name: Original discipline name from the discipline list
        row_name: Row name from student scores
        
    Returns:
        True if direct match, 'elective' for elective courses, 'kurs' for course work,
        'prefix' for prefix-based matching, False otherwise
    """
    orig_name = orig_name.strip()
    row_base = row_name.split('_')[0].strip()
    
    # Direct match for практика
    if 'практика' in orig_name and 'практика' in row_name:
        if row_name.split(' ')[0] in orig_name:
            return True
    
    # Elective (элективн) match
    if '(' in row_base:
        
        base = row_base.split('(')[0].strip()
        if 'лективн' in orig_name and base in orig_name:
            return 'elective'
        if base in orig_name:
            return True
    
    # Dot match
    if '.' in row_base:
        base = row_base.split('.')[0].strip()
        if base in orig_name:
            return True
    
    # Course work
    if 'курсовая' in row_name:
        return 'kurs'
    
    if 'факультатив' in orig_name and row_base in orig_name:
        return 'facultative'
    
    # Prefix match (for grouped disciplines like "Дисциплина * 3")
    if '*' in orig_name:
        return 'prefix'
    
    # Base match
    if row_base in orig_name:
        return True
    
    return False

def parse_discipline(df_stud_scores: pd.DataFrame, discipline_bytes: bytes) -> pd.DataFrame:
    """
    Matches and fills discipline ratings from df_stud_scores into a new DataFrame
    based on names from the discipline file.
    
    Args:
        df_stud_scores: DataFrame with student scores (from the Dean's list)
        discipline_bytes: Bytes content of the discipline XLSX file (template)
        
    Returns:
        DataFrame with matched disciplines and student scores
    """
    df_origin_names = open_workbook(discipline_bytes, "Список дисциплин").parse(0, header=0)
    clean_cols = [re.sub(r'\s+', '', str(col).lower()) for col in df_origin_names.columns]

    target = 'обязательнаячасть'
    matches = [i for i, col in enumerate(clean_cols) if target in col]
    if not matches:
        raise WorkbookError(
            'Список дисциплин: в первой строке первого листа нет колонки '
            '«Обязательная часть». Под этим заголовком должны идти названия '
            'дисциплин из учебного плана.'
        )
    df_origin_names = df_origin_names.iloc[:, matches[0]].drop(df_origin_names.index[0])
    logger.info("Discipline list has %d rows", len(df_origin_names))

    df_result = pd.DataFrame(index=df_origin_names, columns=df_stud_scores.columns)
    # pivot label -> (name in the discipline list, row label of the statement)
    sources: Dict[str, Tuple[str, str]] = {}
    prefix_base = ''
    count_of_prefix = 0
    old_index = ''

    for orig_index in df_result.index:
        matched = False
        # "Группа * N" in the plan: the next N plan rows belong to the group
        in_group = bool(prefix_base) and count_of_prefix > 0

        if isinstance(orig_index, str) and '*' in orig_index and not in_group:
            logger.info(f"Matched prefix pattern: {orig_index}")
            prefix_base = orig_index.split('*')[0].strip()
            count_of_prefix = int(orig_index.split('*')[1].strip())
            old_index = orig_index
            df_result.loc[orig_index] = ''
            continue

        for row_index, row in df_stud_scores.iterrows():
            if isinstance(orig_index, str) and isinstance(row_index, str):
                match = match_row(orig_index, row_index)
                logger.debug(f"Matching '{orig_index}' with '{row_index}': {match}")
                if match is True:
                    if in_group:
                        # Keep the type and credits suffix of the matched row
                        new_index = f"{prefix_base}. {row_index}"
                        df_result = replace_index_occurrence(df_result, orig_index, new_index)
                        df_result.loc[new_index] = row
                        sources[new_index] = (orig_index, row_index)
                        matched = True
                        break
                    else:
                        df_result.loc[orig_index] = row
                        df_result = replace_index_occurrence(df_result, orig_index, row_index)
                        sources[row_index] = (orig_index, row_index)
                        matched = True
                        break
                        
                elif match == 'elective':
                    logger.info(f"Matched elective: {row_index}")
                    df_result = df_result.rename(index={orig_index: row_index})
                    df_result.loc[row_index] = row
                    df_result.loc[orig_index] = np.nan
                    sources[row_index] = (orig_index, row_index)
                    matched = True
                    break

                elif match == 'facultative':
                    logger.info(f"Matched facultative: {row_index}")
                    new_index = row_index.replace('дисциплина', 'факультатив')
                    df_result = df_result.rename(index={orig_index: new_index})
                    df_result.loc[new_index] = row
                    sources[new_index] = (orig_index, row_index)
                    matched = True
                    break

                elif match == 'kurs':
                    logger.info(f"Matched course work: {row_index}")
                    df_result.loc[row_index] = row

        if in_group:
            count_of_prefix -= 1

        # Clean up prefix handling
        if prefix_base and count_of_prefix == 0:
            df_result = remove_index_occurrence(df_result, old_index)
            prefix_base = ''
            count_of_prefix = 0
            old_index = ''
        
        # Mark unmatched disciplines
        if not matched:
            df_result.loc[orig_index] = ''
    
    df_result.index.name = 'Дисциплины'
    df_result.attrs['sources'] = sources
    return df_result

def statement_layout(name: str, df: pd.DataFrame) -> Tuple[str, list]:
    """
    Check that a statement sheet has the «Деканат» layout.

    Returns:
        Student name and cleaned column titles

    Raises:
        WorkbookError: naming the sheet and what is missing
    """
    where = f'Ведомость, лист «{name}»'
    if df.shape[1] <= STUDENT_NAME_COLUMN or len(df) <= TITLES_ROW:
        raise WorkbookError(
            f'{where}: лист не похож на ведомость «Деканата» '
            '(ожидается ФИО студента в ячейке E1 и заголовки колонок в строке 7)'
        )
    stud_name = df.columns[STUDENT_NAME_COLUMN]
    if not isinstance(stud_name, str) or stud_name.startswith('Unnamed'):
        raise WorkbookError(f'{where}: в ячейке E1 нет ФИО студента')
    titles = [clean_text(val) for val in df.iloc[TITLES_ROW, :]]
    missing = [t for t in REQUIRED_TITLES if t not in titles]
    if missing:
        raise WorkbookError(
            f'{where}: в строке 7 нет колонок '
            + ', '.join(f'«{t}»' for t in missing)
            + '. Ожидается ведомость «Деканата» в обычном макете.'
        )
    return stud_name, titles


def settle_credits(
    report: pd.DataFrame,
    hours: Dict[str, float],
    ungraded: Dict[str, int],
    credits: Optional[Dict[str, float]],
    plan_problem: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Put the curriculum credits into the pivot labels and list what to check.

    Without a readable curriculum, or for a discipline missing from it, the
    credits stay as counted from the statement hours and the row is marked
    for the operator to check (B-31).

    Returns:
        Pivot with corrected labels, and the check table
    """
    sources = report.attrs.get('sources', {})
    labels, checks = [], []
    for label in report.index:
        match = LABEL.match(label) if isinstance(label, str) else None
        if not match or match.group(2) == 'курсовая':
            labels.append(label)
            continue
        name, kind, counted = match.group(1), match.group(2), int(match.group(3))
        listed, statement = sources.get(label, (None, label))
        names = [listed, name] + ([name.split('. ', 1)[1]] if '. ' in name else [])
        planned = find_credits(names, credits) if credits is not None else None
        notes = []
        if planned is not None and float(planned).is_integer():
            final, source = int(planned), 'учебный план'
            if final != counted:
                notes.append(f'по часам ведомости {counted} з.е. — тот ли учебный план?')
        else:
            final, source = counted, 'часы ведомости'
            if credits is None:
                notes.append(plan_problem)
            elif planned is None:
                notes.append('нет в учебном плане')
            else:
                notes.append(f'в учебном плане дробные з.е. ({planned:g})')
            spent = hours.get(statement.replace('_факультатив_', '_дисциплина_'))
            if spent and spent % HOURS_PER_CREDIT:
                notes.append(f'часы ведомости не кратны 36 ({spent:g} ч)')
        missing = ungraded.get(statement.replace('_факультатив_', '_дисциплина_'), 0)
        if missing:
            notes.append(f'у {missing} студ. в ведомости есть семестр без оценки')
        new_label = f'{name}_{kind}_{final}'
        labels.append(new_label)
        checks.append({
            'Строка сводной': new_label,
            'з.е. по часам ведомости': counted,
            'з.е. по учебному плану': planned,
            'Источник з.е.': source,
            'Проверить': '; '.join(notes),
        })
    # With semesters summed, a repeated row would count the credits twice
    for check in checks:
        repeats = labels.count(check['Строка сводной'])
        if repeats > 1:
            note = f'строка повторяется в сводной {repeats} раза — оставьте одну'
            check['Проверить'] = '; '.join(filter(None, [check['Проверить'], note]))
    settled = report.copy()
    settled.index = pd.Index(labels, name=report.index.name)
    return settled, pd.DataFrame(checks, columns=[
        'Строка сводной', 'з.е. по часам ведомости', 'з.е. по учебному плану',
        'Источник з.е.', 'Проверить',
    ])


def process_student_workbook(
    scores_bytes: bytes,
    disciplines_bytes: bytes,
    curriculum_bytes: Optional[bytes] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Main processing function that orchestrates the entire parsing workflow.

    Args:
        scores_bytes: Bytes content of the student scores workbook
        disciplines_bytes: Bytes content of the disciplines workbook
        curriculum_bytes: The curriculum, the source of credits; optional

    Returns:
        Tuple of (consolidated_scores_df, final_report_df, credits_check_df)
    """
    logger.info("Starting student workbook processing")

    excel_file = open_workbook(scores_bytes, "Ведомость")
    sheet_names = excel_file.sheet_names
    logger.info(f"Found {len(sheet_names)} student sheets")
    sheets = {sheet: excel_file.parse(sheet) for sheet in sheet_names}

    labels: Dict[str, None] = {}
    grades: Dict[str, Dict[str, object]] = {}
    hours: Dict[str, float] = {}
    ungraded: Dict[str, int] = {}

    for name, df in sheets.items():
        # The sheet name and the student name are personal data: log the position only
        logger.info("Processing statement sheet %d", list(sheets).index(name) + 1)
        stud_name, new_columns = statement_layout(name, df)
        if stud_name in grades:
            raise WorkbookError(
                f'Ведомость, лист «{name}»: студент «{stud_name}» уже есть на '
                'другом листе — у однофамильцев должны различаться инициалы'
            )
        df = df.iloc[TITLES_ROW + 1:]  # Skip header rows
        df.columns = new_columns

        # Drop columns and rows with unwanted data
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, ~df.columns.str.contains('дата', na=False)]
        df = df[df['наименование предмета'].notna()]
        df = df[~df['наименование предмета'].isin([
            'ПГТУ -', 'Всего', '┌ наименование предмета'
        ])]
        df = df[df['часы учр'].notna()]
        spent = pd.to_numeric(df['часы учр'], errors='coerce')
        if spent.isna().any():
            subject = df.loc[spent.isna(), 'наименование предмета'].iloc[0]
            raise WorkbookError(
                f'Ведомость, лист «{name}»: у «{subject}» в колонке «часы уч.р.» '
                f'не число — «{df.loc[spent.isna(), "часы учр"].iloc[0]}»'
            )
        df = df.assign(**{'часы учр': spent})

        # Convert зачет 'V' to 6
        if 'зачет' in df.columns:
            df['зачет'] = df['зачет'].apply(lambda x: 6 if x == 'V' else x)

        grades[stud_name] = {}
        for record in semester_records(df):
            label = record['label']
            labels.setdefault(label, None)
            grades[stud_name][label] = record['grade']
            hours.setdefault(label, record['hours'])
            if record['ungraded']:
                ungraded[label] = ungraded.get(label, 0) + 1

    # A student with no grade yet in a subject gives it a label without a type;
    # when other students have the typed label, both are the same pivot row
    typed = {LABEL.match(l).group(1) for l in labels if isinstance(l, str) and LABEL.match(l)}
    for label in [l for l in labels if not (isinstance(l, str) and LABEL.match(l))]:
        if label in typed:
            del labels[label]
            for values in grades.values():
                values.pop(label, None)

    df_stud_scores = pd.DataFrame(
        index=pd.Index(list(labels), name='наименование предмета'),
        columns=sorted(grades),
        dtype=object,  # Use object dtype to avoid type warnings
    )
    for student, values in grades.items():
        for label, grade in values.items():
            df_stud_scores.loc[label, student] = grade

    logger.info("Matching disciplines from reference list")
    df_final = parse_discipline(df_stud_scores, disciplines_bytes)

    credits, plan_problem = None, 'учебный план не загружен'
    if curriculum_bytes:
        try:
            credits, sheet = plan_credits(curriculum_bytes)
            logger.info("Curriculum sheet %r has credits for %d names", sheet, len(credits))
        except WorkbookError as error:
            plan_problem = f'учебный план не прочитан ({error})'
            logger.warning("Curriculum is unreadable, credits come from the statement")
    df_final, df_check = settle_credits(df_final, hours, ungraded, credits, plan_problem)

    logger.info("Processing complete")
    return df_stud_scores, df_final, df_check
