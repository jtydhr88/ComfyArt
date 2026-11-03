"""#650 follow-up e2e: Skill Creator creation-complete state = Lovart gold create-done.png.
Rows 「Skill ready」 → 「Skill Created」, then the skill card (name, description, Preview, Try this skill), then prose.
Optional SHOT_650_DONE=<dir> writes create-done-loomi-{en,zh}.png at the gold viewport (1280×800)."""
import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install")

COPY = {
    "en": {"rows": ["Skill ready", "Skill Created"], "preview": "Preview", "try": "Try this skill"},
    "zh": {"rows": ["技能加载完成", "技能已创建"], "preview": "预览", "try": "试用此技能"},
}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("createdone650")
    subprocess.run(
        [str(ROOT / "node_modules" / ".bin" / "rolldown"), "-c", "tests/js/createdone650/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:#fff}}{css}</style>"
        f"<div id=root></div><script src=app.js></script>")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_creation_complete_matches_lovart(browser, bundle, lang):
    page = browser.new_page(viewport={"width": 1280, "height": 800})  # gold create-done.png viewport (1280×800, dpr 1)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    c = COPY[lang]
    rows = page.evaluate("""() => [...document.querySelectorAll('#done .ca-process__row')].map(r => [r.dataset.kind,
      (r.querySelector('.ca-process__label') || r).innerText.replace(/\\s+/g,' ').trim()])""")
    assert rows == [["skill", c["rows"][0]], ["skill_created", c["rows"][1]]], rows
    card = page.get_by_test_id("skill-created-card")
    assert card.count() == 1 and card.get_attribute("data-skill") == "zz-test-delete"
    assert page.get_by_test_id("skill-created-name").inner_text() == "zz-test-delete"
    assert page.get_by_test_id("skill-created-desc").inner_text() == "A throwaway test skill"
    assert page.get_by_test_id("skill-created-preview").inner_text() == c["preview"]
    assert page.get_by_test_id("skill-created-try").inner_text() == c["try"]
    # order: rail → card → prose (gold), and buttons sit on the card's right, Preview left of Try
    order = page.evaluate("""() => {
      const r = el => el.getBoundingClientRect()
      const rail = document.querySelector('#done .ca-process__row:last-child'), card = document.querySelector('[data-testid=skill-created-card]')
      const prose = [...document.querySelectorAll('#done *')].find(e => e.children.length === 0 && /Created the minimal/.test(e.textContent))
      const p = document.querySelector('[data-testid=skill-created-preview]'), t = document.querySelector('[data-testid=skill-created-try]')
      return [r(rail).bottom <= r(card).top, r(card).bottom <= r(prose).top, r(p).right <= r(t).left, r(t).right <= r(card).right]
    }""")
    assert order == [True, True, True, True], order
    if os.environ.get("SHOT_650_DONE"):
        page.screenshot(path=f"{os.environ['SHOT_650_DONE']}/create-done-loomi-{lang}.png")
    page.close()
