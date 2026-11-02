"""#498 personal SettingsMenu + Usage modal + canvas usage ledger."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[1]


def test_settings_menu_ac_structure():
    menu = (ROOT / "src/ui/SettingsMenu.tsx").read_text()
    home = (ROOT / "src/home/HomeApp.tsx").read_text()
    usage = (ROOT / "src/ui/UsageDialog.tsx").read_text()
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    overlays = (ROOT / "src/styles/overlays.css").read_text()

    assert "Icons.settings" in home and "rail-settings" in home
    assert "SettingsRailBtn" in home and "rail-settings-balance" in home
    assert "rail-ws-history" not in home

    low = menu.lower()
    for banned in ("avatar", "upgrade", "create team", "subscription", "billing",
                   "contact us", "what\'s new", "whats new", "install plugin",
                   "lovart", "log out", "logout", "coming soon"):
        assert banned not in low, banned

    for tid in ("settings-usage", "settings-lang", "settings-theme", "settings-ws-key",
                "settings-unload", "settings-clear-cache", "settings-ws-history", "settings-guide"):
        assert tid in menu
    assert menu.index("settings-usage") < menu.index("settings-lang") < menu.index("settings-theme")
    assert menu.index("settings-theme") < menu.index("settings-ws-key") < menu.index("settings-unload")
    assert menu.index("settings-unload") < menu.index("settings-clear-cache") < menu.index("settings-ws-history")
    assert menu.index("settings-ws-history") < menu.index("settings-guide")

    assert "FlySub" in menu
    assert "label={t('settings.language')}" in menu  # › submenu, not inline section
    assert "label={t('projectHeader.theme')}" in menu

    assert zh["settings.usage"] == "用量" and en["settings.usage"] == "Usage"
    assert zh["settings.usageCost"] == "花费（按提交报价）"
    assert zh["settings.usageFootnote"] == "以 WaveSpeed 余额为准"
    assert zh["settings.usageEmpty"] == "还没有花费记录"
    assert en["settings.usageCost"]  # present
    assert "ca-usage" in usage and "PAGE_SIZE = 10" in usage
    assert "770px" in overlays and "480px" in overlays

    for path in (ROOT / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css", ".json"}:
            continue
        text = path.read_text(errors="ignore")
        assert "lovart" not in text.lower(), path

    ws = (ROOT / "api/wavespeed.py").read_text()
    assert "_record_submit_usage" in ws and "await _record_submit_usage" in ws
    assert '@routes.get("/comfyart/usage")' in ws

    # Chat must not surface per-call spend
    for rel in ("src/ui/AgentPanel.tsx", "src/ui/TaskDetails.tsx", "src/ui/Composer.tsx"):
        blob = (ROOT / rel).read_text()
        assert "amount_usd" not in blob
        assert "per-call" not in blob.lower()


@pytest.mark.asyncio
async def test_usage_list_filters_and_pages(monkeypatch):
    rows = []
    # 13 billable + noise
    rows.append(dict(id=1, kind="paid_call", status="done", amount_usd=0.12, reason="wavespeed-ai/x", tool="t2i", created_at=100))
    rows.append(dict(id=2, kind="paid_call", status="done", amount_usd=0.0, reason="zero", tool="t2i", created_at=101))
    rows.append(dict(id=3, kind="paid_call", status="failed", amount_usd=0.05, reason="fail", tool="t2i", created_at=102))
    rows.append(dict(id=4, kind="paid_call", status="cancelled", amount_usd=0.07, reason="cancel", tool="t2i", created_at=103))
    rows.append(dict(id=5, kind="llm_tokens", status="done", amount_usd=0.01, reason="tokens", tool="chat", created_at=104))
    for i in range(12):
        rows.append(dict(id=10 + i, kind="paid_call", status="done", amount_usd=0.01 + i * 0.001,
                         reason=f"model-{i}", tool="img", created_at=200 + i))

    store = MagicMock()
    store.list_usage_events.return_value = rows
    monkeypatch.setattr("ComfyArt.api.providers.ensure_run_store", lambda: store)

    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.get("/comfyart/usage?page=1&page_size=10")
        assert res.status == 200
        body = await res.json()
        assert body["page"] == 1 and body["page_size"] == 10
        assert body["total"] == 13
        assert len(body["items"]) == 10
        assert all(it["amount_usd"] > 0 for it in body["items"])
        # newest first
        assert body["items"][0]["detail"] == "model-11"
        res2 = await client.get("/comfyart/usage?page=2&page_size=10")
        body2 = await res2.json()
        assert len(body2["items"]) == 3
        details = {it["detail"] for it in body["items"] + body2["items"]}
        assert "wavespeed-ai/x" in details
        assert "zero" not in details and "fail" not in details and "tokens" not in details
    finally:
        await client.close()
