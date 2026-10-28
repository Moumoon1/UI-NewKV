#!/usr/bin/env python3
"""Fast Pillow-only color evidence for a rendered KV preview.

The output locates color and bottom-edge candidates. Visual classification of
environment, foreground, and material still belongs to the theme workflow.
"""

import argparse
import json
import math
from pathlib import Path

from PIL import Image


def _hex(rgb):
    return "#" + "".join(f"{int(value):02X}" for value in rgb)


def _quantized_colors(image, colors=12, limit=8):
    quantized = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    total = image.width * image.height
    result = []
    for count, index in sorted(quantized.getcolors(), reverse=True)[:limit]:
        rgb = tuple(palette[index * 3:index * 3 + 3])
        result.append({"hex": _hex(rgb), "ratio": round(count / total, 4)})
    return result


def _channel_median(values, channel):
    ordered = sorted(value[channel] for value in values)
    return ordered[len(ordered) // 2]


def _row_stats(image, y, tolerance):
    pixels = [image.getpixel((x, y))[:3] for x in range(image.width)]
    median = tuple(_channel_median(pixels, channel) for channel in range(3))
    means = tuple(sum(pixel[channel] for pixel in pixels) / image.width for channel in range(3))
    stddev = tuple(
        math.sqrt(sum((pixel[channel] - means[channel]) ** 2 for pixel in pixels) / image.width)
        for channel in range(3)
    )
    near = sum(
        math.sqrt(sum((pixel[channel] - median[channel]) ** 2 for channel in range(3))) <= tolerance
        for pixel in pixels
    ) / image.width
    return {
        "y": y,
        "median": _hex(median),
        "mean": _hex(tuple(round(value) for value in means)),
        "nearMedianCoverage": round(near, 4),
        "channelStdDev": [round(value, 3) for value in stddev],
    }


def analyze(path, tolerance=20):
    image = Image.open(path).convert("RGB")
    width, height = image.size
    bottom_height = max(4, min(24, round(height * 0.02)))
    top_height = max(1, round(height / 3))
    bottom = image.crop((0, height - bottom_height, width, height))
    rows = [_row_stats(image, y, tolerance) for y in range(height - bottom_height, height)]
    stable_rows = [row for row in rows if row["nearMedianCoverage"] >= 0.9]
    return {
        "schemaVersion": 1,
        "image": str(Path(path).resolve()),
        "size": [width, height],
        "parameters": {
            "bottomBandHeight": bottom_height,
            "rgbDistanceTolerance": tolerance,
            "stableCoverageReference": 0.9,
        },
        "quantizedCandidates": {
            "full": _quantized_colors(image),
            "upperThird": _quantized_colors(image.crop((0, 0, width, top_height))),
            "bottomBand": _quantized_colors(bottom),
        },
        "bottomBand": {
            "rows": rows,
            "stableRowRatio": round(len(stable_rows) / len(rows), 4),
            "allRowsMeetReference": len(stable_rows) == len(rows),
        },
        "note": "Statistics locate candidates only; visual classification remains required.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--out")
    parser.add_argument("--tolerance", type=float, default=20)
    args = parser.parse_args()
    result = analyze(args.image, args.tolerance)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        output = Path(args.out).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
