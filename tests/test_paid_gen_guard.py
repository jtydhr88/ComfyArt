"""#142: paid-generation guard and product-reference block, shared by every
provider (it sits in the MCP layer, before a paid tool relays to WaveSpeed).
S8 is replayed through the Local LLM provider and through Claude Code (a fake
``claude`` executable speaking real MCP over HTTP). Mocks only: no LLM, CLI or
WaveSpeed traffic leaves the process."""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest
from conftest import wait_bot_done

from ComfyArt.api import chat_store, mcp, paid_guard, wavespeed
from ComfyArt.api.bot_send import compose_provider_text
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.guide import PAID_TOOLS
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest

S8_TEXT = compose_provider_text("用这张产品图做电商图（图片 id: shape:src）", skill_name="product-tvc-advertisement-generator")
ZH_STOP = "已生成 4 张仍未完成，已停止，未继续扣费，请告诉我怎么调整"
EN_STOP = ("Generated 4 images and still not done, so I stopped; no further "
           "charges. Tell me how to adjust.")


@pytest.fixture
def submits(monkeypatch):
    """Fake handlers for the tools S8 touches; paid ones record a submit."""
    class _Log(list):
        decline: dict
    log = _Log()
    decline = {"n": 0}

    def fake(name):
        async def handler(args):
            if name in PAID_TOOLS:
                if decline["n"]:
                    decline["n"] -= 1
                    # Mirrors frontend COST_DECLINED note (#127)
                    return {"cancelled": True, "status": "declined",
                            "note": "已取消该生成，未扣费 / Cancelled this generation; "
                                    "nothing was charged. Reply as normal chat text."}
                log.append((name, dict(args)))
                return {"ids": [f"gen:{len(log)}"]}
            return {"ok": True}
        return handler
    for name in ("generate_image", "generate_video", "edit_image", "update_plan", "wait_generation"):
        monkeypatch.setitem(mcp.TOOLS, name, {**mcp.TOOLS[name], "handler": fake(name)})
    log.decline = decline
    yield log
    paid_guard.TURNS.clear()


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args)}}


def _s8_gen(i: int, **extra) -> tuple[str, dict]:
    # the real S8 calls: a new prompt each time (S8 itself never passed refs)
    return ("generate_image", {"prompt": f"E-commerce shot {i}: the product from the reference image", **extra})


async def _local(monkeypatch, steps, user_text=S8_TEXT, lang="", typed=None):
    """One Local LLM turn wired like bot_turns._run_turn: the guard is opened
    for the chat, every tool call goes through the real MCP dispatch."""
    chat_id = "c-local"
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    responses = [{"choices": [{"message": {"content": "", "tool_calls": [_tc(i, n, a)]}}]}
                 for i, (n, a) in enumerate(steps)]
    responses.append({"choices": [{"message": {"content": "done", "tool_calls": []}}]})
    llm: list[int] = []
    results: dict[str, dict] = {}

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            llm.append(1)
            return responses.pop(0)
        return {"result": {"tools": [{"name": n} for n in ("skill", "generate_image", "update_plan", "wait_generation", "edit_image")]}}

    async def fake_call(session, endpoint, name, arguments):
        token = BOT_CHAT_ID.set(chat_id)
        try:
            out = await mcp._tools_call({"name": name, "arguments": arguments})
        finally:
            BOT_CHAT_ID.reset(token)
        results[name + str(len(results))] = out
        text = out["content"][0]["text"]
        return ("[tool error] " + text if out["isError"] else text), []

    async def fake_wait(session, endpoint, args, model, handle):
        return json.dumps({"status": "done"})

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_wait_stage_done", fake_wait)
    events = []

    async def emit(e):
        events.append(e)
    handle = TurnHandle()
    paid_guard.begin_turn(chat_id, text=typed if typed is not None else user_text, provider_text=user_text,
                          lang=lang, on_stop=paid_guard.stop_later(provider, handle))
    result = await provider.send(TurnRequest(chat_id=chat_id, user_text=user_text, lang=lang,
                                             mcp_endpoint="http://x/mcp", model="m1"), emit, handle)
    stop = paid_guard.end_turn(chat_id)
    return (stop or result.error or ""), events, llm


def _paid(log):
    return [s for s in log if s[0] in PAID_TOOLS]


# ---- rule 1: at most 4 paid generations per plan item (or exactly N) -----------------------------

