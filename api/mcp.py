import json
import logging
import re
import uuid
from pathlib import Path

from aiohttp import web

from . import chat_store
from ._common import routes
from .mcp_tools import TOOLS, bot_tools
from .mcp_tools._context import BOT_CHAT_ID, PROJECT
from .settings import mcp_enabled

_log = logging.getLogger(__name__)

SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
VERSION = re.search(r'^version = "([^"]+)"', (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE).group(1)

INSTRUCTIONS = (
    "Window into ComfyArt, a design canvas running on this ComfyUI. Call "
    "get_canvas first. Every canvas tool is executed by the open ComfyArt page "
    "of the project; without that browser tab they fail with a timeout. "
    "Generation tools return ids at once: wait_generation on them, then "
    "view_canvas to check the result."
)


def _result(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _initialize(params: dict) -> dict:
    requested = params.get("protocolVersion")
    version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "comfyart-mcp", "title": "ComfyArt", "version": VERSION},
        "instructions": INSTRUCTIONS,
    }


def _tool_visible(name: str) -> bool:
    return name not in bot_tools.TOOLS or bool(BOT_CHAT_ID.get())


def _tools_list() -> dict:
    return {"tools": [{"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
                      for name, spec in TOOLS.items() if _tool_visible(name)]}


def _payload_to_content(payload) -> list[dict]:
    images = payload.pop("_images", None) if isinstance(payload, dict) else None
    blocks = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]
    for img in images or []:
        blocks.append({"type": "image", "data": img["data"], "mimeType": img.get("mime", "image/png")})
    return blocks


async def _tools_call(params: dict) -> dict | None:
    name = params.get("name")
    spec = TOOLS.get(name)
    if spec is None or not _tool_visible(name):
        return None
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}
    try:
        payload = await spec["handler"](arguments)
        return {"content": _payload_to_content(payload), "isError": False}
    except (ValueError, TypeError, KeyError) as e:
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    except Exception as e:
        _log.exception("[ComfyArt/mcp] tool %s failed", name)
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}


async def _dispatch(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        return _result(msg_id, _initialize(params))
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        return _result(msg_id, _tools_list())
    if method == "tools/call":
        outcome = await _tools_call(params)
        if outcome is None:
            return _error(msg_id, -32602, f"unknown tool {params.get('name')!r}")
        return _result(msg_id, outcome)
    if method == "resources/list":
        return _result(msg_id, {"resources": []})
    if method == "resources/templates/list":
        return _result(msg_id, {"resourceTemplates": []})
    if method == "prompts/list":
        return _result(msg_id, {"prompts": []})
    return _error(msg_id, -32601, f"method not found: {method}")


@routes.post("/comfyart/mcp")
async def mcp_post(request: web.Request) -> web.Response:
    if not mcp_enabled():
        return web.json_response(_error(None, -32000, "ComfyArt MCP is off: turn it on in Agent settings"), status=403)
    try:
        msg = await request.json()
    except ValueError:
        return web.json_response(_error(None, -32700, "parse error"), status=400)
    if isinstance(msg, list):
        return web.json_response(_error(None, -32600, "batch requests are not supported"), status=400)
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return web.json_response(_error(None, -32600, "invalid JSON-RPC 2.0 message"), status=400)
    chat_id = str(request.query.get("bot_chat") or "")
    chat = chat_store.get_chat(chat_id) if chat_id else None
    chat_token = BOT_CHAT_ID.set(chat_id if chat else "")
    project_token = PROJECT.set(chat["project"] if chat else str(request.query.get("project") or ""))
    try:
        response = await _dispatch(msg)
    finally:
        BOT_CHAT_ID.reset(chat_token)
        PROJECT.reset(project_token)
    if response is None:
        return web.Response(status=202)
    http_response = web.json_response(response)
    if msg.get("method") == "initialize" and "result" in response:
        http_response.headers["Mcp-Session-Id"] = uuid.uuid4().hex
    return http_response


@routes.get("/comfyart/mcp")
async def mcp_get(_request: web.Request) -> web.Response:
    return web.json_response({"error": "SSE streams are not supported; POST JSON-RPC messages instead"}, status=405)


@routes.delete("/comfyart/mcp")
async def mcp_delete(_request: web.Request) -> web.Response:
    return web.Response(status=200)
