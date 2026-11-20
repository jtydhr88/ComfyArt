from __future__ import annotations

import asyncio

import folder_paths
import pytest
from conftest import SENT
from aiohttp import web
from aiohttp.test_utils import TestServer

from ComfyArt.api import cloud

JOB = "966a002f-a5ee-40ae-836f-0850cea02eae"


@pytest.fixture
async def fake_cloud(monkeypatch, fresh_user_dir):
    seen: dict = {"uploads": [], "jobs": [], "imports": []}
    state = {"status": "running", "progress": {"step": 3, "steps": 25}}
    app = web.Application()

    async def upload(request: web.Request):
        reader = await request.multipart()
        fields = []
        async for part in reader:
            fields.append(part.name)
            await part.read()
        seen["uploads"].append(fields)
        return web.json_response({"hash": "blake3:abc123"})

    async def submit(request: web.Request):
        seen["auth"] = request.headers["Authorization"]
        seen["jobs"].append((await request.json())["workflow"])
        return web.json_response({"id": JOB, "status": "queued"}, status=201)

    async def job(request: web.Request):
        if request.match_info["id"] != JOB:
            return web.json_response({}, status=404)
        if state["status"] == "succeeded":
            out = [{"node_id": "9", "name": "comfyart/image_00001_.png", "content_type": "image/png", "url": "http://cloud.comfy.org/content"}]
            return web.json_response({"id": JOB, "status": "succeeded", "outputs": out})
        if state["status"] == "failed":
            return web.json_response({"id": JOB, "status": "failed", "error": {"message": "CUDA out of memory"}})
        return web.json_response({"id": JOB, "status": "running", "progress": state["progress"]})

    async def assets(request: web.Request):
        found = [{"loader_path": "hf__qma.safetensors"}] if state.get("imported") else []
        return web.json_response({"assets": found})

    async def download(request: web.Request):
        seen["imports"].append(await request.json())
        return web.json_response({"task_id": "t1", "status": "created"}, status=202)

    async def task(request: web.Request):
        state["imported"] = True
        return web.json_response({"id": "t1", "status": "completed", "result": {"filename": "hf__qma.safetensors"}})

    async def content(request: web.Request):
        if request.headers.get("Authorization") != "Bearer comfyui-test":
            return web.json_response({}, status=401)
        return web.Response(body=b"png-bytes")

    app.router.add_post("/api/v2/assets", upload)
    app.router.add_post("/api/v2/jobs", submit)
    app.router.add_get("/api/v2/jobs/{id}", job)
    app.router.add_get("/api/assets", assets)
    app.router.add_post("/api/assets/download", download)
    app.router.add_get("/api/tasks/{id}", task)
    app.router.add_get("/content", content)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(cloud, "CLOUD", str(server.make_url("")).rstrip("/"))
    monkeypatch.setattr(cloud, "_uploaded", {})
    monkeypatch.setattr(cloud, "_imported", {})
    real_sleep = asyncio.sleep
    monkeypatch.setattr(cloud.asyncio, "sleep", lambda s: real_sleep(0))
    monkeypatch.setenv("COMFY_API_KEY", "comfyui-test")
    image = fresh_user_dir / "input" / "comfyart" / "ref.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"ref")
    monkeypatch.setattr(folder_paths, "get_annotated_filepath", lambda name: str(fresh_user_dir / "input" / name.rsplit(" [", 1)[0]), raising=False)
    yield seen, state
    await server.close()


GRAPH = {
    "1": {"class_type": "ComfyArtPreciseUNETLoader", "inputs": {"unet_name": "qwen_image_2512_fp8_e4m3fn.safetensors"}},
    "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-9b-nvfp4.safetensors", "weight_dtype": "default"}},
    "3": {"class_type": "LoadImage", "inputs": {"image": "comfyart/ref.png [input]"}},
    "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": "comfyart/image"}},
}


async def test_submit_uploads_inputs_and_swaps_local_only_parts(bot_client, fake_cloud):
    seen, _ = fake_cloud
    res = await bot_client.post("/comfyart/cloud/prompt", json={"prompt": GRAPH})
    assert (await res.json()) == {"prompt_id": "cloud:" + JOB}
    assert seen["auth"] == "Bearer comfyui-test"
    assert seen["uploads"] == [["content_type", "file_path", "tags", "file"]]
    wf = seen["jobs"][0]
    assert wf["1"] == {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2512_fp8_e4m3fn.safetensors", "weight_dtype": "default"}}
    assert wf["2"]["inputs"]["unet_name"] == "flux-2-klein-9b.safetensors"
    assert wf["3"]["inputs"]["image"] == "abc123.png"
    assert wf["4"] == GRAPH["4"]


async def test_cloud_missing_lora_is_imported_once(bot_client, fake_cloud):
    seen, state = fake_cloud
    graph = {"5": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "qwen-image-2.1-qma-camera-angles.safetensors", "strength_model": 1}}}
    await bot_client.post("/comfyart/cloud/prompt", json={"prompt": graph})
    cloud._imported.clear()
    await bot_client.post("/comfyart/cloud/prompt", json={"prompt": graph})
    assert [i["tags"] for i in seen["imports"]] == [["models", "loras"]]
    assert [j["5"]["inputs"]["lora_name"] for j in seen["jobs"]] == ["hf__qma.safetensors", "hf__qma.safetensors"]


async def test_history_reports_progress_then_downloads_outputs(bot_client, fake_cloud, fresh_user_dir):
    _, state = fake_cloud
    pid = "cloud:" + JOB
    running = (await (await bot_client.get(f"/comfyart/cloud/history/{JOB}")).json())[pid]
    assert running == {"status": {"completed": False, "status_str": "running", "messages": []}, "outputs": {}}
    assert ("progress", {"prompt_id": pid, "value": 3, "max": 25}) in SENT

    state["status"] = "succeeded"
    done = (await (await bot_client.get(f"/comfyart/cloud/history/{JOB}")).json())[pid]
    ref = {"filename": "image_00001_cloud-966a002f.png", "subfolder": "comfyart", "type": "output"}
    assert done == {"status": {"completed": True, "status_str": "succeeded", "messages": []}, "outputs": {"9": {"images": [ref]}}}
    assert (fresh_user_dir / "output" / "comfyart" / ref["filename"]).read_bytes() == b"png-bytes"


async def test_failed_job_carries_the_cloud_error(bot_client, fake_cloud):
    _, state = fake_cloud
    state["status"] = "failed"
    hist = (await (await bot_client.get(f"/comfyart/cloud/history/{JOB}")).json())["cloud:" + JOB]
    assert hist["status"]["messages"] == [["execution_error", {"exception_message": "CUDA out of memory"}]]
    assert hist["status"]["completed"] is True


async def test_unknown_job_is_empty_history(bot_client, fake_cloud):
    assert await (await bot_client.get("/comfyart/cloud/history/nope")).json() == {}


async def test_missing_key_explains_how_to_set_it(bot_client, monkeypatch):
    monkeypatch.delenv("COMFY_API_KEY", raising=False)
    res = await bot_client.post("/comfyart/cloud/prompt", json={"prompt": GRAPH})
    assert res.status == 400
    assert "COMFY_API_KEY" in (await res.json())["error"]["message"]
