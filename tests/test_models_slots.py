"""The four model slots chosen through the app layer.

``PUT /api/connections/gui`` takes a catalogue id as ``PUT /api/connections/llm`` does;
``PUT /api/connections/image`` and ``/video`` write the ``[image]`` / ``[video]`` slots; and
for a slot nobody chose the runtime follows the chat provider's own model when it can.
``MockLLM`` only; nothing on the network.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from dragon.config import Settings
from dragon.llm import MockLLM
from dragon.server import create_app
from dragon.server.service import DragonService

BAILIAN = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _make(settings: Settings) -> tuple[TestClient, DragonService]:
    settings.server.token = "secret-token"
    service = DragonService(settings, llm=MockLLM([]))
    app = create_app(settings, service)
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer secret-token"
    return client, service


def _settings_file(settings: Settings) -> dict[str, Any]:
    return json.loads((settings.data_dir / "app-settings.json").read_text("utf-8"))


# ----------------------------------------------------------------------------- the hands
def test_gui_accepts_a_catalogue_id_like_the_chat_slot(settings: Settings) -> None:
    client, service = _make(settings)
    with client:
        view = client.put(
            "/api/connections/gui",
            json={"provider": "bailian", "model": "qwen3.8-27b", "api_key": "sk-hands"},
        ).json()
        assert view["provider"] == "bailian" and view["provider_id"] == "bailian"
        assert view["model"] == "qwen3.8-27b" and view["key_source"] == "vault"
        assert view["effective_model"] == "qwen3.8-27b" and view["effective_source"] == "gui"
        # the id brings the catalogue's endpoint; the key is a vault reference
        assert settings.gui.endpoint == BAILIAN
        saved = _settings_file(settings)["gui"]
        assert saved["provider"] == "bailian" and saved["api_key"] == "{{vault:GUI_API_KEY}}"
        llm = getattr(service.app.make_gui_llm(), "inner", None) or service.app.make_gui_llm()
        assert llm.settings.base_url == BAILIAN and llm.settings.api_key == "sk-hands"
        hands = client.get("/api/providers").json()["configured"]["hands"]
        assert hands == {
            "provider": "bailian",
            "model": "qwen3.8-27b",
            "protocol": "openai",
            "source": "app",
        }
        # the raw forms still work, and a URL's host names the entry
        view = client.put(
            "/api/connections/gui",
            json={
                "provider": "openai",
                "base_url": "https://api.moonshot.cn/v1",
                "model": "kimi-k2.6",
            },
        ).json()
        assert view["provider"] == "openai" and view["provider_id"] == "moonshot"
        assert (
            client.put("/api/connections/gui", json={"provider": "openai_responses"}).status_code
            == 200
        )
        # ids the catalogue lacks, or whose protocol the runtime does not speak, are refused
        r = client.put("/api/connections/gui", json={"provider": "nope"})
        assert r.status_code == 400 and "unknown provider" in r.json()["detail"]
        r = client.put("/api/connections/gui", json={"provider": "anthropic"})
        assert r.status_code == 400 and "anthropic" in r.json()["detail"]
        assert "sk-hands" not in json.dumps(client.get("/api/connections").json())


def test_hands_follow_an_own_chat_provider_that_sees(settings: Settings) -> None:
    """Contract §3: with no ``[gui]`` model, the chat provider's own hands model when the
    chat provider is an own provider with vision — by id, and by the URL's host."""
    settings.llm.provider = "openai"
    settings.llm.base_url = BAILIAN
    settings.llm.model = "qwen3.7-plus"
    client, service = _make(settings)
    with client:
        assert service.app.hands_choice() == ("chat", "qwen3.8-27b")
        gui = client.get("/api/connections").json()["gui"]
        assert gui["effective_model"] == "qwen3.8-27b" and gui["effective_source"] == "chat"
        assert gui["default_model"] == "qwen3.8-27b"
        hands = client.get("/api/providers").json()["configured"]["hands"]
        assert hands["provider"] == "bailian" and hands["model"] == "qwen3.8-27b"
        llm = getattr(service.app.make_gui_llm(), "inner", None) or service.app.make_gui_llm()
        assert llm.settings.model == "qwen3.8-27b" and llm.settings.base_url == BAILIAN
        assert llm.settings.api_key == "test"  # the chat model's key, same host
        # an explicit choice always wins
        client.put("/api/connections/gui", json={"model": "qwen3.7-max"})
        assert service.app.hands_choice() == ("gui", "qwen3.7-max")
        assert service.app.gui_model(default_only=True) == "qwen3.8-27b"

    by_id = settings.model_copy(deep=True)
    by_id.gui.model = ""
    by_id.llm.provider = "bailian"
    by_id.llm.base_url = None
    by_id.llm.model = "qwen3.7-plus"
    by_id.data_dir = settings.data_dir / "by-id"
    by_id.ensure_dirs()
    service2 = DragonService(by_id, llm=MockLLM([]))
    assert service2.app.hands_choice() == ("chat", "qwen3.8-27b")


