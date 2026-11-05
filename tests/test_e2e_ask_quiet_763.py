"""#763 HOLD 98fa5b44 (design 5783457718 / product 5783482534 / QA 6655783604): no empty 输出中… / Outputting…
shell with the docked question, after Skip, or after an answer before reply tokens; plain generating keeps it."""
import os
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUTPUTTING = {"zh": "输出中…", "en": "Outputting…"}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    if not (ROOT / "node_modules/.bin/rolldown").exists():
        pytest.skip("node_modules missing")
    d = tmp_path_factory.mktemp("ask763")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/ask763/rolldown.config.mjs"],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:var(--ca-page,#f5f5f5)}}{css}</style>"
        f"<div id=root></div><script src=app.js></script>", encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.firefox.launch()
        except Exception as e:
            pytest.skip(f"no firefox: {e}")
        yield b
        b.close()


def _state(browser, bundle, scene, lang, theme="light"):
    page = browser.new_page(viewport={"width": 400, "height": 720})
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}&scene={scene}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    bubble = page.locator('[data-testid="ask-answer-bubble"]')
    qmemo = page.locator(".ca-qmemo").count()
    st = {
        "status": page.locator(".ca-process__status").count(),
        "outRow": page.locator('.ca-process__row[data-kind="outputting"]').count(),
        "footer": page.locator('[data-testid="footer"]').count(),
        "dock": page.locator('[data-testid="question-dock"]').count(),
        "botText": page.locator('[data-testid="bot"]').inner_text(),
        "qmemo": qmemo,
        "bubbleCount": bubble.count(),
        "bubbleAsk": bubble.get_attribute("data-ask") if bubble.count() else None,
        "bubbleText": bubble.inner_text() if bubble.count() else "",
        "bubbleIsUser": bubble.evaluate("el => el.classList.contains('ca-chat__user')") if bubble.count() else False,
    }
    page.close()
    return st


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("scene", ["q-open", "skip-after", "answer-before-tokens"])
def test_no_outputting_shell_with_or_right_after_question(browser, bundle, scene, lang):
    st = _state(browser, bundle, scene, lang)
    assert st["status"] == 0 and st["outRow"] == 0 and st["footer"] == 0, st
    assert OUTPUTTING[lang] not in st["botText"], st
    assert st["dock"] == (1 if scene == "q-open" else 0), st


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_generating_without_question_keeps_outputting(browser, bundle, lang):
    st = _state(browser, bundle, "gen-no-question", lang)
    assert st["outRow"] == 1 and st["status"] == 1 and OUTPUTTING[lang] in st["botText"], st


# --- #766: answered/skip → right user bubble, never left grey 问/答 bar ---
SKIP_COPY = {"zh": "跳过这个问题", "en": "Skip this question"}
QA_PREFIX = {"zh": ("问:", "答:"), "en": ("Q:", "A:")}


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_skip_is_right_user_bubble(browser, bundle, lang):
    st = _state(browser, bundle, "skip-after", lang)
    assert st["qmemo"] == 0 and st["bubbleCount"] == 1 and st["bubbleAsk"] == "skip", st
    assert st["bubbleIsUser"] is True
    assert st["bubbleText"].strip() == SKIP_COPY[lang], st
    assert "问 /" not in st["botText"] and "Q /" not in st["botText"]


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_answer_is_right_user_bubble_with_qa_lines(browser, bundle, lang):
    st = _state(browser, bundle, "answer-before-tokens", lang)
    assert st["qmemo"] == 0 and st["bubbleCount"] == 1 and st["bubbleAsk"] == "answer", st
    assert st["bubbleIsUser"] is True
    q, a = QA_PREFIX[lang]
    text = st["bubbleText"]
    assert q in text and a in text, st
    # label for option 'm' is 极简 / Minimal
    assert ("极简" in text) or ("Minimal" in text), st
    # not the old left grey process-style bar
    assert st["bubbleText"].count("\n") >= 1 or "\n" in repr(st["bubbleText"])


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_other_typed_is_right_user_bubble(browser, bundle, lang):
    st = _state(browser, bundle, "other-typed", lang)
    assert st["qmemo"] == 0 and st["bubbleCount"] == 1 and st["bubbleAsk"] == "answer", st
    q, a = QA_PREFIX[lang]
    text = st["bubbleText"]
    assert q in text and a in text, st
    assert ("Hand-drawn ink" in text) or ("手绘墨线" in text), st
    assert len(text.splitlines()) >= 2, st


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_thought_hides_ask_user(browser, bundle, lang):
    """#766 HOLD: collapsed Thought tip + expanded body must not show ask_user."""
    page = browser.new_page(viewport={"width": 400, "height": 720})
    page.goto(f"{bundle}/index.html?lang={lang}&theme=light&scene=thought-leak")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    # Collapsed tip (ca-chat__arg on the lone Thought row)
    tip = page.locator(".ca-chat__thought .ca-chat__arg")
    tip_text = tip.inner_text() if tip.count() else ""
    assert "ask_user" not in tip_text.lower(), tip_text
    # Expand Thought
    page.locator(".ca-chat__thought .ca-chat__step").click()
    page.wait_for_timeout(100)
    body = page.locator(".ca-chat__thoughttext")
    body_text = body.inner_text() if body.count() else ""
    assert "ask_user" not in body_text.lower(), body_text
    # Visible planning line kept
    visible = (tip_text + "\n" + body_text).lower()
    assert "plan" in visible or "logo" in visible or tip.count() == 0
    # Bubble still present
    assert page.locator('[data-testid="ask-answer-bubble"]').count() == 1
    page.close()
