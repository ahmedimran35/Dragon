"""The roster tool for the chief of staff: ``bots`` (list / create / update / delete) —
every action through the tool path and the service's bot methods, its risk levels and the
delete approval card, and the two refusals (a staff bot that tries, and the chief deleting
itself). MockLLM through a real DragonService; no network."""

from __future__ import annotations

import json
from typing import Any

import pytest

from dragon.bots import current_bot_id
from dragon.config import SentinelSettings, Settings
from dragon.llm import MockLLM
from dragon.schema import Function, RiskLevel, ToolCall
from dragon.sentinel import AuditLog, Sentinel
from dragon.server.service import DragonService
from dragon.tools.bots_tool import Bots
from dragon.ui import ApprovalDecision, ApprovalRequest, HeadlessUI


def call(name: str, **args: Any) -> ToolCall:
    return ToolCall(function=Function(name=name, arguments=json.dumps(args)))


class RecordingUI(HeadlessUI):
    """Approves (or declines) and keeps the approval requests — the cards — for inspection."""

    def __init__(self, approve: bool = True) -> None:
        super().__init__(approve=approve)
        self.approve = approve
        self.requests: list[ApprovalRequest] = []

    async def ask_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        self.requests.append(request)
        return ApprovalDecision(approved=self.approve)


@pytest.fixture()
def service(settings: Settings) -> DragonService:
    return DragonService(settings, llm=MockLLM([]))


def tool_of(service: DragonService) -> Bots:
    tool = service.app.tools.get("bots")
    assert tool is not None
    return tool  # type: ignore[return-value]


# ----------------------------------------------------------------------------- registration
def test_the_tool_is_registered_in_every_bot_toolbox(service):
    # one tool collection serves every bot, so every bot sees the tool: the runtime's
    # "chief only" check inside it is the boundary, not the schema
    tool = tool_of(service)
    params = tool.to_param()["function"]
    assert params["name"] == "bots"
    assert params["parameters"]["properties"]["action"]["enum"] == [
        "list",
        "create",
        "update",
        "delete",
    ]


# ----------------------------------------------------------------------------- the actions
async def test_list_shows_the_roster_with_roles_and_briefs(service):
    service.create_bot({"name": "Scout", "tone": "concise", "instructions": "Watch the weather."})
    out = await service.app.tools.execute("bots", {"action": "list"})
    assert out.ok
    assert "Ember (default, chief)" in out.output
    assert "Scout" in out.output and "(b_" in out.output and "staff)" in out.output
    assert "tone: concise" in out.output
    assert "instructions: Watch the weather." in out.output


async def test_create_and_update_go_through_the_service(service):
    out = await service.app.tools.execute(
        "bots",
        {
            "action": "create",
            "name": "Scout",
            "tagline": "Sees first",
            "tone": "concise",
            "instructions": "Watch the weather.",
            "role": "chief",  # swallowed by the tool; the roster owns the role
        },
    )
    assert out.ok and "Scout" in out.output
    made = service.list_bots()[-1]
    assert made["role"] == "staff" and made["tone"] == "concise"
    assert made["instructions"] == "Watch the weather." and made["tagline"] == "Sees first"

    # the same code path as the API: the one-chat rule sees the new bot at once
    first = service.create_thread("Scout chat", bot_id=made["id"])
    assert service.create_thread("again", bot_id=made["id"]).id == first.id

    # `update` is how the chief provides instruction
    out = await service.app.tools.execute(
        "bots",
        {"action": "update", "bot_id": made["id"], "instructions": "Watch the roads too."},
    )
    assert out.ok
    assert service.list_bots()[-1]["instructions"] == "Watch the roads too."

    # and changing the chief mirrors its identity into the profile, as the API does
    out = await service.app.tools.execute(
        "bots", {"action": "update", "bot_id": "default", "name": "Wren"}
    )
    assert out.ok and service.profile.name == "Wren"


async def test_delete_removes_a_staff_bot_and_its_chat(service):
    made = service.create_bot({"name": "Scout"})
    thread = service.create_thread("Scout chat", bot_id=made["id"])
    out = await service.app.tools.execute("bots", {"action": "delete", "bot_id": made["id"]})
    assert out.ok and "Removed Scout from the roster." in out.output
    assert "Its chat went with it." in out.output
    assert [b["id"] for b in service.list_bots()] == ["default"]
    # the same code path as the API: the chat goes when the bot goes
    assert thread.id not in service.threads


