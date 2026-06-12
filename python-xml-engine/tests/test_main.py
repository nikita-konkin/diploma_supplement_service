import io

from fastapi.testclient import TestClient
import pandas as pd

from app.main import app


def test_cannot_hide_missing_disciplines_column():
    pivot = io.BytesIO()
    pd.DataFrame({"Wrong column": ["Math"]}).to_excel(pivot, index=False)
    students = io.BytesIO()
    pd.DataFrame({"ФИО": ["Иванов Иван Иванович"]}).to_excel(students, index=False)
    response = TestClient(app).post(
        "/generate-xml",
        files={
            "pivot_table": ("pivot.xlsx", pivot.getvalue(), "application/octet-stream"),
            "student_info": ("students.xlsx", students.getvalue(), "application/octet-stream"),
        },
        data={
            "edu_term": "4 года",
            "qualification": "бакалавр",
            "edu_form": "очная",
            "speciality": "09.03.01 Информатика",
            "edu_progr_vol": "240",
            "edu_progr_vol_contact": "3180 ак.час",
            "pract_total_z_e": "12",
            "gia_z_e": "9",
            "gek_chairman": "Председатель",
            "state_exam_credits": "6",
        },
    )
    assert (response.status_code, response.json()["detail"]) == (
        500,
        'Failed to generate XML: "None of [\'Дисциплины\'] are in the columns"',
    ), "XML service concealed the missing Дисциплины column"


def test_cannot_accept_wrong_file_extensions():
    response = TestClient(app).post(
        "/generate-xml",
        files={
            "pivot_table": ("pivot.csv", b"bad", "text/csv"),
            "student_info": ("students.xlsx", b"bad", "application/octet-stream"),
        },
        data={
            "edu_term": "4 года",
            "qualification": "бакалавр",
            "edu_form": "очная",
            "speciality": "09.03.01 Информатика",
            "edu_progr_vol": "240",
            "edu_progr_vol_contact": "3180 ак.час",
            "pract_total_z_e": "12",
            "gia_z_e": "9",
            "gek_chairman": "Председатель",
        },
    )
    assert response.json() == {
        "detail": "pivot_table must be an Excel file (.xlsx)"
    }, "XML service failed to reject a disguised CSV file"
