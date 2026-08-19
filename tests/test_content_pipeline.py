from __future__ import annotations

import json

from content_pipeline.education import generate_education, generate_assessment, COURSES
from content_pipeline.jobs import GenerationJob, JobStore
from content_pipeline.reports import report_specs, write_report_specs
from content_pipeline.research import write_research_artifacts
from content_pipeline.validators import validate_education, validate_reports


def test_report_contracts_are_complete_and_ordered(tmp_path):
    write_report_specs(tmp_path)
    result = validate_reports(tmp_path)
    assert result["ok"]
    assert set(report_specs()) == {"AR", "NM", "AW", "WL"}
    assert all(spec.sections[-1].title == "Sources and Filing Provenance" for spec in report_specs().values())


def test_education_generation_counts_and_private_gold(tmp_path):
    summary = generate_education(tmp_path)
    assert summary == {"courses": 8, "assessments": 40, "questions": 296, "submissions": 320}
    result = validate_education(tmp_path)
    assert result["ok"]
    public = json.loads((tmp_path / "assessments" / "CALC1-PS1.json").read_text())
    assert all("answer_key" not in item for item in public["questions"])
    assert (tmp_path / "gold" / "CALC1-PS1.json").is_file()


def test_generation_is_seed_reproducible():
    course = COURSES[0]
    assert generate_assessment(course, "PS1", seed=1234) == generate_assessment(course, "PS1", seed=1234)


def test_job_store_resumable_state(tmp_path):
    store = JobStore(tmp_path / "jobs.jsonl")
    job = GenerationJob("JOB-1", "assessment", "small", "prompt-hash", ["brief"], 7)
    job.transition("generated")
    job.record_attempt(token_usage={"input": 80, "output": 40}, cost_usd=0.01)
    job.transition("accepted")
    store.put(job)
    loaded = store.get("JOB-1")
    assert loaded is not None
    assert loaded.state == "accepted"
    assert loaded.token_usage["output"] == 40


def test_research_ledger_records_license_boundary(tmp_path):
    summary = write_research_artifacts(tmp_path / "sources", sec_root=tmp_path / "missing-sec")
    assert summary["sources"] == 4
    rows = [json.loads(line) for line in (tmp_path / "sources" / "source-ledger.jsonl").read_text().splitlines()]
    assert any(row["permitted_use"] == "research_only" for row in rows)
    assert any(row["source_id"] == "SEC-API" for row in rows)
