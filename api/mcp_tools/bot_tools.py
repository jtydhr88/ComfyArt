import asyncio

from .. import bot_asks, chat_store
from ..bot_turns import ACTIVE_TURNS, broadcast
from ._context import BOT_CHAT_ID


def bot_turn_state():
    chat_id = BOT_CHAT_ID.get()
    if not chat_id:
        return "", None
    return chat_id, ACTIVE_TURNS.get(chat_id)


async def _await_ask(chat_id: str, state, spec: dict, *,
                     timeout: float | None = None,
                     keep_pending_on_timeout: bool = False, wait_forever: bool = False) -> dict:
    ask = bot_asks.create_ask(chat_id, state.message_id, spec)
    block = {"type": "ask", "ask_id": ask.id, "status": "pending", **spec}
    state.blocks.append(block)
    chat_store.update_message(chat_id, state.message_id, blocks=state.blocks)
    broadcast("turn_ask", {
        "chat_id": chat_id, "message_id": state.message_id,
        "ask_id": ask.id, **spec,
    })
    try:
        outcome = await asyncio.wait_for(
            asyncio.shield(ask.future),
            timeout=None if wait_forever else bot_asks.ASK_TIMEOUT_S if timeout is None else timeout)
    except asyncio.TimeoutError:
        if keep_pending_on_timeout:
            bot_asks.abandon_ask(ask.id)
            return {"status": "pending", "ask_id": ask.id}
        bot_asks.resolve_ask(ask.id, "expired")
        outcome = {"status": "expired"}

    block["status"] = outcome["status"]
    if outcome.get("selected") is not None:
        block["selected"] = outcome["selected"]
    if outcome.get("other_text"):
        block["other_text"] = outcome["other_text"]
    if outcome.get("answers") is not None:
        block["answers"] = outcome["answers"]
    chat_store.update_message(chat_id, state.message_id, blocks=state.blocks)
    payload = {
        "chat_id": chat_id, "message_id": state.message_id,
        "ask_id": ask.id, "status": outcome["status"],
        "selected": outcome.get("selected"),
        "other_text": outcome.get("other_text"),
    }
    if outcome.get("answers") is not None:
        payload["answers"] = outcome["answers"]
    broadcast("turn_ask_resolved", payload)
    return outcome


async def ask_user(args: dict) -> dict:
    chat_id, state = bot_turn_state()
    if not chat_id:
        raise ValueError("ask_user is only available inside ComfyArt Agent chats")
    if state is None:
        raise ValueError("no active Agent turn for this chat")
    spec = bot_asks.validate_spec(args)
    outcome = await _await_ask(chat_id, state, spec)
    if outcome["status"] != "answered":
        return {"status": outcome["status"],
                "note": "the user did not answer; proceed conservatively or "
                        "end the turn"}
    selected = outcome.get("selected") or []
    other_text = outcome.get("other_text") or ""
    answers = outcome.get("answers")
    result = {"status": "answered",
              "selected": selected,
              "other_text": other_text}
    if answers is not None:
        result["answers"] = answers
    skipped = (
        bool(spec.get("allow_skip"))
        and not selected
        and not other_text
        and (not answers or all(
            not (a.get("selected") or []) and not a.get("other_text")
            for a in (answers or {}).values()
        ))
    )
    if skipped:
        result["note"] = bot_asks.skip_note()
        result["skipped"] = True
    else:
        result["note"] = bot_asks.answer_note()
    return result


