"""WaveSpeed provider tests against a local mock server (WAVESPEED_BASE_URL); no real API calls."""
from __future__ import annotations

import asyncio
import io
import json
import os

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest

T2I = "alibaba/qwen-image-3.0/text-to-image"
EDIT = "alibaba/qwen-image-3.0/edit"
KEY = "test-key-not-real"


def _meta(model_id, props, required=("prompt",), price=0.03):
    return {"model_id": model_id, "name": model_id.split("/")[-1], "type": "x", "base_price": price, "description": "d",
            "api_schema": {"api_schemas": [{"request_schema": {"properties": props, "required": list(required)}}]}}


MODELS = [
    _meta(T2I, {"prompt": {"type": "string"}, "size": {"type": "string"}, "seed": {"type": "integer"}}),
    _meta("wavespeed-ai/z-image/turbo", {"prompt": {"type": "string"}, "size": {"type": "string"}}, price=0.005),
    _meta(EDIT, {"prompt": {"type": "string"}, "images": {"type": "array", "maxItems": 3}}, ("prompt", "images")),
    _meta("wavespeed-ai/image-eraser", {"image": {"type": "string"}, "mask_image": {"type": "string"}}, ("image",)),
    _meta("wavespeed-ai/paddle-ocr", {"image": {"type": "string"}, "output_format": {"type": "string", "enum": ["json", "markdown"]}}, ("image",), price=0.01),
    _meta("wavespeed-ai/sam3-image", {"image": {"type": "string"}, "prompt": {"type": "string"}, "point_prompts": {"type": "array"}, "box_prompts": {"type": "array"}, "apply_mask": {"type": "boolean"}, "output_format": {"type": "string", "enum": ["png"]}}, ("image",), price=0.005),
    _meta("bytedance/seedream-v5.0-flash/layer-decomposition", {"image": {"type": "string"}, "prompt": {"type": "string"}, "output_format": {"type": "string", "enum": ["jpeg", "png"]}}, ("image",), price=0.459),
    _meta("bytedance/seedream-v5.0-pro/layer-decomposition", {"image": {"type": "string"}, "prompt": {"type": "string"}}, ("image",), price=0.75),
    _meta("wavespeed-ai/minimax-h3/text-to-video", {"prompt": {"type": "string"}, "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"]}, "duration": {"type": "integer", "enum": [3, 4, 5, 6, 7, 8]}, "resolution": {"type": "string", "enum": ["480p", "540p", "768p", "1080p"]}, "seed": {"type": "integer"}}, price=0.04),
    _meta("alibaba/wan-3.0/text-to-video", {"prompt": {"type": "string"}, "duration": {"type": "integer"}}, price=0.1),
    _meta("wavespeed-ai/minimax-h3/image-to-video", {"prompt": {"type": "string"}, "image": {"type": "string"}, "last_image": {"type": "string"}, "duration": {"type": "integer", "enum": [3, 4, 5, 6, 7, 8]}, "resolution": {"type": "string", "enum": ["480p", "768p", "1080p"]}}, ("prompt", "image"), price=0.04),
    _meta("wavespeed-ai/minimax-h3/reference-to-video", {"prompt": {"type": "string"}, "reference_images": {"type": "array"}, "reference_videos": {"type": "array"}, "reference_audios": {"type": "array"}}, price=0.15),
    _meta("wavespeed-ai/wan-2.2/animate", {"image": {"type": "string"}, "video": {"type": "string"}, "prompt": {"type": "string"}}, ("image", "video"), price=0.2),
    _meta("wavespeed-ai/infinitetalk-fast", {"image": {"type": "string"}, "audio": {"type": "string"}, "prompt": {"type": "string"}}, ("audio", "image"), price=0.075),
    _meta("wavespeed-ai/minimax-h3/video-extend", {"video": {"type": "string"}, "prompt": {"type": "string"}, "duration": {"type": "integer", "enum": [3, 4, 5, 6, 7, 8]}}, ("prompt", "video"), price=0.04),
    _meta("wavespeed-ai/video-upscaler", {"video": {"type": "string"}, "target_resolution": {"type": "string", "enum": ["720p", "1080p", "2k", "4k"]}}, ("video",), price=0.005),
    _meta("wavespeed-ai/video-background-remover", {"video": {"type": "string"}}, ("video",), price=0.01),
    _meta("wavespeed-ai/ace-step-1.5", {"tags": {"type": "string"}, "lyrics": {"type": "string"}, "duration": {"type": "number", "minimum": 5, "maximum": 240}, "seed": {"type": "integer"}}, ("tags", "lyrics"), price=0.0003),
    _meta("minimax/music-3.0", {"prompt": {"type": "string"}, "lyrics": {"type": "string"}, "is_instrumental": {"type": "boolean"}}, ("prompt",), price=0.15),
    _meta("elevenlabs/music-v2", {"prompt": {"type": "string"}, "music_length_ms": {"type": "integer"}}, ("prompt", "music_length_ms"), price=0.75),
    # #509: WaveSpeed's documented yue2-3b schema: style + lyrics required, seed, output_format, no duration
    _meta("wavespeed-ai/yue2-3b/text-to-music", {"style": {"type": "string"}, "lyrics": {"type": "string"}, "seed": {"type": "integer", "default": -1}, "output_format": {"type": "string", "enum": ["mp3", "wav"]}}, ("style", "lyrics"), price=0.10),
    _meta("mirelo-ai/sfx-2.0/text-to-audio", {"prompt": {"type": "string"}, "duration": {"type": "number"}}, price=0.016),
    _meta("wavespeed-ai/qwen3-tts/text-to-speech", {"text": {"type": "string"}, "language": {"type": "string", "enum": ["auto", "Chinese", "English"]}, "voice": {"type": "string", "enum": ["Vivian", "Serena", "Uncle_Fu"]}}, ("text", "language", "voice"), price=0.005),
    _meta("wavespeed-ai/qwen3-tts/voice-clone", {"audio": {"type": "string"}, "text": {"type": "string"}, "language": {"type": "string", "enum": ["auto"]}}, ("audio", "text"), price=0.005),
    _meta("wavespeed-ai/trellis-2/image-to-3d", {"image": {"type": "string"}, "seed": {"type": "integer"}}, ("image",), price=0.2),
    _meta("tripo3d/h3.1/multiview-to-3d", {"images": {"type": "array"}}, ("images",), price=0.24),
    _meta("wavespeed-ai/openai-whisper-turbo", {"audio": {"type": "string"}, "language": {"type": "string", "enum": ["auto"]}}, ("audio",), price=0.0007),
    _meta("wavespeed-ai/image-captioner", {"image": {"type": "string"}}, ("image",), price=0.001),
    _meta("wavespeed-ai/depth-anything-v3/image", {"image": {"type": "string"}, "colormap": {"type": "string", "enum": ["grayscale", "inferno", "turbo"]}, "output_format": {"type": "string", "enum": ["jpeg", "png", "webp"]}}, ("image",), price=0.005),
    _meta("wavespeed-ai/image-background-remover", {"image": {"type": "string"}, "output_format": {"type": "string", "enum": ["png", "jpeg"]}}, ("image",), price=0.001),
    _meta("wavespeed-ai/image-upscaler", {"image": {"type": "string"}, "target_resolution": {"type": "string", "enum": ["2k", "4k", "8k"]}}, ("image",)),
    # not in the curated list: only reachable through a custom workflow (#75)
    _meta("acme/my-edit", {"input_image": {"type": "string"}, "instruction": {"type": "string"}, "strength": {"type": "number"}, "dims": {"type": "string"}}, ("input_image", "instruction", "strength")),
]

# #249: the multiple-angles model was missing here, so build_payload saw an empty schema and dropped
# horizontal_angle / vertical_angle / distance. The fixture entry is the parameter definition the mock serves.
_ANGLE_ID = "wavespeed-ai/qwen-image/edit-multiple-angles"
with open(os.path.join(os.path.dirname(__file__), "fixtures", "wavespeed_catalog_subset.json"), encoding="utf-8") as _angle_f:
    _angle_meta = json.load(_angle_f)[_ANGLE_ID]
if not any(m.get("model_id") == _ANGLE_ID for m in MODELS):
    MODELS.append(_angle_meta)

