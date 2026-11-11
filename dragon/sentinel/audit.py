"""Append-only JSONL audit trail of everything the agent did (and was refused).

Every entry carries a ``bot`` field: the id of the bot whose run wrote it, "" when nothing
is known about one. Lines written before that field existed still parse; ``tail`` fills the
field in for them."""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _truncate(value: Any, limit: int = 500) -> Any:
    if isinstance(value, str):
        return (
            value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit} chars]"
        )
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value[:50]]
    return value


def _run_bot_id() -> str:
    """The id of the bot whose agent run is writing this entry: the Sentinel's task context
    when it names one, else the running turn's bot (:mod:`dragon.bots`); "" outside any run.
    Imported here only at call time: the gate imports this module."""
    from dragon.bots import running_bot, running_bot_id
    from dragon.sentinel.gate import current_task

    task = current_task()
    if task is not None and task.bot_id:
        return task.bot_id
    if running_bot() is not None:
        return running_bot_id()
    return ""


def channel_of(tool: str) -> str:
    """Which rung of the ladder a tool call is (docs/gui.md): ``gui`` for the screen the
    hands work on, ``browser`` for the Playwright browser, ``web`` for plain fetches and
    search, ``cli`` for shell and Python, ``api`` for MCP servers and connectors, ``local``
    for everything that stays in the workspace and memory.
    Recorded with every ``tool_call`` so the Activity view can show how much of the work needed
    the screen."""
    if tool.startswith("phone_"):
        return "gui"
    if tool.startswith("browser"):
        return "browser"
    if tool in ("web_fetch", "web_search"):
        return "web"
    if tool in ("shell", "python_execute"):
        return "cli"
    if "__" in tool or tool in ("send_email", "read_emails", "calendar", "contacts"):
        return "api"
    return "local"


class AuditLog:
    # roll over when the trail reaches this size; the old one is kept beside it as `.1`
    MAX_BYTES = 10 * 1024 * 1024

    def __init__(self, path: Path, session_id: str | None = None):
        self.path = Path(path)
        self.session_id = session_id
        self._lock = threading.Lock()

    def record(self, event: str, **fields: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "event": event,
            # which bot did this: the id of the bot whose run wrote the entry, "" when
            # nothing is known about one. Every entry carries the field, so a reader meets
            # the same shape on every line (older lines may lack it; `tail` fills it in).
            "bot": str(fields.pop("bot", "") or _run_bot_id()),
        }
        if self.session_id:
            entry["session"] = self.session_id
        entry.update(_truncate(fields))
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size >= self.MAX_BYTES:
                self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return entry

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            lines = deque(fh, maxlen=n)
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                # a line from before the bot field existed reads as "no bot known"
                entry.setdefault("bot", "")
            out.append(entry)
        return out


__all__ = ["AuditLog", "channel_of"]
