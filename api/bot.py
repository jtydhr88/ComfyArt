from aiohttp import web

from ..bot import bot_asks, get_provider, list_providers
from ..bot.providers import ProviderStatus
from . import chat_store
from . import bot_send as send_core
from ._common import error, json_body, request_user, routes
from .bot_turns import ACTIVE_TURNS, QUEUED, broadcast
from .settings import bot_disabled, bot_enabled


@routes.get("/comfyart/bot/status")
async def bot_status(request: web.Request) -> web.Response:
    user = request_user(request)
    if not bot_enabled():
        return web.json_response({"enabled": False, "user": user, "providers": []})
    out = []
    for provider in list_providers():
        try:
            st = await provider.probe()
        except Exception as e:
            st = ProviderStatus(available=False, detail=f"probe failed: {e}")
        caps = provider.capabilities()
        entry = {
            "id": provider.id,
            "label": provider.label,
            "available": st.available,
            "version": st.version,
            "logged_in": st.logged_in,
            "detail": st.detail,
            "stateful": caps.stateful,
            "attachments": caps.attachments,
            "branch": provider.supports_branch,
            "models": await provider.list_models(),
        }
        options = provider.model_options()
        if options:
            entry["model_options"] = options
        out.append(entry)
    return web.json_response({"enabled": True, "user": user, "providers": out})


def _owned_chat(request: web.Request) -> dict:
    chat = chat_store.get_chat(request.match_info["cid"])
    if chat is None or chat["user"] != request_user(request):
        raise web.HTTPNotFound(text='{"error": "chat not found"}', content_type="application/json")
    return chat


@routes.get("/comfyart/bot/chats")
async def bot_list_chats(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chats = chat_store.list_chats(request_user(request), request.query.get("project", ""),
                                  include_archived=request.query.get("archived") == "1")
    for c in chats:
        c["busy"] = c["id"] in ACTIVE_TURNS
    return web.json_response({"chats": chats})


@routes.post("/comfyart/bot/chats")
async def bot_create_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    body = await json_body(request)
    provider_id = str(body.get("provider") or "")
    if get_provider(provider_id) is None:
        return error(f"unknown provider {provider_id!r}", 400)
    project = str(body.get("project") or "")
    if not project:
        return error("project required", 400)
    run_mode = body.get("run_mode") or "auto"
    if run_mode not in ("auto", "ask"):
        return error("run_mode must be 'auto' or 'ask'", 400)
    chat = chat_store.create_chat(user=request_user(request), project=project, provider=provider_id,
                                  title=str(body.get("title") or ""), run_mode=run_mode)
    broadcast("chat_created", {"chat": chat})
    return web.json_response({"chat": chat})


@routes.get("/comfyart/bot/chats/{cid}")
async def bot_get_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    messages = chat_store.list_messages(chat["id"])
    state = ACTIVE_TURNS.get(chat["id"])
    if state is not None:
        for m in messages:
            if m["id"] == state.message_id:
                m["blocks"] = state.blocks
    chat["busy"] = state is not None
    return web.json_response({"chat": chat, "messages": messages})


@routes.patch("/comfyart/bot/chats/{cid}")
async def bot_update_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    run_mode = body.get("run_mode")
    if run_mode is not None and run_mode not in ("auto", "ask"):
        return error("run_mode must be 'auto' or 'ask'", 400)
    title = body.get("title")
    updated = chat_store.update_chat(
        chat["id"],
        title=str(title) if title is not None else None,
        run_mode=run_mode,
        pinned=bool(body["pinned"]) if "pinned" in body else None,
        archived=bool(body["archived"]) if "archived" in body else None,
    )
    broadcast("chat_updated", {"chat": updated})
    return web.json_response({"chat": updated})


@routes.delete("/comfyart/bot/chats/{cid}")
async def bot_delete_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    await remove_chat(_owned_chat(request))
    return web.json_response({"ok": True})


async def remove_chat(chat: dict) -> None:
    QUEUED.pop(chat["id"], None)
    state = ACTIVE_TURNS.get(chat["id"])
    if state is not None:
        await get_provider(chat["provider"]).stop(state.handle)
    chat_store.delete_chat(chat["id"])
    broadcast("chat_deleted", {"chat_id": chat["id"]})


@routes.post("/comfyart/bot/chats/{cid}/send")
async def bot_send(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    text = str(body.get("text") or "").strip()
    try:
        refs = send_core.parse_refs(body.get("refs"))
        kits = send_core.parse_kits(body.get("kits"))
        docs = send_core.parse_docs(body.get("docs"))
    except ValueError as e:
        return error(str(e), 400)
    if not text and not refs and not docs:
        return error("text, refs or docs required", 400)
    provider = get_provider(chat["provider"])
    if provider is None:
        return error(f"unknown provider {chat['provider']!r}", 400)
    can_see = provider.capabilities().attachments
    if (send_core.visual_refs(refs) or any(k["images"] for k in kits)) and not can_see:
        return error(f"{provider.label} cannot take images; pick another agent or remove the references", 400)
    skill_name = str(body.get("skill") or "").strip()
    try:
        attachments, lines = await send_core.prepare_attachments(refs, kits, docs, page_images=can_see)
    except ValueError as e:
        return error(str(e), 400)
    display_blocks = [{"type": r["kind"], "url": r["src"], "shape": r["id"]} for r in refs]
    display_blocks += [{"type": "file", "url": d["src"], "name": d["name"]} for d in docs]
    display_blocks += [{"type": "kit", "name": k["name"]} for k in kits]
    if skill_name:
        display_blocks.append({"type": "skill", "name": skill_name})
    if text:
        display_blocks.append({"type": "text", "text": text})
    context = str(body.get("context") or "").strip()
    provider_text = send_core.compose_provider_text(
        text, skill_name=skill_name, memory=str(body.get("memory") or ""), lines=[*lines, *([context] if context else [])])
    user_msg, assistant_msg = send_core.queue_or_begin(
        chat, text=text, provider_text=provider_text,
        attachments=attachments, display_blocks=display_blocks)
    if assistant_msg is None:
        return web.json_response({"queued": True, "user_message": user_msg})
    return web.json_response({"user_message": user_msg, "assistant_message": assistant_msg})


@routes.post("/comfyart/bot/chats/{cid}/log")
async def bot_log(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    blocks = body.get("blocks")
    if not isinstance(blocks, list):
        return error("blocks must be a list", 400)
    text = str(body.get("text") or "").strip()
    user_msg = chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{"type": "text", "text": text}])
    assistant_msg = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=blocks, parent_id=user_msg["id"])
    if not chat["title"]:
        broadcast("chat_updated", {"chat": chat_store.update_chat(chat["id"], title=" ".join(text.split())[:48])})
    broadcast("messages_logged", {"chat_id": chat["id"], "messages": [user_msg, assistant_msg]})
    return web.json_response({"messages": [user_msg, assistant_msg]})


