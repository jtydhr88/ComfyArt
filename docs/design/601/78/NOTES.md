# #601 soft FU → #78 visual review

Skill run dialog soft gaps from #599 design soft PASS:

1. Distinct zh/en keys: header **开始创作 / Start Creating** (`skillRun.header`) vs CTA **开始制作 / Start making** (`skillRun.start`)
2. Examples filmstrip zero-padded `01`…`10` via `filmstripIndexLabel`
3. Share + Bookmark already on tip from #581 (`skillShareUrl` / `copyText` / local `toggleFavourite`) — kept wired; no fake favorite counts

Gold UX reference = competitor site (do **not** put competitor brand string in `src/`).

## Refresh after #617

- Merged `origin/main` @ `b315a5700edb049980d865d05d096f2e59a3a512` (#617/#590 FEED_V1 wash-v2 `0e923023…`) into `feat/601-skill-dialog-soft`.
- VOID prior tip `700b508d` (CONFLICTING vs main). Soft FU locales/components kept; FEED_V1 stays wash-v2 pin.
- AFTER shots re-shot post-merge (`DESIGN_601_78_SHOOT=1`); tip-pin absolute raw URLs in draft PR body at **new** tip SHA.

## LEFT = ours (AFTER)

Harness: `harness/shoot.py` + `tests/test_design_601_78_shots.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-skill-modal-header-cta-filmstrip-zh-light.png` | Dual-col modal zh-light: header≠CTA + filmstrip 01… + share/bookmark |
| `left-ours/AFTER-skill-modal-header-cta-share-bookmark-en-dark.png` | Dual-col modal en-dark: Start Creating / Start making + actions |
| `left-ours/AFTER-skill-modal-filmstrip-pad-crop-zh-light.png` | Filmstrip number crop (01…) |
| `left-ours/AFTER-skill-modal-righthead-cta-crop-zh-light.png` | Right column header + primary CTA crop |

Tip-pin: absolute `raw.githubusercontent.com` URLs in draft PR body at tip SHA.
