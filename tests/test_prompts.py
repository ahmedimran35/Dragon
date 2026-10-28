"""The tool-routing guidance: all web work is done in the browser, the light tools are the
fallback for when it cannot do the step."""

from dragon.prompts import SYSTEM_PROMPT
from dragon.tools.browser import Browser
from dragon.tools.web import BROWSER_NUDGE, WebFetch, WebSearch


def test_the_system_prompt_does_all_web_work_in_the_browser():
    assert "All web work happens in the `browser` tool" in SYSTEM_PROMPT
    assert "is read in the browser like anything else" in SYSTEM_PROMPT


def test_the_system_prompt_takes_the_bots_persona():
    from dragon.prompts import COMMUNICATION, SYSTEM_PROMPT, TONES, bot_voice, paragraph

    # the system prompt is parameterised by the bot's persona, one slot per part
    for slot in ("{tagline}", "{tone}", "{communication}", "{style}", "{instructions}"):
        assert slot in SYSTEM_PROMPT
    assert TONES.keys() >= {"warm", "formal", "casual", "playful", "concise"}
    assert COMMUNICATION.keys() >= {"short", "detailed", "bullets"}

    voice = bot_voice({"tone": "warm", "style": "dry", "instructions": "Cite sources."})
    assert voice["tone"] == TONES["warm"] and "dry" in voice["style"]
    assert voice["instructions"] == "Cite sources." and voice["tagline"] == ""
    # an unset persona adds nothing at all: the prompt reads as it always did
    assert all(v == "" for v in bot_voice({}).values())
    assert all(v == "" for v in bot_voice(None).values())
    assert paragraph("") == "" and paragraph("  x  ") == "\n\nx"


def test_the_light_web_tools_are_the_fallback_only():
    for tool in (WebSearch(), WebFetch()):
        assert "fallback" in tool.description
        assert "`browser` tool" in tool.description
    assert Browser().description.startswith("The tool for all web work")


def test_reads_end_with_the_nudge_to_the_browser():
    assert "browser" in BROWSER_NUDGE and "watches it live" in BROWSER_NUDGE


def test_the_light_web_tools_are_not_offered_beside_the_browser():
    from dragon.agent.core import call_refused, model_facing
    from dragon.tools.base import ToolCollection
    from dragon.tools.browser import Browser

    with_browser = ToolCollection(WebSearch(), WebFetch(), Browser())
    assert [t.name for t in model_facing(with_browser)] == ["browser"]
    without = ToolCollection(WebSearch(), WebFetch())
    assert [t.name for t in model_facing(without)] == ["web_search", "web_fetch"]
    # a name recalled from earlier in the conversation is turned back, not run
    assert call_refused("web_fetch", with_browser) is not None
    assert call_refused("web_search", with_browser) is not None
    assert call_refused("web_fetch", without) is None
    assert call_refused("browser", with_browser) is None
