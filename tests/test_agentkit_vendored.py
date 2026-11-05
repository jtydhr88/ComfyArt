"""#754: bot/agentkit.lock documents the comfy-agent-kit files we vendor unmodified. It is a check,
not a sync: files we customized (local_llm, providers, guide, codex, ...) are ours and are not listed."""
import hashlib
import json
from pathlib import Path

BOT = Path(__file__).resolve().parents[1] / "bot"
OURS = {"local_llm.py", "providers.py", "guide.py", "codex.py", "claude_code.py", "qwen_code.py",
        "deepseek_harness.py", "deepseek_harness_runtime.py"}


def _lock() -> dict:
    return json.loads((BOT / "agentkit.lock").read_text(encoding="utf-8"))["files"]


def test_vendored_kit_files_are_unmodified():
    files = _lock()
    assert files
    edited = [n for n, h in files.items()
              if hashlib.sha256((BOT / n).read_bytes().replace(b"\r\n", b"\n")).hexdigest() != h]
    assert not edited, f"{edited} are unmodified kit copies; customize via a wrapper instead"


def test_lock_never_covers_our_customized_files():
    assert not OURS & set(_lock())