# #528/#513 step1: motion-control + generate-with-refs models for custom workflow e2e assign
for _mid in (
    "kwaivgi/kling-v3.0-std/motion-control",
    "wavespeed-ai/qwen-image/text-to-image-lora",
):
    if not any(m.get("model_id") == _mid for m in MODELS):
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "wavespeed_catalog_subset.json"), encoding="utf-8") as _f:
            MODELS.append(json.load(_f)[_mid])


@pytest.fixture(autouse=True)
def uncurated(monkeypatch):
    # These tests exercise submit/poll/pricing mechanics on the mock MODELS above with the base
    # wavespeed_models.json lineup; the #95 curated narrowing is covered in test_curated_models.py.
    monkeypatch.setattr(wavespeed, "load_curated", lambda: {})


@pytest.fixture
async def ws(monkeypatch, fresh_user_dir):
    state = {"status": "completed", "submits": [], "polls": 0, "uploads": 0, "auth": set(), "submit_status": 200, "result_status": 200, "prices": {}, "quotes": []}
    wavespeed._quotes.clear()
    wavespeed._map_cache.clear()
    wavespeed._seg_cats.clear()
    wavespeed._seg_masks.clear()
    app = web.Application()

    async def price(request):
        # documented POST /api/v3/model/price; unknown models answer 400 (code 4005) so the catalog price is used
        body = await request.json()
        state["quotes"].append(body)
        p = state["prices"].get(body.get("model_id"))
        if p is None:
            return web.json_response({"code": 4005, "message": "model not found"}, status=400)
        p = p(body.get("inputs") or {}) if callable(p) else p
        return web.json_response({"code": 200, "message": "success", "data": {"model_id": body["model_id"], "unit_price": p, "price": p, "discounted_price": p, "discount_rate": 1, "currency": "USD"}})

    async def models(request):
        state["auth"].add(request.headers.get("Authorization"))
        return web.json_response({"code": 200, "data": MODELS})

    async def submit(request):
        state["auth"].add(request.headers.get("Authorization"))
        if state["submit_status"] != 200:
            return web.json_response({"code": state.get("submit_code", state["submit_status"]), "message": state.get("submit_message", "nope")}, status=state["submit_status"])
        state["submits"].append((request.match_info["model"], await request.json()))
        if state.get("no_id"):  # #712: charged, but the reply lost its task id
            return web.json_response({"code": 200, "data": {"status": "created"}})
        tid = state["task_id"] if state.get("task_id") else f"task{len(state['submits'])}"  # #715: realistic long ids on demand
        return web.json_response({"code": 200, "data": {"id": tid, "status": "created"}})

    async def result(request):
        state["polls"] += 1
        if state["result_status"] != 200:
            return web.json_response({"message": "x"}, status=state["result_status"])
        st = state["status"]
        data = {"id": request.match_info["id"], "status": st, "outputs": [], "error": ""}
        if st == "completed":
            tid = request.match_info["id"]
            model = state["submits"][int(tid[4:]) - 1][0] if tid.startswith("task") and tid[4:].isdigit() and int(tid[4:]) <= len(state["submits"]) else None
            data["outputs"] = state.get("by_model", {}).get(model) or state.get("outputs") or [str(request.url.with_path("/cdn/out.png"))]
            if state.get("no_outputs"):  # #712: completed (billed) with no image
                data["outputs"] = []
        if st == "failed":
            data["error"] = state.get("task_error", "content flagged")
            if "task_code" in state:
                data["code"] = state["task_code"]
        return web.json_response({"code": 200, "data": data})

    async def upload(request):
        state["uploads"] += 1
        reader = await request.multipart()
        async for part in reader:
            await part.read()
        return web.json_response({"code": 200, "data": {"download_url": f"https://cdn.test/up{state['uploads']}.png"}})

    async def cdn(request):
        return web.Response(body=b"PNGDATA")

    app.router.add_get("/api/v3/models", models)
    app.router.add_post("/api/v3/media/upload/binary", upload)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_post("/api/v3/{model:.+}", submit)
    app.router.add_get("/cdn/out.png", cdn)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", KEY)
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    wavespeed._jobs.clear()
    wavespeed._submits.clear()
    yield state
    await server.close()


async def test_text_to_image_submit_poll_download(ws):
    task = await wavespeed.submit({"feature": "generate_image", "prompt": "a red apple", "width": 1024, "height": 768, "seed": 7})
    model, payload = ws["submits"][0]
    assert model == T2I  # product default when no model is given
    assert payload == {"prompt": "a red apple", "size": "1024*768", "seed": 7}
    assert ws["auth"] == {f"Bearer {KEY}"}
    hist = await wavespeed.poll(task)
    out = hist[f"ws:{task}"]
    assert out["status"]["completed"] is True
    ref = out["outputs"]["ws"]["images"][0]
    assert ref["subfolder"] == "wavespeed" and ref["type"] == "output"
    import folder_paths
    assert wavespeed._read(os.path.join(folder_paths.get_output_directory(), "wavespeed", ref["filename"])) == b"PNGDATA"
    # finished results are cached: no second poll or download
    polls = ws["polls"]
    await wavespeed.poll(task)
    assert ws["polls"] == polls


async def test_model_choice_is_honored_and_validated(ws):
    await wavespeed.submit({"feature": "text_to_image", "model": "wavespeed-ai/z-image/turbo", "prompt": "x"})
    assert ws["submits"][0][0] == "wavespeed-ai/z-image/turbo"
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "model": "made/up-model", "prompt": "x"})
    assert e.value.status == 400 and "unknown model" in str(e.value)
    assert len(ws["submits"]) == 1  # rejected before any (paid) submit


async def test_edit_uploads_local_input(ws):
    import folder_paths
    os.makedirs(os.path.join(folder_paths.get_input_directory(), "comfyart"), exist_ok=True)
    wavespeed._write(os.path.join(folder_paths.get_input_directory(), "comfyart", "a.png"), b"img")
    await wavespeed.submit({"feature": "edit_image", "image": "comfyart/a.png [input]", "prompt": "make it blue"})
    model, payload = ws["submits"][0]
    assert model == EDIT and payload["images"] == ["https://cdn.test/up1.png"] and payload["prompt"] == "make it blue"


async def test_erase_converts_mask(ws):
    import folder_paths
    from PIL import Image
    inp = folder_paths.get_input_directory()
    os.makedirs(inp, exist_ok=True)
    Image.new("RGB", (8, 8)).save(os.path.join(inp, "src.png"))
    mask = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    mask.putpixel((1, 1), (255, 255, 255, 0))
    mask.save(os.path.join(inp, "mask.png"))
    await wavespeed.submit({"feature": "erase_region", "image": "src.png [input]", "mask": "mask.png [input]"})
    payload = ws["submits"][0][1]
    assert set(payload) == {"image", "mask_image"}
    white = Image.open(io.BytesIO(wavespeed.mask_to_white(wavespeed._read(os.path.join(inp, "mask.png")))))
    assert white.getpixel((1, 1)) == 255 and white.getpixel((0, 0)) == 0


async def test_failed_task_reports_error(ws):
    ws["status"] = "failed"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    msgs = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"]
    assert msgs[0][0] == "execution_error" and "content flagged" in msgs[0][1]["exception_message"]


async def test_timeout(ws, monkeypatch):
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["completed"] is False
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    msgs = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"]
    assert "timed out" in msgs[0][1]["exception_message"]


async def test_401_on_submit_and_poll(ws):
    ws["submit_status"] = 401
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert e.value.status == 401 and KEY not in str(e.value)
    ws["submit_status"] = 200
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    ws["result_status"] = 401
    msg = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"][0][1]["exception_message"]
    assert "401" in msg and KEY not in msg


async def test_poll_is_throttled_to_2s(ws, monkeypatch):
    monkeypatch.setattr(wavespeed, "POLL_MIN", 2.0)
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    wavespeed._jobs[task]["next_poll"] = 0
    await wavespeed.poll(task)
    await wavespeed.poll(task)  # within 2 s: answered from cache, no API call
    assert ws["polls"] == 1


async def test_missing_key(ws, monkeypatch):
    monkeypatch.delenv("WAVESPEED_API_KEY")
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert "WAVESPEED_API_KEY" in str(e.value) and "Settings" in str(e.value)


