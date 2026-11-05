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
    st = {
        "status": page.locator(".ca-process__status").count(),
        "outRow": page.locator('.ca-process__row[data-kind="outputting"]').count(),
        "footer": page.locator('[data-testid="footer"]').count(),
        "dock": page.locator('[data-testid="question-dock"]').count(),
        "botText": page.locator('[data-testid="bot"]').inner_text(),
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
