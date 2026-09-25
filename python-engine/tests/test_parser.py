import io

import pandas as pd

from app.parser import parse_discipline


def plan(*names) -> bytes:
    # The first row under the header is a block title that the parser skips.
    workbook = io.BytesIO()
    pd.DataFrame({"Обязательная часть": ["Блок 1", *names]}).to_excel(
        workbook, index=False
    )
    return workbook.getvalue()


def scores() -> pd.DataFrame:
    return pd.DataFrame(
        {"Иванов И. И.": [4, 5]},
        index=["Математика_дисциплина_4", "Волейбол_дисциплина_2"],
    )


def test_cannot_give_group_member_grades_of_first_row():
    result = parse_discipline(
        scores(),
        plan("Математика", "Элективные дисциплины по физической культуре * 1", "Волейбол"),
    )
    grade = result.loc[
        "Элективные дисциплины по физической культуре. Волейбол_дисциплина_2",
        "Иванов И. И.",
    ]
    assert grade == 5, "A group discipline received the grade of the first row"


def test_cannot_leave_group_header_in_pivot():
    result = parse_discipline(
        scores(),
        plan("Математика", "Элективные дисциплины по физической культуре * 1", "Волейбол"),
    )
    assert not any("*" in str(name) for name in result.index), (
        "The '* N' group header stayed in the pivot table"
    )
