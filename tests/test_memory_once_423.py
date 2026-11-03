"""#423 one 记忆已更新 › row per turn; dedupe before write; saved note tells the model to answer now. $0, mocks only."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api.bot_turns import _TurnState, _apply_event, memory_updated_block
from ComfyArt.bot.providers import BotEvent, TurnHandle

ROOT = Path(__file__).resolve().parent.parent


def _use(i):
    return {"type": "tool_use", "id": i, "name": "local__memory", "input": {"action": "add"}}


def _add(blocks, i, ids, texts, upd=()):
    blocks.append(_use(i))
    b = memory_updated_block(blocks, i, "local__memory", json.dumps({"saved": True, "memory_ids": ids, "texts": texts, "updated_ids": list(upd)}), "success")
    if b is not None and b not in blocks:
        blocks.append(b)
    return b


def test_three_adds_merge_into_one_block_with_count():
    blocks = []
    first = _add(blocks, "c1", ["m1"], ["A"])
    assert _add(blocks, "c2", ["m2"], ["B"]) is first
    assert _add(blocks, "c3", ["m3", "m2"], ["C", "B"]) is first
    rows = [b for b in blocks if b["type"] == "memory_updated"]
    assert len(rows) == 1
    assert rows[0]["memory_ids"] == ["m1", "m2", "m3"] and rows[0]["texts"] == ["A", "B", "C"]
    assert rows[0]["count"] == 3 and rows[0]["tool_ids"] == ["c1", "c2", "c3"]


def test_unchanged_only_or_failed_add_makes_no_row():
    blocks = [_use("c1")]
    assert memory_updated_block(blocks, "c1", "local__memory", json.dumps({"saved": True, "memory_ids": []}), "success") is None
    assert memory_updated_block(blocks, "c1", "local__memory", json.dumps({"memory_ids": ["x"]}), "error") is None


def test_apply_event_appends_once_and_payload_carries_merged_block():
    st = _TurnState(TurnHandle(), "c", "m")
    pays = []
    for i, mid in (("c1", "m1"), ("c2", "m2")):
        _apply_event(st, BotEvent(t="tool_use", name="local__memory", input={"action": "add"}, id=i))
        pays.append(_apply_event(st, BotEvent(t="tool_result", name="local__memory", id=i,
                                                     text=json.dumps({"saved": True, "memory_ids": [mid], "texts": [mid]}))))
    assert sum(b.get("type") == "memory_updated" for b in st.blocks) == 1
    assert pays[-1]["memory_updated"]["memory_ids"] == ["m1", "m2"] and pays[-1]["memory_updated"]["count"] == 2


def _src(p):
    return (ROOT / p).read_text()


def test_frontend_single_row_wiring():
    bl = _src("src/botLayout.ts")
    assert "upsertMemory(" in bl and "MEMORY_SAVED_NOTE" in bl and "saved: true" in bl
    assert re.search(r"MEMORY_SAVED_NOTE = '.*reply to the user now", _src("src/memory.ts"), re.I)
    bot = _src("src/bot.ts")
    assert "findIndex((b) => b.type === 'memory_updated')" in bot
    cm = _src("src/ui/ChatMessage.tsx")
    assert "b !== firstMem" in cm and "tool_ids" in cm and "memoryIds: b.type === 'memory_updated' ? memIdsAll" in cm


@pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node")
def test_upsert_dedupes_and_updates(tmp_path):
    out = tmp_path / "m.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "memory_safety.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True,
                                    env={**os.environ, "SETTINGS": json.dumps({"proactive-memory": True, "proactive-skills": True})}).stdout)["upsert_423"]
    assert got["added"] == ["品牌色：克莱因蓝"]
    assert got["updated"] == [["a", "常用画幅：16:9", "常用画幅：9:16"]]
    assert got["unchanged"] == ["b"]
    assert sorted(got["file"]) == sorted(["常用画幅：9:16", "偏好极简", "品牌色：克莱因蓝"])


def test_update_only_add_shows_row_and_counts():
    blocks = []
    b = _add(blocks, "c1", ["old1"], ["画幅：9:16"], upd=["old1"])
    assert b is not None and b["count"] == 1 and b["updated"] == 1 and b["added_count"] == 0


def test_mixed_counts_new_plus_updated():
    blocks = []
    b = _add(blocks, "c1", ["n1"], ["A"])
    _add(blocks, "c2", ["u1"], ["画幅：9:16"], upd=["u1"])
    _add(blocks, "c3", ["n1"], ["A：2"], upd=["n1"])  # added earlier this turn, then changed: still new
    assert (b["count"], b["added_count"], b["updated"], b["updated_ids"]) == (2, 1, 1, ["u1"])


def _run_harness(tmp_path):
    out = tmp_path / "m.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "memory_safety.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True,
                                     env={**os.environ, "SETTINGS": json.dumps({"proactive-memory": True, "proactive-skills": True})}).stdout)


def test_memory_add_tool_rows_always_hidden():
    cm = _src("src/ui/ChatMessage.tsx")
    assert "memCalls.has(b.id) || memAddIds.has(b.id))" in cm   # incl. no-op identical repeat


def test_block_carries_no_undo_payload():
    blocks = [_use("c1")]
    b = memory_updated_block(blocks, "c1", "local__memory", json.dumps({"memory_ids": ["u1"], "texts": ["画幅：4:3"], "updated_ids": ["u1"], "previous": {"u1": "画幅：16:9"}}), "success")
    assert "previous" not in b and b["updated_ids"] == ["u1"]


def _git_main(p):
    r = subprocess.run(["git", "show", f"origin/main:{p}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def test_dialog_and_click_entry_identical_to_main():
    """#423 undo API + #436 shared dialog open without highlight."""
    dlg = _src("src/ui/MemoryDialog.tsx")
    assert "export function openMemoryDialog" in dlg
    assert "memoryOnboardAtom" in dlg
    assert "memoryFocusAtom.set(null)" in dlg
    assert "openMemoryDialog()" in _src("src/ui/ChatMessage.tsx")  # #436: no focus highlight
    mem = _src("src/memory.ts")
    assert "export interface MemoryFocus { id: string; undoable?: boolean }" in mem
    assert "export function undoMemoryUpdated(id: string): Promise<boolean> {\n  return removeMemory(id, 'memory-updated-undo')" in mem


