"""Отчёт об аттестации в Markdown: разделы «Сводка», «Группы», «Дисциплины», «Преподаватели».

Заголовки второго уровня (##) веб-страница показывает вкладками, третьего (###) — карточками
групп и преподавателей; статус в ячейке начинается со значка ● / ▲ / ✕ и подсвечивается цветом.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import report_model as rm


REPORT_NAME = "attestation_report.md"


def cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return lines + [""]


def group_rows(groups: list[rm.GroupSummary]) -> list[list[object]]:
    return [
        [
            group.name,
            group.course or "–",
            rm.LEVEL_TITLES[group.level],
            len(group.students),
            group.fully_attested,
            rm.format_percent(group.failure_rate),
            rm.format_delta(group.delta),
            rm.status_label(group.status),
        ]
        for group in groups
    ]


def summary_section(model: rm.DepartmentModel) -> list[str]:
    lines = [
        "## Сводка",
        "",
        f"Студентов: **{model.students}** · групп: **{len(model.groups)}** · "
        f"аттестованы полностью: **{model.fully_attested}** "
        f"({rm.format_percent(rm.rate(model.fully_attested, model.students))}) · "
        f"Н/А: **{rm.format_percent(model.failure_rate)}**"
        + (f" · место кафедры: **{model.rank.place} из {model.rank.total}**" if model.rank else ""),
        "",
    ]
    lines += [f"- {line}" for line in rm.conclusions(model, critical_reference="ниже")] + [""]
    lines += ["### Группы", ""]
    lines += table(
        ["Группа", "Курс", "Уровень", "Студентов", "Аттестованы полностью", "Н/А", "Изм., п. п.", "Статус"],
        group_rows(model.groups),
    )
    lines += [f"### Дисциплины с Н/А от {rm.CRITICAL_DISCIPLINE_THRESHOLD:.0f} %", ""]
    critical = model.critical_disciplines()
    if not critical:
        return lines + ["Таких дисциплин нет.", ""]
    lines += table(
        ["Группа", "Дисциплина", "Преподаватель", "Н/А", "%"],
        [
            [item.group, item.subject, item.teacher_names, f"{item.failed} из {item.students}", rm.format_percent(item.failure_rate)]
            for item in critical
        ],
    )
    return lines


def groups_section(model: rm.DepartmentModel) -> list[str]:
    lines = ["## Группы", ""]
    for group in model.groups:
        lines += [
            f"### {group.name} · {group.course or '–'} курс · {rm.LEVEL_TITLES[group.level]}",
            "",
            f"Студентов: **{len(group.students)}** · аттестованы полностью: **{group.fully_attested}** · "
            f"Н/А: **{rm.format_percent(group.failure_rate)}** · {rm.status_label(group.status)}",
            "",
        ]
        lines += table(
            ["Дисциплина", "Преподаватель", "Н/А", "%", "0 баллов", "Почти", "Статус"],
            [
                [
                    item.subject,
                    item.teacher_names,
                    f"{item.failed} из {item.students}",
                    rm.format_percent(item.failure_rate),
                    item.zero,
                    item.near,
                    rm.status_label(item.display_status),
                ]
                for item in group.disciplines
            ],
        )
        lines += table(
            ["Студент", "Н/А дисциплин", "%", "Статус"],
            [
                [
                    student.name,
                    f"{student.failed} из {student.subjects}",
                    rm.format_percent(student.failure_rate),
                    rm.status_label(rm.status_for(student.failure_rate)),
                ]
                for student in group.students
            ],
        )
    return lines


def disciplines_section(model: rm.DepartmentModel) -> list[str]:
    items = sorted(model.disciplines, key=lambda item: (-item.failure_rate, item.group, item.subject))
    lines = ["## Дисциплины", ""]
    lines += table(
        ["Группа", "Дисциплина", "Преподаватель", "Н/А", "%", "Статус"],
        [
            [
                item.group,
                item.subject,
                item.teacher_names,
                f"{item.failed} из {item.students}",
                rm.format_percent(item.failure_rate),
                rm.status_label(item.display_status),
            ]
            for item in items
        ],
    )
    return lines


def teachers_section(model: rm.DepartmentModel) -> list[str]:
    lines = ["## Преподаватели", ""]
    if not model.teachers:
        return lines + ["Нет данных отчёта «Процент аттестаций по кафедрам».", ""]
    for teacher in model.teachers:
        lines += [
            f"### {rm.short_name(teacher.name)} · {teacher.kafedra}",
            "",
            f"Групп: **{len(teacher.groups)}** · дисциплин: **{len(teacher.subjects)}** · "
            f"оценок: **{teacher.records}** · Н/А: **{rm.format_percent(teacher.failure_rate)}** · "
            f"{rm.status_label(teacher.status)}",
            "",
        ]
        lines += table(
            ["Группа", "Дисциплина", "Н/А", "%", "Статус"],
            [
                [item.group, item.subject, f"{item.failed} из {item.students}", rm.format_percent(item.failure_rate), rm.status_label(item.display_status)]
                for item in sorted(teacher.disciplines, key=lambda item: (-item.failure_rate, item.group))
            ],
        )
    return lines


def build_markdown(model: rm.DepartmentModel) -> str:
    lines = [
        f"# Кафедра {model.department.name}: {model.title}",
        "",
        f"Данные РИТМ на {model.execution_time}. Н/А — неаттестация (балл ниже минимального). "
        f"Статус: {rm.status_label(rm.STATUS_OK)} — Н/А до {rm.WARN_THRESHOLD:.0f} %, "
        f"{rm.status_label(rm.STATUS_WARN)} — до {rm.CRIT_THRESHOLD:.0f} %, {rm.status_label(rm.STATUS_CRIT)} — выше"
        + (f"; {rm.status_label(rm.STATUS_NONE)} — у всей группы 0 баллов." if model.not_entered_disciplines() else "."),
        "",
    ]
    for section in (summary_section, groups_section, disciplines_section, teachers_section):
        lines += section(model)
    return "\n".join(lines)


def build_markdown_report(attestation_dir: Path, output_path: Path | None = None) -> Path:
    output_path = output_path or attestation_dir / REPORT_NAME
    output_path.write_text(build_markdown(rm.build_model(attestation_dir)), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Отчёт об аттестации кафедры в Markdown.")
    parser.add_argument("attestation_dir", help="Папка аттестации, например 2026-2027/нечет/1")
    args = parser.parse_args()
    print(f"Markdown готов: {build_markdown_report(Path(args.attestation_dir).resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
