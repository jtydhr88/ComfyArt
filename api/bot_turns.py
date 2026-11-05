import logging
import re

from server import PromptServer

from ..bot._cli_common import resolve_comfy_mcp_argv
from ..bot.turns import TurnRunner
from . import chat_store
from ._common import spawn
from .settings import SETTINGS_SPEC, get_setting

_log = logging.getLogger(__name__)


def broadcast(event: str, payload: dict) -> None:
    try:
        PromptServer.instance.send_sync("comfyart-bot", {"event": event, **payload})
    except Exception:
        _log.exception("[ComfyArt/bot] broadcast failed")


def _mcp_endpoint(chat_id: str) -> str:
    return f"http://127.0.0.1:{PromptServer.instance.port}/comfyart/mcp?bot_chat={chat_id}"


def _comfy_mcp_argv() -> list[str]:
    if not get_setting("bot-enable-comfy-mcp"):
        return []
    argv = resolve_comfy_mcp_argv(str(get_setting("bot-comfy-mcp-command") or ""))
    if not argv:
        _log.warning("[ComfyArt/bot] bot-enable-comfy-mcp is on but no "
                     "comfy-mcp executable was found — set "
                     "bot-comfy-mcp-command or install comfy-mcp on PATH")
    return argv


def provider_model(provider_id: str) -> str:
    key = f"bot-model-{provider_id}"
    return str(get_setting(key) or "").strip() if key in SETTINGS_SPEC else ""


def blocks_text(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        kind = b.get("type")
        if kind == "text":
            parts.append(str(b.get("text") or ""))
        elif kind in ("image", "video", "audio"):
            parts.append(f"[attached {kind}: {b.get('url') or ''}]")
        elif kind == "file":
            parts.append(f"[attached document {b.get('name') or ''}: {b.get('url') or ''}]")
        elif kind == "notice" and b.get("text"):
            parts.append(f"[notice: {b.get('text')}]")
    return "\n".join(p for p in parts if p.strip()).strip()


_WRITE_TOOL_RE = re.compile(
    r"\b(generate_image|generate_video|edit_image|animate_image|upscale_image|"
    r"remove_background|expand_image|split_layers|place_html|create_slides|"
    r"add_text|add_shape|create_frame|update_shapes|delete_shapes)\b")


def unverified_write_notice(blocks: list[dict]) -> dict | None:
    if any(b.get("type") == "tool_use" for b in blocks):
        return None
    text = "\n".join(str(b.get("text") or "") for b in blocks if b.get("type") == "text")
    if not _WRITE_TOOL_RE.search(text):
        return None
    return {"type": "notice", "level": "warn",
            "text": "This turn made no tool calls, so nothing it describes was "
                    "actually done — the canvas is unchanged."}


RUNNER = TurnRunner(
    label="ComfyArt", mcp_name="comfyart", store=chat_store, broadcast=broadcast, spawn=spawn,
    mcp_endpoint=_mcp_endpoint, comfy_mcp_argv=_comfy_mcp_argv, provider_model=provider_model,
    replay_text=blocks_text, finish_notice=unverified_write_notice,
)
ACTIVE_TURNS = RUNNER.active
QUEUED = RUNNER.queued
