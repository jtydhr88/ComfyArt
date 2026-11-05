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
    for cls in ("ca-q__head", "ca-q__label", "chatMessage.pageOf", "ca-q__letter", "ca-q__skip", "ca-q__submit", "ca-q__key"):
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
