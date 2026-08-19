"""Fixture-backed Gmail-compatible adapter.

The interface mirrors the operations used by the optional Gmail connector,
which makes local evaluation deterministic and live integration read-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Message:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    sent_at: str
    body: str
    attachments: tuple[dict[str, Any], ...] = ()


class FixtureMailbox:
    def __init__(self, messages: list[Message]):
        self._messages = {m.message_id: m for m in messages}

    def search_messages(self, query: str = "") -> dict[str, Any]:
        needle = query.lower().strip()
        rows = [m for m in self._messages.values()
                if not needle or needle in (m.subject + " " + m.body).lower()]
        rows.sort(key=lambda m: m.sent_at, reverse=True)
        return {"messages": [self._summary(m) for m in rows]}

    def get_message(self, message_id: str) -> dict[str, Any]:
        m = self._messages.get(message_id)
        if not m:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "message": {
            "message_id": m.message_id, "thread_id": m.thread_id,
            "sender": m.sender, "subject": m.subject, "sent_at": m.sent_at,
            "body": m.body, "attachments": list(m.attachments)}}

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        rows = [m for m in self._messages.values() if m.thread_id == thread_id]
        rows.sort(key=lambda m: m.sent_at)
        return {"messages": [self.get_message(m.message_id)["message"] for m in rows]}

    def download_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        m = self._messages.get(message_id)
        if not m:
            return {"ok": False, "error": "not_found"}
        for a in m.attachments:
            if a.get("attachment_id") == attachment_id:
                return {"ok": True, "attachment": dict(a)}
        return {"ok": False, "error": "attachment_not_found"}

    @staticmethod
    def _summary(m: Message) -> dict[str, Any]:
        return {"message_id": m.message_id, "thread_id": m.thread_id,
                "sender": m.sender, "subject": m.subject, "sent_at": m.sent_at,
                "has_attachments": bool(m.attachments)}
