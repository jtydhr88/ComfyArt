"""Pre-check helpers of scripts/gate_lib.sh (gate hardening)."""
import socket
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "scripts" / "gate_lib.sh"
ROOT = Path(__file__).resolve().parents[1]


def _run(fn: str, *args: str, env=None):
    q = " ".join(f"'{a}'" for a in args)
    return subprocess.run(["bash", "-c", f". '{LIB}'; {fn} {q}"], capture_output=True, text=True, env=env)


def test_rejects_hyphen_worktree(tmp_path):
    d = tmp_path / "wt_foo-bar"; d.mkdir()
    r = _run("gate_check_wt_name", str(d))
    assert r.returncode == 1 and "contains '-'" in r.stderr and "use e.g. wt_foobar " in r.stderr
    q = tmp_path / "qa-711h"; q.mkdir()
    assert "use e.g. wt_qa711h " in _run("gate_check_wt_name", str(q)).stderr
    ok = tmp_path / "wt_foobar"; ok.mkdir()
    assert _run("gate_check_wt_name", str(ok)).returncode == 0


def test_node_modules_exists_fails(tmp_path):
    assert _run("gate_check_no_node_modules", str(tmp_path)).returncode == 0
    (tmp_path / "node_modules").mkdir()
    r = _run("gate_check_no_node_modules", str(tmp_path))
    assert r.returncode == 1 and "already exists" in r.stderr


def test_busy_port_detected():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1)
    port = s.getsockname()[1]
    try:
        r = _run("gate_check_ports_free", str(port))
        assert r.returncode == 1 and "busy" in r.stderr
    finally:
        s.close()
    assert _run("gate_check_ports_free", str(port)).returncode == 0


def test_running_pytest_detected():
    # Real default pattern (no GATE_PYTEST_PATTERN override): a process whose cmdline is "python ... -m pytest".
    import os, sys, time
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "-m", "pytest"])
    try:
        time.sleep(0.2)
        env = {k: v for k, v in os.environ.items() if k != "GATE_PYTEST_PATTERN"}
        r = _run("gate_check_no_pytest", env=env)
        assert r.returncode == 1 and "another pytest" in r.stderr and str(p.pid) in r.stderr
    finally:
        p.kill()


def test_log_error_lines(tmp_path):
    good = tmp_path / "g.log"; good.write_text("....\n12 passed in 1.0s\n")
    assert _run("gate_check_log_errors", str(good)).returncode == 0
    bad = tmp_path / "b.log"; bad.write_text("ERROR tests/test_x.py - ImportError\n1 error in 0.1s\n")
    r = _run("gate_check_log_errors", str(bad))
    assert r.returncode == 1 and "error lines" in r.stderr


GATE = LIB.parent / "gate.sh"


def _gate_env(tmp_path, wt):
    import os
    return {**os.environ, "GATE_WT": str(wt), "GATE_MAIN": str(tmp_path / "main"),
            "GATE_PY": "/bin/false", "PATH": os.environ["PATH"]}


def test_rejected_worktree_keeps_sentinel_node_modules(tmp_path):
    wt = tmp_path / "wt_sent"; (wt / "node_modules").mkdir(parents=True)
    (wt / "node_modules" / "SENTINEL").write_text("keep")
    r = subprocess.run(["bash", str(GATE), "sent"], capture_output=True, text=True, env=_gate_env(tmp_path, wt))
    assert r.returncode == 2 and "already exists" in r.stderr
    assert (wt / "node_modules" / "SENTINEL").read_text() == "keep"
    assert not (wt / ".gate_owned").exists()


def test_unowned_interrupted_run_keeps_sentinel(tmp_path):
    # Stale marker from another run (not ours): gate must refuse and must not clean anything.
    import signal, time
    wt = tmp_path / "wt_unowned"; wt.mkdir()
    (wt / ".gate_owned").write_text("999999")
    (wt / "dist").mkdir(); (wt / "dist" / "SENTINEL").write_text("keep")
    r = subprocess.run(["bash", str(GATE), "unowned"], capture_output=True, text=True, env=_gate_env(tmp_path, wt))
    assert r.returncode == 2 and ".gate_owned exists" in r.stderr
    assert (wt / "dist" / "SENTINEL").exists() and (wt / ".gate_owned").read_text() == "999999"
    # Interrupt (SIGTERM) a run that is rejected before owning: sentinel node_modules survives.
    wt2 = tmp_path / "wt_intr"; (wt2 / "node_modules").mkdir(parents=True)
    (wt2 / "node_modules" / "SENTINEL").write_text("keep")
    p = subprocess.Popen(["bash", str(GATE), "intr"], env=_gate_env(tmp_path, wt2),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.05); p.send_signal(signal.SIGTERM); p.wait(10)
    assert (wt2 / "node_modules" / "SENTINEL").read_text() == "keep"
    assert not (wt2 / ".gate_owned").exists()


