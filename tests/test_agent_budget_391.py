"""#391 budget/progress driven agent loop. Everything is mocked: no real LLM, no paid call."""
from __future__ import annotations

import asyncio
import json
import logging

import aiohttp
import pytest

from ComfyArt.bot import agent_loop, local_llm
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import (
    SUB_REASONS, BudgetLimits, ProgressTracker, RunBudget, StepObservation, StopReason, confirm_policy,
    content_tokens, messages_tokens, resolve_policy,
)
from ComfyArt.bot.run_store import set_run_store

IMG = "data:image/png;base64," + "A" * 400


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args)}}


def calls(*items):
    return {"choices": [{"message": {"content": "", "tool_calls": [_tc(i, n, a) for i, (n, a) in enumerate(items)]}}]}


def reply(text):
    return {"choices": [{"message": {"content": text, "tool_calls": []}}]}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Crash(BaseException):
    """A process death in the middle of a run (not caught by the loop)."""


@pytest.fixture
def store():
    from ComfyArt.api.run_store_sqlite import SqliteRunStore
    s = SqliteRunStore()
    set_run_store(s)
    yield s
    set_run_store(None)


class Rig:
    """One provider with scripted LLM / MCP. `script`: list of responses or a callable(messages, n)."""

    def __init__(self, monkeypatch, script, *, policy=None, store=None, window=32_000, prices=None,
                 confirm=True, mcp=None, clock=None, gate=None):
        self.p = LocalLlmProvider(base_url=lambda: "http://x/v1")
        self.script = script
        self.n = 0
        self.mcp: list = []
        self.requests: list = []
        self.confirms: list = []
        self.store = store
        self.clock = clock or Clock()
        pol = resolve_policy(user=policy or {}, env={})
        mon = monkeypatch
        mon.setattr(self.p, "_run_policy", lambda: pol)
        mon.setattr(self.p, "_run_store", lambda: store)
        mon.setattr(self.p, "_run_clock", self.clock)
        mon.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))

        async def ctx_window(session, model):
            return window
        mon.setattr(self.p, "_context_window", ctx_window)

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                if gate is not None:
                    await gate.wait()
                self.requests.append(json_body["messages"])
                s = self.script
                r = s(json_body["messages"], self.n) if callable(s) else s[self.n]
                self.n += 1
                if isinstance(r, BaseException):
                    raise r
                return r
            return {"result": {"tools": [{"name": t} for t in (
                "generate_image", "get_canvas", "add_text", "wait_generation", "update_shapes")]}}
        mon.setattr(self.p, "_request_json", fake_request)

        async def fake_call(session, endpoint, name, arguments):
            self.mcp.append((name, dict(arguments)))
            if mcp:
                out = mcp(name, arguments, len(self.mcp))
                if isinstance(out, BaseException):
                    raise out
                return out if isinstance(out, tuple) else (out, [])
            return json.dumps({"id": f"shape:{len(self.mcp)}"}), []
        mon.setattr(self.p, "_mcp_call_tool", fake_call)

        async def price(name, args):
            return (prices or {}).get(name)
        mon.setattr(self.p, "_price_call", price)

        async def ask(turn, handle, lang, name, p, left):
            self.confirms.append((name, p, left))
            return confirm
        mon.setattr(self.p, "_confirm_over_quote", ask)

    async def send(self, text="画一张猫", *, goal=None, mode="interactive", resume=None, lease=None, handle=None):
        events: list[BotEvent] = []

        async def emit(ev):
            events.append(ev)
        res = await self.p.send(TurnRequest(chat_id="c", user_text=text, lang="zh", mcp_endpoint="http://x/mcp",
                                            model="m", goal_text=text if goal is None else goal, run_mode=mode,
                                            resume_run_id=resume, lease_owner=lease), emit, handle or TurnHandle())
        return res, events

    def paid_mcp(self):
        return [c for c in self.mcp if c[0] == "generate_image"]


def expire_leases(store, by=3600):
    """Advance the store's clock past every lease (the crashed process can no longer renew)."""
    import time as _t
    store._clock = lambda: _t.time() + by


def stop_of(res):
    return res.run["stop"]


def card(events):
    return [e for e in events if e.t == "run_stop"][-1].input


# ------------------------------------------------------------------ units


