#!/usr/bin/env python3
"""Derive inspection views from one real, opaque screenshot (requires Pillow)."""
import argparse
import hashlib
import math
from pathlib import Path
from theme_audit import read_json, save_json


def render_views(source, output, blur_radius=3.0, thumbnail_width=240):
    from PIL import Image, ImageFilter, ImageOps
    if blur_radius <= 0 or thumbnail_width <= 0:
        raise ValueError("blur radius and thumbnail width must be positive")
    source, output = Path(source).resolve(), Path(output).resolve()
    with Image.open(source) as original:
        im = ImageOps.exif_transpose(original).convert("RGBA")
        if im.getchannel("A").getextrema() != (255, 255):
            raise ValueError("Use a screenshot with its real host background; do not flatten transparency onto invented white")
        rgb = im.convert("RGB")
    output.mkdir(parents=True, exist_ok=True)
    views = {"color": rgb, "grayscale": ImageOps.grayscale(rgb),
             "blur": rgb.filter(ImageFilter.GaussianBlur(blur_radius))}
    thumbnail = rgb.copy()
    scale = min(1, thumbnail_width / rgb.width)
    thumbnail.thumbnail((max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))))
    views["thumbnail"] = thumbnail
    targets = {name: output / (name + ".png") for name in views}
    if source in targets.values():
        raise ValueError("output would overwrite source evidence")
    for name, view in views.items():
        view.save(targets[name])
    manifest = {"source": str(source), "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "sourcePixels": [rgb.width, rgb.height], "blurRadiusPixels": blur_radius,
                "views": {name: str(path) for name, path in targets.items()},
                "note": "Derived inspection views, not evidence of a new Figma render or automatic visual PASS."}
    save_json(output / "manifest.json", manifest)
    return manifest


def render_regions(source, output, regions, blur_radius=3.0, thumbnail_width=240):
    """Reuse real screenshot pixels; never resize or invent host context."""
    from PIL import Image, ImageOps
    source, output = Path(source).resolve(), Path(output).resolve()
    if not isinstance(regions, dict) or not regions:
        raise ValueError("nonempty named pixel regions required")
    boxes = {}
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGBA")
        if image.getchannel("A").getextrema() != (255, 255):
            raise ValueError("regions require real opaque host context")
        for name, rect in regions.items():
            if not isinstance(name, str) or not name or name in (".", "..") or "/" in name or "\\" in name:
                raise ValueError("region names must be safe directory names")
            if not isinstance(rect, list) or len(rect) != 4 or not all(type(n) in (int, float) and math.isfinite(n) for n in rect):
                raise ValueError("regions use finite pixel [x,y,width,height]")
            x, y, w, h = rect
            box = (math.floor(x), math.floor(y), math.ceil(x + w), math.ceil(y + h))
            if w <= 0 or h <= 0 or box[0] < 0 or box[1] < 0 or box[2] > image.width or box[3] > image.height:
                raise ValueError("region outside source screenshot")
            boxes[name] = box
        targets = {name: output / name / "context-source.png" for name in boxes}
        output_targets = {p.parent / (name + ".png") for p in targets.values()
                          for name in ("context-source", "color", "grayscale", "blur", "thumbnail")}
        if source in output_targets:
            raise ValueError("region output would overwrite source screenshot")
        manifests = {}
        for name, box in boxes.items():
            target = targets[name]; target.parent.mkdir(parents=True, exist_ok=True)
            image.crop(box).convert("RGB").save(target)
            manifest = render_views(target, target.parent, blur_radius, thumbnail_width)
            manifest.update({"originalSource": str(source),
                             "originalSourceSha256": source_hash,
                             "cropPixels": list(box)})
            save_json(target.parent / "manifest.json", manifest)
            manifests[name] = manifest
    return manifests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--blur-radius", type=float, default=3)
    parser.add_argument("--thumbnail-width", type=int, default=240)
    parser.add_argument("--regions", help="JSON object of named pixel [x,y,width,height] rectangles")
    args = parser.parse_args()
    if args.regions:
        render_regions(args.source, args.output, read_json(args.regions), args.blur_radius, args.thumbnail_width)
    else:
        render_views(args.source, args.output, args.blur_radius, args.thumbnail_width)
