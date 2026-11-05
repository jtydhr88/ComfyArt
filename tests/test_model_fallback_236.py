"""#236: when an image model call fails, switch once to the #133 table's backup.

The backup is the table's model for that task when it is a different model, otherwise the
feature default (the table's 通用 row). The model that failed is never submitted again.
A paid switch asks first, and the second submit stays inside the paid-guard cost rules.
Mocks only: no WaveSpeed HTTP.
"""
import json

import pytest

from ComfyArt.api import mcp, paid_guard
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.local_llm import (
    LocalLlmProvider,
    _cost_block_note,
    _no_switch_note,
    model_call_failed,
)
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest

FLARE = "openai/gpt-image-2.5-flare/text-to-image"
FLARE_EDIT = "openai/gpt-image-2.5-flare/edit"
SEEDREAM = "bytedance/seedream-v5.0-pro"
SEEDREAM_EDIT = "bytedance/seedream-v5.0-pro/edit"
NANO = "google/nano-banana-2.1/edit"
SUNBURST = "openai/gpt-image-2.5-sunburst/edit"
MJ = "midjourney/text-to-image"
RECRAFT = "recraft-ai/recraft-v3"
PORTRAIT = "Photorealistic portrait of an old fisherman"
ANIME = "Anime girl under cherry blossoms"


@pytest.fixture(autouse=True)
def _clear_guard():
    paid_guard.TURNS.clear()
    yield
    paid_guard.TURNS.clear()


def test_reply_contract_still_names_the_model():
    assert "say in your reply" in AGENT_GUIDE
    assert "which model was used and why" in AGENT_GUIDE
    assert "Do not resubmit a paid tool on the same model after that call fails." in AGENT_GUIDE


@pytest.mark.parametrize("action,args,failed,model,edit", [
    ("generate_image", {"prompt": PORTRAIT}, SEEDREAM, FLARE, False),
    ("generate_image", {"prompt": "Minimal logo for a tea brand"}, RECRAFT, FLARE, False),
    ("generate_image", {"prompt": ANIME, "model": "alibaba/qwen-image-3.0/text-to-image"},
     "alibaba/qwen-image-3.0/text-to-image", MJ, False),
    ("generate_image", {"prompt": ANIME}, MJ, FLARE, False),
    ("edit_image", {"id": "shape:a", "prompt": "new background, keep the same person"}, NANO, FLARE_EDIT, False),
    ("edit_image", {"id": "shape:a", "prompt": "new background, keep the same person"}, FLARE_EDIT, NANO, False),
    ("edit_image", {"id": "shape:a", "prompt": "retouch the skin"}, SEEDREAM_EDIT, FLARE_EDIT, False),
    ("edit_region", {"id": "shape:a", "prompt": "redo the sky", "x": 0, "y": 0, "width": 8, "height": 8},
     SUNBURST, FLARE_EDIT, False),
    ("edit_region", {"id": "shape:a", "prompt": "redo the sky", "x": 0, "y": 0, "width": 8, "height": 8},
     FLARE_EDIT, SUNBURST, False),
    ("generate_image", {"prompt": "two refs", "refs": ["shape:a", "shape:b"]}, NANO, FLARE_EDIT, True),
])
def test_fallback_follows_the_133_table(action, args, failed, model, edit):
    choice = canvas._fallback_choice(action, args, failed)
    assert choice["model"] == model and choice["fallback"] == failed and choice["model"] != failed
    assert ("edit_model" in choice) is edit
    if edit:
        assert choice["edit_model"] == model
    note = __import__("ComfyArt.api.auto_models", fromlist=["note"]).note(choice)
    assert note.startswith(f"用了 {model}，因为") and f"Used {model} because" in note
    assert failed in note


@pytest.mark.parametrize("action,args,failed", [
    ("generate_image", {"prompt": "a cup of coffee on a table"}, FLARE),
    ("generate_image", {"prompt": 'Movie poster with the headline "SUMMER"'}, FLARE),
    ("generate_image", {"prompt": "make it blue", "refs": ["shape:r"]}, FLARE_EDIT),
    ("generate_video", {"prompt": "a cat walking"}, "bytedance/seedance-2.0/text-to-video"),
])
def test_no_fallback_when_it_would_repeat_the_same_model(action, args, failed):
    assert canvas._fallback_choice(action, args, failed) is None


