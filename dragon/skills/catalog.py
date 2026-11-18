"""A read-only view of the public AgenticSkills catalog.

The directory has no public data API, so this reads the two public pages it does serve:
the index (JSON-LD plus the complete-index list) and a skill's detail page (which carries
the upstream ``skillMdUrl``). Only the link is used here; installing still goes through
:func:`dragon.skills.fetch_skill_text`, with its private-host guard and size cap.

Nothing here writes to the agent's skills. That is the service's job.
"""

from __future__ import annotations

import asyncio
import html
import json
import re
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from dragon.logger import logger

CATALOG_URL = "https://agenticskills.io/skills"
DETAIL_URL = "https://agenticskills.io/skills/{slug}"
CACHE_SECONDS = 3600
MAX_CATALOG = 500
_CONCURRENCY = 3

_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_LINK = re.compile(
    r'<a\s+href="(https://agenticskills\.io/skills/([^"/?#]+))"[^>]*>(.*?)</a>'
    r"(?:\s*[^<]{0,4}(?:\u2014|-)\s*([^<]*))?",
    re.S,
)
_FIELD = re.compile(r'"(skillMdUrl|githubUrl|license|price|category)"\s*:\s*"([^"]*)"')


class _IndexText(HTMLParser):
    """Collect link text and the description that follows it in the complete index."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, str, str]] = []
        self._href = ""
        self._text: list[str] = []
        self._in_link = False
        self._active = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "nav" and any(
            k == "aria-label" and v == "Complete skill index" for k, v in attrs
        ):
            self._active = True
        elif self._active and tag == "a":
            self._in_link = True
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self._active = False
        elif self._in_link and tag == "a":
            self.rows.append((self._href, "".join(self._text).strip(), ""))
            self._in_link = False

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._text.append(html.unescape(data))


def parse_index(page: str) -> list[dict[str, str]]:
    """The catalog entries: ``slug``, ``name``, ``description``, ``url``.

    The JSON-LD block is the canonical list (it has every item and its order); the
    screen-reader index supplies the one-line descriptions. Either can be missing on a
    redesign, so a skill with no description still gets through.
    """
    items: list[dict[str, str]] = []
    match = _LD.search(page)
    if match:
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            data = None
        for block in data if isinstance(data, list) else [data]:
            if not isinstance(block, dict):
                continue
            main = block.get("mainEntity")
            entities = main.get("itemListElement") if isinstance(main, dict) else []
            for entity in entities:
                url = str(entity.get("url") or "")
                slug = urlparse(url).path.rstrip("/").split("/")[-1]
                if slug and slug not in {"skills"}:
                    items.append(
                        {
                            "slug": slug,
                            "name": str(entity.get("name") or slug),
                            "description": "",
                            "url": url,
                        }
                    )

    if not items:
        # the visible list is a usable fallback when the JSON-LD is gone
        for href, name, _ in _IndexText_rows(page):
            slug = href.rstrip("/").split("/")[-1]
            if slug:
                items.append({"slug": slug, "name": name or slug, "description": "", "url": href})

    descriptions: dict[str, str] = {}
    for href, _, desc in _IndexText_rows(page):
        slug = href.rstrip("/").split("/")[-1]
        if slug and desc:
            descriptions[slug] = desc.strip()
    # the regex fallback also reads the "Name — description" tail on each link
    for _, slug, _, desc in _LINK.findall(page):
        if desc and desc.strip():
            descriptions[slug] = html.unescape(desc).strip()
    for item in items:
        item["description"] = descriptions.get(item["slug"], "")

    seen: set[str] = set()
    unique = [item for item in items if not (item["slug"] in seen or seen.add(item["slug"]))]
    return unique[:MAX_CATALOG]


def _IndexText_rows(page: str) -> list[tuple[str, str, str]]:
    parser = _IndexText()
    try:
        parser.feed(page)
    except Exception:  # a broken page must not break the tab
        logger.warning("could not parse the skill index")
    return parser.rows


def parse_detail(page: str) -> dict[str, str]:
    """The upstream raw SKILL.md link and licence from one skill's detail page."""
    # detail pages also embed "related skills"; the skill's own fields come first
    fields: dict[str, str] = {}
    for key, value in _FIELD.findall(page.replace('\\"', '"')):
        fields.setdefault(key, value.strip())
    raw = fields.get("skillMdUrl", "")
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raw = ""
    return {
        "raw_url": raw,
        "github_url": fields.get("githubUrl", ""),
        "license": fields.get("license", ""),
        "price": fields.get("price", ""),
        "category": fields.get("category", ""),
    }


_cache: dict[str, Any] = {"at": 0.0, "items": []}


async def fetch_catalog(*, refresh: bool = False, transport: Any = None) -> list[dict[str, str]]:
    """Fetch and cache the public index. A failed refresh falls back to the last good copy."""
    if not refresh and _cache["items"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return list(_cache["items"])
    from dragon.tools.web import fetch_public

    try:
        resp = await fetch_public(
            CATALOG_URL, timeout=20, headers={"User-Agent": "Dragon"}, transport=transport
        )
        if resp.status_code >= 400:
            raise ValueError(f"HTTP {resp.status_code} from the skill directory")
        items = parse_index(resp.text)
        if not items:
            raise ValueError("the skill directory returned no skills")
    except (ValueError, OSError, PermissionError) as exc:
        if _cache["items"]:
            logger.warning("skill directory refresh failed ({}); using the cached list", exc)
            return list(_cache["items"])
        raise
    except Exception as exc:  # noqa: BLE001 — httpx errors are reported to the user
        if _cache["items"]:
            logger.warning("skill directory refresh failed ({}); using the cached list", exc)
            return list(_cache["items"])
        raise ValueError(f"could not reach the skill directory: {type(exc).__name__}") from exc
    _cache.update(at=time.time(), items=items)
    return list(items)


async def fetch_detail(slug: str, *, transport: Any = None) -> dict[str, str]:
    """One detail page's upstream link. ``ValueError`` when it has no usable raw URL."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}", slug):
        raise ValueError("not a skill in the directory")
    from dragon.tools.web import fetch_public

    resp = await fetch_public(
        DETAIL_URL.format(slug=slug),
        timeout=20,
        headers={"User-Agent": "Dragon"},
        transport=transport,
    )
    if resp.status_code >= 400:
        raise ValueError(f"HTTP {resp.status_code} for {slug}")
    detail = parse_detail(resp.text)
    if not detail["raw_url"]:
        raise ValueError(f"{slug} has no raw SKILL.md link")
    return detail


async def gather(items: list[dict[str, str]], work: Any) -> list[dict[str, Any]]:
    """Run ``work(item)`` with a small, fixed concurrency; return each result or error."""
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
    for item in items:
        queue.put_nowait(item)
    results: list[dict[str, Any]] = []

    async def runner() -> None:
        while True:
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                results.append(await work(item))
            except (ValueError, OSError, PermissionError) as exc:
                results.append({"slug": item["slug"], "error": str(exc)})
            except Exception as exc:  # noqa: BLE001 — one bad skill must not stop the rest
                results.append({"slug": item["slug"], "error": type(exc).__name__})
            finally:
                queue.task_done()

    await asyncio.gather(*(runner() for _ in range(min(_CONCURRENCY, max(1, len(items))))))
    return results


__all__ = ["CATALOG_URL", "fetch_catalog", "fetch_detail", "gather", "parse_detail", "parse_index"]
