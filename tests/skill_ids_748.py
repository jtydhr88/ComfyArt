"""#748 shared skill-id constants — generated from src/data/skills-748.json (raw/INDEX.md Final table); never hardcode ids."""
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).resolve().parents[1] / "src/data/skills-748.json").read_text())["skills"]
FINAL_IDS = list(_DATA)  # the 16 reference skillKeys
TEMPLATE_IDS = [k for k, v in _DATA.items() if v["kind"] == "template"]
EXAMPLE_IDS = [k for k, v in _DATA.items() if v["kind"] == "example"]
HOLD_IDS = [k for k, v in _DATA.items() if v.get("hold")]
TITLE = {k: v["title"] for k, v in _DATA.items()}
ASSET_DIR = {k: v["assetDir"] for k, v in _DATA.items()}  # washed-asset folder per id (review-assets paths predate the ids)
def asset_dir(sid: str) -> str:
    return ASSET_DIR.get(sid, sid)
