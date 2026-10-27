"""The tool-routing guidance: website work goes to the browser, not the light web tools."""

from dragon.prompts import SYSTEM_PROMPT
from dragon.tools.browser import Browser
from dragon.tools.web import WebFetch, WebSearch


def test_the_system_prompt_sends_site_work_to_the_browser():
    assert "*on a website*" in SYSTEM_PROMPT
    assert "open the `browser` tool and finish the task on the page" in SYSTEM_PROMPT


def test_the_light_web_tools_point_at_the_browser():
    for tool in (WebSearch(), WebFetch()):
        assert "use the `browser` tool instead" in tool.description
    assert Browser().description.startswith("Prefer this over")
