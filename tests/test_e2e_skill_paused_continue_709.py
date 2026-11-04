"""#709 precondition (tech lead, option a): a run that pauses on budget (paused / budget:exhausted) or on a
stuck:* stop shows WHY in plain words (never an internal code) with a PRIMARY 继续生成; it resumes the SAME run (no restart) and can reach done.
Scripted LLM + MCP (no paid call); the card is the backend's real run_stop block, rendered by the real
RunStop in Chromium (tests/js/runstop harness). SHOT_DIR=<dir> writes the docs/qa/709 screenshot."""
import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.bot import agent_loop, run_budget

from test_agent_budget_391 import Clock, Rig, calls, card, reply, stop_of, store  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")
SHOT = os.environ.get("SHOT_DIR")


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = tmp_path_factory.mktemp("paused709")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/runstop/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(f"<!doctype html><meta charset=utf-8><style>{css}</style><div id=root></div>"
        "<script>window.WebSocket = class { constructor() {} send() {} close() {} addEventListener() {} }</script>"
        "<script src=app.js></script>")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browsers not installed
            pytest.skip(f"no chromium: {e}")
        pg = b.new_page(viewport={"width": 412, "height": 360}, device_scale_factor=2)
        pg.goto((d / "index.html").as_uri())
        pg.wait_for_function("window.__ready === true")
        yield pg
        b.close()


CODES = re.compile(r"budget:|stuck:|hard_cap|exhausted|_limit|non_retryable|self_check|timeout|no_progress|same_tool")


def ui_continue(page, block, reason_text, shot=None, title=None):
    """Render the real card: plain reason + PRIMARY 继续生成; clicking it POSTs /runs/<same id>/continue."""
    page.evaluate("([b]) => { window.__calls = []; window.__render(b, 'zh', 'light') }", [[block]])
    page.wait_for_selector(".ca-run")
    r = page.locator(".ca-run").first
    text = r.inner_text()
    assert reason_text in text and text.count(reason_text) == 1
    if title:
        assert r.locator(".ca-run__title").first.inner_text().strip() == title, text
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    assert len(lines) == len(set(lines)), lines             # no duplicated line
    for gone in ("预算用完了", "预算到了，要继续吗？", "换个说法再试", "卡住了"):
        assert gone not in text, text
    assert not CODES.search(text), text                     # no internal code in visible text
    assert [b.inner_text() for b in r.locator("button:not(.ca-run__details button)").all()
            if b.inner_text() in ("先到这里", "继续生成", "换个说法再试", "继续")] == ["先到这里", "继续生成"], text
    if shot:
        Path(shot).parent.mkdir(parents=True, exist_ok=True)
        r.screenshot(path=shot)
    prim = r.locator("button.ca-panel__primary")
    assert prim.count() == 1 and prim.inner_text() == "继续生成" and prim.is_visible()
    prim.click()
    page.wait_for_function("window.__calls.length > 0")
    c = page.evaluate("window.__calls")
    assert [(x["method"], x["url"]) for x in c] == [("POST", f"/api/comfyart/bot/runs/{block['run_id']}/continue")]
    return r, c[0]["url"].split("/runs/")[1].split("/")[0]


def resume_to_done(monkeypatch, store, rid):
    r2 = Rig(monkeypatch, [calls(("add_text", {"text": "end"})), reply("好了")], store=store)
    res2, _ = arun(r2.send("继续生成", resume=rid))
    assert res2.run["run_id"] == rid                       # same run, not a restart
    assert stop_of(res2)["reason"] == "done", stop_of(res2)
    assert store.get_run(rid)["status"] == "done" and len(store.list_runs(chat_id="c")) == 1
    return r2


def images(store, rid):
    return [b["id"] for b in store.get_run(rid)["state"].get("blocks") or [] if b.get("type") == "tool_use"
            and b.get("name") == "generate_image"]


