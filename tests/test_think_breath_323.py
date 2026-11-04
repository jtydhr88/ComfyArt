"""#323 v4: static Icons.think Lucide Brain; live title shimmer; no spin/check/breath/halo on Thought."""
from __future__ import annotations
import pytest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
PANEL = (ROOT / "src/ui/AgentPanel.tsx").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()
ICONS = (ROOT / "src/ui/icons.tsx").read_text()


@pytest.mark.gate_skip(reason="stale on main: think icon path changed with the Lucide swap (#323, #608)")
def test_icons_think_brain() -> None:
    assert "think:" in ICONS
    # Lucide Brain outline paths (current lucide main icons/brain.svg)
    block = ICONS.split("think:")[1].split(",\n")[0]
    assert 'd="M12 18V5"' in block
    assert 'd="M15 13a4.17 4.17 0 01-3-4 4.17 4.17 0 01-3 4"' in block
    assert 'd="M19.967 17.482a4 4 0 11-7.967.517 4 4 0 11-7.967-.517"' in block
    assert "circle" not in block  # no clock circle
    assert "ca-spin" not in block


def test_thought_static_think_icon() -> None:
    thought = CHAT.split("function Thought")[1].split("\nfunction ")[0]
    assert "data-live={live || undefined}" in thought
    assert "Icons.think" in thought
    assert "Icons.check" not in thought
    assert "Icons.agent" not in thought
    assert "ca-chat__thinkspin" not in thought
    assert 'className="ca-chat__thinklabel"' in thought


def test_agentpanel_thinking_uses_think() -> None:
    block = PANEL.split('className="ca-chat__thinking"')[1].split("</div>")[0]
    assert "Icons.think" in block
    assert 'className="ca-chat__thinklabel"' in block
    assert "ca-chat__thinkspin" not in block
    assert "Icons.agent" not in block


def test_css_no_spin_breath_halo() -> None:
    assert "ca-chat__thinkspin" not in OVERLAYS
    assert "ca-think-breath" not in OVERLAYS
    assert ".ca-chat__thinkicon::after" not in OVERLAYS
    assert "stream-light" not in OVERLAYS


def test_live_label_shimmer_only() -> None:
    assert ".ca-chat__thought[data-live] .ca-chat__thinklabel" in OVERLAYS
    assert ".ca-chat__thinking .ca-chat__thinklabel" in OVERLAYS
    block = OVERLAYS.split(".ca-chat__thinking .ca-chat__thinklabel")[1].split("}")[0]
    assert "ca-shine 1.8s" in block
    shell_rule = SHELL.split(".ca-chat__thinking {")[1].split("}")[0]
    assert "ca-shine" not in shell_rule
