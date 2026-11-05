"""#437 (#430 D): chat process rows follow the reference wording."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
PANEL = (ROOT / "src/ui/AgentPanel.tsx").read_text(encoding="utf-8")


def test_thought_done_row() -> None:
    assert ZH["chatMessage.thought"] == "思考完成"
    assert EN["chatMessage.thought"] == "Thought"
    assert "已思考" not in json.dumps(ZH, ensure_ascii=False)


def test_thinking_row_behind_one_flag_and_key() -> None:
    assert ZH["chatMessage.thinking"] == "思考中…" and EN["chatMessage.thinking"] == "Thinking…"
    assert "export const SHOW_THINKING_ROW = true" in CHAT
    assert "SHOW_THINKING_ROW ? t('chatMessage.thinking') : t('chatMessage.outputting')" in CHAT
    assert CHAT.count("t('chatMessage.thinking')") == 1
    for k in ("agentPanel.thinking",):
        assert k not in ZH and k not in EN and k not in PANEL


def test_plain_text_reply_only_outputting() -> None:
    assert ZH["chatMessage.outputting"] == "输出中…"
    assert "t('chatMessage.outputting')" in PANEL
    # reasoning: the Thought row carries 输出中…, no second label; #763: no 工作中… label either (Stop lives in the composer)
    assert "m.blocks.some((b) => b.type === 'thinking') ? '' : t('chatMessage.outputting')" in PANEL
    assert "agentPanel.working" not in PANEL


def test_generation_row_is_model_name() -> None:
    for blob in (EN, ZH):
        assert "chatMessage.imagesGenerated" not in blob
        assert "chatMessage.videoGenerated" not in blob
    assert "已生成图片" not in json.dumps(ZH, ensure_ascii=False)
    assert "if (opts?.model) return opts.model" in CHAT


def test_skill_and_search_rows() -> None:
    assert (ZH["chatMessage.skillReady"], EN["chatMessage.skillReady"]) == ("技能加载完成", "Skill ready")
    assert (ZH["chatMessage.webSearchDone"], EN["chatMessage.webSearchDone"]) == ("联网搜索结果", "Web search results")


def test_no_tidy_memory_row() -> None:
    assert "整理记忆" not in json.dumps(ZH, ensure_ascii=False)


def test_search_row_count_plural_favicon_and_card():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    src = (root / "src/ui/ChatMessage.tsx").read_text()
    en = json.loads((root / "src/locales/en.json").read_text())
    zh = json.loads((root / "src/locales/zh.json").read_text())
    assert "=== 1 ? 'chatMessage.webPage' : 'chatMessage.webPages'" in src
    assert en["chatMessage.webPage"] == "{0} web page" and en["chatMessage.webPages"] == "{0} web pages"
    assert zh["chatMessage.webPage"] == "{0} 个网页" == zh["chatMessage.webPages"]
    # real favicon of the search source, not a drawn glyph; the globe icon stays
    assert "s2/favicons?domain=" in src and "ca-process__favicon" in src
    assert "search_pages: Icons.globe" in src
    assert '<span className="ca-process__cardtitle">{t(\'chatMessage.webSearchDone\')}</span>' in src
    assert en["chatMessage.webSearchDone"] == "Web search results" and zh["chatMessage.webSearchDone"] == "联网搜索结果"


def test_no_wait_for_results_row_when_done():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src/ui/ChatMessage.tsx").read_text()
    assert "if (done && b.type === 'tool_use' && toolName(b.name) === 'wait_generation') return" in src


def test_results_follow_generation_row():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src/ui/ChatMessage.tsx").read_text()
    assert "genAt = items.length" in src
    assert "items.splice(genAt < 0 ? items.length : genAt, 0," in src


def test_favicon_failure_falls_back_to_globe_only():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    src = (root / "src/ui/ChatMessage.tsx").read_text()
    fav = src.split("function Favicon(")[1].split("\n}\n")[0]
    # onError unmounts the <img>: no empty slot, no broken-image glyph; the globe icon is untouched
    assert "onError={() => setFailed(true)}" in fav
    assert "if (failed) return null" in fav
    assert "{s.favicon && <Favicon src={s.favicon} />}" in src
    assert "<img className=\"ca-process__favicon\"" not in src.replace(fav, "")
    assert "search_pages: Icons.globe" in src


def test_rail_is_per_group_segment():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    css = (root / "src/styles/overlays.css").read_text()
    base = (root / "src/styles/base.css").read_text()
    chat = (root / "src/ui/ChatMessage.tsx").read_text()
    assert "s.kind !== 'image' && <span className=\"ca-process__spine\" data-testid=\"process-rail\"" in chat
    assert "top: 20px; bottom: 0; width: 1px;" in css and "background: var(--ca-rail);" in css and "--ca-rail: rgba(0,0,0,.1);" in base and "--ca-rail: rgba(255,255,255,.12);" in base
    assert "margin: calc(12px - var(--ca-process-row-gap)) 0 0;" in css
