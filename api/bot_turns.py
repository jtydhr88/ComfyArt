import asyncio
import json
import logging
import re
import time
from typing import Optional

from server import PromptServer

from ..bot import BotEvent, TurnHandle, TurnRequest, get_provider
from ..bot.local_llm import turn_result_from_blocks
from ..bot._cli_common import resolve_comfy_mcp_argv
from ..bot.agent_host import COMFY_MCP_ALLOWED_TOOLS
from . import bot_asks, chat_store, paid_guard
from .settings import SETTINGS_SPEC, get_setting

_log = logging.getLogger(__name__)

_ALLOWED_TOOLS = ["mcp__comfyart__*"]
_PERSIST_INTERVAL_S = 3.0
_TITLE_MAX = 48


class _TurnState:
    def __init__(self, handle: TurnHandle, chat_id: str, message_id: str) -> None:
        self.handle = handle
        self.chat_id = chat_id
        self.message_id = message_id
        self.blocks: list[dict] = []
        self.last_persist = 0.0
        self.tool_started: dict[str, float] = {}
        self.run_budget: dict = {}
        self.awaiting = ""  # #418: "confirm" while a quote card waits for the user


ACTIVE_TURNS: dict[str, _TurnState] = {}

QUEUED: dict[str, list[dict]] = {}


def broadcast(event: str, payload: dict) -> None:
    PromptServer.instance.send_sync("comfyart-bot", {"event": event, **payload})


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


def _allowed_tools(comfy_mcp_argv: list[str]) -> list[str]:
    tools = list(_ALLOWED_TOOLS)
    if comfy_mcp_argv:
        tools += [f"mcp__comfy__{t}" for t in COMFY_MCP_ALLOWED_TOOLS]
    return tools


def provider_model(provider_id: str) -> str:
    key = f"bot-model-{provider_id}"
    return str(get_setting(key) or "").strip() if key in SETTINGS_SPEC else ""


def refs_from_blocks(blocks: list[dict]) -> list[dict]:
    """#422: image/video/audio refs (shape id + src) from a stored message.

    Thinking blocks are ignored — only media the user attached (or that was
    saved on the message) become refs for later turns.
    """
    out: list[dict] = []
    for b in blocks or []:
        kind = b.get("type")
        if kind not in ("image", "video", "audio"):
            continue
        out.append({
            "id": str(b.get("shape") or ""),
            "src": str(b.get("url") or ""),
            "name": str(b.get("name") or ""),
            "kind": kind,
            "transcript": str(b.get("transcript") or ""),
        })
    return out


def format_ref_lines(refs: list[dict], *, sheet_frames: int = 4) -> list[str]:
    """Canonical Attached-lines with shape ids — same form as the current turn.

    History used to emit `[attached image: url]` without the shape id, so a
    follow-up turn could not pass previous images as generation refs. #422.
    """
    lines: list[str] = []
    for i, r in enumerate(refs or []):
        if not isinstance(r, dict):
            continue
        kind = r.get("kind") if r.get("kind") in ("image", "video", "audio") else "image"
        label = f' "{r["name"]}"' if r.get("name") else ""
        target = f"shape id {r['id']}" if r.get("id") else "not on the canvas"
        src = r.get("src") or ""
        if kind == "audio":
            heard = (f' Transcript: "{r["transcript"]}"' if r.get("transcript")
                     else " No speech was recognised in it.")
            lines.append(
                f"[Attached audio {i + 1}{label}: {target} — {src}. "
                f"Use the shape id as reference_audios, speech_audio or a voice "
                f"reference.{heard}]")
            continue
        frames = (f" Its picture shows {sheet_frames} frames across the video; "
                  f"call view_video for more.") if kind == "video" else ""
        lines.append(
            f"[Attached {kind} {i + 1}{label}: {target} — {src}. "
            f"Use the shape id with edit tools or as a generation ref.{frames}]")
    return lines


def blocks_text(blocks: list[dict]) -> str:
    """Plain text + #422 canonical image-ref lines. Thinking is never included."""
    parts = []
    for b in blocks:
        kind = b.get("type")
        if kind == "text":
            parts.append(str(b.get("text") or ""))
        elif kind in ("image", "video", "audio"):
            continue  # #422: emitted via format_ref_lines below (with shape id)
        elif kind == "file":
            parts.append(f"[attached document {b.get('name') or ''}: {b.get('url') or ''}]")
        elif kind == "notice" and b.get("text"):
            parts.append(f"[notice: {b.get('text')}]")
        # thinking / tool_use / tool_result / kit / skill: omitted on purpose
    parts.extend(format_ref_lines(refs_from_blocks(blocks)))
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


