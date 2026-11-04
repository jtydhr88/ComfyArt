"""#155: WaveSpeed failures show readable zh/en messages: insufficient balance names the top-up link and says nothing
was charged; 1200 / 429 / other errors never show the raw WaveSpeed text. Mock only, no WaveSpeed calls."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
TOP_UP = "https://wavespeed.ai/top-up"


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("wserr") / "wserr.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "ws_errors.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_insufficient_credit_zh_en(js):
    zh, en = js["zh"]["kinds"]["insufficientCredit"], js["en"]["kinds"]["insufficientCredit"]
    assert "余额不足" in zh and "本次未扣费" in zh and TOP_UP in zh
    assert "balance is too low" in en and "Nothing was charged" in en and TOP_UP in en


@pytest.mark.parametrize("kind", ["moderation", "rateLimit", "invalidKey", "network", "failed"])
def test_other_kinds_readable(js, kind):
    zh, en = js["zh"]["kinds"][kind], js["en"]["kinds"][kind]
    assert zh and en and zh != en and "wsErr." not in zh + en
    assert not any(c in zh + en for c in ("{", "(", "1200", "429", "500"))


def test_raw_text_never_shown(js):
    for lang in ("zh", "en"):
        assert "Internal Error xyz" not in js[lang]["raw"] and js[lang]["raw"] == js[lang]["kinds"]["failed"]
        assert js[lang]["untagged"] == "mask file not found"  # ComfyArt's own validation messages pass through
        assert js[lang]["plain"] == "src must be a /api/view URL"
        assert js[lang]["unknown"] is None


def test_old_comfyui_copy_cleaned():
    # #30: only the "before starting ComfyUI" leftover goes; #219 renamed Local LLM to the built-in agent
    # #345: wall text split into builtin/third-party hints; env-key note lives on localLlmKeyEnvHint
    for f, old in (("en.json", "before starting ComfyUI"), ("zh.json", "在启动 ComfyUI 前")):
        data = json.loads((ROOT / "src/locales" / f).read_text())
        text = " ".join([
            data["botSettings.localLlmKeyEnvHint"],
            data["botSettings.builtinAgentHint"],
            data["agentSetup.desc"],
        ])
        assert old not in text and "COMFYART_LOCAL_LLM_API_KEY" in data["botSettings.localLlmKeyEnvHint"]
        assert "botSettings.claudeCodeCodexQwenCode" not in data


def test_agent_relays_our_copy_verbatim(js):
    # follow-up: the agent's tool result carries our zh/en copy as user_message plus a do-not-paraphrase note
    for lang in ("zh", "en"):
        copy = js[lang]["kinds"]["insufficientCredit"]
        a = js[lang]["agent"]
        assert a["user_message"] == a["error"] == copy and "paraphrase" in a["note"] and "word for word" in a["note"]
        assert js[lang]["agentThrown"].startswith(copy) and "do not paraphrase" in js[lang]["agentThrown"]


def test_bot_commands_use_agent_error():
    src = (ROOT / "src/botCommands.ts").read_text()
    assert "...agentError(r.error)" in src and src.count("agentErrorText(err)") == 2


def test_top_up_link_clickable_in_card():
    # #163 design nit: same copy, the top-up URL becomes a link styled like the card text (underlined, inherits colour)
    src = (ROOT / "src/shapes/GeneratorShape.tsx").read_text()
    assert "{withTopUpLink(error)}" in src and "href={TOP_UP_URL}" in src and 'target="_blank"' in src
    css = (ROOT / "src/styles/canvas.css").read_text()
    assert ".ca-gen-card__error a { color: inherit; text-decoration: underline;" in css


def test_174_timeout_copy_zh_en(js):
    zh, en = js["zh"], js["en"]
    assert zh["timeout"] == "任务超时，可能已扣费约 $0.32。重试前请注意可能重复扣费。"
    assert en["timeout"] == "The task timed out and may have been charged about $0.32. Retrying may charge again."
    # amount unknown: the 「约 $…」 / 'about $…' half is dropped cleanly
    assert zh["timeoutNoAmount"] == "任务超时，可能已扣费。重试前请注意可能重复扣费。"
    assert en["timeoutNoAmount"] == "The task timed out and may have been charged. Retrying may charge again."
    assert "约 $1.50。" in zh["timeoutBody"] and "about $1.50." in en["timeoutBody"]
    assert "quoted price" not in zh["timeoutBody"] + en["timeoutBody"]


def test_712_fmt_usd_two_decimals_and_sub_cent(js):
    assert js["fmtUsd"][:4] == ["$0.10", "$0.14", "$1.50", "$0.32"]
    assert js["fmtUsd"][4:6] == ["< $0.01", "< $0.01"]
    assert js["fmtUsd"][6:8] == ["$0.00", "$0.01"] and js["fmtUsd"][9] == "$12.00"
    # #715: exact-ish amounts ($0.00, < $0.01) drop 约/about; >= 1 cent keeps it
    assert js["zh"]["tiny"].startswith("任务已结束但没有返回图片，可能已扣费 < $0.01。") and "约" not in js["zh"]["tiny"]
    assert "may have been charged < $0.01." in js["en"]["tiny"] and "about" not in js["en"]["tiny"]
    assert js["zh"]["zero"] == "任务超时，可能已扣费 $0.00。重试前请注意可能重复扣费。"
    assert js["en"]["zero"] == "The task timed out and may have been charged $0.00. Retrying may charge again."
    assert "可能已扣费 $0.00。" in js["zh"]["zeroNoTaskId"] and "charged $0.00." in js["en"]["zeroNoTaskId"]
    assert "约 $0.01。" in js["zh"]["cent"] and "about $0.01." in js["en"]["cent"]


def test_712_unregistered_and_task_id_copy(js):
    assert js["zh"]["unregisteredModel"] == "所选模型暂不可用，未发送、未扣费。请换一个模型再试。"
    assert js["en"]["unregisteredModel"] == "The selected model isn't available right now. Nothing was sent or charged. Please try another model."
    assert js["zh"]["noTaskId"].startswith("没有拿到任务编号，无法取回结果，可能已扣费约 $0.10。") and "$0.10" in js["zh"]["noTaskId"]
    assert js["en"]["noTaskId"].startswith("No task ID came back, so the result cannot be fetched") and "task id" not in js["en"]["noTaskId"]
    zh = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    assert js["zh"]["noTaskId"] == "没有拿到任务编号，无法取回结果，可能已扣费约 $0.10。已记为失败。"


# #712 PM: no vendor name in user-facing wsErr copy. These keys predate #712, still name the vendor and are left
# unchanged on purpose (reported in PR #715, out of scope); every other wsErr.* key must not.
PRE_712_VENDOR_KEYS = {"wsErr.failed", "wsErr.insufficientCredit", "wsErr.invalidKey", "wsErr.moderation", "wsErr.network",
                       "wsErr.rateLimit"}


def test_712_no_vendor_or_console_in_wserr_copy():
    import re
    for lang in ("zh", "en"):
        loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text(encoding="utf-8"))
        hits = {k for k, v in loc.items() if k.startswith("wsErr.") and re.search(r"wavespeed|kie", v, re.I)}
        assert hits == PRE_712_VENDOR_KEYS, (lang, sorted(hits ^ PRE_712_VENDOR_KEYS))
        # no pointer to a vendor console / back office, nor to a generation history UI that doesn't exist yet (#715 option a)
        bad = [k for k, v in loc.items() if k.startswith("wsErr.") and re.search(r"控制台|后台|console|dashboard|生成记录|历史记录|generation history", v, re.I)]
        assert not bad, (lang, bad)


def test_712_task_id_shown_when_obtained(js):
    zh, en = js["zh"], js["en"]
    assert zh["timeoutId"].endswith("重试前请注意可能重复扣费。\n\n任务编号：`ws-abc123`（反馈或退款时请提供）")  # #715: own line, id as code
    assert en["timeoutId"].endswith("Retrying may charge again.\n\nTask ID: `ws-abc123` (include it in feedback or refund requests)")
    assert " 任务编号" not in zh["timeoutId"] and " Task ID" not in en["timeoutId"]  # no stray space before the ref line
    assert "任务编号：`ws-abc123`" in zh["noOutputId"] and "Task ID: `ws-abc123`" in en["noOutputId"]
    assert "ws-abc123" in zh["bodyId"] and "ws-abc123" in en["bodyId"]
    assert "ws-abc123" not in zh["noTaskIdWithId"] + en["noTaskIdWithId"]  # noTaskId never shows an id
    assert "ws-abc123" not in zh["timeout"] + en["timeout"]  # no id -> no ref line


def test_715_task_ref_prefixes_match_locales():
    # .ca-task-id is chosen by the text before the code span; keep it in sync with wsErr.taskRef
    src = (ROOT / "src/wsErrors.ts").read_text(encoding="utf-8")
    for lang in ("zh", "en"):
        ref = json.loads((ROOT / f"src/locales/{lang}.json").read_text(encoding="utf-8"))["wsErr.taskRef"]
        assert f"'{ref.split('{0}')[0]}'" in src, (lang, ref)
    css = (ROOT / "src/styles/overlays.css").read_text(encoding="utf-8")
    md = [l for l in css.splitlines() if l.startswith(".ca-md code")]
    assert md == [".ca-md code { padding: 1px 4px; border-radius: 4px; background: var(--ca-field); font-size: 12px; }"]  # main's rule, unchanged
