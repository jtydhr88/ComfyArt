"""#627: agent step-rail labels + icons align lovart CN live (product lock 6571777033)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
ICONS = (ROOT / "src/ui/icons.tsx").read_text(encoding="utf-8")


def test_thought_done_is_思考完成_not_bare_思考():
    assert ZH["chatMessage.thought"] == "思考完成"
    assert EN["chatMessage.thought"] == "Thought"
    assert ZH["chatMessage.thought"] != "思考"
    blob = json.dumps(ZH, ensure_ascii=False)
    # bare 思考 as a done label must not exist as a chatMessage value
    assert '"chatMessage.thought": "思考"' not in blob


def test_ref_analysis_labels():
    assert ZH["chatMessage.referenceAnalysisDone"] == "参考素材分析结束"
    assert EN["chatMessage.referenceAnalysisDone"] == "Reference analysis done"
    assert "ref_analysis" in CHAT
    assert "sawMediaGen" in CHAT
    assert "kindResolved = 'ref_analysis'" in CHAT
    assert "ref_analysis: Icons.refAnalysis" in CHAT
    assert "refAnalysis:" in ICONS


def test_image_row_is_runtime_model_slot_not_generated_images():
    # Forbid rail labels only — other product copy may still say "Generated images".
    for key, val in {**EN, **ZH}.items():
        if not key.startswith("chatMessage."):
            continue
        assert "Generated images" not in str(val), key
        assert "已生成图片" not in str(val), key
        assert "图片模型" not in str(val), key
    assert "chatMessage.imagesGenerated" not in EN
    assert "chatMessage.imagesGenerated" not in ZH
    assert "if (opts?.model) return opts.model" in CHAT
    assert "processModelName" in CHAT


def test_skill_and_web_rows():
    assert ZH["chatMessage.skillReady"] == "技能加载完成"
    assert "skill: Icons.files" in CHAT  # stacked docs
    assert ZH["chatMessage.webPages"] == "{0} 个网页"
    assert "search_pages: Icons.globe" in CHAT


def test_icons_not_bulb_and_no_lovart_in_src():
    assert "#627 think done" in ICONS
    assert "refAnalysis:" in ICONS
    assert "sparkleImage:" in ICONS
    src = ROOT / "src"
    for f in src.rglob("*"):
        if f.suffix not in {".ts", ".tsx", ".css", ".json"}:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        assert "Lovart" not in text and "lovart" not in text, f"Lovart string in {f}"


def test_no_second_thought_after_media_path():
    # post-media thinking remapped; thought label must not be forced twice after gen
    assert "sawMediaGen" in CHAT and "ref_analysis" in CHAT
    assert "referenceAnalysisDone" in CHAT
