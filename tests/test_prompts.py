"""The tool-routing guidance: the model picks the web tool by the job — the visible browser
for interactive work, the fast headless tools for plain reads — and shell is ruled out for
fetching pages."""

from dragon.prompts import SYSTEM_PROMPT
from dragon.tools.browser import Browser
from dragon.tools.web import BROWSER_NUDGE, WebFetch, WebSearch


def test_the_system_prompt_lets_the_model_choose_the_web_tool():
    assert "Choose the web tool by the job" in SYSTEM_PROMPT
    # the browser is the default for anything the user would read or watch
    assert "`browser` is the default" in SYSTEM_PROMPT
    # `web_fetch` is for raw endpoints, not human-facing pages
    assert "web_fetch` is only for raw machine endpoints" in SYSTEM_PROMPT
    # the one thing ruled out: fetching web pages through shell
    assert "Do not fetch web pages with `shell`" in SYSTEM_PROMPT


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


def test_each_web_tool_says_what_it_is_for():
    # the browser is the default for anything a person would read or watch
    assert "default for anything the user would" in Browser().description
    # web_search finds what is out there, but points live look-ups to the browser
    assert "open the `browser` instead" in WebSearch().description
    # web_fetch is for raw machine endpoints; it never claims a page a person would read
    assert "raw machine endpoint" in WebFetch().description
    assert "signing in" in WebFetch().description


def test_reads_point_to_the_browser_for_interactive_pages():
    assert "browser" in BROWSER_NUDGE and "headless text read" in BROWSER_NUDGE


def test_the_light_web_tools_are_offered_beside_the_browser():
    from dragon.agent.core import call_refused, model_facing
    from dragon.tools.base import ToolCollection
    from dragon.tools.browser import Browser

    # the browser leads the web tools: it is the default for anything on the web
    with_browser = ToolCollection(Browser(), WebSearch(), WebFetch())
    assert [t.name for t in model_facing(with_browser)] == ["browser", "web_search", "web_fetch"]
    without = ToolCollection(WebSearch(), WebFetch())
    assert [t.name for t in model_facing(without)] == ["web_search", "web_fetch"]
    # nothing is refused: the model may call any offered tool
    assert call_refused("web_fetch", with_browser) is None
    assert call_refused("web_search", with_browser) is None
    assert call_refused("web_fetch", without) is None
    assert call_refused("browser", with_browser) is None
