"""#763: Stop lives in the composer's right primary button; no 工作中/终止 chrome above the input;
question card keeps title + pager, soft selected rows, light Skip and solid Submit."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
read = lambda p: (ROOT / p).read_text(encoding="utf-8")


def test_generating_primary_button_is_stop():
    slot = read("src/ui/ComposerSlot.tsx")
    assert 'data-slot="stop"' in slot and "Icons.stop" in slot and "onStop" in slot
    # stop branch returns before voice/send are rendered
    assert slot.index("if (onStop)") < slot.index("<VoiceButton")
    comp = read("src/ui/Composer.tsx")
    assert "onStop={busy ? () => void stopTurn()" in comp


def test_no_working_or_stop_chrome_in_timeline():
    panel = read("src/ui/AgentPanel.tsx")
    assert "agentPanel.working" not in panel
    assert "t('agentPanel.stop')" not in panel and "stopTurn" not in panel
    assert "chatMessage.outputting" in panel  # faint streaming text stays


def test_question_card_structure():
    msg = read("src/ui/ChatMessage.tsx")
    for cls in ("ca-q__head", "ca-q__label", "ca-q__letter", "ca-q__skip", "ca-q__submit", "ca-q__key"):
        assert cls in msg
    css = read("src/styles/overlays.css")
    on = css.split(".ca-q__opt[data-on] {")[1].split("}")[0]
    assert "var(--ca-opt-on)" in on and "transparent" in on  # soft select, no outline
    sub = css.split(".ca-q__submit {")[1].split("}")[0]
    assert "background: var(--ca-strong)" in sub
    panel = read("src/ui/AgentPanel.tsx")
    assert 'data-testid="question-dock"' in panel and "dockAsks" in panel
    # the dock renders right before the composer; Stop yields to voice/send while a question waits
    assert panel.index("question-dock") < panel.index("<Composer ")
    assert "busy={busy && !docked.length}" in panel
    assert "!(dockAsks && isDockedQuestion(b))" in msg


def test_placeholder_mentions_at_reference():
    for loc in ("en", "zh"):
        ph = json.loads(read(f"src/locales/{loc}.json"))["composer.describeYourDesignNeedsFor"]
        assert '"@"' in ph and '"/"' in ph
    src = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.ts*"))
    assert "Lovart" not in src


def test_single_question_has_no_pager_and_submit_waits():
    msg = read("src/ui/ChatMessage.tsx")
    assert "const showPager = pageCount > 1" in msg and "{showPager && (" in msg
    assert 'className="ca-q__submit" disabled={!allOk}' in msg


def test_d_is_always_other_type_in_row():
    msg = read("src/ui/ChatMessage.tsx")
    block = msg.split("function QuestionBlock")[1].split("/** #328/#330")[0]
    assert "{allowOther && (" not in block
    assert 'data-other=""' in block and "disabled={!allowOther}" in block
    assert json.loads(read("src/locales/en.json"))["chatMessage.other"] == "Other (type your answer)..."


def test_skip_posts_skip_this_question():
    assert json.loads(read("src/locales/en.json"))["chatMessage.skipThisQuestion"] == "Skip this question"
    assert "t('chatMessage.skipThisQuestion')" in read("src/ui/ChatMessage.tsx")


def test_no_ask_you_timeline_row():
    msg = read("src/ui/ChatMessage.tsx")
    assert "toolName(b.name) === 'ask_user') return" in msg


def test_dock_card_geometry():
    css = read("src/styles/shell.css")
    q = css.split(".ca-chat__dock .ca-q {")[1].split("}")[0]
    assert "--ca-opt-h: 36px" in q
    assert "width: 60px; height: 32px" in css.split(".ca-chat__dock .ca-q__skip {")[1].split("}")[0]
    assert "width: 90px; height: 32px" in css.split(".ca-chat__dock .ca-q__submit {")[1].split("}")[0]


def test_at_menu_assets_then_model_and_ref_chip_restored():
    comp = read("src/ui/Composer.tsx")
    assert comp.index('data-at-group="assets"') < comp.index('data-at-group="model"')
    # 参考区 button remounted beside ModelPrefs; @ menu does not replace it
    assert "RefFrameButton" in comp and "{mode === 'agent' && !agentOff && <RefFrameButton editor={editor} />}" in comp
    assert "atOpen ? t('composer.atSearchPlaceholder')" in comp
    css = read("src/styles/shell.css")
    assert ".ca-composer > .ca-composer__suggest { position: absolute" in css
    assert "width: 255px" in css.split(".ca-composer__suggest.ca-at-menu {")[1].split("}")[0]
    mp = read("src/ui/ModelPrefs.tsx")
    assert "Icons.cube" in mp and "ca-modelprefs__btn" in mp
    # #769 model-pref glyph is equilateral wireframe cube (Lucide Box), not skewed Cuboid
    icons = read("src/ui/icons.tsx")
    assert "cube: L(Box" in icons and "cube: L(Cuboid)" not in icons
    assert "hash: L(Hash" in icons  # #769: 参考区 # is Lucide Hash (not Frame that fills the box)
    ref = read("src/ui/RefFrameButton.tsx")
    assert "ca-bar__btn--icon ca-refbtn" in ref and "Icons.hash" in ref
    assert "t('chatFrame.ref')" not in ref  # icon-only; no 参考/Ref label beside Cube
    css = read("src/styles/shell.css")
    assert ".ca-modelprefs__btn .ca-icon { width: 16px; height: 16px; }" in css
    assert ".ca-refbtn .ca-icon { width: 16px; height: 16px; }" in css
    assert ".ca-pop-anchor:has(.ca-modelprefs__btn) + .ca-composer__slotwrap { margin-left: 2px; }" in css  # #769: foot gap 4 + margin 2 → 8px → c2c 40


def test_no_outputting_shell_while_question_open_or_just_ended():
    """#763/#769: no empty 输出中… / Outputting… box with docked question, after Skip/answer, or after wait reply."""
    msg = read("src/ui/ChatMessage.tsx")
    quiet = msg.split("export function askQuiet(m: BotMessage)")[1].split("\n}\n")[0]
    assert "b.type === 'ask'" in quiet and "b.type === 'text'" in quiet and ".trim() !== ''" in quiet
    assert "m.status !== 'streaming'" in quiet  # #769: done turns quiet; plain stream-without-ask keeps Outputting
    assert "ask_user" in quiet  # pending non-ask tools keep Outputting after reply text
    blocks = msg.split("export function AssistantBlocks")[1].split("export function UserMessage")[0]
    assert "const quiet = askQuiet(m)" in blocks
    assert "b.type === 'ask' || b.type === 'task'" not in blocks  # an ask no longer spawns an outputting row
    assert blocks.count("!done && !quiet && proc.length") == 2  # both outputting rows gated
    panel = read("src/ui/AgentPanel.tsx")
    assert "!askQuiet(m)" in panel and "chatMessage.outputting" in panel
    assert "never leave an empty Outputting box" in panel or "foot" in panel


def test_generating_without_question_still_outputting():
    msg = read("src/ui/ChatMessage.tsx")
    assert "kind: 'outputting'" in msg and "label: processLabel('outputting', true)" in msg
    assert "<div className=\"ca-process__status\">{live.label}</div>" in msg
    assert "t('chatMessage.outputting')" in read("src/ui/AgentPanel.tsx")