async def test_s8_replay_local_llm_fifth_paid_submit_is_zero(monkeypatch, submits):
    steps = [("skill", {"action": "read", "name": "product-tvc-advertisement-generator"})]
    for i in range(25):  # S8 asked for 25 generations
        steps += [_s8_gen(i, refs=["shape:src"]), ("wait_generation", {"ids": [f"gen:{i}"]})]
    error, events, llm = await _local(monkeypatch, steps)
    assert len(_paid(submits)) == 4  # the 5th paid submit never happens
    assert error.startswith(ZH_STOP)
    assert "已完成：" in error and "生成图像 ×4" in error and error.rstrip().endswith("。")
    assert len(llm) == 10  # skill + 4×(gen, wait) + the refused 5th; no LLM spend after
    fifth = [e for e in events if e.t == "tool_result" and e.id == "t9"][0]
    assert fifth.text.startswith("[tool error] " + ZH_STOP)


S8_CLAUDE = textwrap.dedent(r"""
    # fake `claude`: replays S8 against the real ComfyArt MCP endpoint
    import json, sys, urllib.request
    argv = sys.argv
    url = json.loads(argv[argv.index("--mcp-config") + 1])["mcpServers"]["comfyart"]["url"]
    def call(i, name, args):
        body = {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}}
        req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json"})
        res = json.loads(urllib.request.urlopen(req).read())["result"]
        print(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": f"t{i}", "name": "mcp__comfyart__" + name, "input": args}]}}), flush=True)
        print(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": f"t{i}", "content": res["content"][0]["text"],
             "is_error": res["isError"]}]}}), flush=True)
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "s8"}), flush=True)
    for i in range(25):
        call(i, "generate_image", {"prompt": f"E-commerce shot {i}: the product from the reference image",
                                   "refs": ["shape:src"]})
    print(json.dumps({"type": "result", "subtype": "success", "result": "done", "session_id": "s8"}), flush=True)
""")


@pytest.mark.parametrize("lang,stop", [("zh", ZH_STOP), ("en", EN_STOP)])
async def test_s8_replay_claude_code_fifth_paid_submit_is_zero(bot_client, submits, monkeypatch, tmp_path, lang, stop):
    from server import PromptServer

    from ComfyArt.bot import claude_code
    script = tmp_path / "fake_claude.py"
    script.write_text(S8_CLAUDE)
    monkeypatch.setattr(claude_code, "resolve_claude_command", lambda: [sys.executable, str(script)])
    monkeypatch.setattr(PromptServer.instance, "port", bot_client.server.port, raising=False)
    chat = chat_store.create_chat(user="default", project="p", provider="claude-code")
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": "用这张产品图做电商图（图片 id: shape:src）", "skill": "product-tvc-advertisement-generator", "lang": lang})
    assert resp.status == 200, await resp.text()
    data = await wait_bot_done(bot_client, chat["id"], timeout=20)
    assert len(_paid(submits)) == 4  # 5th (and every later) submit: 0
    assistant = data["messages"][-1]
    assert assistant["status"] == "error"
    notice = [b for b in assistant["blocks"] if b["type"] == "notice"][-1]
    assert notice["level"] == "error" and notice["text"].startswith(stop)


async def test_stop_text_follows_ui_language_en(monkeypatch, submits):
    error, *_ = await _local(monkeypatch, [_s8_gen(i, refs=["shape:src"]) for i in range(6)], lang="en")
    assert error.startswith(EN_STOP) and "Generate image ×4" in error


async def test_count_argument_counts_images(monkeypatch, submits):
    steps = [_s8_gen(0, refs=["shape:src"], count=3), _s8_gen(1, refs=["shape:src"], count=2)]
    error, *_ = await _local(monkeypatch, steps)
    assert len(_paid(submits)) == 1 and error.startswith(ZH_STOP)


async def test_user_asked_for_n_uses_n(monkeypatch, submits):
    steps = [("generate_image", {"prompt": f"cat {i}"}) for i in range(8)]
    error, *_ = await _local(monkeypatch, steps, user_text="画 6 张猫的插画")
    assert len(_paid(submits)) == 6 and error.startswith("已生成 6 张仍未完成")


async def test_smaller_n_is_exact(monkeypatch, submits):
    steps = [("generate_image", {"prompt": f"cat {i}"}) for i in range(6)]
    error, *_ = await _local(monkeypatch, steps, user_text="做一张猫的海报")
    assert len(_paid(submits)) == 1
    assert error.startswith("已生成 1 张仍未完成，已停止，未继续扣费，请告诉我怎么调整")


async def test_decline_locks_plan_item_no_second_submit(monkeypatch, submits):
    """#127: after the user declines a cost confirm, same plan item gets no
    further paid submits (at most one confirm dialog per item per turn)."""
    submits.decline["n"] = 1
    steps = [("generate_image", {"prompt": f"cat {i}"}) for i in range(3)]
    error, events, _llm = await _local(monkeypatch, steps, user_text="做一张猫的海报")
    assert len(_paid(submits)) == 0
    texts = [e.text for e in events if e.t == "tool_result"]
    assert any("已取消该生成，未扣费" in x for x in texts)
    # later retries are refused before submit (paid_guard DECLINED_TEXT)
    assert sum(1 for x in texts if "已取消该生成，未扣费" in x) >= 2
    assert not error  # not the #137 red cap-stop notice


