# Merge gate (`scripts/gate.sh`)

`scripts/gate.sh <slug>` is the source of truth for PR gating; manual pytest runs don't count.
Worktree = `$GATE_ROOT/wt_<slug without '-'>` (default root `/workspace`).

Stages: `tsc` → UNIT (`-k "skill and not e2e"`) → `vite build` (local only) → pre-checks → E2E (`-k "(skill and e2e) or 650 or creator"`).

## Pre-checks / hardening
- Worktree basename containing `-` is rejected (hyphens break imports); name it like `wt_gatepre`.
- Fails if `node_modules` already exists in the worktree before `cp -al` (and leaves it untouched).
- Before E2E: fails fast if another `python -m pytest` is running, or a port in `GATE_PORTS` (default `9392`, mock WaveSpeed) is busy.
- Per stage: runs `pytest --co` first and prints `collected=N collect_exit=X` (collection errors no longer pass silently), then prints the pytest `exit=` code and fails on non-zero, and fails if the log has `error`/`ERROR` lines.
- On any failure: logs (tsc, collect, pytest tracebacks, build) are archived to `/tmp/gate_<slug>_XXXX.failure.tar.gz` and the path is printed.
- Ownership: after pre-checks pass the gate writes `.gate_owned` (its PID) in the worktree; cleanup/trap only touch the worktree (dist reset, node_modules removal) if that marker is present and ours, then remove it. A pre-existing marker makes the gate refuse (exit 2).
- Last line is always `<slug> GATE_EXIT=<code>`.

Env overrides: `GATE_ROOT`, `GATE_MAIN` (node_modules source), `GATE_PY`, `GATE_WT`, `GATE_PORTS`.
Helpers live in `scripts/gate_lib.sh`; tests in `tests/test_skill_gate_precheck.py`.
