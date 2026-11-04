"""#235: estimate a multi-step paid task and confirm before it starts.

Mocks only. The price table is injected; nothing calls WaveSpeed or an LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.local_llm import (
    LocalLlmProvider, _CANCEL_RE, _PLAN_QUOTE_RULE, _SYSTEM_PROMPT,
)
from ComfyArt.bot.plan_quote import (
    CANCEL_TEXT, START_LABEL, build_quote, canon_key, usd,
)
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest

ROOT = Path(__file__).resolve().parent.parent

POSTER = "acme/poster-xl"
VIDEO = "acme/clip-hd"


def _models(table):
    async def models_for(feature):
        return list(table.get(feature, []))
    return models_for


def _pricer(prices, seen):
    async def pricer(model, inputs):
        seen.append((model, dict(inputs)))
        return prices.get(model)
    return pricer


def _step(text, tool, model, **args):
    return {"text": text, "tool": tool, "model": model, "arguments": args}


async def _quote(steps, *, threshold=0.5, prices=None, models=None, lang="zh"):
    seen = []
    prices = prices if prices is not None else {POSTER: 0.04, VIDEO: 0.60}
    quote = await build_quote(
        steps, lang, threshold=threshold,
        pricer=_pricer(prices, seen),
        models_for=_models(models or {}),
    )
    return quote, seen


def test_usd_matches_the_frontend_formatter():
    assert [usd(n) for n in (0.039, 0.0893, 0.04, 0.10, 1, 0.0035, 0.069, 0.24, 12.5, 0)] == [
        "0.039", "0.0893", "0.04", "0.10", "1.00", "0.0035", "0.069", "0.24", "12.50", "0.00"]


async def test_wording_zh_and_en_and_buttons():
    steps = [_step("生成海报", "generate_image", POSTER, prompt="p"),
             _step("生成视频", "generate_video", VIDEO, prompt="v", duration=5)]
    zh, seen = await _quote(steps, threshold=0.5)
    en, _ = await _quote(steps, threshold=0.5, lang="en")
    assert zh is not None and en is not None
    assert zh.prompt == "这个任务共 2 步，预计约 64 积分，超过了你设置的 50 积分确认线。确定开始吗？"
    assert en.prompt == "This task has 2 steps and will cost about 64 credits, above your 50 credits confirm limit. Start?"
    assert "$" not in zh.prompt and "$" not in en.prompt
    assert zh.ask and en.ask
    assert [(ln.text, ln.price) for ln in zh.lines] == [
        ("生成海报 · poster-xl", "4 积分"), ("生成视频 · clip-hd", "60 积分")]
    assert zh.total_label == "总价" and zh.total_text == "64 积分"
    assert en.total_label == "Total"
    spec = zh.ask_spec()
    assert spec["kind"] == "plan_quote"
    assert [o["label"] for o in spec["options"]] == [START_LABEL["zh"], "取消"]
    assert [o["label"] for o in en.ask_spec()["options"]] == ["Start", "Cancel"]
    assert seen[1][1]["duration"] == 5
    assert "num_images" not in seen[0][1]


async def test_threshold_boundary_and_zero_and_under():
    steps = [_step("a", "generate_image", POSTER, prompt="p"),
             _step("b", "generate_image", POSTER, prompt="q")]
    at, _ = await _quote(steps, threshold=0.08, prices={POSTER: 0.04})
    under, _ = await _quote(steps, threshold=0.09, prices={POSTER: 0.04})
    always, _ = await _quote(steps, threshold=0, prices={POSTER: 0.04})
    assert at is not None and at.total == 0.08 and at.ask
    assert under is not None and under.ask is False
    assert under.started_result() == '{"ok": true, "start": true}'
    assert "$" not in under.started_result()
    assert always is not None and always.ask  # 0 means always confirm


async def test_unknown_price_uses_the_dearest_model_and_marks_approx():
    steps = [_step("海报", "generate_image", "acme/mystery", prompt="p"),
             _step("视频", "generate_video", "", prompt="v")]
    called = []

    async def pricer(model, inputs):
        called.append(model)
        return None

    async def models_for(feature):
        if feature == "text_to_image":
            return [("acme/cheap", 0.02), ("acme/dearest-image", 0.24)]
        if feature == "text_to_video":
            return [("acme/dearest-video", 0.9), ("acme/short", 0.1)]
        return []

    quote = await build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for)
    assert quote is not None and quote.ask
    assert quote.lines[0].price == "约 24 积分" and "mystery" in quote.lines[0].text
    assert quote.lines[1].price == "约 90 积分" and "dearest-video" in quote.lines[1].text
    assert quote.total == 1.14 and quote.total_text == "约 114 积分"
    assert "$" not in quote.total_text and "$" not in quote.prompt
    assert called == ["acme/mystery"]  # a named model is quoted; an empty one is not
    en = await build_quote(steps, "en", threshold=0.5, pricer=pricer, models_for=models_for)
    assert en is not None and en.lines[0].price == "about 24 credits" and en.total_text == "about 114 credits"


async def test_fully_unpriced_step_still_asks_without_a_fake_zero():
    steps = [_step("海报", "generate_image", "acme/mystery", prompt="p"),
             _step("视频", "generate_video", VIDEO, prompt="v")]

    async def pricer(model, inputs):
        return 0.10 if model == VIDEO else None

    async def models_for(feature):
        return []

    quote = await build_quote(steps, "zh", threshold=100, pricer=pricer, models_for=models_for)
    assert quote is not None and quote.ask  # one step has no price at all, so ask even under the line
    assert quote.lines[0].price == "约"
    assert "$" not in quote.lines[0].price and "积分 0" not in quote.lines[0].price
    assert quote.lines[1].price == "10 积分"
    assert quote.total_text == "约 10 积分"  # the unpriced line makes the sum an estimate too


async def test_an_estimate_line_prefixes_the_total():
    """One 「约」 line makes the total 「约 64 积分」 / "about 64 credits". Exact lines leave the total bare."""
    steps = [_step("海报", "generate_image", POSTER, prompt="p"),
             _step("视频", "generate_video", "acme/mystery", prompt="v")]

    async def pricer(model, inputs):
        return 0.40 if model == POSTER else None

    async def models_for(feature):
        return [("acme/dearest-video", 0.24)] if feature == "text_to_video" else []

    zh = await build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for)
    en = await build_quote(steps, "en", threshold=0.5, pricer=pricer, models_for=models_for)
    assert zh is not None and en is not None
    assert zh.lines[0].price == "40 积分" and zh.lines[1].price == "约 24 积分"
    assert zh.total_text == "约 64 积分" and en.total_text == "about 64 credits"
    assert en.lines[1].price == "about 24 credits"
    exact, _ = await _quote(
        [_step("a", "generate_image", POSTER, prompt="p"),
         _step("b", "generate_image", POSTER, prompt="q")],
        threshold=0.5, prices={POSTER: 0.32})
    assert exact is not None and exact.total_text == "64 积分"


async def test_fallback_is_not_priced_and_count_is_multiplied():
    steps = [
        _step("海报", "generate_image", POSTER, prompt="p", count=4),
        {"text": "备用", "tool": "generate_image", "model": "acme/backup", "fallback": True,
         "arguments": {"prompt": "nope"}},
        _step("视频", "generate_video", VIDEO, prompt="v", fallback_model="acme/backup"),
        {"text": "排版", "tool": "add_text", "model": "", "arguments": {}},
    ]
    quote, seen = await _quote(steps, threshold=0.5, prices={POSTER: 0.04, VIDEO: 0.10, "acme/backup": 9})
    assert quote is not None and quote.n == 2
    assert quote.lines[0].price == "16 积分"  # 0.04 x 4, the amount that is summed
    assert quote.lines[1].price == "10 积分"
    assert quote.total == 0.26 and quote.ask is False
    assert [m for m, _ in seen] == [POSTER, VIDEO]
    assert len(quote.keys) == 2


async def test_one_paid_step_is_not_a_plan_quote():
    quote, _ = await _quote([_step("海报", "generate_image", POSTER, prompt="p")])
    assert quote is None


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


def _provider():
    return LocalLlmProvider(base_url=lambda: "http://x/v1")


async def _run(monkeypatch, responses, *, lang="zh", quote=None, confirm="start", user_text="做两张"):
    provider = _provider()
    mcp = []
    quoted = []
    confirms = []

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            return responses.pop(0)
        return {"result": {"tools": [{"name": "generate_image"}, {"name": "update_plan"}, {"name": "server_info"}]}}

    async def fake_call(session, endpoint, name, arguments):
        mcp.append((name, dict(arguments)))
        return f"ok {name}", []

    async def fake_quote(steps, lang_):
        quoted.append(steps)
        return quote

    async def fake_confirm(spec, turn, handle, **_kw):
        confirms.append(spec)
        return confirm

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_quote_steps", fake_quote)

    async def free_price(model, inputs):  # #732: per-call pricing now fails closed; no WaveSpeed key here
        return 0.0

    monkeypatch.setattr(provider, "_price_one", free_price)
    monkeypatch.setattr(provider, "_confirm_plan", fake_confirm)
    events = []

    async def emit(ev: BotEvent):
        if not ev.t.startswith("run_"):  # #391 run_budget / run_stop cards are not part of this contract
            events.append(ev)

    result = await provider.send(
        TurnRequest(chat_id="c", user_text=user_text, lang=lang, mcp_endpoint="http://x/mcp", model="m"),
        emit, TurnHandle())
    return result, events, mcp, quoted, confirms


def _over():
    from ComfyArt.bot.plan_quote import Line, Quote
    line = Line("生成海报 · poster-xl", "40 积分", 0.40, False, False, canon_key("generate_image", {"prompt": "a"}, POSTER))
    line2 = Line("生成视频 · clip-hd", "60 积分", 0.60, False, False, canon_key("generate_video", {"prompt": "b", "duration": 5}, VIDEO))
    return Quote(
        lines=[line, line2], total=1.0, n=2, ask=True, lang="zh",
        prompt="这个任务共 2 步，预计约 $1.00，超过了你设置的 $0.50 确认线。确定开始吗？",
        total_label="总价", total_text="100 积分", keys=[line.key, line2.key], cancel_text=CANCEL_TEXT["zh"],
    )


async def test_cancel_says_the_exact_sentence_and_charges_nothing(monkeypatch):
    steps = {"steps": [
        {"text": "生成海报", "tool": "generate_image", "model": POSTER, "arguments": {"prompt": "a"}},
        {"text": "生成视频", "tool": "generate_video", "model": VIDEO, "arguments": {"prompt": "b", "duration": 5}},
    ]}
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "quote_plan", steps)]}}]},
        {"choices": [{"message": {"content": "should not run", "tool_calls": []}}]},
    ]
    result, events, mcp, quoted, confirms = await _run(monkeypatch, responses, quote=_over(), confirm="cancel")
    assert mcp == []
    assert confirms and confirms[0]["kind"] == "plan_quote"
    assert [e.text for e in events if e.t == "delta"] == [CANCEL_TEXT["zh"]]
    assert result.error == ""
    row = next(e for e in events if e.t == "tool_result")
    assert row.detail == "cancelled" and row.text == CANCEL_TEXT["zh"]
    assert not any(e.t == "tool_use" and e.name == "generate_image" for e in events)


async def test_start_runs_the_quoted_calls_and_skips_a_second_ask(monkeypatch):
    img = {"prompt": "a", "model": POSTER}
    vid = {"prompt": "b", "duration": 5, "model": VIDEO}
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "quote_plan", {"steps": [
                {"text": "生成海报", "tool": "generate_image", "model": POSTER, "arguments": {"prompt": "a"}},
                {"text": "生成视频", "tool": "generate_video", "model": VIDEO, "arguments": {"prompt": "b", "duration": 5}},
            ]}),
            _tc(2, "generate_image", img),
            _tc(3, "generate_video", vid),
        ]}}]},
        {"choices": [{"message": {"content": "好了", "tool_calls": []}}]},
    ]
    result, events, mcp, _quoted, confirms = await _run(monkeypatch, responses, quote=_over(), confirm="start")
    assert [n for n, _ in mcp] == ["generate_image", "generate_video"]
    assert len(confirms) == 1
    assert result.error == "" and events[-1].text == "好了"
    quote_row = next(e for e in events if e.t == "tool_result" and e.name == "quote_plan")
    assert quote_row.text == '{"ok": true, "start": true}'
    assert "$" not in quote_row.text


async def test_under_threshold_does_not_ask_and_hides_prices(monkeypatch):
    from ComfyArt.bot.plan_quote import Line, Quote
    a = Line("a", "4 积分", 0.04, False, False, canon_key("generate_image", {"prompt": "a"}, ""))
    b = Line("b", "4 积分", 0.04, False, False, canon_key("generate_image", {"prompt": "b"}, ""))
    quiet = Quote(lines=[a, b], total=0.08, n=2, ask=False, lang="zh", prompt="unused",
                  total_label="总价", total_text="8 积分", keys=[a.key, b.key], cancel_text=CANCEL_TEXT["zh"])
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "generate_image", {"prompt": "a"}),
            _tc(2, "generate_image", {"prompt": "b"}),
        ]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]
    result, events, mcp, _q, confirms = await _run(monkeypatch, responses, quote=quiet)
    assert confirms == []
    assert [n for n, _ in mcp] == ["generate_image", "generate_image"]
    assert result.error == ""
    assert not any("$" in (e.text or "") for e in events)


async def test_one_paid_call_is_unchanged(monkeypatch):
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "generate_image", {"prompt": "a"})]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]
    result, events, mcp, quoted, confirms = await _run(monkeypatch, responses, quote=None)
    assert len(quoted) == 1 and confirms == []  # #418: quoted, but under the line -> no card
    assert mcp == [("generate_image", {"prompt": "a"})]
    assert result.error == "" and events[-1].text == "done"


async def test_a_plan_without_quote_plan_still_runs_each_step(monkeypatch):
    """#127: update_plan does not by itself block the next paid call. Per-step confirm stays."""
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "update_plan", {"steps": [
            {"text": "海报", "status": "pending"}, {"text": "视频", "status": "pending"}]})]}}]},
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(2, "generate_image", {"prompt": "a"})]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]
    result, events, mcp, quoted, confirms = await _run(monkeypatch, responses, quote=None)
    assert len(quoted) == 1 and confirms == []  # #418: quoted, under the line -> no card
    assert [n for n, _ in mcp] == ["update_plan", "generate_image"]
    assert result.error == "" and events[-1].text == "done"


