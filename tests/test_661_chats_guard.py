"""#661 createSkill white-screen — chatsAtom must never be undefined."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_661_load_chats_never_sets_undefined():
    """loadChats / AgentPanel must coerce missing chats to []."""
    bot = (ROOT / "src/bot.ts").read_text()
    assert "chats ?? []" in bot or ".chats ?? []" in bot
    assert "providers ?? []" in bot or ".providers ?? []" in bot
    panel = (ROOT / "src/ui/AgentPanel.tsx").read_text()
    assert "(chatsAtom.get() ?? [])" in panel
    assert "useValue(chatsAtom) ?? []" in panel
    picker = (ROOT / "src/ui/AgentPicker.tsx").read_text()
    assert "(chatsAtom.get() ?? [])" in picker
    details = (ROOT / "src/ui/TaskDetails.tsx").read_text()
    assert "(chatsAtom.get() ?? [])" in details
