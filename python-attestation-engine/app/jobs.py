"""Background report jobs.

Fetching from RITM takes minutes, longer than a proxy keeps a request open, so the page
starts a job and polls it. Each job works in its own temporary folder: the files contain
student names and scores and are deleted after FILES_TTL seconds.
"""

from __future__ import annotations

import logging
import re
import secrets
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# (login, password, year, odd semester, attestation, levels, work folder, log) -> attestation folder
Pipeline = Callable[[str, str, int, bool, int, list, Path, Callable[[str], None]], Path]

RESULT_FILES = {
    "short": ("attestation_report_short.docx", "Краткий отчёт (DOCX)"),
    "bachelor": ("б/attestation_report_bachelor.docx", "Подробный: бакалавриат (DOCX)"),
    "master": ("м/attestation_report_master.docx", "Подробный: магистратура (DOCX)"),
    "markdown": ("attestation_report.md", "Отчёт в Markdown"),
}


class JobRejected(Exception):
    pass


@dataclass
class Job:
    id: str
    owner: str
    workdir: Path
    title: str
    status: str = "running"
    progress: list[str] = field(default_factory=list)
    error: Optional[str] = None
    markdown: Optional[str] = None
    files: dict[str, Path] = field(default_factory=dict)
    created: float = field(default_factory=time.monotonic)

    def public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress[-12:],
            "error": self.error,
            "markdown": self.markdown,
            "downloads": [
                {"label": RESULT_FILES[key][1], "href": f"/attestation/api/jobs/{self.id}/files/{key}"}
                for key in self.files
            ],
        }


def progress_line(message: str) -> str:
    """Pipeline messages without server paths: «Бакалавриат: 12 групп -> /tmp/…» -> «Бакалавриат: 12 групп»."""
    message = message.split(" -> ", 1)[0]
    return re.sub(r":\s+/\S+", "", message).strip()


class JobRunner:
    def __init__(self, pipeline: Pipeline, files_ttl: int) -> None:
        self.pipeline = pipeline
        self.files_ttl = files_ttl
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        # matplotlib's pyplot is not thread-safe: one report at a time
        self._busy = threading.Lock()

    def start(
        self, owner: str, login: str, password: str, year: int, odd: bool, attestation: int, levels: list
    ) -> Job:
        if not self._busy.acquire(blocking=False):
            raise JobRejected("Уже формируется другой отчёт. Дождитесь его завершения.")
        semester = "нечётный" if odd else "чётный"
        job = Job(
            id=secrets.token_urlsafe(16),
            owner=owner,
            workdir=Path(tempfile.mkdtemp(prefix="attestation-")),
            title=f"Аттестация №{attestation}, {semester} семестр {year}-{year + 1}",
        )
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(
            target=self._run, args=(job, login, password, year, odd, attestation, levels), daemon=True
        )
        thread.start()
        return job

    def _run(self, job: Job, login: str, password: str, year: int, odd: bool, attestation: int, levels: list) -> None:
        try:
            logger.info("Report job %s started: %s", job.id[:6], job.title)
            attestation_dir = self.pipeline(
                login, password, year, odd, attestation, levels, job.workdir,
                lambda message: job.progress.append(progress_line(message)),
            )
            job.files = {
                key: attestation_dir / name
                for key, (name, _) in RESULT_FILES.items()
                if (attestation_dir / name).exists()
            }
            job.markdown = (attestation_dir / RESULT_FILES["markdown"][0]).read_text(encoding="utf-8")
            job.status = "done"
            logger.info("Report job %s finished with %d files", job.id[:6], len(job.files))
        except Exception as error:  # noqa: BLE001 — every failure must reach the page
            job.status = "failed"
            job.error = public_error(error)
            logger.warning("Report job %s failed: %s", job.id[:6], type(error).__name__)
        finally:
            self._busy.release()

    def get(self, job_id: str, owner: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
        return job if job is not None and job.owner == owner else None

    def cleanup(self) -> int:
        """Delete jobs and their files older than files_ttl; returns how many were removed."""
        now = time.monotonic()
        with self._lock:
            expired = [job for job in self._jobs.values() if now - job.created > self.files_ttl and job.status != "running"]
            for job in expired:
                del self._jobs[job.id]
        for job in expired:
            shutil.rmtree(job.workdir, ignore_errors=True)
        return len(expired)

    def start_cleaner(self, interval: int = 60) -> None:
        def loop() -> None:
            while True:
                time.sleep(interval)
                removed = self.cleanup()
                if removed:
                    logger.info("Removed %d expired report jobs", removed)

        threading.Thread(target=loop, daemon=True).start()


def public_error(error: Exception) -> str:
    """Text for the page: RITM errors as they are, network failures in plain words, the rest generic."""
    name = type(error).__name__
    if name == "RitmError":
        return str(error)
    if name in {"ConnectionError", "Timeout", "ReadTimeout", "ConnectTimeout", "SSLError"}:
        return "Портал РИТМ недоступен с сервера. Попробуйте позже."
    return f"Не удалось сформировать отчёт ({name})."
