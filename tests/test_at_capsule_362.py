"""#362 @ menu: 参考/本项目/素材 (no Model) + canvas select → dual composer capsules."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
AGENT = (ROOT / "src/ui/AgentPanel.tsx").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
GUIDE = (ROOT / "bot/guide.py").read_text()


def _at_menu_block() -> str:
    assert 'data-testid="at-menu"' in COMPOSER
    start = COMPOSER.index('data-testid="at-menu"')
    # slice from comment through closing of atOpen block roughly
    head = COMPOSER.rfind("{/* #362:", 0, start)
    # find matching end: next major section chips or slash already passed — use ca-composer__chips boundary after
    end = COMPOSER.index("ca-composer__chips", start)
    return COMPOSER[head:end]


def test_at_menu_exactly_three_groups_in_order() -> None:
    """#763 supersedes #362: @ menu groups are Assets (refs + project + 素材) → Model."""
    block = _at_menu_block()
    assert 'data-at-group="assets"' in block and 'data-at-group="model"' in block
    assert block.index('data-at-group="assets"') < block.index('data-at-group="model"')
    assert block.count("composer.atGroup") == 2
    assert "composer.atGroupAssets" in block and "composer.atGroupModel" in block


def test_at_menu_no_model_group() -> None:
    """#763 product ruling: the Model group is required now (model tiers + More), no model-picker chrome."""
    block = _at_menu_block()
    assert 'data-at-group="model"' in block
    assert "IMAGE_MODELS" in COMPOSER and "AT_MODEL_LIMIT" in COMPOSER
    assert "model-picker" not in block.lower()
    assert '"composer.atGroupModel"' in ZH and '"composer.atGroupModel"' in EN


def test_at_filter_placeholder_style() -> None:
    """#763: the textarea placeholder becomes the search hint (no in-menu filter row)."""
    assert "composer.atSearchPlaceholder" in COMPOSER
    assert 'data-testid="at-search-hint"' in COMPOSER
    assert '"composer.atSearchPlaceholder": "Type a keyword to search references"' in EN
    assert '"composer.atSearchPlaceholder"' in ZH


def test_at_rows_square_thumb_plus_name() -> None:
    block = _at_menu_block()
    assert "ca-at-menu__thumb" in block
    assert "ca-at-menu__row" in block
    assert "ca-menu__grow" in block
    # video play overlay OK
    assert "ca-at-menu__play" in block
    assert "Icons.play" in block


def test_canvas_select_two_capsules_path() -> None:
    """Canvas multi-select lands refs as capsules (thumb + truncated label); removable; no auto-send."""
    assert 'data-testid="composer-capsule"' in COMPOSER
    assert "ca-chip--capsule" in COMPOSER
    assert "ca-chip__thumb" in COMPOSER
    assert "ca-chip__name" in COMPOSER
    assert "truncateLabel" in COMPOSER
    # selection → refs (shown from selected) still drives chips — no auto send on select
    # #389 (0676aed): `shown = selected.filter(...)` became mergeRefIds(selected ids, hidden, extra) — still selection-driven
    assert "mergeRefIds(selected.map((s) => s.id), hidden, extra)" in COMPOSER
    assert "removeRef" in COMPOSER
    # send only via send() / Enter — select alone does not call sendToAgent
    send_fn = COMPOSER.split("const send = () => {")[1].split("\n  const filtered")[0]
    assert "sendToAgent" in send_fn or "generateDirect" in send_fn
    # capsules render from refs map, not inside send()
    assert "refs.map((r)" in COMPOSER or "refs.length > CAPSULE_SUMMARY_AT" in COMPOSER


def test_capsule_css_pill_with_thumb_label() -> None:
    assert ".ca-chip--capsule" in SHELL
    assert ".ca-at-menu" in SHELL
    assert ".ca-at-menu__title" in SHELL
    assert "#362" in SHELL
    assert "#362" in OVERLAYS


def test_summary_capsule_should_path_present() -> None:
    """SHOULD >10 → summary capsule — present but must not block tip if weak."""
    assert "CAPSULE_SUMMARY_AT" in COMPOSER
    assert 'data-testid="capsule-summary"' in COMPOSER
    assert "composer.selectedCount" in COMPOSER


def test_i18n_group_labels() -> None:
    assert '"composer.atGroupAssets": "素材"' in ZH and '"composer.atGroupModel": "模型"' in ZH
    assert '"composer.atGroupAssets": "Assets"' in EN and '"composer.atGroupModel": "Model"' in EN


def test_done_prose_360_untouched() -> None:
    """Must not touch #360 Done prose / suggestion chips."""
    assert "function DoneFeedback" in CHAT
    assert "isMediaDoneMessage" in CHAT
    assert "ca-chat__feedback" in CHAT
    assert "prose next-step" in GUIDE
    assert "下一步建议" in GUIDE


def test_refusal_361_untouched() -> None:
    """Must not touch #361 refusal markdown path."""
    assert "#361" in CHAT or "NEVER suggestion chips" in CHAT
    assert "Markdown" in CHAT
    assert "exactly three markdown unordered list bullets" in GUIDE or "trademarked" in GUIDE


def test_media_hero_untouched() -> None:
    """Must not touch #356/#358 media hero."""
    assert "ca-media-hero" in CHAT
    assert "mediaHero" in CHAT
    hero = OVERLAYS.split(".ca-media-hero {")[1].split("}")[0]
    assert "calc(var(--ca-process-col)" not in hero


def test_review_toggle_364_not_in_scope() -> None:
    """Do not ship #364 review toggle changes on this tip — Composer must not grow review-toggle chrome."""
    assert "reviewToggle" not in COMPOSER
    assert "ca-review-toggle" not in COMPOSER
    assert "post-thought-review" not in COMPOSER


def test_does_not_block_97() -> None:
    """Explicitly out of scope: do not gate/block #97 tip hub."""
    assert "block97" not in COMPOSER
    assert "block #97" not in COMPOSER.lower()
    assert "gate97" not in AGENT
