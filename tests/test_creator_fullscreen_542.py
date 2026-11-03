"""#542 Step 1 + 2 (source locks): both create entries hand off identically (chip, focus, chat-only full screen, no send);
landing = heading + our existing three start buttons; 选择 Skill = "/" + skills list; collapse keeps the draft, no confirm."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
SKILLS_PAGE = (ROOT / "src/home/Skills.tsx").read_text()
PANEL = (ROOT / "src/ui/AgentPanel.tsx").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
APP = (ROOT / "src/App.tsx").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


def _branch() -> str:
    m = re.search(r"if \(createSkill\) \{(.*?)\n  \}\n", HANDOFF, re.S)
    assert m
    return m.group(1)


def _starts() -> str:
    return PANEL.split('<div className="ca-chat__starts">', 1)[1].split("</div>", 1)[0]


def test_both_entries_make_the_identical_call() -> None:
    home = re.search(r'data-testid="home-create-skill" onClick=\{\(\) => \{(.*?)\}\}>', HOME, re.S).group(1)
    assert "newProject({ createSkill: '1' })" in home
    assert "const createConversational = () => newProject({ createSkill: '1' })" in SKILLS_PAGE
    # no entry pre-sets state of its own: everything comes from the one handoff branch
    assert "skillCreatorAtom" not in SKILLS_PAGE and "skillCreatorAtom" not in home


def test_handoff_sets_chip_focus_max_and_never_sends() -> None:
    b = _branch()
    for s in ("chatViewAtom.set('max')", "agentModeAtom.set('agent')",
              "skillCreatorAtom.set({ on: true, chip: CREATE_ENTRY_CHIP_KEY })", "focusComposer()"):
        assert s in b, s
    for bad in ("sendToAgent", "generateDirect", "if (text) {"):
        assert bad not in b, bad
    # P1-1: providers are loaded (not sent to) before focus, so the pill reads Loomi like the normal composer
    assert "await refreshBot().catch(() => {})" in b
    assert b.rstrip().endswith("return")


def test_landing_heading_and_three_existing_buttons() -> None:
    assert ZH["agentPanel.creatorStartTitle"] == "你想设计什么？"  # #650 gold
    assert EN["agentPanel.creatorStartTitle"]
    assert "{creating\n" in PANEL and 'data-testid="creator-landing-title"' in PANEL
    # #650: creator landing uses the gold pill copy; normal panel keeps the old keys
    pairs = re.findall(r"t\(creating \? '(agentPanel\.\w+)' : '(agentPanel\.\w+)'\)", _starts())
    assert pairs == [("agentPanel.creatorAddReference", "agentPanel.uploadReference"), ("agentPanel.creatorStartFromSkill", "agentPanel.startFromSkill"), ("agentPanel.creatorAddBrandKit", "agentPanel.useBrandKit")]
    assert [ZH[a] for a, _ in pairs] == ["添加你的参考", "从技能开始", "添加你的品牌套件"]
    assert [EN[a] for a, _ in pairs] == ["Add your reference", "Start from skill", "Add your brand kit"]
    assert [ZH[b] for _, b in pairs] == ["上传本地参考", "选择 Skill 开始创作", "使用品牌套件"]
    # #650 known diff: no Pinterest pill on the creator landing (home tab keys are separate)
    assert "pinterest" not in PANEL.lower() and not [k for k in ZH if k.startswith("agentPanel.") and "pinterest" in (k + ZH[k]).lower()]


def test_buttons_stacked_172x38_not_stretched() -> None:
    assert re.search(r"\.ca-chat__empty\[data-creator\] \.ca-chat__starts \{[^}]*gap: 15px;[^}]*align-items: center", SHELL)
    assert re.search(r"\.ca-chat__empty\[data-creator\] \.ca-chat__start \{[^}]*width: 172px;[^}]*height: 38px;[^}]*flex: none;[^}]*white-space: nowrap", SHELL)


def test_input_card_720_docked_bottom_and_lovart_placeholder() -> None:
    assert ".ca-agent[data-max] .ca-composer { width: min(720px, calc(100% - 24px));" in SHELL
    assert ".ca-agent[data-max] .ca-composer { margin-bottom: 8px; }" in SHELL
    # #650: creator landing input is empty per gold; normal composer keeps the hint
    assert "placeholder={skillCreator.on ? '' : t('composer.describeYourDesignNeedsFor')}" in COMPOSER
    assert ZH["composer.describeYourDesignNeedsFor"] == '请描述你的设计需求，"/"使用技能，"@"引用参考'


def test_pick_skill_inserts_slash_and_focuses_no_send() -> None:
    btn = re.search(r"onClick=\{\(\) => \{ (draftAtom\.set\('/'\);[^}]*)\}\}>", _starts())
    assert btn and ".ca-composer__input" in btn.group(1) and "send" not in btn.group(1).lower()
    # the composer opens its existing skills list for a lone "/"
    assert r"const slash = /^\/(\S*)$/.exec(draft)" in COMPOSER and "(slash && filtered.length > 0) && (" in COMPOSER


def test_brand_button_leaves_full_screen_so_the_panel_is_visible() -> None:
    assert "onClick={() => { if (max) onMax(); libraryTabAtom.set('brand'); sideAtom.set('assets') }}" in PANEL


def test_collapse_and_back_have_no_confirm_and_keep_draft() -> None:
    assert "onCollapse={() => setChat('closed')}" in APP
    for src in (PANEL, APP, COMPOSER, HANDOFF):
        assert "confirm(" not in src and "beforeunload" not in src and "popstate" not in src
    # the draft lives in a module atom, so unmounting the panel on collapse keeps it
    assert "value={draft}" in COMPOSER and "draftAtom.set(e.target.value)" in COMPOSER


def test_entering_creates_new_project() -> None:
    assert "location.assign(projectUrl(uuid().slice(0, 8), { [NEW_PARAM]: '1', ...params }))" in (ROOT / "src/projects.ts").read_text()