def test_policy_layers_defaults_and_legacy_env(caplog):
    p = resolve_policy(env={})
    assert (p["hard_cap_steps"], p["token_window_multiple"], p["wall_time_s"], p["stall_steps"]) == (300, 40, 900, 4)
    assert p.enabled
    assert resolve_policy(workspace={"hard_cap_steps": 50}, user={"hard_cap_steps": 70}, env={})["hard_cap_steps"] == 70
    assert resolve_policy(user={"hard_cap_steps": 99999}, env={})["hard_cap_steps"] == 1000  # clamped
    assert resolve_policy(plan={"hard_cap_steps": 20}, user={"hard_cap_steps": 70}, env={})["hard_cap_steps"] == 20
    with caplog.at_level(logging.WARNING):
        assert resolve_policy(env={"COMFYART_AGENT_MAX_STEPS": "80"})["hard_cap_steps"] == 80
    assert "deprecated" in caplog.text
    assert not resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"}).enabled


def test_stop_reasons_and_sub_reasons_are_fixed():
    assert {r.value for r in StopReason} == {"done", "budget", "stuck", "hard_cap", "user_stop", "error", "awaiting_confirm"}
    assert set(SUB_REASONS[StopReason.AWAITING_CONFIRM]) == {"not_approved"}
    assert set(SUB_REASONS[StopReason.STUCK]) >= {"no_progress", "repeat", "tool_error", "readonly_limit"}
    assert set(SUB_REASONS[StopReason.BUDGET]) == {"paused", "exhausted", "unattended_skipped"}
    assert "self_check_failed" in SUB_REASONS[StopReason.STUCK]
    assert set(SUB_REASONS[StopReason.USER_STOP]) == {"", "quote_declined"}
    assert confirm_policy("unattended", "soft_limit") == "skip" and confirm_policy("interactive", "soft_limit") != "skip"


def test_images_count_as_tokens():
    plain = content_tokens([{"type": "text", "text": "hi"}], 1500)
    with_img = content_tokens([{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": IMG}}], 1500)
    assert with_img - plain >= 1500


def test_soft_pause_only_when_projection_exceeds_and_once():
    clk = Clock()
    b = RunBudget(BudgetLimits(tokens=1000, credits=5, wall_s=900, hard_steps=300), k=5, clock=clk)
    b.charge_tokens(100); b.charge_credits(1.0); b.end_step()
    assert b.should_soft_pause(remaining_steps=3) is None          # 1 + 3*1 <= 5: not exceeded
    assert b.should_soft_pause(remaining_steps=12) == "credits"    # 1 + 12*1 > 5: exceeded
    b.soft_used = True
    assert b.should_soft_pause(remaining_steps=12) is None         # at most once per run


def test_soft_pause_only_interrupts_for_money():
    """tokens / time projections never interrupt the user (they run to the hard limit)."""
    b = RunBudget(BudgetLimits(tokens=1000, credits=5, wall_s=900, hard_steps=300), k=5, clock=Clock())
    b.charge_tokens(100); b.end_step()
    assert b.should_soft_pause(remaining_steps=50) is None         # 100 + 50*100 tokens > 1000, no money


def test_tracker_readonly_whitelist_and_stall():
    t = ProgressTracker(4, 8, 3, 3)
    for i in range(8):  # 8 read-only steps in a row are fine
        assert t.observe(i, [StepObservation("get_canvas", f"p{i}", '{"shapes": []}')]) is None
    assert t.observe(8, [StepObservation("get_canvas", "p9", "x")]) == "readonly_limit"
    t = ProgressTracker(4, 8, 3, 3)
    subs = [t.observe(i, [StepObservation("add_text", f"a{i}", "ok")]) for i in range(4)]
    assert subs == [None, None, None, "no_progress"]
    t = ProgressTracker(4, 8, 3, 3)
    subs = [t.observe(i, [StepObservation("add_text", f"a{i}", "boom", failed=True)]) for i in range(3)]
    assert subs[-1] == "tool_error"


# ------------------------------------------------------------------ the loop: every stop reason


async def test_done_ends_run_with_card(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "a"})), reply("好了")], store=store)
    res, ev = await r.send("加一行字")
    assert stop_of(res)["reason"] == "done" and res.error == ""
    assert card(ev)["stop"]["reason"] == "done"
    assert store.get_run(res.run["run_id"])["status"] == "done"
    logs = store.list_run_logs(res.run["run_id"])
    assert logs[-1]["stop_code"] == "done" and logs[-1]["project_id"] == "local"