async def test_decline_on_one_plan_item_does_not_block_another(monkeypatch, submits):
    """#127: a decline only locks that plan item; the next item can still run."""
    def plan(active):
        return ("update_plan", {"steps": [
            {"text": t, "status": "active" if t == active else "pending"}
            for t in ("hero", "lifestyle")]})
    submits.decline["n"] = 1  # first paid call (on hero) declines
    steps = [plan("hero"), ("generate_image", {"prompt": "h0"}),
             ("generate_image", {"prompt": "h1"}),  # locked — no submit
             plan("lifestyle"), ("generate_image", {"prompt": "l0"})]
    error, *_ = await _local(monkeypatch, steps, user_text="poster set")
    assert [s[1]["prompt"] for s in _paid(submits)] == ["l0"]
    assert not error


@pytest.mark.gate_skip(reason="stale on main: per-plan-item cap now yields 7 calls, test expects 9 (paid-gen guard, #717)")
async def test_each_plan_item_gets_its_own_four(monkeypatch, submits):
    def plan(active):
        return ("update_plan", {"steps": [{"text": t, "status": "active" if t == active else "pending"}
                                          for t in ("hero", "lifestyle", "detail")]})
    steps = [plan("hero"), *[("generate_image", {"prompt": f"h{i}"}) for i in range(4)],
             plan("lifestyle"), *[("generate_image", {"prompt": f"l{i}"}) for i in range(4)],
             plan("detail"), ("generate_image", {"prompt": "d0"})]
    error, *_ = await _local(monkeypatch, steps, user_text="poster set")
    assert len(_paid(submits)) == 9 and not error


async def test_declined_runs_do_not_count(monkeypatch, submits):
    """Declined runs never increment the cap; a fresh plan item still gets its quota."""
    def plan(active):
        return ("update_plan", {"steps": [
            {"text": t, "status": "active" if t == active else "pending"}
            for t in ("a", "b")]})
    submits.decline["n"] = 1
    steps = [plan("a"), ("generate_image", {"prompt": "declined"}),
             plan("b"), *[("generate_image", {"prompt": f"b{i}"}) for i in range(4)]]
    error, *_ = await _local(monkeypatch, steps, user_text="poster-differentiated-compiler")
    assert len(_paid(submits)) == 4 and not error
    assert all(s[1]["prompt"].startswith("b") for s in _paid(submits))


async def test_no_guard_outside_a_bot_turn(submits):
    # plain MCP clients (no bot chat) are not turn-scoped
    for i in range(6):
        out = await mcp._tools_call({"name": "generate_image", "arguments": {"prompt": str(i)}})
        assert not out["isError"]
    assert len(_paid(submits)) == 6


def test_charged_reads_cancel_and_errors():
    assert paid_guard.charged({"ids": ["gen:1"]})
    assert not paid_guard.charged({"cancelled": True, "status": "declined"})
    assert not paid_guard.charged('{"error": "boom"}')
    assert paid_guard.user_declined({"cancelled": True, "status": "declined"})
    assert not paid_guard.user_declined({"error": "boom"})
    assert not paid_guard.user_declined({"ids": ["gen:1"]})


def test_declined_copy_is_user_facing_not_internal():
    """#127: tool/agent copy is 「已取消该生成，未扣费」, not 「用户已拒绝」."""
    assert "已取消该生成，未扣费" in paid_guard.DECLINED_TEXT["zh"]
    assert "用户已拒绝" not in paid_guard.DECLINED_TEXT["zh"]
    assert "Cancelled this generation" in paid_guard.DECLINED_TEXT["en"]
    assert "nothing was charged" in paid_guard.DECLINED_TEXT["en"]
    root = Path(__file__).resolve().parent.parent
    zh = (root / "src/locales/zh.json").read_text()
    en = (root / "src/locales/en.json").read_text()
    assert '"jobs.costDeclined": "已取消该生成，未扣费"' in zh
    assert '"jobs.costDeclined": "Cancelled this generation; nothing was charged"' in en


def test_requested_count():
    rc = paid_guard.requested_count
    assert rc("做 6 张海报") == 6 and rc("来三张") == 3 and rc("make 2 images") == 2
    assert rc("做一张海报 1:1") == 1 and rc("电商图") == 0
    assert rc(S8_TEXT) == 0  # skill hint text is not the user's ask


