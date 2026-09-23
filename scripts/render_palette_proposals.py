#!/usr/bin/env python3
"""Render comparable, non-Figma UI palette proposal boards from declared role colors."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


ROLES = ("background", "card", "number", "icon", "button", "tab")
DISPLAY_LABELS = {"background": "BG", "card": "CARD", "number": "NUMBER",
                  "icon": "ICON", "button": "BUTTON", "tab": "TAB"}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _rgb(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError(f"expected #RRGGBB, got {value!r}")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _text(draw, xy, value, fill, font):
    draw.text(xy, str(value), fill=fill, font=font)


def _luminance(rgb):
    linear = [v / 255 / 12.92 if v / 255 <= .04045
              else ((v / 255 + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def _text_color(rgb):
    luminance = _luminance(rgb)
    dark = (30, 20, 34)
    light = (255, 250, 255)
    dark_luminance = _luminance(dark)
    light_luminance = _luminance(light)
    dark_contrast = (luminance + .05) / (dark_luminance + .05)
    light_contrast = (light_luminance + .05) / (luminance + .05)
    return dark if dark_contrast > light_contrast else light


def _button_text_color(scheme):
    if "buttonTextColor" in scheme:
        return _rgb(scheme["buttonTextColor"])
    if scheme.get("buttonVariant") == "gold-bright":
        return (82, 48, 27)
    if scheme.get("buttonTextPriority") == "vivid-contrast-white":
        return (255, 255, 255)
    # Other buttons need a contextual decision. This is only a provisional
    # preview fallback; the real host and material are reviewed later.
    return _text_color(_rgb(scheme["colors"]["button"]))


def _mix(a, b, weight):
    return tuple(round(x * (1 - weight) + y * weight) for x, y in zip(a, b))


def _panel(draw, origin, scheme, font, small_font):
    ox, oy = origin
    colors = scheme["colors"]
    rgb = {role: _rgb(colors[role]) for role in ROLES}
    background_text = _text_color(rgb["background"])
    card_text = _text_color(rgb["card"])
    draw.rounded_rectangle((ox, oy, ox + 404, oy + 350), radius=20,
                           fill=rgb["background"])
    _text(draw, (ox + 20, oy + 15), scheme["id"], background_text, font)
    strategy = scheme.get("buttonVariant", scheme.get("hueStrategy"))
    label = f'{scheme["targetUiMode"]} / {strategy}'
    _text(draw, (ox + 105, oy + 18), label, background_text, small_font)

    card = (ox + 18, oy + 55, ox + 386, oy + 250)
    draw.rounded_rectangle(card, radius=16, fill=rgb["card"])
    _text(draw, (ox + 38, oy + 75), "CARD", card_text, small_font)
    _text(draw, (ox + 38, oy + 105), "12,680", rgb["number"], font)

    icon_base = _mix(rgb["card"], rgb["icon"], .16)
    icon_edge = _mix(rgb["card"], rgb["icon"], .30)
    draw.ellipse((ox + 318, oy + 78, ox + 354, oy + 114),
                 fill=icon_base, outline=icon_edge, width=1)
    draw.ellipse((ox + 328, oy + 88, ox + 344, oy + 104), fill=rgb["icon"])

    draw.rounded_rectangle((ox + 38, oy + 145, ox + 170, oy + 184), radius=18,
                           fill=rgb["tab"])
    _text(draw, (ox + 86, oy + 157), "TAB", _text_color(rgb["tab"]), small_font)

    draw.rounded_rectangle((ox + 190, oy + 140, ox + 350, oy + 192), radius=18,
                           fill=rgb["button"])
    _text(draw, (ox + 246, oy + 157), "BUTTON", _button_text_color(scheme), small_font)

    for i, role in enumerate(ROLES):
        x = ox + 18 + i * 61
        draw.rounded_rectangle((x, oy + 272, x + 52, oy + 302), radius=6, fill=rgb[role])
        _text(draw, (x, oy + 309), DISPLAY_LABELS[role], background_text, small_font)
        _text(draw, (x, oy + 326), colors[role][1:].upper(), background_text, small_font)


def render_palette_proposals(data, output):
    from PIL import Image, ImageDraw, ImageFont
    if not isinstance(data, dict) or set(data) - {"title", "schemes"}:
        raise ValueError("input must contain only title? and schemes")
    schemes = data.get("schemes")
    if not isinstance(schemes, list) or not 1 <= len(schemes) <= 6:
        raise ValueError("schemes must contain 1 to 6 proposals")
    ids = []
    for scheme in schemes:
        required = {"id", "targetUiMode", "colors"}
        strategy_keys = {"hueStrategy", "buttonVariant"} & set(scheme)
        optional = {"hueStrategy", "buttonVariant", "buttonTextPriority", "buttonTextColor", "buttonTextEvidence"}
        if not required.issubset(scheme) or set(scheme) - (required | optional):
            raise ValueError("each scheme requires id, targetUiMode, colors and one strategy field")
        if len(strategy_keys) != 1:
            raise ValueError("each scheme requires exactly one of hueStrategy or buttonVariant")
        if scheme["targetUiMode"] not in {"light", "dark"}:
            raise ValueError("targetUiMode must be light or dark")
        if "hueStrategy" in scheme and scheme["hueStrategy"] not in {"analogous", "contrast", "complementary"}:
            raise ValueError("hueStrategy must be analogous or contrast (legacy complementary accepted)")
        if "buttonVariant" in scheme and scheme["buttonVariant"] not in {
                "metallic-analogous", "gold-bright", "clean-deep"}:
            raise ValueError("buttonVariant must be metallic-analogous, gold-bright or clean-deep")
        if scheme.get("buttonTextPriority") not in {None, "contextual", "vivid-contrast-white"}:
            raise ValueError("buttonTextPriority must be contextual or vivid-contrast-white")
        if (scheme.get("buttonTextPriority") == "vivid-contrast-white" and
                scheme.get("hueStrategy") not in {"contrast", "complementary"}):
            raise ValueError("vivid-contrast-white priority requires a vivid contrast scheme")
        if ("buttonTextColor" in scheme) != ("buttonTextEvidence" in scheme):
            raise ValueError("buttonTextColor override requires buttonTextEvidence")
        if "buttonTextColor" in scheme:
            _rgb(scheme["buttonTextColor"])
            if not isinstance(scheme["buttonTextEvidence"], str) or not scheme["buttonTextEvidence"].strip():
                raise ValueError("buttonTextEvidence must explain the text choice in its actual context")
        if not isinstance(scheme["id"], str) or not scheme["id"].strip():
            raise ValueError("scheme id required")
        if set(scheme["colors"]) != set(ROLES):
            raise ValueError("colors must contain exactly: " + ", ".join(ROLES))
        for value in scheme["colors"].values():
            _rgb(value)
        if scheme["targetUiMode"] == "dark" and _rgb(scheme["colors"]["number"]) != _rgb(scheme["colors"]["icon"]):
            raise ValueError("dark UI highlighted number and icon anchors must have identical RGB")
        ids.append(scheme["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate scheme id")

    columns = 2 if len(schemes) > 1 else 1
    rows = math.ceil(len(schemes) / columns)
    width, height = columns * 424 + 20, rows * 370 + 60
    image = Image.new("RGB", (width, height), (242, 242, 244))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    small_font = ImageFont.load_default(size=11)
    _text(draw, (20, 16), data.get("title", "UI Palette Proposals"), (30, 30, 34), font)
    for i, scheme in enumerate(schemes):
        _panel(draw, (20 + (i % columns) * 424, 48 + (i // columns) * 370),
               scheme, font, small_font)

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    manifest = {
        "inputSha256": hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "output": str(output), "pixels": [width, height], "schemeIds": ids,
        "buttonTextColors": {scheme["id"]: "#" + "".join(f"{v:02X}" for v in _button_text_color(scheme))
                             for scheme in schemes},
        "buttonTextPriorities": {scheme["id"]: scheme.get("buttonTextPriority", "contextual")
                                 for scheme in schemes},
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