def test_collection_error_prints_no_count(tmp_path):
    # A broken collection must report COLLECTION_ERROR, never a misleading collected=N.
    src = (LIB.parent / "gate.sh").read_text()
    assert "collected=COLLECTION_ERROR" in src
    i_err, i_cnt = src.index("collected=COLLECTION_ERROR"), src.index('collected=${cnt:-?}')
    assert i_err < i_cnt and "return" in src[i_err:i_cnt]


def test_concurrency_checks_run_before_unit():
    src = (LIB.parent / "gate.sh").read_text()
    unit = src.index('stage UNIT')
    assert src.index("gate_check_no_pytest") < unit and src.index("gate_check_ports_free") < unit
    assert src.index("gate_check_no_pytest", unit) < src.index('stage E2E')


def test_collection_error_tail_drops_pytest_count_line(tmp_path):
    log = tmp_path / "u.collect.log"
    log.write_text("ERROR tests/test_bad.py - SyntaxError\n"
                   "345/3075 tests collected (2730 deselected), 1 error in 2.10s\n"
                   "1 test collected, 1 error in 0.1s\n")
    r = _run("gate_collect_err_tail", str(log))
    assert r.returncode == 0
    assert "SyntaxError" in r.stdout and "collected" not in r.stdout
    assert "gate_collect_err_tail" in (LIB.parent / "gate.sh").read_text()


# --- #712: UNIT runs the whole unit suite; only gate_skip tests (with reason + issue) drop out ---
def test_gate_unit_stage_runs_all_unit_tests():
    sh = (ROOT / "scripts" / "gate.sh").read_text()
    assert 'stage UNIT "not e2e"' in sh
    assert sh.count('-m "not gate_skip"') == 2  # collect + run


def test_gate_skip_marker_registered():
    assert "gate_skip(reason)" in (ROOT / "pyproject.toml").read_text()


def test_every_gate_skip_names_reason_and_issue():
    import re
    hits = []
    for p in (ROOT / "tests").glob("test_*.py"):
        for m in re.finditer(r"@pytest\.mark\.gate_skip\((.*?)\)\n", p.read_text()):
            hits.append((p.name, m.group(1)))
    assert hits, "expected the known main failures to be marked"
    for name, args in hits:
        assert 'reason="' in args and re.search(r"#\d+", args), (name, args)


# --- #712 no-spend: gate stages unset paid keys and block outbound network ---
def test_gate_stages_unset_paid_keys_and_enable_guard():
    sh = (ROOT / "scripts" / "gate.sh").read_text()
    assert sh.count("env -u WAVESPEED_API_KEY -u KIE_API_KEY GATE=1") == 2  # collect + run
    assert "duration=" in sh


def test_gate_guard_blocks_outbound_allows_localhost():
    code = (
        "import os, socket, sys; os.environ['WAVESPEED_API_KEY']='x'; os.environ['GATE']='1';"
        "sys.path.insert(0, 'tests'); import conftest;"
        "assert 'WAVESPEED_API_KEY' not in os.environ;"
        "s=socket.socket(); s.settimeout(1)\n"
        "try:\n s.connect(('8.8.8.8', 443)); print('OPEN')\n"
        "except conftest.GateNetworkBlocked: print('BLOCKED')\n"
        "try:\n socket.getaddrinfo('api.wavespeed.ai', 443); print('DNS')\n"
        "except conftest.GateNetworkBlocked: print('DNSBLOCKED')\n"
        "srv=socket.socket(); srv.bind(('127.0.0.1',0)); srv.listen(1);"
        "c=socket.socket(); c.connect(srv.getsockname()); print('LOCAL')"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.stdout.split() == ["BLOCKED", "DNSBLOCKED", "LOCAL"], out.stderr[-800:]