@routes.patch("/comfyart/bot/chats/{cid}/messages/{mid}")
async def bot_patch_message(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    if not isinstance(body.get("blocks"), list):
        return error("blocks must be a list", 400)
    state = ACTIVE_TURNS.get(chat["id"])
    if state is not None and state.message_id == request.match_info["mid"]:
        return error("message is streaming", 409)
    message = chat_store.update_message(chat["id"], request.match_info["mid"], blocks=body["blocks"])
    if message is None:
        return error("message not found", 404)
    return web.json_response({"message": message})


@routes.post("/comfyart/bot/chats/{cid}/stop")
async def bot_stop(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    state = ACTIVE_TURNS.get(chat["id"])
    if state is None:
        return error("no active turn", 409)
    bot_asks.cancel_chat_asks(chat["id"])
    await get_provider(chat["provider"]).stop(state.handle)
    return web.json_response({"ok": True})


@routes.post("/comfyart/bot/chats/{cid}/branch")
async def bot_branch_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    message_id = str(body.get("message_id") or "")
    if not message_id:
        return error("message_id required", 400)
    provider = get_provider(chat["provider"])
    if not provider.supports_branch:
        return error(f"{provider.label} sessions cannot be forked, so this chat cannot be branched. Start a new chat instead.", 400)
    branch = chat_store.branch_chat(chat["id"], message_id)
    if branch is None:
        return error("message not found", 404)
    broadcast("chat_created", {"chat": branch})
    return web.json_response({"chat": branch, "messages": chat_store.list_messages(branch["id"])})


@routes.post("/comfyart/bot/chats/{cid}/asks/{aid}/answer")
async def bot_answer_ask(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    selected = body.get("selected")
    if not isinstance(selected, list):
        return error("selected must be a list", 400)
    selected = [str(s) for s in selected]
    other_text = str(body.get("other_text") or "")
    ask = bot_asks.PENDING.get(request.match_info["aid"])
    if ask is None or ask.chat_id != chat["id"]:
        return error("ask not found or already resolved", 409)
    try:
        bot_asks.validate_answer(ask.spec, selected, other_text)
    except ValueError as e:
        return error(str(e), 422)
    if bot_asks.resolve_ask(ask.id, "answered", selected, other_text) is None:
        return error("ask not found or already resolved", 409)
    return web.json_response({"ok": True}, status=202)


def reap_stale_messages() -> None:
    chat_store.abort_unfinished()