def test_decline_and_guard_are_not_model_failures():
    declined = json.dumps({"cancelled": True, "status": "declined",
                           "note": "已取消该生成，未扣费 / Cancelled this generation; nothing was charged."})
    assert model_call_failed("generate_image", {"prompt": PORTRAIT}, declined) is None
    assert model_call_failed("generate_image", {}, "已生成 1 张仍未完成，已停止，未继续扣费") is None
    assert model_call_failed("generate_image", {"model": SEEDREAM},
                             json.dumps({"status": "failed", "error": "WaveSpeed task failed", "model": SEEDREAM})) == SEEDREAM


def test_fallback_allowed_follows_the_cap_and_a_decline():
    paid_guard.begin_turn("c", text="做一张猫", provider_text="做一张猫", lang="zh")
    assert paid_guard.fallback_allowed("c", "generate_image", {"prompt": "p"})
    paid_guard.after_call("c", "generate_image", {"prompt": "p"},
                          {"status": "failed", "error": "WaveSpeed task failed"}, True)
    assert paid_guard.fallback_allowed("c", "generate_image", {"prompt": "p"})  # a failed run does not spend the cap
    paid_guard.after_call("c", "generate_image", {"prompt": "p"}, {"ids": ["g"]}, True)
    assert not paid_guard.fallback_allowed("c", "generate_image", {"prompt": "p"})
    paid_guard.TURNS.clear()
    paid_guard.begin_turn("c", text="poster-differentiated-compiler", provider_text="poster-differentiated-compiler", lang="en")
    paid_guard.after_call("c", "generate_image", {}, {"cancelled": True, "status": "declined"}, True)
    assert not paid_guard.fallback_allowed("c", "generate_image", {"prompt": "p"})
    assert paid_guard.fallback_allowed("no-such-turn", "generate_image", {"prompt": "p"})


@pytest.fixture
def page(monkeypatch):
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append((action, dict(args)))
        n = len([s for s in sent if s[0] == "generate_image"])
        if action == "wait_generation":
            return {"status": "done", "results": [{"id": "g1", "status": "error", "error": "WaveSpeed task failed"}]}
        if n == 1 and not args.get("fallback_for"):
            return {"status": "failed", "error": "WaveSpeed task failed", "model": args.get("model") or args.get("edit_model")}
        return {"ids": ["g2"], "model": args.get("edit_model") or args.get("model")}

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    return sent


def _gens(sent):
    return [a for action, a in sent if action == "generate_image"]


