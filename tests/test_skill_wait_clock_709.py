"""#709: wait_timeout runs on the run's monotonic clock (same as the other loop caps), never time.time()."""
from __future__ import annotations

import inspect
import time

from ComfyArt.bot import agent_loop
from ComfyArt.bot.run_budget import ProgressTracker, StepObservation


class FakeClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def poll(job="job1"):
    return [StepObservation(tool="wait_generation", args_key='wait_generation\x00{"ids": ["%s"]}' % job,
                            result='{"status": "pending"}', failed=False)]


def tracker():
    return ProgressTracker(3, 6, 3)


def test_wait_timeout_uses_fake_clock_not_wall_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: (_ for _ in ()).throw(AssertionError("time.time used")))
    clk, tr = FakeClock(), tracker()
    assert not tr.wait_timeout(poll(), now=clk())
    clk.t += 599
    assert not tr.wait_timeout(poll(), now=clk())
    clk.t += 2                                   # 601 s on the run clock since the first poll
    assert tr.wait_timeout(poll(), now=clk())
    assert tr.wait_waited_s == 601


def test_wall_clock_jump_does_not_trip_timeout(monkeypatch):
    clk, tr = FakeClock(), tracker()
    monkeypatch.setattr(time, "time", lambda: 10**12)   # a wall-clock jump must not matter
    for _ in range(5):
        clk.t += 10
        assert not tr.wait_timeout(poll(), now=clk())


def test_default_clock_is_monotonic(monkeypatch):
    monkeypatch.setattr(time, "monotonic", lambda: 5.0)
    monkeypatch.setattr(time, "time", lambda: (_ for _ in ()).throw(AssertionError("time.time used")))
    tr = tracker()
    tr.wait_timeout(poll())
    assert tr.wait_first == {"job1": 5.0}


def test_agent_loop_passes_the_run_clock():
    src = inspect.getsource(agent_loop.run)
    assert "wait_timeout(obs, now=clock())" in src
    assert inspect.signature(agent_loop.run).parameters["clock"].default is time.monotonic
