import asyncio

from aiohttp import web
from server import PromptServer

from ..bot.command_relay import CommandRelay
from ._common import json_body, routes

DEFAULT_TIMEOUT_S = 20.0

RELAY = CommandRelay("comfyart-mcp-command", lambda event, data, sid: PromptServer.instance.send_sync(event, data, sid))
_pages: dict[str, str] = {}


def _open_pages() -> dict[str, str]:
    live = PromptServer.instance.sockets
    for client in [c for c in _pages if c not in live]:
        del _pages[client]
    return _pages


def _target(project: str) -> tuple[str, str]:
    pages = _open_pages()
    if project:
        clients = [c for c, p in pages.items() if p == project]
        if not clients:
            raise ValueError(f"project {project} is not open in any browser tab — open it in ComfyArt and retry")
        return clients[-1], project
    projects = list(dict.fromkeys(pages.values()))
    if not projects:
        raise ValueError("no ComfyArt project is open in a browser tab — open one and retry")
    if len(projects) > 1:
        raise ValueError(f"several ComfyArt projects are open ({', '.join(projects)}); connect with ?project=<id> to pick one")
    return _target(projects[0])


async def submit_command(action: str, payload: dict, project: str,
                         timeout: float = DEFAULT_TIMEOUT_S, chat: str = "") -> dict:
    client, project = _target(project)
    try:
        return await RELAY.submit({"action": action, "project": project, "chat": chat, "args": payload},
                                  sid=client, timeout=timeout)
    except asyncio.TimeoutError:
        if client not in _open_pages():
            raise ValueError(f"the ComfyArt tab of project {project} closed before {action!r} finished")
        raise ValueError(
            f"the ComfyArt page did not finish {action!r} within {timeout:.0f}s; it may still complete — "
            f"check get_canvas before retrying")


@routes.post("/comfyart/mcp_page")
async def register_page(request: web.Request) -> web.Response:
    body = await json_body(request)
    client, project = str(body.get("client_id") or ""), str(body.get("project") or "")
    if not client or not project:
        return web.json_response({"error": "client_id and project are required"}, status=400)
    _pages.pop(client, None)
    _pages[client] = project
    return web.json_response({"ok": True})


@routes.post("/comfyart/mcp_command_result")
async def post_command_result(request: web.Request) -> web.Response:
    out, status = RELAY.resolve(await json_body(request), "command failed in the ComfyArt page")
    return web.json_response(out, status=status)
