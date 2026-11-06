"""Paid-generation guard shared by every agent provider (#142).

Every provider (Local LLM, Claude Code, Codex, Qwen Code, DeepSeek...) reaches
the paid tools through the same MCP endpoint (``/comfyart/mcp?bot_chat=...``),
whose handlers relay the run to WaveSpeed. ``api/mcp.py`` asks this module
before a paid tool runs, so the rules hold for all of them:

* per turn, each update_plan item gets at most 4 paid images, or exactly N
  when the user named a count; declined, cancelled and failed runs don't count.
  Past the cap nothing is submitted, the turn is stopped and ends with the
  localized stop notice (same red notice and language plumbing as #137);
* after the user declines a cost confirm on a plan item, further paid calls for
  that same item are refused without opening another dialog (#127); the tool
  result tells the agent to reply as normal chat text (not the #137 red stop);
* in a product task where the user supplied an image, generate_image /
  generate_video calls that don't pass it are refused before submitting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..bot.guide import PAID_TOOLS
from ..bot.external_context import clip_image_blocks
from ..bot.local_llm import (
    _MAX_STEPS_ENV,
    _SKILL_HINT_RE,
    _reply_lang,
    _step_label,
    _step_limit_summary,
    max_steps_from,
)

_log = logging.getLogger(__name__)

DEFAULT_CAP = 4
CAP_TEXT = {
    "zh": "已生成 {n} 张仍未完成，已停止，未继续扣费，请告诉我怎么调整",
    "en": "Generated {n} images and still not done, so I stopped; no further "
          "charges. Tell me how to adjust.",
}
# #127: user cancelled the cost confirm — normal reply, not the #137 red stop.
DECLINED_TEXT = {
    "zh": "已取消该生成，未扣费。请用正常回复告诉用户，并询问如何调整；"
          "本轮不要再提交这一项。",
    "en": "Cancelled this generation; nothing was charged. Tell the user in a "
          "normal reply and ask how to adjust; do not resubmit this plan item "
          "in this turn.",
}
REF_BLOCK_TEXT = (
    "blocked before submitting (nothing was charged): the user supplied the "
    "product image {ids}. Every {tool} call must pass it - put the shape id in "
    "{field}. Describing it in the prompt does not send the image.")
_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}
_COUNT_RE = re.compile(
    r"(\d+|[一两二三四五六七八九十])\s*(?:张|幅|款|个版本|images?\b|pictures?\b"
    r"|photos?\b|versions?\b|variations?\b)", re.I)
_SHAPE_ID_RE = re.compile(r"shape:[A-Za-z0-9_\-]+")
_PRODUCT_RE = re.compile(r"产品|商品|电商|\bproducts?\b", re.I)
REF_FIELDS = {
    "generate_image": ("refs", "base"),
    "generate_video": ("first_frame", "last_frame", "reference_images"),
}


def requested_count(user_text: str) -> int:
    """Images the user explicitly asked for ("做 6 张", "3 images"), else 0."""
    text = _SKILL_HINT_RE.sub("", user_text or "")
    best = 0
    for m in _COUNT_RE.finditer(text):
        raw = m.group(1)
        best = max(best, int(raw) if raw.isdigit() else _ZH_NUM.get(raw, 0))
    return best


def product_refs(provider_text: str) -> list[str]:
    """Image shape ids the user supplied for a product task.

    Attached images arrive as "[Attached image 1: shape id shape:x ...]"; users
    can also name an id in the text. Audio/video attachments don't count."""
    text = provider_text or ""
    skill = re.search(r"Use the ComfyArt skill '([^']+)'", text)
    body = _SKILL_HINT_RE.sub("", text)
    if not ((skill and skill.group(1) == "product") or _PRODUCT_RE.search(body)):
        return []
    ids: list[str] = []
    for line in body.splitlines():
        if re.match(r"\s*\[Attached (audio|video)", line):
            continue
        for sid in _SHAPE_ID_RE.findall(line):
            if sid not in ids:
                ids.append(sid)
    return ids


def passes_ref(name: str, args: dict, refs: list[str]) -> bool:
    fields = REF_FIELDS.get(name)
    if not fields or not refs:
        return True
    given: list[str] = []
    for f in fields:
        v = args.get(f)
        given += [str(x) for x in v] if isinstance(v, list) else [str(v or "")]
    return any(r in given for r in refs)