def test_locales_only_add_memory_retrieved_430():
    """#430 A + #436 Arti memory entry copy; chat memory strings stay."""
    # keys #436 intentionally changes / adds on Arti page
    allow = {
        "arti.levelStatus", "arti.levelHint",
        "arti.tellYourself", "arti.tellYourselfDesc",
        "arti.learnPast", "arti.learnPastDesc", "arti.learnPastSoon",
        "arti.memory.tabEmpty", "arti.memory.goComplete",
        # #436 onboard welcome / Q1 copy
        "memoryDialog.welcomeHi", "memoryDialog.welcomeBody", "memoryDialog.ready",
        "memoryDialog.skip", "memoryDialog.confirm", "memoryDialog.other",
        "memoryDialog.nickArtist", "memoryDialog.nickBoss", "memoryDialog.nickCaptain",
        "memoryDialog.partTitle.about", "memoryDialog.partTitle.work",
        "memoryDialog.partTitle.taste", "memoryDialog.partTitle.assets",
        "memoryDialog.stepOf", "memoryDialog.freeHint",
        # #570: to3d / upscale tool panel copy
        "toolPanel.reset", "toolPanel.useNow", "toolPanel.model", "toolPanel.mode", "toolPanel.faithful", "toolPanel.enhance", "toolPanel.resolution",
        # #423: 「已保存 N 条」 under the memory row
        "chatMessage.memorySavedCount",
        # #494: 技能页标签中文化、作者行「个人」，移除旧作者与浏览量文案
        "home.skillsFavourites", "home.skillsExplore", "home.skillsPersonal",
        "home.skillsAuthorPersonal", "home.skillsCommunity", "home.skillsViews",
        "home.skills", "home.skillsCreate",
        # #509: 配乐时长提示、空风格拦截、自定义配乐工作流文案（非记忆文案）
        "audio.needMusicPrompt", "audio.needLyrics", "audio.durationByLyrics",
        "customWorkflows.action.music", "customWorkflows.musicGone", "customWorkflows.group.audio",
        "customWorkflows.action.speech", "customWorkflows.action.clone", "customWorkflows.action.sfx",
        "customWorkflows.speechGone",
        # #509 PR3: video extend/upscale/cutout + model3d custom workflows
        "customWorkflows.action.extend", "customWorkflows.action.videoUpscale",
        "customWorkflows.action.videoCutout", "customWorkflows.action.model3d",
        "customWorkflows.group.model", "customWorkflows.model3dGone", "customWorkflows.needsVideo",
        # #542: Skill Creator landing heading (not memory copy)
        "agentPanel.creatorStartTitle",
        # #539 PR-B: Assets page empty state + embedded detail upload copy (not memory copy)
        "assets.emptyTitle", "assets.emptyHint", "assets.dropHint", "assets.importUrl", "assets.dropFormats",
        "assets.newItem",
        # #539 PR-C: 20MB upload + URL import errors (not memory copy)
        "assets.tooLarge", "assets.urlInvalid", "assets.badFormat", "assets.urlFormat",
        # #568: top-bar Saved/Saving label removed (not memory copy)
        "projectHeader.saved", "projectHeader.savedAt", "projectHeader.saving",
        # #672: builtin custom-workflow card removed (not memory copy)
        "skills.customWorkflow", "skills.cat.custom-workflow", "skills.desc.custom-workflow",
    }
    for p, v in (("src/locales/zh.json", "记忆已读取"), ("src/locales/en.json", "Memory retrieved")):
        m = _git_main(p)
        if m is None:
            pytest.skip("origin/main not available")
        cur, base = json.loads(_src(p)), json.loads(m)
        assert cur.pop("chatMessage.memoryRetrieved") == v; base.pop("chatMessage.memoryRetrieved", None)
        cur.pop("chatMessage.memoryUpdated"); base.pop("chatMessage.memoryUpdated")  # #441: › moved to an svg
        cur.pop("chatMessage.memoryUpdating", None)
        base.pop("chatMessage.memoryUpdating", None)
        for k in allow:
            cur.pop(k, None)
            base.pop(k, None)
        for d in (cur, base):  # #463 skill import copy is its own namespace, not memory copy
            for k in [k for k in d if k.startswith("skillsImport.")]:
                d.pop(k)
        assert cur == base
    zh, en = json.loads(_src("src/locales/zh.json")), json.loads(_src("src/locales/en.json"))
    assert zh["chatMessage.memoryUpdated"] == "记忆已更新" and en["chatMessage.memoryUpdated"] == "Memory updated"
    assert zh["chatMessage.memoryUpdating"] == "记忆更新中" and en["chatMessage.memoryUpdating"] == "Updating memory"


