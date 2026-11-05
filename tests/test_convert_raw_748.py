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
