"""#393 render-level tests for the #391 stop cards: the real RunStop (src/ui/ChatMessage.tsx) + src/styles CSS in
Chromium. Copy comes from the backend's locked table (agent_loop.CARD_COPY / _card_body). fetch is recorded in
the page, nothing leaves it. SHOT_DIR=<dir> also writes the #78 review shots."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.bot import agent_loop as al

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")
SHOT = os.environ.get("SHOT_DIR")
DETAILS = {lk: [f"{lab} {v}" for lab, v in zip(al._DETAIL_LABEL[lk], ("42", "21.4k", "32", "1:14"))] for lk in ("zh", "en")}
TONE = {"done": "ok", "budget": "warn", "hard_cap": "warn", "stuck": "warn", "stuck:self_check_failed": "warn",
        "user_stop": "neutral", "user_stop:quote_declined": "neutral", "error:network": "error", "error": "error",
        "awaiting_confirm:not_approved": "warn"}
# (copy key, body args): the same 11 cards as the #78 sheet
CARDS = [("done", dict(n=4, m=4, x=None, kind="image")), ("done", dict(n=0, m=None, x=None, kind="")),
         ("budget", dict(n=3, m=4, x=40, kind="image", reason={"zh": "已运行 15 分钟，达到单次时长上限。已生成的图保留在画布上。", "en": "Ran for 15 min, reaching the per-run time limit. Images already made stay on the canvas."})), ("hard_cap", dict(n=3, m=4, x=None, kind="image")),
         ("budget", dict(n=0, m=None, x=None, kind="", reason={"zh": "已运行 15 分钟，达到单次时长上限。已生成的图保留在画布上。", "en": "Ran for 15 min, reaching the per-run time limit. Images already made stay on the canvas."})),
         ("stuck", dict(n=0, m=None, x=None, kind="", step={"zh": "生成图片", "en": "Generate image"},
                            reason={"zh": "连续重复同一步，已停下", "en": "Repeated the same step in a row, stopped"})),
         ("stuck:self_check_failed", dict(n=3, m=4, x=None, kind="image", miss={"zh": "1 张图", "en": "1 image"})),
         ("user_stop", dict(n=3, m=4, x=None, kind="image")),
         ("user_stop:quote_declined", dict(n=3, m=4, x=None, kind="image")),
         ("error:network", dict(n=3, m=4, x=None, kind="image")),
         ("error", dict(n=0, m=None, x=None, kind="", reason={"zh": "模型服务暂时不可用", "en": "The model service is unavailable"}))]


def block(key, kw, i):
    copy = {"key": key, "action": al._PRIMARY_ACTION.get(key.split(":")[0], "continue"), "tone": TONE[key]}
    for lk in ("zh", "en"):
        title, _, primary, secondary = al.CARD_COPY[key][lk]
        args = {k: (v[lk] if isinstance(v, dict) else v) for k, v in kw.items()}
        copy[lk] = {"title": title, "body": al._card_body(key, lk, **args), "primary": primary, "secondary": secondary}
    return {"type": "run_stop", "run_id": f"run{i}", "stop": {"reason": key.split(":")[0]}, "copy": copy,
            "details": DETAILS, "can_continue": key != "done"}


BLOCKS = [block(k, kw, i) for i, (k, kw) in enumerate(CARDS)]
NEUTRAL = ("user_stop", "user_stop:quote_declined")
# #492: reason=done is filtered in RunStop — visible sheet excludes the two done cards.
VISIBLE_BLOCKS = [b for b in BLOCKS if b["stop"]["reason"] != "done"]
DONE_BLOCKS = [b for b in BLOCKS if b["stop"]["reason"] == "done"]

# effective colour of text: its colour alpha-composited over the card, the card over the panel
CONTRAST = """(sel) => {
  const p = (s) => { const m = s.match(/[\\d.]+/g).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1] }
  const over = (f, b) => [0, 1, 2].map((i) => f[i] * f[3] + b[i] * (1 - f[3])).concat(1)
  const lum = (c) => { const v = c.slice(0, 3).map((x) => { x /= 255; return x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4 }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2] }
  const panel = p(getComputedStyle(document.getElementById('wrap')).backgroundColor)
  return [...document.querySelectorAll(sel)].map((e) => {
    const card = over(p(getComputedStyle(e.closest('.ca-run')).backgroundColor), panel)
    const fg = over(p(getComputedStyle(e).color), card)
    const [a, b] = [lum(fg), lum(card)].sort((x, y) => y - x)
    return { key: e.closest('.ca-run').dataset.key, text: e.textContent, color: getComputedStyle(e).color,
             size: getComputedStyle(e).fontSize, ratio: (a + .05) / (b + .05) }
  })
}"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = tmp_path_factory.mktemp("runstop")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/runstop/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(f"<!doctype html><meta charset=utf-8><style>{css}</style><div id=root></div>"
        "<script>window.WebSocket = class { constructor() {} send() {} close() {} addEventListener() {} }</script>"  # no live socket
        "<script src=app.js></script>")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browsers not installed
            pytest.skip(f"no chromium: {e}")
        pg = b.new_page(viewport={"width": 412, "height": 900}, device_scale_factor=2)
        pg.goto((d / "index.html").as_uri())
        pg.wait_for_function("window.__ready === true")
        yield pg
        b.close()


