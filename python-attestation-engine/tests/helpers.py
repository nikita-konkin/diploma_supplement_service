"""A service instance with a fake RITM pipeline, and a logged-in client for it."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import Settings, create_app
from app.security import hash_password

SITE_USER = "head"
SITE_PASSWORD = "correct horse battery"
SITE_HASH = hash_password(SITE_PASSWORD)


class RitmError(RuntimeError):
    """Same name as ritm_fetch.RitmError: the service shows these messages as they are."""


class FakePipeline:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple] = []

    def __call__(self, login, password, year, odd, attestation, levels, workdir, log) -> Path:
        self.calls.append((login, password, year, odd, attestation, tuple(levels)))
        log(f"Бакалавриат: 2 групп -> {workdir}")
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result(workdir, levels, log)
        (workdir / "attestation_report.md").write_text("# Отчёт\n\n## Сводка\n\nТест\n", encoding="utf-8")
        (workdir / "attestation_report_short.docx").write_bytes(b"docx")
        return workdir


def make_service(tmp_path: Path, pipeline=None, **overrides):
    settings = Settings(
        username=SITE_USER,
        password_hash=overrides.pop("password_hash", SITE_HASH),
        cookie_secure=True,
        data_dir=tmp_path / "data",
        files_ttl=overrides.pop("files_ttl", 1800),
        session_idle=overrides.pop("session_idle", 1800),
        session_absolute=28800,
    )
    app = create_app(settings, pipeline or FakePipeline())
    return app, TestClient(app, base_url="https://testserver")


def log_in(client: TestClient, password: str = SITE_PASSWORD):
    return client.post(
        "/attestation/login",
        data={"username": SITE_USER, "password": password},
        follow_redirects=False,
    )


def csrf(client: TestClient) -> dict:
    return {"X-CSRF-Token": client.get("/attestation/api/me").json()["csrf"]}


def job_body(**overrides) -> dict:
    body = {
        "login": "marstu.net\\tester",
        "password": "ritm-secret-42",
        "year": 2026,
        "odd_semester": True,
        "attestation": 1,
        "levels": ["б", "м"],
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
