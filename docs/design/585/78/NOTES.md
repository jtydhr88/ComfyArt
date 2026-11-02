# #585 → #78 tip-pin — cache last agent label while `/bot/status` loads

**Branch:** `feat/585-agent-label-cache` · **Asia/Shanghai** · Issue #585 P2  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the PR body (exact tip SHA). Do not treat an older tip in chat history as current.  
**Scope:** `src/ui/AgentPicker.tsx` only (home + canvas share `useCurrentAgent`). No new components. No canvas-reload loader over the input. No competitor brand strings in `src/`.

## Behavior / lock

| Item | Spec |
|------|------|
| Cache key | `comfyart.lastAgentLabel` → `{ id, shortLabel }` in localStorage |
| While `/bot/status` loads | Show last cached agent icon+label (not Loomi flash) |
| First open (no cache) | Fall back to built-in Loomi only |
| Missing shortLabel | Never show raw id (e.g. `claude-code`); use `safeAgentDisplayName` |
| Cache write | On successful provider resolve via `useEffect` in `useCurrentAgent` |

## LEFT = ours (AFTER) — live dist 1280×800, cropped to composer agent chip

Harness: `harness/shoot.py` (Playwright vs `app_url`, hold `/bot/status` ~2.5s, cache seeded DeepSeek). Same path as `CHAT_585_SHOTS=docs/design/585/78/left-ours pytest tests/test_e2e_chat_no_flash_557.py -k cached_deepseek`.

| File | Shows |
|------|-------|
| `left-ours/AFTER-agent-chip-loading-zh-light.png` | zh-light — DeepSeek chip while status held (from cache) |
| `left-ours/AFTER-agent-chip-loaded-zh-light.png` | zh-light — DeepSeek chip after status resolves |
| `left-ours/AFTER-agent-chip-loading-en-dark.png` | en-dark — DeepSeek chip while status held (from cache) |
| `left-ours/AFTER-agent-chip-loaded-en-dark.png` | en-dark — DeepSeek chip after status resolves |

## @design
Please re-sign after visual check on tip (loading matches after-load; no Loomi flash; no raw id).
