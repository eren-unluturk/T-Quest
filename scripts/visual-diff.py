#!/usr/bin/env python
"""Compare two folders of same-named 390x844 PNG screenshots (before and after).

    python scripts/visual-diff.py .work/baseline .work/after [--nav-top 730]

Prints, per screen, the share of pixels that differ above the bottom navigation (rows < nav-top) and below it
(the nav region, where changes are expected), plus the bounding box of the differences above the nav.
Live data (map, trains, random fun fact) can move a few pixels; the point is that static chrome does not change.
Writes a side-by-side diff image per screen to <after>/diff-<name>.png (gitignored with .work/).
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops

args = [a for a in sys.argv[1:] if not a.startswith("--")]
nav_top = 730
if "--nav-top" in sys.argv:
    nav_top = int(sys.argv[sys.argv.index("--nav-top") + 1])
before, after = Path(args[0]), Path(args[1])
THRESH = 24

for b in sorted(before.glob("0*.png")):
    a = after / b.name
    if not a.exists():
        print(f"{b.name}: missing in after")
        continue
    ib, ia = Image.open(b).convert("RGB"), Image.open(a).convert("RGB")
    if ib.size != ia.size:
        print(f"{b.name}: size changed {ib.size} -> {ia.size}")
        continue
    diff = ImageChops.difference(ib, ia).convert("L").point(lambda v: 255 if v > THRESH else 0)
    w, h = diff.size
    top = diff.crop((0, 0, w, nav_top))
    nav = diff.crop((0, nav_top, w, h))
    pct = lambda im: 100.0 * sum(1 for v in im.getdata() if v) / (im.size[0] * im.size[1])
    bbox = top.getbbox()
    print(f"{b.name}: above nav {pct(top):5.2f}% differ, bbox {bbox}; nav region {pct(nav):5.2f}% differ")
    side = Image.new("RGB", (w * 3, h), "white")
    side.paste(ib, (0, 0)); side.paste(ia, (w, 0)); side.paste(diff.convert("RGB"), (w * 2, 0))
    side.save(after / f"diff-{b.stem}.png")