def render(page, lang="zh", theme="light", blocks=BLOCKS):
    page.evaluate("([b, l, t]) => { window.__calls = []; window.__render(b, l, t) }", [blocks, lang, theme])
    page.wait_for_selector("#wrap")
    if any((b.get("stop") or {}).get("reason") != "done" for b in blocks):
        page.wait_for_selector(".ca-run")
    else:
        page.wait_for_function("() => document.getElementById('wrap') && !document.querySelector('.ca-run')")
    return page


def run(page, key):
    return page.locator(f'.ca-run[data-key="{key}"]').first


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_details_collapsed_by_default(page, lang):
    render(page, lang)
    assert page.evaluate("[...document.querySelectorAll('.ca-run details')].map(d => d.open)") == [False] * len(VISIBLE_BLOCKS)


def test_no_progress_bar_or_meter(page):
    render(page)
    assert page.locator(".ca-run progress, .ca-run meter, .ca-run [role=progressbar], .ca-run [class*='bar']").count() == 0


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_no_cap_numbers(page, lang):
    render(page, lang)
    page.evaluate("document.querySelectorAll('.ca-run details').forEach(d => d.open = true)")
    for e in page.locator(".ca-run__title, .ca-run__details").all():
        txt = e.inner_text()
        assert "/" not in txt and "上限" not in txt and not re.search(r"\bcap\b|\blimit\b", txt, re.I), txt
    lines = page.locator(".ca-run__details > div").all_inner_texts()
    assert lines[:4] == DETAILS[lang]           # actual values only