# ----------------------------------------------------------------------------- pictures, clips
def test_image_and_video_slots_round_trip(settings: Settings) -> None:
    settings.llm.base_url = "https://api.deepseek.com"  # draws nothing by itself
    client, service = _make(settings)
    with client:
        before = client.get("/api/connections").json()
        assert (
            before["image"]["configured"] is False and before["image"]["effective_provider"] == ""
        )
        assert client.get("/api/providers").json()["configured"]["image"] is None

        image = client.put(
            "/api/connections/image", json={"provider": "zhipu", "api_key": "sk-img"}
        ).json()
        assert image["provider"] == "zhipu" and image["provider_id"] == "zhipu"
        assert image["model"] == "" and image["key_source"] == "vault" and image["from_app"] is True
        # an empty model is the catalogue's default; the slot is the answer, from the app
        assert image["effective_provider"] == "zhipu" and image["effective_model"] == "glm-image"
        assert image["effective_source"] == "app"
        assert client.get("/api/connections/image").json() == image
        assert client.get("/api/connections").json()["image"] == image
        saved = _settings_file(settings)
        assert saved["image"] == {"provider": "zhipu", "api_key": "{{vault:IMAGE_API_KEY}}"}
        assert service.app.vault.get("IMAGE_API_KEY") == "sk-img"
        assert (
            settings.image.provider == "zhipu"
            and settings.image.api_key == "{{vault:IMAGE_API_KEY}}"
        )
        ep = service.avatar.endpoint()
        assert ep is not None and ep.base_url == "https://open.bigmodel.cn/api/paas/v4"
        assert ep.api_key == "sk-img" and ep.image_model == "glm-image" and not ep.clips

        video = client.put(
            "/api/connections/video",
            json={"provider": "bailian", "model": "wan2.2-i2v-flash", "api_key": "sk-vid"},
        ).json()
        assert video["provider"] == "bailian" and video["model"] == "wan2.2-i2v-flash"
        assert video["effective_provider"] == "bailian" and video["effective_source"] == "app"
        assert client.get("/api/connections/video").json() == video
        assert _settings_file(settings)["video"]["api_key"] == "{{vault:VIDEO_API_KEY}}"
        ep = service.avatar.endpoint()
        assert ep is not None and ep.clips and ep.video_host == "https://dashscope.aliyuncs.com"
        assert ep.video_key == "sk-vid" and ep.api_key == "sk-img"  # each host its own key

        view = client.get("/api/providers").json()
        assert view["configured"]["image"]["provider"] == "zhipu"
        assert view["configured"]["image"]["model"] == "glm-image"
        assert view["configured"]["image"]["source"] == "app"
        assert view["configured"]["video"]["provider"] == "bailian"
        assert view["configured"]["video"]["model"] == "wan2.2-i2v-flash"
        zhipu = next(p for p in view["providers"] if p["id"] == "zhipu")
        assert zhipu["configured"] == ["image"]
        assert next(p for p in view["providers"] if p["id"] == "bailian")["configured"] == ["video"]
        assert "image" in view["capabilities"] and "video" in view["capabilities"]
        assert view["unavailable"]["image"] == "" and view["unavailable"]["video"] == ""
        assert "sk-img" not in json.dumps(view) and "sk-vid" not in json.dumps(view)
        assert "sk-img" not in json.dumps(client.get("/api/connections").json())

        # a bare URL for a host the catalogue does not list, and a model there
        other = client.put(
            "/api/connections/image",
            json={
                "provider": "openai",
                "base_url": "https://images.example.com",
                "model": "flux-2",
            },
        ).json()
        assert other["base_url"] == "https://images.example.com/v1" and other["provider_id"] == ""
        assert other["effective_model"] == "flux-2"
        assert client.get("/api/providers").json()["configured"]["image"]["provider"] == "custom"

        # a reference to a key the vault already holds (the account's) is kept as written
        service.app.vault.set("MODEL_API_KEY", "test-key")
        ref = client.put(
            "/api/connections/image",
            json={"provider": "bailian", "api_key": "{{vault:MODEL_API_KEY}}"},
        ).json()
        assert ref["key_source"] == "vault"
        assert _settings_file(settings)["image"]["api_key"] == "{{vault:MODEL_API_KEY}}"
        assert service.app.vault.get("IMAGE_API_KEY") == "sk-img"  # untouched
        ep = service.avatar.endpoint()
        assert ep is not None and ep.api_key == "test-key"
        missing = client.put(
            "/api/connections/image", json={"api_key": "{{vault:NOBODY_HAS_THIS}}"}
        ).json()
        assert missing["key_source"] == "missing"
        service.app.vault.delete("MODEL_API_KEY")  # key removed

        # clearing: all four empty, and the slot is gone from the file and the vault
        cleared = client.put(
            "/api/connections/image",
            json={"provider": "", "model": "", "base_url": "", "api_key": ""},
        ).json()
        assert cleared["configured"] is False and cleared["from_app"] is False
        assert cleared["key_source"] == "none" and cleared["effective_provider"] == ""
        assert "image" not in _settings_file(settings)
        assert service.app.vault.get("IMAGE_API_KEY") is None
        assert settings.image.configured is False
        assert client.get("/api/providers").json()["configured"]["image"] is None
        # the clips slot stands on its own
        assert client.get("/api/connections/video").json()["provider"] == "bailian"


