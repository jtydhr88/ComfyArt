"""#687 — hard-coded Lovart dialog field spec (source: docs/qa/687-audit/README.md @6fdfd01c + gold dialog_fields.txt).
Shared by the unit test (tests/test_skill_fields_687.py) and the e2e (tests/test_e2e_skill_fields_687.py).
Row = (key, type, required, accept, maxLength, zh label, en label, en placeholder)."""
UP = ("file", "image", False, "image", None, "上传文件", "Upload Files", None)
NOTE500 = ("note", "textarea", False, None, 500, "补充描述", "Additional Details", "Anything else to add?")
LOVART_2 = [UP, NOTE500]
MOTION_REMAKE = [
    ("refVideo", "image", True, "video", None, "参考视频", "Reference video file", None),
    ("remakeBrief", "textarea", True, None, 200, "重制说明", "Remake brief",
     "What should change or stay? Combine product, person, brand, copy or other requested changes."),
    ("replaceImages", "image", False, "image", None, "替换图（可选）", "Replacement images (optional)", None),
    ("visualDirection", "textarea", False, None, 200, "视觉方向", "Visual direction",
     "Describe your preferred visual treatment or provide a reference. Leave blank if you have no preference."),
]
VISUAL = ("visual", "text", False, None, None, "视觉呈现方式", "Visual presentation", "Visual preferences to keep or avoid; leave blank if none")
SPEC = {
    **{sid: LOVART_2 for sid in ["brand", "packaging", "character", "logo-material", "meta-ads", "marketing-campaign",
                                 "web-product", "mobile-ui", "social", "poster", "banner", "interior"]},  # #687 HOLD fix: all 12 aligned
    "motion": MOTION_REMAKE,
    # (4) unchanged — already match Lovart
    "product": [("productImage", "image", True, "image", None, "商品图片", "Product images", None),
                ("productInfo", "text", False, None, None, "商品资料", "Product details", "Product name, real selling points and use cases"), VISUAL],
    "thumbnail": [("file", "image", False, "image", None, "上传文件", "Upload file", None),
                  ("note", "textarea", False, None, None, "补充描述", "Additional notes", "Anything you want to add?")],
    "multi-angle": [("file", "image", False, "image", None, "上传文件", "Upload file", None),
                    ("note", "textarea", False, None, None, "补充描述", "Additional notes",
                     "Anything you want to add? Uploading a reference image is recommended")],
}
CHANGED = [k for k in SPEC if k not in ("product", "thumbnail", "multi-angle")]
NOTE_PH_ZH = "还有什么想补充的吗？"  # exact zh placeholder on all 12 reference cards
REF12 = [k for k, v in SPEC.items() if v is LOVART_2]
MOTION_TITLE = {"zh": "参考视频重制", "en": "Reference Video Remake"}
MOTION_DESC_EN = "Adapt a reference video with your content while preserving its shot structure and pacing"
MOTION_FEATURED_REMOVED = "580/featured-v1/motion/03.webp"

# #687 decision (技术经理): NO old→new key mapping. Old drafts / handoff links using these pre-#687 keys
# must not throw and must open the dialog with empty fields.
OLD_KEYS_687 = {
    "brand": {"brandInfo": "Old brand", "brandAssets": "/view?f=old.png", "visual": "old visual"},
    "packaging": {"packInfo": "Old pack", "visual": "old"},
    "character": {"characterRef": "/view?f=old.png", "characterInfo": "Old char"},
    "logo-material": {"logoImage": "/view?f=old.png", "materialNotes": "old"},
    "meta-ads": {"campaignBrief": "Old brief", "adAssets": "/view?f=old.png"},
    "marketing-campaign": {"campaignGoal": "Old goal", "campaignAssets": "/view?f=old.png"},
    "web-product": {"webBrief": "Old web", "webRefs": "/view?f=old.png"},
    "mobile-ui": {"appBrief": "Old app", "uiRefs": "/view?f=old.png"},
    "social": {"productRef": "/view?f=old.png", "personRef": "/view?f=old.png"},
    "motion": {"stillArt": "/view?f=old.png", "motionNotes": "Old motion", "visual": "old"},
}
