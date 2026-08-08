"""Grading ActionAPI — inbox rubrics through Gradescope grades/regrades."""
from __future__ import annotations

from dataclasses import dataclass

from core.actions import BaseActionAPI, err, ok
from core.artifacts import write_docx
from core.db import ENV_NOW


@dataclass
class ActionAPI(BaseActionAPI):
    _rubric_seq: int = 0
    _grade_seq: int = 0

    # ---------------------------------------------------------------- reads
    def list_emails(self) -> dict:
        return self._record("list_emails", {}, ok(emails=self._rows(
            "SELECT email_id, sender, subject, sent_at, stated_total_points, "
            "assignment_code, is_messy FROM a.emails ORDER BY sent_at")))

    def get_email(self, email_id: str) -> dict:
        r = self._one("SELECT * FROM a.emails WHERE email_id = ?", (email_id,))
        drafts = self._rows(
            "SELECT * FROM a.rubric_drafts WHERE email_id = ? ORDER BY item_ord",
            (email_id,)) if r else []
        res = ok(email=r, rubric_drafts=drafts) if r else err(
            "not_found", f"no email {email_id!r}")
        return self._record("get_email", {"email_id": email_id}, res)

    def list_assignments(self) -> dict:
        return self._record("list_assignments", {}, ok(assignments=self._rows(
            "SELECT * FROM b.assignments ORDER BY assignment_id")))

    def list_submissions(self, assignment_id: str) -> dict:
        if not self._one("SELECT 1 FROM b.assignments WHERE assignment_id = ?",
                         (assignment_id,)):
            return self._record("list_submissions",
                                {"assignment_id": assignment_id},
                                err("not_found", f"no assignment {assignment_id!r}"))
        rows = self._rows(
            "SELECT submission_id, assignment_id, user_id, clarity, "
            "handwriting_noise FROM b.submissions WHERE assignment_id = ? "
            "ORDER BY submission_id", (assignment_id,))
        return self._record("list_submissions", {"assignment_id": assignment_id},
                            ok(submissions=rows))

    def get_submission(self, submission_id: str) -> dict:
        r = self._one("SELECT * FROM b.submissions WHERE submission_id = ?",
                      (submission_id,))
        res = ok(submission=r) if r else err(
            "not_found", f"no submission {submission_id!r}")
        return self._record("get_submission", {"submission_id": submission_id}, res)

    def list_students(self) -> dict:
        return self._record("list_students", {}, ok(students=self._rows(
            "SELECT * FROM b.students ORDER BY user_id")))

    def get_rubric(self, assignment_id: str) -> dict:
        r = self._one("SELECT * FROM b.rubrics WHERE assignment_id = ?",
                      (assignment_id,))
        if not r:
            return self._record("get_rubric", {"assignment_id": assignment_id},
                                err("not_found", "no published rubric"))
        items = self._rows(
            "SELECT * FROM b.rubric_items WHERE rubric_id = ? ORDER BY item_ord",
            (r["rubric_id"],))
        return self._record("get_rubric", {"assignment_id": assignment_id},
                            ok(rubric=r, items=items))

    def list_regrade_requests(self, status: str | None = None) -> dict:
        if status:
            rows = self._rows(
                "SELECT * FROM b.regrade_requests WHERE status = ? "
                "ORDER BY regrade_id", (status,))
        else:
            rows = self._rows(
                "SELECT * FROM b.regrade_requests ORDER BY regrade_id")
        return self._record("list_regrade_requests", {"status": status},
                            ok(requests=rows))

    def get_grade(self, submission_id: str) -> dict:
        g = self._one("SELECT * FROM b.grades WHERE submission_id = ?",
                      (submission_id,))
        if not g:
            return self._record("get_grade", {"submission_id": submission_id},
                                err("not_found", "no grade yet"))
        items = self._rows(
            "SELECT * FROM b.grade_items WHERE grade_id = ?", (g["grade_id"],))
        return self._record("get_grade", {"submission_id": submission_id},
                            ok(grade=g, items=items))

    # ---------------------------------------------------------------- writes
    def publish_rubric(self, assignment_id: str, source_email_id: str,
                       items: list[dict]) -> dict:
        """items: [{item_key, description, max_points, expected_key, item_ord}]"""
        args = {"assignment_id": assignment_id,
                "source_email_id": source_email_id, "items": items}
        if not self._one("SELECT 1 FROM b.assignments WHERE assignment_id = ?",
                         (assignment_id,)):
            return self._record("publish_rubric", args, err(
                "not_found", f"no assignment {assignment_id!r}"))
        if not self._one("SELECT 1 FROM a.emails WHERE email_id = ?",
                         (source_email_id,)):
            return self._record("publish_rubric", args, err(
                "not_found", f"no email {source_email_id!r}"))
        if not isinstance(items, list) or not items:
            return self._record("publish_rubric", args, err(
                "invalid_value", "items must be a non-empty list"))
        total = 0
        for it in items:
            for k in ("item_key", "description", "max_points", "expected_key",
                      "item_ord"):
                if k not in it:
                    return self._record("publish_rubric", args, err(
                        "invalid_value", f"item missing {k}"))
            if not isinstance(it["max_points"], int):
                return self._record("publish_rubric", args, err(
                    "type_error", "max_points must be int"))
            total += it["max_points"]
        # Replace existing rubric for assignment if any
        old = self._one("SELECT rubric_id FROM b.rubrics WHERE assignment_id = ?",
                        (assignment_id,))
        if old:
            self.con.execute("DELETE FROM b.rubric_items WHERE rubric_id = ?",
                             (old["rubric_id"],))
            self.con.execute("DELETE FROM b.rubrics WHERE rubric_id = ?",
                             (old["rubric_id"],))
        self._rubric_seq += 1
        rid = f"RUB-{self._rubric_seq:04d}"
        self.con.execute(
            "INSERT INTO b.rubrics VALUES (?,?,?,?,?)",
            (rid, assignment_id, total, ENV_NOW, source_email_id))
        for it in items:
            self.con.execute(
                "INSERT INTO b.rubric_items VALUES (?,?,?,?,?,?)",
                (rid, it["item_key"], it["description"], it["max_points"],
                 it["expected_key"], it["item_ord"]))
        self.con.commit()
        return self._record("publish_rubric", args, ok(
            rubric_id=rid, total_points=total))

    def set_item_scores(self, submission_id: str, user_id: str,
                        item_scores: dict, comment: str = "") -> dict:
        """item_scores: {item_key: points}. Creates/updates grade + grade_items."""
        args = {"submission_id": submission_id, "user_id": user_id,
                "item_scores": item_scores, "comment": comment}
        sub = self._one("SELECT * FROM b.submissions WHERE submission_id = ?",
                        (submission_id,))
        if not sub:
            return self._record("set_item_scores", args, err(
                "not_found", f"no submission {submission_id!r}"))
        if not self._one("SELECT 1 FROM b.students WHERE user_id = ?", (user_id,)):
            return self._record("set_item_scores", args, err(
                "not_found", f"no student {user_id!r}"))
        if not isinstance(item_scores, dict) or not item_scores:
            return self._record("set_item_scores", args, err(
                "invalid_value", "item_scores must be a non-empty object"))
        for k, v in item_scores.items():
            if not isinstance(v, int):
                return self._record("set_item_scores", args, err(
                    "type_error", f"points for {k} must be int"))
        total = sum(item_scores.values())
        existing = self._one(
            "SELECT grade_id FROM b.grades WHERE submission_id = ?",
            (submission_id,))
        if existing:
            gid = existing["grade_id"]
            self.con.execute("DELETE FROM b.grade_items WHERE grade_id = ?", (gid,))
            self.con.execute(
                "UPDATE b.grades SET user_id=?, grade_total=?, comment=?, "
                "graded_at=? WHERE grade_id=?",
                (user_id, total, comment, ENV_NOW, gid))
        else:
            self._grade_seq += 1
            gid = f"GRD-{self._grade_seq:04d}"
            self.con.execute(
                "INSERT INTO b.grades VALUES (?,?,?,?,?,?)",
                (gid, submission_id, user_id, total, comment, ENV_NOW))
        for k, v in item_scores.items():
            self.con.execute(
                "INSERT INTO b.grade_items VALUES (?,?,?)", (gid, k, v))
        self.con.commit()
        docx_path = None
        if self.artifacts_dir is not None:
            # Rebuild full book gradesheet after each grade write.
            grades = self._rows(
                "SELECT g.submission_id, g.user_id, g.grade_total, g.comment, "
                "s.display_name FROM b.grades g "
                "LEFT JOIN b.students s ON s.user_id = g.user_id "
                "ORDER BY g.submission_id")
            sections = []
            for g in grades:
                items = self._rows(
                    "SELECT gi.item_key, gi.points FROM b.grade_items gi "
                    "JOIN b.grades gg ON gg.grade_id = gi.grade_id "
                    "WHERE gg.submission_id = ? ORDER BY gi.item_key",
                    (g["submission_id"],))
                body = "\n".join(
                    f"{it['item_key']}: {it['points']}" for it in items)
                body += f"\nTotal: {g['grade_total']}"
                if g.get("comment"):
                    body += f"\nComment: {g['comment']}"
                sections.append(
                    (f"{g['submission_id']} · {g.get('display_name') or g['user_id']}",
                     body))
            docx = self.artifacts_dir / "reports" / "gradescope_gradesheet.docx"
            write_docx(docx, title="Gradescope Gradesheet", sections=sections)
            docx_path = self._note_file("docx", docx, grade_id=gid)
        return self._record("set_item_scores", args, ok(
            grade_id=gid, grade_total=total, docx_path=docx_path))

    def resolve_regrade(self, regrade_id: str, decision: str,
                        resolution_note: str,
                        adjusted_total: int | None = None) -> dict:
        args = {"regrade_id": regrade_id, "decision": decision,
                "resolution_note": resolution_note,
                "adjusted_total": adjusted_total}
        rg = self._one("SELECT * FROM b.regrade_requests WHERE regrade_id = ?",
                       (regrade_id,))
        if not rg:
            return self._record("resolve_regrade", args, err(
                "not_found", f"no regrade {regrade_id!r}"))
        if decision not in ("uphold", "adjust"):
            return self._record("resolve_regrade", args, err(
                "invalid_value", "decision must be uphold|adjust"))
        status = "upheld" if decision == "uphold" else "adjusted"
        if decision == "adjust":
            if adjusted_total is None or not isinstance(adjusted_total, int):
                return self._record("resolve_regrade", args, err(
                    "invalid_value", "adjusted_total required int when adjusting"))
            g = self._one(
                "SELECT * FROM b.grades WHERE submission_id = ?",
                (rg["submission_id"],))
            if g:
                self.con.execute(
                    "UPDATE b.grades SET grade_total = ? WHERE grade_id = ?",
                    (adjusted_total, g["grade_id"]))
        self.con.execute(
            "UPDATE b.regrade_requests SET status=?, resolution_note=?, "
            "resolved_at=? WHERE regrade_id=?",
            (status, resolution_note, ENV_NOW, regrade_id))
        self.con.commit()
        return self._record("resolve_regrade", args, ok(
            regrade_id=regrade_id, status=status))
