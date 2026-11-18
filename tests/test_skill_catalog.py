"""The public AgenticSkills catalog: parsing the two public pages and importing through
the vetted SKILL.md importer. No network: the catalog pages are synthetic and the service
helpers are patched, as everywhere else in the suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dragon.config import Settings, load_app_settings
from dragon.llm import MockLLM
from dragon.server import create_app
from dragon.server.service import DragonService
from dragon.skills.catalog import parse_detail, parse_index

INDEX = """<html><body>
<script type="application/ld+json">[{"@context":"https://schema.org","@type":"CollectionPage",
"mainEntity":{"@type":"ItemList","numberOfItems":2,"itemListElement":[
{"@type":"ListItem","position":1,"url":"https://agenticskills.io/skills/first-one","name":"First One"},
{"@type":"ListItem","position":2,"url":"https://agenticskills.io/skills/second-one","name":"Second One"}]}}]</script>
<nav aria-label="Complete skill index"><ul>
<li><a href="https://agenticskills.io/skills/first-one">First One</a> — Does the first job.</li>
<li><a href="https://agenticskills.io/skills/second-one">Second One</a> &mdash; Does the second job.</li>
</ul></nav></body></html>"""

DETAIL = r"""<html><body>{\"name\":\"First One\",\"skillMdUrl\":\"
https://raw.githubusercontent.com/someone/things/main/first/SKILL.md\",
\"githubUrl\":\"https://github.com/someone/things\",\"license\":\"MIT\",
\"related\":{\"skillMdUrl\":\"https://raw.githubusercontent.com/other/other/main/SKILL.md\"}}</body></html>"""

SKILL = """---
name: first-one
description: Does the first job, use when asked to do it.
---

# First one

1. Do the job.
"""


def test_parse_index_and_detail():
    items = parse_index(INDEX)
    assert [i["slug"] for i in items] == ["first-one", "second-one"]
    assert items[0]["description"] == "Does the first job."
    assert items[0]["name"] == "First One"
    detail = parse_detail(DETAIL)
    assert (
        detail["raw_url"] == "https://raw.githubusercontent.com/someone/things/main/first/SKILL.md"
    )
    assert detail["github_url"] == "https://github.com/someone/things"
    assert detail["license"] == "MIT"
    # only raw.githubusercontent.com links are usable
    assert parse_detail('{"skillMdUrl":"https://evil.test/SKILL.md"}')["raw_url"] == ""
    assert parse_index("<html></html>") == []


def test_catalog_routes_import_and_auto_sync(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import dragon.skills as skills_pkg
    import dragon.skills.catalog as catalog

    items = parse_index(INDEX)

    async def fake_catalog(*, refresh: bool = False, transport=None):
        return list(items)

    async def fake_detail(slug: str, *, transport=None):
        return parse_detail(DETAIL)

    async def fake_text(url: str) -> str:
        assert url.endswith("/first/SKILL.md")
        return SKILL

    monkeypatch.setattr(catalog, "fetch_catalog", fake_catalog)
    monkeypatch.setattr(catalog, "fetch_detail", fake_detail)
    monkeypatch.setattr(skills_pkg, "fetch_skill_text", fake_text)

    settings.server.token = "secret-token"
    service = DragonService(settings, llm=MockLLM([]))
    app = create_app(settings, service)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer secret-token"
        # /api/skills/{name} must not swallow /api/skills/catalog
        view = client.get("/api/skills/catalog").json()
        assert view["total"] == 2 and view["source"] == catalog.CATALOG_URL
        assert [i["slug"] for i in view["items"]] == ["first-one", "second-one"]
        assert all(not i["installed"] for i in view["items"])
        assert client.get("/api/skills/catalog/status").status_code == 200

        r = client.post("/api/skills/catalog/import", json={"slug": "nope"})
        assert r.status_code == 400
        r = client.post("/api/skills/catalog/import", json={"slug": "first-one"})
        assert r.status_code == 200, r.text
        assert r.json()["skill"]["name"] == "first-one"
        assert (settings.skills_dir / "first-one" / "SKILL.md").exists()
        # imported skills are added but not switched on: the model never sees them yet
        assert client.get("/api/skills/first-one").json()["enabled"] is False
        assert load_app_settings(settings.data_dir)["skills"]["disabled"] == ["first-one"]
        state = load_app_settings(settings.data_dir)["skill_catalog"]
        assert state["installed"] == {"first-one": "first-one"}
        assert state["seen"] == ["first-one"]
        view = client.get("/api/skills/catalog").json()
        assert view["items"][0]["installed"] is True

        # auto sync is a persisted setting; enabling it starts the poller
        assert (
            client.put("/api/skills/catalog/auto", json={"enabled": True}).json()["auto_sync"]
            is True
        )
        assert load_app_settings(settings.data_dir)["skill_catalog"]["auto_sync"] is True
        assert (
            client.put("/api/skills/catalog/auto", json={"enabled": False}).json()["auto_sync"]
            is False
        )
