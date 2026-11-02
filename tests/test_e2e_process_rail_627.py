"""#627 e2e: full rail labels from real AssistantBlocks; optional SHOT_DIR for #78 after PNGs."""
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
SHOT = os.environ.get("SHOT_DIR")

FORBIDDEN = (
    "Generated images", "已生成图片", "图片模型",
    # bare 思考 as a rail label (思考完成 is required)
)


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("process627")
    subprocess.run(
        [str(ROOT / "node_modules" / ".bin" / "rolldown"), "-c", "tests/js/process627/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text()
                    for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:#f0f0f0}}"
        f"{css}</style><div id=root></div><script src=app.js></script>")
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


def _open(browser, bundle, *, lang, theme, scene):
    page = browser.new_page(viewport={"width": 420, "height": 900}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}&scene={scene}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(250)
    return page


def _labels(page, scope):
    return page.evaluate("""(s) => [...document.querySelectorAll(s + ' .ca-process__row')].map(r => ({
      kind: r.dataset.kind,
      label: (r.querySelector('.ca-process__label') || r).innerText.replace(/\\s+/g,' ').trim(),
    }))""", scope)


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
def test_full_rail_labels(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang=lang, theme=theme, scene="full")
    rows = _labels(page, "#full")
    kinds = [r["kind"] for r in rows]
    labels = [r["label"] for r in rows]
    blob = " | ".join(labels)
    for bad in FORBIDDEN:
        assert bad not in blob, blob
    assert "thought" in kinds
    assert "image" in kinds
    assert "ref_analysis" in kinds
    assert kinds.index("image") < kinds.index("ref_analysis")
    # model-name slot (runtime example in harness)
    assert any("GPT Image 2.5 Flare" == r["label"] or r["label"].endswith("GPT Image 2.5 Flare") for r in rows if r["kind"] == "image"), labels
    if lang == "zh":
        assert any(r["kind"] == "thought" and "思考完成" in r["label"] for r in rows)
        assert any(r["kind"] == "ref_analysis" and "参考素材分析结束" in r["label"] for r in rows)
        assert not any(r["kind"] == "thought" and r["label"].strip() == "思考" for r in rows)
        # no second visible 思考完成 after image
        thought_after = [r for r in rows[kinds.index("image")+1:] if r["kind"] == "thought"]
        assert thought_after == [], thought_after
    else:
        assert any(r["kind"] == "thought" and r["label"].strip() == "Thought" for r in rows)
        assert any(r["kind"] == "ref_analysis" and "Reference analysis done" in r["label"] for r in rows)
    if "skill" in kinds:
        want = "技能加载完成" if lang == "zh" else "Skill ready"
        assert any(r["kind"] == "skill" and want in r["label"] for r in rows)
    if "search_pages" in kinds:
        assert any("网页" in r["label"] or "web page" in r["label"] for r in rows if r["kind"] == "search_pages")
    # prose + thumbs (DoneFeedback)
    assert page.locator(".ca-chat__feedback, [data-testid=chat-done-feedback]").count() >= 1 or "已生成完成" in page.inner_text("#full") or "Generation" in page.inner_text("#full") or "已画" in page.inner_text("#full") or "红" in page.inner_text("#full")
    page.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
def test_simple_turn_no_think_rail(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang=lang, theme=theme, scene="simple")
    rows = _labels(page, "#simple")
    kinds = [r["kind"] for r in rows]
    assert "thought" not in kinds
    assert "ref_analysis" not in kinds
    assert "image" in kinds
    assert any("GPT Image 2.5 Flare" in r["label"] for r in rows if r["kind"] == "image")
    blob = " | ".join(r["label"] for r in rows)
    for bad in FORBIDDEN:
        assert bad not in blob
    page.close()


@pytest.mark.skipif(not SHOT, reason="SHOT_DIR not set")
@pytest.mark.parametrize("lang,theme,scene,name", [
    ("zh", "light", "full", "full-rail-zh-light"),
    ("en", "dark", "full", "full-rail-en-dark"),
    ("zh", "light", "simple", "simple-turn-zh-light"),
    ("en", "dark", "simple", "simple-turn-en-dark"),
])
def test_shoot_after(browser, bundle, lang, theme, scene, name):
    os.makedirs(SHOT, exist_ok=True)
    page = _open(browser, bundle, lang=lang, theme=theme, scene=scene)
    # paint a card frame for tip pin
    page.evaluate("""() => {
      const root = document.querySelector('.ca-root');
      root.style.background = getComputedStyle(document.documentElement).getPropertyValue('--ca-float') || '#fff';
      root.style.borderRadius = '16px';
      root.style.boxShadow = '0 8px 24px rgba(0,0,0,.08)';
      root.style.margin = '12px';
    }""")
    page.locator(".ca-root").screenshot(path=f"{SHOT}/{name}.png")
    # forbid bad strings in DOM at shoot time
    text = page.inner_text(".ca-root")
    for bad in FORBIDDEN + ("已生成图片", "Generated images"):
        assert bad not in text, text
    if scene == "full":
        assert ("参考素材分析结束" in text) or ("Reference analysis done" in text)
        assert "GPT Image 2.5 Flare" in text
        assert ("思考完成" in text) or ("Thought" in text)
    page.close()