def _replay_history(chat_id: str, current_message_id: str) -> list[dict]:
    rows = chat_store.list_messages(chat_id)
    current = next((r for r in rows if r["id"] == current_message_id), None)
    skip = {current_message_id}
    if current and current.get("parent_id"):
        skip.add(current["parent_id"])
    history = []
    for row in rows:
        if row["id"] in skip or row["role"] not in ("user", "assistant"):
            continue
        text = blocks_text(row["blocks"])
        refs = refs_from_blocks(row["blocks"])
        item = {"role": row["role"], "text": text}
        if refs:
            item["refs"] = refs  # #422: previous-turn image refs for fit_history
        # #234: each assistant turn records the shapes it placed and the failures,
        # so later context can keep id / type / model / prompt without the raw tool output.
        if row["role"] == "assistant":
            recorded = turn_result_from_blocks(row["blocks"])
            if recorded:
                item["result"] = recorded
        if text or item.get("result") or refs:
            history.append(item)
    return history


def _derive_title(text: str) -> str:
    line = " ".join(text.split())
    return line[:_TITLE_MAX]


def memory_updated_block(blocks: list[dict], call_id: str, name: str, text: str, status: str) -> Optional[dict]:
    """#413: a successful memory add from the agent loop becomes one memory_updated block."""
    if status != "success" or str(name or "").split("__")[-1] != "memory":
        return None
    use = next((b for b in reversed(blocks) if b.get("type") == "tool_use" and call_id and b.get("id") == call_id), None)
    if use is None or str((use.get("input") or {}).get("action") or "") != "add":
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        m = re.search(r"\{.*\}", str(text or ""), re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except ValueError:
            data = {}
    ids = [str(i) for i in (data.get("memory_ids") or []) if i] if isinstance(data, dict) else []
    if not ids:
        return None
    texts = [str(x) for x in (data.get("texts") or []) if x] or [str(data.get("added") or "")]
    upd = [str(i) for i in (data.get("updated_ids") or []) if i]
    # #423: one 记忆已更新 › row per turn. Later adds merge into the first block (ids / texts deduped).
    prev = next((b for b in blocks if b.get("type") == "memory_updated"), None)
    if prev is not None:
        for i in ids:
            if i not in prev.setdefault("memory_ids", []):
                prev["memory_ids"].append(i)
                if i in upd:  # first written this turn as an update; an entry added earlier this turn stays "new"
                    prev.setdefault("updated_ids", []).append(i)
        for x in texts:
            if x and x not in prev.setdefault("texts", []):
                prev["texts"].append(x)
        if call_id and call_id not in prev.setdefault("tool_ids", [t for t in [prev.get("tool_id")] if t]):
            prev["tool_ids"].append(call_id)
        _counts(prev)
        return prev
    return _counts({"type": "memory_updated", "memory_ids": ids, "texts": texts, "tool_id": call_id,
                    "tool_ids": [call_id], "updated_ids": [i for i in ids if i in upd]})


def _counts(b: dict) -> dict:
    """#423: N = new + updated; both count toward the row appearing."""
    b["updated_ids"] = [i for i in b.get("updated_ids", []) if i in b["memory_ids"]]
    b["count"] = len(b["memory_ids"])
    b["updated"] = len(b["updated_ids"])
    b["added_count"] = b["count"] - b["updated"]
    return b


def _apply_event(state: _TurnState, ev: BotEvent) -> Optional[dict]:
    if ev.t == "delta":
        if state.blocks and state.blocks[-1].get("type") == "text":
            state.blocks[-1]["text"] += ev.text
        else:
            state.blocks.append({"type": "text", "text": ev.text})
        return {"event": "turn_delta", "text": ev.text}
    if ev.t == "thinking":
        if state.blocks and state.blocks[-1].get("type") == "thinking":
            state.blocks[-1]["text"] += ev.text
        else:
            state.blocks.append({"type": "thinking", "text": ev.text})
        return {"event": "turn_thinking", "text": ev.text}
    if ev.t == "tool_use":
        block = {"type": "tool_use", "name": ev.name, "input": ev.input or {}}
        payload = {"event": "turn_tool_use", "name": ev.name,
                   "input": ev.input or {}}
        if ev.id:
            block["id"] = payload["id"] = ev.id
            state.tool_started[ev.id] = time.monotonic()
        state.blocks.append(block)
        return payload
    if ev.t == "tool_result":
        # #232: a declined / guard-refused paid step is "cancelled", never success
        tool_status = "cancelled" if ev.detail == "cancelled" else ("error" if ev.is_error else "success")
        block = {"type": "tool_result", "name": ev.name, "text": ev.text,
                 "status": tool_status}
        payload = {"event": "turn_tool_result", "name": ev.name,
                   "text": ev.text, "status": tool_status}
        if ev.id:
            block["id"] = payload["id"] = ev.id
            started = state.tool_started.pop(ev.id, None)
            if started is not None:
                duration_ms = int((time.monotonic() - started) * 1000)
                block["duration_ms"] = payload["duration_ms"] = duration_ms
        state.blocks.append(block)
        mem = memory_updated_block(state.blocks, ev.id, ev.name, ev.text, tool_status)
        if mem:  # #413: the agent saved memory in-loop -> 记忆已更新 › row right after the call
            if not any(b is mem for b in state.blocks):  # #423: a merged add updates the turn's one row
                state.blocks.append(mem)
            payload["memory_updated"] = dict(mem)
        return payload
    if ev.t == "run_budget":  # #391: live budget bar (not persisted; the stop card keeps the final numbers)
        state.run_budget = dict(ev.input or {})
        return {"event": "turn_run_budget", "budget": state.run_budget}
    if ev.t == "run_stop":  # #391: stop reason + done / remaining / estimate (+ Continue when allowed)
        block = {"type": "run_stop", **(ev.input or {})}
        state.blocks.append(block)
        return {"event": "turn_run_stop", "block": block}
    if ev.t == "notify":  # #391/#388: unattended runs notify instead of waiting
        block = {"type": "notice", "level": "warn", "text": ev.text, "notify": True, **(ev.input or {})}
        state.blocks.append(block)
        return {"event": "turn_notify", "block": block}
    if ev.t == "retry":  # #232: LLM timeout / 429 / 5xx retry row (429 shows a countdown)
        block = {"type": "retry", "kind": ev.name, **(ev.input or {})}
        state.blocks.append(block)
        return {"event": "turn_retry", "block": block}
    return None


async def _run_turn(chat: dict, text: str, state: _TurnState, *,
                    provider_text: str | None = None,
                    attachments: list[dict] | None = None,
                    lang: str = "", resume_run_id: str = "", lease_owner: str = "",
                    run_mode: str = "interactive") -> None:
    chat_id = chat["id"]
    provider = get_provider(chat["provider"])
    await asyncio.sleep(0.1)

    async def emit(ev: BotEvent) -> None:
        if ev.t == "session":
            if not ev.id:
                return
            if chat_store.update_message(chat_id, state.message_id, resume_token_after=ev.id) is None:
                raise RuntimeError("bot message no longer exists")
            if chat_store.update_chat(chat_id, resume_token=ev.id) is None:
                raise RuntimeError("bot chat no longer exists")
            return
        payload = _apply_event(state, ev)
        if payload is None:
            return
        payload.update({"chat_id": chat_id, "message_id": state.message_id})
        broadcast(payload.pop("event"), payload)
        now = time.monotonic()
        if ev.t in ("tool_use", "tool_result", "retry", "run_stop", "notify") or now - state.last_persist > _PERSIST_INTERVAL_S:
            state.last_persist = now
            chat_store.update_message(chat_id, state.message_id, blocks=state.blocks)

    # #238: external CLIs keep their own resumed session, but a cold start still needs
    # this history so the same token budget can be applied. They ignore it when resuming.
    history = _replay_history(chat_id, state.message_id)

    comfy_mcp_argv = _comfy_mcp_argv()
    paid_guard.begin_turn(chat_id, text=text,
                          provider_text=provider_text if provider_text is not None else text,
                          lang=lang, on_stop=paid_guard.stop_later(provider, state.handle))
    try:
        result = await provider.send(
            TurnRequest(
                chat_id=chat_id,
                user_text=provider_text if provider_text is not None else text,
                resume_token=chat.get("resume_token"),
                history=history,
                mcp_endpoint=_mcp_endpoint(chat_id),
                allowed_tools=_allowed_tools(comfy_mcp_argv),
                attachments=attachments or [],
                model=provider_model(chat["provider"]),
                comfy_mcp_argv=comfy_mcp_argv,
                lang=lang,
                goal_text=text,
                run_mode=run_mode,
                resume_run_id=resume_run_id,
                lease_owner=lease_owner,
                project_id=str(chat.get("project") or "local"),
            ),
            emit,
            state.handle,
        )
    except Exception as e:
        _log.exception("[ComfyArt/bot] turn failed for chat %s", chat_id)
        result = None
        error = str(e) or type(e).__name__
        status = "error"
    else:
        error = result.error
        status = "aborted" if result.aborted else ("error" if error else "done")
    paid_stop = paid_guard.end_turn(chat_id)
    if paid_stop:  # #142: the paid cap stopped this turn -> its notice, whatever the provider returned
        error, status = paid_stop, "error"

    ACTIVE_TURNS.pop(chat_id, None)
    bot_asks.cancel_chat_asks(chat_id)
    token = result.resume_token if result else None
    usage = result.usage if result else None
    run = result.run if result else None
    # #383: goal self-check for every provider. Never report "done" over missing deliverables.
    self_check_info: dict = {"self_check": "skip"}
    if status in ("done", "error"):
        from ..bot import self_check as _sc
        goal_text = text if not resume_run_id else ""
        if run and run.get("self_check"):
            # the budget loop already ran the check (with a live canvas read): trust it, scrub on fail
            self_check_info = run["self_check"]
            if goal_text and self_check_info.get("self_check") == "fail":
                state.blocks = [({**b, "text": _sc.scrub_done_claims(str(b.get("text") or ""))}
                                 if b.get("type") == "text" else b) for b in state.blocks]
        elif goal_text:
            already = bool(error) and any(k in error for k in ("目标核对未通过", "Goal check failed"))
            state.blocks, self_check_info = _sc.apply_to_blocks(goal_text, state.blocks, lang, note=not already)
        if self_check_info.get("self_check") == "fail" and error:
            error = _sc.scrub_done_claims(error)
    if error:
        state.blocks.append({"type": "notice", "level": "error", "text": error,
                             **({"self_check": self_check_info} if self_check_info.get("self_check") == "fail" else {})})
    elif status == "done":
        notice = unverified_write_notice(state.blocks)
        if notice:
            state.blocks.append(notice)
    chat_store.update_message(chat_id, state.message_id, blocks=state.blocks, status=status,
                              resume_token_after=token, usage=usage)
    updates: dict = {"resume_token": token} if token else {}
    # #227: a failed/aborted turn (e.g. no WaveSpeed Key) must not name the chat or its board
    if status == "done" and not (chat.get("title") or "").strip():
        updates["title"] = _derive_title(text)
    if updates:
        chat_store.update_chat(chat_id, **updates)
    broadcast("turn_done", {
        "chat_id": chat_id,
        "message_id": state.message_id,
        "status": status,
        "error": error,
        "title": updates.get("title"),
        "usage": usage,
        "self_check": self_check_info,
        "run": ({k: run.get(k) for k in ("run_id", "status", "stop")} if run else None),
    })
    _drain_queue(chat_id)


def begin_turn(chat: dict, *, text: str, provider_text: str,
               attachments: list[dict], user_msg: dict, lang: str = "",
               resume_run_id: str = "", lease_owner: str = "",
               run_mode: str = "interactive") -> dict:
    assistant_msg = chat_store.create_message(
        chat_id=chat["id"], role="assistant", blocks=[], status="streaming",
        parent_id=user_msg["id"],
    )
    state = _TurnState(TurnHandle(), chat["id"], assistant_msg["id"])
    ACTIVE_TURNS[chat["id"]] = state
    broadcast("turn_start", {
        "chat_id": chat["id"],
        "user_message": user_msg,
        "assistant_message": assistant_msg,
    })
    asyncio.create_task(
        _run_turn(chat, text, state, provider_text=provider_text,
                  attachments=attachments, lang=lang, resume_run_id=resume_run_id,
                  lease_owner=lease_owner, run_mode=run_mode),
        name=f"comfyart-bot-{chat['id'][:8]}",
    )
    return assistant_msg


def _drain_queue(chat_id: str) -> None:
    queue = QUEUED.get(chat_id)
    if not queue:
        QUEUED.pop(chat_id, None)
        return
    item = queue.pop(0)
    if not queue:
        QUEUED.pop(chat_id, None)
    chat = chat_store.get_chat(chat_id)
    if chat is None:
        return
    user_msg = chat_store.update_message(chat_id, item["user_msg"]["id"], status="done")
    begin_turn(chat, text=item["text"],
               provider_text=item["provider_text"],
               attachments=item["attachments"],
               lang=item.get("lang", ""),
               user_msg=user_msg or item["user_msg"],
               run_mode=item.get("run_mode") or "interactive")
