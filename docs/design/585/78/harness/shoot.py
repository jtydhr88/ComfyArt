"""#585 #78 AFTER tip-pin — agent chip loading vs after-load (cache seeded DeepSeek).

Prefer:
  CHAT_585_SHOTS=docs/design/585/78/left-ours \\
    PYTHONPATH=.. pytest -q tests/test_e2e_chat_no_flash_557.py -k cached_deepseek -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-agent-chip-loading-zh-light.png",
    "AFTER-agent-chip-loaded-zh-light.png",
    "AFTER-agent-chip-loading-en-dark.png",
    "AFTER-agent-chip-loaded-en-dark.png",
]

if __name__ == "__main__":
    raise SystemExit(
        "Use: CHAT_585_SHOTS=docs/design/585/78/left-ours "
        "pytest -q tests/test_e2e_chat_no_flash_557.py -k cached_deepseek -s"
    )
