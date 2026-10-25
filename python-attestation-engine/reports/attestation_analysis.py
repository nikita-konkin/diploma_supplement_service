"""Графики и текстовый отчёт по XML аттестации — те же расчёты, что в ноутбуках

    attestation_analysis_group_detail_v2.ipynb  (графики)
    attestation_text_report_notebook.ipynb      (attestation_text_report.txt)

но без ручной правки DATA_DIR: на вход подаётся папка с XML, результаты пишутся туда же.
"""

from __future__ import annotations

import argparse
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


FONT_FAMILY = ["Times New Roman", "Liberation Serif", "DejaVu Serif"]  # Liberation — замена в Linux
BASE_FONT_SIZE = 14
TITLE_FONT_SIZE = 18
TICK_FONT_SIZE = 12
LEGEND_FONT_SIZE = 12
ANNOTATION_FONT_SIZE = 10

TOP_PROBLEM_GROUPS = 3
TOP_SUCCESS_GROUPS = 3
TOP_GROUP_DISCIPLINES = 5
DETAIL_GROUPS_COUNT = 3
CRITICAL_DISCIPLINE_THRESHOLD = 85.0  # дисциплины с >= этого % Н/А попадут в раздел критических
ZERO_DISCIPLINE_THRESHOLD = 100.0
SUCCESS_DISCIPLINE_THRESHOLD = 0.0

TEXT_REPORT_NAME = "attestation_text_report.txt"


def installed_font_family() -> list[str]:
    """FONT_FAMILY without fonts missing here: matplotlib warns about each one on every label."""
    from matplotlib import font_manager

    installed = {font.name for font in font_manager.fontManager.ttflist}
    return [name for name in FONT_FAMILY if name in installed] or ["DejaVu Sans"]


def configure_matplotlib() -> None:
    plt.rcParams["font.family"] = installed_font_family()
    plt.rcParams["font.size"] = BASE_FONT_SIZE
    plt.rcParams["axes.titlesize"] = TITLE_FONT_SIZE
    plt.rcParams["axes.labelsize"] = BASE_FONT_SIZE
    plt.rcParams["xtick.labelsize"] = TICK_FONT_SIZE
    plt.rcParams["ytick.labelsize"] = TICK_FONT_SIZE
    plt.rcParams["legend.fontsize"] = LEGEND_FONT_SIZE
    plt.rcParams["figure.titlesize"] = TITLE_FONT_SIZE


def minmax_scale(series: pd.Series, invert: bool = False) -> pd.Series:
    """Масштабирует Series в [0, 1]; для константного ряда возвращает 1.0."""
    s = pd.to_numeric(series, errors="coerce")
    valid = s.dropna()
    result = pd.Series(np.nan, index=s.index, dtype=float)
    if valid.empty:
        return result

    min_val = valid.min()
    max_val = valid.max()
    if np.isclose(max_val, min_val):
        result.loc[valid.index] = 1.0
    else:
        result.loc[valid.index] = (valid - min_val) / (max_val - min_val)
    return 1 - result if invert else result


def apply_group_minmax(df_in: pd.DataFrame, columns: list[str], suffix: str = "_mm") -> pd.DataFrame:
    df_out = df_in.copy()
    for col in columns:
        df_out[f"{col}{suffix}"] = minmax_scale(df_out[col])
    return df_out


# --- Загрузка XML ---------------------------------------------------------------------------


def parse_range(text: str | None) -> tuple[float, float]:
    """'13 - 19,5' -> (13.0, 19.5)."""
    if text is None:
        return np.nan, np.nan
    cleaned = str(text).replace(",", ".").replace("–", "-").strip()
    nums = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return float(nums[0]), float(nums[0])
    return np.nan, np.nan


def parse_course_from_group(group_name: str) -> float:
    """'ИТС(о)-41' -> 4: первая цифра после дефиса."""
    match = re.search(r"-(\d+)", group_name)
    return int(match.group(1)[0]) if match else np.nan


