"""#495 sidebar — expand/collapse + recent list on existing HomeApp rail (no parallel component)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text()
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
BASE_CSS = (ROOT / "src/styles/base.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


def test_modifies_homeapp_rail_in_place() -> None:
    assert 'data-testid="account-rail"' in HOME_APP
    assert "export function HomeApp" in HOME_APP
    # no parallel sidebar component file
    home_dir = ROOT / "src/home"
    assert not (home_dir / "Sidebar.tsx").exists()
    assert not (home_dir / "AppSidebar.tsx").exists()


def test_collapse_persisted() -> None:
    assert "RAIL_COLLAPSE_KEY" in HOME_APP
    assert "comfyart.rail.collapsed" in HOME_APP
    assert "writeLocal(RAIL_COLLAPSE_KEY" in HOME_APP
    assert "readLocal(RAIL_COLLAPSE_KEY)" in HOME_APP
    assert 'data-testid="rail-collapse"' in HOME_APP
    assert 'data-testid="rail-expand"' in HOME_APP


def test_nav_order_and_labels() -> None:
    # order in source: new → home → projects → skills → (assets gated) → schedules → arti
    order = [
        m.start()
        for m in [
            re.search(r'testId="rail-new"', HOME_APP),
            re.search(r'testId="rail-home"', HOME_APP),
            re.search(r'testId="rail-projects"', HOME_APP),
            re.search(r'testId="rail-skills"', HOME_APP),
            re.search(r'testId="rail-schedules"', HOME_APP),
            re.search(r'testId="rail-arti"', HOME_APP),
        ]
    ]
    assert all(x is not None for x in order)
    assert order == sorted(order)
    assert 'label={t(\'home.projects\')}' in HOME_APP or 'label={t("home.projects")}' in HOME_APP
    assert "home.designSchedules" in HOME_APP
    assert ZH["home.designSchedules"] == "设计日程"
    assert EN["home.designSchedules"] == "Schedules"
    assert ZH["home.projects"] == "项目"
    assert EN["home.projects"] == "Projects"


def test_assets_hidden_until_497() -> None:
    # #539 PR-A: assertion updated (not removed) — the gate now flips ON because the Assets
    # page shell landed; the gate itself must still exist and the entry must route in place.
    assert "SHOW_ASSETS = true" in HOME_APP
    assert "SHOW_ASSETS ?" in HOME_APP or "SHOW_ASSETS &&" in HOME_APP
    assert "onClick={() => openView('assets')}" in HOME_APP
    assert "onClick={() => {}}" not in HOME_APP  # mutation: dead entry
    # order: skills → assets → schedules
    assert HOME_APP.index('testId="rail-skills"') < HOME_APP.index('testId="rail-assets"') < HOME_APP.index('testId="rail-schedules"')


def test_assets_page_shell_539() -> None:
    projects = (ROOT / "src/projects.ts").read_text()
    main = (ROOT / "src/main.tsx").read_text()
    assets = (ROOT / "src/home/Assets.tsx").read_text()
    panel = (ROOT / "src/ui/LibraryPanel.tsx").read_text()
    assert "'assets'" in projects.split("export type HomeView")[1].split("\n")[0]
    assert "viewParam === 'assets'" in main
    assert "if (view === 'assets') return <Assets />" in HOME_APP
    # reuses existing LibraryPanel + libraryAtom data; no parallel list/store
    assert "<LibraryPanel kitsOnly" in assets
    assert "loadLibrary" in assets
    assert "atom(" not in assets and "AssetGrid" not in assets
    for f in ("AssetsPanel.tsx", "AssetList.tsx", "AssetLibrary.tsx"):
        assert not (ROOT / "src/home" / f).exists() and not (ROOT / "src/ui" / f).exists()
    # kitsOnly hides 「文件」 tab only; canvas path keeps it
    assert "kitsOnly ? TABS.filter(([k]) => k !== 'files') : TABS" in panel
    assert "['files', t('libraryPanel.files')]" in panel
    # no demo data
    for demo in ("demo", "sample", "示例"):
        assert demo not in assets.lower()
    # #539 PR-B: assertion updated (not removed) — assets.emptyTitle dropped because the spec'd
    # empty state is one neutral hint line + 新建 (no title/icon); the remaining keys are checked.
    for k in ("assets.emptyHint", "assets.dropHint", "assets.importUrl", "assets.dropFormats"):
        assert ZH[k] and EN[k] and ZH[k] != EN[k]
    assert "assets.emptyTitle" not in assets


def test_assets_detail_539b() -> None:
    """#539 PR-B: right pane = existing KitEditor (embedded); default-select; empty state; scoped list styles."""
    assets = (ROOT / "src/home/Assets.tsx").read_text()
    kit = (ROOT / "src/ui/KitEditor.tsx").read_text()
    panel = (ROOT / "src/ui/LibraryPanel.tsx").read_text()
    css = (ROOT / "src/styles/home.css").read_text()
    # reuse, no duplicate editor/list
    assert "<KitEditor embedded" in assets
    for f in ("AssetDetail.tsx", "AssetsDetail.tsx", "KitDetail.tsx"):
        assert not (ROOT / "src/home" / f).exists() and not (ROOT / "src/ui" / f).exists()
    # default-select first kit of active tab; never auto-create
    assert "kitEditAtom.set(items[0]?.id ?? null)" in assets
    assert "createLibraryItem(kind, fail)" in assets and "useEffect(() => { createLibraryItem" not in assets
    # one shared create action for list 新建 + empty 新建
    assert "const create = (kind: LibraryKind) => createLibraryItem(kind, onError)" in panel
    # #539 PR-C: assertion updated (not removed) — embedded CTA is now wired (test_assets_c_539);
    # canvas path keeps newProject + Escape close; URL import may HEAD the link only to confirm its type
    emb = kit.split("{embedded ? (\n        /* #539 PR-C: full-width bar")[1].split(") : brand && (")[0]
    assert "onClick={createProject}" in emb
    assert "newProject({ kit: item.id })" in kit
    assert "if (!embedded && e.key === 'Escape') close()" in kit
    assert kit.count("fetch(") == 1 and "{ method: 'HEAD' }" in kit
    # list column measurements, scoped to the page (canvas .ca-lib untouched)
    rules = css.split("/* #539 我的素材 page")[1]
    assert "width: 380px" in rules and "border-right: 1px solid var(--ca-border)" in rules
    assert "font: 600 18px/26px" in rules
    assert ".ca-assets-page .ca-lib__new { border-style: dashed" in rules
    assert ".ca-kit[data-embedded] .ca-kit__page { max-width: 800px" in rules
    for line in rules.splitlines():
        if line.startswith(".ca-lib") or line.startswith(".ca-kit "):
            raise AssertionError(f"unscoped rule: {line}")
    for f in (assets, rules):
        assert "lovart" not in f.lower()
    # product ruling: Assets create buttons = shared assets.newItem 新建/New; canvas keeps libraryPanel.newItem
    assert "{t('assets.newItem')}" in assets
    assert "kitsOnly ? t('assets.newItem') : t('libraryPanel.newItem', KIND_LABELS[tab])" in panel
    assert ZH["assets.newItem"] == "新建" and EN["assets.newItem"] == "New"
    # persistent selected card = one scoped rule on two theme tokens
    assert ".ca-assets-page .ca-lib__card[data-on] { background: var(--ca-assets-card-on-bg); border-color: var(--ca-assets-card-on-border); }" in rules