async def maybe_ask_run_approval(action: str) -> dict | None:
    chat_id, state = bot_turn_state()
    if not chat_id or state is None:
        return None
    chat = chat_store.get_chat(chat_id)
    if not chat or chat.get("run_mode") != "ask":
        return None
    outcome = bot_asks.take_run_approval_answer(chat_id, action)
    if outcome is None:
        outcome = await _await_ask(chat_id, state, {
            "prompt": action,
            "options": [
                {"id": "run", "label": "运行"},
                {"id": "always", "label": "总是运行",
                 "description": "运行并把这个对话切回自动"},
                {"id": "cancel", "label": "取消"},
            ],
            "min_selections": 1,
            "max_selections": 1,
            "allow_other": False,
            "kind": bot_asks.RUN_APPROVAL_KIND,
        }, timeout=bot_asks.RUN_APPROVAL_WAIT_S, keep_pending_on_timeout=True)
    selected = outcome.get("selected") or []
    if outcome["status"] == "answered" and "always" in selected:
        chat_store.update_chat(chat_id, run_mode="auto")
        return None
    if outcome["status"] == "answered" and "run" in selected:
        return None
    if outcome["status"] == "pending":
        return {"started": False, "pending_approval": True,
                "ask_id": outcome.get("ask_id"),
                "note": f"the user has not answered '{action}' yet — the "
                        "question stays open in the chat panel. Nothing ran. "
                        "Tell the user it is waiting for their approval; once "
                        "they answer, call this tool again with the same "
                        "arguments and it will proceed without asking twice."}
    if outcome["status"] == "answered":
        return {"cancelled": True, "status": "declined",
                "note": "the user declined this run; do not retry it without "
                        "new instructions"}
    return {"cancelled": True, "status": outcome["status"],
            "note": f"the run approval was {outcome['status']} before the user "
                    "answered — nothing ran; ask the user whether to run it"}


async def update_plan(args: dict) -> dict:
    steps = args.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty array")
    return {"ok": True}


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "active", "done"]},
                },
                "required": ["text", "status"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["steps"],
    "additionalProperties": False,
}

ASK_USER_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string"},
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "recommended": {"type": "boolean"},
                },
                "required": ["id", "label"],
                "additionalProperties": False,
            },
        },
        "min_selections": {"type": "integer"},
        "max_selections": {"type": "integer"},
        "allow_other": {"type": "boolean"},
        "allow_skip": {"type": "boolean"},
        "defaults": {
            "type": "array",
            "items": {"type": "string"},
        },
        "page": {"type": "integer"},
        "page_count": {"type": "integer"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "recommended": {"type": "boolean"},
                },
                "required": ["id", "label"],
                "additionalProperties": False,
            },
                    },
                    "min_selections": {"type": "integer"},
                    "max_selections": {"type": "integer"},
                    "allow_other": {"type": "boolean"},
                    "defaults": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "page": {"type": "integer"},
                    "placeholder": {"type": "string"},
                },
                "required": ["id", "prompt"],
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

TOOLS: dict[str, dict] = {
    "ask_user": {
        "description": (
            "Pause and ask the user in the chat panel. Pass either a single "
            "prompt+options (legacy) or questions[] for one card with several "
            "questions (text / single-select / multi-select can mix) and "
            "optional page/page_count for in-card paging (Next advances the "
            "local page; Submit resolves). Blocks until they answer, skip, or "
            "a few minutes pass. Use when a required parameter or creative "
            "choice is missing. options are choices (A–E); min/max_selections "
            "for multi-select; allow_other for free text; allow_skip (default "
            "true). Returns {status, selected, other_text, answers?, note}. "
            "After the user answers or skips: do NOT emit a separate "
            "pre-generate confirmation sentence; immediately continue the "
            "original task (generation expected when they did not ask to "
            "wait). Restate the choice in the post-image completion intro. "
            "Only if their own instructions asked you to wait or not "
            "generate yet, use the pinned wait sentences and do not "
            "generate this turn — do not re-ask immediately. status "
            "cancelled/expired means no answer."
        ),
        "inputSchema": ASK_USER_SCHEMA,
        "handler": ask_user,
    },
    "update_plan": {
        "description": (
            "Show the user your plan for a task with several steps as a "
            "checklist in the chat. Call it before starting with every step "
            "pending (or the first active), then again with the full list "
            "whenever a step becomes active or done. Skip it for one-step "
            "requests."
        ),
        "inputSchema": PLAN_SCHEMA,
        "handler": update_plan,
    },
}
