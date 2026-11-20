import asyncio
import json
import mimetypes
import os
import re
from urllib.parse import urlsplit

import aiohttp
import folder_paths
from aiohttp import web
from server import PromptServer

from ._common import error, json_body, routes

CLOUD = "https://cloud.comfy.org"
ANNOTATED = re.compile(r".+ \[(input|output|temp)\]$")
MODEL_SWAPS = {"flux-2-klein-9b-nvfp4.safetensors": "flux-2-klein-9b.safetensors"}
CLASS_SWAPS = {"ComfyArtPreciseUNETLoader": ("UNETLoader", {"weight_dtype": "default"})}
OUTPUT_KEYS = {"image": "images", "video": "videos", "audio": "audio"}
CLOUD_IMPORTS = {
    "qwen-image-2.1-qma-camera-angles.safetensors": ("loras", "https://huggingface.co/gribbliest/qwen-image-2.1-qma-camera-angles/blob/main/qwen-image-2.1-qma-camera-angles.safetensors"),
}

_uploaded: dict[tuple[str, int, int], str] = {}
_imported: dict[str, str] = {}


def _fail(cls: type[web.HTTPException], message: str) -> web.HTTPException:
    return cls(text=json.dumps({"error": {"message": message}}), content_type="application/json")


def _headers() -> dict[str, str]:
    key = os.environ.get("COMFY_API_KEY")
    if not key:
        raise _fail(web.HTTPBadRequest, "Comfy Cloud needs an API key: set COMFY_API_KEY from platform.comfy.org/profile/api-keys and restart ComfyUI")
    return {"Authorization": f"Bearer {key}"}


async def _upload(session: aiohttp.ClientSession, path: str) -> str:
    stat = os.stat(path)
    cache_key = (path, stat.st_mtime_ns, stat.st_size)
    if cache_key not in _uploaded:
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        form = aiohttp.FormData()
        form.add_field("content_type", content_type)
        form.add_field("file_path", "comfyart/" + os.path.basename(path))
        form.add_field("tags", '["input"]')
        with open(path, "rb") as f:
            form.add_field("file", f, filename=os.path.basename(path), content_type=content_type)
            async with session.post(f"{CLOUD}/api/v2/assets", data=form) as res:
                body = await res.json()
        if res.status >= 400:
            raise _fail(web.HTTPBadGateway, f"upload {os.path.basename(path)} failed: {res.status}")
        _uploaded[cache_key] = body["hash"].split(":", 1)[1] + os.path.splitext(path)[1]
    return _uploaded[cache_key]


async def _import(session: aiohttp.ClientSession, name: str) -> str:
    if name not in _imported:
        folder, url = CLOUD_IMPORTS[name]
        query = {"include_tags": f"models,{folder}", "name_contains": os.path.splitext(name)[0], "limit": "1"}
        async with session.get(f"{CLOUD}/api/assets", params=query) as res:
            found = (await res.json())["assets"]
        if found:
            _imported[name] = found[0]["loader_path"]
        else:
            async with session.post(f"{CLOUD}/api/assets/download", json={"source_url": url, "tags": ["models", folder]}) as res:
                task = await res.json()
            task_id = task["task_id"]
            while task.get("status") not in ("completed", "failed"):
                await asyncio.sleep(2)
                async with session.get(f"{CLOUD}/api/tasks/{task_id}") as res:
                    task = await res.json()
            if task["status"] == "failed":
                raise _fail(web.HTTPBadGateway, f"Comfy Cloud could not import {name} from {url}")
            _imported[name] = task["result"]["filename"]
    return _imported[name]


