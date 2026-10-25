import threading

from fastapi.testclient import TestClient
from helpers import (
    PERIOD,
    RITM_PASSWORD,
    ConnectionError,
    FakePortal,
    PortalSessionExpired,
    RitmError,
    csrf,
    finished,
    job_body,
    log_in,
    make_service,
    wait_for,
)

from app.logging_config import configure_logging


def test_cannot_show_app_before_login(tmp_path):
    _, client, _ = make_service(tmp_path)
    assert 'action="/attestation/login"' in client.get("/attestation").text, "Report page opened without login"


def test_cannot_use_api_without_session(tmp_path):
    _, client, _ = make_service(tmp_path)
    assert client.get("/attestation/api/me").status_code == 401, "API answered without a session"


def test_cannot_log_in_with_password_portal_refused(tmp_path):
    _, client, _ = make_service(tmp_path)
    assert log_in(client, "wrong password").headers["location"] == "/attestation?error=wrong", (
        "Refused RITM password did not return to the login form"
    )


def test_cannot_get_session_cookie_with_refused_password(tmp_path):
    _, client, _ = make_service(tmp_path)
    assert "set-cookie" not in log_in(client, "wrong password").headers, "Refused password still produced a cookie"


def test_cannot_issue_cookie_readable_by_scripts(tmp_path):
    _, client, _ = make_service(tmp_path)
    cookie = log_in(client).headers["set-cookie"].lower()
    assert all(part in cookie for part in ("httponly", "secure", "samesite=strict", "path=/attestation")), (
        f"Session cookie is missing a protection flag: {cookie}"
    )


def test_cannot_keep_ritm_password_in_session(tmp_path):
    app, client, _ = make_service(tmp_path)
    log_in(client)
    kept = repr([vars(session) for session in app.state.sessions._sessions.values()])
    assert RITM_PASSWORD not in kept, "Session kept the RITM password"


def test_cannot_blame_password_when_portal_is_down(tmp_path):
    _, client, _ = make_service(tmp_path, FakePortal(login_error=ConnectionError("refused")))
    assert log_in(client).headers["location"] == "/attestation?error=portal", (
        "Portal outage was reported as a wrong password"
    )


def test_cannot_keep_guessing_portal_passwords(tmp_path):
    _, client, _ = make_service(tmp_path)
    for _ in range(5):
        log_in(client, "wrong password")
    assert log_in(client).headers["location"] == "/attestation?error=limit", (
        "Correct password accepted right after five failures"
    )


def test_cannot_forward_guesses_to_portal_after_limit(tmp_path):
    _, client, portal = make_service(tmp_path)
    for _ in range(7):
        log_in(client, "wrong password")
    assert len(portal.logins) == 5, "Limited logins still reached the RITM portal"


