"""The roster tool: the chief of staff's ``bots`` (list / create / update / delete).

Every bot's tool collection contains this tool — the boundary is the runtime check, not
the schema: the call refuses unless the bot whose turn is running is the chief of staff
(:func:`dragon.bots.running_bot_id`), so a staff bot that tries is answered with one
sentence and nothing changes. The tool works through ``DragonService``'s bot methods —
the same code path as ``/api/bots`` — so deleting a bot reassigns its chat to the chief
and the chief's identity keeps mirroring into the profile.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dragon.bots import DEFAULT_BOT_ID, ROLE_CHIEF, running_bot_id
from dragon.prompts import COMMUNICATION, TONES
from dragon.schema import RiskLevel, ToolResult
from dragon.tools.base import BaseTool, CallAssessment

# the persona fields a caller may set (the bot's `role` is server-owned and never set)
PERSONA_FIELDS = (
    "name",
    "avatar",
    "emoji",
    "color",
    "tagline",
    "tone",
    "communication",
    "style",
    "instructions",
)

CHIEF_ONLY = "Only the chief of staff manages the roster."
CHIEF_KEEPS = "The chief of staff cannot be removed from the roster."
NO_SERVICE = "The roster is only available while the Dragon server is running."
ACTIONS = ("list", "create", "update", "delete")


def _render(bot: dict[str, Any]) -> str:
    """One bot as plain text: id, name and role first, then the fields that brief it."""
    head = f"{bot.get('name') or '?'} ({bot.get('id')}, {bot.get('role') or 'staff'})"
    lines = [head]
    for key in ("tagline", "tone", "communication", "style", "instructions"):
        value = str(bot.get(key) or "").strip()
        if value:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


class Bots(BaseTool):
    name: str = "bots"
    description: str = (
        "Manage the roster of bots: the staff personas the user's chats speak as. Only the "
        "chief of staff (the default bot) manages the roster; a call from any other bot is "
        "refused. Actions: `list` (every bot with its id, role, tagline, tone and "
        "instructions; read it before you brief anyone), `create` (name plus any of "
        "avatar, emoji, color, tagline, tone, communication, style, instructions: a new "
        "staff bot and its brief), `update` (bot_id plus any field to change; pass "
        "`instructions` to give a bot a new brief), `delete` (bot_id: remove a staff bot; "
        "its chat falls back to the chief). Every bot you create is staff; the chief of "
        "staff cannot be deleted."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(ACTIONS),
            },
            "bot_id": {
                "type": "string",
                "description": "Which bot (the id from `list`); required for update and delete.",
            },
            "name": {"type": "string", "description": "The bot's name (required for create)."},
            "avatar": {
                "type": "string",
                "description": "The face: 'dragon', a studio face id, or '' for the emoji.",
            },
            "emoji": {"type": "string"},
            "color": {"type": "string"},
            "tagline": {"type": "string", "description": "One line under the name."},
            "tone": {
                "type": "string",
                "description": "How it talks. One of: " + ", ".join(TONES) + ", or ''.",
            },
            "communication": {
                "type": "string",
                "description": "Length and shape of replies. One of: "
                + ", ".join(COMMUNICATION)
                + ", or ''.",
            },
            "style": {"type": "string", "description": "Free text about how it writes."},
            "instructions": {
                "type": "string",
                "description": "The bot's standing brief: what it does and how it works.",
            },
        },
        "required": ["action"],
    }
    risk: RiskLevel = RiskLevel.SAFE
    # the live DragonService through a getter: the tool is built in DragonApp._build_tools
    # before the service exists, and DragonService points DragonApp.service at itself once
    # constructed. Without one (the CLI's plain agent) there is no roster to manage.
    service: Callable[[], Any] | None = None

    # ------------------------------------------------------------------ assessment
    def _svc(self) -> Any:
        return self.service() if self.service is not None else None

    def _name_of(self, bot_id: str) -> str:
        """A bot's name as the roster has it, for the summary on an approval card."""
        svc = self._svc()
        if svc is not None:
            for bot in svc.list_bots():
                if bot.get("id") == bot_id:
                    return str(bot.get("name") or "")
        return ""

    def assess(self, args: dict[str, Any]) -> CallAssessment:
        a = super().assess(args)
        action = str(args.get("action") or "?")
        name = str(args.get("name") or "").strip()
        bot_id = str(args.get("bot_id") or "").strip()
        if action == "create":
            # a new persona is state (strict mode asks); so is changing one or removing it
            a.risk = RiskLevel.MODERATE
            a.summary = "Creating a staff bot" + (f": {name}" if name else "")
        elif action == "update":
            a.risk = RiskLevel.MODERATE
            changed = [k for k in PERSONA_FIELDS if k in args and args.get(k) is not None]
            who = self._name_of(bot_id) or bot_id
            a.summary = f"Updating {who}" + (f": {', '.join(changed)}" if changed else "")
        elif action == "delete":
            a.risk = RiskLevel.SENSITIVE
            who = self._name_of(bot_id) or bot_id or "?"
            a.summary = f"Removing {who} from the roster"
        else:
            a.summary = "Listing the roster"
        return a

    # ------------------------------------------------------------------ execution
    async def execute(
        self,
        action: str = "",
        bot_id: str | None = None,
        name: str | None = None,
        avatar: str | None = None,
        emoji: str | None = None,
        color: str | None = None,
        tagline: str | None = None,
        tone: str | None = None,
        communication: str | None = None,
        style: str | None = None,
        instructions: str | None = None,
        **_: Any,
    ) -> ToolResult:
        if running_bot_id() != DEFAULT_BOT_ID:
            return ToolResult.fail(CHIEF_ONLY)
        if action not in ACTIONS:
            return ToolResult.fail(f"unknown action '{action}'")
        svc = self._svc()
        if svc is None:
            return ToolResult.fail(NO_SERVICE)
        values = {
            "name": name,
            "avatar": avatar,
            "emoji": emoji,
            "color": color,
            "tagline": tagline,
            "tone": tone,
            "communication": communication,
            "style": style,
            "instructions": instructions,
        }
        try:
            if action == "list":
                bots = svc.list_bots()
                return ToolResult(output="\n\n".join(_render(b) for b in bots))
            if action == "create":
                if not name:
                    return ToolResult.fail("`name` is required")
                data = {k: v for k, v in values.items() if v is not None}
                bot = svc.create_bot(data)
                return ToolResult(
                    output=f"Created {bot['name']} ({bot['id']}), on the staff.\n{_render(bot)}"
                )
            if not bot_id:
                return ToolResult.fail("`bot_id` is required")
            if action == "update":
                data = {k: v for k, v in values.items() if v is not None}
                if not data:
                    return ToolResult.fail("nothing to change: pass the fields to set")
                bot = svc.update_bot(bot_id, data)
                return ToolResult(output=f"Updated {bot['name']}.\n{_render(bot)}")
            if action == "delete":
                bot = next((b for b in svc.list_bots() if b.get("id") == bot_id), None)
                if bot is None:
                    return ToolResult.fail(f"no bot {bot_id}")
                if bot.get("role") == ROLE_CHIEF:
                    return ToolResult.fail(CHIEF_KEEPS)
                had_chat = any(t.bot_id == bot_id for t in svc.visible_threads())
                svc.delete_bot(bot_id)
                note = " Its chat now speaks as the chief of staff." if had_chat else ""
                return ToolResult(output=f"Removed {bot['name']} from the roster.{note}")
            return ToolResult.fail(f"unknown action '{action}'")
        except KeyError:
            return ToolResult.fail(f"no bot {bot_id}")
        except ValueError as exc:
            return ToolResult.fail(str(exc))


__all__ = ["Bots"]