def load_attestation_xml(file_path: Path) -> list[dict]:
    """Одна запись = один студент по одной дисциплине."""
    root = ET.parse(file_path).getroot()
    report_title = root.attrib.get("ReportTitle", "")
    group_match = re.search(r"группы\s+(.+)$", report_title)
    group_name = group_match.group(1).strip() if group_match else file_path.stem
    course = parse_course_from_group(group_name)

    ns_prefix = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    rows = []
    for student_node in root.findall(f".//{ns_prefix}stFIO"):
        student_name = student_node.attrib.get("stFIO")
        if not student_name:
            continue
        student_number_node = student_node.find(f"./{ns_prefix}StudentNumber")
        if student_number_node is None:
            continue
        student_number = student_number_node.attrib.get("StudentNumber")

        for subj in student_number_node.findall(f".//{ns_prefix}SubjectName"):
            minball_node = subj.find(f"./{ns_prefix}minBall")
            if minball_node is None:
                continue
            lower_bound, _ = parse_range(minball_node.attrib.get("minBall"))
            attball_text = minball_node.attrib.get("AttBall")
            try:
                att_ball = float(str(attball_text).replace(",", ".")) if attball_text is not None else np.nan
            except ValueError:
                att_ball = np.nan

            known = not (pd.isna(att_ball) or pd.isna(lower_bound))
            rows.append({
                "group": group_name,
                "course": course,
                "student_name": student_name.strip(),
                "student_number": student_number,
                "subject": subj.attrib.get("SubjectName", "").strip(),
                "lower_bound": lower_bound,
                "att_ball": att_ball,
                "below_min": int(att_ball < lower_bound) if known else np.nan,
                "margin_to_min": att_ball - lower_bound if known else np.nan,
                "normalized_to_min": (
                    att_ball / lower_bound if known and lower_bound != 0 else np.nan
                ),
                "zero_score": int(att_ball == 0) if not pd.isna(att_ball) else np.nan,
            })
    return rows


def load_records(data_dir: Path) -> pd.DataFrame:
    xml_files = sorted(data_dir.glob("*.xml"))
    if not xml_files:
        raise FileNotFoundError(f"В папке {data_dir} не найдены XML-файлы.")
    records = [row for path in xml_files for row in load_attestation_xml(path)]
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"После разбора XML из {data_dir} таблица оказалась пустой.")
    return df[df["subject"].str.len() > 0].copy()


