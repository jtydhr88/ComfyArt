"""#195: browser end-to-end tests (mock only) for comment-run (评论直接执行) and click-to-edit (点选修改).

The real built app (dist/) runs in headless Chromium against the real ComfyArt aiohttp routes, which talk to a
local mock WaveSpeed. Covers: Ctrl+click point comment -> SAM point prompt -> 生成 / Enter -> inpaint edit payload
(model, prompt, image ref, mask, paste crop) -> result inserted back on the canvas; 「运行全部」 from the comments
list; the cost dialog (decline sends nothing, accept submits); failed task and timeout paths.
No network, no key, $0. Skipped when Playwright + Chromium are not installed (CI stays as is)."""
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image, ImageDraw

from ComfyArt.api import wavespeed
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EDIT = "openai/gpt-image-2.5-sunburst/edit"
SAM = "wavespeed-ai/sam3-image"
REAL_CURATED = wavespeed.load_curated
SHOTS = Path("/tmp/pr195-shots")
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")


def _png(draw) -> bytes:
    img = Image.new("RGB", (512, 512), (0, 0, 0))
    draw(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


SOURCE = _png(lambda d: (d.rectangle((0, 0, 512, 512), fill=(232, 222, 205)), d.rectangle((160, 160, 352, 352), fill=(80, 130, 200))))
MASK = _png(lambda d: d.ellipse((150, 150, 362, 362), fill=(255, 255, 255)))  # SAM: white object on black
RESULT = _png(lambda d: d.rectangle((0, 0, 512, 512), fill=(220, 30, 30)))


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    state = {"status": "completed", "submits": [], "quotes": [], "price": {EDIT: 0.039, SAM: 0.005}}
    for c in (wavespeed._quotes, wavespeed._map_cache, wavespeed._seg_cats, wavespeed._seg_masks, wavespeed._jobs, wavespeed._submits):
        c.clear()
    app = web.Application(client_max_size=50 * 2**20)

    async def models(r):
        return web.json_response({"code": 200, "data": [m for m in MODELS if m["model_id"] != EDIT] + [FIXTURE[EDIT]]})

    async def price(r):
        b = await r.json()
        state["quotes"].append(b)
        p = state["price"].get(b.get("model_id"), 0.01)
        return web.json_response({"code": 200, "data": {"model_id": b.get("model_id"), "price": p, "unit_price": p, "currency": "USD"}})

    async def submit(r):
        state["submits"].append((r.match_info["model"], await r.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(r):
        tid = r.match_info["id"]
        model = state["submits"][int(tid[4:]) - 1][0]
        st = state["status"] if model == EDIT else "completed"
        data = {"id": tid, "status": st, "outputs": [], "error": ""}
        if st == "completed":
            data["outputs"] = [str(r.url.with_path("/cdn/mask.png" if model == SAM else "/cdn/out.png").with_query(None))]
        if st == "failed":
            data["error"] = "mock model error"
        return web.json_response({"code": 200, "data": data})

    async def upload(r):
        async for part in await r.multipart():
            await part.read()
        return web.json_response({"code": 200, "data": {"download_url": str(r.url.with_path("/cdn/up.png"))}})

    app.router.add_get("/api/v3/models", models)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_post("/api/v3/media/upload/binary", upload)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/{model:.+}", submit)
    for name, data in (("mask", MASK), ("out", RESULT), ("up", SOURCE)):
        app.router.add_get(f"/cdn/{name}.png", _bytes(data))
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "load_curated", REAL_CURATED)
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield state
    await server.close()


def _bytes(b):
    async def h(r):
        return web.Response(body=b, content_type="image/png")
    return h


@pytest.fixture
async def app_url(mock_ws, monkeypatch):
    """The ComfyArt routes as registered on the (stubbed) host server, plus the few host endpoints the UI reads."""
    import folder_paths
    from server import PromptServer
    import os
    monkeypatch.setattr(folder_paths, "folder_names_and_paths", {}, raising=False)
    base = folder_paths.STATE["base"]
    for d in ("input", "output", "temp", "user/default"):
        os.makedirs(base / d, exist_ok=True)
    app = web.Application(client_max_size=200 * 2**20)
    app.router.add_routes(PromptServer.instance.routes)
    for rd in PromptServer.instance.routes:
        if isinstance(rd, web.RouteDef):
            app.router.add_route(rd.method, "/api" + rd.path, rd.handler)

    def ud(r):
        return base / "user/default" / r.match_info["file"]

    async def ud_get(r):
        return web.FileResponse(ud(r)) if ud(r).is_file() else web.Response(status=404)

    async def ud_post(r):
        ud(r).parent.mkdir(parents=True, exist_ok=True)
        ud(r).write_bytes(await r.read())
        return web.json_response(r.match_info["file"])

    async def view(r):
        q = r.query
        p = base / q.get("type", "output") / q.get("subfolder", "") / q["filename"]
        return web.FileResponse(p) if p.is_file() else web.Response(status=404)

    async def upload_image(r):
        form = await r.post()
        f, sub, kind = form["image"], form.get("subfolder", ""), form.get("type", "input")
        (base / kind / sub).mkdir(parents=True, exist_ok=True)
        (base / kind / sub / f.filename).write_bytes(f.file.read())
        return web.json_response({"name": f.filename, "subfolder": sub, "type": kind})

    async def wsock(r):
        s = web.WebSocketResponse()
        await s.prepare(r)
        async for _ in s:
            pass
        return s

    def js(v):
        async def h(r):
            return web.json_response(v)
        return h
    for path, h in (("/api/userdata", js([])), ("/api/models/{k}", js([])), ("/api/settings/{id}", js(None)), ("/api/queue", js({"queue_running": [], "queue_pending": []})),
                    ("/api/view", view), ("/api/userdata/{file:.+}", ud_get), ("/ws", wsock)):
        app.router.add_get(path, h)
    for path, h in (("/api/settings/{id}", js({})), ("/api/queue", js({})), ("/api/interrupt", js({})), ("/api/userdata/{file:.+}", ud_post), ("/api/upload/image", upload_image)):
        app.router.add_post(path, h)
    server = TestServer(app)
    await server.start_server()
    yield str(server.make_url("/comfyart/"))
    await server.close()


@pytest.fixture
async def page(app_url, tmp_path):
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:  # browser binaries not installed
            pytest.skip(f"chromium not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        pg = await ctx.new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh')")
        src = tmp_path / "src.png"
        src.write_bytes(SOURCE)
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.mouse.click(28, 83)  # home: new project
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1500)
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").nth(-2).click()
        await pg.locator("input[type=file][accept*=image]").first.set_input_files(str(src))
        await pg.locator(".tl-image").first.wait_for()
        await pg.wait_for_timeout(800)
        await pg.keyboard.press("Escape")
        yield pg
        await browser.close()


async def _until(fn, timeout=15.0):
    for _ in range(int(timeout * 10)):
        v = await fn()
        if v:
            return v
        await asyncio.sleep(0.1)
    raise AssertionError("timed out waiting")


async def _image_box(pg):
    return await pg.locator(".tl-image").first.bounding_box()


async def _point_comment(pg, mock_ws, text, fx=0.5, fy=0.5):
    b = await _image_box(pg)
    n = len(mock_ws["submits"])
    await pg.keyboard.down("Control")
    await pg.mouse.click(b["x"] + b["width"] * fx, b["y"] + b["height"] * fy)
    await pg.keyboard.up("Control")
    panel = pg.locator(".ca-cpanel")
    await panel.wait_for()
    # click-select: the point is sent to SAM in source-image pixels, then the panel reports the marked object
    await _until(lambda: _async(len(mock_ws["submits"]) > n))
    await _until(lambda: _not_detecting(panel))
    await panel.locator("textarea").fill(text)
    return panel


async def _not_detecting(panel):
    return ZH["commentPanel.detecting"] not in await panel.inner_text()


async def _async(v):
    return v


SAMPLE = """async () => {
  // the result is placed to the right of the source
  const img = [...document.querySelectorAll('.tl-image img, img.tl-image')].sort((a, b) => a.getBoundingClientRect().x - b.getBoundingClientRect().x).at(-1)
  const el = new Image(); el.src = img.src; await el.decode()
  const c = document.createElement('canvas'); c.width = el.naturalWidth; c.height = el.naturalHeight
  const x = c.getContext('2d'); x.drawImage(el, 0, 0)
  const px = (u, v) => [...x.getImageData(Math.round(u * c.width), Math.round(v * c.height), 1, 1).data].slice(0, 3)
  return [px(0.5, 0.5), px(0.03, 0.03)]
}"""


def _edits(state):
    return [b for m, b in state["submits"] if m == EDIT]


async def _images(pg):
    return await pg.locator(".tl-image").count()


async def test_click_to_edit_point_comment_runs_inpaint_and_pastes_back(page, mock_ws):
    pg = page
    panel = await _point_comment(pg, mock_ws, "把蓝色方块改成红色")
    model, sam = mock_ws["submits"][0]
    assert model == SAM
    (pt,) = sam["point_prompts"]
    assert pt["label"] == 1 and abs(pt["x"] - 256) <= 8 and abs(pt["y"] - 256) <= 8, pt  # image px, not screen px
    assert ZH["commentPanel.markedObject"].split("{")[0] in await panel.inner_text()
    SHOTS.mkdir(exist_ok=True)
    await pg.screenshot(path=str(SHOTS / "e2e-01-click-select-zh.png"))
    await panel.get_by_role("button", name=ZH["common.generate"]).click()
    await _until(lambda: _async(len(_edits(mock_ws)) == 1))
    edit = _edits(mock_ws)[0]
    assert "把蓝色方块改成红色" in edit["prompt"] and "unchanged" in edit["prompt"]
    assert len(edit["images"]) == 1 and edit["images"][0].startswith("http")  # the crop around the mark is uploaded
    # the quote the backend priced is the one submitted (no under-quote): sunburst edit with one image ref
    q = [x for x in mock_ws["quotes"] if x["model_id"] == EDIT][-1]["inputs"]
    assert len(q["images"]) == 1 and q.get("resolution") == edit.get("resolution")
    # result is pasted back as a new image next to the source and a done notice is raised
    await _until(lambda: _two_images(pg), 20)
    await pg.wait_for_timeout(1200)
    await pg.screenshot(path=str(SHOTS / "e2e-02-pasted-back-zh.png"))
    assert ZH["actions.localEdit"].split("·")[-1].strip() in await pg.locator("body").inner_text()
    # pixels of the inserted result: the marked object took the model output, the rest of the source is kept
    center, corner = await pg.evaluate(SAMPLE)
    assert center[0] > 180 and center[2] < 90, center   # red from the mock edit result inside the SAM mask
    assert abs(corner[0] - 232) < 12 and abs(corner[2] - 205) < 12, corner  # untouched background


async def _two_images(pg):
    return await _images(pg) >= 2


async def test_enter_key_runs_comment_edit(page, mock_ws):
    pg = page
    await _point_comment(pg, mock_ws, "加一顶帽子")
    await pg.keyboard.press("Enter")
    await _until(lambda: _async(len(_edits(mock_ws)) == 1))
    await _until(lambda: _two_images(pg), 20)
    edit = _edits(mock_ws)[0]
    assert edit["prompt"].startswith("加一顶帽子")
    # the inpaint mask is uploaded alongside the crop (sunburst edit gets image + mask refs, never the full canvas)
    assert len(edit["images"]) == 1


async def test_run_all_comments_from_list(page, mock_ws):
    pg = page
    await _point_comment(pg, mock_ws, "左上角加一朵云", 0.2, 0.2)
    await pg.keyboard.press("Escape")
    await _point_comment(pg, mock_ws, "右下角加一棵树", 0.8, 0.8)
    await pg.keyboard.press("Escape")
    await pg.locator(f'button[title="{ZH["common.allComments"]}"]').click()
    run_all = pg.get_by_role("button", name=ZH["commentsList.runAll"])
    await run_all.wait_for()
    await pg.screenshot(path=str(SHOTS / "e2e-03-run-all-zh.png"))
    await run_all.click()
    await _until(lambda: _async(len(_edits(mock_ws)) == 2), 20)
    prompts = [e["prompt"] for e in _edits(mock_ws)]
    assert any(p.startswith("右下角加一棵树") for p in prompts) and any(p.startswith("左上角加一朵云") for p in prompts)
    sams = [b["point_prompts"][0] for m, b in mock_ws["submits"] if m == SAM]
    assert any(p["x"] < 160 and p["y"] < 160 for p in sams) and any(p["x"] > 352 and p["y"] > 352 for p in sams)
    await _until(lambda: _images_at_least(pg, 3), 25)


async def _images_at_least(pg, n):
    return await _images(pg) >= n


async def test_cost_dialog_decline_sends_nothing_accept_submits(page, mock_ws):
    pg = page
    mock_ws["price"][EDIT] = 0.62  # over the $0.50 default confirm line
    panel = await _point_comment(pg, mock_ws, "换成金属材质")
    await panel.get_by_role("button", name=ZH["common.generate"]).click()
    dialog = pg.locator(".ca-modal")
    await dialog.wait_for()
    # #397 (PR #405): the confirm shows UI credits, not $ — $0.62 → uiCredits = 62
    assert ZH["jobs.confirmCost"].replace("{0}", "62") in await dialog.inner_text() and ZH["jobs.confirmTitle"] in await dialog.inner_text()
    await pg.screenshot(path=str(SHOTS / "e2e-04-cost-zh.png"))
    await dialog.get_by_role("button", name=ZH["common.cancel"]).click()
    await pg.wait_for_timeout(800)
    assert _edits(mock_ws) == []  # declined: nothing submitted, nothing charged
    # second run on a fresh comment, accepted
    panel = await _point_comment(pg, mock_ws, "换成木头材质", 0.3, 0.3)
    await panel.get_by_role("button", name=ZH["common.generate"]).click()
    await dialog.wait_for()
    await dialog.get_by_role("button", name=ZH["jobs.confirmOk"]).click()
    await _until(lambda: _async(len(_edits(mock_ws)) == 1))
    assert _edits(mock_ws)[0]["prompt"].startswith("换成木头材质")


@pytest.mark.parametrize("mode", ["failed", "timeout"])
async def test_comment_edit_failure_and_timeout_are_reported(page, mock_ws, monkeypatch, mode):
    pg = page
    mock_ws["status"] = "failed" if mode == "failed" else "processing"
    if mode == "timeout":
        monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 2.0)
    panel = await _point_comment(pg, mock_ws, "把背景变成夜晚")
    await panel.get_by_role("button", name=ZH["common.generate"]).click()
    await _until(lambda: _async(len(_edits(mock_ws)) == 1))
    want = ZH["wsErr.failed"] if mode == "failed" else ZH["wsErr.timeout"].split("{0}")[0]
    await _until(lambda: _body_has(pg, want), 25)
    await pg.screenshot(path=str(SHOTS / f"e2e-05-{mode}-zh.png"))
    await pg.wait_for_timeout(500)
    assert await _images(pg) == 1  # nothing half-finished is left on the canvas


async def _body_has(pg, s):
    return s in await pg.locator("body").inner_text()
