import logging

from app.logging_config import configure_logging, redact


def test_cannot_mix_events_with_errors(tmp_path):
    configure_logging("angry-attestation", tmp_path)
    logging.getLogger("app.angry-test").warning("suspicious event")
    logging.getLogger("app.angry-test").error("fatal report failure")
    assert (
        "suspicious event" in (tmp_path / "angry-attestation-events.log").read_text("utf-8"),
        "fatal report failure" not in (tmp_path / "angry-attestation-events.log").read_text("utf-8"),
        "fatal report failure" in (tmp_path / "angry-attestation-errors.log").read_text("utf-8"),
    ) == (True, True, True), "Logging mixed routine events with failures"


def test_cannot_log_password_in_form_body():
    assert "ritm-secret" not in redact("username=a&password=ritm-secret&x=1"), "Redaction missed a form password"


def test_cannot_log_password_in_json():
    assert "ritm-secret" not in redact('{"password": "ritm-secret"}'), "Redaction missed a JSON password"


def test_cannot_log_password_passed_as_argument(tmp_path):
    configure_logging("angry-redact", tmp_path)
    logging.getLogger("app.angry-test").warning("body %s", "password=ritm-secret")
    assert "ritm-secret" not in (tmp_path / "angry-redact-events.log").read_text("utf-8"), (
        "Password reached the event log"
    )
