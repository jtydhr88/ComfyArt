"""#730: paid MCP tools stay capped without a valid bot_chat; unknown bot_chat is rejected."""
from __future__ import annotations

import pytest
from conftest import write_settings

from ComfyArt.api import chat_store, mcp, paid_guard
from ComfyArt.bot.guide import PAID_TOOLS

ZH_STOP = "已生成 4 张仍未完成，已停止，未继续扣费，请告诉我怎么调整"
EN_STOP = ("Generated 4 images and still not done, so I stopped; no further "
           "charges. Tell me how to adjust.")


def _rpc(method, params=None, rid=1):
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}


@pytest.fixture
def submits(monkeypatch):
    log = []

    def fake(name):
        async def handler(args):
            if name in PAID_TOOLS:
                log.append((name, dict(args)))
                return {"ids": [f"gen:{len(log)}"]}
            return {"ok": True}
        return handler

    # Re-wrap after swapping the underlying handler so the paid guard stays on top.
    for name in PAID_TOOLS:
        if name not in mcp.TOOLS:
            continue
        monkeypatch.setitem(
            mcp.TOOLS, name,
            {**mcp.TOOLS[name], "handler": fake(name), "_paid_guarded": False})
    mcp._install_paid_handler_guards()
    yield log
    paid_guard.TURNS.clear()


@pytest.mark.asyncio
async def test_paid_call_without_turn_is_guarded(bot_client, submits):
    write_settings(**{"enable-mcp": True})
    headers = {"Mcp-Session-Id": "sess-730-cap"}
    # DEFAULT_CAP = 4 → 5th call must refuse with the cap text
    results = []
    for i in range(5):
        resp = await bot_client.post(
            "/comfyart/mcp",
            json=_rpc("tools/call", {"name": "generate_image", "arguments": {"prompt": f"p{i}"}}, rid=i),
            headers=headers,
        )
        assert resp.status == 200, await resp.text()
        results.append(await resp.json())
    assert len(submits) == 4
    fifth = results[4]["result"]
    assert fifth["isError"] is True
    assert fifth["content"][0]["text"].startswith(EN_STOP)

    # Reference rule on the same no-turn bucket: seed product refs, then call without them.
    paid_guard.TURNS.clear()
    key = paid_guard.noturn_key("sess-730-ref")
    paid_guard.begin_turn(
        key,
        text="用这张产品图做电商图",
        provider_text="用这张产品图做电商图（图片 id: shape:src） Use the ComfyArt skill 'product'",
        lang="en",
    )
    # Force product refs the same way product_refs would for a product skill line
    paid_guard.TURNS[key].refs = ["shape:src"]
    submits.clear()
    resp = await bot_client.post(
        "/comfyart/mcp",
        json=_rpc("tools/call", {"name": "generate_image", "arguments": {"prompt": "no refs"}}, rid=99),
        headers={"Mcp-Session-Id": "sess-730-ref"},
    )
    body = await resp.json()
    assert body["result"]["isError"] is True
    assert "shape:src" in body["result"]["content"][0]["text"]
    assert "nothing was charged" in body["result"]["content"][0]["text"]
    assert len(submits) == 0


@pytest.mark.asyncio
async def test_unknown_bot_chat_rejected(bot_client, submits):
    write_settings(**{"enable-mcp": True})
    resp = await bot_client.post(
        "/comfyart/mcp?bot_chat=does-not-exist",
        json=_rpc("tools/call", {"name": "generate_image", "arguments": {"prompt": "x"}}),
    )
    assert resp.status == 403
    data = await resp.json()
    assert data["error"]["code"] == -32000
    assert "unknown bot_chat" in data["error"]["message"]
    assert len(submits) == 0


@pytest.mark.asyncio
async def test_guard_runs_at_handler_level(submits, monkeypatch):
    """Calling the generate_image handler directly (not via _tools_call) still hits before_call."""
    seen: list[str] = []
    real_before = paid_guard.before_call

    def spy(chat_id, name, args, *, external=False):
        seen.append(name)
        return real_before(chat_id, name, args, external=external)

    monkeypatch.setattr(paid_guard, "before_call", spy)
    paid_guard.TURNS.clear()
    handler = mcp.TOOLS["generate_image"]["handler"]
    # First four succeed under anonymous noturn; fifth refuses.
    for i in range(4):
        out = await handler({"prompt": f"h{i}"})
        assert out["ids"]
    assert seen.count("generate_image") == 4
    assert len(submits) == 4
    with pytest.raises(paid_guard.PaidRefused) as e:
        await handler({"prompt": "h4"})
    assert e.value.message.startswith(EN_STOP)
    assert len(submits) == 4
    assert seen.count("generate_image") == 5
