"""The reflector: the pass that turns what happened into durable lessons.

After a run, the trajectory (what the user asked, which tools ran and how it went, what
they corrected) goes to the model with the lessons already kept, and comes back with at
most a few new ones: a preference the user showed, a fact about a site or a service,
something that failed and why. They land in memory like anything else, so a later turn
recalls the one that matters at the right moment, and the Memory page shows what was
learned so the person can correct it. The pass is throttled and can be turned off
(``[agent] reflect``).
"""

from __future__ import annotations

import json
import re
from typing import Any

REFLECT_PROMPT = """You are {name}, the user's personal agent, reviewing what happened lately to learn durable lessons.

Write a lesson only when it will matter again: a preference the user showed, a fact about a site or a service, something that failed and why, a constraint worth carrying into later work. Do not write task summaries, do not write what one message makes obvious, and do not repeat a lesson you already keep.

Answer with a JSON array only, no prose. Each item: {{"content": "<one specific sentence>", "applies": "<the situation where this matters>", "about": "<two to five keywords this should surface under>"}}. At most {n}. Write in the user's language ({language}).

What happened:
{trajectory}

Lessons you already keep:
{known}"""

LESSONS_PER_PASS = 3


def json_objects(text: str) -> list[Any]:
    """The JSON objects in a model reply that should have been a JSON array.

    Usually it is one: ``[{...}, {...}]``, possibly inside a code fence. When the
    array does not parse (a real newline inside a string, a trailing comma, the
    reply cut off at max_tokens before the closing bracket), each ``{...}`` that
    parses on its own is kept, so one bad item does not cost the whole list.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1], strict=False)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    decoder = json.JSONDecoder(strict=False)
    found: list[Any] = []
    pos = text.find("{")
    while pos >= 0:
        try:
            obj, stop = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            pos = text.find("{", pos + 1)
            continue
        found.append(obj)
        pos = text.find("{", stop)
    return found


def parse_lessons(text: str) -> list[dict[str, str]]:
    """The lessons in a model reply: ``content`` kept as written, ``applies`` and
    ``about`` trimmed beside it. A lesson without words is not a lesson."""
    lessons: list[dict[str, str]] = []
    for item in json_objects(text):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        lessons.append(
            {
                "content": content[:300],
                "applies": str(item.get("applies", "")).strip()[:120],
                "about": str(item.get("about", "")).strip()[:120],
            }
        )
    return lessons[:LESSONS_PER_PASS]


def lesson_line(lesson: dict[str, str]) -> str:
    """The lesson as one memory line: the sentence, and when it applies."""
    content = lesson["content"]
    applies = lesson.get("applies", "")
    return f"{content} (when: {applies})" if applies else content