def gen_units(name: str, args: dict) -> int:
    if name == "generate_image":
        try:
            return max(1, int(args.get("count") or 1))
        except (TypeError, ValueError):
            return 1
    return 1


def active_plan_item(args: dict) -> Optional[str]:
    steps = args.get("steps")
    if not isinstance(steps, list):
        return None
    for st in steps:
        if isinstance(st, dict) and st.get("status") == "active":
            return str(st.get("text") or "")
    return ""


def charged(payload: Any) -> bool:
    """A declined, cancelled or failed run charged nothing."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return True
    return not (isinstance(payload, dict) and (
        payload.get("cancelled") or payload.get("error")
        or payload.get("status") in ("declined", "cancelled", "failed")))


def user_declined(payload: Any) -> bool:
    """True when the user cancelled the cost confirm (not a failed run)."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return False
    return isinstance(payload, dict) and (
        bool(payload.get("cancelled"))
        or payload.get("status") in ("declined", "cancelled"))


@dataclass
class TurnGuard:
    lang: str
    cap: int
    refs: list[str]
    on_stop: Optional[Callable[[], None]] = None
    plan_item: str = ""
    used: dict[str, int] = field(default_factory=dict)
    done: list[str] = field(default_factory=list)
    stopped: str = ""
    declined_items: set[str] = field(default_factory=set)
    # #238: external CLIs only. The built-in agent counts steps in its own loop.
    external_steps: int = 0
    screenshots_sent: int = 0

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for label in self.done:
            counts[label] = counts.get(label, 0) + 1
        items = [k + (f" ×{c}" if c > 1 else "") for k, c in counts.items()]
        if self.lang == "zh":
            return (CAP_TEXT["zh"].format(n=self.cap) + "。已完成："
                    + ("、".join(items) if items else "无") + "。")
        return (CAP_TEXT["en"].format(n=self.cap) + " Done so far: "
                + (", ".join(items) if items else "nothing") + ".")


TURNS: dict[str, TurnGuard] = {}

NOTURN_PREFIX = "__noturn__:"


class PaidRefused(Exception):
    """Raised by the paid-tool handler wrap when before_call blocks the submit (#730)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def noturn_key(session_or_client: str) -> str:
    tag = (session_or_client or "").strip() or "anonymous"
    return f"{NOTURN_PREFIX}{tag}"


def ensure_noturn(chat_id: str) -> TurnGuard:
    """Open a default-cap guard for a no-turn MCP client; no-op if one already exists."""
    existing = TURNS.get(chat_id)
    if existing is not None:
        return existing
    if not chat_id.startswith(NOTURN_PREFIX):
        raise ValueError(f"ensure_noturn expects a {NOTURN_PREFIX!r} key, got {chat_id!r}")
    return begin_turn(chat_id, text="", provider_text="", lang="en")


def resolve_guard_chat_id() -> str:
    """Chat id for the paid guard: explicit guard key, bot chat, or anonymous noturn."""
    from .mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID
    return GUARD_CHAT_ID.get() or BOT_CHAT_ID.get() or noturn_key("anonymous")



def begin_turn(chat_id: str, *, text: str, provider_text: str, lang: str = "",
               on_stop: Optional[Callable[[], None]] = None) -> TurnGuard:
    """Open the guard for one turn. ``text`` is what the user typed (the count
    comes from it); ``provider_text`` also carries attached-image lines."""
    guard = TurnGuard(
        lang=lang if lang in ("zh", "en") else _reply_lang(text),
        cap=requested_count(text) or DEFAULT_CAP,
        refs=product_refs(provider_text),
        on_stop=on_stop)
    TURNS[chat_id] = guard
    return guard


def end_turn(chat_id: str) -> str:
    """Close the turn; returns the stop notice if the cap stopped it."""
    guard = TURNS.pop(chat_id, None)
    return guard.stopped if guard else ""


def external_step_limit() -> int:
    """#238: same cap as the built-in agent (setting, or COMFYART_AGENT_MAX_STEPS)."""
    import os

    from .settings import get_setting

    env = os.environ.get(_MAX_STEPS_ENV)
    if env:
        return max_steps_from(env)
    return max_steps_from(get_setting("bot-max-steps"))


