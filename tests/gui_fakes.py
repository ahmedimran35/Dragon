"""Shared fakes for the GUI operator's tests: a link to a scripted device, a stub act
tool, screen fixtures and the approval-less UI the operator loop is driven with.

The operator (:mod:`dragon.gui.operator`) speaks to anything that looks like a link —
``screen()``, ``act(params)``, ``task_event(…)``, ``last_screen`` — so the tests give it
:class:`FakeLink` and :class:`FakeAct` and script the device's answers with plain dicts.
"""

from __future__ import annotations

import asyncio
import base64
import json
import struct
import zlib
from pathlib import Path
from typing import Any

from dragon.config import Settings
from dragon.gui.errors import STOP_MARKER
from dragon.gui.screen import Screen
from dragon.schema import LLMResponse, RiskLevel, ToolResult
from dragon.sentinel import AuditLog, Sentinel
from dragon.tools.base import BaseTool, CallAssessment
from dragon.ui import ApprovalDecision, ApprovalRequest


def png(width: int, height: int) -> str:
    """A real (tiny) PNG of the given size, base64 — one grey row, repeated."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    ).decode()


PAY_SCREEN = {
    "app": "alipay",
    "app_name": "支付宝",
    "route": "/transfer/confirm",
    "width": 390,
    "height": 844,
    "keyboard": False,
    "screenshot": png(39, 84),
}

HOME_SCREEN = {
    "app": "launcher",
    "app_name": "Home",
    "width": 390,
    "height": 844,
    "screenshot": png(39, 84),
}

LOGIN_SCREEN = {
    "app": "com.tencent.mm",
    "app_name": "微信",
    "width": 1080,
    "height": 2400,
    "screenshot": png(36, 80),
    "nodes": [
        {"id": "0.1", "class": "TextView", "text": "手机号登录", "cx": 540, "cy": 300},
        {
            "id": "0.2.0",
            "class": "EditText",
            "hint": "密码",
            "cx": 540,
            "cy": 900,
            "editable": True,
            "password": True,
        },
        {"id": "0.3", "class": "Button", "text": "登录", "cx": 540, "cy": 1200, "clickable": True},
        {"id": "0.4", "class": "View", "cx": 10, "cy": 10, "clickable": True},
        {
            "id": "0.5",
            "class": "CheckBox",
            "text": "记住我",
            "cx": 100,
            "cy": 1000,
            "checked": False,
        },
        "not a node",
    ],
}


def reply(action: str, thought: str = "look", **arguments: Any) -> LLMResponse:
    """A model turn in the computer_use dialect."""
    call = {"name": "computer_use", "arguments": {"action": action, **arguments}}
    return LLMResponse(
        content=f"Thought: {thought}\nAction: {arguments.pop('_label', action)}\n"
        f"<tool_call>\n{json.dumps(call, ensure_ascii=False)}\n</tool_call>"
    )


def labelled(label: str, action: str, **arguments: Any) -> LLMResponse:
    call = {"name": "computer_use", "arguments": {"action": action, **arguments}}
    return LLMResponse(
        content=f"Thought: I see it.\nAction: {label}\n<tool_call>\n{json.dumps(call, ensure_ascii=False)}\n</tool_call>"
    )


class FakeDevice:
    """What a device on the other end of a link says about itself."""

    def __init__(
        self,
        name: str = "Test computer",
        platform: str = "mobilegym",
        width: int = 390,
        height: int = 844,
        apps: str = "微信, 支付宝",
    ) -> None:
        self.name = name
        self.platform = platform
        self.width = width
        self.height = height
        self.apps = apps

    def app_list(self) -> str:
        return self.apps

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "platform": self.platform}


class FakeLink:
    """A link to a scripted device: answers ``screen`` and ``act`` from a list of screens.

    It speaks the little interface the GUI operator and its act tool need: ``screen()``
    and ``act(params)`` as coroutines, ``task_event(kind, text)`` for the task's card,
    ``last_screen`` with the freshest observation and ``wait_connected`` for a link that
    dropped. The actions taken land in ``acts``; the task events in ``tasks``."""

    def __init__(
        self,
        screens: list[dict[str, Any]],
        shots_dir: Path | None = None,
        stop_after: int = 0,
        device: FakeDevice | None = None,
    ) -> None:
        self.screens = list(screens)
        self.acts: list[dict[str, Any]] = []
        self.tasks: list[dict[str, Any]] = []
        self.shots_dir = shots_dir
        self.stop_after = stop_after  # the n-th action comes back with the Stop marker
        self.hang = False  # a device that never answers a screen or an action
        self.hung = 0  # how many requests it swallowed that way
        self.device = device or FakeDevice()
        self.last_screen: Screen | None = None
        self.stopped = False

    def current(self) -> dict[str, Any]:
        return self.screens[0] if len(self.screens) == 1 else self.screens.pop(0)

    async def screen(self) -> Screen:
        if self.hang:
            self.hung += 1
            await asyncio.sleep(3600)
        self.last_screen = Screen.from_device(self.current(), shots_dir=self.shots_dir)
        return self.last_screen

    async def act(self, params: dict[str, Any]) -> Screen:
        self.acts.append(params)
        return await self.screen()

    async def task_event(self, kind: str, text: str = "") -> None:
        self.tasks.append({"op": "task", "kind": kind, "text": text})

    async def wait_connected(self, grace: float) -> bool:
        return True

    def stop(self) -> bool:
        self.stopped = True
        return True


class FakeAct(BaseTool):
    """The act tool the operator drives: records the action and looks again."""

    name: str = "fake_act"
    description: str = "one action on the device"
    parameters: dict[str, Any] = {"type": "object", "properties": {"action": {"type": "string"}}}
    risk: RiskLevel = RiskLevel.MODERATE
    link: Any = None

    def assess(self, args: dict[str, Any]) -> CallAssessment:
        return CallAssessment(
            risk=RiskLevel.MODERATE,
            egress=False,
            egress_target=None,
            target=None,
            summary=f"{self.name}: {args.get('action', '?')}",
        )

    async def execute(self, **params: Any) -> ToolResult:
        self.link.acts.append(params)
        if self.link.stop_after and len(self.link.acts) >= self.link.stop_after:
            return ToolResult.fail(f"the user pressed Stop on the device ({STOP_MARKER})")
        screen = await self.link.screen()
        return ToolResult(output=screen.render())


class AutoApproveUI:
    def __init__(self, approve: bool = True):
        self.approve = approve
        self.requests: list[ApprovalRequest] = []
        self.calls: list[str] = []

    def on_text_delta(self, text: str) -> None: ...
    def on_assistant_message(self, content, reasoning) -> None: ...  # noqa: ANN001
    def on_tool_call(self, call, summary: str) -> None:  # noqa: ANN001
        self.calls.append(summary)

    def on_tool_result(self, call, result) -> None: ...  # noqa: ANN001
    def on_sentinel(self, decision: str, summary: str, reasons: list[str]) -> None: ...
    def info(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...

    async def ask_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        self.requests.append(request)
        return ApprovalDecision(approved=self.approve, reason="" if self.approve else "no")

    async def ask_user(self, question: str) -> str:
        return ""


def make_sentinel(settings: Settings, ui: AutoApproveUI) -> Sentinel:
    audit = AuditLog(settings.data_dir / "audit.jsonl", session_id="t")
    return Sentinel(settings.sentinel, audit=audit, ui=ui)
