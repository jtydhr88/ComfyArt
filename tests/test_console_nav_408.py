"""#408 WaveSpeed console task-history nav (adapted from upstream ComfyUI↔ComfyArt).

#498: home-rail history entry moved into SettingsMenu; ProjectHeader menu entry stays.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = "https://wavespeed.ai/history"


def test_ui_and_locales_present():
    home = (ROOT / "src/home/HomeApp.tsx").read_text()
    header = (ROOT / "src/ui/ProjectHeader.tsx").read_text()
    menu = (ROOT / "src/ui/SettingsMenu.tsx").read_text()
    icons = (ROOT / "src/ui/icons.tsx").read_text()
    key = (ROOT / "src/wavespeedKey.ts").read_text()

    # #498: rail no longer hosts history; SettingsMenu does
    assert "rail-ws-history" not in home
    assert "settings-ws-history" in menu
    assert "WAVESPEED_HISTORY_URL" in menu
    assert "window.open(WAVESPEED_HISTORY_URL" in menu
    assert "_blank" in menu and "noopener" in menu
    assert "settings.waveSpeedTaskHistory" in menu
    assert "Icons.exit" in menu

    assert "WAVESPEED_HISTORY_URL" in header and "menu-ws-history" in header
    assert "Icons.exit" in header and "home.waveSpeedTaskHistory" in header
    assert "window.open(WAVESPEED_HISTORY_URL" in header

    assert "exit:" in icons
    assert "WAVESPEED_HISTORY_URL" in key and HISTORY in key
    assert "backToComfyUI" not in home and "backToComfyUI" not in header
    assert "location.assign('/')" not in home and "location.assign('/')" not in header

    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["home.waveSpeedTaskHistory"] == "打开 WaveSpeed 任务记录"
    assert en["home.waveSpeedTaskHistory"] == "Open WaveSpeed task history"
    assert "backToComfyUI" not in zh and "backToComfyUI" not in en
    assert "WaveSpeed" in zh["home.waveSpeedTaskHistory"]
    assert "任务记录" in zh["home.waveSpeedTaskHistory"]
    assert "WaveSpeed" in en["home.waveSpeedTaskHistory"]
    assert "task history" in en["home.waveSpeedTaskHistory"].lower()
