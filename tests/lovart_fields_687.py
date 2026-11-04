"""#687 — hard-coded Lovart dialog field spec (source: docs/qa/687-audit/README.md @6fdfd01c + gold dialog_fields.txt).
Shared by the unit test (tests/test_skill_fields_687.py) and the e2e (tests/test_e2e_skill_fields_687.py).
Row = (key, type, required, accept, maxLength, zh label, en label, en placeholder)."""
UP = ("file", "image", False, "image", None, "上传文件", "Upload Files", None)
NOTE500 = ("note", "textarea", False, None, 500, "补充描述", "Additional Details", "Anything else to add?")
NOTE_EFFECT = ("note", "textarea", False, None, None, "补充描述", "Additional Details", "Anything else to add?")
LOVART_2 = [UP, NOTE500]
MOTION_REMAKE = [
    ("refVideo", "image", True, "video", None, "参考视频", "Reference video file", None),
    ("remakeBrief", "textarea", True, None, 200, "重制说明", "Remake brief",
     "What should change or stay? Combine product, person, brand, copy or other requested changes."),
    ("replaceImages", "image", False, "image", None, "替换图", "Replacement images", None),
    ("visualDirection", "textarea", False, None, 200, "视觉方向", "Visual direction",
     "Describe your preferred visual treatment or provide a reference. Leave blank if you have no preference."),
]
VISUAL = ("visual", "text", False, None, None, "视觉呈现方式", "Visual presentation", "Visual preferences to keep or avoid; leave blank if none")
SPEC = {
    **{sid: LOVART_2 for sid in ["brand", "packaging", "character", "logo-material", "meta-ads", "marketing-campaign",
                                 "web-product", "mobile-ui", "social"]},
    **{sid: [UP, NOTE_EFFECT] for sid in ["poster", "banner", "interior"]},
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
MOTION_FEATURED_REMOVED = "580/featured-v1/motion/03.webp"
