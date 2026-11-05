"""#748 QA: convert_raw_748 fails hard on bad id / official collision / duplicate app ids."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("c748", Path(__file__).parent.parent / "scripts/convert_raw_748.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)


def test_ugc_suffix_stripped_official_kept():
    assert c.app_id("fabric-collage-1730000000000-ab12cd") == "fabric-collage"
    assert c.app_id("interior-architectural-visualization") == "interior-architectural-visualization"


@pytest.mark.parametrize("bad", ["Poster_Maker", "poster maker", "-poster", "海报"])
def test_bad_id_format_fails(bad):
    with pytest.raises(c.ConvertError, match="bad id format"):
        c.check_app_ids([bad], set())


def test_collision_with_official_fails():
    with pytest.raises(c.ConvertError, match="collides with official"):
        c.check_app_ids(["poster-design", "poster-design-1730000000000-ab12cd"], {"poster-design"})


def test_duplicate_app_ids_fail():
    with pytest.raises(c.ConvertError, match="duplicate app id"):
        c.check_app_ids(["logo-a-1730000000000-ab12cd", "logo-a-1730000099999-ff00ee"], set())


def test_own_id_collision_fails():
    with pytest.raises(c.ConvertError):
        c.check_own({"poster-design": {}}, ["poster-design"])


def test_ext_appends_own_templates(tmp_path):
    import json
    (tmp_path / "raw").mkdir(); (tmp_path / "own").mkdir()
    (tmp_path / "own" / "x-skill.ext.json").write_text(json.dumps({"skillKey": "x-skill", "source": "comfyart", "collectionMembers": [{"title": "t8"}]}))
    assert c.load_ext(tmp_path / "raw", "x-skill") == [{"title": "t8"}]
    assert c.load_ext(tmp_path / "raw", "y-skill") == []
    (tmp_path / "own" / "z-skill.ext.json").write_text(json.dumps({"skillKey": "other", "source": "comfyart"}))
    with pytest.raises(c.ConvertError, match="bad ext"):
        c.load_ext(tmp_path / "raw", "z-skill")


def test_character_raw_plus_ext_is_8():
    import json
    t = json.loads((Path(__file__).parent.parent / "src/data/skills-748.json").read_text())["skills"]["character-sheet-design"]["templates"]
    assert len(t) == 8 and t[-1]["source"] == "comfyart" and t[-1]["name"]["en"] == "Editorial Fashion Sheet"
    assert all("source" not in x for x in t[:7])


# QA: every Final 16 skill's left media (length + video markers) and right inputs equal raw (+ own ext).
# media string: v = video, i = image. Template skills: per-template media depth + inputs.
import json  # noqa: E402

RAW = Path("/workspace/lovart-inputs/raw")
DATA = json.loads((Path(__file__).parent.parent / "src/data/skills-748.json").read_text())["skills"]
EXAMPLE = {  # sid: (media, n inputs)
    "cover-design-director": ("v", 2), "poster-differentiated-compiler": ("iiiii", 2), "meta-ads-creative-director": ("iiii", 2),
    "marketing-campaign-generator": ("v" + "i" * 7, 2), "banner-design-director": ("v", 2), "logo-material-explorer": ("vii", 2),
    "mobile-app-visual-design": ("i" * 13, 2), "web-product-visual-design": ("i" * 9, 2), "universal-multi-angle-grid": ("i" * 11, 2),
    "interior-architectural-visualization": ("iiii", 2), "rednote-cover-maker": ("i" * 10, 2),
}
TEMPLATE = {  # sid: ([media depth per template], n inputs per template)
    "character-sheet-design": ([1] * 8, None), "packaging-design-director": ([1, 3, 4, 1, 1], None), "motion-poster-generator": ([1, 1], None),
    "product-tvc-advertisement-generator": ([1] * 7, 5), "brand-identity-director": ([4] * 6, None),
}


def _raw(sid):
    f = {c.app_id(r["id"]): r["file"] for r in c.final_table((RAW / "INDEX.md").read_text())}[sid]
    return json.loads((RAW / f).read_text())


def test_final16_covered():
    assert set(DATA) == set(EXAMPLE) | set(TEMPLATE) and len(DATA) == 16


@pytest.mark.parametrize("sid", sorted(EXAMPLE))
def test_example_media_and_inputs_match_raw(sid):
    s, (media, n) = DATA[sid], EXAMPLE[sid]
    assert "".join(h["type"][0] for h in s["highlights"]) == media
    assert len(s["inputs"]) == n
    if RAW.exists():
        ct = _raw(sid).get("content") or {}
        hl = sorted(ct.get("highlights") or [], key=lambda h: h.get("order", 0))
        assert "".join("v" if h.get("mediaType") == "video" else "i" for h in hl) == media
        assert len(((ct.get("template") or {}).get("questions")) or []) == n


@pytest.mark.parametrize("sid", sorted(TEMPLATE))
def test_template_media_and_inputs_match_raw_plus_ext(sid):
    s, (depths, n) = DATA[sid], TEMPLATE[sid]
    assert [t["depth"] for t in s["templates"]] == depths == [len(t["media"]) for t in s["templates"]]
    if n is not None:
        assert all(len(t["inputs"]) == n for t in s["templates"])
    if RAW.exists():
        d = _raw(sid)
        mem = (d.get("collectionMembers") or []) + c.load_ext(RAW, sid)
        assert len(mem) == len(depths)
        for t, m in zip(s["templates"], mem):
            mc = m.get("content") or {}
            if not (mc.get("media") is None and m in c.load_ext(RAW, sid)):
                assert len(mc.get("media") or []) == t["depth"]
                assert [x["type"] for x in t["media"]] == [c._kind(x.get("url")) for x in mc.get("media") or []]
            assert [q["key"] for q in t["inputs"]] == [q["key"] for q in ((mc.get("template") or {}).get("questions") or [])]


def test_own_id_collides_with_final_id_fails():
    with pytest.raises(c.ConvertError, match="Final skill id"):
        c.check_own({"logo-material-explorer": {}}, ["logo-material-explorer"])


def test_own_id_collides_with_feed_skillkey_fails():
    with pytest.raises(c.ConvertError, match="reference feed skillKey"):
        c.check_own({}, ["animated-poster-maker"], frozenset({"animated-poster-maker"}))


def test_required_ext_missing_is_hard_fail(tmp_path):
    (tmp_path / "raw").mkdir()  # no sibling own/ dir → character would silently drop to 7 / 27 total
    with pytest.raises(c.ConvertError, match="required ext missing"):
        c.load_ext(tmp_path / "raw", "character-sheet-design")
    assert c.load_ext(tmp_path / "raw", "packaging-design-director") == []