async def _turn(monkeypatch, steps, *, user_text="画一张写实人像", lang="zh", agree=True):
    """Built-in agent loop with the real MCP tool handlers and a fake page. No WaveSpeed."""
    chat_id = "c-236"
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    responses = [{"choices": [{"message": {"content": "", "tool_calls": [
        {"id": f"t{i}", "function": {"name": n, "arguments": json.dumps(a)}}]}}]}
                 for i, (n, a) in enumerate(steps)]
    responses.append({"choices": [{"message": {"content": "done", "tool_calls": []}}]})
    seen = []

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            seen.append(json_body)
            return responses.pop(0)
        return {"result": {"tools": [{"name": "generate_image"}, {"name": "edit_image"},
                                     {"name": "wait_generation"}, {"name": "ask_user"}]}}

    async def fake_call(session, endpoint, name, arguments):
        token = BOT_CHAT_ID.set(chat_id)
        try:
            out = await mcp._tools_call({"name": name, "arguments": arguments})
        finally:
            BOT_CHAT_ID.reset(token)
        text = out["content"][0]["text"]
        return ("[tool error] " + text if out.get("isError") else text), []

    asked = []

    async def confirm(self, session, endpoint, emit, lang_, messages, done, failed, target):
        asked.append((failed, target, lang_))
        return agree

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)

    async def free_price(model, inputs):  # #732: pricing now fails closed, so stub it (no WaveSpeed key here)
        return 0.0

    monkeypatch.setattr(provider, "_price_one", free_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_fallback", confirm)
    events: list[BotEvent] = []

    async def emit(ev: BotEvent):
        events.append(ev)

    paid_guard.begin_turn(chat_id, text=user_text, provider_text=user_text, lang=lang)
    result = await provider.send(TurnRequest(chat_id=chat_id, user_text=user_text, lang=lang,
                                             mcp_endpoint="http://x/mcp", model="m"), emit, TurnHandle())
    paid_guard.end_turn(chat_id)
    return result, events, seen, asked


async def test_paid_failure_asks_then_uses_the_table_default(monkeypatch, page):
    _result, events, seen, asked = await _turn(
        monkeypatch, [("generate_image", {"prompt": PORTRAIT})], user_text="画写实人像")
    assert asked == [(SEEDREAM, FLARE, "zh")]
    models = [a.get("model") for a in _gens(page)]
    assert models == [SEEDREAM, FLARE]
    blob = "\n".join(json.dumps(m, ensure_ascii=False) for m in seen)
    assert f"用了 {FLARE}，因为" in blob and f"Used {FLARE} because" in blob and SEEDREAM in blob
    notes = [json.loads(e.text).get("model_choice", {}).get("note", "")
             for e in events if e.t == "tool_result" and e.text.startswith("{")]
    assert any(n.startswith(f"用了 {FLARE}，因为") and f"Used {FLARE} because" in n and SEEDREAM in n for n in notes)


async def test_user_named_failure_switches_to_the_table_model(monkeypatch, page):
    named = "alibaba/qwen-image-3.0/text-to-image"
    await _turn(monkeypatch, [("generate_image", {"prompt": ANIME, "model": named})], user_text="画动漫")
    assert [a.get("model") for a in _gens(page)] == [named, MJ]


async def test_no_does_not_submit_the_fallback_or_the_same_model(monkeypatch, page):
    _result, events, _seen, asked = await _turn(
        monkeypatch, [("generate_image", {"prompt": PORTRAIT})], agree=False)
    assert [a.get("model") for a in _gens(page)] == [SEEDREAM]
    assert asked and asked[0][0] == SEEDREAM
    deltas = " ".join(e.text for e in events if e.t == "delta")
    assert _no_switch_note(SEEDREAM, FLARE, "zh") in deltas
    assert "没有用" in deltas and "was not submitted again" in deltas


async def test_same_model_is_not_retried_when_the_default_fails(monkeypatch, page):
    _result, events, _seen, asked = await _turn(
        monkeypatch, [("generate_image", {"prompt": "a cup of coffee on a table"})], user_text="画一杯咖啡")
    assert len(_gens(page)) == 1 and "model" not in _gens(page)[0]  # the default is the page's Auto model
    assert asked == []
    assert [e.text for e in events if e.t == "delta"] == ["done"]


async def test_declined_confirm_does_not_switch(monkeypatch):
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append(dict(args))
        return {"cancelled": True, "status": "declined",
                "note": "已取消该生成，未扣费 / Cancelled this generation; nothing was charged."}

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    _result, events, _seen, asked = await _turn(
        monkeypatch, [("generate_image", {"prompt": PORTRAIT})])
    assert len(sent) == 1 and asked == []
    assert not any("备用模型" in e.text for e in events if e.t == "delta")


async def test_cost_cap_blocks_the_fallback_submit(monkeypatch):
    """The first submit succeeded, so it counts. A later failure must not buy a second paid submit."""
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append((action, dict(args)))
        if action == "wait_generation":
            return {"status": "done", "results": [{"id": "g1", "status": "error", "error": "WaveSpeed task failed"}]}
        return {"ids": ["g1"], "model": args.get("model")}

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    _result, events, _seen, asked = await _turn(
        monkeypatch,
        [("generate_image", {"prompt": PORTRAIT}), ("wait_generation", {"ids": ["g1"]})],
        user_text="做一张写实人像")
    assert [a.get("model") for action, a in sent if action == "generate_image"] == [SEEDREAM]
    assert asked == []
    deltas = " ".join(e.text for e in events if e.t == "delta")
    assert _cost_block_note(SEEDREAM, FLARE, "zh") in deltas
    assert "费用规则" in deltas and "was not submitted again" in deltas


async def test_a_failed_fallback_does_not_chain(monkeypatch):
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append(dict(args))
        return {"status": "failed", "error": "WaveSpeed task failed",
                "model": args.get("model") or args.get("edit_model")}

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    await _turn(monkeypatch, [("generate_image", {"prompt": PORTRAIT})], user_text="画写实人像")
    assert [a.get("model") for a in sent] == [SEEDREAM, FLARE]


async def test_two_refs_fall_back_to_the_edit_default(monkeypatch):
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append(dict(args))
        if not args.get("edit_model") or args.get("edit_model") == NANO:
            return {"status": "failed", "error": "WaveSpeed task failed", "model": NANO}
        return {"ids": ["g2"], "model": args.get("edit_model")}

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    await _turn(monkeypatch, [("generate_image", {"prompt": "the mug", "refs": ["shape:a", "shape:b"]})],
                user_text="用这两张图")
    edits = [a.get("edit_model") for a in sent]
    assert edits == [NANO, FLARE_EDIT]
    assert all(a.get("model") != NANO for a in sent)
    assert all("fallback_for" not in a for a in sent)


async def test_handler_refuses_same_model_without_submitting(page):
    out = await canvas.TOOLS["generate_image"]["handler"](
        {"prompt": "a cup of coffee on a table", "fallback_for": FLARE})
    assert out["same_model_retry"] is False and out["model"] == FLARE
    assert page == []
    assert "Did not submit" in out["note"] and "没有用" in out["note"]


async def test_ask_is_the_paid_gate_and_names_both_models(monkeypatch):
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    calls = []

    async def fake_call(session, endpoint, name, arguments):
        calls.append((name, dict(arguments)))
        if name == "ask_user":
            return json.dumps({"status": "answered", "selected": ["no"]}), []
        return json.dumps({"status": "failed", "error": "WaveSpeed task failed", "model": SEEDREAM}), []

    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    script = [{"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "t0", "function": {"name": "generate_image", "arguments": json.dumps({"prompt": PORTRAIT})}}]}}]},
              {"choices": [{"message": {"content": "done", "tool_calls": []}}]}]

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            return script.pop(0)
        return {"result": {"tools": [{"name": "generate_image"}, {"name": "ask_user"}]}}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    events: list[BotEvent] = []

    async def emit(ev):
        events.append(ev)

    await provider.send(TurnRequest(chat_id="c", user_text="portrait", lang="en",
                                    mcp_endpoint="http://x/mcp", model="m"), emit, TurnHandle())
    assert [c[0] for c in calls] == ["generate_image", "ask_user"]
    prompt = calls[1][1]["prompt"]
    assert SEEDREAM in prompt and FLARE in prompt and "same model will not be submitted again" in prompt
    assert [o["id"] for o in calls[1][1]["options"]] == ["yes", "no"]
    assert any(_no_switch_note(SEEDREAM, FLARE, "en") in e.text for e in events if e.t == "delta")


async def test_handler_submit_uses_fallback_and_names_it(page):
    out = await canvas.TOOLS["generate_image"]["handler"]({"prompt": PORTRAIT, "fallback_for": SEEDREAM})
    assert _gens(page)[0]["model"] == FLARE and "fallback_for" not in _gens(page)[0]
    note = out["model_choice"]["note"]
    assert note.startswith(f"用了 {FLARE}，因为") and f"Used {FLARE} because" in note and SEEDREAM in note
    assert "费用规则" in _cost_block_note(SEEDREAM, FLARE, "zh")
    assert "cost rules" in _cost_block_note(SEEDREAM, FLARE, "en")