async def _cloud_graph(session: aiohttp.ClientSession, graph: dict) -> dict:
    out = {}
    for node_id, node in graph.items():
        class_type, extra = CLASS_SWAPS.get(node["class_type"], (node["class_type"], {}))
        inputs = {}
        for name, value in node["inputs"].items():
            if isinstance(value, str) and ANNOTATED.match(value):
                value = await _upload(session, folder_paths.get_annotated_filepath(value))
            elif isinstance(value, str) and value in CLOUD_IMPORTS:
                value = await _import(session, value)
            inputs[name] = MODEL_SWAPS.get(value, value) if isinstance(value, str) else value
        out[node_id] = {**node, "class_type": class_type, "inputs": {**inputs, **extra}}
    return out


async def _download(session: aiohttp.ClientSession, job_id: str, output: dict) -> dict:
    subfolder, name = os.path.split(output["name"])
    stem, ext = os.path.splitext(name)
    filename = f"{stem.rstrip('_')}_cloud-{job_id[:8]}{ext}"
    root = os.path.abspath(folder_paths.get_output_directory())
    path = os.path.abspath(os.path.join(root, subfolder, filename))
    if os.path.commonpath([root, path]) != root:
        raise _fail(web.HTTPBadGateway, f"unexpected output path {output['name']}")
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with session.get(CLOUD + urlsplit(output["url"]).path) as res:
            res.raise_for_status()
            data = await res.read()
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    return {"filename": filename, "subfolder": subfolder, "type": "output"}


def _history(prompt_id: str, status: str, messages: list, outputs: dict) -> web.Response:
    done = status in ("succeeded", "failed", "cancelled")
    return web.json_response({prompt_id: {"status": {"completed": done, "status_str": "error" if status == "failed" else status, "messages": messages}, "outputs": outputs}})


@routes.post("/comfyart/cloud/prompt")
async def cloud_prompt(request: web.Request) -> web.Response:
    graph = (await json_body(request)).get("prompt")
    if not isinstance(graph, dict):
        return error("prompt must be an object", 400)
    async with aiohttp.ClientSession(headers=_headers()) as session:
        workflow = await _cloud_graph(session, graph)
        async with session.post(f"{CLOUD}/api/v2/jobs", json={"workflow": workflow}) as res:
            body = await res.json()
    if res.status >= 400:
        return web.json_response(body, status=res.status)
    return web.json_response({"prompt_id": "cloud:" + body["id"]})


@routes.get("/comfyart/cloud/history/{job_id}")
async def cloud_history(request: web.Request) -> web.Response:
    job_id = request.match_info["job_id"]
    prompt_id = "cloud:" + job_id
    async with aiohttp.ClientSession(headers=_headers()) as session:
        async with session.get(f"{CLOUD}/api/v2/jobs/{job_id}") as res:
            if res.status == 404:
                return web.json_response({})
            res.raise_for_status()
            job = await res.json()
        status = job["status"]
        if status == "failed":
            return _history(prompt_id, status, [["execution_error", {"exception_message": (job.get("error") or {}).get("message", "Comfy Cloud job failed")}]], {})
        if status == "cancelled":
            return _history(prompt_id, status, [["execution_interrupted", {}]], {})
        if status != "succeeded":
            progress = job.get("progress") or {}
            if progress.get("steps"):
                PromptServer.instance.send_sync("progress", {"prompt_id": prompt_id, "value": progress.get("step", 0), "max": progress["steps"]})
            return _history(prompt_id, status, [], {})
        outputs: dict[str, dict] = {}
        for output in job.get("outputs") or []:
            key = OUTPUT_KEYS.get(output["content_type"].split("/")[0], "3d")
            outputs.setdefault(output["node_id"], {}).setdefault(key, []).append(await _download(session, job_id, output))
    return _history(prompt_id, status, [], outputs)


@routes.post("/comfyart/cloud/cancel/{job_id}")
async def cloud_cancel(request: web.Request) -> web.Response:
    async with aiohttp.ClientSession(headers=_headers()) as session:
        async with session.post(f"{CLOUD}/api/v2/jobs/{request.match_info['job_id']}/cancel") as res:
            return web.json_response({}, status=200 if res.status < 400 else res.status)