async def test_hard_cap_stops_and_says_so(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 5},
            store=store)
    res, ev = await r.send("加很多字")
    c = card(ev)
    assert stop_of(res)["reason"] == "hard_cap" and res.error  # announced, not silent
    # no parsable goal and only free steps: no ratio and no credits estimate (EL 6441143985)
    assert c["copy"]["zh"]["title"] == "已自动暂停" and c["copy"]["zh"]["body"] == "已达到单次步数上限，已生成的图会保留。"
    assert (c["copy"]["zh"]["primary"], c["copy"]["zh"]["secondary"]) == ("继续生成", "先到这里")   # no estimate
    assert "5 步" not in res.error and "上限" not in res.error  # the cap number is never shown
    assert len(r.mcp) == 5 and c["can_continue"]


async def test_default_hard_cap_is_not_80(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})) if n < 120 else reply("120 条都加好了"),
            store=store)
    res, _ = await r.send("把 120 条标语加到画布上")
    assert stop_of(res)["reason"] == "done" and len([c for c in r.mcp if c[0] == "add_text"]) == 120


async def test_stuck_no_progress_after_one_nudge(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store,
            mcp=lambda name, a, i: "ok")
    res, _ = await r.send("加字")
    assert stop_of(res) ["reason"] == "stuck" and stop_of(res)["sub"] == "no_progress"
    nudges = [m for m in r.requests[-1] if m["role"] == "user" and "换一个思路" in str(m.get("content"))]
    assert len(nudges) == 1                       # "try another approach" at most once
    assert len(r.mcp) == 8                        # 4 unchanged -> nudge -> 4 unchanged -> stop


async def test_stuck_repeat(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": "same"})), store=store)
    res, _ = await r.send("加字")
    assert stop_of(res)["sub"] == "repeat"


async def test_stuck_tool_error_after_3_failures(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store,
            mcp=lambda name, a, i: aiohttp.ClientConnectionError("down"))
    res, _ = await r.send("加字")
    assert stop_of(res)["sub"] == "tool_error" and len(r.mcp) == 6  # 3 -> nudge -> 3


async def test_readonly_steps_are_not_no_progress(monkeypatch, store):
    """8 read-only steps, then real work: never stuck; the same reads in a row are not 'no progress'."""
    def script(m, n):
        if n < 8:
            return calls(("get_canvas", {"page": f"p{n}"}))
        if n < 12:
            return calls(("add_text", {"text": f"x{n}"}))
        return reply("好了")
    r = Rig(monkeypatch, script, store=store, mcp=lambda name, a, i: '{"shapes": []}' if name == "get_canvas"
            else json.dumps({"id": f"s{i}"}))
    res, _ = await r.send("看看画布再加字")
    assert stop_of(res)["reason"] == "done"


async def test_readonly_limit(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("get_canvas", {"page": f"p{n}"})), store=store)
    res, _ = await r.send("检查所有页面")
    assert stop_of(res)["sub"] == "readonly_limit" and len(r.mcp) == 18


async def test_user_stop(monkeypatch, store):
    h = TurnHandle()

    def mcp(name, a, i):
        h.stop_requested = True
        return json.dumps({"id": f"s{i}"})
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store, mcp=mcp)
    res, _ = await r.send("加字", handle=h)
    assert stop_of(res)["reason"] == "user_stop" and res.aborted and len(r.mcp) == 1


async def test_error_llm_retry_exhausted(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: local_llm.LlmHttpError(500, "boom"), store=store)
    res, _ = await r.send("加字")
    assert stop_of(res)["reason"] == "error" and stop_of(res)["sub"] == "llm_retry_exhausted"
    assert r.n == 3  # the LLM call is retried twice, not forever


async def test_soft_limit_exceeded_pauses_interactive(monkeypatch, store):
    """Money projection over budget: pause once, card says done / remaining / estimated cost."""
    r = Rig(monkeypatch, lambda m, n: calls(("generate_image", {"prompt": f"p{n}", "model": "m"})), store=store,
            policy={"credits_usd": 1.0}, prices={"generate_image": 0.4},
            mcp=lambda name, a, i: json.dumps({"id": f"shape:s{i}"}))
    res, ev = await r.send("画 4 张猫")
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("budget", "paused") and s["dimension"] == "credits"
    c = card(ev)
    assert c["can_continue"] and c["estimate"]["credits"] > 0 and c["remaining"]["deliverables"] >= 1
    zh = c["copy"]["zh"]
    assert zh["title"] == "已自动暂停" and zh["primary"] == "继续生成" and zh["secondary"] == "先到这里"
    assert zh["body"].startswith("已用 ") and "达到单次积分上限。已生成的图保留在画布上。继续大约需要" in zh["body"]
    assert "预算" not in zh["body"] and "reason" not in zh
    assert store.get_run(res.run["run_id"])["status"] == "paused"