async def test_after_start_an_unquoted_paid_call_is_refused(monkeypatch):
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "quote_plan", {"steps": [
            {"text": "生成海报", "tool": "generate_image", "model": POSTER, "arguments": {"prompt": "a"}},
            {"text": "生成视频", "tool": "generate_video", "model": VIDEO, "arguments": {"prompt": "b"}},
        ]})]}}]},
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(2, "generate_image", {"prompt": "a", "model": POSTER})]}}]},
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(3, "generate_image", {"prompt": "extra"})]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]
    result, events, mcp, _q, confirms = await _run(monkeypatch, responses, quote=_over(), confirm="start")
    assert confirms and confirms[0]["kind"] == "plan_quote" and len(confirms) == 1
    assert mcp == [("generate_image", {"prompt": "a", "model": POSTER})]
    err = next(e for e in events if e.t == "tool_result" and e.is_error)
    assert "quote_plan" in err.text and CANCEL_TEXT["zh"] not in err.text
    assert result.error == ""


async def test_cancel_sentence_marks_the_step_cancelled():
    assert _CANCEL_RE.search(CANCEL_TEXT["zh"])
    assert _CANCEL_RE.search(CANCEL_TEXT["en"])
    assert not _CANCEL_RE.search("这次调用没有执行。")


def test_prompt_stays_off_the_external_guide_and_on_the_builtin_agent():
    assert "quote_plan" not in AGENT_GUIDE
    assert _PLAN_QUOTE_RULE in _SYSTEM_PROMPT
    assert "quote_plan" in _PLAN_QUOTE_RULE


