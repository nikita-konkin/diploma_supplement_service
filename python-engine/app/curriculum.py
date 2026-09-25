"""
Credits (з.е.) of disciplines from the curriculum (учебный план).

A «Деканат» statement lists a discipline once per semester, so its credits
cannot be read from a single row (B-31). The curriculum has the total in
«Объем частей ОП в зачетных единицах» → «Всего» (the format of «Планы»)
or «Трудоемкость в зачетных единицах» → «всего» (older plans).
"""

import re
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd

from .excel import WorkbookError, open_workbook

NAME_TITLES = ('структура оп', 'наименование дисциплин')
CREDIT_TITLES = ('объем частей оп в зачетных единицах', 'трудоемкость в зачетных единицах')
HEADER_ROWS = 60


def name_key(name) -> str:
    """Discipline name reduced for comparison: case, ё, punctuation and spaces."""
    text = str(name).lower().replace('ё', 'е')
    return ' '.join(re.sub(r'[^0-9a-zа-я]+', ' ', text).split())


def title(value) -> str:
    return ' '.join(str(value).lower().replace('ё', 'е').split()) if isinstance(value, str) else ''


def plan_credits(content: bytes) -> Tuple[Dict[str, float], str]:
    """
    Credits by discipline name key, and the sheet they were read from.

    A name listed twice (a practice split between blocks) gets the sum.

    Raises:
        WorkbookError: the file is not a workbook or has no credits columns
    """
    book = open_workbook(content, 'Учебный план')
    for sheet in book.sheet_names:
        df = book.parse(sheet, header=None)
        name_at = credit_at = None
        for (row, col), value in _cells(df.head(HEADER_ROWS)):
            text = title(value)
            if name_at is None and text in NAME_TITLES:
                name_at = (row, col)
            if credit_at is None and text.startswith(CREDIT_TITLES):
                credit_at = (row, col)
        if name_at is None or credit_at is None:
            continue
        credits: Dict[str, float] = {}
        for row in range(max(name_at[0], credit_at[0]) + 1, len(df)):
            name = df.iat[row, name_at[1]]
            value = pd.to_numeric(df.iat[row, credit_at[1]], errors='coerce')
            if isinstance(name, str) and name.strip() and pd.notna(value):
                key = name_key(name)
                credits[key] = credits.get(key, 0) + float(value)
        if credits:
            return credits, sheet
    raise WorkbookError(
        'Учебный план: не найдены колонки «Структура ОП» (или «Наименование '
        'дисциплин») и «Объем частей ОП в зачетных единицах» (или «Трудоемкость '
        'в зачетных единицах»)'
    )


def find_credits(names: Iterable[str], credits: Dict[str, float]) -> Optional[float]:
    """
    Credits of the first name found in the plan: exactly, or as the only plan
    name that contains it or is contained in it.
    """
    keys = [name_key(n) for n in names if isinstance(n, str) and n.strip()]
    for key in keys:
        if key in credits:
            return credits[key]
    for key in keys:
        if len(key) < 10:
            continue
        near = [k for k in credits if key in k or (len(k) >= 10 and k in key)]
        if len(near) == 1:
            return credits[near[0]]
    return None


def _cells(df: pd.DataFrame):
    for row in range(len(df)):
        for col in range(df.shape[1]):
            value = df.iat[row, col]
            if isinstance(value, str):
                yield (row, col), value
