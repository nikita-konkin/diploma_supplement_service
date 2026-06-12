import logging

from app.logging_config import configure_logging


def test_cannot_mix_events_with_errors(tmp_path):
    configure_logging("angry-pivot", tmp_path)
    logging.getLogger("app.angry-pivot-test").info("ordinary event")
    logging.getLogger("app.angry-pivot-test").error("serious failure")
    assert (
        "ordinary event" in (tmp_path / "angry-pivot-events.log").read_text("utf-8"),
        "serious failure" not in (tmp_path / "angry-pivot-events.log").read_text("utf-8"),
        "serious failure" in (tmp_path / "angry-pivot-errors.log").read_text("utf-8"),
    ) == (True, True, True), "Logging mixed routine events with failures"
