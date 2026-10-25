"""Выгрузка отчёта «Аттестация по выбранной группе» с портала РИТМ (portal.volgatech.net).

Скрипт входит на портал через форму входа, получает у сервера отчётов (SSRS) список
групп факультета, оставляет группы кафедры и сохраняет XML каждой группы в папку

    <root>/<год>-<год+1>/<нечет|чет>/<номер аттестации>/<б|м>/<группа>.xml

Пароль спрашивается при первом запуске и хранится в Связке ключей (keyring).
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys
import time
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape

warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import requests  # noqa: E402


PORTAL = "https://portal.volgatech.net"
LOGON_URL = f"{PORTAL}/CookieAuth.dll?Logon"
SOAP_URL = f"{PORTAL}/_vti_bin/ReportServer/ReportService2010.asmx"
RENDER_URL = f"{PORTAL}/_vti_bin/ReportServer"
REPORT_PATH = f"{PORTAL}/RITM/DocLib1/Отчеты по факультетам/AttestationByGroup.rdl"
KAFEDRA_REPORT_PATH = f"{PORTAL}/RITM/DocLib1/AttestationByKafedra.rdl"
KAFEDRA_REPORT_FILE = "AttestationByKafedra.xml"  # лежит рядом с папками б/м, а не внутри них
DEPARTMENT_NAME = "ИТРС"
RS_NS = "http://schemas.microsoft.com/sqlserver/reporting/2010/03/01/ReportServer"

KEYRING_SERVICE = "ritm-portal"
KEYRING_USERNAME_KEY = "__username__"

FACULTY_ID = "1857"  # РТФ
GROUP_PATTERN = re.compile(r"^(ИТС|ИСТ)м?\(о\)-\d+$")  # очные группы кафедры ИТРС
LEVELS = {"б": 0, "м": 1}  # значение параметра isMagistr
LEVEL_TITLES = {"б": "бакалавриат", "м": "магистратура"}
REQUEST_PAUSE_SEC = 0.3


class RitmError(RuntimeError):
    pass


class PortalSessionExpired(RitmError):
    """Портал больше не считает сеанс вошедшим: нужен новый вход."""


@dataclass(frozen=True)
class AttestationPeriod:
    study_year: int  # год начала учебного года: 2026 = 2026-2027
    odd_semester: bool
    attestation: int

    @property
    def label(self) -> str:
        semester = "нечётный" if self.odd_semester else "чётный"
        return (
            f"{self.study_year}-{self.study_year + 1} уч. год, {semester} семестр, "
            f"аттестация №{self.attestation}"
        )

    def attestation_directory(self, root: Path) -> Path:
        semester = "нечет" if self.odd_semester else "чет"
        return root / f"{self.study_year}-{self.study_year + 1}" / semester / str(self.attestation)

    def directory(self, root: Path, level: str) -> Path:
        return self.attestation_directory(root) / level


@dataclass(frozen=True)
class StudyGroup:
    group_id: str
    name: str


def current_period_defaults(today: date | None = None) -> tuple[int, bool]:
    """Учебный год и семестр по текущей дате: сентябрь-январь — нечётный, февраль-август — чётный."""
    today = today or date.today()
    if today.month >= 9:
        return today.year, True
    if today.month == 1:
        return today.year - 1, True
    return today.year - 1, False


def parse_semester(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"odd", "нечет", "нечёт", "нечетный", "нечётный", "1"}:
        return True
    if normalized in {"even", "чет", "чёт", "четный", "чётный", "2", "0"}:
        return False
    raise argparse.ArgumentTypeError(f"Непонятный семестр: {value}. Используйте odd/нечет или even/чет.")


def add_period_arguments(parser: argparse.ArgumentParser) -> None:
    default_year, default_odd = current_period_defaults()
    parser.add_argument("--att", type=int, required=True, choices=[1, 2, 3], help="Номер аттестации.")
    parser.add_argument(
        "--year",
        type=int,
        default=default_year,
        help=f"Год начала учебного года (2026 = 2026-2027). По умолчанию {default_year}.",
    )
    parser.add_argument(
        "--semester",
        type=parse_semester,
        default=default_odd,
        help="Семестр: odd/нечет или even/чет. По умолчанию — по текущей дате.",
    )
    parser.add_argument(
        "--level",
        choices=["б", "м", "all"],
        default="all",
        help="б — бакалавриат, м — магистратура, all — оба (по умолчанию).",
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent),
        help="Корневая папка с данными. По умолчанию — папка скрипта.",
    )


def selected_levels(level: str) -> list[str]:
    return list(LEVELS) if level == "all" else [level]


# --- Учётные данные -------------------------------------------------------------------------


# keyring нужен только для запуска из командной строки; веб-сервис хранит пароль сам
def read_credentials(force_prompt: bool = False, previous_username: str = "") -> tuple[str, str]:
    import keyring

    username = None if force_prompt else keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
    password = keyring.get_password(KEYRING_SERVICE, username) if username else None

    if not username:
        hint = f" [{previous_username}]" if previous_username else ""
        username = input(f"Логин портала (Домен\\пользователь){hint}: ").strip() or previous_username
    if not password:
        password = getpass.getpass(f"Пароль для {username}: ")
    if not username or not password:
        raise RitmError("Логин и пароль не указаны.")
    return username, password


def save_credentials(username: str, password: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, username)
    keyring.set_password(KEYRING_SERVICE, username, password)


def forget_credentials() -> None:
    import keyring
    import keyring.errors

    username = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
    for key in filter(None, [username, KEYRING_USERNAME_KEY]):
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass


# --- Сеанс портала --------------------------------------------------------------------------


def is_logon_page(response: requests.Response) -> bool:
    return "CookieAuth.dll" in response.url or b'id="logonForm"' in response.content[:20000]


def ensure_authenticated(response: requests.Response) -> None:
    if is_logon_page(response):
        raise PortalSessionExpired("Портал вернул страницу входа: сеанс не авторизован или истёк.")
    if response.status_code == 401:
        raise PortalSessionExpired("Портал ответил 401 Unauthorized.")


def login(username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (ritm_fetch)"
    response = session.post(
        LOGON_URL,
        data={
            "curl": "Z2FRITMZ2FDocLib1Z2FFormsZ2FAllItems.aspx",
            "flags": "0",
            "forcedownlevel": "0",
            "formdir": "12",
            "trusted": "4",
            "username": username,
            "password": password,
            "SubmitCreds": "Log On",
        },
        timeout=60,
    )
    if is_logon_page(response):
        raise RitmError("Неверный логин или пароль.")
    response.raise_for_status()
    return session


def open_session(max_attempts: int = 3) -> requests.Session:
    """Входит на портал с паролем из Связки ключей; при ошибке спрашивает заново."""
    force_prompt = False
    username = ""
    for _ in range(max_attempts):
        username, password = read_credentials(force_prompt, username)
        try:
            session = login(username, password)
            list_groups(session, AttestationPeriod(*current_period_defaults(), 1), "б")
        except RitmError as exc:
            print(f"Вход не удался: {exc}", file=sys.stderr)
            forget_credentials()
            force_prompt = True
            continue
        save_credentials(username, password)
        print(f"Вход на портал выполнен: {username}")
        return session
    raise RitmError(f"Не удалось войти на портал за {max_attempts} попытки.")


# --- Сервер отчётов -------------------------------------------------------------------------


def soap_call(session: requests.Session, operation: str, inner_xml: str) -> ET.Element:
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
        f'<{operation} xmlns="{RS_NS}">{inner_xml}</{operation}>'
        "</soap:Body></soap:Envelope>"
    )
    response = session.post(
        SOAP_URL,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{RS_NS}/{operation}",
        },
        timeout=120,
    )
    ensure_authenticated(response)
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise RitmError(f"Сервер отчётов вернул не XML (HTTP {response.status_code}).") from exc
    fault = root.find(".//faultstring")
    if fault is not None:
        raise RitmError(f"Ошибка сервера отчётов: {fault.text}")
    response.raise_for_status()
    return root


def parameter_values(values: dict[str, object]) -> str:
    return "".join(
        f"<ParameterValue><Name>{escape(name)}</Name><Value>{escape(str(value))}</Value></ParameterValue>"
        for name, value in values.items()
    )


def report_parameters(period: AttestationPeriod, level: str, faculty: str = FACULTY_ID) -> dict[str, object]:
    return {
        "studyYear": period.study_year,
        "oddSemestr": 1 if period.odd_semester else 0,
        "attNum": period.attestation,
        "isMagistr": LEVELS[level],
        "faculty": faculty,
    }


def parameter_choices(
    session: requests.Session, values: dict[str, object], name: str
) -> list[tuple[str, str]]:
    """Варианты параметра отчёта «Аттестация по выбранной группе»: (значение, подпись)."""
    root = soap_call(
        session,
        "GetItemParameters",
        f"<ItemPath>{escape(REPORT_PATH)}</ItemPath><ForRendering>true</ForRendering>"
        f"<Values>{parameter_values(values)}</Values>",
    )
    for parameter in root.iter(f"{{{RS_NS}}}ItemParameter"):
        if parameter.findtext(f"{{{RS_NS}}}Name") == name:
            return [
                (value.findtext(f"{{{RS_NS}}}Value", ""), value.findtext(f"{{{RS_NS}}}Label", "").strip())
                for value in parameter.iter(f"{{{RS_NS}}}ValidValue")
            ]
    raise RitmError(f"В отчёте не найден параметр {name}.")


def list_faculties(session: requests.Session, period: AttestationPeriod) -> list[tuple[str, str]]:
    values = report_parameters(period, "б")
    del values["faculty"]
    return parameter_choices(session, values, "faculty")


def list_groups(
    session: requests.Session, period: AttestationPeriod, level: str, faculty: str = FACULTY_ID
) -> list[StudyGroup]:
    return [
        StudyGroup(group_id=value, name=label)
        for value, label in parameter_choices(session, report_parameters(period, level, faculty), "eduDroup")
    ]


def group_code(name: str) -> str:
    """Направление и форма обучения группы: «ИТС(о)-11» -> «ИТС(о)», «ИТСм(о)-21» -> «ИТСм(о)»."""
    return name.rsplit("-", 1)[0] if "-" in name else name


def department_groups(groups: list[StudyGroup], codes: set[str] | None = None) -> list[StudyGroup]:
    """Группы кафедры: по выбранным направлениям, без них — по шаблону групп ИТРС."""
    selected = (
        (group for group in groups if group_code(group.name) in codes)
        if codes is not None
        else (group for group in groups if GROUP_PATTERN.match(group.name))
    )
    return sorted(selected, key=lambda group: group.name)


def render_xml(
    session: requests.Session, report_path: str, params: list[tuple[str, object]], what: str
) -> tuple[bytes, ET.Element]:
    """Строит отчёт в формате XML; params — список пар, чтобы передавать многозначные параметры."""
    url = (
        f"{RENDER_URL}?{quote(report_path, safe='')}"
        f"&rs:Command=Render&rs:Format=XML&{urlencode(params)}"
    )
    response = session.get(url, timeout=180)
    ensure_authenticated(response)
    response.raise_for_status()
    try:
        return response.content, ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise RitmError(f"Отчёт «{what}» пришёл не в формате XML.") from exc


def render_group_xml(
    session: requests.Session,
    period: AttestationPeriod,
    level: str,
    group: StudyGroup,
    faculty: str = FACULTY_ID,
) -> bytes:
    params = {**report_parameters(period, level, faculty), "eduDroup": group.group_id, "showBalls": 1}
    content, root = render_xml(session, REPORT_PATH, list(params.items()), group.name)
    title = root.attrib.get("ReportTitle", "")
    if group.name not in title:
        raise RitmError(f"Неожиданный заголовок отчёта для {group.name}: {title!r}")
    return content


def fetch_kafedra_report(
    session: requests.Session,
    period: AttestationPeriod,
    root_dir: Path,
    log: Callable[[str], None] = print,
    department: str = DEPARTMENT_NAME,
) -> Path:
    """«Процент аттестаций по кафедрам»: все кафедры вуза с разбивкой по преподавателям."""
    content, root = fetch_kafedra_xml(session, period)

    departments = kafedra_departments(root)
    if department not in departments:
        # Отчёт всё равно нужен: без него нет преподавателей, но аттестация групп строится
        log(f"В отчёте по кафедрам нет кафедры {department}: места кафедры и её преподавателей не будет")

    path = period.attestation_directory(root_dir) / KAFEDRA_REPORT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    log(f"Отчёт по кафедрам: {len(departments)} кафедр -> {path}")
    return path


def kafedra_departments(root: ET.Element) -> list[str]:
    """Кафедры из XML «Процент аттестаций по кафедрам», без повторов, по алфавиту."""
    names = {el.attrib.get("subjectKafedra", "").strip() for el in root.iter() if el.tag.endswith("}subjectKafedra")}
    return sorted(name for name in names if name)


def fetch_kafedra_xml(session: requests.Session, period: AttestationPeriod) -> tuple[bytes, ET.Element]:
    params: list[tuple[str, object]] = [
        ("studyYear", period.study_year),
        ("oddSemestr", 1 if period.odd_semester else 0),
        ("numAtt", period.attestation),
        ("prepodAssigned", 3),  # все преподаватели, и закреплённые, и нет
        ("onlyFilled", 0),  # «Учесть нулевых»: да
    ]
    params += [("courseNum", course) for course in range(1, 6)]
    return render_xml(session, KAFEDRA_REPORT_PATH, params, "Процент аттестаций по кафедрам")


def fetch_level(
    session: requests.Session,
    period: AttestationPeriod,
    level: str,
    root_dir: Path,
    log: Callable[[str], None] = print,
    faculty: str = FACULTY_ID,
    codes: set[str] | None = None,
) -> list[Path]:
    output_dir = period.directory(root_dir, level)
    groups = department_groups(list_groups(session, period, level, faculty), codes)
    if not groups:
        raise RitmError(f"Не найдено групп кафедры ({LEVEL_TITLES[level]}) для периода: {period.label}")

    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"{LEVEL_TITLES[level].capitalize()}: {len(groups)} групп -> {output_dir}")

    saved: list[Path] = []
    for group in groups:
        content = render_group_xml(session, period, level, group, faculty)
        path = output_dir / f"{group.name}.xml"
        path.write_bytes(content)
        students = content.count(b"<StudentNumber ")
        log(f"  {group.name}: студентов {students}")
        saved.append(path)
        time.sleep(REQUEST_PAUSE_SEC)
    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Выгрузка XML «Аттестация по выбранной группе» для групп кафедры ИТРС с портала РИТМ."
    )
    add_period_arguments(parser)
    parser.add_argument(
        "--forget-password",
        action="store_true",
        help="Удалить сохранённые логин и пароль из Связки ключей и выйти.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.forget_password:
        forget_credentials()
        print("Логин и пароль удалены из Связки ключей.")
        return 0

    period = AttestationPeriod(args.year, args.semester, args.att)
    print(period.label)
    try:
        session = open_session()
        for level in selected_levels(args.level):
            fetch_level(session, period, level, Path(args.root))
        fetch_kafedra_report(session, period, Path(args.root))
    except (RitmError, requests.RequestException) as exc:
        print(f"Ошибка выгрузки: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