async def test_app_concurrency_limit(ws, monkeypatch):
    ws["status"] = "processing"
    monkeypatch.setattr(wavespeed, "limits", lambda: {"app_concurrent": 1, "wavespeed_concurrent": 300, "wavespeed_submits_per_minute": 500, "batch_max": 50, "confirm_usd": 0.5})
    await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "y"})
    assert e.value.status == 429 and len(ws["submits"]) == 1


async def test_list_models_curated_only(ws):
    out = await canvas.TOOLS["list_models"]["handler"]({"type": "image"})
    t2i = out["features"]["text_to_image"]
    ids = [m["id"] for m in t2i["models"]]
    assert t2i["default"] == T2I and ids[0] == T2I
    assert "made/up-model" not in ids and len(ids) == len(wavespeed.load_config()["features"]["text_to_image"]["models"])
    assert next(m for m in t2i["models"] if m["id"] == T2I)["usd"] == 0.03
    # unavailable (pending) features are left out of list_models
    assert "image_to_video" in (await canvas.TOOLS["list_models"]["handler"]({"type": "video"}))["features"]
    tools = (await canvas.TOOLS["list_models"]["handler"]({"type": "image_tools"}))["features"]
    assert "split_layers" in tools and "segment" in tools
    assert "model" in canvas.TOOLS["edit_image"]["inputSchema"]["properties"]


async def test_routes_run_and_history(ws):
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/wavespeed/run", json={"inputs": {"feature": "text_to_image", "prompt": "hi"}})
        pid = (await res.json())["prompt_id"]
        assert pid.startswith("ws:")
        hist = await (await client.get(f"/comfyart/wavespeed/history/{pid[3:]}")).json()
        assert hist[pid]["outputs"]["ws"]["images"]
        models = await (await client.get("/comfyart/wavespeed/models")).json()
        assert KEY not in json.dumps(models) and models["enabled"] is True
        bad = await client.post("/comfyart/wavespeed/run", json={"inputs": {"feature": "text_to_image", "model": "x/y", "prompt": "hi"}})
        assert bad.status == 400
    finally:
        await client.close()


async def test_builtin_agent_one_sentence_image(ws):
    """Built-in agent (OpenAI-compatible endpoint, mocked) turns one sentence into a WaveSpeed image."""
    llm_calls = []
    replies = [
        {"tool_calls": [{"id": "1", "function": {"name": "list_models", "arguments": "{}"}}]},
        {"tool_calls": [{"id": "2", "function": {"name": "generate_image", "arguments": json.dumps({"prompt": "a cat astronaut"})}}]},
        {"tool_calls": [{"id": "3", "function": {"name": "wait_generation", "arguments": json.dumps({"ids": ["shape:g"]})}}]},
        {"content": "Done: your cat astronaut is on the canvas.", "tool_calls": []},
    ]
    llm = web.Application()

    async def completions(request):
        body = await request.json()
        llm_calls.append(body)
        return web.json_response({"choices": [{"message": {"content": "", **replies.pop(0)}}]})

    llm.router.add_post("/v1/chat/completions", completions)
    llm_server = TestServer(llm)
    await llm_server.start_server()
    jobs = {}

    async def fake_mcp(session, endpoint, name, arguments):
        if name == "list_models":
            return json.dumps(await canvas.TOOLS["list_models"]["handler"](arguments)), []
        if name == "generate_image":  # what the page does: queue the pseudo graph
            jobs["shape:g"] = await wavespeed.submit({"feature": "text_to_image", "model": arguments.get("model"), "prompt": arguments["prompt"], "width": 1024, "height": 1024})
            return json.dumps({"ids": ["shape:g"]}), []
        if name == "wait_generation":
            return json.dumps(await wavespeed.poll(jobs["shape:g"])), []
        raise AssertionError(name)

    async def fake_tools(session, endpoint):
        return [{"name": n, "description": "", "inputSchema": {"type": "object"}} for n in ("list_models", "generate_image", "wait_generation")]

    provider = LocalLlmProvider(base_url=lambda: str(llm_server.make_url("/v1")))
    provider._mcp_call_tool = fake_mcp
    provider._mcp_list_tools = fake_tools
    events = []

    async def emit(ev):
        events.append(ev)

    try:
        result = await provider.send(TurnRequest(chat_id="c", user_text="画一只宇航员猫", mcp_endpoint="http://x/mcp", model="kimi"), emit, TurnHandle())
    finally:
        await llm_server.close()
    assert result.error == ""
    assert [m for m, _ in ws["submits"]] == [T2I]
    assert ws["submits"][0][1]["prompt"] == "a cat astronaut"
    assert [e.name for e in events if e.t == "tool_use"] == ["list_models", "generate_image", "wait_generation"]
    # #391 (PR #393) appends a run_stop card after the final reply; the final assistant text is now the
    # delta stream after the last tool event. Product ruling (#499): assert main's card as-is — it carries
    # no final reply text (text == "", the card dict has no reply field); a separate card tracks that.
    assert events[-1].t == "run_stop"
    assert events[-1].text == ""
    assert "Done: your cat astronaut" not in json.dumps(events[-1].input, ensure_ascii=False)
    assert events[-1].input["can_continue"] is False
    last_tool = max(i for i, e in enumerate(events) if e.t in ("tool_use", "tool_result"))
    final_text = "".join(e.text or "" for e in events[last_tool + 1:] if e.t == "delta")
    assert final_text.startswith("Done")
    assert len(llm_calls) == 4


async def test_ocr_runs_on_wavespeed(ws, bot_client, fresh_user_dir):
    from PIL import Image
    path = fresh_user_dir / "output" / "sale.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 24), "white").save(path)
    ws["outputs"] = [json.dumps({"layout": [{"block_content": "SUMMER SALE", "block_bbox": [4, 2, 70, 20]}, {"text": "50%", "poly": [[1, 1], [9, 1], [9, 5], [1, 5]], "score": 0.9}]})]
    res = await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=sale.png&subfolder=&type=output"})
    assert res.status == 200, await res.text()
    lines = (await res.json())["lines"]
    assert [ln["text"] for ln in lines] == ["SUMMER SALE", "50%"] and all(len(ln["box"]) == 4 for ln in lines)
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/paddle-ocr" and payload["output_format"] == "json" and payload["image"].startswith("https://cdn.test/")


def _input_png(name="src.png"):
    import folder_paths
    from PIL import Image
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    Image.new("RGB", (8, 8)).save(os.path.join(folder_paths.get_input_directory(), name))
    return f"{name} [input]"


async def test_sam_segment_points_and_text(ws):
    image = _input_png()
    pts = [{"x": 3, "y": 4, "label": 1}]
    task = await wavespeed.submit({"feature": "segment", "image": image, "params": {"apply_mask": False, "output_format": "png", "point_prompts": pts}})
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/sam3-image"
    assert payload == {"image": "https://cdn.test/up1.png", "apply_mask": False, "output_format": "png", "point_prompts": pts}
    assert (await wavespeed.poll(task))[f"ws:{task}"]["outputs"]["ws"]["images"]
    await wavespeed.submit({"feature": "edit_elements", "image": image, "prompt": "person", "params": {"apply_mask": False}})
    assert ws["submits"][1][1]["prompt"] == "person"


async def test_split_layers_default_runs_without_confirmation(ws):
    await wavespeed.submit({"feature": "split_layers", "image": _input_png(), "png": True, "layers": 4})
    model, payload = ws["submits"][0]
    assert model == "bytedance/seedream-v5.0-flash/layer-decomposition" and payload["output_format"] == "png"
    assert payload["prompt"] == "Separate into 4 layers."
    await wavespeed.submit({"feature": "split_layers", "image": _input_png(), "prompt": "keep the logo", "layers": 3})
    assert ws["submits"][1][1]["prompt"] == "keep the logo. Separate into 3 layers."
    await wavespeed.submit({"feature": "split_layers", "image": _input_png(), "prompt": "poster.", "layers": 3})
    assert ws["submits"][2][1]["prompt"] == "poster. Separate into 3 layers."


async def test_jobs_over_50_cents_need_confirmation(ws):
    image = _input_png()
    job = {"feature": "split_layers", "model": "bytedance/seedream-v5.0-pro/layer-decomposition", "image": image}
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.confirm == 0.75 and not ws["submits"]
    await wavespeed.submit({**job, "confirmed": True})
    assert ws["submits"][0][0] == "bytedance/seedream-v5.0-pro/layer-decomposition"