async def test_tokens_budget_exhaustion_stops_without_asking(monkeypatch, store):
    big = "x" * 8000
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store, window=2000,
            policy={"token_window_multiple": 2}, mcp=lambda name, a, i: json.dumps({"id": f"s{i}", "t": big}))
    res, ev = await r.send("画 4 张猫")
    s = stop_of(res)
    assert (s["reason"], s["sub"], s["dimension"]) == ("budget", "exhausted", "tokens")
    assert r.confirms == [] and "max_steps" not in json.dumps(s)


async def test_credits_budget_exhaustion(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("generate_image", {"prompt": f"p{n}", "model": "m"})), store=store,
            policy={"credits_usd": 1.0, "soft_fraction": 1.0}, prices={"generate_image": 0.5},
            mcp=lambda name, a, i: json.dumps({"id": f"shape:s{i}"}))
    r.p  # noqa: B018
    res, _ = await r.send("做一下", goal="")
    s = stop_of(res)
    assert (s["reason"], s["dimension"]) == ("budget", "credits") and "max_steps" not in json.dumps(s)
    assert len(r.paid_mcp()) == 2 and res.run["log"]["credits_usd"] == pytest.approx(1.0)


async def test_soft_limit_not_exceeded_runs_through(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "a"})), calls(("add_text", {"text": "b"})), reply("好了")],
            store=store)
    res, ev = await r.send("加两行字")
    assert stop_of(res)["reason"] == "done"
    assert not [e for e in ev if e.t == "run_stop" and e.input["stop"]["sub"] == "paused"]


async def test_unattended_never_waits_and_charges_nothing_over_budget(monkeypatch, store):
    big = "x" * 8000
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"p{n}"})),
            store=store, window=2000, policy={"token_window_multiple": 2},
            mcp=lambda name, a, i: json.dumps({"id": f"s{i}", "t": big}))
    res, ev = await r.send("画 4 张猫", mode="unattended")
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("budget", "unattended_skipped")
    assert r.confirms == []                                  # never asked
    assert len([e for e in ev if e.t == "notify"]) == 1      # exactly one notification
    assert r.paid_mcp() == [] and res.run["log"]["paid_calls"] == 0
    assert store.get_run(res.run["run_id"])["status"] == "paused"  # checkpoint kept


async def test_unattended_paid_over_quote_is_skipped_not_charged(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("generate_image", {"prompt": "a", "model": "m"}))], store=store,
            policy={"credits_usd": 1.0}, prices={"generate_image": 1.5})
    res, _ = await r.send("画一张猫", mode="unattended")
    assert stop_of(res)["sub"] == "unattended_skipped" and r.confirms == []
    assert r.paid_mcp() == [] and res.run["log"]["credits_usd"] == 0
    assert [e for e in store.list_usage_events(run_id=res.run["run_id"]) if e["kind"] == "paid_call"] == []


async def test_paid_over_quote_needs_confirm_never_auto_continue(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("generate_image", {"prompt": "a", "model": "m"}))], store=store,
            policy={"credits_usd": 1.0}, prices={"generate_image": 1.5}, confirm=False)
    res, _ = await r.send("画一张猫")
    assert stop_of(res)["reason"] == "user_stop" and stop_of(res)["sub"] == "quote_declined"
    assert not res.error  # cancelled by the user: not shown as an error
    assert len(r.confirms) == 1 and r.paid_mcp() == []
    assert res.run["log"]["credits_usd"] == 0


async def test_paid_confirm_raises_limit_by_exactly_the_quote(monkeypatch, store):
    script = [calls(("generate_image", {"prompt": "a", "model": "m"})), reply("好了")]
    r = Rig(monkeypatch, script, store=store, policy={"credits_usd": 1.0}, prices={"generate_image": 1.5})
    res, _ = await r.send("画一张猫")
    st = store.get_run(res.run["run_id"])["state"]["budget"]
    assert len(r.confirms) == 1 and len(r.paid_mcp()) == 1
    assert st["limits"]["credits"] == pytest.approx(1.5) and st["used"]["credits"] == pytest.approx(1.5)
    paid = [e for e in store.list_usage_events(run_id=res.run["run_id"]) if e["kind"] == "paid_call"]
    assert [e["amount_usd"] for e in paid] == [1.5]          # every paid call writes a usage event
    assert (paid[0]["owner_id"], paid[0]["workspace_id"]) == ("local", "local") and paid[0]["reason"]
    assert res.run["log"]["credits_usd"] == pytest.approx(1.5)  # paid calls count toward credits


