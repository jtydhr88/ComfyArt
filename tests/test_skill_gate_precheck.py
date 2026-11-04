"""Pre-check helpers of scripts/gate_lib.sh (gate hardening)."""
import socket
import subprocess
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "scripts" / "gate_lib.sh"


def _run(fn: str, *args: str, env=None):
    q = " ".join(f"'{a}'" for a in args)
    return subprocess.run(["bash", "-c", f". '{LIB}'; {fn} {q}"], capture_output=True, text=True, env=env)


def test_rejects_hyphen_worktree(tmp_path):
    d = tmp_path / "wt_foo-bar"; d.mkdir()
    r = _run("gate_check_wt_name", str(d))
    assert r.returncode == 1 and "contains '-'" in r.stderr
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
    p = subprocess.Popen(["bash", "-c", "exec -a gatefakeproc sleep 30"])
    try:
        import os
        env = {**os.environ, "GATE_PYTEST_PATTERN": "gatefakeproc"}
        r = _run("gate_check_no_pytest", env=env)
        assert r.returncode == 1 and "another pytest" in r.stderr
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
