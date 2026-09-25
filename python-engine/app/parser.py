"""
Core parsing logic for student score XLSX files.
Handles data extraction, normalization, and discipline matching.
"""

import re
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import logging

from .excel import WorkbookError, open_workbook

logger = logging.getLogger(__name__)

# Layout of a statement sheet exported from «Деканат» (0-based, pandas rows
# start after the first sheet row): the student name is the header of column E,
# column titles are on sheet row 7.
STUDENT_NAME_COLUMN = 4
TITLES_ROW = 5
REQUIRED_TITLES = ('наименование предмета', 'часы учр')


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

def parse_rating(df: pd.DataFrame, df_stud_scores: pd.DataFrame, stud_name: str) -> None:
    """
    Updates df_stud_scores with student ratings from df for a given student name.
    Handles 'зачет', 'экзамен', and 'курсовой' columns.
    
    Args:
        df: DataFrame containing student scores
        df_stud_scores: Accumulator DataFrame for all students
        stud_name: Student name (column name)
    """
    for _, row in df.iterrows():
        subject = row['наименование предмета']
        r_units = row['зач ед']
        
        # Determine the type of rating and suffix
        if pd.notna(row.get('зачет')):
            rate = row['зачет']
            suffix = '_практика_' if 'практика' in str(subject).lower() else '_дисциплина_'
        elif 'практика' in str(subject).lower():
            rate = row.get('зачет', np.nan)
            suffix = '_практика_'
        elif pd.notna(row.get('экзамен')):
            rate = row['экзамен']
            suffix = '_дисциплина_'
        elif pd.notna(row.get('курсовой')):
            rate = row['курсовой']
            suffix = '_курсовая_'
        else:
            continue  # Skip if no rating
        
        new_index = f'{subject}{suffix}{r_units}'
        
        # Rename index if not already renamed
        if subject in df_stud_scores.index:
            df_stud_scores.rename(index={subject: new_index}, inplace=True)
        
        # Set the rating - ensure proper type handling
        df_stud_scores.loc[new_index, stud_name] = rate

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
                        matched = True
                        break
                    else:
                        df_result.loc[orig_index] = row
                        df_result = replace_index_occurrence(df_result, orig_index, row_index)
                        matched = True
                        break
                        
                elif match == 'elective':
                    logger.info(f"Matched elective: {row_index}")
                    df_result = df_result.rename(index={orig_index: row_index})
                    df_result.loc[row_index] = row
                    df_result.loc[orig_index] = np.nan
                    matched = True
                    break

                elif match == 'facultative':
                    logger.info(f"Matched facultative: {row_index}")
                    new_index = row_index.replace('дисциплина', 'факультатив')
                    df_result = df_result.rename(index={orig_index: new_index})
                    df_result.loc[new_index] = row
                    # df_result.loc[orig_index] = np.nan
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
    
    # Set index name
    df_result.index.name = 'Дисциплины'
    
    # Add header row
    # new_row = pd.DataFrame({"Дисциплины": np.nan}, index=["дисциплина"])
    # df_result2 = pd.concat([new_row, df_result])
    # df_result2.index.name = 'Дисциплины'
    
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


def process_student_workbook(
    scores_bytes: bytes,
    disciplines_bytes: bytes
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main processing function that orchestrates the entire parsing workflow.
    
    Args:
        scores_bytes: Bytes content of the student scores XLSX file
        disciplines_bytes: Bytes content of the disciplines XLSX file
        
    Returns:
        Tuple of (consolidated_scores_df, final_report_df)
    """
    logger.info("Starting student workbook processing")
    
    excel_file = open_workbook(scores_bytes, "Ведомость")
    sheet_names = excel_file.sheet_names
    
    logger.info(f"Found {len(sheet_names)} student sheets")
    
    # Load each sheet into a dictionary
    sheets = {sheet: excel_file.parse(sheet) for sheet in sheet_names}
    
    df_stud_scores = None
    first_student = True
    
    # Process each student sheet
    for name, df in sheets.items():
        # The sheet name and the student name are personal data: log the position only
        logger.info("Processing statement sheet %d", list(sheets).index(name) + 1)
        stud_name, new_columns = statement_layout(name, df)
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
        hours = pd.to_numeric(df['часы учр'], errors='coerce')
        if hours.isna().any():
            subject = df.loc[hours.isna(), 'наименование предмета'].iloc[0]
            raise WorkbookError(
                f'Ведомость, лист «{name}»: у «{subject}» в колонке «часы уч.р.» '
                f'не число — «{df.loc[hours.isna(), "часы учр"].iloc[0]}»'
            )

        # Convert credits (hours to units)
        df['часы учр'] = (hours.astype(int) / 36).astype(int)
        df.rename(columns={"часы учр": "зач ед"}, inplace=True)
        
        # Convert зачет 'V' to 6
        if 'зачет' in df.columns:
            df['зачет'] = df['зачет'].apply(lambda x: 6 if x == 'V' else x)
        
        # Initialize or update df_stud_scores
        if first_student:
            df_stud_scores = pd.DataFrame(
                columns=[stud_name], 
                index=df.iloc[:, 0],
                dtype=object  # Use object dtype to avoid type warnings
            )
            first_student = False
        else:
            df_stud_scores.insert(0, stud_name, np.nan)
        
        # Parse ratings for this student
        parse_rating(df, df_stud_scores, stud_name)
    
    # Final cleanup of df_stud_scores
    df_stud_scores = df_stud_scores.reindex(sorted(df_stud_scores.columns), axis=1)
    df_stud_scores = df_stud_scores.reset_index()
    df_stud_scores = df_stud_scores.set_index('наименование предмета')
    
    logger.info("Matching disciplines from reference list")
    
    # Match against discipline list
    df_final = parse_discipline(df_stud_scores, disciplines_bytes)
    
    logger.info("Processing complete")
    
    return df_stud_scores, df_final