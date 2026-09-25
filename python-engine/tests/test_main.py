import io

import openpyxl
from fastapi.testclient import TestClient

from app.main import app
from workbooks import curriculum, plan, statement


def pivot(scores=None, disciplines=None, scores_name="scores.xlsx", plan_bytes=None):
    files = {
        "scores_xlsx": (scores_name, statement() if scores is None else scores),
        "disciplines_xlsx": ("disciplines.xlsx", plan("Математика") if disciplines is None else disciplines),
    }
    if plan_bytes is not None:
        files["curriculum_xlsx"] = ("plan.xlsx", plan_bytes)
    return TestClient(app).post("/pivot", files=files)


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
    response = pivot(disciplines=plan("Математика", column="Дисциплины"))
    assert "нет колонки «Обязательная часть»" in response.json()["detail"], (
        "A discipline list without its column gave an unexplained error"
    )


def test_cannot_crash_on_foreign_statement_layout():
    response = pivot(scores=statement(("Тестов Т. Т.", []), titles=("Предмет", "Часы")))
    assert "в строке 7 нет колонок «наименование предмета», «часы учр»" in (
        response.json()["detail"]
    ), "A statement in another layout gave an unexplained error"


def test_cannot_accept_hours_that_are_not_numbers():
    response = pivot(scores=statement(("Тестов Т. Т.", [("Математика", "сто восемь", None, 5, None)])))
    assert "у «Математика» в колонке «часы уч.р.» не число" in response.json()["detail"], (
        "Non-numeric hours gave an unexplained error"
    )


def test_cannot_ignore_uploaded_curriculum():
    response = pivot(plan_bytes=curriculum({"Математика": 4}))
    report = openpyxl.load_workbook(io.BytesIO(response.content))["Report"]
    assert report["A2"].value == "Математика_дисциплина_4", (
        "Credits from the uploaded curriculum did not reach the pivot"
    )


def test_cannot_hide_where_credits_came_from():
    response = pivot()
    sheets = openpyxl.load_workbook(io.BytesIO(response.content)).sheetnames
    assert "Проверка з.е." in sheets, "The pivot has no sheet explaining its credits"
