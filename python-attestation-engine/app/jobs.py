"""Background report jobs.

Fetching from RITM takes minutes, longer than a proxy keeps a request open, so the page
starts a job and polls it. Each job works in its own temporary folder: the files contain
student names and scores and are deleted after FILES_TTL seconds.
"""

from __future__ import annotations

import json
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

# (work folder, log) -> attestation folder with the reports
Work = Callable[[Path, Callable[[str], None]], Path]

RESULT_FILES = {
    "short": ("attestation_report_short.docx", "Краткий отчёт (DOCX)"),
    "bachelor": ("б/attestation_report_bachelor.docx", "Подробный: бакалавриат (DOCX)"),
    "master": ("м/attestation_report_master.docx", "Подробный: магистратура (DOCX)"),
    "markdown": ("attestation_report.md", "Отчёт в Markdown"),
}
DATA_FILE = "attestation_report.json"  # данные графиков страницы, см. report_model.model_data


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
    data: Optional[dict] = None
    files: dict[str, Path] = field(default_factory=dict)
    created: float = field(default_factory=time.monotonic)

    def public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress[-12:],
            "error": self.error,
            "markdown": self.markdown,
            "data": self.data,
            "downloads": [
                {"label": RESULT_FILES[key][1], "href": f"/attestation/api/jobs/{self.id}/files/{key}"}
                for key in self.files
            ],
        }


LEVEL_FOLDERS = {"б": "бакалавриат", "м": "магистратура"}


def progress_line(message: str) -> str:
    """Pipeline messages without server paths.

    «Бакалавриат: 12 групп -> /tmp/…» -> «Бакалавриат: 12 групп»;
    «Анализ: /tmp/…/1/б» -> «Анализ: бакалавриат»; «Отчёт готов: /tmp/…/x.docx» -> «Отчёт готов: x.docx».
    """
    message = message.split(" -> ", 1)[0]

    def last_part(match: re.Match) -> str:
        name = match.group(1).rstrip("/").rsplit("/", 1)[-1]
        return ": " + LEVEL_FOLDERS.get(name, name)

    return re.sub(r":\s+(/\S+)", last_part, message).strip()


class JobRunner:
    def __init__(self, files_ttl: int) -> None:
        self.files_ttl = files_ttl
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        # matplotlib's pyplot is not thread-safe: one report at a time
        self._busy = threading.Lock()

    def start(self, owner: str, title: str, work: Work) -> Job:
        if not self._busy.acquire(blocking=False):
            raise JobRejected("Сейчас формируется другой отчёт (возможно, другим преподавателем). Попробуйте через несколько минут.")
        job = Job(
            id=secrets.token_urlsafe(16),
            owner=owner,
            workdir=Path(tempfile.mkdtemp(prefix="attestation-")),
            title=title,
        )
        with self._lock:
            self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job, work), daemon=True).start()
        return job

    def _run(self, job: Job, work: Work) -> None:
        try:
            logger.info("Report job %s started: %s", job.id[:6], job.title)
            attestation_dir = work(job.workdir, lambda message: job.progress.append(progress_line(message)))
            job.files = {
                key: attestation_dir / name
                for key, (name, _) in RESULT_FILES.items()
                if (attestation_dir / name).exists()
            }
            job.markdown = (attestation_dir / RESULT_FILES["markdown"][0]).read_text(encoding="utf-8")
            data_path = attestation_dir / DATA_FILE
            # without the data the page still shows the report, only without charts
            job.data = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else None
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



def public_error(error: Exception) -> str:
    """Text for the page: RITM errors as they are, network failures in plain words, the rest generic."""
    name = type(error).__name__
    if name == "PortalSessionExpired":
        return "Сеанс портала РИТМ истёк. Выйдите и войдите снова."
    if name == "RitmError":
        return str(error)
    if name in {"ConnectionError", "Timeout", "ReadTimeout", "ConnectTimeout", "SSLError"}:
        return "Портал РИТМ недоступен с сервера. Попробуйте позже."
    return f"Не удалось сформировать отчёт ({name})."