def test_cannot_show_logged_in_user_wrongly(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    assert client.get("/attestation/api/me").json()["login"] == "marstu.net\\tester", "Page shows a wrong login"


def test_cannot_lose_department_list(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    assert client.get("/attestation/api/departments", params=PERIOD).json() == ["ВМ", "ИТРС", "ФИЗ"], (
        "Department list did not reach the page"
    )


def test_cannot_mix_master_directions_with_bachelor(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    groups = client.get("/attestation/api/groups", params={**PERIOD, "faculty": "1857"}).json()
    assert [item["level"] for item in groups if item["code"] == "ИТСм(о)"] == ["м"], "Master's direction lost its level"


def test_cannot_send_arbitrary_faculty_to_portal(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    response = client.get("/attestation/api/groups", params={**PERIOD, "faculty": "1857' or 1=1"})
    assert response.status_code == 422, "Non-numeric faculty went to the portal"


def test_cannot_hide_portal_error_on_lists(tmp_path):
    _, client, _ = make_service(tmp_path, FakePortal(error=RitmError("Ошибка сервера отчётов: нет прав")))
    log_in(client)
    response = client.get("/attestation/api/faculties", params=PERIOD)
    assert (response.status_code, response.json()["detail"]) == (502, "Ошибка сервера отчётов: нет прав"), (
        "Portal refusal was hidden from the page"
    )


def test_cannot_keep_session_after_portal_expired(tmp_path):
    _, client, _ = make_service(tmp_path, FakePortal(error=PortalSessionExpired("истёк")))
    log_in(client)
    client.get("/attestation/api/faculties", params=PERIOD)
    assert client.get("/attestation/api/me").status_code == 401, "Session outlived the portal's session"


def test_cannot_offer_preset_of_built_in_department_wrongly(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    assert client.get("/attestation/api/preset", params={"department": "ИТРС"}).json()["faculty"] == "1857", (
        "ИТРС preset lost its faculty"
    )


def test_cannot_remember_choice_before_report_succeeds(tmp_path):
    _, client, _ = make_service(tmp_path, FakePortal(error=RitmError("сбой")))
    log_in(client)
    finished(client, department="ВМ", codes=["ПИ(о)"])
    assert client.get("/attestation/api/preset", params={"department": "ВМ"}).json() is None, (
        "Failed report still saved its group choice"
    )


def test_cannot_forget_choice_after_report(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    finished(client, department="ВМ", codes=["ПИ(о)"], faculty="1930")
    assert client.get("/attestation/api/preset", params={"department": "ВМ"}).json()["codes"] == ["ПИ(о)"], (
        "Group choice of a department was not remembered"
    )


def test_cannot_pass_wrong_choice_to_report(tmp_path):
    _, client, portal = make_service(tmp_path)
    log_in(client)
    finished(client, department="ВМ", codes=["ПИ(о)", "ПИм(о)"], faculty="1930")
    request = portal.requests[-1]
    assert (request.department, request.faculty, sorted(request.codes)) == ("ВМ", "1930", ["ПИ(о)", "ПИм(о)"]), (
        f"Report was built for something else: {request}"
    )


def test_cannot_start_job_without_directions(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    response = client.post("/attestation/api/jobs", json=job_body(codes=[" "]), headers=csrf(client))
    assert response.status_code == 400, "Job started without any group direction"


def test_cannot_start_job_without_csrf_token(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    assert client.post("/attestation/api/jobs", json=job_body()).status_code == 403, "Job started without CSRF token"


def test_cannot_crash_on_non_ascii_csrf_token(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    response = client.post(
        "/attestation/api/jobs", json=job_body(), headers={"X-CSRF-Token": "тест".encode("utf-8")}
    )
    assert response.status_code == 403, "Non-ASCII CSRF token was not simply refused"


def test_cannot_read_job_of_other_session(tmp_path):
    app, client, _ = make_service(tmp_path)
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    other = TestClient(app, base_url="https://testserver")
    log_in(other)
    assert other.get(f"/attestation/api/jobs/{job['id']}").status_code == 404, "Another session read the job"


def test_cannot_skip_content_security_policy(tmp_path):
    _, client, _ = make_service(tmp_path)
    assert "script-src 'self'" in client.get("/attestation").headers["content-security-policy"], (
        "Page is served without a script policy"
    )


def test_cannot_let_pages_be_cached(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    assert client.get("/attestation/api/me").headers["cache-control"] == "no-store", "API answers may be cached"


def test_cannot_serve_files_outside_static_list(tmp_path):
    _, client, _ = make_service(tmp_path)
    assert client.get("/attestation/static/index.html").status_code == 404, "Unlisted static file was served"


def test_cannot_lose_ritm_error_in_job(tmp_path):
    _, client, _ = make_service(tmp_path, FakePortal(error=RitmError("В выбранных направлениях нет групп.")))
    log_in(client)
    assert finished(client)["error"] == "В выбранных направлениях нет групп.", "RITM error in the job was hidden"


def test_cannot_show_internal_error_details(tmp_path):
    _, client, _ = make_service(tmp_path, FakePortal(error=KeyError("/srv/secret/path")))
    log_in(client)
    assert "/srv/secret" not in finished(client)["error"], "Internal error details reached the page"


def test_cannot_show_server_paths_in_progress(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    assert finished(client)["progress"] == ["Бакалавриат: 2 групп"], "Progress exposed server paths"


def test_cannot_write_ritm_password_to_logs(tmp_path):
    configure_logging("angry-attestation-flow", tmp_path / "logs")
    _, client, _ = make_service(tmp_path)
    log_in(client, "wrong-" + RITM_PASSWORD)
    log_in(client)
    finished(client)
    logs = "".join(path.read_text("utf-8") for path in (tmp_path / "logs").glob("*.log"))
    assert RITM_PASSWORD not in logs, "RITM password reached the logs"


def test_cannot_run_two_reports_at_once(tmp_path):
    gate = threading.Event()

    def slow(request, workdir, log):
        gate.wait(10)
        (workdir / "attestation_report.md").write_text("# Отчёт\n", encoding="utf-8")
        return workdir

    _, client, _ = make_service(tmp_path, FakePortal(build=slow))
    log_in(client)
    headers = csrf(client)
    client.post("/attestation/api/jobs", json=job_body(), headers=headers)
    second = client.post("/attestation/api/jobs", json=job_body(), headers=headers)
    gate.set()
    assert second.status_code == 409, "Second report started while the first was running"


def test_cannot_keep_student_files_after_ttl(tmp_path):
    app, client, _ = make_service(tmp_path, files_ttl=-1)
    log_in(client)
    job = finished(client)
    workdir = app.state.runner._jobs[job["id"]].workdir
    app.state.runner.cleanup()
    assert not workdir.exists(), "Report files outlived their time limit"


def test_cannot_use_session_after_logout(tmp_path):
    _, client, _ = make_service(tmp_path)
    log_in(client)
    cookie = client.cookies.get("attestation_session")
    client.post("/attestation/logout", headers=csrf(client))
    client.cookies.set("attestation_session", cookie, path="/attestation")
    assert client.get("/attestation/api/me").status_code == 401, "Session still worked after logout"


def test_cannot_hide_which_level_is_analysed():
    from app.jobs import progress_line

    assert progress_line("Анализ: /tmp/attestation-x/2026-2027/нечет/1/м") == "Анализ: магистратура", (
        "Progress line lost the level being analysed"
    )
