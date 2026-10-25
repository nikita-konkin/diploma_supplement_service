"""Разбор отчёта «Процент аттестаций по кафедрам» (AttestationByKafedra.xml) и рейтинг кафедр.

Структура отчёта: кафедра -> преподаватель -> группа -> дисциплина (всего, аттестовано).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from attestation_analysis import installed_font_family  # noqa: E402


KAFEDRA_REPORT_FILE = "AttestationByKafedra.xml"
DEPARTMENT_NAME = "ИТРС"


@dataclass
class TeacherRecord:
    group: str
    subject: str
    total: int
    attested: int

    @property
    def failed(self) -> int:
        return self.total - self.attested

    @property
    def failure_rate(self) -> float:
        return self.failed / self.total * 100 if self.total else 0.0


@dataclass
class Teacher:
    name: str
    records: list[TeacherRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(record.total for record in self.records)

    @property
    def attested(self) -> int:
        return sum(record.attested for record in self.records)

    @property
    def failed(self) -> int:
        return self.total - self.attested

    @property
    def failure_rate(self) -> float:
        return self.failed / self.total * 100 if self.total else 0.0

    @property
    def groups(self) -> set[str]:
        return {record.group for record in self.records}

    @property
    def subjects(self) -> set[str]:
        return {record.subject for record in self.records}


@dataclass
class Department:
    name: str
    teachers: list[Teacher]

    @property
    def total(self) -> int:
        return sum(teacher.total for teacher in self.teachers)

    @property
    def attested(self) -> int:
        return sum(teacher.attested for teacher in self.teachers)

    @property
    def failed(self) -> int:
        return self.total - self.attested

    @property
    def failure_rate(self) -> float:
        return self.failed / self.total * 100 if self.total else 0.0

    @property
    def groups(self) -> set[str]:
        return {group for teacher in self.teachers for group in teacher.groups}

    @property
    def records(self) -> list[tuple[Teacher, TeacherRecord]]:
        return [(teacher, record) for teacher in self.teachers for record in teacher.records]


@dataclass
class KafedraReport:
    source_path: Path
    execution_time: str
    departments: list[Department]

    def department(self, name: str = DEPARTMENT_NAME) -> Department | None:
        return next((item for item in self.departments if item.name == name), None)

    def ranking(self) -> list[Department]:
        """Кафедры от наименьшей доли неаттестованных к наибольшей: 1-е место — лучшая."""
        ranked = [item for item in self.departments if item.total]
        return sorted(ranked, key=lambda item: (item.failure_rate, item.name))

    def rank_of(self, name: str = DEPARTMENT_NAME) -> int | None:
        for place, item in enumerate(self.ranking(), start=1):
            if item.name == name:
                return place
        return None

    @property
    def total(self) -> int:
        return sum(item.total for item in self.departments)

    @property
    def failure_rate(self) -> float:
        failed = sum(item.failed for item in self.departments)
        return failed / self.total * 100 if self.total else 0.0


def find_kafedra_report(input_dir: Path) -> Path | None:
    """XML лежит в папке аттестации, рядом с папками б/м."""
    candidate = input_dir.parent / KAFEDRA_REPORT_FILE
    return candidate if candidate.exists() else None


def parse_int(value: str | None) -> int:
    try:
        return int(float((value or "0").replace(",", ".")))
    except ValueError:
        return 0


def format_execution_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value[:19]).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def children(element: ET.Element, name: str) -> list[ET.Element]:
    """Дочерние элементы через обёртку <name_Collection>."""
    return [
        item
        for collection in element
        if local_name(collection) == f"{name}_Collection"
        for item in collection
        if local_name(item) == name
    ]


def parse_kafedra_report(xml_path: Path) -> KafedraReport:
    root = ET.parse(xml_path).getroot()
    departments: list[Department] = []
    for department_el in root.iter():
        if local_name(department_el) != "subjectKafedra" or "subjectKafedra" not in department_el.attrib:
            continue
        teachers = []
        for teacher_el in children(department_el, "lectorFIO"):
            teacher = Teacher(name=teacher_el.attrib.get("lectorFIO", "").strip())
            for group_el in children(teacher_el, "egName"):
                for subject_el in children(group_el, "sbj"):
                    teacher.records.append(
                        TeacherRecord(
                            group=group_el.attrib.get("egName", "").strip(),
                            subject=subject_el.attrib.get("sbj", "").strip(),
                            total=parse_int(subject_el.attrib.get("total")),
                            attested=parse_int(subject_el.attrib.get("attested")),
                        )
                    )
            teachers.append(teacher)
        departments.append(Department(name=department_el.attrib["subjectKafedra"].strip(), teachers=teachers))

    return KafedraReport(
        source_path=xml_path,
        execution_time=format_execution_time(root.attrib.get("ExecutionTime2", "")),
        departments=merge_duplicate_departments(departments),
    )


def merge_duplicate_departments(departments: list[Department]) -> list[Department]:
    merged: dict[str, list[Teacher]] = defaultdict(list)
    for department in departments:
        merged[department.name].extend(department.teachers)
    return [Department(name=name, teachers=teachers) for name, teachers in merged.items()]


def render_ranking_chart(report: KafedraReport, image_path: Path, highlight: str = DEPARTMENT_NAME) -> None:
    ranking = report.ranking()
    names = [item.name for item in ranking]
    values = [item.failure_rate for item in ranking]
    colors = ["#c0392b" if name == highlight else "#9aa5b1" for name in names]

    with plt.rc_context({"font.family": installed_font_family(), "font.size": 12}):
        draw_ranking_chart(report, names, values, colors, image_path, highlight)


def draw_ranking_chart(
    report: KafedraReport,
    names: list[str],
    values: list[float],
    colors: list[str],
    image_path: Path,
    highlight: str,
) -> None:
    fig, ax = plt.subplots(figsize=(12, max(7, len(names) * 0.32)))
    positions = list(range(len(names)))
    bars = ax.barh(positions, values, color=colors)
    ax.set_yticks(positions)
    ax.set_yticklabels([f"{place}. {name}" for place, name in enumerate(names, start=1)])
    for label, name in zip(ax.get_yticklabels(), names):
        if name == highlight:
            label.set_fontweight("bold")
            label.set_color("#c0392b")
    ax.invert_yaxis()
    ax.axvline(report.failure_rate, color="#333333", linestyle="--", linewidth=1)
    ax.text(
        report.failure_rate,
        -0.9,
        f"в среднем по вузу {report.failure_rate:.1f}%".replace(".", ","),
        ha="center",
        va="bottom",
        fontsize=11,
    )
    for bar, name, value in zip(bars, names, values):
        weight = "bold" if name == highlight else "normal"
        ax.text(value + 0.5, bar.get_y() + bar.get_height() / 2, f"{value:.1f}".replace(".", ","),
                va="center", fontsize=10, fontweight=weight)
    ax.set_xlabel("Доля неаттестованных записей, %")
    ax.set_title("Кафедры вуза по доле неаттестованных (сверху — наименьшая)")
    ax.set_xlim(0, max(values) * 1.12 if values else 1)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.tight_layout()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(image_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
