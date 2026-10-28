"""Bots as first-class personas: the bot store and its migration from profile.json, the
per-bot system prompt, threads bound to a bot, and memory scoped to the bot that wrote it."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

import pytest

from dragon.agent import DragonAgent
from dragon.bots import DEFAULT_BOT_ID, BotStore
from dragon.config import Settings
from dragon.llm import MockLLM
from dragon.memory import MemoryStore
from dragon.schema import Function, LLMResponse, Role, ToolCall, ToolResult
from dragon.sentinel import AuditLog, Sentinel
from dragon.server.service import TONES, DragonService
from dragon.tools import Recall, Remember, Terminate, ToolCollection
from dragon.tools.base import BaseTool
from dragon.ui import HeadlessUI


class Adder(BaseTool):
    name: str = "add"
    description: str = "add two numbers"
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
    }

    async def execute(self, a: float = 0, b: float = 0, **_: Any) -> ToolResult:
        return ToolResult(output=str(a + b))


def tc(name: str, **args: Any) -> ToolCall:
    return ToolCall(function=Function(name=name, arguments=json.dumps(args)))


def make_agent(
    settings: Settings,
    script: list,
    bot: dict[str, Any] | None = None,
    memory: MemoryStore | None = None,
):
    ui = HeadlessUI()
    memory = memory or MemoryStore(settings.memory_db)
    tools = ToolCollection(Terminate(), Adder(), Remember(store=memory), Recall(store=memory))
    audit = AuditLog(settings.audit_file)
    sentinel = Sentinel(settings.sentinel, audit, ui)
    llm = MockLLM(script)
    agent = DragonAgent(settings, llm, tools, sentinel, ui, audit, memory=memory, bot=bot)
    return agent, llm, memory


# ----------------------------------------------------------------------------- the store
def test_bot_store_crud_and_validation(tmp_path):
    store = BotStore(tmp_path / "bots.json")
    bots = store.list()
    assert [b["id"] for b in bots] == [DEFAULT_BOT_ID] and bots[0]["name"] == "Ember"
    assert bots[0]["role"] == "chief", "the default bot is the chief of staff"

    made = store.create({"name": "Scout", "tone": "concise", "style": "terse", "noise": 1})
    assert re.fullmatch(r"b_[0-9a-f]{8}", made["id"])
    assert isinstance(made["created_at"], int) and made["created_at"] > 1_700_000_000
    assert made["tone"] == "concise" and made["style"] == "terse" and "noise" not in made
    assert made["role"] == "staff", "every new bot joins the staff"
    assert store.create({"name": "Warm one", "tone": "warm"})["tone"] == "warm"
    # the id is minted here; a client-supplied one is ignored
    assert store.create({"id": "default", "name": "Copycat"})["id"] != "default"
    # and so is a client-supplied role: server-owned, never obeyed
    assert store.create({"name": "Upstart", "role": "chief"})["role"] == "staff"

    with pytest.raises(ValueError):  # a bot needs a name
        store.create({"tone": "warm"})
    with pytest.raises(ValueError):  # a tone must be a key of TONES
        store.create({"name": "Loud", "tone": "loud"})
    with pytest.raises(KeyError):
        store.update("b_nope", {"name": "x"})
    with pytest.raises(ValueError):
        store.update(made["id"], {"name": "   "})

    updated = store.update(made["id"], {"tagline": "Sees first", "avatar": "Dragon-2!", "gone": 0})
    assert updated["name"] == "Scout" and updated["style"] == "terse"  # untouched fields stay
    assert updated["tagline"] == "Sees first" and updated["avatar"] == "dragon-2"
    assert store.get(made["id"]) == updated
    assert store.update(made["id"], {"role": "chief"})["role"] == "staff", "a sent role is ignored"

    with pytest.raises(ValueError):  # the default bot stays
        store.delete("default")
    store.delete(made["id"])
    assert store.get(made["id"]) is None
    with pytest.raises(KeyError):
        store.delete("b_nope")

    # every change is on disk: a fresh store reads the same bots back
    again = BotStore(tmp_path / "bots.json")
    assert [b["name"] for b in again.list()][0] == "Ember"
    assert {b["name"] for b in again.list()} >= {"Warm one", "Copycat"}
    assert again.get(made["id"]) is None


def test_bot_ids_are_unique_and_stable(tmp_path):
    store = BotStore(tmp_path / "bots.json")
    ids = {store.create({"name": f"Bot {i}"})["id"] for i in range(5)}
    assert len(ids) == 5 and DEFAULT_BOT_ID not in ids
    assert all(re.fullmatch(r"b_[0-9a-f]{8}", i) for i in ids)


def test_bots_without_a_role_migrate_and_the_file_is_rewritten(tmp_path):
    """A bots.json from before roles existed: the default bot becomes the chief of staff,
    every other bot staff, and the file is rewritten in the new shape. A file that claims
    a role the id contradicts loses the claim the same way — only "chief" and "staff"
    can exist, and the id decides which."""
    path = tmp_path / "bots.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bots": [
                    {"id": "default", "name": "Wren", "created_at": 1700000000},
                    {
                        "id": "b_1a2b3c4d",
                        "name": "Scout",
                        "tone": "concise",
                        "created_at": 1700000001,
                    },
                ],
            }
        ),
        "utf-8",
    )
    store = BotStore(path)
    assert [b["role"] for b in store.list()] == ["chief", "staff"]
    saved = json.loads(path.read_text("utf-8"))
    assert [b["role"] for b in saved["bots"]] == ["chief", "staff"], "rewritten in the new shape"

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bots": [
                    {"id": "default", "name": "Wren", "role": "staff", "created_at": 1700000000},
                    {
                        "id": "b_1a2b3c4d",
                        "name": "Scout",
                        "role": "chief",
                        "created_at": 1700000001,
                    },
                ],
            }
        ),
        "utf-8",
    )
    store = BotStore(path)
    assert [b["role"] for b in store.list()] == ["chief", "staff"]
    saved = json.loads(path.read_text("utf-8"))
    assert [b["role"] for b in saved["bots"]] == ["chief", "staff"]


# ----------------------------------------------------------------------------- migration
def test_the_default_bot_migrates_from_profile_json(settings: Settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "profile.json").write_text(
        json.dumps(
            {
                "name": "Wren",
                "avatar": "dragon",
                "emoji": "🦉",
                "color": "#123456",
                "tagline": "Your day, sorted.",
                "tone": "playful",
                "communication": "bullets",
                "style": "uses metric units",
                "user_name": "Lin",
                "proactivity": "high",
                "quiet_hours": "22:00-08:00",
            }
        ),
        "utf-8",
    )
    service = DragonService(settings, llm=MockLLM([]))
    bots = service.list_bots()
    assert len(bots) == 1
    bot = bots[0]
    assert bot["id"] == "default" and bot["name"] == "Wren"
    assert bot["role"] == "chief"
    assert bot["avatar"] == "dragon" and bot["emoji"] == "🦉" and bot["color"] == "#123456"
    assert bot["tagline"] == "Your day, sorted."
    assert bot["tone"] == "playful" and bot["communication"] == "bullets"
    assert bot["style"] == "uses metric units"
    assert bot["instructions"] == "" and bot["model"] == ""
    # user settings are not bot fields
    assert not {"user_name", "proactivity", "quiet_hours"} & set(bot)
    assert service.profile.user_name == "Lin" and service.profile.quiet_hours == "22:00-08:00"
    # the migration happens once: a restart keeps the bot as it is now
    service.update_bot("default", {"name": "Renamed"})
    again = DragonService(settings, llm=MockLLM([]))
    assert again.list_bots()[0]["name"] == "Renamed"


def test_profile_and_the_default_bot_keep_each_other_current(settings: Settings):
    service = DragonService(settings, llm=MockLLM([]))
    # identity fields on the profile move to the default bot
    service.update_profile({"name": "Veda", "style": "warm and concise", "tone": "formal"})
    bot = service.list_bots()[0]
    assert bot["name"] == "Veda" and bot["style"] == "warm and concise" and bot["tone"] == "formal"
    # and a rename of the default bot lands on the profile, which older surfaces read
    service.update_bot("default", {"name": "Scout", "tone": "warm"})
    assert service.profile.name == "Scout" and service.profile.tone == "warm"
    saved = json.loads((settings.data_dir / "profile.json").read_text("utf-8"))
    assert saved["name"] == "Scout" and saved["tone"] == "warm"
    # user settings stay on the profile alone
    service.update_profile({"user_name": "Lin"})
    assert "user_name" not in service.list_bots()[0]


# ----------------------------------------------------------------------------- the prompt
async def test_each_bot_gets_its_own_persona_and_nothing_else(settings: Settings):
    scout = {
        "id": "b_aaaaaaaa",
        "name": "Scout",
        "tone": "concise",
        "style": "terse and dry",
        "instructions": "Always check the weather first.",
        "tagline": "Sees first",
    }
    sage = {
        "id": "b_bbbbbbbb",
        "name": "Sage",
        "tone": "formal",
        "communication": "bullets",
        "style": "patient teacher",
        "instructions": "Always cite sources.",
    }
    agent_a, llm_a, memory = make_agent(settings, [LLMResponse(content="hi")], bot=scout)
    await agent_a.run("hi")
    system_a = llm_a.calls[0]["messages"][0].content
    assert "You are Scout" in system_a
    assert TONES["concise"] in system_a and "terse and dry" in system_a
    assert "Always check the weather first." in system_a and "Sees first" in system_a
    # not one word of the other bot's persona
    assert "Sage" not in system_a
    assert TONES["formal"] not in system_a and "patient teacher" not in system_a
    assert "Always cite sources." not in system_a and "prefer bullet points" not in system_a

    agent_b, llm_b, _ = make_agent(settings, [LLMResponse(content="hi")], bot=sage, memory=memory)
    await agent_b.run("hi")
    system_b = llm_b.calls[0]["messages"][0].content
    assert "You are Sage" in system_b
    assert TONES["formal"] in system_b and "patient teacher" in system_b
    assert "Always cite sources." in system_b and "prefer bullet points" in system_b
    assert "Scout" not in system_b and "terse and dry" not in system_b
    assert TONES["concise"] not in system_b and "Sees first" not in system_b


async def test_the_default_bot_keeps_the_old_identity_and_the_addendum(settings: Settings):
    settings.agent.instructions = "Base standing instructions."
    agent, llm, _ = make_agent(settings, [LLMResponse(content="hi")])
    await agent.run("hi")
    system = llm.calls[0]["messages"][0].content
    assert system.startswith("You are Ember")
    assert "Base standing instructions." in system
    # the thread-level hook still rides along with the bot's persona
    agent.prompt_addendum = lambda: "First conversation: choosing a name."
    system = agent.build_system_prompt("hi")
    assert "First conversation: choosing a name." in system and "You are Ember" in system
    agent.bot = {"id": "b_aaaaaaaa", "name": "Scout", "instructions": "Check the weather."}
    system = agent.build_system_prompt("hi")
    assert "You are Scout" in system and "Check the weather." in system
    assert "First conversation: choosing a name." in system
    assert "Base standing instructions." in system


# ----------------------------------------------------------------------------- threads
def test_threads_bind_to_a_bot_and_say_so(settings: Settings):
    service = DragonService(settings, llm=MockLLM([]))
    made = service.create_bot({"name": "Scout", "tone": "concise", "style": "terse"})
    thread = service.create_thread("trip", bot_id=made["id"])
    assert thread.bot_id == made["id"]
    meta = thread.meta()
    assert meta["bot_id"] == made["id"] and meta["title"] == "trip"
    assert service.bot_of_thread(thread.id)["name"] == "Scout"
    # the agent speaks as the thread's bot
    prompt = thread.agent.build_system_prompt("hi")
    assert "You are Scout" in prompt and "terse" in prompt

    state = service.state()
    assert [b["id"] for b in state["bots"]] == [DEFAULT_BOT_ID, made["id"]]
    assert any(t["id"] == thread.id and t["bot_id"] == made["id"] for t in state["threads"])
    assert all(t["bot_id"] == DEFAULT_BOT_ID for t in state["threads"] if t["id"] == "main")

    # a chat that names no bot gets the default one; an unknown one is refused
    assert service.create_thread("plain").bot_id == DEFAULT_BOT_ID
    assert service.threads["main"].bot_id == DEFAULT_BOT_ID
    assert service.bot_of_thread("nope")["id"] == DEFAULT_BOT_ID
    with pytest.raises(KeyError):
        service.create_thread("nope", bot_id="b_nope")

    # the binding is in the threads index, so it survives a restart
    index = json.loads((settings.data_dir / "threads" / "index.json").read_text("utf-8"))
    row = next(m for m in index if m["id"] == thread.id)
    assert row["bot_id"] == made["id"]
    again = DragonService(settings, llm=MockLLM([]))
    assert again.threads[thread.id].bot_id == made["id"]
    assert again.bot_of_thread(thread.id)["name"] == "Scout"


def test_a_staff_bot_gets_one_thread_and_the_chief_gets_many(settings: Settings):
    """The one-chat rule: a staff bot's chat is its only thread — asking again returns it,
    unchanged — while the chief of staff (the default bot) gets a new chat every time."""
    service = DragonService(settings, llm=MockLLM([]))
    scout = service.create_bot({"name": "Scout"})
    assert scout["role"] == "staff"
    first = service.create_thread("Scout chat", bot_id=scout["id"])
    again = service.create_thread("Another", bot_id=scout["id"])
    assert again.id == first.id
    assert again.title == first.title, "the one chat comes back unchanged"
    assert [t.id for t in service.visible_threads() if t.bot_id == scout["id"]] == [first.id]

    one = service.create_thread("one")
    two = service.create_thread("two", bot_id=DEFAULT_BOT_ID)
    assert one.id != two.id and one.bot_id == two.bot_id == DEFAULT_BOT_ID

    # the rule survives a restart: the loaded chat is still the bot's one chat
    reloaded = DragonService(settings, llm=MockLLM([]))
    assert reloaded.create_thread("more", bot_id=scout["id"]).id == first.id

    # deleting the chat frees the slot: asking again makes a new one
    service.delete_thread(first.id)
    fresh = service.create_thread("back", bot_id=scout["id"])
    assert fresh.id != first.id


def test_delete_bot_reassigns_its_threads(settings: Settings):
    service = DragonService(settings, llm=MockLLM([]))
    made = service.create_bot({"name": "Scout", "tone": "concise"})
    thread = service.create_thread("trip", bot_id=made["id"])
    default_name = service.list_bots()[0]["name"]

    with pytest.raises(ValueError):  # the default bot always stays
        service.delete_bot(DEFAULT_BOT_ID)
    with pytest.raises(KeyError):
        service.delete_bot("b_nope")

    service.delete_bot(made["id"])
    assert [b["id"] for b in service.list_bots()] == [DEFAULT_BOT_ID]
    assert service.threads[thread.id].bot_id == DEFAULT_BOT_ID
    assert service.threads[thread.id].agent.bot["name"] == default_name
    assert service.bot_of_thread(thread.id)["id"] == DEFAULT_BOT_ID
    index = json.loads((settings.data_dir / "threads" / "index.json").read_text("utf-8"))
    assert next(m for m in index if m["id"] == thread.id)["bot_id"] == DEFAULT_BOT_ID


# ----------------------------------------------------------------------------- memory
async def test_memories_stay_with_the_bot_that_wrote_them(settings: Settings):
    memory = MemoryStore(settings.memory_db)
    scout = {"id": "b_aaaaaaaa", "name": "Scout"}
    sage = {"id": "b_bbbbbbbb", "name": "Sage"}
    # bot A remembers something: the line is tagged with A's id
    agent_a, llm_a, _ = make_agent(
        settings,
        [
            LLMResponse(
                tool_calls=[tc("remember", content="Scout's user keeps bees", category="fact")]
            ),
            LLMResponse(content="noted"),
        ],
        bot=scout,
        memory=memory,
    )
    await agent_a.run("remember this")
    rows = memory.all()
    assert [m.owner for m in rows] == ["b_aaaaaaaa"] and "keeps bees" in rows[0].content

    # what the runtime writes outside a run is shared with every bot
    shared_row = memory.add("Lives in Shanghai", "profile")
    assert shared_row.owner == "shared"

    # bot A sees its own line and the shared one; bot B sees only the shared one
    prompt_a = agent_a.build_system_prompt("what do you know?")
    assert "keeps bees" in prompt_a and "Lives in Shanghai" in prompt_a
    agent_b, llm_b, _ = make_agent(settings, [LLMResponse(content="done")], bot=sage, memory=memory)
    prompt_b = agent_b.build_system_prompt("what do you know?")
    assert "keeps bees" not in prompt_b and "Lives in Shanghai" in prompt_b

    # and the recall tool answers within the same scope
    ask_a, llm_ask_a, _ = make_agent(
        settings,
        [LLMResponse(tool_calls=[tc("recall", query="bees")]), LLMResponse(content="ok")],
        bot=scout,
        memory=memory,
    )
    await ask_a.run("bees?")
    answered = [m.content for m in llm_ask_a.calls[1]["messages"] if m.role == Role.TOOL]
    assert answered and "keeps bees" in answered[0]
    ask_b, llm_ask_b, _ = make_agent(
        settings,
        [LLMResponse(tool_calls=[tc("recall", query="bees")]), LLMResponse(content="ok")],
        bot=sage,
        memory=memory,
    )
    await ask_b.run("bees?")
    answered = [m.content for m in llm_ask_b.calls[1]["messages"] if m.role == Role.TOOL]
    assert answered and "keeps bees" not in answered[0] and "No matching memories" in answered[0]

    # one bot cannot rewrite another bot's line
    out = await Remember(store=memory).execute(content="changed", replaces=rows[0].id)
    assert out.error and memory.get(rows[0].id) is not None


async def test_remember_outside_a_run_tags_the_default_bot(settings: Settings):
    memory = MemoryStore(settings.memory_db)
    out = await Remember(store=memory).execute(content="Lives in Shanghai", category="profile")
    assert out.output.startswith("Remembered")
    assert memory.all()[0].owner == DEFAULT_BOT_ID
    # an exact repeat is the existing line, not a second one
    again = await Remember(store=memory).execute(content="Lives in Shanghai", category="profile")
    assert again.output.startswith("Remembered") and len(memory.all()) == 1


def test_legacy_memory_rows_become_shared(tmp_path):
    """Rows from before bots existed had no owner; they belong to everyone."""
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT NOT NULL,"
        " category TEXT NOT NULL DEFAULT 'general', created_at TEXT NOT NULL,"
        " source TEXT NOT NULL DEFAULT 'agent')"
    )
    conn.execute(
        "INSERT INTO memories (id, content, category, created_at, source)"
        " VALUES ('m_old', 'Lives in Shanghai', 'profile', '2026-01-01T00:00:00+00:00', 'agent')"
    )
    conn.commit()
    conn.close()
    store = MemoryStore(db)
    item = store.get("m_old")
    assert item is not None and item.owner == "shared"
    assert [m.id for m in store.all(owner="b_aaaaaaaa")] == ["m_old"]
    assert store.search("Shanghai", owner="b_bbbbbbbb")[0].id == "m_old"
    store.close()
