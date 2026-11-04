"""#705 P0 — skill read with an empty id: explicit non-retryable error (real src/skills.ts via a node harness),
and the agent loop guards (non-retryable stop, P1 same-tool >3 stop). No LLM, no WaveSpeed."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from ComfyArt.bot.run_budget import SUB_REASONS, ProgressTracker, StepObservation, StopReason

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"skillid705-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/skillid705/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@needs_node
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_skill_empty_id_is_explicit_and_non_retryable(lang) -> None:
    r = report()
    assert r["marker"] == "[non-retryable]"
    for case in ("empty", "emptyId", "blankName"):
        err = r[lang][case]["error"]
        assert err.startswith("[non-retryable] skill read needs a non-empty id or name"), err
        assert "unknown skill undefined" not in err


@needs_node
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_skill_linkedin_banner_registered_and_every_builtin_reads_by_id_and_name(lang) -> None:
    r = report()[lang]
    assert r["inList"] is True
    assert r["badReads"] == {}
    # (b) the registry error lists every skill, linkedin-banner included (it sits near the end, ~char 1800)
    assert "(linkedin-banner)" in r["unknownName"]["error"]
    assert "[non-retryable]" not in r["unknownName"]["error"]  # a wrong name is still retryable (call list)


def test_same_sub_reasons_are_registered() -> None:
    assert {"same_tool", "non_retryable"} <= SUB_REASONS[StopReason.STUCK]


def _obs(tool, i, result=None):
    return [StepObservation(tool=tool, args_key=f"{tool}{i}", result=result if result is not None else f"text {i}")]


def test_tracker_same_tool_more_than_3_in_a_row() -> None:
    t = ProgressTracker()
    assert [t.observe(i, _obs("skill", i)) for i in range(1, 5)] == [None, None, None, "same_tool"]


def test_tracker_same_tool_reset_by_artifacts_other_tool_or_parallel_batch() -> None:
    t = ProgressTracker()
    for i in range(1, 9):  # each step lands a new shape: real progress, never same_tool
        assert t.observe(i, _obs("add_text", i, json.dumps({"id": f"shape:{i}"}))) is None
    t = ProgressTracker()
    out = [t.observe(i, _obs(n, i)) for i, n in enumerate(["skill"] * 3 + ["add_text"] + ["skill"] * 3, 1)]
    assert out == [None] * 7
    t = ProgressTracker()  # one step with 4 parallel generate_image calls counts once
    batch = [StepObservation("generate_image", f"g{k}", json.dumps({"id": f"job:{k}"})) for k in range(4)]
    assert t.observe(1, batch) is None


def test_tracker_budget_cap_tool_calls_and_generate_image() -> None:
    from ComfyArt.bot.run_budget import DEFAULT_PLANNED_IMAGES
    t = ProgressTracker()
    assert t.gen_cap() == DEFAULT_PLANNED_IMAGES + 2 == 6
    # every step lands a NEW image (so no_progress/same_tool never fire) but never finishes
    hits = [t.over_budget([StepObservation("generate_image", f"g{i}", json.dumps({"id": f"shape:{i}"}))]) for i in range(1, 8)]
    assert hits == [False] * 6 + [True]
    t = ProgressTracker(planned_images=1)
    assert [t.over_budget(_obs("generate_image", i)) for i in range(1, 5)] == [False, False, False, True]
    t = ProgressTracker()  # local tools never hit the paid cap, only the 300 backstop
    assert not any(t.over_budget(_obs("add_text", i)) for i in range(1, 301))
    assert t.over_budget(_obs("add_text", 301)) is True
    t = ProgressTracker(planned_images=100)  # 30 paid (non-generate_image here) calls max
    assert [t.over_budget(_obs("edit_image", i)) for i in range(1, 32)] == [False] * 30 + [True]


def test_tracker_readonly_skill_reads_count_toward_30_cap() -> None:
    t = ProgressTracker(planned_images=100)  # #705: a read-only loop cannot bypass the 30 cap
    assert [t.over_budget(_obs("skill", i)) for i in range(1, 32)] == [False] * 30 + [True]
    t = ProgressTracker()
    assert not any(t.over_budget(_obs("wait_generation", i)) for i in range(1, 60))  # polls are not capped


def test_tool_error_prefix_is_a_failure() -> None:
    from ComfyArt.bot.agent_loop import _result_failed
    assert _result_failed({"status": "success", "text": "[tool error] ValueError: [non-retryable] x"})
    assert _result_failed({"status": "error", "text": "x"}) and _result_failed({"text": "[error] x"})
    assert not _result_failed({"status": "success", "text": '{"id": "shape:1"}'})


def test_autofill_skill_read_uses_current_skill_only() -> None:
    from types import SimpleNamespace
    from ComfyArt.api.bot_send import compose_provider_text
    from ComfyArt.bot.agent_loop import autofill_skill_read, current_skill_from_messages
    msgs = [{"role": "user", "content": compose_provider_text("go", skill_name="LinkedIn Banner")}]
    assert current_skill_from_messages(msgs) == "LinkedIn Banner"
    assert current_skill_from_messages([{"role": "user", "content": "go"}]) == ""
    ctx = SimpleNamespace(current_skill="LinkedIn Banner", skill_autofills=0, run_id="r", store=None)
    assert autofill_skill_read(ctx, "skill", {"action": "read"}) == {"action": "read", "name": "LinkedIn Banner"}
    assert autofill_skill_read(ctx, "skill", {"action": "read", "id": " "})["name"] == "LinkedIn Banner"
    assert autofill_skill_read(ctx, "skill", {"action": "read", "id": "x"}) == {"action": "read", "id": "x"}
    assert autofill_skill_read(ctx, "skill", {"action": "list"}) == {"action": "list"}
    assert ctx.skill_autofills == 2
    none = SimpleNamespace(current_skill="", skill_autofills=0, run_id="r", store=None)
    assert autofill_skill_read(none, "skill", {"action": "read"}) == {"action": "read"}


def test_wait_generation_own_limit_timeout() -> None:
    from ComfyArt.bot.run_budget import SUB_REASONS, StopReason
    assert "timeout" in SUB_REASONS[StopReason.STUCK]
    w = lambda ids: [StepObservation("wait_generation", "wait_generation\x00" + json.dumps({"ids": ids}), "pending")]
    t = ProgressTracker()  # 120 polls ok, 121st trips; polls never touch the 30 cap
    assert [t.wait_timeout(w(["job1"]), now=1000.0 + i) for i in range(1, 122)] == [False] * 120 + [True]
    assert not t.over_budget(w(["job1"]))
    t = ProgressTracker()  # 10 minutes from the first poll of that task
    assert t.wait_timeout(w(["a"]), now=0.0) is False
    assert t.wait_timeout(w(["a"]), now=600.0) is False
    assert t.wait_timeout(w(["b"]), now=601.0) is False      # a new task has its own clock
    assert t.wait_timeout(w(["a"]), now=600.5) is True
    assert ProgressTracker.restore(t.snapshot()).wait_polls == {"a": 3, "b": 1}