def test_image_and_video_slots_refuse_what_the_catalogue_rules_out(settings: Settings) -> None:
    client, service = _make(settings)
    with client:
        r = client.put("/api/connections/image", json={"provider": "deepseek"})
        assert r.status_code == 400 and "DeepSeek has no image models" in r.json()["detail"]
        assert "Pictures need a provider with image models" in r.json()["detail"]
        r = client.put("/api/connections/video", json={"provider": "zhipu"})
        assert r.status_code == 400 and "has no video models" in r.json()["detail"]
        r = client.put("/api/connections/image", json={"provider": "chatgpt"})
        assert r.status_code == 400 and "ChatGPT sign-in" in r.json()["detail"]
        r = client.put("/api/connections/image", json={"provider": "nope"})
        assert r.status_code == 400 and "unknown provider" in r.json()["detail"]
        r = client.put("/api/connections/image", json={"provider": "anthropic"})
        assert r.status_code == 400
        # a URL whose host the catalogue knows cannot draw
        r = client.put("/api/connections/image", json={"base_url": "https://api.deepseek.com/v1"})
        assert r.status_code == 400 and "DeepSeek" in r.json()["detail"]
        # nothing was written
        assert "image" not in _settings_file(settings) and settings.image.configured is False
        assert TestClient(client.app).put("/api/connections/image", json={}).status_code == 401
