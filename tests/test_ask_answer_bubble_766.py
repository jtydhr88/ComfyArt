"""#766: after submit/skip, ask answer is a right user bubble — not the old left grey 问/答 bar."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
read = lambda p: (ROOT / p).read_text(encoding="utf-8")


def test_question_answered_is_right_user_bubble():
    msg = read("src/ui/ChatMessage.tsx")
    answered = msg.split("function QuestionAnswered")[1].split("\nfunction QuestionBlock")[0]
    assert 'data-testid="ask-answer-bubble"' in answered
    assert 'className="ca-chat__user"' in answered
    assert "ca-chat__bubble--ask" in answered
    assert "ca-qmemo" not in answered  # old left grey bar gone
    assert "isAskSkipped" in msg
    assert "chatMessage.skipThisQuestion" in answered
    # prefixes live inside the bubble text as Q:/A: or 问:/答:
    assert "chatMessage.qaAsk" in answered and "chatMessage.qaAnswer" in answered
    assert "lines.join(" in answered


def test_locales_qa_and_skip_copy():
    en = json.loads(read("src/locales/en.json"))
    zh = json.loads(read("src/locales/zh.json"))
    assert en["chatMessage.qaAsk"] == "Q" and en["chatMessage.qaAnswer"] == "A"
    assert zh["chatMessage.qaAsk"] == "问" and zh["chatMessage.qaAnswer"] == "答"
    assert en["chatMessage.skipThisQuestion"] == "Skip this question"
    assert zh["chatMessage.skipThisQuestion"] == "跳过这个问题"


def test_bubble_ask_typography():
    css = read("src/styles/shell.css")
    rule = css.split(".ca-chat__bubble--ask {")[1].split("}")[0]
    assert "500 14px/24px" in rule and "var(--ca-font)" in rule
    assert "var(--ca-text)" in rule
    assert "ca-qmemo" not in read("src/styles/overlays.css")


def test_no_lovart_string_in_src():
    src = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.ts*"))
    assert "Lovart" not in src
