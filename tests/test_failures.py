"""The sentence a failed run leaves in the chat (dragon/server/failures.py)."""

from __future__ import annotations

import httpx
import openai

from dragon.server.failures import describe_failure, failure_notice


def _status_error(cls, status: int, body: dict):
    request = httpx.Request("POST", "https://relay.test/v1/chat/completions")
    response = httpx.Response(status, request=request, json={"error": body})
    return cls(body.get("message", "no"), response=response, body=body)


def test_own_key_failures():
    exc = _status_error(openai.AuthenticationError, 401, {"message": "Incorrect API key provided"})
    code, text = describe_failure(exc)
    assert code == "key" and "Incorrect API key" not in text

    exc = _status_error(
        openai.BadRequestError,
        400,
        {"message": "This model's maximum context length is 32768 tokens"},
    )
    assert describe_failure(exc)[0] == "too_long"

    exc = _status_error(openai.BadRequestError, 400, {"message": "unknown parameter foo"})
    code, text = describe_failure(exc)
    assert code == "request" and "unknown parameter foo" in text

    assert (
        describe_failure(openai.APITimeoutError(httpx.Request("POST", "https://x")))[0] == "timeout"
    )
    assert (
        describe_failure(openai.APIConnectionError(request=httpx.Request("POST", "https://x")))[0]
        == "network"
    )
    assert (
        describe_failure(_status_error(openai.NotFoundError, 404, {"message": "model not found"}))[
            0
        ]
        == "model"
    )


def test_unknown_failures_keep_the_type_and_first_line():
    code, text = describe_failure(ValueError("first line\nsecond line"))
    assert code == "unknown" and text == "Something went wrong: ValueError: first line"
    notice = failure_notice(ValueError("boom"), "t1")
    assert notice["type"] == "notice" and notice["level"] == "error" and notice["thread"] == "t1"
    assert notice["code"] == "unknown" and notice["detail"] == "ValueError: boom"


def test_timeline_writes_are_coalesced_on_a_loop_and_immediate_off_one(tmp_path):
    import asyncio
    import json

    from dragon.server.events import Timeline

    path = tmp_path / "t.json"
    off = Timeline("t", path)
    off.add({"type": "user", "text": "now"})
    assert json.loads(path.read_text("utf-8"))["events"][0]["text"] == "now"

    def written() -> list[str]:
        # the texts on disk, not a substring of the file: an event id is random hex and can
        # contain "e19" by chance, which made the first version of this test flaky
        return [e["text"] for e in json.loads(path.read_text("utf-8"))["events"]]

    async def burst() -> None:
        tl = Timeline("t", path)
        for i in range(20):
            tl.add({"type": "user", "text": f"e{i}"})
        # nothing written yet: the burst is still being coalesced
        assert "e19" not in written()
        await asyncio.sleep(0.8)
        assert "e19" in written()
        tl.add({"type": "user", "text": "last"})
        tl.flush()  # shutdown path: written at once, the scheduled write dropped
        assert "last" in written()

    asyncio.run(burst())


# ----------------------------------------------------------------------------- update check