def test_retrieved_row_before_updated_only_on_update_430():
    cm = _src("src/ui/ChatMessage.tsx")
    i = cm.index("kind: 'memory_retrieved'")
    assert i < cm.index("kind: kindResolved", i)  # pushed right before the 记忆已更新 › step
    assert "memBlocks.some((x) => (x.updated_ids ?? []).length > 0)" in cm
    assert "const isMemory = s.kind === 'memory_updated'" in cm  # only 记忆已更新 › is clickable
    assert "memory_retrieved: Icons.memoryHead" in cm and "memory_updating: Icons.memoryHead" in cm and "memory_updated: Icons.memoryHead" in cm
    assert "kind: 'memory_updating'" in cm and "memory-updating-row" in cm
    assert "isMemory && <span className=\"ca-process__memchev" in cm  # › only on 记忆已更新


def test_update_block_flags_retrieved_add_does_not_430():
    blocks = []
    b = _add(blocks, "c1", ["n1"], ["A"])
    assert b["updated_ids"] == []  # plain add -> no 记忆已读取
    _add(blocks, "c2", ["u1"], ["画幅：9:16"], upd=["u1"])
    assert b["updated_ids"] == ["u1"] and sum(x["type"] == "memory_updated" for x in blocks) == 1


def test_memory_row_measured_css_441() -> None:
    root = Path(__file__).resolve().parent.parent
    css = (root / "src/styles/overlays.css").read_text()
    for frag in ("--ca-memory-text: rgba(0,0,0,.55)", "--ca-memory-text: rgba(255,255,255,.55)",
                 ":last-child { height: 20px; margin: 0;",
                 "> .ca-process__row[data-kind^='memory_'] > .ca-process__spine { top: 20px; }",
                 "font-weight: 400; font-size: 14px; line-height: 20px; height: 20px; color: inherit; gap: 6px;",
                 "[data-kind^='memory_']:hover { color: var(--ca-text); }",
                 ".ca-process__memchev { width: 16px; height: 16px;"):
        assert frag in css, frag
    icons = (root / "src/ui/icons.tsx").read_text()
    line = next(l for l in icons.splitlines() if l.strip().startswith("memoryHead:"))
    assert "<Svg strokeWidth={1.5}>" in line and "fill" not in line  # #441 v7: thin outline, not solid
    cm = (root / "src/ui/ChatMessage.tsx").read_text()
    assert "{isMemory && <span className=\"ca-process__memchev ca-icon\"" in cm

    assert "memory_']:last-child) { margin-bottom" not in css  # #441 v5: no extra gap before the reply (main pitch)