def test_hidden_items_absent() -> None:
    for forbidden in ("个人主页", "设计委托", "Personal homepage", "Design commission"):
        assert forbidden not in HOME_APP
    # nav label is 设计日程, not 设计委托
    assert ZH["home.designSchedules"] != "设计委托"


def test_wavespeed_and_gear_kept() -> None:
    # #498: WaveSpeed history moved into SettingsMenu; gear/settings rail entry stays
    assert 'testId="rail-ws-history"' not in HOME_APP
    assert "SettingsMenu" in HOME_APP
    assert 'testId="rail-settings"' in HOME_APP or 'data-testid="rail-settings"' in HOME_APP
    menu = (ROOT / "src/ui/SettingsMenu.tsx").read_text()
    assert "settings-ws-history" in menu and "WAVESPEED_HISTORY_URL" in menu


def test_recent_max_8_titles_menu() -> None:
    assert "RECENT_LIMIT = 8" in HOME_APP
    assert "slice(0, RECENT_LIMIT)" in HOME_APP
    assert 'data-testid="rail-recent"' in HOME_APP
    assert 'data-testid="rail-recent-menu"' in HOME_APP
    for tid in ("rail-recent-pin", "rail-recent-rename", "rail-recent-duplicate", "rail-recent-delete"):
        assert f'data-testid="{tid}"' in HOME_APP
    assert "setPinned" in HOME_APP and "renameProject" in HOME_APP
    assert "duplicateProject" in HOME_APP and "confirmDelete" in HOME_APP
    assert "ca-menu__item--danger" in HOME_APP
    # collapsed: recent not shown
    assert "expanded && recent" in HOME_APP


def test_expanded_css_and_theme_var() -> None:
    assert ".ca-rail[data-expanded]" in HOME_CSS
    assert "width: var(--ca-rail-w-expanded)" in HOME_CSS  # #546: 160 → Lovart 240
    assert "--ca-rail-w-expanded: 240px" in BASE_CSS
    assert "var(--ca-rail-bg)" in HOME_CSS
    assert "--ca-rail-bg: #f5f5f5" in BASE_CSS  # #552 design measured (was #f2f2f2)
    assert "--ca-rail-bg: #1c1c1c" in BASE_CSS
    assert ".ca-rail__recent-name" in HOME_CSS
    assert "text-overflow: ellipsis" in HOME_CSS


def test_i18n_collapse_keys() -> None:
    assert ZH["home.collapseSidebar"]
    assert EN["home.collapseSidebar"]
    assert ZH["home.expandSidebar"]
    assert EN["home.expandSidebar"]
    assert ZH["home.assets"] == "我的素材"
    assert EN["home.assets"] == "Assets"


