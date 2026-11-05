from __future__ import annotations

import asyncio

from conftest import SENT, wait_bot_done, write_settings

from ComfyArt.api import chat_store
from ComfyArt.bot import bot_asks
from ComfyArt.api.bot import reap_stale_messages
from ComfyArt.api.bot_turns import ACTIVE_TURNS
from ComfyArt.bot.providers import BotEvent


async def _chat(client, provider="fake-test", headers=None):
    resp = await client.post("/comfyart/bot/chats", json={"project": "p", "provider": provider}, headers=headers)
    assert resp.status == 200
    return (await resp.json())["chat"]


async def test_everything_is_off_by_default(bot_client):
    write_settings(**{"enable-mcp": False, "enable-bot": False})
    assert (await (await bot_client.get("/comfyart/bot/status")).json()) == {"enabled": False, "user": "default", "providers": []}
    resp = await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "codex"})
    assert resp.status == 403
    assert (await bot_client.post("/comfyart/bot/complete", json={"text": "hi"})).status == 403


async def test_bot_needs_mcp_too(bot_client, fake_provider):
    write_settings(**{"enable-mcp": False, "enable-bot": True})
    assert (await bot_client.get("/comfyart/bot/chats?project=p")).status == 403


async def test_create_requires_project_and_known_provider(bot_client, fake_provider):
    assert (await bot_client.post("/comfyart/bot/chats", json={"provider": "fake-test"})).status == 400
    assert (await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "nope"})).status == 400


async def test_other_users_cannot_see_or_touch_a_chat(bot_client, fake_provider):
    chat = await _chat(bot_client)
    alice = {"comfy-user": "alice"}
    assert (await bot_client.get(f"/comfyart/bot/chats/{chat['id']}", headers=alice)).status == 404
    assert (await bot_client.delete(f"/comfyart/bot/chats/{chat['id']}", headers=alice)).status == 404
    listed = await (await bot_client.get("/comfyart/bot/chats?project=p", headers=alice)).json()
    assert listed["chats"] == []
    assert (await bot_client.get("/comfyart/bot/chats?project=p", headers={"comfy-user": "mallory"})).status == 403


async def test_send_streams_blocks_and_titles_the_chat(bot_client, fake_provider):
    fake_provider.script = [BotEvent(t="thinking", text="Plan "), BotEvent(t="thinking", text="first"),
                            BotEvent(t="delta", text="Hello "), BotEvent(t="delta", text="there"),
                            BotEvent(t="tool_use", name="get_canvas", input={}, id="t1"),
                            BotEvent(t="tool_result", name="get_canvas", text="{}", id="t1")]
    chat = await _chat(bot_client)
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "make a poster", "memory": "MEM", "context": "[CTX]"})
    assert resp.status == 200
    data = await wait_bot_done(bot_client, chat["id"])
    assistant = data["messages"][-1]
    assert [b["type"] for b in assistant["blocks"]] == ["thinking", "text", "tool_use", "tool_result"]
    assert assistant["blocks"][0]["text"] == "Plan first"
    assert assistant["blocks"][1]["text"] == "Hello there"
    assert assistant["blocks"][3]["duration_ms"] >= 0
    assert data["chat"]["title"] == "make a poster"
    assert data["chat"]["resume_token"] == "tok-1"
    assert fake_provider.last_turn.user_text.startswith("MEM\n\nmake a poster")
    assert fake_provider.last_turn.user_text.endswith("[CTX]")
    assert [b["text"] for b in data["messages"][0]["blocks"] if b["type"] == "text"] == ["make a poster"]
    assert fake_provider.last_turn.mcp_endpoint.endswith(f"/comfyart/mcp?bot_chat={chat['id']}")
    assert any(event == "comfyart-bot" and data["event"] == "turn_done" for event, data in SENT)


