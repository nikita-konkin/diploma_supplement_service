import pandas as pd

from app.parser import parse_discipline, process_student_workbook
from workbooks import curriculum, plan, statement


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


TWO_SEMESTERS = ("Тестов Т. Т.", [
    ("Математика", 72, "V", None, None),
    ("Математика", 108, None, 5, None),
])


def pivot_of(*students, curriculum_bytes=None, names=("Математика",)):
    _, report, check = process_student_workbook(
        statement(*students), plan(*names), curriculum_bytes
    )
    return report, check


def test_cannot_count_credits_of_one_semester():
    report, _ = pivot_of(TWO_SEMESTERS)
    assert "Математика_дисциплина_5" in report.index, (
        "Credits of a two-semester discipline were taken from one semester"
    )


def test_cannot_prefer_first_semester_grade_to_exam():
    report, _ = pivot_of(TWO_SEMESTERS)
    assert report.iloc[0]["Тестов Т. Т."] == 5, (
        "The grade of a first-semester test replaced the exam grade"
    )


def test_cannot_prefer_later_test_to_exam():
    report, _ = pivot_of(("Тестов Т. Т.", [
        ("Физика", 252, None, 3, None),
        ("Физика", 72, 4, None, None),
    ]), names=("Физика",))
    assert report.iloc[0]["Тестов Т. Т."] == 3, (
        "A later graded test replaced the exam grade"
    )


def test_cannot_leave_course_work_hours_out_of_credits():
    report, _ = pivot_of(("Тестов Т. Т.", [
        ("Радиоприемные устройства", 80, None, 4, None),
        ("Радиоприемные устройства", 100, None, None, 5),
    ]), names=("Радиоприемные устройства",))
    assert "Радиоприемные устройства_дисциплина_5" in report.index, (
        "Course work hours were not counted in the discipline credits"
    )


def test_cannot_ignore_curriculum_credits():
    report, _ = pivot_of(TWO_SEMESTERS, curriculum_bytes=curriculum({"Математика": 6}))
    assert "Математика_дисциплина_6" in report.index, (
        "Credits from the curriculum did not reach the pivot"
    )


def test_cannot_read_old_curriculum_format():
    report, _ = pivot_of(TWO_SEMESTERS, curriculum_bytes=curriculum(
        {"Математика": 6},
        titles=("Наименование дисциплин", "ТРУДОЕМКОСТЬ В ЗАЧЕТНЫХ ЕДИНИЦАХ"),
    ))
    assert "Математика_дисциплина_6" in report.index, (
        "Credits from a curriculum in the old format were not read"
    )


def test_cannot_hide_credits_missing_from_curriculum():
    _, check = pivot_of(TWO_SEMESTERS, curriculum_bytes=curriculum({"Физика": 9}))
    assert check.iloc[0]["Проверить"] == "нет в учебном плане", (
        "A discipline absent from the curriculum was not marked for checking"
    )


def test_cannot_fail_on_unreadable_curriculum():
    _, check = pivot_of(TWO_SEMESTERS, curriculum_bytes=b"not a workbook")
    assert check.iloc[0]["Проверить"].startswith("учебный план не прочитан"), (
        "An unreadable curriculum was not reported for checking"
    )


def test_cannot_lose_grades_when_first_student_has_none():
    report, _ = pivot_of(
        ("Андреев А. А.", [("Математика", 108, None, None, None)]),
        ("Борисов Б. Б.", [("Математика", 108, None, 4, None)]),
    )
    assert report.loc["Математика_дисциплина_3", "Борисов Б. Б."] == 4, (
        "A grade was lost because the first student had none yet"
    )
