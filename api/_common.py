import asyncio
import json
import os
from typing import Any, Coroutine
from urllib.parse import parse_qs, urlparse

import folder_paths
from aiohttp import web
from server import PromptServer

routes = PromptServer.instance.routes

_TASKS: set[asyncio.Task] = set()


def spawn(coro: Coroutine[Any, Any, None], name: str) -> None:
    task = asyncio.create_task(coro, name=name)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


def app_path(*parts: str) -> str:
    return os.path.join(folder_paths.get_system_user_directory("comfyart"), *parts)


def request_user(request: web.Request) -> str:
    try:
        return PromptServer.instance.user_manager.get_request_user_id(request)
    except KeyError as e:
        raise web.HTTPForbidden(text=json.dumps({"error": str(e)}), content_type="application/json")


def error(message: str, status: int) -> web.Response:
    return web.json_response({"error": message}, status=status)


def bad_request(message: str) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(text=json.dumps({"error": message}), content_type="application/json")


async def json_body(request: web.Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        raise bad_request("invalid JSON body")
    if not isinstance(body, dict):
        raise bad_request("body must be an object")
    return body


def read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def view_path(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    name = (query.get("filename") or [""])[0]
    subfolder = (query.get("subfolder") or [""])[0]
    root = folder_paths.get_directory_by_type((query.get("type") or ["output"])[0])
    if not name or root is None:
        raise ValueError(f"not a ComfyUI file URL: {url}")
    root = os.path.abspath(root)
    path = os.path.abspath(os.path.join(root, subfolder, name))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        raise ValueError(f"file not found: {url}")
    return path
