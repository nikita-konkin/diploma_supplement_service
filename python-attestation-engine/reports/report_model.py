"""Сводки по аттестации кафедры — общая модель для краткого отчёта, Markdown и веб-страницы.

На вход — папка аттестации нового вида (<год>-<год+1>/<нечет|чет>/<номер>), в которой лежат
папки б/ и м/ с XML групп и AttestationByKafedra.xml с преподавателями.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import build_attestation_report as detailed
import kafedra_teachers
from department_info import DepartmentInfo, load_department


LEVEL_TITLES = {"б": "бакалавриат", "м": "магистратура"}
LEVEL_GENITIVE = {"б": "бакалавриата", "м": "магистратуры"}

WARN_THRESHOLD = 30.0  # доля неаттестаций, %: до этого значения — «норма»
CRIT_THRESHOLD = 50.0  # выше этого значения — «критично»
CRITICAL_DISCIPLINE_THRESHOLD = 85.0
NEAR_THRESHOLD_SHARE = 0.8  # «почти аттестован»: балл не ниже 80% от минимального

NBSP = "\u00a0"  # неразрывный пробел: инициалы и знак % не отрываются при переносе

STATUS_OK = "норма"
STATUS_WARN = "внимание"
STATUS_CRIT = "критично"
STATUS_NONE = "не выставлено"  # у всей группы 0 баллов: скорее всего, баллы ещё не внесены
STATUS_MARKS = {STATUS_OK: "●", STATUS_WARN: "▲", STATUS_CRIT: "✕", STATUS_NONE: "○"}
REPORT_DATA_FILE = "attestation_report.json"


def status_for(rate: float) -> str:
    if rate > CRIT_THRESHOLD:
        return STATUS_CRIT
    if rate > WARN_THRESHOLD:
        return STATUS_WARN
    return STATUS_OK


def status_label(status: str) -> str:
    return f"{STATUS_MARKS[status]} {status}"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def short_name(full_name: str) -> str:
    """«Конкин Никита Александрович» -> «Конкин Н. А.»; «Тестов Иван -» -> «Тестов И.»."""
    parts = full_name.split()
    # у иностранных студентов на месте отчества в РИТМ бывает «-»
    initials = [part for part in parts[1:3] if part[0].isalpha()]
    if not initials:
        return full_name
    return parts[0] + NBSP + NBSP.join(f"{part[0]}." for part in initials)


def rate(failed: int, total: int) -> float:
    return failed / total * 100 if total else 0.0


@dataclass
class DisciplineSummary:
    group: str
    level: str
    subject: str
    students: int = 0
    failed: int = 0
    zero: int = 0
    near: int = 0
    threshold: float = 0.0
    teachers: list[tuple[str, str]] = field(default_factory=list)  # (ФИО, кафедра)

    @property
    def failure_rate(self) -> float:
        return rate(self.failed, self.students)

    @property
    def not_entered(self) -> bool:
        """У всех студентов группы 0 баллов — это почти всегда не внесённые баллы, а не неуспеваемость."""
        return self.students > 0 and self.zero == self.students

    @property
    def status(self) -> str:
        return status_for(self.failure_rate)

    @property
    def display_status(self) -> str:
        return STATUS_NONE if self.not_entered else self.status

    @property
    def teacher_names(self) -> str:
        return ", ".join(short_name(name) for name, _ in self.teachers) or "не указан"


@dataclass
class StudentSummary:
    group: str
    name: str
    number: str
    subjects: int
    failed: int
    scores: dict[str, float] = field(default_factory=dict)  # дисциплина -> балл
    failed_subjects: set[str] = field(default_factory=set)  # у каждого студента свой минимальный балл

    @property
    def failure_rate(self) -> float:
        return rate(self.failed, self.subjects)


@dataclass
class GroupSummary:
    name: str
    level: str
    course: int | None
    execution_time: str
    disciplines: list[DisciplineSummary]
    students: list[StudentSummary]
    previous_rate: float | None = None
    # итоги той же группы на прошлой аттестации, если она выгружена рядом
    previous_failed: int | None = None
    previous_records: int | None = None
    previous_fully_attested: int | None = None
    previous_students: int | None = None

    @property
    def records(self) -> int:
        return sum(item.students for item in self.disciplines)

    @property
    def failed(self) -> int:
        return sum(item.failed for item in self.disciplines)

    @property
    def zero(self) -> int:
        return sum(item.zero for item in self.disciplines)

    @property
    def not_entered(self) -> int:
        """Неаттестации в дисциплинах, где баллы не выставлены всей группе."""
        return sum(item.failed for item in self.disciplines if item.not_entered)

    @property
    def failure_rate(self) -> float:
        return rate(self.failed, self.records)

    @property
    def fully_attested(self) -> int:
        return sum(1 for student in self.students if student.failed == 0)

    @property
    def status(self) -> str:
        return status_for(self.failure_rate)

    @property
    def delta(self) -> float | None:
        return None if self.previous_rate is None else self.failure_rate - self.previous_rate


@dataclass
class TeacherSummary:
    name: str
    kafedras: list[str] = field(default_factory=list)  # дисциплины преподавателя могут числиться за разными кафедрами
    disciplines: list[DisciplineSummary] = field(default_factory=list)

    @property
    def kafedra(self) -> str:
        return ", ".join(self.kafedras)

    @property
    def groups(self) -> set[str]:
        return {item.group for item in self.disciplines}

    @property
    def subjects(self) -> set[str]:
        return {item.subject for item in self.disciplines}

    @property
    def records(self) -> int:
        return sum(item.students for item in self.disciplines)

    @property
    def failed(self) -> int:
        return sum(item.failed for item in self.disciplines)

    @property
    def failure_rate(self) -> float:
        return rate(self.failed, self.records)

    @property
    def status(self) -> str:
        return status_for(self.failure_rate)


@dataclass
class DepartmentRank:
    place: int
    total: int
    failure_rate: float
    university_rate: float


@dataclass
class DepartmentModel:
    attestation_dir: Path
    department: DepartmentInfo
    study_year: str
    semester: str
    attestation: str
    groups: list[GroupSummary]
    teachers: list[TeacherSummary]
    rank: DepartmentRank | None
    teachers_source_time: str | None

    @property
    def title(self) -> str:
        return f"аттестация № {self.attestation}, {self.semester} семестр {self.study_year} учебного года"

    @property
    def execution_time(self) -> str:
        times = sorted({group.execution_time for group in self.groups if group.execution_time})
        return times[-1] if times else ""

    @property
    def disciplines(self) -> list[DisciplineSummary]:
        return [item for group in self.groups for item in group.disciplines]

    @property
    def students(self) -> int:
        return sum(len(group.students) for group in self.groups)

    @property
    def records(self) -> int:
        return sum(group.records for group in self.groups)

    @property
    def failed(self) -> int:
        return sum(group.failed for group in self.groups)

    @property
    def zero(self) -> int:
        return sum(group.zero for group in self.groups)

    @property
    def near(self) -> int:
        return sum(item.near for item in self.disciplines)

    @property
    def failure_rate(self) -> float:
        return rate(self.failed, self.records)

    @property
    def fully_attested(self) -> int:
        return sum(group.fully_attested for group in self.groups)

    @property
    def not_entered(self) -> int:
        return sum(group.not_entered for group in self.groups)

    def not_entered_disciplines(self) -> list[DisciplineSummary]:
        return [item for item in self.disciplines if item.not_entered]

    def comparison(self) -> dict | None:
        """Динамика к прошлой аттестации по группам, у которых она есть: доля Н/А и доля аттестованных полностью."""
        groups = [group for group in self.groups if group.previous_records]
        if not groups:
            return None
        records = sum(group.records for group in groups)
        failed = sum(group.failed for group in groups)
        students = sum(len(group.students) for group in groups)
        fully = sum(group.fully_attested for group in groups)
        previous_records = sum(group.previous_records for group in groups)
        previous_failed = sum(group.previous_failed for group in groups)
        previous_students = sum(group.previous_students for group in groups)
        previous_fully = sum(group.previous_fully_attested for group in groups)
        return {
            "attestation": int(self.attestation) - 1,
            "groups": len(groups),
            "failure_rate": rate(previous_failed, previous_records),
            "failure_delta": rate(failed, records) - rate(previous_failed, previous_records),
            "fully_attested_rate": rate(previous_fully, previous_students),
            "fully_attested_delta": rate(fully, students) - rate(previous_fully, previous_students),
        }

    def groups_of(self, level: str) -> list[GroupSummary]:
        return [group for group in self.groups if group.level == level]

    def critical_disciplines(self) -> list[DisciplineSummary]:
        # дисциплины без выставленных баллов перечислены в выводах отдельно, это не неуспеваемость
        items = [
            item for item in self.disciplines
            if item.failure_rate >= CRITICAL_DISCIPLINE_THRESHOLD and not item.not_entered
        ]
        return sorted(items, key=lambda item: (-item.failure_rate, -item.failed, item.group, item.subject))


def parse_period(attestation_dir: Path) -> tuple[str, str, str]:
    semester = {"нечет": "нечётный", "чет": "чётный"}.get(attestation_dir.parent.name, attestation_dir.parent.name)
    return attestation_dir.parent.parent.name, semester, attestation_dir.name


def parse_course(group_name: str) -> int | None:
    match = re.search(r"-(\d)", group_name)
    return int(match.group(1)) if match else None


def load_teacher_index(attestation_dir: Path) -> tuple[dict[tuple[str, str], list[tuple[str, str]]], kafedra_teachers.KafedraReport | None]:
    path = attestation_dir / kafedra_teachers.KAFEDRA_REPORT_FILE
    if not path.exists():
        return {}, None
    report = kafedra_teachers.parse_kafedra_report(path)
    index: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for department in report.departments:
        for teacher in department.teachers:
            for record in teacher.records:
                key = (normalize(record.group), normalize(record.subject))
                if (teacher.name, department.name) not in index[key]:
                    index[key].append((teacher.name, department.name))
    return index, report


def summarize_group(
    report: detailed.GroupReport, level: str, teacher_index: dict[tuple[str, str], list[tuple[str, str]]]
) -> GroupSummary:
    disciplines: dict[str, DisciplineSummary] = {}
    students = []
    for student in report.students:
        students.append(
            StudentSummary(
                group=report.name,
                name=student.full_name,
                number=student.student_number,
                subjects=len(student.subjects),
                failed=student.failed_count,
                scores={normalize(subject.name): subject.att_ball for subject in student.subjects},
                failed_subjects={normalize(subject.name) for subject in student.subjects if not subject.is_attested},
            )
        )
        for subject in student.subjects:
            name = normalize(subject.name)
            item = disciplines.setdefault(
                name,
                DisciplineSummary(
                    group=report.name,
                    level=level,
                    subject=name,
                    teachers=teacher_index.get((normalize(report.name), name), []),
                ),
            )
            item.students += 1
            item.threshold = max(item.threshold, subject.threshold)
            if not subject.is_attested:
                item.failed += 1
                if subject.att_ball == 0:
                    item.zero += 1
                elif subject.threshold and subject.att_ball >= NEAR_THRESHOLD_SHARE * subject.threshold:
                    item.near += 1

    return GroupSummary(
        name=report.name,
        level=level,
        course=parse_course(report.name),
        execution_time=report.execution_time.replace("по состоянию на:", "").strip(),
        disciplines=sorted(disciplines.values(), key=lambda item: (-item.failure_rate, item.subject)),
        students=sorted(students, key=lambda item: (-item.failed, item.name)),
    )


def previous_groups(attestation_dir: Path, level: str) -> dict[str, detailed.GroupReport]:
    """Группы прошлой аттестации того же семестра, если её папка лежит рядом."""
    try:
        number = int(attestation_dir.name)
    except ValueError:
        return {}
    previous_dir = attestation_dir.parent / str(number - 1) / level
    if number <= 1 or not previous_dir.is_dir() or not any(previous_dir.glob("*.xml")):
        return {}
    return {group.name: group for group in detailed.parse_all_groups(previous_dir)}


def build_teachers(groups: list[GroupSummary]) -> list[TeacherSummary]:
    teachers: dict[str, TeacherSummary] = {}
    for group in groups:
        for item in group.disciplines:
            for name, kafedra in item.teachers:
                teacher = teachers.setdefault(name, TeacherSummary(name=name))
                if kafedra not in teacher.kafedras:
                    teacher.kafedras.append(kafedra)
                if item not in teacher.disciplines:
                    teacher.disciplines.append(item)
    return sorted(teachers.values(), key=lambda item: (-item.failure_rate, item.name))


def build_model(attestation_dir: Path, level: str | None = None) -> DepartmentModel:
    """Модель по всем группам кафедры или, с level («б», «м»), по одному уровню образования."""
    info = load_department(attestation_dir)
    teacher_index, kafedra_report = load_teacher_index(attestation_dir)
    groups: list[GroupSummary] = []
    for level_key in [level] if level else LEVEL_TITLES:
        level_dir = attestation_dir / level_key
        if not level_dir.is_dir() or not any(level_dir.glob("*.xml")):
            continue
        previous = previous_groups(attestation_dir, level_key)
        for report in sorted(detailed.parse_all_groups(level_dir), key=lambda item: (parse_course(item.name) or 0, item.name)):
            summary = summarize_group(report, level_key, teacher_index)
            before = previous.get(summary.name)
            if before is not None and before.total_records:
                summary.previous_rate = before.failure_rate
                summary.previous_failed = before.total_failed
                summary.previous_records = before.total_records
                summary.previous_students = len(before.students)
                summary.previous_fully_attested = sum(1 for student in before.students if student.failed_count == 0)
            groups.append(summary)
    if not groups:
        folders = f"{level}/" if level else "б/ и м/"
        raise FileNotFoundError(f"В {attestation_dir} нет XML групп в папках {folders}.")

    rank = None
    # «Процент аттестаций по кафедрам» не содержит групп магистратуры: место кафедры о ней ничего не говорит
    if kafedra_report is not None and level != "м":
        department = kafedra_report.department(info.name)
        place = kafedra_report.rank_of(info.name)
        if department is not None and place is not None:
            rank = DepartmentRank(
                place=place,
                total=len(kafedra_report.ranking()),
                failure_rate=department.failure_rate,
                university_rate=kafedra_report.failure_rate,
            )

    study_year, semester, attestation = parse_period(attestation_dir)
    return DepartmentModel(
        attestation_dir=attestation_dir,
        department=info,
        study_year=study_year,
        semester=semester,
        attestation=attestation,
        groups=groups,
        teachers=build_teachers(groups),
        rank=rank,
        teachers_source_time=kafedra_report.execution_time if kafedra_report else None,
    )


def format_percent(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + NBSP + "%"


def plural(number: int, forms: tuple[str, str, str]) -> str:
    """plural(62, ("оценка", "оценки", "оценок")) -> «оценки»."""
    if number % 10 == 1 and number % 100 != 11:
        return forms[0]
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return forms[1]
    return forms[2]


def sentence(text: str) -> str:
    return text if text.endswith(".") else text + "."


def format_delta(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:+.1f}".replace(".", ",").replace("-", "−")


def conclusions(model: DepartmentModel, critical_reference: str = "в таблице 3") -> list[str]:
    """Автоматические выводы для краткого отчёта и сводки на сайте."""
    lines = []
    critical_groups = [group.name for group in model.groups if group.status == STATUS_CRIT]
    if critical_groups:
        lines.append(
            f"Доля неаттестаций выше {CRIT_THRESHOLD:.0f} % в группах: {', '.join(critical_groups)}."
        )
    not_fully = model.students - model.fully_attested
    lines.append(
        f"По всем дисциплинам аттестованы {model.fully_attested} из {model.students} студентов "
        f"({format_percent(rate(model.fully_attested, model.students))}); остальные {not_fully} "
        f"имеют хотя бы одну неаттестацию."
    )
    critical = model.critical_disciplines()
    if critical:
        lines.append(
            f"Дисциплин с долей неаттестаций {CRITICAL_DISCIPLINE_THRESHOLD:.0f} % и более: {len(critical)} "
            f"(перечень — {critical_reference})."
        )
    if model.failed:
        lines.append(
            f"Нулевые баллы составляют {format_percent(rate(model.zero, model.failed))} неаттестаций; "
            f"ещё {model.near} {plural(model.near, ('оценка', 'оценки', 'оценок'))} ниже порога менее чем на "
            f"{(1 - NEAR_THRESHOLD_SHARE) * 100:.0f} % — эти студенты близки к аттестации."
        )
    not_entered = model.not_entered_disciplines()
    if not_entered:
        groups = {item.group for item in not_entered}
        lines.append(
            f"Баллы не выставлены (у всей группы 0) по {len(not_entered)} "
            f"{plural(len(not_entered), ('дисциплине', 'дисциплинам', 'дисциплинам'))} в {len(groups)} "
            f"{plural(len(groups), ('группе', 'группах', 'группах'))}: это {format_percent(rate(model.not_entered, model.failed))} "
            f"неаттестаций; без них доля Н/А составила бы "
            f"{format_percent(rate(model.failed - model.not_entered, model.records - model.not_entered))}."
        )
    department_teachers = [
        teacher for teacher in model.teachers
        if model.department.name in teacher.kafedras and teacher.status == STATUS_CRIT
    ]
    if department_teachers:
        names = ", ".join(short_name(teacher.name) for teacher in department_teachers)
        lines.append(sentence(f"Доля неаттестаций выше {CRIT_THRESHOLD:.0f} % у преподавателей кафедры: {names}"))
    if model.rank is not None:
        lines.append(
            f"По доле неаттестаций кафедра {model.department.name} занимает {model.rank.place}-е место из "
            f"{model.rank.total} кафедр вуза ({format_percent(model.rank.failure_rate)} при среднем "
            f"{format_percent(model.rank.university_rate)})."
        )
    return lines


def model_data(model: DepartmentModel) -> dict:
    """Данные для графиков на сайте: сводка, группы с составом Н/А и баллы студентов."""

    def number(value: float | None) -> float | None:
        return None if value is None else round(value, 2)

    groups = []
    for group in model.groups:
        disciplines = sorted(group.disciplines, key=lambda item: (-item.failure_rate, item.subject))
        groups.append({
            "name": group.name,
            "level": group.level,
            "course": group.course,
            "students": len(group.students),
            "fully_attested": group.fully_attested,
            "records": group.records,
            "failed": group.failed,
            "zero": group.zero - group.not_entered,
            "not_entered": group.not_entered,
            "failure_rate": number(group.failure_rate),
            "previous_rate": number(group.previous_rate),
            "status": group.status,
            "disciplines": [
                {
                    "subject": item.subject,
                    "teachers": [short_name(name) for name, _ in item.teachers],
                    "threshold": number(item.threshold),
                    "students": item.students,
                    "failed": item.failed,
                    "zero": item.zero,
                    "near": item.near,
                    "not_entered": item.not_entered,
                }
                for item in disciplines
            ],
            "students_scores": [
                {
                    "name": student.name,
                    "failed": student.failed,
                    "subjects": student.subjects,
                    "scores": [number(student.scores.get(item.subject)) for item in disciplines],
                }
                for student in group.students
            ],
        })
    rank = model.rank
    return {
        "department": model.department.name,
        "title": model.title,
        "execution_time": model.execution_time,
        "thresholds": {"warn": WARN_THRESHOLD, "crit": CRIT_THRESHOLD, "near_share": NEAR_THRESHOLD_SHARE},
        "summary": {
            "students": model.students,
            "groups": len(model.groups),
            "fully_attested": model.fully_attested,
            "records": model.records,
            "failed": model.failed,
            "zero": model.zero - model.not_entered,
            "near": model.near,
            "not_entered": model.not_entered,
            "not_entered_disciplines": len(model.not_entered_disciplines()),
            "failure_rate": number(model.failure_rate),
            "comparison": None if model.comparison() is None else {
                key: number(value) if isinstance(value, float) else value
                for key, value in model.comparison().items()
            },
            "rank": None if rank is None else {
                "place": rank.place,
                "total": rank.total,
                "failure_rate": number(rank.failure_rate),
                "university_rate": number(rank.university_rate),
            },
        },
        "groups": groups,
    }


def write_report_data(attestation_dir: Path, output_path: Path | None = None) -> Path:
    path = output_path or attestation_dir / REPORT_DATA_FILE
    path.write_text(json.dumps(model_data(build_model(attestation_dir)), ensure_ascii=False), encoding="utf-8")
    return path
