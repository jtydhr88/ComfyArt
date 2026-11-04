# Merge gate (`scripts/gate.sh`)

`scripts/gate.sh <slug>` is the source of truth for PR gating; manual pytest runs don't count.
Worktree = `$GATE_ROOT/wt_<slug without '-'>` (default root `/workspace`).

Stages: `tsc` → UNIT (`-k "not e2e"`, the whole unit suite since #712) → `vite build` (local only) → pre-checks → E2E (`-k "(skill and e2e) or 650 or creator or (e2e and 712)"`).

## Excluded tests (`gate_skip`)
Every stage runs with `-m "not gate_skip"`. A test that fails on clean main for a reason outside the PR is marked
`@pytest.mark.gate_skip(reason="... (#issue)")` (marker registered in `pyproject.toml`); never deselect it by name.
The reason must name the issue tracking the fix; remove the marker in that fix. `pytest -m gate_skip` lists them.

## Pre-checks / hardening
- Worktree basename containing `-` is rejected (hyphens break imports); name it like `wt_gatepre`.
- Fails if `node_modules` already exists in the worktree before `cp -al` (and leaves it untouched).
- Before the UNIT stage and again before E2E: fails fast if another `python -m pytest` is running, or a port in `GATE_PORTS` (default `9392`, mock WaveSpeed) is busy.
- Per stage: runs `pytest --co` first and prints `collected=N collect_exit=X` (or `collected=COLLECTION_ERROR` and skips the stage on a broken collection) (collection errors no longer pass silently), then prints the pytest `exit=` code and fails on non-zero, and fails if the log has `error`/`ERROR` lines.
- On any failure: logs (tsc, collect, pytest tracebacks, build) are archived to `/tmp/gate_<slug>_XXXX.failure.tar.gz` and the path is printed.
- Ownership: after pre-checks pass the gate writes `.gate_owned` (its PID) in the worktree; cleanup/trap only touch the worktree (dist reset, node_modules removal) if that marker is present and ours, then remove it. A pre-existing marker makes the gate refuse (exit 2).
- Last line is always `<slug> GATE_EXIT=<code>`.

Env overrides: `GATE_ROOT`, `GATE_MAIN` (node_modules source), `GATE_PY`, `GATE_WT`, `GATE_PORTS`.
Helpers live in `scripts/gate_lib.sh`; tests in `tests/test_skill_gate_precheck.py`.

## No spend (#712)
Every pytest stage runs under `env -u WAVESPEED_API_KEY -u KIE_API_KEY GATE=1`. With `GATE=1`, `tests/conftest.py`
removes the paid keys and patches `socket.connect`/`getaddrinfo` so only localhost (mock servers, vite, playwright) is reachable;
any other host raises `GateNetworkBlocked`. Each stage prints `duration=Ns`; parallelize (xdist by dir) if UNIT exceeds 5 min.
