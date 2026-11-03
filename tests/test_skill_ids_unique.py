"""Builtin skill ids must be unique; PHASE1 / PHASE2_NEW / PHASE3_NEW must not overlap. custom-workflow removed (no Lovart card)."""
import re
from pathlib import Path

SKILLS_TS = (Path(__file__).resolve().parents[1] / "src/skills.ts").read_text(encoding="utf-8")


def _const_ids(name: str) -> list[str]:
    m = re.search(rf"export const {name} = \[([^\]]+)\] as const", SKILLS_TS, re.S)
    assert m, f"{name} literal missing"
    return re.findall(r"'([^']+)'", m.group(1))


def _builtin_ids() -> list[str]:
    body = SKILLS_TS.split("export const BUILTIN_SKILLS", 1)[1]
    return re.findall(r"^\s*\{ id: '([^']+)'", body, re.M)


def test_builtin_ids_unique():
    ids = _builtin_ids()
    dups = sorted({i for i in ids if ids.count(i) > 1})
    assert not dups, dups
    assert len(ids) == 49 and "custom-workflow" not in ids


def test_phase_lists_unique_and_disjoint():
    p1, p2, p3 = (_const_ids(n) for n in ("PHASE1_SKILL_IDS", "PHASE2_NEW_SKILL_IDS", "PHASE3_NEW_SKILL_IDS"))
    for lst in (p1, p2, p3):
        assert len(lst) == len(set(lst)), lst
    assert not set(p1) & set(p2), set(p1) & set(p2)
    assert not set(p1) & set(p3), set(p1) & set(p3)
    assert not set(p2) & set(p3), set(p2) & set(p3)
    assert set(p1) | set(p2) | set(p3) | set(_const_ids("UNTOUCHED_SKILL_IDS")) <= set(_builtin_ids())
