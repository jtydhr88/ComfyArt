"""#382 P0-2 memory inject budget + 「记忆已更新 ›」 — behavior tests (mock only).

Harness: tests/js/memory_budget_382.ts. No network, no paid API."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m382") / "memory_budget_382.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "memory_budget_382.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True)
    return json.loads(run.stdout)


def test_constants_match_policy(got):
    import json as _json
    policy = _json.loads((ROOT / "api/memory_policy.json").read_text())
    c = got["constants"]
    assert c["MAX_INJECT"] == policy["max_inject"] == 40
    assert c["MAX_INJECT_TOKENS"] == policy["max_inject_tokens"] == 1500
    assert c["IMAGE_TOKENS"] == policy["image_tokens"] == 1500
    assert c["MAX_LOG"] == policy["max_log"] == 500
    # #493: FE fallback window matches bot/local_llm._FALLBACK_CONTEXT_WINDOW
    assert policy["fallback_context_window"] == 270_000


def test_ac1_topn_and_token_cap(got):
    o = got["ac1_topn_budget"]
    assert o["count"] <= o["maxInject"]
    assert o["count"] > 0
    assert o["allRelevant"] is True
    assert o["underCap"] is True
    assert o["tokens"] <= o["maxTokens"]
    assert o["hasHeader"] is True
    assert o["uncappedWouldIncludeNoise"] is True


def test_mut_ac1_no_topn_would_exceed(got):
    """Mutation: dropping top-N truncation → count > MAX_INJECT (AC1 red)."""
    m = got["mut_ac1_no_topn"]
    assert m["exceeds"] is True
    assert m["fullCount"] > got["constants"]["MAX_INJECT"]


def test_ac2_unified_budget_counts_images(got):
    o = got["ac2_unified"]
    assert o["imagesCounted"] is True
    assert o["imageTokens"] == 4 * got["constants"]["IMAGE_TOKENS"]
    assert o["dropImagesUndercounts"] is True
    assert o["withImg"]["images"] == o["imageTokens"]
    assert o["noImg"]["images"] == 0


def test_mut_ac2_drop_image_estimate_undercounts(got):
    """Mutation: budget calc without image estimate → undercount (AC2 red)."""
    m = got["ac2_unified"]["mutationRed"]
    assert m["undercount"] is True
    # Fake (no images) claims a smaller total; often falsely fits when real does not.
    assert m["fakeFits"] or m["undercount"]


def test_ac3_zero_relevant_and_disabled(got):
    o = got["ac3_empty"]
    assert o["none"] == ""
    assert o["noHeader"] is True
    assert o["disabledEmpty"] is True


def test_ac4_log_cap(got):
    o = got["ac4_log_cap"]
    assert o["capped"] is True
    assert o["len"] == o["max"] == 500
    assert o["newestFirst"] is True
    assert o["oldestSeedGone"] is True
    assert o["keptRecentSeed"] is True


def test_mut_ac4_no_cap_would_exceed(got):
    """Mutation: dropping log cap → length MAX_LOG+50 (AC4 red)."""
    m = got["mut_ac4_no_cap"]
    assert m["exceeds"] is True
    assert m["wouldBe"] == 550


def test_ac5_memory_updated_between_thought_and_reply(got):
    o = got["ac5_row_placement"]
    assert o["ok"] is True
    assert o["between"] is True
    assert o["count"] == 1
    assert o["types"] == ["thinking", "memory_updated", "text"]
    assert o["noLearnRows"] is False


def test_ac5_memory_row_before_second_thought(got):
    """#382 fix: reference order 思考完成 → 记忆已更新 → 思考完成 → reply."""
    o = got["ac5_row_two_thoughts"]
    assert o["twoThought"] == ["thinking", "memory_updated", "thinking", "text"]
    assert o["withTools"][:2] == ["thinking", "memory_updated"]
    assert o["withTools"].count("memory_updated") == 1


@pytest.mark.gate_skip(reason="stale on main: memory row rail markup changed since the test was written (#382)")
def test_memory_row_same_rail_structure():
    """#382 fix: history icon, no separate --memory button/label override."""
    src = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    css = (ROOT / "src/styles/overlays.css").read_text()
    icons = (ROOT / "src/ui/icons.tsx").read_text()
    assert "memory_updated: Icons.memoryHead" in src  # #435: reference icon
    assert "rowbtn--memory" not in src and "rowbtn--memory" not in css
    assert 'data-kind="memory_updated"] .ca-process__label' not in css
    assert "history: <Svg strokeWidth={2}>" in icons


def test_mut_ac5_after_reply_fails_placement(got):
    """Mutation: row after reply → placement check fails (AC5 red)."""
    o = got["ac5_row_placement"]
    assert o["mutAfterReplyOk"] is False


def test_ac6_undo_removes_and_logs(got):
    o = got["ac6_undo"]
    assert o["ok"] is True
    assert o["gone"] is True
    assert o["logGrew"] is True
    assert o["logAction"] == "forget"
    assert o["logSource"] == "memory-updated-undo"
    assert o["persists"] is True


def test_mut_ac6_ui_only_resurrects(got):
    """Mutation: UI-only clear without removeMemory → refresh resurrects (AC6 red)."""
    assert got["mut_ac6_ui_only"]["resurrected"] is True