def build_student_table(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(["group", "course", "student_name", "student_number"], as_index=False).agg(
        mean_normalized_to_min=("normalized_to_min", "mean"),
    )


# --- Общие графики --------------------------------------------------------------------------


def plot_group_boxplot(student_df: pd.DataFrame, save_dir: Path) -> None:
    student_df = student_df.copy()
    student_df["group_compare_value"] = np.nan
    for _, idx in student_df.groupby("group").groups.items():
        student_df.loc[idx, "group_compare_value"] = minmax_scale(
            student_df.loc[idx, "mean_normalized_to_min"]
        ).values

    ordered_groups = student_df.groupby("group")["group_compare_value"].median().sort_values().index
    data = [
        student_df.loc[student_df["group"] == g, "group_compare_value"].dropna().values
        for g in ordered_groups
    ]

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.boxplot(data, vert=True, showfliers=True)
    ax.set_xticks(range(1, len(ordered_groups) + 1))
    ax.set_xticklabels(ordered_groups, rotation=45, ha="right")
    ax.set_ylabel("Нормализированное значение балла")
    ax.set_xlabel("Группа")
    ax.set_title("Распределение студентов по нормализованной успеваемости внутри групп")
    fig.tight_layout()
    fig.savefig(save_dir / "group_comparison_boxplot.png", dpi=300)
    plt.close(fig)


def plot_top_problematic_subjects(df: pd.DataFrame, save_dir: Path, top_n: int = 20) -> None:
    subject_risk = (
        df.groupby("subject", as_index=False)
        .agg(
            fail_rate=("below_min", "mean"),
            zero_rate=("zero_score", "mean"),
            avg_margin_to_min=("margin_to_min", "mean"),
        )
        .sort_values(["fail_rate", "zero_rate", "avg_margin_to_min"], ascending=[False, False, True])
    )
    subject_risk["fail_rate_pct"] = subject_risk["fail_rate"] * 100
    top_subjects = subject_risk.head(top_n).sort_values("fail_rate_pct")
    labels = ["\n".join(textwrap.wrap(name, 60)) for name in top_subjects["subject"]]

    fig, ax = plt.subplots(figsize=(12, max(7, len(labels) * 0.5)))
    ax.barh(labels, top_subjects["fail_rate_pct"])
    ax.set_xlabel("% студентов ниже минимума")
    ax.set_ylabel("Дисциплина")
    ax.set_title(f"Топ-{top_n} проблемных дисциплин по доле несдавших")
    fig.tight_layout()
    fig.savefig(save_dir / "top_problematic_subjects.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def compute_risk_index(df: pd.DataFrame) -> pd.DataFrame:
    """risk_index = 0.5·fail_rate~ + 0.3·zero_rate~ + 0.2·avg_deficit~ (компоненты Min-Max scaled)."""
    risk_df = df.groupby("group", as_index=False).agg(
        fail_rate=("below_min", "mean"),
        zero_rate=("zero_score", "mean"),
        avg_margin_to_min=("margin_to_min", "mean"),
    )
    risk_df["avg_deficit"] = risk_df["avg_margin_to_min"].apply(
        lambda x: max(0, -x) if pd.notna(x) else np.nan
    )
    risk_df = apply_group_minmax(risk_df, columns=["fail_rate", "zero_rate", "avg_deficit"])
    risk_df["risk_index"] = (
        0.5 * risk_df["fail_rate_mm"].fillna(0)
        + 0.3 * risk_df["zero_rate_mm"].fillna(0)
        + 0.2 * risk_df["avg_deficit_mm"].fillna(0)
    )
    return risk_df.sort_values("risk_index", ascending=False)


def plot_group_risk_index(df: pd.DataFrame, save_dir: Path) -> None:
    risk_df = compute_risk_index(df)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(risk_df["group"], risk_df["risk_index"])
    ax.tick_params(axis="x", labelrotation=45)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    ax.set_ylabel("Индекс риска")
    ax.set_xlabel("Группа")
    ax.set_title("Рейтинг групп по интегральному индексу риска")
    fig.tight_layout()
    fig.savefig(save_dir / "group_risk_index.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# --- Графики по группе ----------------------------------------------------------------------


def plot_attestation_breakdown(
    group_df: pd.DataFrame,
    *,
    by: str,
    count_label: str,
    axis_label: str,
    title: str,
    hatches: tuple[str, str],
    na_text_color: str,
    width: float,
    row_height: float,
    output_path: Path,
) -> None:
    """Горизонтальный stacked bar: по каждому студенту/дисциплине — число A и Н/А."""
    group_df = group_df.assign(
        att_status=np.where(group_df["below_min"].fillna(1).astype(int) == 1, "Н/А", "A")
    )
    stats = group_df.groupby(by, as_index=False).agg(
        total=("att_status", "size"),
        attested_count=("att_status", lambda s: int((s == "A").sum())),
        not_attested_count=("att_status", lambda s: int((s == "Н/А").sum())),
    )
    stats["na_share"] = np.where(stats["total"] > 0, 100 * stats["not_attested_count"] / stats["total"], np.nan)
    stats = stats.sort_values(["na_share", "not_attested_count", by], ascending=[False, False, True])

    labels = [f"{name}, % Н/А - {share:.1f}" for name, share in zip(stats[by], stats["na_share"])]
    fig, ax = plt.subplots(figsize=(width, max(7, len(stats) * row_height)))
    y = np.arange(len(stats))
    att = stats["attested_count"].values
    na = stats["not_attested_count"].values

    ax.barh(y, att, label="A", hatch=hatches[0], edgecolor="#1B7400")
    ax.barh(y, na, left=att, label="Н/А", hatch=hatches[1], edgecolor="#FF1616", facecolor="white")
    for i, (a_val, na_val) in enumerate(zip(att, na)):
        if a_val > 0:
            ax.text(a_val - 0.1, i, f"{int(a_val)}", va="center", ha="right",
                    color="#FFFFFF", fontsize=ANNOTATION_FONT_SIZE + 8)
        if na_val > 0:
            ax.text(a_val + na_val - 0.1, i, f"{int(na_val)}", va="center", ha="right",
                    color=na_text_color, fontsize=ANNOTATION_FONT_SIZE + 8)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel(count_label)
    ax.set_ylabel(axis_label)
    ax.set_title(title)
    ax.legend(title="Тип аттестации", loc="upper left", bbox_to_anchor=(1.02, 1.0))
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_group_charts(df: pd.DataFrame, save_dir: Path, attestation_number: str) -> None:
    for group_name in df["group"].dropna().unique():
        group_df = df[df["group"] == group_name]
        plot_attestation_breakdown(
            group_df,
            by="student_name",
            count_label="Количество дисциплин",
            axis_label="Студенты",
            title=f"Аттестация №{attestation_number} по студентам группы {group_name}",
            hatches=("++", "xx"),
            na_text_color="#000000",
            width=14,
            row_height=0.45,
            output_path=save_dir / f"by_stud_{group_name}.png",
        )
        plot_attestation_breakdown(
            group_df,
            by="subject",
            count_label="Количество студентов",
            axis_label="Дисциплины",
            title=f"Аттестация №{attestation_number} по дисциплинам группы {group_name}",
            hatches=("///", "\\\\"),
            na_text_color="#FF1616",
            width=16,
            row_height=0.55,
            output_path=save_dir / f"by_sub_{group_name}.png",
        )


# --- Текстовый отчёт ------------------------------------------------------------------------


def bullet(text: str) -> str:
    return f"•      {text}"


def numbered(i: int, text: str) -> str:
    return f"{i}.    {text}"


def summarize(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.assign(is_not_attested=df["below_min"].fillna(0).astype(int))
    df["is_attested"] = 1 - df["is_not_attested"]

    group_summary = df.groupby("group").agg(
        students=("student_name", "nunique"),
        disciplines=("subject", "nunique"),
        records=("subject", "size"),
        attested=("is_attested", "sum"),
        not_attested=("is_not_attested", "sum"),
    ).reset_index()
    group_summary["not_attested_pct"] = 100 * group_summary["not_attested"] / group_summary["records"]
    group_summary["attested_pct"] = 100 * group_summary["attested"] / group_summary["records"]

    discipline_in_group = df.groupby(["group", "subject"]).agg(
        records=("subject", "size"),
        not_attested=("is_not_attested", "sum"),
    ).reset_index()
    discipline_in_group["not_attested_pct"] = (
        100 * discipline_in_group["not_attested"] / discipline_in_group["records"]
    )
    discipline_in_group = discipline_in_group.sort_values(
        ["not_attested_pct", "not_attested", "group", "subject"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)
    return group_summary, discipline_in_group


def build_group_section(group_summary: pd.DataFrame) -> list[str]:
    lines = ["АНАЛИЗ ПО ГРУППАМ", "", "Проблемные группы:"]
    by_failure = group_summary.sort_values(["not_attested_pct", "not_attested"], ascending=[False, False])
    for _, row in by_failure.head(TOP_PROBLEM_GROUPS).iterrows():
        lines.append(bullet(f"{row['group']}: {row['not_attested_pct']:.1f}% неаттестованных ({int(row['disciplines'])} дисциплин)"))
    lines += ["", "Успешные группы:"]
    by_success = group_summary.sort_values(["not_attested_pct", "not_attested"], ascending=[True, True])
    for _, row in by_success.head(TOP_SUCCESS_GROUPS).iterrows():
        lines.append(bullet(f"{row['group']}: {row['not_attested_pct']:.1f}% неаттестованных ({int(row['disciplines'])} дисциплин)"))
    lines.append("")
    return lines


def build_critical_disciplines_section(discipline_in_group: pd.DataFrame) -> list[str]:
    lines = ["КРИТИЧЕСКИЕ ДИСЦИПЛИНЫ", "", "1. Дисциплины со 100% неаттестацией:"]
    full_fail = discipline_in_group[discipline_in_group["not_attested_pct"] >= ZERO_DISCIPLINE_THRESHOLD]
    if full_fail.empty:
        lines.append(bullet("Нет дисциплин со 100% неаттестацией"))
    for _, row in full_fail.iterrows():
        lines.append(bullet(f"{row['subject']} ({row['group']})"))
    lines.append("")

    crit = discipline_in_group[
        (discipline_in_group["not_attested_pct"] >= CRITICAL_DISCIPLINE_THRESHOLD)
        & (discipline_in_group["not_attested_pct"] < ZERO_DISCIPLINE_THRESHOLD)
    ]
    lines.append(f"2. Другие критические дисциплины (≥{CRITICAL_DISCIPLINE_THRESHOLD:.0f}% неаттестации):")
    if crit.empty:
        lines.append(bullet(f"Нет дисциплин с неаттестацией ≥{CRITICAL_DISCIPLINE_THRESHOLD:.0f}%"))
    for _, row in crit.iterrows():
        lines.append(bullet(
            f"{row['subject']}: {row['not_attested_pct']:.1f}% "
            f"({int(row['not_attested'])} неаттестованных студентов) ({row['group']})"
        ))
    lines.append("")
    return lines


def build_success_disciplines_section(discipline_in_group: pd.DataFrame) -> list[str]:
    lines = ["УСПЕШНЫЕ ДИСЦИПЛИНЫ", "", "Дисциплины с нулевым процентом неаттестованных:"]
    success = discipline_in_group[
        discipline_in_group["not_attested_pct"] <= SUCCESS_DISCIPLINE_THRESHOLD
    ].sort_values(["group", "subject"])
    if success.empty:
        lines.append(bullet("Нет дисциплин с нулевым процентом неаттестованных"))
    for _, row in success.iterrows():
        lines.append(bullet(f"{row['subject']} ({row['group']})"))
    lines.append("")
    return lines


def build_detailed_problem_groups_section(
    group_summary: pd.DataFrame, discipline_in_group: pd.DataFrame
) -> list[str]:
    lines = ["ДЕТАЛЬНЫЙ АНАЛИЗ ПРОБЛЕМНЫХ ГРУПП", ""]
    problem_groups = group_summary.sort_values(
        ["not_attested_pct", "not_attested"], ascending=[False, False]
    ).head(DETAIL_GROUPS_COUNT)

    for idx, (_, g) in enumerate(problem_groups.iterrows(), start=1):
        lines += [
            f"{idx}. ГРУППА {g['group']}",
            f"Общий процент неаттестации: {g['not_attested_pct']:.1f}%",
            f"{idx}.1. Общая характеристика",
            bullet(f"Количество студентов: {int(g['students'])}"),
            bullet(f"Количество дисциплин: {int(g['disciplines'])}"),
            bullet(f"Всего аттестационных записей: {int(g['records'])}"),
            bullet(
                f"Аттестовано: {int(g['attested'])} ({g['attested_pct']:.1f}%), "
                f"Не аттестовано: {int(g['not_attested'])} ({g['not_attested_pct']:.1f}%)"
            ),
            f"{idx}.2. Проблемные дисциплины",
        ]
        sub = discipline_in_group[discipline_in_group["group"] == g["group"]].sort_values(
            ["not_attested_pct", "not_attested", "subject"], ascending=[False, False, True]
        ).head(TOP_GROUP_DISCIPLINES)
        if sub.empty:
            lines.append(bullet("Нет данных по дисциплинам"))
        for j, (_, row) in enumerate(sub.iterrows(), start=1):
            lines.append(numbered(j, f"{row['subject']}: {row['not_attested_pct']:.1f}%"))
        lines.append("")
    return lines


def build_text_report(df: pd.DataFrame) -> str:
    group_summary, discipline_in_group = summarize(df)
    lines = (
        build_group_section(group_summary)
        + build_critical_disciplines_section(discipline_in_group)
        + build_success_disciplines_section(discipline_in_group)
        + build_detailed_problem_groups_section(group_summary, discipline_in_group)
    )
    return "\n".join(lines)


# --- Точка входа ----------------------------------------------------------------------------


def run_analysis(data_dir: Path) -> None:
    """Строит все графики и текстовый отчёт в папке data_dir (номер аттестации = имя родительской папки)."""
    configure_matplotlib()
    df = load_records(data_dir)
    attestation_number = data_dir.parent.name

    plot_group_boxplot(build_student_table(df), data_dir)
    plot_top_problematic_subjects(df, data_dir)
    plot_group_risk_index(df, data_dir)
    plot_group_charts(df, data_dir, attestation_number)
    (data_dir / TEXT_REPORT_NAME).write_text(build_text_report(df), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Графики и текстовый отчёт по XML аттестации в папке.")
    parser.add_argument("input_dir", help="Папка с XML-файлами групп.")
    args = parser.parse_args()
    run_analysis(Path(args.input_dir).resolve())
    print("ANALYSIS_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
