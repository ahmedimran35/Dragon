"""Bots as first-class personas: ``/api/bots``, a thread's ``bot_id``, the ``bots`` and
thread ``bot_id`` of the state snapshot, the audit entry's ``bot`` field, and the bot name
on the Sentinel's prompts. MockLLM throughout; no network."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dragon.bots import current_bot, current_bot_id
from dragon.config import SentinelSettings, Settings
from dragon.llm import MockLLM
from dragon.schema import Function, RiskLevel, ToolCall, ToolResult
from dragon.sentinel import AuditLog, Sentinel
from dragon.sentinel.gate import TaskContext, current_task
from dragon.server import create_app
from dragon.server.service import DragonService
from dragon.tools.base import BaseTool
from dragon.ui import ApprovalDecision, ApprovalRequest, HeadlessUI

# the Bot object the three layers share
BOT_KEYS = {
    "id",
    "name",
    "avatar",
    "emoji",
    "color",
    "tagline",
    "tone",
    "communication",
    "style",
    "instructions",
    "model",
    "created_at",
}


@pytest.fixture()
def server(settings: Settings) -> Iterator[tuple[TestClient, DragonService]]:
    settings.server.token = "secret-token"
    service = DragonService(settings, llm=MockLLM([]))
    app = create_app(settings, service)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer secret-token"
        yield client, service


# ----------------------------------------------------------------------------- the routes
def test_bot_routes_create_change_and_remove(server):
    client, service = server
    listing = client.get("/api/bots").json()
    assert set(listing) == {"bots"} and len(listing["bots"]) == 1
    default = listing["bots"][0]
    assert default["id"] == "default" and default["name"] == service.settings.agent.name
    assert set(default) == BOT_KEYS and isinstance(default["created_at"], int)

    created = client.post(
        "/api/bots",
        json={"name": "Scout", "tagline": "Keeps an eye out.", "model": "gpt-6.1-sol"},
    )
    assert created.status_code == 201, created.text
    bot = created.json()["bot"]
    assert set(created.json()) == {"bot"} and set(bot) == BOT_KEYS
    assert re.fullmatch(r"b_[0-9a-f]{8}", bot["id"])
    assert bot["name"] == "Scout" and bot["tagline"] == "Keeps an eye out."
    # the model is stored as given; "" would mean the runtime default
    assert bot["model"] == "gpt-6.1-sol"

    patched = client.patch(f"/api/bots/{bot['id']}", json={"tagline": "On patrol."})
    assert patched.status_code == 200, patched.text
    assert set(patched.json()) == {"bot"}
    assert patched.json()["bot"]["name"] == "Scout", "a partial change leaves the rest alone"
    assert patched.json()["bot"]["tagline"] == "On patrol."
    assert client.patch("/api/bots/b_nobody00", json={"name": "x"}).status_code == 404

    gone = client.delete(f"/api/bots/{bot['id']}")
    assert gone.status_code == 200 and gone.json() == {"ok": True}
    assert [b["id"] for b in client.get("/api/bots").json()["bots"]] == ["default"]
    assert client.delete(f"/api/bots/{bot['id']}").status_code == 404


def test_the_default_bot_cannot_be_deleted(server):
    client, service = server
    refused = client.delete("/api/bots/default")
    assert refused.status_code == 400
    # the reason travels under "error", as the shared contract has it
    assert refused.json()["error"]
    assert [b["id"] for b in client.get("/api/bots").json()["bots"]] == ["default"]
    assert client.delete("/api/bots/b_nobody00").status_code == 404


# ----------------------------------------------------------------------------- threads & state
def test_thread_creation_with_and_without_a_bot(server):
    client, service = server
    plain = client.post("/api/threads", json={"title": "Notes"}).json()
    assert plain["bot_id"] == "default" == service.default_bot_id
    bot = client.post("/api/bots", json={"name": "Scout"}).json()["bot"]
    as_scout = client.post("/api/threads", json={"title": "Scout chat", "bot_id": bot["id"]})
    assert as_scout.status_code == 200, as_scout.text
    assert as_scout.json()["bot_id"] == bot["id"]
    assert (
        client.post("/api/threads", json={"title": "Nowhere", "bot_id": "b_nobody00"}).status_code
        == 404
    )


def test_the_state_snapshot_carries_bots_and_each_thread_bot(server):
    client, service = server
    bot = client.post("/api/bots", json={"name": "Scout"}).json()["bot"]
    thread = client.post("/api/threads", json={"title": "Scout chat", "bot_id": bot["id"]}).json()
    state = client.get("/api/state").json()
    assert [b["id"] for b in state["bots"]] == ["default", bot["id"]]
    assert all(set(b) == BOT_KEYS for b in state["bots"])
    metas = {t["id"]: t for t in state["threads"]}
    assert metas["main"]["bot_id"] == "default"
    assert metas[thread["id"]]["bot_id"] == bot["id"]


# ----------------------------------------------------------------------------- the audit log
class Echo(BaseTool):
    name: str = "echo"
    description: str = "echo"
    parameters: dict[str, Any] = {"type": "object", "properties": {"text": {"type": "string"}}}
    risk: RiskLevel = RiskLevel.SAFE

    async def execute(self, text: str = "", **_: Any) -> ToolResult:
        return ToolResult(output=f"echo: {text}")


def call(name: str, **args: Any) -> ToolCall:
    return ToolCall(function=Function(name=name, arguments=json.dumps(args)))


def test_every_audit_entry_names_its_bot(tmp_path: Path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    gate = Sentinel(SentinelSettings(), audit, HeadlessUI())
    # outside any agent run nothing is known about a bot
    assert audit.record("user_message", content="hi")["bot"] == ""
    token = gate.begin_task(
        "look around", conversation="t_1", bot_name="Scout", bot_id="b_1234abcd"
    )
    assert audit.record("tool_call", tool="echo")["bot"] == "b_1234abcd"
    # a caller that knows the bot says so itself
    assert audit.record("tool_call", tool="echo", bot="b_called00")["bot"] == "b_called00"
    gate.end_task(token)
    assert audit.record("user_message", content="again")["bot"] == ""


async def test_a_guarded_call_is_audited_with_the_bot(tmp_path: Path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    gate = Sentinel(SentinelSettings(), audit, HeadlessUI())
    token = gate.begin_task("try it", conversation="t_1", bot_name="Scout", bot_id="b_1234abcd")
    result = await gate.guard(call("echo", text="hi"), Echo())
    gate.end_task(token)
    assert result.ok
    entry = audit.tail()[-1]
    assert entry["event"] == "tool_call" and entry["decision"] == "allow"
    assert entry["bot"] == "b_1234abcd"


def test_lines_written_before_the_bot_field_still_parse(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        '{"ts": "2026-01-01T00:00:00.000+00:00", "event": "tool_call", "tool": "echo", '
        '"decision": "allow"}\n',
        "utf-8",
    )
    entries = AuditLog(path).tail()
    assert entries[0]["event"] == "tool_call" and entries[0]["tool"] == "echo"
    assert entries[0]["bot"] == "", "an old line reads as no bot known"


# ----------------------------------------------------------------------------- the task context
class RecordingUI(HeadlessUI):
    """Approves and keeps the approval requests for inspection."""

    def __init__(self) -> None:
        super().__init__(approve=True)
        self.requests: list[ApprovalRequest] = []

    async def ask_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        self.requests.append(request)
        return ApprovalDecision(approved=True)


def test_the_task_context_carries_the_bot():
    ctx = TaskContext(id="run-1", bot_name="Scout", bot_id="b_1234abcd")
    assert ctx.bot_name == "Scout" and ctx.bot_id == "b_1234abcd"
    # the keyword fields default to "nothing known", so older call sites keep working
    plain = TaskContext(id="run-2")
    assert plain.bot_name == "" and plain.bot_id == ""
    gate = Sentinel(SentinelSettings(), AuditLog(Path("unused.jsonl")), HeadlessUI())
    token = gate.begin_task("a job", bot_name="Scout", bot_id="b_1234abcd")
    assert current_task() is not None and current_task().bot_name == "Scout"
    assert current_task().bot_id == "b_1234abcd"
    gate.end_task(token)
    token = gate.begin_task(context=TaskContext(id="run-3", bot_name="Wren"))
    assert current_task() is not None and current_task().id == "run-3"
    assert current_task().bot_name == "Wren" and current_task().bot_id == ""
    gate.end_task(token)


def test_the_running_bot_fills_the_task_context(tmp_path: Path):
    """A run that does not name its bot takes the running turn's bot."""
    audit = AuditLog(tmp_path / "a.jsonl")
    gate = Sentinel(SentinelSettings(), audit, HeadlessUI())
    bot_token = current_bot_id.set("b_1234abcd")
    persona_token = current_bot.set({"id": "b_1234abcd", "name": "Scout"})
    try:
        token = gate.begin_task("a job", conversation="t_1")
        assert current_task() is not None
        assert current_task().bot_name == "Scout" and current_task().bot_id == "b_1234abcd"
        assert audit.record("tool_call", tool="echo")["bot"] == "b_1234abcd"
        gate.end_task(token)
    finally:
        current_bot.reset(persona_token)
        current_bot_id.reset(bot_token)


async def test_the_allow_app_prompt_uses_the_bot_name(tmp_path: Path):
    """ "Let <name> use <App>?": the bot the run speaks as when it has one, else the agent's
    own name as the caller has it."""
    ui = RecordingUI()
    gate = Sentinel(SentinelSettings(), AuditLog(tmp_path / "a.jsonl"), ui)
    token = gate.begin_task("paint", conversation="t_1", bot_name="Scout", bot_id="b_1234abcd")
    assert await gate.allow_app("com.example.Notes", "Notes", "Ember")
    assert ui.requests[-1].summary == "Let Scout use Notes?"
    gate.end_task(token)
    # no bot on the run: the agent's own name, as the caller has it
    token = gate.begin_task("paint")
    await gate.allow_app("com.example.Notes", "Notes", "Ember")
    assert ui.requests[-1].summary == "Let Ember use Notes?"
    gate.end_task(token)
    # and the caller's own fallback when it has no name either
    await gate.allow_app("com.example.Notes", "Notes")
    assert ui.requests[-1].summary == "Let Dragon use Notes?"