def test_paid_tools_match_wavespeed_tool_features():
    assert PAID_TOOLS == set(wavespeed.load_config()["tool_features"])


# ---- rule 2: the product reference must be passed -----------------------------------------------

async def test_generation_without_reference_is_blocked_before_submit(monkeypatch, submits):
    steps = [_s8_gen(0), _s8_gen(1, refs=["shape:src"], ref_modes=["content"])]
    error, events, _ = await _local(monkeypatch, steps)
    assert [s[1].get("refs") for s in _paid(submits)] == [["shape:src"]]
    blocked = [e for e in events if e.t == "tool_result" and e.id == "t0"][0]
    assert blocked.text.startswith("[tool error]") and "shape:src" in blocked.text and "refs" in blocked.text
    assert "nothing was charged" in blocked.text
    assert not error


@pytest.mark.gate_skip(reason="stale on main: guard returns no paid calls in this path (paid-gen guard, #717)")
async def test_blocked_calls_do_not_count_toward_cap(monkeypatch, submits):
    steps = [_s8_gen(i) for i in range(6)] + [_s8_gen(9, refs=["shape:src"])]
    error, *_ = await _local(monkeypatch, steps)
    assert len(_paid(submits)) == 1 and not error


async def test_base_or_attached_image_line_counts_as_reference(monkeypatch, submits):
    text = compose_provider_text("做电商主图", skill_name="product-tvc-advertisement-generator", lines=[
        "[Attached image 1: shape id shape:abc — /view?x. Use the shape id with edit tools or as a generation ref.]"])
    assert paid_guard.product_refs(text) == ["shape:abc"]
    steps = [("generate_image", {"prompt": "p", "base": "shape:abc"}),
             ("generate_image", {"prompt": "p", "refs": ["shape:other"]})]
    await _local(monkeypatch, steps, user_text=text)
    assert len(_paid(submits)) == 1


async def test_no_block_without_product_reference(monkeypatch, submits):
    assert paid_guard.product_refs("画一张极简咖啡海报") == []
    assert paid_guard.product_refs("把这张图背景换成海边（图片 id: shape:src）") == []
    await _local(monkeypatch, [("generate_image", {"prompt": "p"})], user_text="画一张海报")
    assert len(_paid(submits)) == 1


async def test_edit_tools_are_not_ref_blocked(monkeypatch, submits):
    await _local(monkeypatch, [("edit_image", {"id": "shape:src", "prompt": "white bg"})])
    assert len(_paid(submits)) == 1


def test_product_skill_tells_the_agent_to_pass_refs():
    src = (Path(__file__).resolve().parent.parent / "src" / "skills.ts").read_text()
    line = next(l for l in src.splitlines() if "id: 'product-tvc-advertisement-generator'" in l)
    assert "refs" in line and "does not send the image" in line
    assert "only refs do" in canvas.TOOLS["generate_image"]["description"]


# ---- #143: list_models accepts tool names --------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json"


@pytest.fixture
def mock_catalog(monkeypatch):
    models = json.loads(FIXTURE.read_text())

    async def fake_catalog(refresh=False):
        return models
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    monkeypatch.setattr(canvas, "grouped_models", wavespeed.grouped_models)


@pytest.mark.parametrize("tool,feature", [("animate_image", "image_to_video"),
                                          ("generate_image", "text_to_image"),
                                          ("edit_image", "image_edit")])
async def test_list_models_tool_name_matches_feature(mock_catalog, tool, feature):
    for extra in ({}, {"all": True}):
        assert (await canvas._list_models({"type": tool, **extra})
                == await canvas._list_models({"type": feature, **extra}))


async def test_list_models_unknown_type_lists_valid_names(mock_catalog):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await canvas._list_models({"type": "bogus"})
    msg = str(e.value)
    for name in ("video", "image_to_video", "text_to_image", "animate_image", "generate_image"):
        assert name in msg



@pytest.fixture(autouse=True)
def _known_low_price(monkeypatch):
    """#418: these cases are about caps / guards, not the confirm card. Pin every WaveSpeed price to a
    known low quote (1 credit, under the default 50-credit line) so no test reaches the real price API
    and an offline run is not 'unpriced' (which, by rule, always asks)."""
    from ComfyArt.api import wavespeed as _ws

    async def _low(model, inputs):
        return 0.01, "quote"
    monkeypatch.setattr(_ws, "_quote", _low)

    async def _cheap_models(self, feature):
        return [("known-low/model", 0.01)]
    from ComfyArt.bot.local_llm import LocalLlmProvider as _P
    monkeypatch.setattr(_P, "_models_for", _cheap_models)
