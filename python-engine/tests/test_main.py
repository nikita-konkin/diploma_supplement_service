import io

import openpyxl
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app


def statement(*rows, titles=("наименование предмета", "часы учр", "зачет", "экзамен", "курсовой")) -> bytes:
    # «Деканат» layout: student name in E1, column titles on row 7
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Лист1"
    sheet.append(["", "", "", "", "Тестов Т. Т."])
    for _ in range(5):
        sheet.append(["-"])
    sheet.append(list(titles))
    for row in rows or [("Математика", 108, None, 5, None)]:
        sheet.append(list(row))
    content = io.BytesIO()
    workbook.save(content)
    return content.getvalue()


def plan(column="Обязательная часть") -> bytes:
    content = io.BytesIO()
    pd.DataFrame({column: ["Блок 1", "Математика"]}).to_excel(content, index=False)
    return content.getvalue()


def pivot(scores=None, disciplines=None, scores_name="scores.xlsx"):
    return TestClient(app).post(
        "/pivot",
        files={
            "scores_xlsx": (scores_name, statement() if scores is None else scores),
            "disciplines_xlsx": ("disciplines.xlsx", plan() if disciplines is None else disciplines),
        },
    )


def test_cannot_accept_text_file_as_workbook():
    response = pivot(scores=b"this is not an xlsx archive")
    assert (
        response.status_code,
        "не является книгой Excel" in response.json()["detail"],
    ) == (400, True), "A text file was not refused as a workbook"


def test_cannot_reject_workbook_by_its_extension():
    response = pivot(scores_name="scores.xls")
    assert response.status_code == 200, (
        "A valid workbook was refused because of its file name"
    )


def test_cannot_hide_missing_required_part_column():
    response = pivot(disciplines=plan(column="Дисциплины"))
    assert "нет колонки «Обязательная часть»" in response.json()["detail"], (
        "A discipline list without its column gave an unexplained error"
    )


def test_cannot_crash_on_foreign_statement_layout():
    response = pivot(scores=statement(titles=("Предмет", "Часы")))
    assert "в строке 7 нет колонок «наименование предмета», «часы учр»" in (
        response.json()["detail"]
    ), "A statement in another layout gave an unexplained error"


def test_cannot_accept_hours_that_are_not_numbers():
    response = pivot(scores=statement(("Математика", "сто восемь", None, 5, None)))
    assert "у «Математика» в колонке «часы уч.р.» не число" in response.json()["detail"], (
        "Non-numeric hours gave an unexplained error"
    )
