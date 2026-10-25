import pytest
import ritm_fetch

from app.portal import Period, ReportRequest, RitmPortal

GROUPS = {
    "б": ["ИТС(о)-11", "ИТС(о)-21", "ИТС(з)-11", "РСК(о)-11"],
    "м": ["ИТСм(о)-11", "РТм(о)-11"],
}


@pytest.fixture
def portal_groups(monkeypatch):
    def fake_list(session, period, level, faculty=ritm_fetch.FACULTY_ID):
        return [ritm_fetch.StudyGroup(group_id=name, name=name) for name in GROUPS[level]]

    monkeypatch.setattr(ritm_fetch, "list_groups", fake_list)


def test_cannot_merge_full_time_and_extramural_groups(portal_groups):
    codes = [item["code"] for item in RitmPortal().groups(None, Period(2026, True, 1), "1857")]
    assert codes == ["ИТС(з)", "ИТС(о)", "РСК(о)", "ИТСм(о)", "РТм(о)"], f"Directions were merged or lost: {codes}"


def test_cannot_list_groups_of_direction_incompletely(portal_groups):
    directions = RitmPortal().groups(None, Period(2026, True, 1), "1857")
    assert next(item for item in directions if item["code"] == "ИТС(о)")["groups"] == ["ИТС(о)-11", "ИТС(о)-21"], (
        "A direction lost one of its groups"
    )


def test_cannot_build_report_for_directions_without_groups(portal_groups):
    request = ReportRequest(Period(2026, True, 1), "1857", "ИТРС", frozenset({"НЕТ(о)"}), "РТФ", "")
    with pytest.raises(ritm_fetch.RitmError, match="нет групп"):
        RitmPortal().build(None, request, None, print)
