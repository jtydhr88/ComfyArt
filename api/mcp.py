import json
import logging
import uuid

from aiohttp import web

from . import chat_store, paid_guard
from ._common import routes
from .mcp_tools import TOOLS, bot_tools
from .mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID, MCP_EXTERNAL, PROJECT
import hmac
import secrets

from .settings import mcp_enabled
from ..bot.guide import PAID_TOOLS

_log = logging.getLogger(__name__)

SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
DEFAULT_PROTOCOL_VERSION = "2025-06-18"

INSTRUCTIONS = (
    "Window into ComfyArt, a design canvas. Images, videos and audio are generated "
    "by cloud models called through WaveSpeed, and ComfyUI is only the host app. Call "
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
        "serverInfo": {"name": "comfyart-mcp", "title": "ComfyArt", "version": "0.1.0"},
        "instructions": INSTRUCTIONS,
    }


def _tool_visible(name: str) -> bool:
    return name not in bot_tools.TOOLS or bool(BOT_CHAT_ID.get())


def _payload_to_content(payload) -> list[dict]:
    images = payload.pop("_images", None) if isinstance(payload, dict) else None
    blocks = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]
    for img in images or []:
        blocks.append({"type": "image", "data": img["data"], "mimeType": img.get("mime", "image/png")})
    return blocks


def _wrap_paid_handler(name: str, original):
    """#730: direct handler() calls still hit before_call/after_call (no bot turn / no _tools_call)."""

    async def handler(arguments: dict):
        chat_id = paid_guard.resolve_guard_chat_id()
        if not chat_id or chat_id.startswith(paid_guard.NOTURN_PREFIX):
            chat_id = chat_id if chat_id.startswith(paid_guard.NOTURN_PREFIX) else paid_guard.noturn_key("anonymous")
            paid_guard.ensure_noturn(chat_id)
        external = bool(MCP_EXTERNAL.get())
        refused = paid_guard.before_call(chat_id, name, arguments, external=external)
        if refused:
            raise paid_guard.PaidRefused(refused)
        payload = await original(arguments)
        paid_guard.after_call(chat_id, name, arguments, payload, True)
        return payload

    handler._paid_inner = original  # type: ignore[attr-defined]
    return handler


def _install_paid_handler_guards() -> None:
    for name in PAID_TOOLS:
        spec = TOOLS.get(name)
        if not spec or spec.get("_paid_guarded"):
            continue
        spec["handler"] = _wrap_paid_handler(name, spec["handler"])
        spec["_paid_guarded"] = True


def _handler_inner(spec: dict):
    """Unwrap the #730 paid guard so _tools_call can apply before/after once for every tool."""
    handler = spec["handler"]
    return getattr(handler, "_paid_inner", handler)


_install_paid_handler_guards()


async def _tools_call(params: dict, *, external: bool = False) -> dict | None:
    name = params.get("name")
    spec = TOOLS.get(name)
    if spec is None or not _tool_visible(name):
        return None
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}
    chat_id = paid_guard.resolve_guard_chat_id()
    if chat_id.startswith(paid_guard.NOTURN_PREFIX):
        paid_guard.ensure_noturn(chat_id)
    # #142/#238/#730: guard every tool call when we have a chat or no-turn bucket.
    # Paid handlers are also wrapped for direct calls; use _paid_inner here to avoid double-counting.
    refused = paid_guard.before_call(chat_id, name, arguments, external=external) if chat_id else None
    if refused:
        return {"content": [{"type": "text", "text": refused}], "isError": True}
    try:
        payload = await _handler_inner(spec)(arguments)
        if chat_id:
            paid_guard.after_call(chat_id, name, arguments, payload, True)
        content = _payload_to_content(payload)
        if external and chat_id:
            content = paid_guard.clip_external_screenshots(chat_id, content)
        return {"content": content, "isError": False}
    except paid_guard.PaidRefused as e:
        return {"content": [{"type": "text", "text": e.message}], "isError": True}
    except (ValueError, TypeError, KeyError) as e:
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    except Exception as e:
        _log.exception("[ComfyArt/mcp] tool %s failed", name)
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}


async def _dispatch(msg: dict, *, external: bool = False) -> dict | None:
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
        outcome = await _tools_call(params, external=external)
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


def _tools_list() -> dict:
    return {"tools": [{"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
                      for name, spec in TOOLS.items() if _tool_visible(name)]}


# #219: the built-in agent calls this endpoint in-process with a per-process secret header, so it works while
# the external MCP switch is off; every other caller (local MCP clients, external tools) needs the switch on.
INTERNAL_HEADER = "X-ComfyArt-Internal"
INTERNAL_TOKEN = secrets.token_urlsafe(32)


def internal_request(request: web.Request) -> bool:
    return hmac.compare_digest(request.headers.get(INTERNAL_HEADER, ""), INTERNAL_TOKEN)


def _guard_key_for_request(request: web.Request) -> str:
    """No-turn bucket: prefer Mcp-Session-Id, else client IP (#730)."""
    session = (request.headers.get("Mcp-Session-Id") or "").strip()
    peer = (request.remote or "").strip()
    return paid_guard.noturn_key(session or peer or "anonymous")


@routes.post("/comfyart/mcp")
async def mcp_post(request: web.Request) -> web.Response:
    if not mcp_enabled() and not internal_request(request):
        return web.json_response(_error(None, -32000, "ComfyArt MCP is off: turn it on in Agent settings"), status=403)
    try:
        msg = await request.json()
    except ValueError:
        return web.json_response(_error(None, -32700, "parse error"), status=400)
    if isinstance(msg, list):
        return web.json_response(_error(None, -32600, "batch requests are not supported"), status=400)
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return web.json_response(_error(None, -32600, "invalid JSON-RPC 2.0 message"), status=400)

    raw_chat = str(request.query.get("bot_chat") or "").strip()
    if raw_chat:
        chat = chat_store.get_chat(raw_chat)
        if chat is None:
            # #730: forged/unknown bot_chat must not silently degrade to an unguarded call
            return web.json_response(
                _error(msg.get("id"), -32000, f"unknown bot_chat {raw_chat!r}"), status=403)
        bot_chat_id = raw_chat
        guard_id = raw_chat
        project = chat["project"]
    else:
        chat = None
        bot_chat_id = ""
        guard_id = _guard_key_for_request(request)
        paid_guard.ensure_noturn(guard_id)
        project = str(request.query.get("project") or "")

    external = not internal_request(request)
    chat_token = BOT_CHAT_ID.set(bot_chat_id)
    guard_token = GUARD_CHAT_ID.set(guard_id)
    project_token = PROJECT.set(project)
    external_token = MCP_EXTERNAL.set(external)
    try:
        response = await _dispatch(msg, external=external)
    finally:
        BOT_CHAT_ID.reset(chat_token)
        GUARD_CHAT_ID.reset(guard_token)
        PROJECT.reset(project_token)
        MCP_EXTERNAL.reset(external_token)
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
