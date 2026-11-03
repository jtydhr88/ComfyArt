"""#583 — Skills page header 1:1 gold lock (title/tabs/chip/create/search + pinned chrome + adaptive grid)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/home/Skills.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()


def _rule(sel: str, css: str = CSS) -> str:
    return css.split(sel + " {", 1)[1].split("}", 1)[0]


def test_chrome_scroll_structure() -> None:
    assert 'data-testid="skills-chrome"' in SKILLS
    assert 'data-testid="skills-scroll"' in SKILLS
    assert 'data-testid="skills-search"' in SKILLS
    assert 'data-testid="skills-tabs"' in SKILLS
    # search lives in tab row, not title row
    head = SKILLS.split("ca-skills__head", 1)[1].split("ca-skills__tabs", 1)[0]
    assert "skills-search" not in head and "Icons.search" not in head
    tabs = SKILLS.split("ca-skills__tabs", 1)[1].split("ca-skills__chips", 1)[0]
    assert "skills-search" in tabs and "Icons.search" in tabs
    # no filter icon until a real filter exists
    assert "Icons.filter" not in SKILLS


def test_create_split_80x36_radius_8() -> None:
    create = _rule(".ca-skills__create")
    assert "height: 36px" in create and "border-radius: 8px" in create
    assert "400 14px/22px" in create
    wrap = _rule(".ca-skills__createwrap", OVERLAYS)
    assert "width: 80px" in wrap and "height: 36px" in wrap
    inner = _rule(".ca-skills__createwrap .ca-skills__create", OVERLAYS)
    assert "border-radius: 8px 0 0 8px" in inner
    # #676: 「创建」 must never wrap to two lines
    assert "white-space: nowrap" in inner and "min-width: 52px" in inner and "min-width: 0" not in inner
    more = _rule(".ca-skills__createmore", OVERLAYS)
    assert "width: 28px" in more and "border-radius: 0 8px 8px 0" in more
    # create label only — plus moved off the primary face (gold split is text + chevron)
    face = SKILLS.split('data-testid="skills-create"', 1)[1].split("</button>", 1)[0]
    assert "Icons.plus" not in face and "home.skillsCreate" in face


def test_title_tabs_search_tokens() -> None:
    page = _rule(".ca-skillspage")
    assert "height: 100%" in page and "overflow: hidden" in page
    chrome = _rule(".ca-skills__chrome")
    assert "padding: 24px 60px 12px" in chrome
    title = _rule(".ca-skills__head h1")
    assert "600 18px/26px" in title and "var(--ca-text)" in title
    head = _rule(".ca-skills__head")
    assert "margin: 0 0 12px" in head and "padding: 0 0 0 4px" in head
    tabs = _rule(".ca-skills__tabs")
    assert "height: 36px" in tabs and "padding: 8px 4px 0" in tabs
    assert "justify-content: space-between" in tabs
    tab = _rule(".ca-skills__tab")
    assert "var(--ca-skilltabs-font)" in tab and "padding: 0 0 8px" in tab
    on = _rule(".ca-skills__tab[data-on]")
    assert "var(--ca-skilltabs-on-weight)" in on
    under = _rule(".ca-skills__tab[data-on]::after")
    assert "left: 0; right: 0" in under and "var(--ca-skilltabs-indicator-h)" in under
    assert "--ca-skilltabs-on-weight: 500" in CSS
    assert "--ca-skilltabs-gap: 20px" in CSS and "--ca-skilltabs-indicator-h: 1px" in CSS
    icon = _rule(".ca-skills__iconbtn")
    assert "width: 28px" in icon and "height: 28px" in icon and "border: none" in icon
    assert "width: 16px" in _rule(".ca-skills__iconbtn .ca-icon")


def test_chips_and_vertical_rhythm() -> None:
    chips = _rule(".ca-skills__chips")
    assert "margin: 12px 0 0" in chips and "padding: 8px 0 0" in chips  # tab→chip ~20
    assert "gap: var(--ca-chip-gap)" in chips
    chip = _rule(".ca-skills__chip")
    assert "var(--ca-chip-h)" in chip and "var(--ca-chip-py)" in chip
    assert "--ca-chip-h: 30px" in CSS and "--ca-chip-on-bg: rgba(0, 0, 0, .08)" in CSS
    scroll = _rule(".ca-skills__scroll")
    assert "padding: 8px 60px 96px" in scroll and "overflow-y: auto" in scroll  # chip→card ~28


def test_adaptive_grid_3col_at_920() -> None:
    wall = _rule(".ca-swall")
    assert "minmax(min(100%, 296px), 1fr)" in wall
    assert "gap: 24px 16px" in wall
    # 920 content: 3×296 + 2×16 = 920
    assert 3 * 296 + 2 * 16 == 920


def test_no_competitor_brand_in_skills_header_src() -> None:
    blob = SKILLS + CSS + OVERLAYS
    assert "Lovart" not in blob and "lovart" not in blob
