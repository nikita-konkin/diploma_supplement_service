import logging

from app.logging_config import configure_logging


def test_cannot_mix_events_with_errors(tmp_path):
    configure_logging("angry-xml", tmp_path)
    logging.getLogger("app.angry-xml-test").warning("suspicious event")
    logging.getLogger("app.angry-xml-test").error("fatal generation failure")
    assert (
        "suspicious event" in (tmp_path / "angry-xml-events.log").read_text("utf-8"),
        "fatal generation failure" not in (tmp_path / "angry-xml-events.log").read_text("utf-8"),
        "fatal generation failure" in (tmp_path / "angry-xml-errors.log").read_text("utf-8"),
    ) == (True, True, True), "Logging mixed routine events with failures"


def test_cannot_start_without_event_log(tmp_path):
    configure_logging("angry-xml-startup", tmp_path)
    assert "Logging initialized" in (
        tmp_path / "angry-xml-startup-events.log"
    ).read_text("utf-8"), "XML service started without writing an event log"
