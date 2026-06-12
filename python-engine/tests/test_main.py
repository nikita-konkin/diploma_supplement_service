from fastapi.testclient import TestClient

from app.main import app


def test_cannot_accept_fake_excel_files():
    response = TestClient(app).post(
        "/pivot",
        files={
            "scores_xlsx": (
                "scores.xlsx",
                b"this is not an xlsx archive",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            "disciplines_xlsx": (
                "disciplines.xlsx",
                b"this is not an xlsx archive either",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
    )
    assert (
        response.status_code,
        response.json()["detail"].startswith("Failed to process workbooks:"),
    ) == (500, True), "Pivot service silently accepted a corrupt workbook"


def test_cannot_accept_wrong_file_extensions():
    response = TestClient(app).post(
        "/pivot",
        files={
            "scores_xlsx": ("scores.txt", b"bad", "text/plain"),
            "disciplines_xlsx": ("disciplines.xlsx", b"bad", "application/octet-stream"),
        },
    )
    assert response.json() == {
        "detail": "scores_xlsx must be an Excel file (.xlsx)"
    }, "Pivot service failed to reject a disguised text file"
