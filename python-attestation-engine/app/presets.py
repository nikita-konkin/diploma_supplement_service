"""Remembered choice of groups for each department.

Which groups belong to a department is not in RITM, so the first teacher of a department
ticks its directions once («ИТС(о)», «ИСТм(о)»: direction and form of study, see
ritm_fetch.group_code) and the service remembers them for everyone. New first-year groups
of the same direction are then picked up without any setup.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Preset:
    faculty: str = ""
    codes: list[str] = field(default_factory=list)
    faculty_title: str = ""
    head_name: str = ""


BUILT_IN = {
    "ИТРС": Preset(
        faculty="1857",
        codes=["ИСТ(о)", "ИСТм(о)", "ИТС(о)", "ИТСм(о)"],
        faculty_title="Радиотехнический факультет",
    ),
}


class Presets:
    def __init__(self, directory: Path) -> None:
        self.path = directory / "departments.json"
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def get(self, department: str) -> Optional[Preset]:
        stored = self._read().get(department)
        if stored is not None:
            known = Preset.__dataclass_fields__
            return Preset(**{key: value for key, value in stored.items() if key in known})
        return BUILT_IN.get(department)

    def save(self, department: str, preset: Preset) -> None:
        with self._lock:
            data = self._read()
            data[department] = asdict(preset)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
