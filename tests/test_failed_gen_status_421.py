"""#421: a failed generate_image must show as failed, not the success/done generation row."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ComfyArt.api import paid_guard
from ComfyArt.bot.local_llm import LocalLlmProvider, model_call_failed
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "src/styles/overlays.css").read_text(encoding="utf-8")
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))

SEEDREAM = "bytedance/seedream-v5.0-pro"
FAIL_JSON = json.dumps({
    "status": "failed",
    "error": "WaveSpeed task failed",
    "model": SEEDREAM,
})
CANCEL_TEXT = "已取消该生成，未扣费。"


async def _free_price(model, inputs):
    return 0.0


def test_model_call_failed_detects_payload() -> None:
    assert model_call_failed("generate_image", {"model": SEEDREAM}, FAIL_JSON) == SEEDREAM
    assert model_call_failed("generate_image", {}, CANCEL_TEXT) is None
    wait_fail = json.dumps({
        "status": "done",
        "results": [{"id": "g1", "status": "error", "error": "WaveSpeed task failed", "model": SEEDREAM}],
    })
    assert model_call_failed("wait_generation", {"ids": ["g1"]}, wait_fail) == SEEDREAM


@pytest.fixture(autouse=True)
def _clear_guard():
    paid_guard.TURNS.clear()
    yield
    paid_guard.TURNS.clear()


@pytest.mark.asyncio
async def test_generate_image_failure_marks_is_error(monkeypatch) -> None:
    """Backend: WaveSpeed/model failure on generate_image sets tool_result.is_error (not only transport)."""
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [{
            "id": "t1", "function": {
                "name": "generate_image",
                "arguments": json.dumps({"prompt": "cat", "model": SEEDREAM}),
            },
        }]}}]},
        {"choices": [{"message": {"content": "sorry", "tool_calls": []}}]},
    ]

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            return responses.pop(0)
        return {"result": {"tools": [
            {"name": "generate_image"}, {"name": "wait_generation"}, {"name": "ask_user"},
        ]}}

    async def fake_call(session, endpoint, name, arguments):
        if name == "ask_user":
            return json.dumps({"status": "answered", "selected": ["no"]}), []
        return FAIL_JSON, []

    async def no_fallback(self, *a, **k):
        return False

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_price_one", _free_price)  # #732: pricing fails closed; no key here
    monkeypatch.setattr(LocalLlmProvider, "_confirm_fallback", no_fallback)

    events: list[BotEvent] = []

    async def emit(ev: BotEvent):
        if not ev.t.startswith("run_"):
            events.append(ev)

    chat_id = "c421"
    paid_guard.begin_turn(chat_id, text="画一只猫", provider_text="画一只猫", lang="zh")
    await provider.send(
        TurnRequest(chat_id=chat_id, user_text="画一只猫", lang="zh",
                    mcp_endpoint="http://x/mcp", model="m1"),
        emit, TurnHandle())
    paid_guard.end_turn(chat_id)

    tr = next(e for e in events if e.t == "tool_result" and e.name == "generate_image")
    assert tr.is_error is True
    assert "failed" in tr.text


@pytest.mark.asyncio
async def test_cancelled_generate_is_not_error(monkeypatch) -> None:
    """Cancel / decline must stay non-error (detail=cancelled), same as before #421."""
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [{
            "id": "t1", "function": {
                "name": "generate_image",
                "arguments": json.dumps({"prompt": "cat", "model": SEEDREAM}),
            },
        }]}}]},
        {"choices": [{"message": {"content": "ok", "tool_calls": []}}]},
    ]

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            return responses.pop(0)
        return {"result": {"tools": [{"name": "generate_image"}, {"name": "ask_user"}]}}

    async def fake_call(session, endpoint, name, arguments):
        return CANCEL_TEXT, []

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_price_one", _free_price)  # #732: pricing fails closed; no key here

    events: list[BotEvent] = []

    async def emit(ev: BotEvent):
        if not ev.t.startswith("run_"):
            events.append(ev)

    chat_id = "c421c"
    paid_guard.begin_turn(chat_id, text="画", provider_text="画", lang="zh")
    await provider.send(
        TurnRequest(chat_id=chat_id, user_text="画", lang="zh",
                    mcp_endpoint="http://x/mcp", model="m1"),
        emit, TurnHandle())
    paid_guard.end_turn(chat_id)

    tr = next(e for e in events if e.t == "tool_result" and e.name == "generate_image")
    assert tr.is_error is False
    assert tr.detail == "cancelled"


def test_ui_wires_failed_generation_label() -> None:
    assert ZH["chatMessage.failed"] == "失败" and EN["chatMessage.failed"] == "Failed"
    assert "chatMessage.failed" in CHAT
    assert "genFailed" in CHAT and "waitFailed" in CHAT
    assert "data-error={s.error || undefined}" in CHAT
    assert "process-row-failed" in CHAT
    assert ".ca-process__row[data-error] .ca-process__label" in CSS