async def test_messages_queue_while_busy_and_stop_aborts(bot_client, fake_provider):
    fake_provider.gate = asyncio.Event()
    chat = await _chat(bot_client)
    await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "one"})
    second = await (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "two"})).json()
    assert second["queued"] is True
    await asyncio.sleep(0.15)
    assert (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/stop")).status == 200
    fake_provider.gate = None
    data = await wait_bot_done(bot_client, chat["id"])
    statuses = [m["status"] for m in data["messages"] if m["role"] == "assistant"]
    assert statuses == ["aborted", "done"]


async def test_ask_answer_round_trip(bot_client, fake_provider):
    chat = await _chat(bot_client)
    ask = bot_asks.create_ask(chat["id"], "m", bot_asks.validate_spec(
        {"prompt": "color?", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}))
    bad = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/asks/{ask.id}/answer", json={"selected": ["z"]})
    assert bad.status == 422
    ok = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/asks/{ask.id}/answer", json={"selected": ["b"]})
    assert ok.status == 202
    assert (await ask.future)["selected"] == ["b"]


async def test_log_and_patch_message(bot_client, fake_provider):
    chat = await _chat(bot_client)
    logged = await (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/log", json={
        "text": "a cat", "blocks": [{"type": "task", "holder": "shape:x"}]})).json()
    reply = logged["messages"][1]
    patched = await bot_client.patch(f"/comfyart/bot/chats/{chat['id']}/messages/{reply['id']}",
                                     json={"blocks": [{"type": "task", "holder": "shape:x", "srcs": ["/v"]}]})
    assert patched.status == 200
    assert chat_store.list_messages(chat["id"])[1]["blocks"][0]["srcs"] == ["/v"]
    assert chat_store.get_chat(chat["id"])["title"] == "a cat"


async def test_patch_refuses_the_streaming_message(bot_client, fake_provider):
    fake_provider.gate = asyncio.Event()
    chat = await _chat(bot_client)
    started = await (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "x"})).json()
    resp = await bot_client.patch(f"/comfyart/bot/chats/{chat['id']}/messages/{started['assistant_message']['id']}",
                                  json={"blocks": []})
    assert resp.status == 409
    fake_provider.gate.set()
    await wait_bot_done(bot_client, chat["id"])


async def test_refs_need_an_attachment_capable_provider(bot_client, fake_provider, monkeypatch):
    from ComfyArt.bot.providers import ProviderCaps
    monkeypatch.setattr(type(fake_provider), "capabilities", lambda self: ProviderCaps(attachments=False))
    chat = await _chat(bot_client)
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": "x", "refs": [{"id": "shape:a", "src": "/api/view?filename=a.png"}]})
    assert resp.status == 400
    assert "cannot take images" in (await resp.json())["error"]


async def test_settings_validate_keys_and_types(bot_client):
    assert (await bot_client.put("/comfyart/settings", json={"nope": 1})).status == 400
    assert (await bot_client.put("/comfyart/settings", json={"enable-bot": "yes"})).status == 400
    saved = await (await bot_client.put("/comfyart/settings", json={"bot-local-llm-url": "http://h/v1"})).json()
    assert saved["bot-local-llm-url"] == "http://h/v1"
    assert saved["ocr-engine"] == "local"
    assert (await bot_client.put("/comfyart/settings", json={"ocr-engine": "cloud"})).status == 400
    saved = await (await bot_client.put("/comfyart/settings", json={"ocr-engine": "agent"})).json()
    assert saved["ocr-engine"] == "agent"


async def test_status_survives_a_failing_probe(bot_client, fake_provider, monkeypatch):
    async def boom(self):
        raise OSError(448, "untrusted mount point")
    monkeypatch.setattr(type(fake_provider), "probe", boom)
    resp = await bot_client.get("/comfyart/bot/status")
    assert resp.status == 200
    entry = next(p for p in (await resp.json())["providers"] if p["id"] == "fake-test")
    assert entry["available"] is False and "untrusted mount point" in entry["detail"]


def test_reap_marks_unfinished_messages_aborted():
    chat = chat_store.create_chat(user="default", project="p", provider="codex")
    msg = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[], status="streaming")
    ACTIVE_TURNS.clear()
    reap_stale_messages()
    assert chat_store.list_messages(chat["id"])[0]["status"] == "aborted"
    assert msg["status"] == "streaming"


async def test_a_broken_history_block_does_not_stick_the_turn(bot_client, fake_stateless):
    chat = await _chat(bot_client, provider="fake-stateless")
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=["not a block", {"type": "text", "text": "earlier"}])
    await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "next"})
    data = await wait_bot_done(bot_client, chat["id"])
    assert data["messages"][-1]["status"] == "done"
    assert fake_stateless.last_turn.history == [{"role": "user", "text": "earlier"}]


async def test_a_chat_whose_provider_is_gone_can_still_be_deleted(bot_client, fake_provider, monkeypatch):
    from ComfyArt.api import bot as bot_api
    from ComfyArt.bot.turns import TurnState
    from ComfyArt.bot.providers import TurnHandle
    chat = await _chat(bot_client)
    ACTIVE_TURNS[chat["id"]] = TurnState(TurnHandle(), chat["id"], "m")
    monkeypatch.setattr(bot_api, "get_provider", lambda _id: None)
    assert (await bot_client.delete(f"/comfyart/bot/chats/{chat['id']}")).status == 200
    assert chat_store.get_chat(chat["id"]) is None
