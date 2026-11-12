import ipaddress

from aiohttp import web

from ._common import app_path, error, json_body, read_json, routes, write_json

SETTINGS_SPEC: dict[str, object] = {
    "enable-mcp": False,
    "enable-bot": False,
    "bot-provider": "",
    "bot-model-claude-code": "",
    "bot-model-codex": "",
    "bot-model-qwen-code": "",
    "bot-model-deepseek-harness": "",
    "bot-hermes-ssh-host": "",
    "bot-hermes-profile": "comfyart",
    "bot-model-hermes": "",
    "bot-local-llm-url": "",
    "bot-model-local-llm": "",
    "bot-enable-comfy-mcp": False,
    "bot-comfy-mcp-command": "",
    "ocr-engine": "local",
    "generation-backend": "local",
    "generation-target": "auto",
    "memory-enabled": True,
    "proactive-memory": False,
    "proactive-skills": False,
    "proactive-review": False,
    "proactive-daily": 5,
}

CHOICES: dict[str, tuple[str, ...]] = {"ocr-engine": ("local", "agent"), "generation-backend": ("local", "cloud")}

LOCAL_ONLY = ("enable-mcp", "enable-bot", "bot-enable-comfy-mcp", "bot-comfy-mcp-command", "bot-hermes-ssh-host")


def _file() -> str:
    return app_path("settings.json")


def all_settings() -> dict:
    saved = read_json(_file(), {})
    return {k: saved.get(k, default) for k, default in SETTINGS_SPEC.items()}


def get_setting(key: str):
    return all_settings()[key]


def mcp_enabled() -> bool:
    return bool(get_setting("enable-mcp"))


def bot_enabled() -> bool:
    return mcp_enabled() and bool(get_setting("enable-bot"))


def bot_disabled() -> web.Response:
    return error("the ComfyArt Agent is off: turn on MCP and the Agent in Agent settings", 403)


@routes.get("/comfyart/settings")
async def get_settings(_request: web.Request) -> web.Response:
    return web.json_response(all_settings())


@routes.put("/comfyart/settings")
async def put_settings(request: web.Request) -> web.Response:
    body = await json_body(request)
    unknown = [k for k in body if k not in SETTINGS_SPEC]
    if unknown:
        return error(f"unknown settings: {', '.join(unknown)}", 400)
    for key, value in body.items():
        if type(value) is not type(SETTINGS_SPEC[key]):
            return error(f"{key} must be a {type(SETTINGS_SPEC[key]).__name__}", 400)
        if key in CHOICES and value not in CHOICES[key]:
            return error(f"{key} must be one of {', '.join(CHOICES[key])}", 400)
    current = all_settings()
    if not ipaddress.ip_address(request.remote).is_loopback:
        blocked = [k for k in LOCAL_ONLY if k in body and body[k] != current[k]]
        if blocked:
            return error(f"{', '.join(blocked)} can only be changed from the machine running ComfyUI", 403)
    current.update(body)
    write_json(_file(), current)
    return web.json_response(current)
