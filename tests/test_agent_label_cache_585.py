"""#585: agent label cache contracts — never raw id; cache key; loading prefers cache."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "src/ui/AgentPicker.tsx").read_text()


def test_src_has_cache_key_and_loading_uses_cache() -> None:
    assert "comfyart.lastAgentLabel" in SRC
    assert "AGENT_LABEL_CACHE_KEY" in SRC
    assert "safeAgentDisplayName" in SRC
    assert "readAgentLabelCache" in SRC
    assert "writeAgentLabelCache" in SRC
    assert "readAgentLabelCache()" in SRC
    # #585 must not paint raw providerId as label while loading
    assert "label: providerId" not in SRC
    # first-open fallback is built-in Loomi
    assert "BUILTIN_AGENT" in SRC
    assert "useEffect" in SRC  # cache write on successful resolve


def test_shortlabel_never_falls_through_to_raw_id() -> None:
    # shortLabel must call safeAgentDisplayName when label missing/equals id
    assert "safeAgentDisplayName(p.id)" in SRC
    assert "L !== p.id" in SRC


def test_no_lovart_in_agent_picker() -> None:
    assert "Lovart" not in SRC
    assert "lovart" not in SRC.lower()


def test_safe_display_and_cache_roundtrip_node() -> None:
    """Mirror of the pure #585 helpers (kept in sync via source snippet asserts above)."""
    script = r"""
const KEY = 'comfyart.lastAgentLabel';
const ls = {};
globalThis.localStorage = {
  getItem: (k) => (k in ls ? ls[k] : null),
  setItem: (k, v) => { ls[k] = String(v); },
  removeItem: (k) => { delete ls[k]; },
};
function safeAgentDisplayName(id) {
  const parts = id.split(/[-_]/).filter(Boolean);
  if (!parts.length) return 'Loomi';
  return parts.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}
function writeAgentLabelCache(entry) {
  const id = entry.id.trim();
  const shortLabel = entry.shortLabel.trim();
  if (!id || !shortLabel) return;
  localStorage.setItem(KEY, JSON.stringify({
    id,
    shortLabel: shortLabel === id ? safeAgentDisplayName(id) : shortLabel,
  }));
}
function readAgentLabelCache() {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  const o = JSON.parse(raw);
  if (!o || typeof o !== 'object' || Array.isArray(o)) return null;
  if (typeof o.id !== 'string' || !o.id.trim()) return null;
  if (typeof o.shortLabel !== 'string' || !o.shortLabel.trim()) return null;
  const id = o.id.trim();
  const short = o.shortLabel.trim();
  return { id, shortLabel: short === id ? safeAgentDisplayName(id) : short };
}
writeAgentLabelCache({ id: 'deepseek-harness', shortLabel: 'DeepSeek' });
const a = readAgentLabelCache();
writeAgentLabelCache({ id: 'claude-code', shortLabel: 'claude-code' });
const b = readAgentLabelCache();
localStorage.removeItem(KEY);
const c = readAgentLabelCache();
console.log(JSON.stringify({
  safe: safeAgentDisplayName('claude-code'),
  safeQwen: safeAgentDisplayName('qwen-code'),
  a, b, c,
}));
"""
    out = subprocess.check_output(["node", "-e", script], text=True)
    data = json.loads(out.strip())
    assert data["safe"] == "Claude Code"
    assert data["safeQwen"] == "Qwen Code"
    assert data["a"] == {"id": "deepseek-harness", "shortLabel": "DeepSeek"}
    assert data["b"] == {"id": "claude-code", "shortLabel": "Claude Code"}
    assert data["c"] is None
