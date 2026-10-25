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
import ritm_fetch


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


def build_all(
    session: ritm_fetch.requests.Session | None,
    period: ritm_fetch.AttestationPeriod,
    root: Path,
    levels: list[str],
    log: Callable[[str], None] = print,
) -> Path:
    """Выгрузка (если есть сеанс портала), анализ и все отчёты; возвращает папку аттестации."""
    if session is not None:
        ritm_fetch.fetch_kafedra_report(session, period, root, log)
    for level in levels:
        data_dir = period.directory(root, level)
        if session is not None:
            ritm_fetch.fetch_level(session, period, level, root, log)
        elif not data_dir.is_dir():
            raise ritm_fetch.RitmError(f"Нет папки с данными: {data_dir}")

        log(f"Анализ: {data_dir}")
        attestation_analysis.run_analysis(data_dir)
        report_path = build_attestation_report.build_report(data_dir, data_dir / REPORT_NAMES[level])
        log(f"Отчёт готов: {report_path}")

    attestation_dir = period.attestation_directory(root)
    log(f"Краткий отчёт: {build_short_report.build_short_report(attestation_dir)}")
    log(f"Markdown: {build_markdown_report.build_markdown_report(attestation_dir)}")
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
