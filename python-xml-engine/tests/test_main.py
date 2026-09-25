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
            "direction": "09.03.02 ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ",
            "profile": "Интеллектуальные информационные системы и технологии",
            "edu_progr_vol": "240",
            "edu_progr_vol_contact": "3180 ак.час",
            "pract_total_z_e": "12",
            "gia_z_e": "9",
            "gek_chairman": "Председатель",
            "state_exam_credits": "6",
        },
    )
    assert (
        response.status_code,
        "нет колонки «Дисциплины»" in response.json()["detail"],
    ) == (400, True), "XML service concealed the missing Дисциплины column"


def test_cannot_accept_text_file_as_workbook():
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
            "direction": "09.03.02 ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ",
            "profile": "Интеллектуальные информационные системы и технологии",
            "edu_progr_vol": "240",
            "edu_progr_vol_contact": "3180 ак.час",
            "pract_total_z_e": "12",
            "gia_z_e": "9",
            "gek_chairman": "Председатель",
        },
    )
    assert response.json()["detail"].startswith(
        "Сводная таблица: файл не является книгой Excel"
    ), "XML service failed to reject a disguised CSV file"


def test_cannot_accept_obsolete_speciality_field():
    response = TestClient(app).post(
        "/generate-xml",
        files={
            "pivot_table": ("pivot.xlsx", b"bad", "application/octet-stream"),
            "student_info": ("students.xlsx", b"bad", "application/octet-stream"),
        },
        data={
            "edu_term": "4 года",
            "qualification": "бакалавр",
            "edu_form": "очная",
            "speciality": "09.03.02 Интеллектуальные информационные системы и технологии",
            "edu_progr_vol": "240",
            "edu_progr_vol_contact": "3180 ак.час",
            "pract_total_z_e": "12",
            "gia_z_e": "9",
            "gek_chairman": "Председатель",
        },
    )
    assert response.json()["detail"].startswith("Форма устарела"), (
        "A stale page sent the profile as the direction and it was accepted"
    )