async def test_confirmation_route_answers_409_with_price(ws):
    import server
    _input_png()
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/wavespeed/run", json={"inputs": {"feature": "split_layers", "model": "bytedance/seedream-v5.0-pro/layer-decomposition", "image": "src.png [input]"}})
        assert res.status == 409 and (await res.json())["error"]["confirm_usd"] == 0.75
    finally:
        await client.close()


def _input_file(name, data=b"x"):
    import folder_paths
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    wavespeed._write(os.path.join(folder_paths.get_input_directory(), name), data)
    return f"{name} [input]"


async def test_text_to_video_default_and_mapping(ws):
    ws["prices"].update({m["model_id"]: 0.01 for m in MODELS})  # #159: priced (an unpriced non-default tier always asks first)
    task = await wavespeed.submit({"feature": "text_to_video", "prompt": "waves", "ratio": "16:9", "duration": 5, "resolution": "768p", "seed": 3})
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/minimax-h3/text-to-video"
    assert payload == {"prompt": "waves", "aspect_ratio": "16:9", "duration": 5, "resolution": "768p", "seed": 3}
    assert (await wavespeed.poll(task))[f"ws:{task}"]["outputs"]["ws"]["images"]


async def test_video_duration_snaps_to_enum_and_model_validated(ws):
    ws["prices"].update({m["model_id"]: 0.01 for m in MODELS})  # #159: priced (an unpriced non-default tier always asks first)
    await wavespeed.submit({"feature": "text_to_video", "prompt": "x", "duration": 10})
    assert ws["submits"][0][1]["duration"] == 8
    await wavespeed.submit({"feature": "text_to_video", "model": "alibaba/wan-3.0/text-to-video", "prompt": "x", "duration": 10})
    assert ws["submits"][1] == ("alibaba/wan-3.0/text-to-video", {"prompt": "x", "duration": 10})
    with pytest.raises(wavespeed.WaveSpeedError):
        await wavespeed.submit({"feature": "text_to_video", "model": "wavespeed-ai/minimax-h3/image-to-video", "prompt": "x"})
    assert len(ws["submits"]) == 2


async def test_image_to_video_with_last_frame(ws):
    img = _input_png()
    await wavespeed.submit({"feature": "animate_image", "image": img, "last_image": img, "prompt": "move", "duration": 3})
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/minimax-h3/image-to-video" and payload["image"].startswith("https://cdn.test/") and payload["last_image"] == payload["image"] and payload["duration"] == 3


async def test_reference_motion_lipsync(ws):
    img, vid, aud = _input_png(), _input_file("m.mp4"), _input_file("s.wav")
    await wavespeed.submit({"feature": "reference_to_video", "prompt": "p", "reference_images": [img], "reference_videos": [vid], "reference_audios": [aud]})
    await wavespeed.submit({"feature": "motion_control", "image": img, "video": vid})
    await wavespeed.submit({"feature": "lip_sync", "image": img, "audio": aud})
    (m1, p1), (m2, p2), (m3, p3) = ws["submits"]
    assert m1 == "wavespeed-ai/minimax-h3/reference-to-video" and len(p1["reference_images"]) == len(p1["reference_videos"]) == len(p1["reference_audios"]) == 1
    assert m2 == "wavespeed-ai/wan-2.2/animate" and set(p2) == {"image", "video"}
    assert m3 == "wavespeed-ai/infinitetalk-fast" and set(p3) == {"image", "audio"}


async def test_video_tools(ws):
    ws["prices"].update({m["model_id"]: 0.01 for m in MODELS})  # #159: priced (an unpriced non-default tier always asks first)
    vid = _input_file("v.mp4")
    await wavespeed.submit({"feature": "extend_video", "video": vid, "prompt": "go on", "duration": 5})
    await wavespeed.submit({"feature": "upscale_video", "video": vid, "params": {"target_resolution": "4k"}})
    await wavespeed.submit({"feature": "remove_video_background", "video": vid})
    assert [m for m, _ in ws["submits"]] == ["wavespeed-ai/minimax-h3/video-extend", "wavespeed-ai/video-upscaler", "wavespeed-ai/video-background-remover"]
    assert ws["submits"][1][1]["target_resolution"] == "4k"


async def test_audio_tools(ws):
    await wavespeed.submit({"feature": "generate_music", "prompt": "lofi", "lyrics": "", "duration": 30})
    await wavespeed.submit({"feature": "generate_sound_effect", "prompt": "door slam", "duration": 3})
    await wavespeed.submit({"feature": "text_to_speech", "text": "你好", "voice": "Uncle_fu"})
    await wavespeed.submit({"feature": "voice_clone", "text": "hi", "audio": _input_file("ref.wav")})
    (m1, p1), (m2, p2), (m3, p3), (m4, p4) = ws["submits"]
    assert m1 == "minimax/music-3.0" and p1 == {"prompt": "lofi"}
    assert m2 == "mirelo-ai/sfx-2.0/text-to-audio" and p2 == {"prompt": "door slam", "duration": 3}
    assert m3 == "wavespeed-ai/qwen3-tts/text-to-speech" and p3 == {"text": "你好", "voice": "Uncle_Fu", "language": "auto"}
    assert m4 == "wavespeed-ai/qwen3-tts/voice-clone" and p4["text"] == "hi" and p4["audio"].startswith("https://cdn.test/")


async def test_music_duration_clamped_to_model_range(ws):
    # bot generate_music accepts up to 1000 s; ace-step-1.5 only takes 5..240 s
    ace = "wavespeed-ai/ace-step-1.5"
    await wavespeed.submit({"feature": "generate_music", "model": ace, "prompt": "lofi", "lyrics": "[verse] hi", "duration": 600})
    await wavespeed.submit({"feature": "generate_music", "model": ace, "prompt": "lofi", "duration": 1})
    (m1, p1), (_, p2) = ws["submits"]
    assert m1 == "wavespeed-ai/ace-step-1.5" and p1 == {"tags": "lofi", "lyrics": "[verse] hi", "duration": 240}
    assert p2["duration"] == 5 and p2["lyrics"] == "[instrumental]"


async def test_expensive_music_reuses_confirmation(ws):
    job = {"feature": "music", "model": "elevenlabs/music-v2", "prompt": "epic", "duration": 30}
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.confirm == 0.75 and not ws["submits"]
    await wavespeed.submit({**job, "confirmed": True})
    assert ws["submits"][0][1] == {"prompt": "epic", "music_length_ms": 30000}


async def test_3d_single_and_multiview(ws):
    img = _input_png()
    task = await wavespeed.submit({"feature": "image_to_3d", "image": img})
    await wavespeed.submit({"feature": "image_to_3d", "model": "tripo3d/h3.1/multiview-to-3d", "images": [img, _input_png("b.png")]})
    (m1, p1), (m2, p2) = ws["submits"]
    assert m1 == "wavespeed-ai/trellis-2/image-to-3d" and set(p1) == {"image"}
    assert m2 == "tripo3d/h3.1/multiview-to-3d" and len(p2["images"]) == 2
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["completed"] is True


async def test_transcribe_route(ws, bot_client, fresh_user_dir):
    path = fresh_user_dir / "input" / "voice.webm"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")
    ws["outputs"] = ["你好世界"]
    res = await bot_client.post("/comfyart/wavespeed/transcribe", json={"src": "/api/view?filename=voice.webm&subfolder=&type=input"})
    assert res.status == 200, await res.text()
    assert (await res.json())["text"] == "你好世界"
    assert ws["submits"][0][0] == "wavespeed-ai/openai-whisper-turbo"