def test_zh_has_no_english_labels(page):
    render(page, "zh")
    page.evaluate("document.querySelectorAll('.ca-run details').forEach(d => d.open = true)")
    for txt in page.locator(".ca-run").all_inner_texts():
        assert not re.findall(r"[A-Za-z]{2,}", txt), txt   # 「21.4k」 is the only latin letter


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_hard_cap_title_has_no_step_count(page, lang):
    render(page, lang)
    t = run(page, "hard_cap").locator(".ca-run__title").inner_text()
    assert t == al.CARD_COPY["hard_cap"][lang][0] and not re.search(r"\d", t)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_cancelled_is_not_error_styled(page, theme):
    render(page, "zh", theme)
    c = run(page, "user_stop:quote_declined")
    assert c.get_attribute("data-tone") != "error"
    err = run(page, "error").locator(".ca-run__title").evaluate("e => getComputedStyle(e).color")
    assert c.locator(".ca-run__title").evaluate("e => getComputedStyle(e).color") != err


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_contrast_neutral_titles_details_and_danger(page, theme):
    render(page, "zh", theme)
    page.evaluate("document.querySelectorAll('.ca-run details').forEach(d => d.open = true)")
    text2 = page.evaluate("""() => { const e = document.createElement('span'); e.style.color = 'var(--ca-text-2)';
        document.getElementById('wrap').appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c }""")
    danger = page.evaluate("""() => { const e = document.createElement('span'); e.style.color = 'var(--ca-danger)';
        document.getElementById('wrap').appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c }""")
    titles = [r for r in page.evaluate(CONTRAST, ".ca-run__title") if r["key"] in NEUTRAL]
    details = page.evaluate(CONTRAST, ".ca-run__details > summary, .ca-run__details > div")
    errors = [r for r in page.evaluate(CONTRAST, ".ca-run__title") if r["key"].startswith("error")]
    assert len(titles) == 2 and details and len(errors) == 2
    for r in titles + details:
        assert r["color"] == text2, r                      # the --ca-text-2 token
        assert r["ratio"] >= 4.5, r
    for r in details:
        assert r["size"] == "12px", r
    for r in errors:
        assert r["color"] == danger, r                     # the --ca-danger token, not a hardcoded red
        assert r["ratio"] >= 4.5, r


@pytest.mark.parametrize("key,want", [("budget", 2), ("hard_cap", 2), ("user_stop:quote_declined", 1)])
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_buttons(page, key, want, lang):
    render(page, lang)
    btns = run(page, key).locator("button").all_inner_texts()
    _, _, primary, secondary = al.CARD_COPY[key][lang]
    assert btns == ([secondary, primary] if want == 2 else [primary])
    if key == "user_stop:quote_declined":
        assert al.CARD_COPY[key]["zh"][2:] == ("继续", None)   # product ruling: no 「先到这里」


def test_cancelled_continue_only_asks_the_server_to_resume(page):
    """继续 on 已取消 charges nothing in the client: one POST to /api/comfyart/bot/runs/<id>/continue, the server re-shows the quote card
    (tests/test_agent_budget_391_el.py::test_cancelled_continue_requotes_before_any_charge)."""
    i = next(i for i, b in enumerate(BLOCKS) if b["copy"]["key"] == "user_stop:quote_declined")
    render(page, "zh", blocks=[BLOCKS[i]])     # the panel CSS clips overflow, so render the card alone
    run(page, "user_stop:quote_declined").locator("button", has_text="继续").click()
    page.wait_for_function("window.__calls.length > 0")
    page.wait_for_timeout(200)
    calls = page.evaluate("window.__calls")
    assert [(c["method"], c["url"]) for c in calls] == [("POST", f"/api/comfyart/bot/runs/run{i}/continue")]
    assert json.loads(calls[0]["body"]) == {"lang": "zh"}




# --- #492: hide reason=done stop card (product AC 6519682583 / 6526218598) ---

def test_done_reason_not_rendered_in_sheet(page):
    """#492 flip: the two done cards in BLOCKS must NOT render (was: they rendered). Backend payload unchanged."""
    assert len(DONE_BLOCKS) == 2
    render(page)
    assert page.locator('.ca-run[data-reason="done"]').count() == 0
    assert page.locator(".ca-run").count() == len(VISIBLE_BLOCKS)


def test_done_only_blocks_leave_empty_dom(page):
    """#492: even a chat that only has reason=done run_stop blocks paints zero .ca-run nodes."""
    render(page, blocks=DONE_BLOCKS)
    assert page.locator(".ca-run").count() == 0
    assert page.locator('.ca-run[data-reason="done"]').count() == 0


