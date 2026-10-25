from helpers import FakePipeline, RitmError, csrf, job_body, log_in, make_service, wait_for

from app.logging_config import configure_logging


def test_cannot_show_app_before_login(tmp_path):
    _, client = make_service(tmp_path)
    assert 'action="/attestation/login"' in client.get("/attestation").text, "Report page opened without login"


def test_cannot_use_api_without_session(tmp_path):
    _, client = make_service(tmp_path)
    assert client.get("/attestation/api/me").status_code == 401, "API answered without a session"


def test_cannot_log_in_with_wrong_password(tmp_path):
    _, client = make_service(tmp_path)
    assert log_in(client, "wrong password").headers["location"] == "/attestation?error=wrong", (
        "Wrong site password did not return to the login form"
    )


def test_cannot_get_session_cookie_with_wrong_password(tmp_path):
    _, client = make_service(tmp_path)
    assert "set-cookie" not in log_in(client, "wrong password").headers, "Wrong password still produced a cookie"


def test_cannot_issue_cookie_readable_by_scripts(tmp_path):
    _, client = make_service(tmp_path)
    cookie = log_in(client).headers["set-cookie"].lower()
    assert all(part in cookie for part in ("httponly", "secure", "samesite=strict", "path=/attestation")), (
        f"Session cookie is missing a protection flag: {cookie}"
    )


def test_cannot_log_in_without_configured_hash(tmp_path):
    _, client = make_service(tmp_path, password_hash="")
    assert log_in(client).headers["location"] == "/attestation?error=setup", "Login worked without a password hash"


def test_cannot_keep_guessing_site_password(tmp_path):
    _, client = make_service(tmp_path)
    for _ in range(5):
        log_in(client, "wrong password")
    assert log_in(client).headers["location"] == "/attestation?error=limit", (
        "Correct password accepted right after five failures"
    )


def test_cannot_start_job_without_csrf_token(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    assert client.post("/attestation/api/jobs", json=job_body()).status_code == 403, "Job started without CSRF token"


def test_cannot_read_job_of_other_session(tmp_path):
    app, client = make_service(tmp_path)
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    from fastapi.testclient import TestClient

    other = TestClient(app, base_url="https://testserver")
    log_in(other)
    assert other.get(f"/attestation/api/jobs/{job['id']}").status_code == 404, "Another session read the job"


def test_cannot_skip_content_security_policy(tmp_path):
    _, client = make_service(tmp_path)
    assert "script-src 'self'" in client.get("/attestation").headers["content-security-policy"], (
        "Page is served without a script policy"
    )


def test_cannot_let_pages_be_cached(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    assert client.get("/attestation/api/me").headers["cache-control"] == "no-store", "API answers may be cached"


def test_cannot_serve_files_outside_static_list(tmp_path):
    _, client = make_service(tmp_path)
    assert client.get("/attestation/static/index.html").status_code == 404, "Unlisted static file was served"


def test_cannot_lose_ritm_login_error(tmp_path):
    _, client = make_service(tmp_path, FakePipeline(error=RitmError("Неверный логин или пароль.")))
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    assert wait_for(client, job["id"])["error"] == "Неверный логин или пароль.", "RITM login error was hidden"


def test_cannot_show_internal_error_details(tmp_path):
    _, client = make_service(tmp_path, FakePipeline(error=KeyError("/srv/secret/path")))
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    assert "/srv/secret" not in wait_for(client, job["id"])["error"], "Internal error details reached the page"


def test_cannot_show_server_paths_in_progress(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    assert wait_for(client, job["id"])["progress"] == ["Бакалавриат: 2 групп"], "Progress exposed server paths"


def test_cannot_write_ritm_password_to_logs(tmp_path):
    configure_logging("angry-attestation-flow", tmp_path / "logs")
    _, client = make_service(tmp_path, FakePipeline(error=RitmError("Неверный логин или пароль.")))
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(remember=True), headers=csrf(client)).json()
    wait_for(client, job["id"])
    logs = "".join(path.read_text("utf-8") for path in (tmp_path / "logs").glob("*.log"))
    assert "ritm-secret-42" not in logs, "RITM password reached the logs"


def test_cannot_start_job_without_ritm_password(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    response = client.post("/attestation/api/jobs", json=job_body(password=""), headers=csrf(client))
    assert response.status_code == 400, "Job started without a RITM password"


def test_cannot_forget_remembered_password_between_jobs(tmp_path):
    pipeline = FakePipeline()
    _, client = make_service(tmp_path, pipeline)
    log_in(client)
    headers = csrf(client)
    first = client.post("/attestation/api/jobs", json=job_body(remember=True), headers=headers).json()
    wait_for(client, first["id"])
    second = client.post("/attestation/api/jobs", json=job_body(login="", password="", use_saved=True), headers=headers)
    wait_for(client, second.json()["id"])
    assert pipeline.calls[-1][:2] == ("marstu.net\\tester", "ritm-secret-42"), "Saved RITM password did not come back"


def test_cannot_use_saved_password_after_forget(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    headers = csrf(client)
    first = client.post("/attestation/api/jobs", json=job_body(remember=True), headers=headers).json()
    wait_for(client, first["id"])
    client.post("/attestation/api/vault/forget", headers=headers)
    response = client.post("/attestation/api/jobs", json=job_body(use_saved=True), headers=headers)
    assert response.status_code == 400, "Forgotten RITM password was still used"


def test_cannot_run_two_reports_at_once(tmp_path):
    import threading

    gate = threading.Event()

    def slow(workdir, levels, log):
        gate.wait(10)
        (workdir / "attestation_report.md").write_text("# Отчёт\n", encoding="utf-8")
        return workdir

    _, client = make_service(tmp_path, FakePipeline(result=slow))
    log_in(client)
    headers = csrf(client)
    client.post("/attestation/api/jobs", json=job_body(), headers=headers)
    second = client.post("/attestation/api/jobs", json=job_body(), headers=headers)
    gate.set()
    assert second.status_code == 409, "Second report started while the first was running"


def test_cannot_keep_student_files_after_ttl(tmp_path):
    app, client = make_service(tmp_path, files_ttl=-1)
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    wait_for(client, job["id"])
    workdir = app.state.runner._jobs[job["id"]].workdir
    app.state.runner.cleanup()
    assert not workdir.exists(), "Report files outlived their time limit"


def test_cannot_use_session_after_logout(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    cookie = client.cookies.get("attestation_session")
    client.post("/attestation/logout", headers=csrf(client))
    client.cookies.set("attestation_session", cookie, path="/attestation")
    assert client.get("/attestation/api/me").status_code == 401, "Session still worked after logout"


def test_cannot_crash_on_non_ascii_csrf_token(tmp_path):
    _, client = make_service(tmp_path)
    log_in(client)
    response = client.post(
        "/attestation/api/jobs", json=job_body(), headers={"X-CSRF-Token": "тест".encode("utf-8")}
    )
    assert response.status_code == 403, "Non-ASCII CSRF token was not simply refused"