async def test_budget_time_dimension(monkeypatch, store):
    clk = Clock()

    def mcp(name, a, i):
        clk.t += 400
        return json.dumps({"id": f"s{i}"})
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store, clock=clk, mcp=mcp,
            policy={"wall_time_s": 600})
    res, _ = await r.send("加字", mode="unattended")
    s = stop_of(res)
    assert s["reason"] == "budget" and s["dimension"] == "time"


async def test_long_runs_never_overflow_the_window(monkeypatch, store):
    """150 and 200 steps, each with a screenshot: the request stays inside the real window."""
    window = 16_000
    for steps in (150, 200):
        r = Rig(monkeypatch, lambda m, n, steps=steps: calls(("add_text", {"text": f"x{n}"})) if n < steps
                else reply("好了"), store=store, window=window, policy={"token_window_multiple": 200},
                mcp=lambda name, a, i: (json.dumps({"id": f"s{i}", "note": "y" * 600}), [IMG]))
        res, ev = await r.send("把标语逐条加到画布上")
        assert stop_of(res)["reason"] == "done", stop_of(res)
        peak = max(messages_tokens(m, 1500) for m in r.requests)
        assert peak <= window, peak
        assert res.run["log"]["compressions"] > 0
        assert res.run["log"]["tokens"] > steps * 1500  # images are charged


async def test_defaults_pass_single_batch_long(monkeypatch, store):
    single = [calls(("generate_image", {"prompt": "a"})), calls(("wait_generation", {"ids": ["j1"]})), reply("好了")]
    batch = [calls(("generate_image", {"prompt": f"a{i}"})) for i in range(4)] + [reply("好了")]
    long = [calls(("add_text", {"text": f"x{i}"})) for i in range(60)] + [reply("好了")]
    for script in (single, batch, long):
        r = Rig(monkeypatch, script, store=store)
        res, _ = await r.send("做一下")  # no deliverable count: just the budget defaults
        assert stop_of(res)["reason"] == "done", stop_of(res)


# ------------------------------------------------------------------ checkpoint / resume / lease


async def test_checkpoint_written_every_step(monkeypatch, store):
    seen = []

    def mcp(name, a, i):
        runs = store.list_runs(chat_id="c")
        seen.append(runs[-1]["step"] if runs else None)
        return json.dumps({"id": f"s{i}"})
    r = Rig(monkeypatch, [calls(("add_text", {"text": f"x{i}"})) for i in range(3)] + [reply("好了")],
            store=store, mcp=mcp)
    await r.send("加字")
    assert seen == [0, 1, 2]  # the DB row advances each step (not only in memory)


