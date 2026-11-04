"""#715 (tech lead): run_raw (used by /comfyart/ocr) must put the submitted task id on timeout / noOutput error bodies.
The mock answers the real submit HTTP call with an id; nothing pre-carries task_id."""
import pytest
from PIL import Image

from test_wavespeed import ws  # noqa: F401  (mock WaveSpeed server fixture)

TID = "8f3c2a9e4b1d4c7fa6e05b2d9c13f7a4"


@pytest.mark.parametrize("case,kind", [("timeout", "timeout"), ("no_outputs", "noOutput")])
async def test_715_ocr_error_body_carries_submitted_task_id(ws, bot_client, fresh_user_dir, case, kind):  # noqa: F811
    path = fresh_user_dir / "output" / "sale.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 24), "white").save(path)
    ws["task_id"] = TID  # the id comes back from the mocked POST submit response only
    if case == "timeout":
        ws["status"] = "timeout"
    else:
        ws["no_outputs"] = True
    res = await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=sale.png&subfolder=&type=output"})
    body = await res.json()
    assert res.status >= 400 and ws["submits"], body
    err = body["error"]
    assert err["kind"] == kind and err["task_id"] == TID, body