# ----------------------------------------------------------------------------- risk & card
def test_risk_levels_and_assessment_summaries(service):
    tool = tool_of(service)
    assert tool.assess({"action": "list"}).risk == RiskLevel.SAFE
    created = tool.assess({"action": "create", "name": "Scout"})
    assert created.risk == RiskLevel.MODERATE
    assert created.summary == "Creating a staff bot: Scout"
    made = service.create_bot({"name": "Scout"})
    updated = tool.assess(
        {"action": "update", "bot_id": made["id"], "tone": "concise", "instructions": "x"}
    )
    assert updated.risk == RiskLevel.MODERATE
    assert updated.summary == "Updating Scout: tone, instructions"
    deleted = tool.assess({"action": "delete", "bot_id": made["id"]})
    assert deleted.risk == RiskLevel.SENSITIVE
    assert deleted.summary == "Removing Scout from the roster"


async def test_delete_surfaces_as_an_approval_card(service):
    made = service.create_bot({"name": "Scout"})
    ui = RecordingUI()
    gate = Sentinel(SentinelSettings(), AuditLog(service.data_dir / "audit.jsonl"), ui)
    token = gate.begin_task("trim the roster", conversation="t_1")
    result = await gate.guard(call("bots", action="delete", bot_id=made["id"]), tool_of(service))
    gate.end_task(token)
    assert result.ok
    assert [b["id"] for b in service.list_bots()] == ["default"], "approved: it ran"
    assert len(ui.requests) == 1
    card = ui.requests[0]
    assert card.tool == "bots" and card.risk == RiskLevel.SENSITIVE
    assert card.summary == "Removing Scout from the roster"


async def test_a_declined_card_keeps_the_bot(service):
    made = service.create_bot({"name": "Scout"})
    ui = RecordingUI(approve=False)
    gate = Sentinel(SentinelSettings(), AuditLog(service.data_dir / "audit.jsonl"), ui)
    token = gate.begin_task("trim the roster", conversation="t_1")
    result = await gate.guard(call("bots", action="delete", bot_id=made["id"]), tool_of(service))
    gate.end_task(token)
    assert not result.ok
    assert ui.requests and ui.requests[0].summary == "Removing Scout from the roster"
    assert service.bots.get(made["id"]) is not None, "declined: nothing was removed"


# ----------------------------------------------------------------------------- refusals
async def test_only_the_chief_of_staff_manages_the_roster(service):
    made = service.create_bot({"name": "Scout"})
    tool = tool_of(service)
    token = current_bot_id.set(made["id"])
    try:
        for args in (
            {"action": "list"},
            {"action": "create", "name": "Spy"},
            {"action": "update", "bot_id": "default", "name": "Renamed"},
            {"action": "delete", "bot_id": made["id"]},
        ):
            out = await tool.execute(**args)
            assert not out.ok
            assert out.error == "Only the chief of staff manages the roster."
    finally:
        current_bot_id.reset(token)
    names = [b["name"] for b in service.list_bots()]
    assert names == [service.settings.agent.name, "Scout"], "a refused call changed nothing"


async def test_the_chief_cannot_delete_itself(service):
    tool = tool_of(service)
    out = await tool.execute(action="delete", bot_id="default")
    assert not out.ok
    assert out.error == "The chief of staff cannot be removed from the roster."
    assert [b["id"] for b in service.list_bots()] == ["default"]
    # an unknown id gets its own sentence
    out = await tool.execute(action="delete", bot_id="b_nobody00")
    assert not out.ok and "b_nobody00" in (out.error or "")


async def test_argument_mistakes_answer_with_one_sentence(service):
    tool = tool_of(service)
    out = await tool.execute(action="create")
    assert not out.ok and out.error == "`name` is required"
    out = await tool.execute(action="update", bot_id="default")
    assert not out.ok and "nothing to change" in (out.error or "")
    out = await tool.execute(action="dance")
    assert not out.ok and "unknown action" in (out.error or "")


async def test_without_a_running_server_the_tool_says_so():
    out = await Bots().execute(action="list")
    assert not out.ok
    assert out.error == "The roster is only available while the Dragon server is running."
