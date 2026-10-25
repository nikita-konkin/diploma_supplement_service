"""Made-up RITM exports for tests: invented names and scores, the same XML shape as the portal's.

Real student data must never be committed, so every test builds its files here.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import quoteattr

SUBJECTS = ["Базы данных", "Сети и телекоммуникации", "Программирование", "Высшая математика"]
TEACHERS = {
    "Базы данных": ("ИТРС", "Петров Пётр Петрович"),
    "Сети и телекоммуникации": ("ИТРС", "Сидорова Анна Сергеевна"),
    "Программирование": ("ИТРС", "Петров Пётр Петрович"),
    "Высшая математика": ("ВМ", "Кузнецов Олег Иванович"),
}


def group_xml(group: str, scores: list[list[float]], threshold: str = "13 - 19,5") -> str:
    students = []
    for index, row in enumerate(scores, start=1):
        subjects = "".join(
            f'<SubjectName SubjectName={quoteattr(subject)}>'
            f'<minBall minBall="{threshold}" AttBall="{str(score).replace(".", ",")}" /></SubjectName>'
            for subject, score in zip(SUBJECTS, row)
        )
        students.append(
            f'<stFIO><Textbox48 Textbox48="{index}"><stFIO stFIO="Студент{index} Тест Тестович">'
            f'<StudentNumber StudentNumber="{1000 + index}"><SubjectName_Collection>{subjects}'
            f"</SubjectName_Collection></StudentNumber></stFIO></Textbox48></stFIO>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<Report Name="AttestationByGroup.rdl" ReportTitle="Аттестация №1 студентов группы  {group}" '
        'ExecutionTime="по состоянию на:01.10.2026 12:00:00" xmlns="AttestationByGroup.rdl">'
        f"<Tablix1><stFIO_Collection>{''.join(students)}</stFIO_Collection></Tablix1></Report>"
    )


def kafedra_xml(groups: dict[str, list[list[float]]]) -> str:
    """Teachers of the subjects above, plus one other department for the ranking."""
    by_department: dict[str, dict[str, list[str]]] = {}
    for group, scores in groups.items():
        for column, subject in enumerate(SUBJECTS):
            department, teacher = TEACHERS[subject]
            total = len(scores)
            attested = sum(1 for row in scores if row[column] >= 13)
            by_department.setdefault(department, {}).setdefault(teacher, []).append(
                f"<egName_Collection><egName egName={quoteattr(group)}><sbj_Collection>"
                f'<sbj sbj={quoteattr(subject)} total="{total}" attested="{attested}" />'
                "</sbj_Collection></egName></egName_Collection>"
            )
    by_department.setdefault("ФИЗ", {})["Морозов Иван Ильич"] = [
        '<egName_Collection><egName egName="ЭМ(о)-11"><sbj_Collection>'
        '<sbj sbj="Физика" total="20" attested="18" /></sbj_Collection></egName></egName_Collection>'
    ]
    departments = "".join(
        f"<subjectKafedra subjectKafedra={quoteattr(name)}><lectorFIO_Collection>"
        + "".join(
            f"<lectorFIO lectorFIO={quoteattr(teacher)}>{''.join(parts)}</lectorFIO>"
            for teacher, parts in teachers.items()
        )
        + "</lectorFIO_Collection></subjectKafedra>"
        for name, teachers in by_department.items()
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<Report Name="AttestationByKafedra.rdl" ExecutionTime2="2026-10-01T12:00:00+03:00" '
        f'xmlns="AttestationByKafedra.rdl"><Tablix5><subjectKafedra_Collection>{departments}'
        "</subjectKafedra_Collection></Tablix5></Report>"
    )


BACHELOR = {
    "ИТС(о)-11": [[20, 5, 18, 14], [0, 15, 13, 2], [17, 19, 0, 16], [14, 3, 15, 0]],
    "ИСТ(о)-21": [[19, 19, 19, 19], [12, 14, 16, 5], [0, 0, 0, 0]],
}
MASTER = {"ИТСм(о)-11": [[18, 17, 0, 19], [16, 15, 14, 13]]}


def write_attestation(root: Path, year: int = 2026, odd: bool = True, attestation: int = 1) -> Path:
    """The folder layout fetch_level and fetch_kafedra_report leave behind; returns the attestation folder."""
    attestation_dir = root / f"{year}-{year + 1}" / ("нечет" if odd else "чет") / str(attestation)
    for level, groups in (("б", BACHELOR), ("м", MASTER)):
        level_dir = attestation_dir / level
        level_dir.mkdir(parents=True, exist_ok=True)
        for group, scores in groups.items():
            (level_dir / f"{group}.xml").write_text(group_xml(group, scores), encoding="utf-8")
    (attestation_dir / "AttestationByKafedra.xml").write_text(kafedra_xml(BACHELOR), encoding="utf-8")
    return attestation_dir