def test_memory_updating_row_437() -> None:
    """#437: in-flight memory add shows 记忆更新中 (no ›); same icon; dialog pill key stays separate."""
    cm = _src("src/ui/ChatMessage.tsx")
    assert "memory_updating" in cm and "chatMessage.memoryUpdating" in cm
    assert "memory-updating-row" in cm
    assert "orderMemorySteps" in cm  # retrieved → updating → updated
    assert "MEM_STEP_ORDER" in cm
    # process row only — no ca-process__status bubble for memory_* live
    assert "!live.kind.startsWith('memory_') && <div className=\"ca-process__status\">" in cm
    # › only when isMemory (memory_updated)
    assert cm.count("memory-updated-chev") == 1
    assert "memoryDialog.saving" not in cm  # dialog pill copy is not the process-row key
    zh = json.loads(_src("src/locales/zh.json"))
    assert zh["chatMessage.memoryUpdating"] == zh["memoryDialog.saving"] == "记忆更新中"
    # EN: same words as dialog for now; process-row EN awaits design's next reference frame
    assert json.loads(_src("src/locales/en.json"))["chatMessage.memoryUpdating"] == "Updating memory"
    assert json.loads(_src("src/locales/en.json"))["memoryDialog.saving"] == "Updating memory"
    css = _src("src/styles/overlays.css")
    assert "width: 18px; height: 18px" in css.split(".ca-memory__spin")[1].split("}")[0]
    assert "gap: 6px" in css.split(".ca-memory__saving")[1].split("}")[0]
    assert "ca-mem-body-shimmer 1.6s" in css
    assert ".ca-arti-mem__row[data-saving] .ca-arti-mem__actions { display: none; }" in css


def test_saved_count_detail_wiring_423() -> None:
    """#423: chat shows 「已保存 N 条」 under the single 记忆已更新 › row; locales already ship the key."""
    cm = _src("src/ui/ChatMessage.tsx")
    assert "memoryTexts" in cm and "memTextsAll" in cm
    assert 'data-testid="memory-saved-detail"' in cm
    assert "chatMessage.memorySavedCount" in cm
    assert "ca-process__memdetail" in cm and "ca-process__memcount" in cm
    css = _src("src/styles/overlays.css")
    assert ".ca-process__memdetail" in css and ".ca-process__memcount" in css
    zh = json.loads(_src("src/locales/zh.json"))
    en = json.loads(_src("src/locales/en.json"))
    assert zh["chatMessage.memorySavedCount"] == "已保存 {0} 条"
    assert en["chatMessage.memorySavedCount"] == "Saved {0}"
