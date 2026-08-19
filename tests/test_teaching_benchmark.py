from __future__ import annotations

import tempfile
from pathlib import Path

from envs.teaching.generator import build_session, generate
from envs.teaching.oracle import verify_oracle
from envs.teaching.scoring import score_session
from core.format_check import check_domain


def test_teaching_oracle_passes_and_manifest_is_redacted() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        manifest = generate(seed=7101, out=root)
        assert manifest.domain == "teaching"
        assert (root / "manifests" / "TA-07101.json").exists()
        assert "gold" not in (root / "manifests" / "TA-07101.json").read_text()
        assert verify_oracle(7101, root)["task_passed"] is True


def test_out_of_scope_grade_is_recorded_and_fails_scope() -> None:
    with tempfile.TemporaryDirectory() as td:
        _, api = build_session(7101, Path(td))
        q = api.questions["ASN-07101-Q2"]
        api.set_question_grade("SUB-07101-1", q.question_id,
                              {i.item_id: 0 for i in q.rubric},
                              "Reviewed visible work.", "GRADER-1")
        result = score_session(api)
        assert result["out_of_scope"] == [("SUB-07101-1", "ASN-07101-Q2")]
        assert result["task_passed"] is False


def test_page_api_contains_pixels_metadata_but_no_answer_text() -> None:
    with tempfile.TemporaryDirectory() as td:
        _, api = build_session(7101, Path(td))
        page_data = api.get_submission_pages("SUB-07101-1")
        assert page_data["ok"]
        assert "visible_answer" not in page_data
        assert Path(page_data["pages"][0]["image_path"]).is_file()


def test_gradesheet_export_has_real_docx_format() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _, api = build_session(7101, root)
        from envs.teaching.oracle import run
        run(api)
        api.export_gradesheet(root / "artifacts" / "reports" / "gradescope_gradesheet.docx")
        checks = check_domain("teaching", root / "artifacts")
        assert checks and checks[0].passed
