"""#408 unload + clear-cache slice: Settings menu entries adapted for WaveSpeed (no local models)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ComfyArt.api import wavespeed
from ComfyArt.api._common import app_path
from tests.test_wavespeed import ws  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_ui_and_locales_present():
    menu = (ROOT / "src/ui/SettingsMenu.tsx").read_text()
    assert "settings-unload" in menu and "settings-clear-cache" in menu
    assert "unloadModels" in menu and "clearCache" in menu
    assert "settings.unloadModels" in menu and "settings.clearCache" in menu
    assert "reportSuccess" in menu and "showMemoryToast" in menu
    # nav jump (互跳) is deferred — must not appear in this slice
    assert "backToComfyUI" not in menu
    # #498: history lives in SettingsMenu (settings-ws-history), not a rail id
    assert "rail-ws-history" not in menu
    assert "settings-ws-history" in menu
    comfy = (ROOT / "src/comfy.ts").read_text()
    assert "export async function unloadModels" in comfy
    assert "export async function clearCache" in comfy
    assert "/comfyart/wavespeed/unload" in comfy
    assert "/comfyart/cache/clear" in comfy
    toasts = (ROOT / "src/ui/ErrorToasts.tsx").read_text()
    assert "reportSuccess" in toasts and "severity: 'success'" in toasts
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["settings.unloadModels"] == "卸载模型"
    assert zh["settings.clearCache"] == "清缓存"
    assert "{0}" in zh["settings.unloadModelsDone"] and "{1}" in zh["settings.unloadModelsDone"]
    assert "{0}" in zh["settings.clearCacheDone"] and "{1}" in zh["settings.clearCacheDone"]
    assert en["settings.unloadModels"] == "Unload models"
    assert en["settings.clearCache"] == "Clear cache"
    assert "{0}" in en["settings.unloadModelsDone"] and "{1}" in en["settings.unloadModelsDone"]
    assert "{0}" in en["settings.clearCacheDone"] and "{1}" in en["settings.clearCacheDone"]
    # No ComfyUI /free endpoint — WaveSpeed-adapted paths only
    assert "/free" not in comfy
    assert "freeMemory" not in menu


@pytest.mark.asyncio
async def test_unload_clears_model_list_and_price_table(ws):
    wavespeed._catalog.clear()
    wavespeed._catalog.update({"at": time.time(), "models": {"a/b": {}, "c/d": {}, "e/f": {}}})
    wavespeed._quotes.clear()
    wavespeed._quotes.update({"q1": (0.01, time.time()), "q2": (0.02, time.time())})

    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/wavespeed/unload")
        body = await res.json()
        assert res.status == 200
        assert body == {"models": 3, "prices": 2}
        assert wavespeed._catalog.get("models") == {}
        assert wavespeed._catalog.get("at") == 0.0
        assert "stale" not in wavespeed._catalog
        assert not wavespeed._quotes
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_clear_cache_clears_local_caches_and_thumbs_keeps_outputs(ws):
    # #499: these are module-level caches; earlier tests in a full run leave entries behind (seen: 94 != 4).
    # Start from empty so the count checks exactly the 4 seeded below.
    for c in (wavespeed._map_cache, wavespeed._seg_cats, wavespeed._seg_masks, wavespeed._uploaded):
        c.clear()
    wavespeed._map_cache[("x", "depth", 1)] = b"1"
    wavespeed._seg_cats["img"] = ["a"]
    wavespeed._seg_masks[("img", "a")] = b"m"
    wavespeed._uploaded[("u", 1, 1)] = "https://example/x"
    import shutil
    shutil.rmtree(app_path("thumbs"), ignore_errors=True)
    os.makedirs(app_path("thumbs"), exist_ok=True)
    for i in range(3):
        Path(app_path("thumbs", f"t{i}.webp")).write_bytes(b"x")
    import folder_paths
    out = Path(folder_paths.get_output_directory()) / "keep.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"png")

    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/cache/clear")
        body = await res.json()
        assert res.status == 200
        # 1 map + 1 seg_cat + 1 seg_mask + 1 uploaded = 4
        assert body["entries"] == 4
        assert body["thumbs"] == 3
        assert not wavespeed._map_cache and not wavespeed._seg_cats
        assert not wavespeed._seg_masks and not wavespeed._uploaded
        assert not os.listdir(app_path("thumbs"))
        assert out.read_bytes() == b"png"  # generated files untouched
    finally:
        await client.close()
