"""The whole report pipeline on made-up portal exports, through the service."""

import make_report
import ritm_fetch
import synthetic
from helpers import FakePipeline, csrf, job_body, log_in, make_service, wait_for


def offline_reports(workdir, levels, log):
    synthetic.write_attestation(workdir)
    return make_report.build_all(None, ritm_fetch.AttestationPeriod(2026, True, 1), workdir, levels, log=log)


def finished_job(tmp_path):
    _, client = make_service(tmp_path, FakePipeline(result=offline_reports))
    log_in(client)
    job = client.post("/attestation/api/jobs", json=job_body(), headers=csrf(client)).json()
    return client, wait_for(client, job["id"])


def test_cannot_lose_any_report_file(tmp_path):
    _, job = finished_job(tmp_path)
    assert len(job["downloads"]) == 4, f"Expected short, two detailed and Markdown reports: {job}"


def test_cannot_drop_master_group_from_markdown(tmp_path):
    _, job = finished_job(tmp_path)
    assert "ИТСм(о)-11" in job["markdown"], "Master's group is missing from the Markdown report"


def test_cannot_download_short_report_as_something_else(tmp_path):
    client, job = finished_job(tmp_path)
    short = next(item for item in job["downloads"] if "Краткий" in item["label"])
    assert client.get(short["href"]).content[:2] == b"PK", "Short report download is not a DOCX file"


def test_cannot_show_department_rank_wrong(tmp_path):
    _, job = finished_job(tmp_path)
    assert "место кафедры: **2 из 3**" in job["markdown"], "Department rank in the summary is wrong"


def test_cannot_print_empty_critical_table(tmp_path):
    _, job = finished_job(tmp_path)
    assert "Таких дисциплин нет." in job["markdown"], "Empty critical-disciplines table was printed as a bare header"
