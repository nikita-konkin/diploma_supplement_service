"""A service instance with a fake RITM portal, and a logged-in client for it."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import Settings, create_app

RITM_LOGIN = "marstu.net\\tester"
RITM_PASSWORD = "ritm-secret-42"


class RitmError(RuntimeError):
    """Same name as ritm_fetch.RitmError: the service shows these messages as they are."""


class PortalSessionExpired(RitmError):
    """Same name as ritm_fetch.PortalSessionExpired."""


class ConnectionError(OSError):  # noqa: A001 — the name requests uses
    pass


class FakePortal:
    def __init__(self, build=None, error: Exception | None = None, login_error: Exception | None = None) -> None:
        self.build_result = build
        self.error = error
        self.login_error = login_error
        self.logins: list[tuple[str, str]] = []
        self.requests: list = []

    def login(self, username, password):
        self.logins.append((username, password))
        if self.login_error is not None:
            raise self.login_error
        if password != RITM_PASSWORD:
            raise RitmError("Неверный логин или пароль.")
        return {"portal-cookie": "abc"}

    def faculties(self, portal, period):
        if self.error is not None:
            raise self.error
        return [{"id": "1857", "label": "РТФ"}, {"id": "1930", "label": "ФИиВТ"}]

    def departments(self, portal, period):
        if self.error is not None:
            raise self.error
        return ["ВМ", "ИТРС", "ФИЗ"]

    def groups(self, portal, period, faculty):
        if self.error is not None:
            raise self.error
        return [
            {"code": "ИТС(о)", "level": "б", "groups": ["ИТС(о)-11", "ИТС(о)-21"]},
            {"code": "ИТСм(о)", "level": "м", "groups": ["ИТСм(о)-11"]},
        ]

    def build(self, portal, request, workdir: Path, log) -> Path:
        self.requests.append(request)
        log(f"Бакалавриат: 2 групп -> {workdir}")
        if self.error is not None:
            raise self.error
        if self.build_result is not None:
            return self.build_result(request, workdir, log)
        (workdir / "attestation_report.md").write_text("# Отчёт\n\n## Сводка\n\nТест\n", encoding="utf-8")
        (workdir / "attestation_report_short_bachelor.docx").write_bytes(b"docx")
        return workdir


def make_service(tmp_path: Path, portal=None, **overrides):
    settings = Settings(
        cookie_secure=True,
        data_dir=tmp_path / "data",
        files_ttl=overrides.pop("files_ttl", 1800),
        session_idle=overrides.pop("session_idle", 1800),
        session_absolute=28800,
    )
    portal = portal or FakePortal()
    app = create_app(settings, portal)
    return app, TestClient(app, base_url="https://testserver"), portal


def log_in(client: TestClient, password: str = RITM_PASSWORD):
    return client.post(
        "/attestation/login",
        data={"username": RITM_LOGIN, "password": password},
        follow_redirects=False,
    )


def csrf(client: TestClient) -> dict:
    return {"X-CSRF-Token": client.get("/attestation/api/me").json()["csrf"]}


PERIOD = {"year": 2026, "odd_semester": True, "attestation": 1}


def job_body(**overrides) -> dict:
    body = {
        **PERIOD,
        "faculty": "1857",
        "department": "ИТРС",
        "codes": ["ИТС(о)", "ИТСм(о)"],
        "faculty_title": "Радиотехнический факультет",
        "head_name": "И. О. Заведующий",
    }
    body.update(overrides)
    return body


def wait_for(client: TestClient, job_id: str, timeout: float = 120) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        job = client.get(f"/attestation/api/jobs/{job_id}").json()
        if job["status"] != "running" or time.monotonic() > deadline:
            return job
        time.sleep(0.05)


def finished(client: TestClient, **overrides) -> dict:
    job = client.post("/attestation/api/jobs", json=job_body(**overrides), headers=csrf(client)).json()
    return wait_for(client, job["id"])