def test_card_reuses_the_confirm_component_and_skips_the_second_dialog():
    confirm = (ROOT / "src/ui/Confirm.tsx").read_text()
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    comfy = (ROOT / "src/comfy.ts").read_text()
    jobs = (ROOT / "src/jobs.ts").read_text()
    commands = (ROOT / "src/botCommands.ts").read_text()
    bot = (ROOT / "src/bot.ts").read_text()
    step = (ROOT / "src/ui/stepState.ts").read_text()
    css = "\n".join((ROOT / "src/styles").glob("*.css") and [p.read_text() for p in (ROOT / "src/styles").glob("*.css")])
    assert "ca-panel__secondary" in confirm and "ca-panel__primary" in confirm
    assert "ca-panel__val" in confirm and "ca-keys__row" in confirm and "ca-plan__head" in confirm
    assert "ca-quote" not in css and "plan_quote" not in css
    assert "kind === 'plan_quote'" in chat and "confirmAtom.set" in chat
    assert "setAgentPlanConfirmed(true)" in chat and "t('jobs.confirmTitle')" in chat
    assert "planBypassNow" in comfy and "inputs.confirmed = true" in comfy
    assert "const skipConfirm = planBypassNow()" in jobs
    assert "queuePrompt(graph, opts.runOn, skipConfirm)" in jobs
    assert "pushAgentCommand()" in commands and "popAgentCommand()" in commands
    assert "setAgentPlanConfirmed(false)" in bot
    assert "已取消，没有扣费。" in step and "Cancelled\\. Nothing was charged\\." in step
    # the per-job dialog keeps its own copy; the plan card does not reuse 继续生成
    assert "jobs.confirmOk" not in chat