async def test_storyboard_chains_last_frame_and_concats(ws, monkeypatch):
    ws["prices"].update({m["model_id"]: 0.01 for m in MODELS})  # #159: priced (an unpriced non-default tier always asks first)
    frames, joined = [], []
    monkeypatch.setattr(wavespeed, "_last_frame", lambda src, out: (frames.append(src), wavespeed._write(out, b"png")))
    monkeypatch.setattr(wavespeed, "_concat", lambda paths, out: (joined.extend(paths), wavespeed._write(out, b"mp4")))
    scenes = [{"prompt": "a", "duration": 3}, {"prompt": "b", "duration": 4}, {"prompt": "c", "duration": 3}]
    group = await wavespeed.submit({"feature": "text_to_video", "prompt": "x", "scenes": scenes})
    for _ in range(10):
        hist = (await wavespeed.poll(group))[f"ws:{group}"]
        if hist["status"]["completed"]:
            break
    assert hist["status"]["status_str"] == "completed"
    models = [m for m, _ in ws["submits"]]
    assert models == ["wavespeed-ai/minimax-h3/text-to-video"] + ["wavespeed-ai/minimax-h3/image-to-video"] * 2
    assert [p["prompt"] for _, p in ws["submits"]] == ["a", "b", "c"]
    assert all(p["image"].startswith("https://cdn.test/") for _, p in ws["submits"][1:])
    assert len(frames) == 2 and len(joined) == 3
    assert hist["outputs"]["ws"]["images"][0]["filename"].endswith("_storyboard.mp4")


async def test_storyboard_confirms_total_price(ws):
    scenes = [{"prompt": str(i), "duration": 3} for i in range(13)]  # 13 x $0.04 = $0.52
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_video", "prompt": "x", "scenes": scenes})
    assert e.value.status == 409 and e.value.confirm == 0.52 and not ws["submits"]


async def test_mockup_surface_depth_and_mask(ws, monkeypatch):
    from PIL import Image

    buf = io.BytesIO()
    cut = Image.new("RGBA", (4, 2), (10, 20, 30, 0))
    cut.putpixel((1, 0), (10, 20, 30, 255))
    cut.save(buf, format="PNG")
    group = await wavespeed.submit({"feature": "mockup_surface", "image": "https://cdn.test/photo.png"})
    assert group.startswith("ms-")
    (m1, p1), (m2, p2) = ws["submits"]
    assert m1 == "wavespeed-ai/depth-anything-v3/image" and p1 == {"image": "https://cdn.test/photo.png", "colormap": "grayscale", "output_format": "png"}
    assert m2 == "wavespeed-ai/image-background-remover" and p2 == {"image": "https://cdn.test/photo.png", "output_format": "png"}
    real_read = wavespeed._read
    monkeypatch.setattr(wavespeed, "_read", lambda path: buf.getvalue() if path.endswith("_0.png") and "task2" in path else real_read(path))
    hist = (await wavespeed.poll(group))[f"ws:{group}"]
    assert hist["status"]["status_str"] == "completed"
    assert hist["outputs"]["ws"]["images"][0]["filename"].startswith("ws_task1")
    mask_ref = hist["outputs"]["mask"]["images"][0]
    import folder_paths
    mask = Image.open(io.BytesIO(real_read(os.path.join(folder_paths.get_output_directory(), "wavespeed", mask_ref["filename"]))))
    assert mask.getpixel((1, 0))[0] == 255 and mask.getpixel((0, 0))[0] == 0


async def test_mockup_surface_failure_propagates(ws):
    ws["status"] = "failed"
    group = await wavespeed.submit({"feature": "mockup_surface", "image": "https://cdn.test/photo.png"})
    hist = (await wavespeed.poll(group))[f"ws:{group}"]
    assert hist["status"]["status_str"] == "error"


def test_last_frame_and_concat_with_ffmpeg(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    clips = []
    for i, color in enumerate(["red", "blue"]):
        out = tmp_path / f"c{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={color}:s=64x64:d=0.5:r=10", "-pix_fmt", "yuv420p", str(out)], check=True)
        clips.append(str(out))
    wavespeed._last_frame(clips[0], str(tmp_path / "last.png"))
    assert (tmp_path / "last.png").stat().st_size > 0
    wavespeed._concat(clips, str(tmp_path / "all.mp4"))
    import av
    with av.open(str(tmp_path / "all.mp4")) as box:
        assert sum(1 for _ in box.decode(video=0)) == 9  # 5 + 5 - dropped first frame of clip 2


async def test_caption_route(ws, bot_client, fresh_user_dir):
    path = fresh_user_dir / "input" / "pic.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    ws["outputs"] = ["a red bicycle"]
    res = await bot_client.post("/comfyart/wavespeed/caption", json={"src": "/api/view?filename=pic.png&subfolder=&type=input"})
    assert res.status == 200, await res.text()
    assert (await res.json())["text"] == "a red bicycle"
    assert ws["submits"][0][0] == "wavespeed-ai/image-captioner"


async def test_llm_complete_uses_openai_compatible_endpoint(bot_client, monkeypatch):
    from conftest import write_settings
    seen = {}
    app = web.Application()

    async def models(request):
        return web.json_response({"data": [{"id": "my-model"}]})

    async def chat(request):
        seen.update(await request.json())
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"choices": [{"message": {"content": "hello there"}}]})

    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat)
    server = TestServer(app)
    await server.start_server()
    try:
        write_settings(**{"enable-mcp": True, "enable-bot": True, "bot-local-llm-url": str(server.make_url("/v1")),
                          "bot-model-local-llm": ""})  # #120: no saved model -> first model the endpoint lists
        monkeypatch.setenv("COMFYART_LOCAL_LLM_API_KEY", "llm-test")
        res = await bot_client.post("/comfyart/llm/complete", json={"text": "hi", "system": "be brief", "images": []})
        assert res.status == 200, await res.text()
        assert (await res.json())["text"] == "hello there"
        assert seen["model"] == "my-model" and seen["messages"][0] == {"role": "system", "content": "be brief"} and seen["auth"] == "Bearer llm-test"
    finally:
        await server.close()


def test_picker_short_label_and_subtitle():
    ws = wavespeed
    assert ws.short_label("openai/gpt-image-2.5-flare/text-to-image") == "gpt-image-2.5-flare"
    assert ws.short_label("alibaba/qwen-image-3.0/text-to-image") == "qwen-image-3.0"
    assert ws.short_label("wavespeed-ai/z-image/turbo") == "z-image turbo"
    assert ws.short_label("ideogram-ai/ideogram-v4.5") == "ideogram-v4.5"
    assert ws.subtitle("google/nano-banana-2.1/text-to-image", None) == "nano-banana-2.1/text-to-image"
    assert ws.subtitle("x/y", "Flux.2 Klein 9B") == "Flux.2 Klein 9B"


def test_grouped_models_never_uses_local_name(monkeypatch):
    import asyncio
    ws = wavespeed
    async def no_catalog(refresh=False):
        raise ws.WaveSpeedError("offline")
    monkeypatch.setattr(ws, "catalog", no_catalog)
    out = asyncio.run(ws.grouped_models())
    m = out["text_to_image"]["models"][0]
    assert m["label"] == "qwen-image-3.0" and m["subtitle"] == "qwen-image-3.0/text-to-image"
    assert "2512" not in str({k: v for k, v in m.items() if k != "local_equivalent"})


CUSTOM = {"model": "acme/my-edit", "fields": {"@image": "input_image", "@prompt": "instruction", "@size": "dims"}, "params": {"strength": 0.4}}


async def test_custom_workflow_check(ws):
    meta = await wavespeed.catalog()
    ok = wavespeed.check_custom(CUSTOM, ["image", "prompt"], ["size"], meta)
    assert ok["ok"] and ok["errors"] == [] and ok["fields"]["image"] == "input_image"
    # unmapped image + missing required param + bad field + unknown model
    bad = wavespeed.check_custom({"model": "acme/my-edit", "fields": {"@prompt": "nope"}}, ["image", "prompt"], [], meta)
    codes = {c["code"]: c for c in bad["codes"]}
    assert codes["missingFields"]["markers"] == ["@image"] and codes["requiredParams"]["params"] == ["input_image", "instruction"] and "strength" not in codes["requiredParams"]["params"] and codes["badField"]["field"] == "nope"
    assert wavespeed.check_custom({"model": "made/up"}, ["image"], [], meta)["codes"] == [{"code": "unknownModel", "model": "made/up"}]
    assert wavespeed.check_custom({"model": "noslash"}, ["image"], [], meta)["codes"][0]["code"] == "badModelId"
    assert not bad["ok"] and any("@image" in e for e in bad["errors"]) and not any("strength" in e for e in bad["errors"]) and any("'nope'" in e for e in bad["errors"])
    assert not wavespeed.check_custom({"model": "made/up"}, ["image"], [], meta)["ok"]
    assert not wavespeed.check_custom({"model": "noslash"}, ["image"], [], meta)["ok"]
    # unknown or unused markers only warn; a curated model maps automatically
    warn = wavespeed.check_custom({"model": T2I, "fields": {"@foo": "prompt", "@mask": "prompt"}}, ["prompt", "size"], [], meta)
    assert warn["ok"] and len(warn["warnings"]) == 2
    assert ws["submits"] == []  # checking never submits a paid task


