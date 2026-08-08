"""Retired annual-review domain.

SwivelBench banking is now `envs.commercial_banking` (CB-* tasks). This package
remains only as a clear import error for old CR-* callers.
"""


def __getattr__(name: str):
    raise ImportError(
        "envs.credit_ops has been replaced by envs.commercial_banking. "
        "Use CB-* task ids (e.g. CB-SEED-001) via envs.registry.resolve."
    )
