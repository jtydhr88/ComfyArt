"""#712 e2e: a mocked WaveSpeed run that completes with no image is marked failed with its cost, and the UI shows the
reason and the amount (zh light / en dark). Mock WaveSpeed only, $0. COMFYART_712_SHOTS=<dir> keeps the shots."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

import pytest

from ComfyArt.api import gen_ledger, wavespeed
from test_wavespeed import ws  # noqa: F401  (mocked WaveSpeed API)

ROOT = Path(__file__).resolve().parent.parent
apw = pytest.importorskip("playwright.async_api")
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install")
SHOT_DIR = Path(os.environ.get("COMFYART_712_SHOTS", str(ROOT / "tmp-712-shots")))
MODEL = "wavespeed-ai/minimax-h3/text-to-video"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("sf712")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/sf712/rolldown.config.mjs"],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0}}{css}</style>"
                                  f"<div id=root></div><script src=app.js></script>")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_712_charged_no_output_shows_reason_and_amount(ws, bundle, lang, theme):  # noqa: F811
    ws["no_outputs"] = True
    ws["prices"][MODEL] = 0.32
    ws["task_id"] = LONG_ID  # #715 design: realistic 32-hex WaveSpeed-like id, not task1
    task = await wavespeed.submit({"feature": "text_to_video", "model": MODEL, "prompt": "x", "duration": 5, "confirmed": True})
    hist = await wavespeed.poll(task)
    info = hist[f"ws:{task}"]["status"]["messages"][0][1]
    assert hist[f"ws:{task}"]["generation_succeeded"] is False
    fail = [f for f in gen_ledger.failures() if f["task_id"] == task][0]
    assert fail["cost_usd"] == pytest.approx(0.32)
    async with apw.async_playwright() as p:
        try:
            b = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        page = await b.new_page(viewport={"width": 560, "height": 300}, device_scale_factor=2)
        await page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
        qs = urlencode({"lang": lang, "theme": theme, "kind": info["ws_kind"], "charged": info["ws_charged"], "model": MODEL, "task": info["ws_task_id"]})
        await page.goto(f"{bundle}/index.html?{qs}")
        await page.wait_for_function("window.__ready")
        await page.wait_for_timeout(200)
        body = await page.locator("[data-testid=ws-failure]").inner_text()
        assert "$0.32" in body
        assert ((f"任务编号：{task}" if lang == "zh" else f"Task ID: {task}") in body)
        assert "WaveSpeed" not in body
        assert ("没有返回图片" in body) if lang == "zh" else ("returned no image" in body)
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        await page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"failure-cost-{lang}-{theme}.png"))
        await b.close()


async def _shot(bundle, lang, theme, kind, charged, name, task=None, code=None):
    async with apw.async_playwright() as p:
        try:
            b = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        page = await b.new_page(viewport={"width": 560, "height": 300}, device_scale_factor=2)
        await page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
        q = {"lang": lang, "theme": theme, "kind": kind, "model": MODEL}
        if charged is not None:
            q["charged"] = charged
        if task:
            q["task"] = task
        if code:
            q["code"] = code
        await page.goto(f"{bundle}/index.html?{urlencode(q)}")
        await page.wait_for_function("window.__ready")
        await page.wait_for_timeout(200)
        body = await page.locator("[data-testid=ws-failure]").inner_text()
        if task:  # #715 design: id never wraps mid-string, stays selectable, full id in title
            st = await page.evaluate("""() => [...document.querySelectorAll('.ca-md .ca-task-id')].map(c => {
                const s = getComputedStyle(c); return [c.textContent, c.title, s.whiteSpace, s.userSelect, c.getClientRects().length] })""")
            assert [x[0] for x in st].count(task) >= 1, st
            for txt, title, ws_, sel, rects in st:
                if txt == task:
                    assert title == task and ws_ == "nowrap" and sel != "none" and rects == 1, (txt, ws_, sel, rects)
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        await page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"{name}-{lang}-{theme}.png"))
        await b.close()
        return body


# #715 design: realistic ids (WaveSpeed ids are 32 hex); XLONG (86 chars) overflows a 360px card -> ellipsis, full id in title
LONG_ID = "8f3c2a9e4b1d4c7fa6e05b2d9c13f7a4"
XLONG_ID = "8f3c2a9e4b1d4c7fa6e05b2d9c13f7a4-0b6e91d3c5a84f27a1d9e3b7c2f05a68-retry-2-e4b1d4c7fa6e05b2d9"  # 86 chars


# (kind, charged, file stem, zh text, en text); amounts are the mock quote, None = amount unknown
CASES = [
    ("noTaskId", 0.32, "failure-notaskid", "没有拿到任务编号，无法取回结果", "No task ID came back"),
    ("noOutput", None, "failure-nooutput-noamount", "没有返回图片，可能已扣费。", "returned no image, and it may have been charged."),
    ("noTaskId", None, "failure-notaskid-noamount", "无法取回结果，可能已扣费。", "cannot be fetched, and it may have been charged."),
    ("timeout", 0.32, "failure-timeout", "任务超时，可能已扣费约 $0.32。重试前请注意可能重复扣费。", "may have been charged about $0.32. Retrying may charge again."),
    ("timeout", None, "failure-timeout-noamount", "任务超时，可能已扣费。重试前请注意可能重复扣费。", "may have been charged. Retrying may charge again."),
    ("unregisteredModel", None, "failure-unregistered", "所选模型暂不可用，未发送、未扣费", "isn't available right now. Nothing was sent or charged"),
]


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
@pytest.mark.parametrize("kind,charged,stem,zh,en", CASES)
async def test_712_failure_kinds_shown(ws, bundle, lang, theme, kind, charged, stem, zh, en):  # noqa: F811
    if kind == "noTaskId":  # the kind + amount come from the mocked backend
        ws["no_id"] = True
        if charged is not None:
            ws["prices"][MODEL] = charged
        with pytest.raises(wavespeed.WaveSpeedError) as e:
            await wavespeed.submit({"feature": "text_to_video", "model": MODEL, "prompt": "x", "duration": 5, "confirmed": True})
        assert e.value.kind == "noTaskId"
        charged = e.value.charged if charged is not None else None
    task = LONG_ID if kind in ("timeout", "noOutput") else None  # noTaskId has none
    body = await _shot(bundle, lang, theme, kind, charged, stem, task)
    if task:
        assert (f"\n任务编号：{task}（反馈或退款时请提供）" if lang == "zh" else f"\nTask ID: {task} (include it in feedback or refund requests)") in body  # own line, no stray space
    else:
        assert "任务编号：" not in body and "Task ID:" not in body
    assert (zh if lang == "zh" else en) in body and not re.search(r"wavespeed|kie|控制台|后台|console|dashboard|生成记录|历史记录|generation history", body, re.I)
    assert "$0.32" in body if charged is not None else "$" not in body


PLAIN_CODE = "comfyart/api/mcp_tools/canvas.py::generate_image(model=google/nano-banana-pro/edit,size=2k,aspect=3:4,retries=2)"


async def test_715_plain_inline_code_still_wraps(ws, bundle):  # noqa: F811
    # #715 team: nowrap/ellipsis/title only on .ca-task-id; ordinary inline code keeps main's wrapping
    body = await _shot(bundle, "zh", "light", "timeout", 0.32, "failure-timeout-plaincode", LONG_ID, PLAIN_CODE)
    assert PLAIN_CODE in body and f"任务编号：{LONG_ID}" in body
    async with apw.async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 560, "height": 300})
        await page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
        await page.goto(f"{bundle}/index.html?" + urlencode({"lang": "zh", "kind": "timeout", "charged": 0.32, "model": MODEL, "task": LONG_ID, "code": PLAIN_CODE}))
        await page.wait_for_function("window.__ready")
        info = await page.evaluate("""() => [...document.querySelectorAll('.ca-md code')].map(c => {
            const s = getComputedStyle(c); return {t: c.textContent, cls: c.className, title: c.title, ws: s.whiteSpace, to: s.textOverflow,
              rects: c.getClientRects().length, clipped: c.scrollWidth > c.clientWidth + 1} })""")
        await b.close()
    plain = [x for x in info if x["t"] == PLAIN_CODE][0]
    tid = [x for x in info if x["t"] == LONG_ID][0]
    assert plain["cls"] == "" and plain["title"] == "" and plain["ws"] != "nowrap" and plain["to"] != "ellipsis", plain
    assert plain["rects"] > 1 and not plain["clipped"], plain  # wraps, full text visible
    assert tid["cls"] == "ca-task-id" and tid["title"] == LONG_ID and tid["ws"] == "nowrap" and tid["to"] == "ellipsis" and tid["rects"] == 1, tid


async def _narrow(bundle, lang, theme, surface, name):
    """#715 design: 360px viewport, 86-char id -> trailing ellipsis, parenthetical on its own line, nothing overflows."""
    async with apw.async_playwright() as p:
        try:
            b = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        page = await b.new_page(viewport={"width": 360, "height": 300}, device_scale_factor=2)
        await page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
        await page.goto(f"{bundle}/index.html?" + urlencode({"lang": lang, "theme": theme, "kind": "timeout", "charged": 0.32,
                                                            "model": MODEL, "task": XLONG_ID, "w": 360, "surface": surface}))
        await page.wait_for_function("window.__ready")
        await page.wait_for_timeout(200)
        m = await page.evaluate("""() => {
            const id = document.querySelector('.ca-task-id'), box = document.querySelector('[data-testid=ws-failure]')
            const root = document.querySelector('.ca-root'), r = id.getBoundingClientRect(), b = box.getBoundingClientRect()
            const s = getComputedStyle(id)
            // where does the parenthetical start? the text node right after the id
            const rg = document.createRange(), n = id.nextSibling || id.parentNode.nextSibling
            let after = null
            if (n && n.nodeType === 3 && n.textContent.trim()) { rg.setStart(n, 0); rg.setEnd(n, 1); after = rg.getBoundingClientRect().top }
            return {title: id.title, text: id.textContent, to: s.textOverflow, ws: s.whiteSpace, clipped: id.scrollWidth > id.clientWidth,
                    idTop: r.top, idBottom: r.bottom, idRight: r.right, idLeft: r.left, boxLeft: b.left, boxRight: b.right,
                    rootOverflow: root.scrollWidth > root.clientWidth, docOverflow: document.documentElement.scrollWidth > 360, after}
        }""")
        await page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"{name}-{lang}-{theme}.png"))
        await b.close()
    assert m["text"] == XLONG_ID and m["title"] == XLONG_ID and m["ws"] == "nowrap" and m["to"] == "ellipsis", m
    assert m["clipped"], m  # really truncated -> trailing ellipsis rendered
    assert m["boxLeft"] - 0.5 <= m["idLeft"] and m["idRight"] <= m["boxRight"] + 0.5, m  # id stays inside the card/bubble
    assert not m["rootOverflow"] and not m["docOverflow"], m
    assert m["after"] is not None and m["after"] >= m["idBottom"] - 1, m  # （…）/ (include it…) starts on the next line


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_715_long_id_truncates_chat_360(ws, bundle, lang, theme):  # noqa: F811
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    await _narrow(bundle, lang, theme, "chat", "failure-timeout-longid-360")


async def test_715_long_id_truncates_canvas_card_360(ws, bundle):  # noqa: F811
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    await _narrow(bundle, "zh", "light", "card", "failure-card-longid-360")