async def test_custom_workflow_submit_maps_fields(ws):
    import folder_paths
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    wavespeed._write(os.path.join(folder_paths.get_input_directory(), "c.png"), b"img")
    await wavespeed.submit({"feature": "image_edit", "custom": True, "image": "c.png [input]", "prompt": "make it blue", "width": 640, "height": 480, **CUSTOM})
    model, payload = ws["submits"][0]
    assert model == "acme/my-edit"
    assert payload == {"input_image": "https://cdn.test/up1.png", "instruction": "make it blue", "dims": "640*480", "strength": 0.4}
    # without the custom flag the non-curated model is still rejected
    with pytest.raises(wavespeed.WaveSpeedError):
        await wavespeed.submit({"feature": "image_edit", "model": "acme/my-edit", "image": "c.png [input]", "prompt": "x"})
    with pytest.raises(wavespeed.WaveSpeedError):
        await wavespeed.submit({"feature": "image_edit", "custom": True, "model": "made/up", "prompt": "x"})
    assert len(ws["submits"]) == 1


async def test_custom_workflow_check_route_and_tool(ws):
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/wavespeed/custom/check", json={"spec": CUSTOM, "required": ["image", "prompt"], "optional": ["size"]})
        body = await res.json()
        assert res.status == 200 and body["ok"] is True and KEY not in json.dumps(body)
        res = await client.post("/comfyart/wavespeed/custom/check", json={"spec": {"model": "acme/my-edit"}, "required": ["image"]})
        assert (await res.json())["ok"] is False
    finally:
        await client.close()
    assert set(canvas.SPECS["custom_workflow"]["inputSchema"]["properties"]["action"]["enum"]) == {"rules", "list", "check", "install", "assign"}


# --- #72 change_angle: a transient poll error must not fail an already-charged task ---

async def test_poll_timeout_then_success_single_submit(ws, monkeypatch):
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    real_get = aiohttp.ClientSession.get
    calls = {"n": 0}

    def flaky_get(self, url, *a, **k):
        if "/predictions/" in str(url) and calls["n"] == 0:
            calls["n"] += 1
            raise asyncio.TimeoutError()
        return real_get(self, url, *a, **k)

    monkeypatch.setattr(aiohttp.ClientSession, "get", flaky_get)
    first = (await wavespeed.poll(task))[f"ws:{task}"]["status"]
    assert first["completed"] is False and first["status_str"] == "processing" and not first["messages"]
    assert wavespeed._jobs[task]["errors"] == 1
    wavespeed._jobs[task]["next_poll"] = 0
    hist = (await wavespeed.poll(task))[f"ws:{task}"]
    assert hist["status"]["completed"] is True and hist["status"]["status_str"] == "completed"
    assert hist["outputs"]["ws"]["images"]
    assert len(ws["submits"]) == 1


async def test_poll_5xx_backs_off_then_success(ws):
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    ws["result_status"] = 503
    for _ in range(3):
        wavespeed._jobs[task]["next_poll"] = 0
        assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["status_str"] == "processing"
    assert wavespeed._jobs[task]["errors"] == 3
    ws["result_status"] = 200
    wavespeed._jobs[task]["next_poll"] = 0
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["status_str"] == "completed"
    assert len(ws["submits"]) == 1


def test_backoff_is_capped(monkeypatch):
    monkeypatch.setattr(wavespeed, "POLL_MIN", 2.0)
    job = {"errors": 0}
    waits = []
    for _ in range(6):
        wavespeed._backoff("t", job, 100.0, "x")
        waits.append(job["next_poll"] - 100.0)
    assert waits == [2.0, 4.0, 8.0, 15.0, 15.0, 15.0]


async def test_poll_401_still_fails(ws):
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    ws["result_status"] = 401
    st = (await wavespeed.poll(task))[f"ws:{task}"]["status"]
    assert st["status_str"] == "error" and st["completed"] is True
    assert len(ws["submits"]) == 1


async def test_transient_errors_still_hit_job_timeout(ws, monkeypatch):
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    ws["result_status"] = 502
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["status_str"] == "processing"
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    msgs = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"]
    assert "timed out" in msgs[0][1]["exception_message"]
    assert len(ws["submits"]) == 1


async def test_download_5xx_retries_without_resubmit(ws, monkeypatch):
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    real_get = aiohttp.ClientSession.get
    calls = {"n": 0}

    class Bad:
        status = 502
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    def flaky_get(self, url, *a, **k):
        if "/cdn/" in str(url) and calls["n"] == 0:
            calls["n"] += 1
            return Bad()
        return real_get(self, url, *a, **k)

    monkeypatch.setattr(aiohttp.ClientSession, "get", flaky_get)
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["status_str"] == "processing"
    wavespeed._jobs[task]["next_poll"] = 0
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["status_str"] == "completed"
    assert len(ws["submits"]) == 1


async def test_run_raw_survives_timeout(ws, monkeypatch):
    real_get = aiohttp.ClientSession.get
    calls = {"n": 0}

    def flaky_get(self, url, *a, **k):
        if "/predictions/" in str(url) and calls["n"] == 0:
            calls["n"] += 1
            raise aiohttp.ClientConnectionError("blip")
        return real_get(self, url, *a, **k)

    monkeypatch.setattr(aiohttp.ClientSession, "get", flaky_get)
    out = await wavespeed.run_raw({"feature": "text_to_image", "prompt": "x"}, timeout=5)
    assert out and len(ws["submits"]) == 1


async def test_history_route_survives_download_5xx(ws, monkeypatch):
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    real_get = aiohttp.ClientSession.get
    calls = {"n": 0}

    class Bad:
        status = 502
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    def flaky_get(self, url, *a, **k):
        if "/cdn/" in str(url) and calls["n"] == 0:
            calls["n"] += 1
            return Bad()
        return real_get(self, url, *a, **k)

    try:
        task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
        monkeypatch.setattr(aiohttp.ClientSession, "get", flaky_get)
        res = await client.get(f"/comfyart/wavespeed/history/{task}")
        assert res.status == 200  # a non-2xx here makes src/comfy.ts mark the job failed
        assert (await res.json())[f"ws:{task}"]["status"]["status_str"] == "processing"
        wavespeed._jobs[task]["next_poll"] = 0
        res = await client.get(f"/comfyart/wavespeed/history/{task}")
        assert (await res.json())[f"ws:{task}"]["status"]["status_str"] == "completed"
        assert len(ws["submits"]) == 1
    finally:
        await client.close()


async def test_estimate_uses_documented_price_endpoint_and_caches(ws):
    model = "wavespeed-ai/minimax-h3/text-to-video"
    ws["prices"][model] = lambda inputs: 0.1 * inputs.get("duration", 1)
    job = {"feature": "text_to_video", "prompt": "waves", "duration": 5, "resolution": "768p", "ratio": "16:9", "width": 9, "image": "x"}
    est = await wavespeed.estimate(job)
    assert est["price"] == pytest.approx(0.5) and est["source"] == "quote" and est["confirm"] is True and est["confirm_usd"] == 0.5
    assert ws["quotes"][0] == {"model_id": model, "inputs": {"duration": 5, "resolution": "768p", "aspect_ratio": "16:9"}}
    await wavespeed.estimate(job)
    assert len(ws["quotes"]) == 1  # cached for 5 minutes
    wavespeed._quotes.update({k: (v[0], v[1] - 301) for k, v in wavespeed._quotes.items()})
    await wavespeed.estimate(job)
    assert len(ws["quotes"]) == 2


async def test_estimate_falls_back_to_catalog_price_marked_as_estimate(ws):
    est = await wavespeed.estimate({"feature": "music", "model": "elevenlabs/music-v2", "prompt": "x"})
    assert est == {"price": 0.75, "currency": "USD", "source": "estimate", "confirm_usd": 0.5, "confirm": True}  # #159