async def test_restart_resume_is_idempotent_no_duplicate_paid(monkeypatch, store):
    cat = ("generate_image", {"prompt": "cat", "model": "m"})
    dog = ("generate_image", {"prompt": "dog", "model": "m"})
    # one step, two paid calls: the first finishes, the process dies inside the second (before the step checkpoint)
    r = Rig(monkeypatch, [calls(cat, dog)], store=store, prices={"generate_image": 0.5},
            mcp=lambda name, a, i: Crash() if a.get("prompt") == "dog" else json.dumps({"id": "shape:g1"}))
    with pytest.raises(Crash):
        await r.send("生成一下", goal="")
    (run,) = store.list_runs(chat_id="c")
    assert run["status"] == "running"
    assert store.mark_interrupted() == 0                       # lease still live: maybe another instance
    expire_leases(store)
    assert store.mark_interrupted() == 1                       # restart after the lease expired
    run = store.get_run(run["id"])
    assert (run["status"], run["status_detail"]) == ("paused", "interrupted")
    # resume: the crashed step's exact tool calls (same tool_call_id) are replayed: cat is reused, dog
    # (pending, outcome unknown) is not re-called
    r2 = Rig(monkeypatch, [reply("好了")], store=store, prices={"generate_image": 0.5})
    res, _ = await r2.send("", resume=run["id"])
    assert res.run, res.error
    assert stop_of(res)["reason"] == "done"
    assert len(r.paid_mcp()) == 2 and r2.paid_mcp() == []
    paid = [e for e in store.list_usage_events(run_id=run["id"]) if e["kind"] == "paid_call"]
    assert sorted(e["status"] for e in paid) == ["done", "pending"]
    # replayed without asking the model again: its first request already carries both results of the crashed step
    tool_msgs = [m for m in r2.requests[0] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and "shape:g1" in str(tool_msgs[0].get("content"))


async def test_crash_during_paid_call_never_recalls(monkeypatch, store):
    gen = ("generate_image", {"prompt": "cat", "model": "m"})
    r = Rig(monkeypatch, [calls(gen)], store=store, prices={"generate_image": 0.5},
            mcp=lambda name, a, i: Crash())
    with pytest.raises(Crash):
        await r.send("画一张猫")
    expire_leases(store)
    store.mark_interrupted()
    (run,) = store.list_runs(chat_id="c")
    r2 = Rig(monkeypatch, [reply("好了")], store=store, prices={"generate_image": 0.5})
    await r2.send("", resume=run["id"])
    assert r2.paid_mcp() == []  # pending marker was durable: no second paid call
    ev = [e for e in store.list_usage_events(run_id=run["id"]) if e["kind"] == "paid_call"]
    assert [e["status"] for e in ev] == ["pending"]  # written with the pending checkpoint, survived the crash


async def test_continue_resumes_without_redoing_steps(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 3},
            store=store)
    res, _ = await r.send("加字")
    assert stop_of(res)["reason"] == "hard_cap" and len(r.mcp) == 3
    rid = res.run["run_id"]
    r2 = Rig(monkeypatch, [calls(("add_text", {"text": "x3"})), reply("好了")], policy={"hard_cap_steps": 3},
             store=store)
    res2, _ = await r2.send("继续", resume=rid)
    assert stop_of(res2)["reason"] == "done"
    assert [a["text"] for _, a in r2.mcp] == ["x3"]           # only new work, nothing redone
    assert res2.run["log"]["steps"] == 5 and res2.run["run_id"] == rid
    # the model saw the earlier results (resumed from the checkpoint, not from scratch)
    assert sum(1 for m in r2.requests[0] if m["role"] == "tool") == 3


async def test_two_concurrent_continues_only_one_wins(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 2},
            store=store)
    res, _ = await r.send("加字")
    rid = res.run["run_id"]
    assert store.acquire_lease(rid, "A", 60) and not store.acquire_lease(rid, "B", 60)
    store.release_lease(rid, "A")
    gate = asyncio.Event()
    ra = Rig(monkeypatch, [calls(("add_text", {"text": "a"})), reply("好了")], store=store,
             policy={"hard_cap_steps": 2}, gate=gate)
    rb = Rig(monkeypatch, [calls(("add_text", {"text": "b"})), reply("好了")], store=store,
             policy={"hard_cap_steps": 2})

    async def second():
        await asyncio.sleep(0)
        try:
            return await rb.send("继续", resume=rid, lease="B")
        finally:
            gate.set()
    (a, _), (b, _) = await asyncio.gather(ra.send("继续", resume=rid, lease="A"), second())
    errs = [x.error for x in (a, b)]
    assert sum("already being continued" in e for e in errs) == 1
    assert len(ra.mcp) + len(rb.mcp) == 1


async def test_lease_expires_and_can_be_taken_over(store):
    from ComfyArt.api.run_store_sqlite import SqliteRunStore
    t = [0.0]
    s = SqliteRunStore(clock=lambda: t[0])
    s.create_run(run_id="r1", chat_id="c", message_id="", mode="interactive", goal="")
    assert s.acquire_lease("r1", "A", 10) and not s.acquire_lease("r1", "B", 10)
    t[0] = 11
    assert s.acquire_lease("r1", "B", 10)
    assert not s.renew_lease("r1", "A", 10)
    assert s.get_run("r1")["project_id"] == "local"


# ------------------------------------------------------------------ feature flag


async def test_flag_off_uses_legacy_loop(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "a"})), reply("好了")], store=store)
    monkeypatch.setattr(r.p, "_run_policy", lambda: resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"}))
    res, ev = await r.send("加字")
    assert res.run is None and not [e for e in ev if e.t.startswith("run_")]
    assert store.list_runs(chat_id="c") == []


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
