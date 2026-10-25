"""Единый запуск: выгрузка XML с портала РИТМ -> графики и текстовый анализ -> отчёт DOCX.

Примеры:
    python make_report.py --att 1                      # текущий семестр, бакалавриат и магистратура
    python make_report.py --att 2 --year 2025 --semester чет --level б
    python make_report.py --att 1 --skip-fetch         # пересобрать отчёт по уже скачанным XML
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import attestation_analysis
import build_attestation_report
import build_markdown_report
import build_short_report
import report_model
import ritm_fetch
from department_info import DepartmentInfo


REPORT_NAMES = {
    "б": "attestation_report_bachelor.docx",
    "м": "attestation_report_master.docx",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Отчёт об аттестации групп кафедры ИТРС: выгрузка с портала, анализ, DOCX."
    )
    ritm_fetch.add_period_arguments(parser)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Не обращаться к порталу, использовать уже скачанные XML.",
    )
    return parser.parse_args()


def fetch_previous(
    session: ritm_fetch.requests.Session,
    period: ritm_fetch.AttestationPeriod,
    root: Path,
    levels: list[str],
    log: Callable[[str], None],
    faculty: str,
    codes: set[str] | None,
) -> None:
    """Прошлая аттестация того же семестра — для динамики; уже выгруженная не скачивается заново."""
    if period.attestation <= 1:
        return
    previous = ritm_fetch.AttestationPeriod(period.study_year, period.odd_semester, period.attestation - 1)
    for level in levels:
        if any(previous.directory(root, level).glob("*.xml")):
            continue
        try:
            ritm_fetch.fetch_level(
                session, previous, level, root,
                lambda message: log(f"Аттестация №{previous.attestation} для динамики. {message.strip()}"),
                faculty, codes,
            )
        except ritm_fetch.RitmError as exc:
            # без прошлой аттестации отчёт всё равно строится, только без динамики
            log(f"Аттестация №{previous.attestation} недоступна, динамики не будет: {exc}")


def build_all(
    session: ritm_fetch.requests.Session | None,
    period: ritm_fetch.AttestationPeriod,
    root: Path,
    levels: list[str],
    log: Callable[[str], None] = print,
    department: DepartmentInfo | None = None,
    faculty: str = ritm_fetch.FACULTY_ID,
    codes: set[str] | None = None,
) -> Path:
    """Выгрузка (если есть сеанс портала), анализ и все отчёты; возвращает папку аттестации.

    department, faculty и codes (направления групп, «ИТС(о)») задают кафедру; без них — ИТРС.
    """
    attestation_dir = period.attestation_directory(root)
    if department is not None:
        department.save(attestation_dir)
    department_name = department.name if department is not None else ritm_fetch.DEPARTMENT_NAME
    if session is not None:
        ritm_fetch.fetch_kafedra_report(session, period, root, log, department_name)
        fetch_previous(session, period, root, levels, log, faculty, codes)
    for level in levels:
        data_dir = period.directory(root, level)
        if session is not None:
            ritm_fetch.fetch_level(session, period, level, root, log, faculty, codes)
        elif not data_dir.is_dir():
            raise ritm_fetch.RitmError(f"Нет папки с данными: {data_dir}")

        log(f"Анализ: {data_dir}")
        attestation_analysis.run_analysis(data_dir)
        report_path = build_attestation_report.build_report(data_dir, data_dir / REPORT_NAMES[level])
        log(f"Отчёт готов: {report_path}")

    log(f"Краткий отчёт: {build_short_report.build_short_report(attestation_dir)}")
    log(f"Markdown: {build_markdown_report.build_markdown_report(attestation_dir)}")
    log(f"Данные для графиков: {report_model.write_report_data(attestation_dir)}")
    return attestation_dir


def main() -> int:
    args = parse_args()
    period = ritm_fetch.AttestationPeriod(args.year, args.semester, args.att)
    print(period.label)

    try:
        session = None if args.skip_fetch else ritm_fetch.open_session()
        build_all(session, period, Path(args.root).resolve(), ritm_fetch.selected_levels(args.level))
    except (ritm_fetch.RitmError, ritm_fetch.requests.RequestException) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
