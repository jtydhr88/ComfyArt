# #601 soft FU → #78 visual review

Skill run dialog soft gaps from #599 design soft PASS:

1. Distinct zh/en keys: header **开始创作 / Start Creating** (`skillRun.header`) vs CTA **开始制作 / Start making** (`skillRun.start`)
2. Examples filmstrip zero-padded `01`…`10` via `filmstripIndexLabel`
3. Share + Bookmark already on tip from #581 (`skillShareUrl` / `copyText` / local `toggleFavourite`) — kept wired; no fake favorite counts

Gold UX reference = competitor site (do **not** put competitor brand string in `src/`).

## LEFT = ours (AFTER)

Harness: `harness/shoot.py` + `tests/test_design_601_78_shots.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-skill-modal-header-cta-filmstrip-zh-light.png` | Dual-col modal zh-light: header≠CTA + filmstrip 01… + share/bookmark |
| `left-ours/AFTER-skill-modal-header-cta-share-bookmark-en-dark.png` | Dual-col modal en-dark: Start Creating / Start making + actions |
| `left-ours/AFTER-skill-modal-filmstrip-pad-crop-zh-light.png` | Filmstrip number crop (01…) |
| `left-ours/AFTER-skill-modal-righthead-cta-crop-zh-light.png` | Right column header + primary CTA crop |

Tip-pin: absolute `raw.githubusercontent.com` URLs in draft PR body at tip SHA.
