"""#766: collapsed Thought tip is 正文 (no ask_user); expanded thinking keeps ask_user."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
MSG = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")


def test_helper_and_wiring():
    assert "export function thoughtCollapsedTip" in MSG
    thought = MSG.split("function Thought(")[1].split("\nfunction StepGroup")[0]
    assert "thoughtCollapsedTip(text)" in thought
    # collapsed uses tip; expanded keeps raw text.trim()
    assert "ca-chat__thoughttext" in thought
    assert "text.trim()" in thought
    assert "sanitizeThoughtText" not in MSG
    assert 'data-testid="live-thought-inline"' in MSG
    assert "thoughtCollapsedTip(s.text" in MSG
    # process detail expanded stays raw
    detail = [l for l in MSG.splitlines() if "ca-process__detail" in l]
    assert detail and "sanitizeThoughtText" not in "".join(detail)
    assert any("s.text.trim()" in l for l in detail)


def test_tip_behavior_node():
    js = r"""
function thoughtCollapsedTip(text) {
  const lines = text.trim().split('\n').map((l) => l.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    if (!/ask_user/i.test(lines[i])) return lines[i];
  }
  return '';
}
const samples = [
  ['Plan the logo.\nLet me call ask_user with one multiple-choice question.', 'Plan the logo.'],
  ['Let me call ask_user with one multiple-choice question.', ''],
  ['Ask the style first.\nThen wait.', 'Then wait.'],
  ['CALL ASK_USER now\nReady.', 'Ready.'],
  ['Only ask_user here', ''],
];
let fail = 0;
for (const [raw, want] of samples) {
  const got = thoughtCollapsedTip(raw);
  if (got !== want) { console.error('FAIL', {raw, want, got}); fail++; }
  if (/ask_user/i.test(got)) { console.error('LEAK', got); fail++; }
}
// expanded contract: raw text unchanged (caller responsibility)
const expanded = 'Plan.\nLet me call ask_user with one multiple-choice question.';
if (expanded.trim() !== expanded) { fail++; }
if (!/ask_user/i.test(expanded)) { fail++; }
if (fail) process.exit(1);
console.log('ok', samples.length);
"""
    r = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
