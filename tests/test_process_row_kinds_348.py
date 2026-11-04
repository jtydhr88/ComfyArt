"""#348 process timeline row-kind full spread (MUST): kinds · Lucide · i18n · skill live · no Thought rebuild."""
from __future__ import annotations
import pytest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
ICONS = (ROOT / "src/ui/icons.tsx").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()

MUST_KINDS = [
    "outputting",
    "skill_file_read",
    "search_pages",
    "code",
    "code_generated",
    "code_updated",
    "design_validated",
    "preview_artifact",
]


def test_process_kind_union_includes_must() -> None:
    for k in MUST_KINDS:
        assert f"'{k}'" in CHAT or f'"{k}"' in CHAT
    # retained tip kinds
    for k in ("thought", "skill", "search", "image", "video"):
        assert f"'{k}'" in CHAT


@pytest.mark.gate_skip(reason="stale on main: process icons moved to Lucide components (#348, #608)")
def test_process_icons_lucide_new() -> None:
    assert "fileSearch:" in ICONS
    assert "squareCode:" in ICONS
    assert "fileCode:" in ICONS
    assert "filePenLine:" in ICONS
    assert "listChecks:" in ICONS
    assert "sparkles:" in ICONS
    assert "Icons.fileSearch" in CHAT
    assert "Icons.squareCode" in CHAT
    assert "Icons.fileCode" in CHAT
    assert "Icons.filePenLine" in CHAT
    assert "Icons.listChecks" in CHAT
    assert "Icons.sparkles" in CHAT
    # FileSearch has magnifier circle (Lucide)
    fs = ICONS.split("fileSearch:")[1].split(",\n")[0]
    assert "circle" in fs.lower() or "r=" in fs
    sq = ICONS.split("squareCode:")[1].split(",\n")[0]
    assert "rect" in sq.lower() or 'rx="2"' in sq


def test_skill_file_read_mapping() -> None:
    assert "skillActionIsFileRead" in CHAT
    assert "skill_file_read" in CHAT
    assert "action === 'read'" in CHAT


def test_skill_live_status_shimmer_parity() -> None:
    # live title shimmer + status card outside rail (v3.4) — shared for all live rows incl. skill
    assert "ca-process__label--active" in CHAT
    assert "ca-process__status" in CHAT
    proc = CHAT.split("function ProcessTimeline")[1].split("\nfunction ")[0]
    assert "ca-spin" not in proc
    assert "Icons.check" not in proc


def test_image_video_model_suffix_optional() -> None:
    assert "processModelName" in CHAT
    assert "opts?.model" in CHAT  # #437: model name is the row label


def test_writing_code_family_mapping() -> None:
    assert "CODE_GENERATED_TOOLS" in CHAT
    assert "CODE_UPDATED_TOOLS" in CHAT
    assert "DESIGN_VALIDATED_TOOLS" in CHAT
    assert "PREVIEW_ARTIFACT_TOOLS" in CHAT
    assert "CODE_SUB_KINDS" in CHAT
    # header synthesized before first sub-kind
    assert "p${i}-code" in CHAT or "p${i}-code" in CHAT.replace("`", "")
    assert "kind: 'code'" in CHAT


def test_outputting_wait_row() -> None:
    assert "outputting" in CHAT
    assert "out-end" in CHAT
    assert "Icons.think" in CHAT  # same Brain glyph


def test_search_pages_count() -> None:
    assert "searchResultCount" in CHAT
    assert "search_pages" in CHAT
    assert "webPages" in CHAT


def test_no_thought_collapse_rebuild() -> None:
    ab = CHAT.split("export function AssistantBlocks")[1].split("\nexport function ")[0]
    assert "onlyThought" in ab
    assert "<Thought" in ab
    assert "function Thought" in CHAT


def test_css_v34_lock_intact() -> None:
    assert "--ca-process-step: 30px" in OVERLAYS
    spine = OVERLAYS.split(".ca-process__spine")[1].split("}")[0]
    assert "1px" in spine and "dashed" not in spine
    assert "ca-shine" in OVERLAYS.split(".ca-process__label--active")[1].split("}")[0]


def test_locale_must_keys_en_zh() -> None:
    for blob in (EN, ZH):
        assert "chatMessage.outputting" in blob
        assert "chatMessage.webPages" in blob
        assert "chatMessage.skillFileRead" in blob
        assert "chatMessage.skillFileReadLive" in blob
        assert "chatMessage.writingCode" in blob
        assert "chatMessage.writingCodeLive" in blob
        assert "chatMessage.codeGenerated" in blob
        assert "chatMessage.codeUpdated" in blob
        assert "chatMessage.designValidated" in blob
        assert "chatMessage.previewArtifact" in blob
        assert "chatMessage.usingModel" in blob
    assert "Outputting…" in EN
    assert "输出中…" in ZH
    assert "Reading skill file…" in EN
    assert "正在读取技能文件…" in ZH
    assert "{0} web pages" in EN
    assert "{0} 个网页" in ZH