async def test_storyboard_estimate_is_the_total(ws):
    ws["prices"]["wavespeed-ai/minimax-h3/text-to-video"] = 0.2
    ws["prices"]["wavespeed-ai/minimax-h3/image-to-video"] = 0.15
    est = await wavespeed.estimate({"feature": "text_to_video", "scenes": [{"prompt": "a"}, {"prompt": "b"}, {"prompt": "c"}]})
    assert est["price"] == pytest.approx(0.5) and est["confirm"] is True


async def test_confirm_threshold_setting(ws):
    """#397: confirm API is integer credits; confirm_usd() is credits/100 for backend comparison."""
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        assert (await (await client.get("/comfyart/wavespeed/confirm")).json()) == {"confirm_credits": 50}
        for bad in (-1, "1", True, None, 1e9, 0.5, 1.5):
            assert (await client.put("/comfyart/wavespeed/confirm", json={"confirm_credits": bad})).status == 400
        assert (await client.put("/comfyart/wavespeed/confirm", json={"confirm_credits": 100})).status == 200
        assert wavespeed.confirm_credits() == 100 and wavespeed.confirm_usd() == 1.0
        job = {"feature": "music", "model": "elevenlabs/music-v2", "prompt": "epic", "duration": 30}
        await wavespeed.submit(job)  # $0.75 is under the new $1 (=100 credits) threshold
        assert len(ws["submits"]) == 1
        await client.put("/comfyart/wavespeed/confirm", json={"confirm_credits": 0})
        res = await client.post("/comfyart/wavespeed/estimate", json={"inputs": {"feature": "text_to_speech", "text": "hi"}})
        assert (await res.json())["confirm"] is True  # 0 = always confirm
        with pytest.raises(wavespeed.WaveSpeedError) as e:
            await wavespeed.submit({"feature": "text_to_speech", "text": "hi"})
        assert e.value.status == 409
        assert (await client.post("/comfyart/wavespeed/estimate", json={"inputs": 3})).status == 400
    finally:
        await client.close()


# #119 upstream v1.0.1 music: default MiniMax Music 3, ACE-Step 1.5 optional; bpm/language/key only reach ACE-Step.
async def test_music_default_is_minimax_music3(ws):
    await wavespeed.submit({"feature": "music", "prompt": "lofi", "lyrics": "[verse] hi", "duration": 30})
    (m, p), = ws["submits"]
    assert m == "minimax/music-3.0"
    assert not {"bpm", "language", "keyscale", "key", "tags"} & set(p)


async def test_music_minimax_ignores_ace_settings(ws):
    await wavespeed.submit({"feature": "music", "model": "minimax/music-3.0", "prompt": "lofi", "lyrics": "", "duration": 30})
    (m, p), = ws["submits"]
    assert m == "minimax/music-3.0" and p["prompt"] == "lofi" and not {"bpm", "language", "keyscale", "tags"} & set(p)


async def test_music_ace_step_maps_bpm_language_key(ws):
    await wavespeed.submit({"feature": "music", "model": "wavespeed-ai/ace-step-1.5", "prompt": "lofi", "lyrics": "", "duration": 30,
                            "music": {"bpm": 92, "language": "zh", "key": "F minor"}})
    (m, p), = ws["submits"]
    assert m == "wavespeed-ai/ace-step-1.5"
    assert p["tags"] == "lofi, 92 bpm, language zh, key F minor"


def test_ace_music_fields_use_schema_fields_when_present():
    payload = {"tags": "lofi"}
    wavespeed._ace_music_fields({"tags": {}, "bpm": {}, "language": {}, "keyscale": {}}, {"bpm": "120", "language": "en", "key": "C major"}, payload)
    assert payload == {"tags": "lofi", "bpm": 120, "language": "en", "keyscale": "C major"}


async def test_quote_uses_rounded_duration_on_every_path(ws, monkeypatch):
    # #128: 7s is submitted as 10s on a 5/10/15 model, so every price path must quote 10s (per-second mock price)
    t2v = "wavespeed-ai/minimax-h3/text-to-video"
    meta = next(m for m in MODELS if m["model_id"] == t2v)
    monkeypatch.setitem(meta["api_schema"]["api_schemas"][0]["request_schema"]["properties"], "duration", {"type": "integer", "enum": [5, 10, 15]})
    ws["prices"][t2v] = lambda inputs: 0.06 * inputs.get("duration", 0)
    job = {"feature": "text_to_video", "model": t2v, "prompt": "waves", "duration": 7}
    p7, _ = await wavespeed.quote(t2v, job)
    p5, _ = await wavespeed.quote(t2v, {**job, "duration": 5})
    assert p7 == pytest.approx(0.6) and p7 > p5 == pytest.approx(0.3)
    assert (await wavespeed.estimate(job))["price"] == pytest.approx(0.6)
    board = await wavespeed.estimate({**job, "scenes": [{"prompt": "a", "duration": 7}]})
    assert board["price"] == pytest.approx(0.6) and board["source"] == "quote"
    assert all(q["inputs"]["duration"] in (5, 10) for q in ws["quotes"] if q["model_id"] == t2v)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.confirm == pytest.approx(0.6) and not ws["submits"]


# #155: every WaveSpeed failure carries a kind so the UI shows a readable zh/en message instead of the raw text.
@pytest.mark.parametrize("code,error,kind", [
    (1407, "insufficient_credits", "insufficientCredit"),
    (1200, "The content contains sensitive information.", "moderation"),
    (1403, "Task Execution Failed: raw upstream trace", "failed"),
])
async def test_failed_task_kind(ws, code, error, kind):
    ws.update(status="failed", task_code=code, task_error=error)
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    info = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"][0][1]
    assert info["ws_kind"] == kind
    if kind == "insufficientCredit":
        assert "nothing was charged" in info["exception_message"] and wavespeed.TOP_UP_URL in info["exception_message"]


@pytest.mark.parametrize("status,code,message,kind", [
    (402, 402, "nope", "insufficientCredit"),
    (400, 1407, "insufficient_credits", "insufficientCredit"),
    (403, 403, "Insufficient balance", "insufficientCredit"),
    (403, 403, "insufficient permissions", "failed"),
    (400, 1401, "balance must be a number", "failed"),
    (400, 1401, "credit field is invalid", "failed"),
    (400, 1200, "The content contains sensitive information.", "moderation"),
    (429, 429, "Too Many Requests", "rateLimit"),
    (401, 401, "Unauthorized", "invalidKey"),
    (500, 5000, "Internal Error xyz", "failed"),
])
async def test_submit_error_kind_reaches_route(ws, status, code, message, kind):
    ws.update(submit_status=status, submit_code=code, submit_message=message)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert e.value.kind == kind
    body = json.loads(wavespeed._respond_error(e.value).body)
    assert body["error"]["kind"] == kind
    assert not ws["submits"]  # nothing was submitted, so nothing was charged


def test_error_kind_1407_is_insufficient_credit():
    # https://wavespeed.ai/docs/error-codes: 1407 insufficient_credits
    assert wavespeed.error_kind(None, 1407) == "insufficientCredit"
    assert wavespeed.error_kind(None, "1200") == "moderation"
    assert wavespeed.error_kind(500, None, "boom") == "failed"
    # narrowed: bare "balance"/"credit" is not enough
    assert wavespeed.error_kind(400, 1401, "balance must be a number") == "failed"
    assert wavespeed.error_kind(400, None, "credit field is invalid") == "failed"
    assert wavespeed.error_kind(400, None, "Insufficient credits") == "insufficientCredit"


# --- #170: one mock error case per modality (image / video / audio / 3D) -------------------------------------------
# WaveSpeed fails -> the job carries a #161 kind, the UI shows that kind's zh/en copy, never the raw WaveSpeed text,
# and nothing is resubmitted (no second charge). The kind -> copy mapping itself is covered in test_ws_errors.py.
RAW = "Internal Error xyz-7781"


def _copy(kind):
    from pathlib import Path
    root = Path(wavespeed.__file__).resolve().parent.parent / "src" / "locales"
    return [json.loads((root / f"{lang}.json").read_text())[f"wsErr.{kind}"] for lang in ("zh", "en")]


def _shown(kind):
    # mirrors src/comfy.ts: wsErrorText(ws_kind) ?? exception_message
    texts = _copy(kind)
    assert all(t and RAW not in t and "xyz" not in t for t in texts)
    return texts


