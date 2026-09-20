#!/usr/bin/env python3
"""Render comparable, non-Figma UI palette proposal boards from declared role colors."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


ROLES = (
    "page", "card", "container", "border", "textPrimary", "textSecondary",
    "titleAccent", "dataAccent", "tabSelected", "tabDefault",
    "iconGraphic", "iconContainer", "smallButton", "cta", "buttonText",
)
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _rgb(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError(f"expected #RRGGBB, got {value!r}")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _text(draw, xy, value, fill, font):
    draw.text(xy, str(value), fill=fill, font=font)


def _panel(draw, origin, scheme, font, small_font):
    ox, oy = origin
    colors = scheme["colors"]
    rgb = {role: _rgb(colors[role]) for role in ROLES}
    draw.rounded_rectangle((ox, oy, ox + 404, oy + 500), radius=20,
                           fill=rgb["page"], outline=rgb["border"], width=2)
    _text(draw, (ox + 20, oy + 15), scheme["id"], rgb["textPrimary"], font)
    label = f'{scheme["targetUiMode"]} / {scheme["hueStrategy"]}'
    _text(draw, (ox + 105, oy + 18), label, rgb["textSecondary"], small_font)

    card = (ox + 18, oy + 55, ox + 386, oy + 350)
    draw.rounded_rectangle(card, radius=16, fill=rgb["card"], outline=rgb["border"], width=2)
    _text(draw, (ox + 38, oy + 75), "TITLE", rgb["titleAccent"], font)
    _text(draw, (ox + 38, oy + 108), "Primary content", rgb["textPrimary"], small_font)
    _text(draw, (ox + 38, oy + 132), "Secondary information", rgb["textSecondary"], small_font)
    _text(draw, (ox + 290, oy + 101), "128", rgb["dataAccent"], font)

    draw.rounded_rectangle((ox + 38, oy + 165, ox + 170, oy + 202), radius=18,
                           fill=rgb["tabSelected"])
    draw.rounded_rectangle((ox + 180, oy + 165, ox + 312, oy + 202), radius=18,
                           fill=rgb["tabDefault"])
    _text(draw, (ox + 72, oy + 176), "Selected", rgb["textPrimary"], small_font)
    _text(draw, (ox + 215, oy + 176), "Default", rgb["textSecondary"], small_font)

    draw.rounded_rectangle((ox + 38, oy + 222, ox + 110, oy + 294), radius=18,
                           fill=rgb["iconContainer"])
    draw.ellipse((ox + 58, oy + 242, ox + 90, oy + 274), fill=rgb["iconGraphic"])
    draw.rounded_rectangle((ox + 132, oy + 232, ox + 254, oy + 284), radius=16,
                           fill=rgb["smallButton"])
    _text(draw, (ox + 164, oy + 249), "BUTTON", rgb["buttonText"], small_font)

    draw.rounded_rectangle((ox + 38, oy + 308, ox + 348, oy + 338), radius=12,
                           fill=rgb["container"])
    draw.rectangle((ox + 54, oy + 319, ox + 240, oy + 325), fill=rgb["textSecondary"])

    draw.rounded_rectangle((ox + 18, oy + 370, ox + 386, oy + 430), radius=24,
                           fill=rgb["cta"], outline=rgb["border"], width=1)
    _text(draw, (ox + 164, oy + 391), "CTA", rgb["buttonText"], font)

    chips = ("page", "card", "container", "smallButton", "cta", "dataAccent")
    for i, role in enumerate(chips):
        x = ox + 18 + i * 62
        draw.rectangle((x, oy + 450, x + 52, oy + 470), fill=rgb[role])
        _text(draw, (x, oy + 474), colors[role][1:].upper(), rgb["textPrimary"], small_font)


def render_palette_proposals(data, output):
    from PIL import Image, ImageDraw, ImageFont
    if not isinstance(data, dict) or set(data) - {"title", "schemes"}:
        raise ValueError("input must contain only title? and schemes")
    schemes = data.get("schemes")
    if not isinstance(schemes, list) or not 1 <= len(schemes) <= 4:
        raise ValueError("schemes must contain 1 to 4 proposals")
    ids = []
    for scheme in schemes:
        if set(scheme) != {"id", "targetUiMode", "hueStrategy", "colors"}:
            raise ValueError("each scheme requires id, targetUiMode, hueStrategy and colors")
        if scheme["targetUiMode"] not in {"light", "dark"}:
            raise ValueError("targetUiMode must be light or dark")
        if scheme["hueStrategy"] not in {"analogous", "complementary"}:
            raise ValueError("hueStrategy must be analogous or complementary")
        if not isinstance(scheme["id"], str) or not scheme["id"].strip():
            raise ValueError("scheme id required")
        if set(scheme["colors"]) != set(ROLES):
            raise ValueError("colors must contain exactly: " + ", ".join(ROLES))
        for value in scheme["colors"].values():
            _rgb(value)
        ids.append(scheme["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate scheme id")

    columns = 2 if len(schemes) > 1 else 1
    rows = math.ceil(len(schemes) / columns)
    width, height = columns * 424 + 20, rows * 520 + 60
    image = Image.new("RGB", (width, height), (242, 242, 244))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    small_font = ImageFont.load_default(size=11)
    _text(draw, (20, 16), data.get("title", "UI Palette Proposals"), (30, 30, 34), font)
    for i, scheme in enumerate(schemes):
        _panel(draw, (20 + (i % columns) * 424, 48 + (i // columns) * 520),
               scheme, font, small_font)

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    manifest = {
        "inputSha256": hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "output": str(output), "pixels": [width, height], "schemeIds": ids,
        "note": "Communication preview only; not a Figma render or material-validation PASS.",
    }
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text())
    print(json.dumps(render_palette_proposals(data, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
