"""#712: no silent failures. The task id is saved at submit, a lost poll resumes with it, and a run that may be billed
with no image lands in the `failures` list with its cost and generation_succeeded=false. Mock WaveSpeed only, $0."""
from __future__ import annotations

import pytest

from ComfyArt.api import gen_ledger, wavespeed
from test_wavespeed import ws  # noqa: F401  (mocked WaveSpeed API)

MODEL = "wavespeed-ai/minimax-h3/text-to-video"
BODY = {"feature": "text_to_video", "model": MODEL, "prompt": "x", "duration": 5, "confirmed": True}


def _info(hist: dict, task: str) -> dict:
    return hist[f"ws:{task}"]["status"]["messages"][0][1]


async def test_id_saved_before_polling(ws):  # noqa: F811
    ws["status"] = "processing"
    task = await wavespeed.submit(dict(BODY))
    row = gen_ledger.run(task)
    assert row["status"] == "submitted" and row["model"] == MODEL and ws["polls"] == 0


async def test_completed_without_output_is_failed_with_cost(ws):  # noqa: F811
    ws["no_outputs"] = True
    ws["prices"][MODEL] = 0.32
    task = await wavespeed.submit(dict(BODY))
    hist = await wavespeed.poll(task)
    info = _info(hist, task)
    assert info["ws_kind"] == "noOutput" and info["ws_charged"] == pytest.approx(0.32)
    assert info["ws_task_id"] == task  # #712: the UI shows it
    assert hist[f"ws:{task}"]["generation_succeeded"] is False
    fail = [f for f in gen_ledger.failures() if f["task_id"] == task]
    assert len(fail) == 1 and fail[0]["cost_usd"] == pytest.approx(0.32) and fail[0]["generation_succeeded"] is False


async def test_no_task_id_is_failed_with_cost(ws):  # noqa: F811
    ws["no_id"] = True
    ws["prices"][MODEL] = 0.32
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(dict(BODY))
    assert e.value.kind == "noTaskId" and e.value.charged == pytest.approx(0.32)
    fail = gen_ledger.failures()[-1]
    assert fail["task_id"] is None and fail["kind"] == "noTaskId" and fail["cost_usd"] == pytest.approx(0.32)


async def test_poll_timeout_recovered_with_saved_id(ws, monkeypatch):  # noqa: F811
    task = await wavespeed.submit(dict(BODY))  # mock finishes at once
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    hist = await wavespeed.poll(task)
    assert hist[f"ws:{task}"]["generation_succeeded"] is True
    assert len(ws["submits"]) == 1 and gen_ledger.run(task)["status"] == "completed"
    assert not [f for f in gen_ledger.failures() if f["task_id"] == task]


async def test_poll_resumes_after_restart_from_ledger(ws):  # noqa: F811
    task = await wavespeed.submit(dict(BODY))
    wavespeed._jobs.pop(task)  # server restarted; only the saved id is left
    hist = await wavespeed.poll(task)
    assert hist[f"ws:{task}"]["generation_succeeded"] is True and len(ws["submits"]) == 1


async def test_run_raw_no_output_recorded(ws):  # noqa: F811
    ws["no_outputs"] = True
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.run_raw({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    assert e.value.kind == "noOutput"
    assert gen_ledger.failures()[-1]["kind"] == "noOutput"


def test_ui_shows_reason_and_amount():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "src"
    ts = (root / "wsErrors.ts").read_text()
    assert "'noOutput', 'noTaskId'" in ts
    import json
    for lang in ("en", "zh"):
        loc = json.loads((root / "locales" / f"{lang}.json").read_text())
        for k in ("noOutput", "noTaskId"):
            assert "{0}" in loc[f"wsErr.{k}"] and "${0}" not in loc[f"wsErr.{k}"] and f"wsErr.{k}NoAmount" in loc


def test_unregistered_model_raises():
    from ComfyArt.api import auto_models
    with pytest.raises(auto_models.UnregisteredModel):
        auto_models.registered({"model": "nope/x"}, {"a"}, "text_to_image/x")


def test_explicit_fallback_switches_with_log_line(caplog):
    from ComfyArt.api import auto_models
    with caplog.at_level("WARNING"):
        assert auto_models.registered({"model": "nope/x", "fallback": ["nope/y", "a"]}, {"a"}, "text_to_image/x") == ("a", "nope/x")
    assert "registered fallback a" in caplog.text and "nope/x" in caplog.text
