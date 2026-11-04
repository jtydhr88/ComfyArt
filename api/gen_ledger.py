"""#712: generation run ledger. A paid submit is written down the moment WaveSpeed returns its request id, before any
poll, so a dropped poll or a restart can still fetch the result with the same id (never a resubmit). A run that was
charged but produced nothing, or that never got an id back, lands in ``failures`` with its cost and task id and
``generation_succeeded`` false, instead of vanishing.

File: <ComfyArt app dir>/generation_runs.json  {"runs": {task: {...}}, "failures": [...]}. Never holds keys or prompts.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from ._common import app_path

log = logging.getLogger("comfyart.gen_ledger")
FILE = "generation_runs.json"
MAX_RUNS = 500
MAX_FAILURES = 200
_lock = threading.Lock()


def path() -> str:
    return app_path(FILE)


def _load() -> dict:
    try:
        with open(path(), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    runs = doc.get("runs") if isinstance(doc.get("runs"), dict) else {}
    fails = doc.get("failures") if isinstance(doc.get("failures"), list) else []
    return {"runs": runs, "failures": fails}


def _save(doc: dict) -> None:
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if len(doc["runs"]) > MAX_RUNS:
        keep = sorted(doc["runs"].items(), key=lambda kv: kv[1].get("submitted_at") or 0)[-MAX_RUNS:]
        doc["runs"] = dict(keep)
    doc["failures"] = doc["failures"][-MAX_FAILURES:]
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _guard(fn):
    def run(*a, **kw):
        try:
            with _lock:
                return fn(*a, **kw)
        except Exception:  # noqa: BLE001 - the ledger must never break a generation
            log.exception("#712: generation ledger write failed")
            return None
    return run


@_guard
def record_submit(task: str, provider: str, model: str, feature: str = "", quoted_usd: float | None = None) -> dict:
    """Persist the request id right after submit, before the first poll."""
    doc = _load()
    row = {"task_id": task, "provider": provider, "model": model, "feature": feature, "quoted_usd": quoted_usd,
           "submitted_at": time.time(), "status": "submitted", "generation_succeeded": None}
    doc["runs"][task] = row
    _save(doc)
    log.info("#712: saved request id %s (%s %s) before polling", task, provider, model)
    return row


@_guard
def mark_succeeded(task: str, outputs: int) -> None:
    doc = _load()
    row = doc["runs"].get(task)
    if row is None:
        return
    row.update(status="completed", generation_succeeded=True, outputs=outputs, finished_at=time.time())
    _save(doc)


@_guard
def record_failure(task: str | None, provider: str, model: str, reason: str, kind: str = "failed",
                   cost_usd: float | None = None, feature: str = "") -> dict:
    """A failed generation: generation_succeeded=false, plus one row in ``failures`` (cost + task id)."""
    doc = _load()
    fail = {"task_id": task, "provider": provider, "model": model, "feature": feature, "kind": kind,
            "reason": reason, "cost_usd": cost_usd, "at": time.time(), "generation_succeeded": False}
    if task:
        row = doc["runs"].setdefault(task, {"task_id": task, "provider": provider, "model": model, "feature": feature,
                                            "submitted_at": time.time()})
        if row.get("generation_succeeded") is False:
            return fail  # already recorded once for this task
        row.update(status="failed", generation_succeeded=False, kind=kind, reason=reason, cost_usd=cost_usd,
                   finished_at=time.time())
    doc["failures"].append(fail)
    _save(doc)
    log.warning("#712: generation failed (task %s, %s %s, kind %s, cost %s): %s",
                task or "<no id>", provider, model, kind, "unknown" if cost_usd is None else f"${cost_usd:g}", reason)
    return fail


def run(task: str) -> dict | None:
    try:
        return _load()["runs"].get(task)
    except Exception:  # noqa: BLE001
        return None


def failures() -> list[dict]:
    try:
        return list(_load()["failures"])
    except Exception:  # noqa: BLE001
        return []


def pending() -> dict:
    return {k: v for k, v in _load()["runs"].items() if v.get("status") == "submitted"}
