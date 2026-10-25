"""Кафедра, для которой строится отчёт: название, факультет и заведующий для шапки краткого отчёта.

Лежит в папке аттестации файлом department.json, его пишет make_report.build_all. Без файла
(старые выгрузки, запуск из командной строки) — кафедра ИТРС.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

FILE_NAME = "department.json"


@dataclass(frozen=True)
class DepartmentInfo:
    name: str = "ИТРС"
    faculty_title: str = "Радиотехнический факультет"
    head_name: str = "И. О. Фамилия"

    def save(self, attestation_dir: Path) -> Path:
        path = attestation_dir / FILE_NAME
        attestation_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def load_department(attestation_dir: Path) -> DepartmentInfo:
    path = attestation_dir / FILE_NAME
    if not path.exists():
        return DepartmentInfo()
    data = json.loads(path.read_text(encoding="utf-8"))
    default = DepartmentInfo()
    return DepartmentInfo(
        name=data.get("name") or default.name,
        faculty_title=data.get("faculty_title") or default.faculty_title,
        head_name=data.get("head_name") or default.head_name,
    )
