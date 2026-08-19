"""Content acquisition, generation, provenance, and release validation.

The package deliberately uses standard-library data structures for the core
contract. Optional renderers and model clients can sit on top without making
the manifest or offline verification path depend on a vendor SDK.
"""

from .jobs import GenerationJob, JobStore
from .provenance import append_jsonl, sha256_file
from .schemas import ContentManifest, FilingSnapshot, ReportSpec, SecFact, SourceRecord

__all__ = [
    "ContentManifest",
    "FilingSnapshot",
    "GenerationJob",
    "JobStore",
    "ReportSpec",
    "SecFact",
    "SourceRecord",
    "append_jsonl",
    "sha256_file",
]
