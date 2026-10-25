"""Data behind the page's charts (report_model.model_data) on made-up exports."""

import make_report
import report_model
import ritm_fetch
import synthetic


def build(root, attestation=1):
    synthetic.write_attestation(root, attestation=attestation)
    period = ritm_fetch.AttestationPeriod(2026, True, attestation)
    return make_report.build_all(None, period, root, ["б", "м"], log=lambda message: None, pdf=False)


def data_of(attestation_dir):
    return report_model.model_data(report_model.build_model(attestation_dir))


def test_cannot_skip_chart_data_file(tmp_path):
    attestation_dir = build(tmp_path)
    assert (attestation_dir / report_model.REPORT_DATA_FILE).exists(), "Report folder has no data for the charts"


def test_cannot_lose_scores_of_a_student(tmp_path):
    group = next(item for item in data_of(build(tmp_path))["groups"] if item["name"] == "ИТС(о)-11")
    subjects = [item["subject"] for item in group["disciplines"]]
    student = next(item for item in group["students_scores"] if item["name"].startswith("Студент2 "))
    scores = dict(zip(subjects, student["scores"]))
    assert scores == {"Базы данных": 0, "Сети и телекоммуникации": 15, "Программирование": 13, "Высшая математика": 2}, (
        f"Heatmap scores do not match the export: {scores}"
    )


def test_cannot_split_failures_beyond_their_total(tmp_path):
    for group in data_of(build(tmp_path))["groups"]:
        assert group["zero"] + group["not_entered"] <= group["failed"], f"Bar parts exceed failures in {group['name']}"


def test_cannot_invent_dynamics_for_first_attestation(tmp_path):
    assert data_of(build(tmp_path))["summary"]["comparison"] is None, "First attestation got a made-up comparison"


def test_cannot_miss_previous_attestation(tmp_path):
    build(tmp_path, attestation=1)
    summary = data_of(build(tmp_path, attestation=2))["summary"]
    assert (summary["comparison"]["attestation"], summary["comparison"]["groups"]) == (1, 3), (
        f"Comparison with attestation 1 is missing: {summary['comparison']}"
    )


def test_cannot_show_change_where_nothing_changed(tmp_path):
    build(tmp_path, attestation=1)
    summary = data_of(build(tmp_path, attestation=2))["summary"]
    assert summary["comparison"]["failure_delta"] == 0, "Identical attestations show a change"


def write_not_entered(attestation_dir):
    # Высшая математика (4-й столбец): у всей группы 0 — баллы не внесены
    scores = [[19, 19, 19, 0], [12, 14, 16, 0], [0, 0, 0, 0]]
    (attestation_dir / "б" / "ИСТ(о)-21.xml").write_text(synthetic.group_xml("ИСТ(о)-21", scores), encoding="utf-8")


def rebuilt_with_not_entered(tmp_path):
    attestation_dir = build(tmp_path)
    write_not_entered(attestation_dir)
    return attestation_dir


def test_cannot_count_not_entered_as_ordinary_zeros(tmp_path):
    summary = data_of(rebuilt_with_not_entered(tmp_path))["summary"]
    assert (summary["not_entered_disciplines"], summary["not_entered"]) == (1, 3), (
        f"Discipline with zeros for the whole group was not singled out: {summary}"
    )


def test_cannot_mark_partly_zero_discipline_as_not_entered(tmp_path):
    groups = data_of(rebuilt_with_not_entered(tmp_path))["groups"]
    flagged = [(group["name"], item["subject"]) for group in groups for item in group["disciplines"] if item["not_entered"]]
    assert flagged == [("ИСТ(о)-21", "Высшая математика")], f"Wrong disciplines marked as not entered: {flagged}"


def test_cannot_hide_not_entered_in_conclusions(tmp_path):
    model = report_model.build_model(rebuilt_with_not_entered(tmp_path))
    assert any(line.startswith("Баллы не выставлены") for line in report_model.conclusions(model)), (
        "Conclusions do not mention disciplines without scores"
    )


def test_cannot_label_not_entered_discipline_as_critical(tmp_path):
    import build_markdown_report

    attestation_dir = rebuilt_with_not_entered(tmp_path)
    markdown = build_markdown_report.build_markdown_report(attestation_dir).read_text(encoding="utf-8")
    rows = [line for line in markdown.splitlines() if line.startswith("| ИСТ(о)-21 | Высшая математика")]
    assert rows and all(row.endswith("○ не выставлено |") for row in rows), (
        f"Discipline without scores is labelled as a failure: {rows}"
    )


def test_cannot_refetch_previous_attestation_already_on_disk(tmp_path, monkeypatch):
    build(tmp_path, attestation=1)
    calls = []
    monkeypatch.setattr(ritm_fetch, "fetch_level", lambda *args, **kwargs: calls.append(args[1]))
    make_report.fetch_previous(object(), ritm_fetch.AttestationPeriod(2026, True, 2), tmp_path, ["б", "м"], print, "1857", None)
    assert calls == [], "Previous attestation was downloaded again although it is on disk"


def test_cannot_skip_previous_attestation_for_dynamics(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ritm_fetch, "fetch_level", lambda session, period, level, *rest: calls.append((period.attestation, level)))
    make_report.fetch_previous(object(), ritm_fetch.AttestationPeriod(2026, True, 3), tmp_path, ["б", "м"], print, "1857", None)
    assert calls == [(2, "б"), (2, "м")], f"Previous attestation was not fetched for dynamics: {calls}"


def test_cannot_fail_report_when_previous_attestation_is_missing(tmp_path, monkeypatch):
    def missing(*args, **kwargs):
        raise ritm_fetch.RitmError("Не найдено групп кафедры")

    messages = []
    monkeypatch.setattr(ritm_fetch, "fetch_level", missing)
    make_report.fetch_previous(object(), ritm_fetch.AttestationPeriod(2026, True, 2), tmp_path, ["б"], messages.append, "1857", None)
    assert "динамики не будет" in messages[-1], "Missing previous attestation was not reported calmly"


def test_cannot_list_not_entered_discipline_among_critical(tmp_path):
    model = report_model.build_model(rebuilt_with_not_entered(tmp_path))
    assert all(not item.not_entered for item in model.critical_disciplines()), (
        "Discipline without scores is listed among critical ones"
    )