async def test_170_image_task_failed_is_readable(ws):
    ws["status"], ws["task_error"] = "failed", RAW
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    hist = (await wavespeed.poll(task))[f"ws:{task}"]
    info = hist["status"]["messages"][0][1]
    assert hist["status"]["completed"] is True and hist["status"]["status_str"] == "error"
    assert info["ws_kind"] == "failed" and _shown("failed")[0] == "WaveSpeed 没能完成这次任务，请检查输入后再试。"
    assert (await wavespeed.poll(task)) == {f"ws:{task}": hist} and len(ws["submits"]) == 1  # cached, not resubmitted


async def test_170_video_insufficient_balance_on_submit(ws):
    # #164: an unpriced tier now stops at the confirm step before submit, so mock a cheap live price for the
    # model and keep the same non-default tier (duration 5); the job then reaches submit and the 402/1407 path is what this test exercises
    ws["prices"][wavespeed.resolve_model("text_to_video", None)] = 0.05
    ws["submit_status"], ws["submit_code"], ws["submit_message"] = 402, 1407, RAW
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_video", "prompt": "waves", "duration": 5})
    assert not e.value.unpriced and e.value.confirm is None
    assert e.value.kind == "insufficientCredit" and e.value.status == 402 and RAW not in str(e.value)
    body = json.loads(wavespeed._respond_error(e.value).body)["error"]
    assert body["kind"] == "insufficientCredit" and ws["submits"] == [] and not wavespeed._jobs
    zh, en = _shown("insufficientCredit")
    assert "本次未扣费" in zh and "Nothing was charged" in en


async def test_170_audio_task_moderation_is_readable(ws):
    ws["status"], ws["task_error"], ws["task_code"] = "failed", RAW, 1200
    task = await wavespeed.submit({"feature": "generate_sound_effect", "prompt": "door slam", "duration": 3})
    info = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"][0][1]
    assert info["ws_kind"] == "moderation" and len(ws["submits"]) == 1
    zh, en = _shown("moderation")
    assert "没有生成" in zh and "Nothing was generated" in en


async def test_170_3d_submit_server_error_is_readable(ws):
    ws["submit_status"], ws["submit_message"] = 500, RAW
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "image_to_3d", "image": _input_png()})
    body = json.loads(wavespeed._respond_error(e.value).body)["error"]
    assert body["kind"] == "failed" and e.value.status == 502 and ws["submits"] == []
    _shown("failed")


async def test_170_task_timeout_has_readable_kind(ws, monkeypatch):
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    info = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"][0][1]
    assert "timed out" in info["exception_message"]
    assert info.get("ws_kind") == "timeout"  # #174


def test_insufficient_permissions_is_not_balance():
    # #163 review: "insufficient" alone is not enough; it must name balance or credit (402 / 1407 unchanged)
    assert wavespeed.error_kind(403, None, "insufficient permissions") != "insufficientCredit"
    assert wavespeed.error_kind(400, None, "Insufficient credits") == "insufficientCredit"
    assert wavespeed.error_kind(400, None, "insufficient balance") == "insufficientCredit"
    assert wavespeed.error_kind(402, None, "whatever") == "insufficientCredit"
    assert wavespeed.error_kind(400, 1407, "whatever") == "insufficientCredit"


# #509 YuE2 + schema-driven music length.
YUE2 = "wavespeed-ai/yue2-3b/text-to-music"


async def test_music_yue2_maps_style_lyrics_seed_and_drops_duration(ws):
    await wavespeed.submit({"feature": "music", "model": YUE2, "prompt": "mandarin pop, female vocal", "lyrics": "[verse] 你好\n[chorus] 再见", "seed": 7, "duration": 600})
    await wavespeed.submit({"feature": "generate_music", "model": YUE2, "prompt": "lofi", "lyrics": "", "duration": 30})
    (m1, p1), (m2, p2) = ws["submits"]
    assert m1 == YUE2 and p1 == {"style": "mandarin pop, female vocal", "lyrics": "[verse] 你好\n[chorus] 再见", "seed": 7}
    # empty lyrics -> [instrumental]; the duration is ignored, not an error
    assert m2 == YUE2 and p2 == {"style": "lofi", "lyrics": "[instrumental]"}


def test_music_duration_range_comes_from_the_schema():
    props = lambda m: wavespeed._schema(next(x for x in MODELS if x["model_id"] == m))["properties"]
    assert wavespeed.duration_range(props("wavespeed-ai/ace-step-1.5")) == {"min": 5, "max": 240, "step": 1}
    assert wavespeed._caps(wavespeed._schema(next(x for x in MODELS if x["model_id"] == "wavespeed-ai/ace-step-1.5")))["duration_range"]["max"] == 240
    # no duration field (YuE2, MiniMax music-3.0) -> no slider
    assert wavespeed.duration_range(props(YUE2)) is None
    assert wavespeed.duration_range(props("minimax/music-3.0")) is None
    assert "duration_range" not in wavespeed._caps(wavespeed._schema(next(x for x in MODELS if x["model_id"] == YUE2)))
    # an enum duration is a picker, not a range; a free field without bounds has no range either
    assert wavespeed.duration_range({"duration": {"type": "integer", "enum": [3, 4, 5]}}) is None
    assert wavespeed.duration_range({"duration": {"type": "number"}}) is None
    # schema step and default are kept; music_length_ms is converted to seconds
    assert wavespeed.duration_range({"duration": {"type": "integer", "minimum": 10, "maximum": 600, "step": 10, "default": 60}}) == {"min": 10, "max": 600, "step": 10, "default": 60}
    assert wavespeed.duration_range({"music_length_ms": {"type": "integer", "minimum": 3000, "maximum": 300000}}) == {"min": 3, "max": 300, "step": 1}


async def test_custom_music_workflow_checks_and_maps_lyrics(ws):
    meta = await wavespeed.catalog()
    # YuE2 needs no mapping: @prompt goes to style, @lyrics to lyrics
    ok = wavespeed.check_custom({"model": YUE2}, ["prompt"], ["lyrics", "seconds"], meta)
    assert ok["ok"], ok
    await wavespeed.submit({"feature": "music", "custom": True, "model": YUE2, "fields": {"@lyrics": "lyrics"}, "prompt": "folk", "lyrics": "[verse] la", "duration": 40})
    (m, p), = ws["submits"]
    assert m == YUE2 and p == {"style": "folk", "lyrics": "[verse] la"}


# #509 PR1 QA: payloads actually posted to WaveSpeed.
async def test_qa_music_ace_241_and_3_clamped_minimax_yue2_no_duration(ws):
    ace = "wavespeed-ai/ace-step-1.5"
    await wavespeed.submit({"feature": "music", "model": ace, "prompt": "lofi", "lyrics": "[verse] hi", "duration": 241})
    await wavespeed.submit({"feature": "music", "model": ace, "prompt": "lofi", "lyrics": "[verse] hi", "duration": 3})
    await wavespeed.submit({"feature": "music", "model": "minimax/music-3.0", "prompt": "pop", "lyrics": "[verse] hi", "duration": 180})
    await wavespeed.submit({"feature": "music", "model": YUE2, "prompt": "folk", "lyrics": "", "duration": 180})
    (_, a), (_, b), (m3, c), (m4, d) = ws["submits"]
    assert a == {"tags": "lofi", "lyrics": "[verse] hi", "duration": 240} and b == {"tags": "lofi", "lyrics": "[verse] hi", "duration": 5}
    assert m3 == "minimax/music-3.0" and c == {"prompt": "pop", "lyrics": "[verse] hi"}
    assert m4 == YUE2 and d == {"style": "folk", "lyrics": "[instrumental]"}  # style always sent; empty lyrics -> [instrumental]
    for p in (c, d):
        assert "duration" not in p and "music_length_ms" not in p


async def test_qa_music_without_custom_uses_default_path(ws):
    await wavespeed.submit({"feature": "music", "model": YUE2, "fields": {"@lyrics": "lyrics"}, "prompt": "folk", "lyrics": "[verse] la"})
    await wavespeed.submit({"feature": "music", "prompt": "folk"})
    (m1, p1), (m2, p2) = ws["submits"]
    assert m1 == YUE2 and p1 == {"style": "folk", "lyrics": "[verse] la"}  # no custom flag: fields ignored, normal mapping
    assert m2 == "minimax/music-3.0" and p2 == {"prompt": "folk"}
