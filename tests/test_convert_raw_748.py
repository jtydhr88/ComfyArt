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