def test_assets_c_539() -> None:
    """#539 PR-C: 20MB check, URL import, wired CTA, design P2s — all in the existing files."""
    kit = (ROOT / "src/ui/KitEditor.tsx").read_text()
    css = (ROOT / "src/styles/home.css").read_text()
    rules = css.split("/* #539 我的素材 page")[1]
    for f in ("AssetDetail.tsx", "UrlImport.tsx", "AssetUpload.tsx"):
        assert not (ROOT / "src/home" / f).exists() and not (ROOT / "src/ui" / f).exists()
    # (a) 20MB limit before upload, i18n error
    assert "export const MAX_UPLOAD = 20 * 1024 * 1024" in kit
    assert "f.size > MAX_UPLOAD" in kit and "t('assets.tooLarge'" in kit
    assert "20MB" in ZH["assets.tooLarge"] and "20MB" in EN["assets.tooLarge"]
    # (b) URL import: http/https only, i18n error
    assert "['http:', 'https:'].includes(parsed.protocol)" in kit and "t('assets.urlInvalid')" in kit
    assert ZH["assets.urlInvalid"] and EN["assets.urlInvalid"]
    # product ruling: PNG/JPG/PDF only, ext OR content-type, HEAD failure = unconfirmed
    assert "const OK_EXT = /\\.(png|jpe?g|pdf)$/i" in kit
    assert "const OK_TYPES = ['image/png', 'image/jpeg', 'application/pdf']" in kit
    assert "catch {\n    return false" in kit and "t('assets.urlFormat')" in kit and "t('assets.badFormat'" in kit
    assert 'aria-disabled="true"' not in kit
    # (c) CTA reuses #555 newProject with the selected kit
    # #539 PR-C scope change: every kit type rides ?kit=; App attaches non-brand kits like 「添加到对话」
    assert "const createProject = () => { flush(); newProject({ kit: item.id }) }" in kit
    app = (ROOT / "src/App.tsx").read_text()
    assert "brandKit: (other ? null : kit) ?? defaultKitId()" in app
    assert "kitsAtom.set([...kitsAtom.get(), other])" in app
    # P2 1: arrow icon + no dashed border (embedded only)
    assert "embedded ? Icons.uploadArrow : Icons.upload" in kit
    assert ".ca-kit[data-embedded] .ca-kit__drop { border: none; }" in rules
    # P2 2: single-line guide ~30
    assert "rows={embedded ? 1 : undefined}" in kit and "height: 30px" in rules
    # P2 3: 「…」 hover only, scoped to the page
    # P1 2: hover-only scoped to list cards; detail-title 「…」 always visible
    assert ".ca-assets-page .ca-lib__card .ca-lib__more { opacity: 0; }" in rules
    assert ".ca-assets-page .ca-lib__more { opacity: 0; }" not in rules
    assert ".ca-assets-page .ca-lib__card .ca-lib__more[data-open]" in rules
    # P1 1: title = card display name via shared helper, body colour (value, not placeholder)
    lib = (ROOT / "src/library.ts").read_text()
    assert "export const kitDisplayName = (item: { name: string; kind: LibraryKind }) => item.name || t('kitEditor.untitled', KIND_LABELS[item.kind])" in lib
    assert "const name = kitDisplayName(item)" in (ROOT / "src/ui/LibraryPanel.tsx").read_text()
    assert "value={titleDraft ?? kitDisplayName(item)}" in kit
    # P2: upload errors inline only (no toast), stale errors cleared, 「添加」 reuses 「取消」 button class
    assert "if (msg) onError(msg)" not in kit and "setUploadErr(msg); setUrlErr('')" in kit
    assert kit.count("setUploadErr('')") >= 5
    assert 'className="ca-kit__urlsave" data-testid="assets-url-save" disabled={!url.trim() || checking}' in kit
    base = (ROOT / "src/styles/base.css").read_text()
    assert "--ca-btn-primary-bg: #191919;" in base and "--ca-btn-primary-fg: #ffffff;" in base
    assert "--ca-btn-primary-bg: #e8e8e8;" in base and "--ca-btn-primary-fg: #161616;" in base
    assert "padding: 0 12px; border: none; border-radius: 8px; background: var(--ca-btn-primary-bg); color: var(--ca-btn-primary-fg); font: 13px/20px var(--ca-font)" in rules
    assert ".ca-kit[data-embedded] .ca-kit__urlsave:disabled { opacity: .4;" in rules
    assert 'className="ca-assets-page__new" data-testid="assets-url-cancel"' in kit
    assert "placeholder={t('kitEditor.untitled', '')}" not in kit
    assert ".ca-assets-page .ca-lib__card:hover .ca-lib__more" in rules
    # P2 5: CTA at the right edge of an 800 centred container
    assert '<div className="ca-kit__footin">' in kit
    assert ".ca-kit[data-embedded] .ca-kit__footin { display: flex; justify-content: flex-end; width: 100%; max-width: 800px; }" in rules
    # P2 4: no Acme seed names in screenshot tests
    assert "Acme" not in (ROOT / "tests/test_e2e_sidebar_495.py").read_text()