@pytest.mark.parametrize("key", [
    "budget", "hard_cap", "stuck", "stuck:self_check_failed",
    "user_stop", "user_stop:quote_declined", "error:network", "error",
])
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_non_done_reasons_still_render(page, key, lang):
    """#492: every non-done stop reason keeps title/body/详情 on main behavior."""
    b = next(x for x in BLOCKS if x["copy"]["key"] == key)
    render(page, lang, blocks=[b])
    card = run(page, key)
    assert card.count() == 1
    assert card.get_attribute("data-reason") == key.split(":")[0]
    assert card.locator(".ca-run__title").inner_text() == al.CARD_COPY[key][lang][0]
    body = al.CARD_COPY[key][lang][1]
    # body templates may format; rendered body comes from block copy
    assert card.locator(".ca-run__body").inner_text() == b["copy"][lang]["body"]
    assert card.locator("details.ca-run__details").count() == 1
    assert card.locator("details.ca-run__details summary").inner_text() in ("详情", "Details")


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_awaiting_confirm_still_renders(page, lang):
    """#492: awaiting_confirm unchanged — one assert (not in the #393 11-card sheet)."""
    key = "awaiting_confirm:not_approved"
    b = block(key, dict(n=0, m=None, x=None, kind=""), 99)
    # reason for awaiting_confirm keys: split gives awaiting_confirm
    assert b["stop"]["reason"] == "awaiting_confirm"
    render(page, lang, blocks=[b])
    card = run(page, key)
    assert card.count() == 1
    assert card.get_attribute("data-reason") == "awaiting_confirm"
    assert card.locator(".ca-run__title").inner_text() == al.CARD_COPY[key][lang][0]
    assert card.locator("button").count() >= 1  # Continue


def test_continue_on_non_done_latest_unchanged(page):
    """#492: Continue on non-done latest card still POSTs /continue; done stays buttonless."""
    budget = next(b for b in BLOCKS if b["copy"]["key"] == "budget")
    render(page, "zh", blocks=[budget])
    run(page, "budget").locator("button.ca-panel__primary").click()
    page.wait_for_function("window.__calls.length > 0")
    calls = page.evaluate("window.__calls")
    assert calls[0]["method"] == "POST" and calls[0]["url"].endswith("/continue")
    # done alone: no buttons in DOM
    render(page, "zh", blocks=DONE_BLOCKS[:1])
    assert page.locator(".ca-run button").count() == 0


def test_chatmessage_source_filters_done():
    """#492 source lock: AssistantBlocks skips done; RunStop returns null; stoppedSubmitted/latest scan untouched."""
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "if (reason === 'done') return null" in chat
    assert "if ((b.stop?.reason ?? '') !== 'done')" in chat
    # stoppedSubmitted still counts every run_stop (incl done) — do not narrow it
    ss = chat.split("export function stoppedSubmitted")[1].split("export function ")[0]
    assert "b.type === 'run_stop'" in ss
    assert "done" not in ss.split("return")[0]  # no done filter inside stoppedSubmitted
    # latest-card scan still looks at all run_stop siblings (string locked next to the filter)
    assert "latest={!m.blocks.slice(i + 1).some((x) => x.type === 'run_stop')}" in chat

@pytest.mark.skipif(not SHOT, reason="SHOT_DIR not set")
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_shots_78(page, lang, theme):
    os.makedirs(SHOT, exist_ok=True)
    render(page, lang, theme)
    page.locator("#wrap").screenshot(path=f"{SHOT}/run-stop-{lang}-{theme}.png")
    render(page, lang, theme, [b for b in BLOCKS if b["copy"]["key"] in ("budget",)][:1])
    page.evaluate("document.querySelectorAll('.ca-run details').forEach(d => d.open = true)")
    page.locator(".ca-run").first.screenshot(path=f"{SHOT}/run-stop-details-{lang}-{theme}.png")
    for k in NEUTRAL:
        render(page, lang, theme, [b for b in BLOCKS if b["copy"]["key"] == k])
        page.evaluate("document.querySelectorAll('.ca-run details').forEach(d => d.open = true)")
        page.locator(".ca-run").first.screenshot(path=f"{SHOT}/run-stop-{k.split(':')[-1].replace('_', '-')}-details-{lang}-{theme}.png")
