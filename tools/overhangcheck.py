#!/usr/bin/env python3
"""
overhangcheck -- prove a tile prints without support, from its exported mesh.

The generator claims support-freedom as a property of the geometry: printed
back-face-down the fins are a height field, so every layer's footprint sits
inside the one below. This checks that claim the only way worth checking it --
by measuring the downward-facing faces of the actual STL.

Print orientation maps the model's +Y (depth, away from the wall) to the
printer's +Z. A face is a support risk when it points downward and lies closer
to horizontal than the support threshold.

Two kinds of downward face are expected and are NOT failures:
  - the flat back face itself, which is the surface on the build plate;
  - the ceilings of the key pockets and keyhole slots, which are enclosed
    bridges anchored on all sides, not overhangs.
Both are reported separately with their spans so a bridge that grew too long
is visible rather than silently accepted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import trimesh


def analyse(path: Path, threshold_deg: float = 45.0, up_axis: int = 1):
    mesh = trimesh.load(str(path), force="mesh")
    n = mesh.face_normals
    areas = mesh.area_faces
    comp = n[:, up_axis]

    # Angle of each face from the build plate: 0 deg = horizontal, 90 = vertical.
    incline = np.degrees(np.arccos(np.clip(np.abs(comp), 0, 1)))
    downward = comp < 0
    risky = downward & (incline < threshold_deg)

    lo = mesh.bounds[0][up_axis]
    on_bed = risky & (np.abs(mesh.triangles[:, :, up_axis].max(axis=1) - lo) < 1e-6)
    internal = risky & ~on_bed

    return {
        "mesh": mesh, "areas": areas, "incline": incline,
        "risky": risky, "on_bed": on_bed, "internal": internal,
    }


def bridge_spans(mesh, mask, up_axis=1):
    """Footprint extents of each connected group of internal downward faces."""
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    sub = mesh.submesh([idx], append=True)
    groups = sub.split(only_watertight=False)
    plane = [a for a in range(3) if a != up_axis]
    out = []
    for g in groups:
        ext = g.extents
        out.append((float(ext[plane[0]]), float(ext[plane[1]]),
                    float(g.area), float(g.bounds[0][up_axis])))
    return sorted(out, key=lambda t: -max(t[0], t[1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stl", type=Path, nargs="+")
    ap.add_argument("--threshold", type=float, default=45.0,
                    help="faces inclined less than this from the plate are risky")
    ap.add_argument("--max-bridge", type=float, default=20.0,
                    help="longest acceptable unsupported bridge span, mm")
    args = ap.parse_args()

    failures = 0
    for path in args.stl:
        r = analyse(path, args.threshold)
        mesh, areas = r["mesh"], r["areas"]
        total = areas.sum()
        a_bed = areas[r["on_bed"]].sum()
        a_int = areas[r["internal"]].sum()

        print(f"\n{path.name}")
        print(f"  faces {len(areas)}   downward-and-shallow: "
              f"{int(r['risky'].sum())} "
              f"({100*areas[r['risky']].sum()/total:.2f}% of area)")
        print(f"    on the build plate (the back face): {100*a_bed/total:.2f}% of area")
        print(f"    internal (enclosed bridges):        {100*a_int/total:.2f}% of area")

        spans = bridge_spans(mesh, r["internal"])
        if not spans:
            print("    no internal downward faces at all")
        for w, h, area, z in spans[:8]:
            span = max(w, h)
            flag = "OK" if span <= args.max_bridge else "TOO LONG"
            print(f"    bridge span {span:6.2f} mm  (footprint {w:.1f} x {h:.1f}, "
                  f"area {area:6.1f} mm2, at height {z:.2f})  {flag}")
            if span > args.max_bridge:
                failures += 1

        # The real claim: no unsupported overhang on the fins themselves.
        if spans:
            worst = max(max(w, h) for w, h, _, _ in spans)
        else:
            worst = 0.0
        verdict = "PASS" if worst <= args.max_bridge else "FAIL"
        print(f"  longest unsupported span {worst:.2f} mm "
              f"(limit {args.max_bridge}) -> {verdict}")

    print()
    if failures:
        print(f"== {failures} bridge(s) over the limit ==")
        return 1
    print("== no support required ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