def _external_step_block(guard: TurnGuard) -> Optional[str]:
    """Refuse the call once this external turn has used its step budget. Nothing runs."""
    if guard.stopped:
        return guard.stopped
    limit = external_step_limit()
    if guard.external_steps >= limit:
        guard.stopped = _step_limit_summary(guard.done, limit, guard.lang)
        if guard.on_stop:
            guard.on_stop()
        return guard.stopped
    guard.external_steps += 1
    return None


def fallback_allowed(chat_id: str, name: str, args: dict) -> bool:
    """#236: a fallback submit has to stay inside this turn's cost rules.

    Read-only. A missing guard allows it (the MCP check still runs on the real
    call). Over the cap, a declined plan item, a stopped turn, or a missing
    product reference all refuse it, and nothing here stops the turn or submits.
    """
    guard = TURNS.get(chat_id)
    if guard is None or name not in PAID_TOOLS:
        return True
    if guard.stopped or guard.plan_item in guard.declined_items:
        return False
    if not passes_ref(name, args, guard.refs):
        return False
    used = guard.used.get(guard.plan_item, 0)
    return used + gen_units(name, args) <= guard.cap


def before_call(chat_id: str, name: str, args: dict, *, external: bool = False) -> Optional[str]:
    """None to let the call run; otherwise the error text (nothing submitted)."""
    guard = TURNS.get(chat_id)
    if guard is None and chat_id.startswith(NOTURN_PREFIX):
        guard = ensure_noturn(chat_id)
    if guard is None:
        return None
    if external:
        # A stopped external turn refuses every later tool, paid or not.
        blocked = _external_step_block(guard)
        if blocked:
            return blocked
    if name not in PAID_TOOLS:
        return None
    if guard.stopped:
        return guard.stopped
    if guard.plan_item in guard.declined_items:
        return DECLINED_TEXT.get(guard.lang, DECLINED_TEXT["en"])
    if not passes_ref(name, args, guard.refs):
        return REF_BLOCK_TEXT.format(ids=", ".join(guard.refs), tool=name,
                                     field=REF_FIELDS[name][0])
    used = guard.used.get(guard.plan_item, 0)
    if used + gen_units(name, args) > guard.cap:
        _log.warning("[ComfyArt/paid-guard] chat %s: %s on plan item %r used "
                     "%d of %d, stopping", chat_id, name, guard.plan_item,
                     used, guard.cap)
        guard.stopped = guard.summary()
        if guard.on_stop:
            guard.on_stop()
        return guard.stopped
    return None


def after_call(chat_id: str, name: str, args: dict, payload: Any,
               ok: bool) -> None:
    guard = TURNS.get(chat_id)
    if guard is None:
        return
    if ok:
        guard.done.append(_step_label(name, args, guard.lang))
    if not ok:
        return
    if name == "update_plan":
        item = active_plan_item(args)
        if item is not None:
            guard.plan_item = item
    elif name in PAID_TOOLS:
        if charged(payload):
            guard.used[guard.plan_item] = (guard.used.get(guard.plan_item, 0)
                                           + gen_units(name, args))
        elif user_declined(payload):
            # At most one cost-confirm dialog per plan item this turn (#127).
            guard.declined_items.add(guard.plan_item)


def clip_external_screenshots(chat_id: str, blocks: list[dict]) -> list[dict]:
    """#238: at most 2 screenshot images returned to an external CLI during one turn."""
    guard = TURNS.get(chat_id)
    if guard is None or not blocks:
        return blocks
    clipped, guard.screenshots_sent = clip_image_blocks(
        blocks, already_sent=guard.screenshots_sent)
    return clipped


def stop_later(provider: Any, handle: Any) -> Callable[[], None]:
    """on_stop for a live turn: flag it now, stop the provider once the
    refused call's response is on its way."""
    def _stop() -> None:
        handle.stop_requested = True
        loop = asyncio.get_running_loop()
        loop.call_later(0.2, lambda: asyncio.ensure_future(provider.stop(handle)))
    return _stop