def test_budget_exhausted_plain_reason_primary_continue_keeps_images(monkeypatch, store, page):
    clk = Clock()

    def mcp(name, a, i):
        clk.t += 400
        return json.dumps({"id": f"shape:img{i}"})
    gen = ("generate_image", {"prompt": "cat", "model": "m"})
    r = Rig(monkeypatch, lambda m, n: calls(gen), store=store, clock=clk, mcp=mcp, prices={"generate_image": 0.01},
            policy={"wall_time_s": 600})
    res, ev = arun(r.send("画猫", goal=""))
    s, rid = stop_of(res), res.run["run_id"]
    assert (s["reason"], s["sub"], s["dimension"]) == ("budget", "exhausted", "time")
    assert store.get_run(rid)["status"] == "paused"
    made = images(store, rid)
    assert made and len(made) == len(r.paid_mcp())                      # images made before the pause …
    assert not [c for c in r.mcp if c[0].startswith("delete")]          # … and nothing removed them from the canvas
    art = list(store.get_run(rid)["state"]["artifacts"])
    b = card(ev)
    assert b["can_continue"] and b["run_id"] == rid
    mins = max(1, round(res.run["log"]["wall_s"] / 60))
    want = f"已运行 {mins} 分钟，达到单次时长上限，已生成的图会保留。"
    shot = str(Path(SHOT) / "paused_budget_time_zh.png") if SHOT else None
    card_el, got = ui_continue(page, b, want, shot, title="已自动暂停")
    assert got == rid
    assert card_el.locator("button.ca-panel__secondary").inner_text() == "先到这里"
    assert len(images(store, rid)) == len(made) and store.get_run(rid)["state"]["artifacts"] == art  # unchanged while paused
    r2 = resume_to_done(monkeypatch, store, rid)
    assert set(art) <= set(store.get_run(rid)["state"]["artifacts"])   # resume keeps them
    assert not [c for c in r2.mcp if c[0].startswith("delete")]


def test_stuck_plain_reason_and_primary_continue_resumes_same_run(monkeypatch, store, page):
    r = Rig(monkeypatch, lambda m, n: calls(("generate_image", {"prompt": f"v{n}"})), store=store,
            mcp=lambda name, a, i: f"queued attempt {i}", prices={"generate_image": 0.01})
    res, ev = arun(r.send("Banner", goal=""))
    s, rid = stop_of(res), res.run["run_id"]
    assert s["reason"] == "stuck" and store.get_run(rid)["status"] == "paused"
    b = card(ev)
    assert s["sub"] == "same_tool", s
    want = "连续重复同一步，已停下。"
    assert b["copy"]["zh"]["body"] == want and "reason" not in b["copy"]["zh"] and b["copy"]["action"] == "continue"
    shot = str(Path(SHOT) / "paused_stuck_same_tool_zh.png") if SHOT else None
    assert ui_continue(page, b, want, shot, title="已暂停")[1] == rid
    resume_to_done(monkeypatch, store, rid)


def test_stuck_timeout_plain_reason_and_primary_continue_resumes_same_run(monkeypatch, store, page):
    clk = Clock()   # the run's own (monotonic-style) clock drives wait_timeout, not time.time()

    def mcp(name, a, i):
        clk.t += 330
        return json.dumps({"status": "pending"})
    r = Rig(monkeypatch, lambda m, n: calls(("wait_generation", {"ids": ["job1"]})), store=store, clock=clk, mcp=mcp,
            policy={"wall_time_s": 10**6})
    res, ev = arun(r.send("加字", goal=""))
    s, rid = stop_of(res), res.run["run_id"]
    assert (s["reason"], s["sub"]) == ("stuck", "timeout") and store.get_run(rid)["status"] == "paused"
    shot = str(Path(SHOT) / "paused_wait_timeout_zh.png") if SHOT else None
    assert ui_continue(page, card(ev), "等待生成结果超过 11 分钟。", shot, title="已暂停")[1] == rid
    resume_to_done(monkeypatch, store, rid)


def test_hard_cap_unified_title_plain_body_primary_continue(monkeypatch, store, page):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 3},
            store=store)
    res, ev = arun(r.send("加字", goal=""))
    s, rid = stop_of(res), res.run["run_id"]
    assert s["reason"] == "hard_cap" and store.get_run(rid)["status"] == "paused"
    b = card(ev)
    want = "已达到单次步数上限，已生成的图会保留。"
    assert (b["copy"]["zh"]["title"], b["copy"]["zh"]["body"]) == ("已自动暂停", want)
    assert (b["copy"]["zh"]["primary"], b["copy"]["zh"]["secondary"]) == ("继续生成", "先到这里")
    shot = str(Path(SHOT) / "paused_hard_cap_zh.png") if SHOT else None
    card_el, got = ui_continue(page, b, want, shot, title="已自动暂停")
    assert got == rid and card_el.locator("button.ca-panel__secondary").inner_text() == "先到这里"
    resume_to_done(monkeypatch, store, rid)


def arun(coro):
    """The scripted backend runs on its own loop in a worker thread (sync Playwright owns this thread's loop)."""
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(asyncio.run, coro).result()
