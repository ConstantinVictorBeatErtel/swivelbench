"""Versioned JSON-serializable contracts for content artifacts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA_VERSION = "swivelbench.content.v1"


def _clean(value: Any) -> Any:
    """Convert nested dataclasses to JSON-safe values."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    url: str
    publisher: str
    title: str
    accessed_at: str
    license: str
    permitted_use: Literal["source", "research_only", "distributable"]
    sha256: str = ""
    local_artifact: str = ""
    notes: str = ""
    modified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class FilingSnapshot:
    company_id: str
    ticker: str
    cik: str
    accession: str
    form: str
    filed_date: str
    period_end: str
    primary_document: str
    primary_sha256: str
    companyfacts_sha256: str
    source_url: str
    local_artifact: str = ""
    index_artifact: str = ""
    xbrl_artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class SecFact:
    fact_id: str
    company_id: str
    taxonomy: str
    concept: str
    value: float | int | str
    unit: str
    start_date: str | None
    end_date: str | None
    instant_date: str | None
    form: str
    filed_date: str
    accession: str
    source_url: str
    source_artifact: str
    context_hash: str = ""
    derivation_rule: str = "reported"
    confidence: Literal["high", "review", "unavailable"] = "high"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class ReportSectionSpec:
    section_id: str
    title: str
    purpose: str
    required_evidence: tuple[str, ...] = ()
    calculations: tuple[str, ...] = ()
    required_claims: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()
    verifier_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))


@dataclass(frozen=True)
class ReportSpec:
    report_type: str
    title: str
    sections: tuple[ReportSectionSpec, ...]
    required_evidence: tuple[str, ...] = ()
    decision_rules: tuple[str, ...] = ()
    format_contract: dict[str, Any] = field(default_factory=dict)
    verifier_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "report_type": self.report_type,
            "title": self.title,
            "sections": [s.to_dict() for s in self.sections],
            "required_evidence": list(self.required_evidence),
            "decision_rules": list(self.decision_rules),
            "format_contract": _clean(self.format_contract),
            "verifier_ids": list(self.verifier_ids),
        }


@dataclass(frozen=True)
class CourseSpec:
    course_id: str
    title: str
    discipline: str
    split: Literal["train", "validation", "test"]
    learning_objectives: tuple[str, ...]
    policies: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class QuestionSpec:
    question_id: str
    assessment_id: str
    question_type: str
    prompt: str
    learning_objective: str
    difficulty: str
    points: int
    answer_key_ref: str
    rubric_ref: str
    misconception_ids: tuple[str, ...] = ()
    render_contract: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class AssessmentSpec:
    assessment_id: str
    course_id: str
    assessment_type: str
    title: str
    instructions_ref: str
    question_ids: tuple[str, ...]
    allowed_resources: tuple[str, ...]
    grading_policy_ref: str
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class RubricCriterion:
    criterion_id: str
    question_id: str
    description: str
    points: int
    verifier: str
    required_evidence: tuple[str, ...] = ()
    role: str = "required"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class SubmissionManifest:
    submission_id: str
    assessment_id: str
    profile_id: str
    response_ref: str
    rendered_artifacts: tuple[str, ...]
    visible_answer_hash: str
    gold_ref: str
    review_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_VERSION, **_clean(asdict(self))}


@dataclass(frozen=True)
class ContentManifest:
    corpus_version: str
    split: str
    generated_at: str
    public_inputs: tuple[str, ...]
    private_gold_refs: tuple[str, ...]
    source_ids: tuple[str, ...]
    artifact_hashes: dict[str, str]
    renderer_version: str
    task_ids: tuple[str, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            **_clean(asdict(self)),
        }
