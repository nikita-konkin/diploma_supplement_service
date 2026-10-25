"""Everything the service asks of the RITM portal, behind one class the tests replace.

The modules come from reports/ on PYTHONPATH (the same ones the command line runs), and
they are imported lazily so that the service starts even before matplotlib warms up.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Period:
    year: int
    odd_semester: bool
    attestation: int


@dataclass(frozen=True)
class ReportRequest:
    period: Period
    faculty: str
    department: str
    codes: frozenset[str]
    faculty_title: str
    head_name: str


class RitmPortal:
    # The department list takes the 5-second «Процент аттестаций по кафедрам»; it is the same
    # for everyone and changes only with the period
    DEPARTMENTS_TTL = 3600

    def __init__(self) -> None:
        self._departments: dict[Period, tuple[float, list[str]]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _period(period: Period):
        import ritm_fetch

        return ritm_fetch.AttestationPeriod(period.year, period.odd_semester, period.attestation)

    def login(self, username: str, password: str) -> Any:
        """Portal session for these credentials; RitmError when the portal refuses them."""
        import ritm_fetch

        return ritm_fetch.login(username, password)

    def faculties(self, portal: Any, period: Period) -> list[dict]:
        import ritm_fetch

        return [
            {"id": value, "label": label}
            for value, label in ritm_fetch.list_faculties(portal, self._period(period))
        ]

    def groups(self, portal: Any, period: Period, faculty: str) -> list[dict]:
        """Groups of the faculty as directions: [{code, level, groups: [names]}]."""
        import ritm_fetch

        directions: dict[tuple[str, str], list[str]] = {}
        for level in ritm_fetch.LEVELS:
            for group in ritm_fetch.list_groups(portal, self._period(period), level, faculty):
                directions.setdefault((level, ritm_fetch.group_code(group.name)), []).append(group.name)
        return [
            {"code": code, "level": level, "groups": sorted(names)}
            for (level, code), names in sorted(directions.items())
        ]

    def departments(self, portal: Any, period: Period) -> list[str]:
        import ritm_fetch

        now = time.monotonic()
        with self._lock:
            cached = self._departments.get(period)
        if cached is not None and now - cached[0] < self.DEPARTMENTS_TTL:
            return cached[1]
        _, root = ritm_fetch.fetch_kafedra_xml(portal, self._period(period))
        names = ritm_fetch.kafedra_departments(root)
        with self._lock:
            self._departments[period] = (now, names)
        return names

    def build(self, portal: Any, request: ReportRequest, workdir: Path, log: Callable[[str], None]) -> Path:
        """Fetch the chosen groups and build every report; returns the attestation folder."""
        import make_report
        import ritm_fetch
        from department_info import DepartmentInfo

        period = self._period(request.period)
        levels = [
            level
            for level in ritm_fetch.LEVELS
            if ritm_fetch.department_groups(
                ritm_fetch.list_groups(portal, period, level, request.faculty), set(request.codes)
            )
        ]
        if not levels:
            raise ritm_fetch.RitmError("В выбранных направлениях нет групп за этот период.")
        log(period.label)
        department = DepartmentInfo(
            name=request.department,
            faculty_title=request.faculty_title,
            head_name=request.head_name or DepartmentInfo.head_name,
        )
        return make_report.build_all(
            portal, period, workdir, levels, log=log,
            department=department, faculty=request.faculty, codes=set(request.codes),
        )
