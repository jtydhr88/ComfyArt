"""#247: external agent setup guide in the mode menu, Agent Settings and docs (static, $0)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
SETTINGS = (ROOT / "src/ui/BotSettings.tsx").read_text()
PICKER = (ROOT / "src/ui/AgentPicker.tsx").read_text()
DOCS = ROOT / "docs-site"
PROVIDERS = ("claude-code", "codex", "qwen-code", "deepseek-harness", "hermes")
LINKS = (
    "https://docs.claude.com/en/docs/claude-code/overview",
    "https://developers.openai.com/codex/cli",
    "https://github.com/QwenLM/qwen-code",
    "https://www.npmjs.com/package/@deepseek-ai/dsh",
    "https://hermes-agent.nousresearch.com/docs/getting-started/installation",
)


def test_copy_zh_en():
    # #399 (PR #401): brand is the {brand} placeholder (rendered as BRAND.name = Loomi), not hard-coded ComfyArt
    # #345: section retitled 本机第三方 Agent / Local third-party agents; desc expands install+login+detect+no-keys
    assert ZH["agentSetup.title"] == "本机第三方 Agent" and EN["agentSetup.title"] == "Local third-party agents"
    assert ZH["agentSetup.desc"] == "用你电脑上已安装并登录的 Claude Code、Codex、Hermes 等。检测到才会出现在列表里；{brand} 不保存它们的密钥。"
    assert EN["agentSetup.desc"] == "Use Claude Code, Codex, Hermes, and similar tools already installed and signed in on this computer. They only appear in the list when detected; {brand} never stores their keys."
    assert (ZH["agentSetup.setUp"], EN["agentSetup.setUp"]) == ("去配置", "Set up")
    assert (ZH["agentSetup.connected"], EN["agentSetup.connected"]) == ("已连接", "Connected")
    assert (ZH["agentSetup.copy"], EN["agentSetup.copy"]) == ("复制", "Copy")
    assert (ZH["agentSetup.checkAgain"], EN["agentSetup.checkAgain"]) == ("重新检测", "Check again")
    assert (ZH["agentSetup.viewGuide"], EN["agentSetup.viewGuide"]) == ("查看教程", "View guide")
    assert {k for k in ZH if k.startswith("agentSetup.")} == {k for k in EN if k.startswith("agentSetup.")}


def test_official_links_and_guide_path():
    for p, link in zip(PROVIDERS, LINKS):
        assert re.search(rf"'?{p}'?: '{re.escape(link)}'", SETTINGS), p
    assert "AGENT_GUIDE_PATH = '/guides/external-agents'" in SETTINGS
    assert "/comfyart/mcp" in SETTINGS


def _off_row() -> str:
    i = PICKER.index("ca-agentpick__off")
    start = PICKER.rfind("<button", 0, i)
    return PICKER[start:PICKER.index("</button>", i) + len("</button>")]


def test_undetected_row_opens_setup_not_switch():
    # #257: whole-row button opens settings; onClick is on the row, not a nested setup button
    off = _off_row()
    assert "agentSetupFocusAtom.set(p.id)" in off and "botSettingsOpenAtom.set(true)" in off
    assert "pick(p.id)" not in off


def test_undetected_row_whole_row_opens_settings():
    # #257/#247: whole-row button opens settings (not aria-disabled); 去配置 sits in the ✓ column
    off = _off_row()
    assert 'type="button"' in off and "botSettingsOpenAtom.set(true)" in off
    assert "aria-disabled" not in off
    assert "ca-agentpick__check" in off and "ca-agentpick__setup" in off
    assert off.index("ca-agentpick__check") < off.index("ca-agentpick__setup")
    css = (ROOT / "src/styles/shell.css").read_text()
    assert "min-width: 52px" in css and "justify-content: flex-end" in css


def test_undetected_row_shows_detail_reason():
    # #324: off row shows one-line reason (status) + title prefers provider.detail
    off = _off_row()
    assert "offRowTitle(p)" in off and "offRowReason(p)" in off
    assert "ca-agentpick__status" in off
    assert "offRowTitle" in PICKER and "offRowReason" in PICKER
    assert "executable not found" in PICKER  # probe-miss → short i18n
    assert "agentPicker.notDetected" in PICKER and "agentSetup.setUp" in PICKER
    css = (ROOT / "src/styles/shell.css").read_text()
    assert "ca-agentpick__off .ca-agentpick__status" in css
    assert "max-width: 140px" in css


def test_redetect_clears_probe_cache():
    bot_ts = (ROOT / "src/bot.ts").read_text()
    settings = SETTINGS
    api = (ROOT / "api/bot.py").read_text()
    providers = (ROOT / "bot/providers.py").read_text()
    assert "refresh: true" in settings or "refresh: true" in settings.replace(" ", "")
    assert "refreshBot({ refresh: true })" in settings
    assert "?refresh=1" in bot_ts and "opts?.refresh" in bot_ts
    assert 'query.get("refresh") == "1"' in api
    assert "clear_probe_cache()" in api
    assert "def clear_probe_cache(self)" in providers


def test_docs_pages_nav_and_links():
    nav = json.loads((DOCS / "docs.json").read_text())
    flat = json.dumps(nav)
    assert '"guides/external-agents"' in flat and '"zh/guides/external-agents"' in flat
    for page, prefix in (("guides", ""), ("zh/guides", "/zh")):
        text = (DOCS / page / "external-agents.mdx").read_text()
        for link in LINKS:
            assert link in text
        assert "/comfyart/mcp" in text and "PORT" in text
        assert not re.search(r"ws_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{16,}", text)
        for img in re.findall(r'src="(/images/[^"]+)"', text):
            assert (DOCS / img.lstrip("/")).is_file(), img
        for other in ("agent.mdx", "mcp.mdx"):
            assert f"{prefix}/guides/external-agents" in (DOCS / page / other).read_text()


def test_settings_modal_wider_and_tab_hint_contrast():
    css = (ROOT / "src/styles/shell.css").read_text()
    assert ".ca-modal__card.ca-botsettings" in css and "560px" in css
    canvas = (ROOT / "src/styles/canvas.css").read_text()
    hint = re.search(r"\.ca-bar__hint \{[^}]*\}", canvas).group(0)
    assert "--ca-muted" not in hint


def test_dist_has_setup():
    js = "".join(p.read_text(errors="ignore") for p in (ROOT / "dist/assets").glob("*.js"))
    assert "external-agents" in js and "ca-agentsetup" in js


def test_hermes_settings_copy_and_fields():
    assert "botSettings.hermesSshHost" in ZH and "botSettings.hermesSshHost" in EN
    assert "botSettings.hermesProfile" in ZH and "botSettings.hermesProfile" in EN
    assert 'data-testid="hermes-settings"' in SETTINGS
    assert "bot-hermes-ssh-host" in SETTINGS and "bot-hermes-profile" in SETTINGS
    assert "hermes" in SETTINGS
