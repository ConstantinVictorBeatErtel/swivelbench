"""Synthetic multimodal teaching-assistant benchmark."""

from .generator import generate
from .scoring import score_session

__all__ = ["generate", "score_session"]
