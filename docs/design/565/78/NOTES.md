# #565 #78 — stale e2e on main (tests only)

## Diagnosis (tip vs issue tips)

| Item | On issue tips (`920596c` / `e1756fa`) | On current `origin/main` tip | Fix |
|---|---|---|---|
| `test_e2e_toolbar_polish_283` ×6 | All **360px** cases fail: collapse-chat click times out (`element is outside of the viewport`) | **13/13 green** (product already fixed on main; no stale assert) | none (verify only) |
| `test_e2e_audio_speech_voice_509` ×1 | Missing fixture `artifacts/509-2/speech-demo.json` (`assert WF.is_file()`) | same until fixture added | commit fixture (same shape as `artifacts/509-3/*.json`) |
| worktree rolldown ×2 setup | Env: worktree without `npm ci` / `node_modules/.bin/rolldown`. No hardcoded `../node_modules/.bin/rolldown` in harness (paths use repo-root `ROOT` / `_REPO`). Symlink target inside `.bin` is `../rolldown/bin/cli.mjs` (package-local). | N/A when `scripts/test.sh` / `npm ci` run | no harness change |

## AFTER embeds (this tip)

- `after/pytest-pass.png` — both files green
- `after/workflows-speech-assigned-zh-light.png` — custom speech row shows `speech-demo`
- `after/audio-speech-voice-zh-light.png` — audio dialog voice fieldselect after custom speech

## Out of scope
No product behavior changes. No skips/xfails. No `src/` edits.
