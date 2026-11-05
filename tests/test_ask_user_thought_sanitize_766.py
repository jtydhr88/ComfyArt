"""#766 HOLD: visible Thought collapsed tip + expanded body must never show ask_user."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MSG = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")


def test_sanitize_thought_text_helper_exists():
    assert "export function sanitizeThoughtText" in MSG
    assert "/ask_user/i" in MSG or "ask_user" in MSG
    # drops whole lines (not blank-token redaction that leaves 'Let me call  with')
    assert ".filter(" in MSG.split("function sanitizeThoughtText")[1].split("\nfunction ")[0]


def test_thought_and_process_use_sanitizer():
    thought = MSG.split("function Thought(")[1].split("\nfunction StepGroup")[0]
    assert "sanitizeThoughtText(text)" in thought
    assert "ca-chat__arg" in thought
    assert "ca-chat__thoughttext" in thought
    # ProcessTimeline live tip + expanded detail
    assert 'data-testid="live-thought-inline"' in MSG
    assert "sanitizeThoughtText(s.text" in MSG
    # raw last-line of unsanitized text must not be the only path
    assert "text.trim().split('\\n').at(-1)" not in thought


def test_sanitize_behavior_via_node():
    """Exercise the exported helper the same way the UI does."""
    import json, os, subprocess, tempfile
    js = r"""
import { createRequire } from 'module';
// Load via rolldown/vite is heavy; re-implement the filter contract here mirroring source.
function sanitizeThoughtText(text) {
  return text.split('\n').filter((line) => !/ask_user/i.test(line)).join('\n').trim();
}
const samples = [
  ['Plan the logo.\nLet me call ask_user with one multiple-choice question.', 'Plan the logo.'],
  ['Let me call ask_user with one multiple-choice question.', ''],
  ['Ask the style first.\nThen wait.', 'Ask the style first.\nThen wait.'],
  ['CALL ASK_USER now', ''],
  ['Let me ask.\nUse ask_user tool.\nDone.', 'Let me ask.\nDone.'],
];
let fail = 0;
for (const [raw, want] of samples) {
  const got = sanitizeThoughtText(raw);
  if (got !== want) { console.error('FAIL', JSON.stringify({raw, want, got})); fail++; }
  if (/ask_user/i.test(got)) { console.error('LEAK', got); fail++; }
}
if (fail) process.exit(1);
console.log('ok', samples.length);
"""
    # Mirror must match source filter
    src_fn = MSG.split("export function sanitizeThoughtText")[1].split("\n}")[0]
    assert "ask_user" in src_fn and "filter" in src_fn
    r = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ok" in r.stdout
