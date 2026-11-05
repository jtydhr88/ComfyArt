"""#754: kit interface adapted onto our providers (host=, unloads_lms_during_waits, after_output_id,
core_tools, single ask_user PENDING store)."""
import asyncio
import json

from ComfyArt.api import bot_asks as api_asks
from ComfyArt.api.providers import AgentLlmProvider
from ComfyArt.bot import bot_asks as kit_asks
from ComfyArt.bot import lms
from ComfyArt.bot.guide import CORE_MCP_TOOLS, HOST, PAID_TOOLS
from ComfyArt.bot.providers import TurnHandle

WS_URL = "https://llm.wavespeed.ai/v1"
LMS_URL = "http://127.0.0.1:1234/v1"


def _provider(url):
    return AgentLlmProvider(host=HOST, base_url=lambda: url)


def _run_wait(provider, monkeypatch, replies):
    calls = {"unload": 0, "load": 0, "args": []}

    async def unload():
        calls["unload"] += 1
        return True

    async def load(model):
        calls["load"] += 1

    monkeypatch.setattr(lms, "lms_bin", lambda: "/usr/bin/lms")
    monkeypatch.setattr(lms, "unload_models", unload)
    monkeypatch.setattr(lms, "load_model", load)
    it = iter(replies)

    async def call_tool(session, endpoint, name, args):
        assert name == HOST.wait_tool
        calls["args"].append(dict(args))
        return json.dumps(next(it)), []

    monkeypatch.setattr(provider, "_mcp_call_tool", call_tool)
    raw = asyncio.run(provider._wait_stage_done(None, "http://x/mcp", {"ids": ["a"]}, "m", TurnHandle()))
    return raw, calls


def test_wavespeed_url_does_not_unload_lms(monkeypatch):
    p = _provider(WS_URL)
    assert p.unloads_lms_during_waits is False
    _raw, calls = _run_wait(p, monkeypatch, [{"status": "done"}])
    assert calls["unload"] == 0 and calls["load"] == 0


def test_lm_studio_url_keeps_unload_reload(monkeypatch):
    p = _provider(LMS_URL)
    assert p.unloads_lms_during_waits is True
    _raw, calls = _run_wait(p, monkeypatch, [{"status": "done"}])
    assert calls["unload"] == 1 and calls["load"] == 1


def test_after_output_id_resumes_wait(monkeypatch):
    p = _provider(WS_URL)
    raw, calls = _run_wait(p, monkeypatch, [
        {"status": "running", "after_output_id": "o1"},
        {"status": "running", "after_output_id": "o2"},
        {"status": "done"},
    ])
    assert json.loads(raw)["status"] == "done"
    assert "after_output_id" not in calls["args"][0]
    assert calls["args"][1]["after_output_id"] == "o1"
    assert calls["args"][2]["after_output_id"] == "o2"


def test_host_core_tools_keep_skills_and_guard_tools():
    tools = set(HOST.core_tools)
    assert tools == set(CORE_MCP_TOOLS)
    for t in ("skill", "ask_user", "update_plan", "wait_generation", "custom_workflow", "memory"):
        assert t in tools
    paid_mcp = {t for t in PAID_TOOLS if t not in ("ocr", "transcribe")}
    assert paid_mcp <= tools
    assert HOST.local_llm_key_env == "COMFYART_LOCAL_LLM_API_KEY"


def test_api_and_kit_bot_asks_share_one_pending_store():
    assert api_asks.PENDING is kit_asks.PENDING
    assert api_asks.ANSWERED_RUN_APPROVALS is kit_asks.ANSWERED_RUN_APPROVALS
    assert issubclass(api_asks.PendingAsk, kit_asks.PendingAsk)
    assert api_asks.ASK_TIMEOUT_S == kit_asks.ASK_TIMEOUT_S

    async def go():
        ask = api_asks.create_ask("c754", "m1", {"prompt": "?", "options": [{"id": "a", "label": "A"}]})
        try:
            assert kit_asks.PENDING[ask.id] is ask
        finally:
            api_asks.cancel_chat_asks("c754")
        assert ask.id not in kit_asks.PENDING

    asyncio.run(go())
