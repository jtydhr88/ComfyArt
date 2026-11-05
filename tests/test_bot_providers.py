from __future__ import annotations

import pytest
from ComfyArt.bot.providers import BotEvent
from conftest import wait_bot_done as _wait_done


@pytest.fixture()
def client(bot_client):
    return bot_client


class TestModelOverride:
    async def test_status_reports_models(self, client, fake_provider):
        resp = await client.get("/comfyart/bot/status")
        data = await resp.json()
        entry = next(p for p in data["providers"] if p["id"] == "fake-test")
        assert entry["models"] == []

    async def test_setting_reaches_provider(self, client, fake_provider,
                                            monkeypatch):
        from conftest import write_settings
        write_settings(**{"bot-model-fake-test": "shiny-model"})
        resp = await client.post("/comfyart/bot/chats",
                                 json={"project": "p", "provider": "fake-test"})
        chat = (await resp.json())["chat"]
        resp = await client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": "hello"})
        assert resp.status == 200
        await _wait_done(client, chat["id"])
        assert fake_provider.last_turn.model == "shiny-model"

    async def test_stateless_provider_gets_history(self, client, fake_stateless):
        fake_stateless.script = [BotEvent(t="delta", text="first answer")]
        resp = await client.post("/comfyart/bot/chats",
                                 json={"project": "p", "provider": "fake-stateless"})
        chat = (await resp.json())["chat"]
        await client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                          json={"text": "first question"})
        await _wait_done(client, chat["id"])
        assert fake_stateless.last_turn.history == []
        fake_stateless.script = [BotEvent(t="delta", text="second answer")]
        await client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                          json={"text": "second question"})
        await _wait_done(client, chat["id"])
        assert fake_stateless.last_turn.history == [
            {"role": "user", "text": "first question"},
            {"role": "assistant", "text": "first answer"},
        ]

    async def test_stateful_provider_gets_no_history(self, client, fake_provider):
        resp = await client.post("/comfyart/bot/chats",
                                 json={"project": "p", "provider": "fake-test"})
        chat = (await resp.json())["chat"]
        await client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                          json={"text": "one"})
        await _wait_done(client, chat["id"])
        assert fake_provider.last_turn.history is None

    async def test_blank_setting_means_default(self, client, fake_provider):
        resp = await client.post("/comfyart/bot/chats",
                                 json={"project": "p", "provider": "fake-test"})
        chat = (await resp.json())["chat"]
        resp = await client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": "hello"})
        assert resp.status == 200
        await _wait_done(client, chat["id"])
        assert fake_provider.last_turn.model == ""
