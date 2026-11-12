#!/usr/bin/env python3
"""Check an exported pulley's bore is the SHAPE it was asked for.

Nothing else does. A D-shaft bore whose flat never got cut is watertight,
single-bodied, the right bounding box and the right volume to three figures --
every check the matrix runs passes, and the part is a plain round hole. That
bug shipped and was found by eye on a render.

The bore's extents give the shape away: a flat takes its depth off one of
them, and a hex is wider across corners than across flats by 2/sqrt(3).

Corner relief has to be allowed for or every cornered bore looks wrong. The
relief circles sit ON the corners, so each extent grows by one relief diameter
-- a square asked for 8.3 measures 8.9 at 0.6mm relief, and reading that as a
defect is how you end up "fixing" a part that was right.

    python3 tools/borecheck.py part.stl --expect d-shaft --size 6 --flat 0.5
"""
import argparse
import math
from pathlib import Path


import numpy as np


def bore_profile(path: Path):
    import trimesh
    from shapely.geometry import Point, Polygon

    mesh = trimesh.load(str(path), force="mesh")
    lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]

    # Scan up from the bottom rather than slicing at mid-height. On a long hub
    # the middle of the PART is inside the hub, where the clamp slot opens the
    # bore to the outside and it is no longer a closed ring -- the bore reads
    # as missing when it is simply not enclosed there. The toothed section
    # lower down always encloses it.
    z = lo + (hi - lo) * 0.02
    while z < hi:
        sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is not None:
            pl, _ = sec.to_2D()
            best = None
            for poly in pl.polygons_full:
                for ring in poly.interiors:
                    a = Polygon(ring).area
                    if best is None or a > best[1]:
                        best = (np.asarray(ring.coords)[:-1], a)
            if best is not None:
                return best[0]
        z += (hi - lo) * 0.04
    return None


def check(path: Path, kind: str, size: float, clearance: float, flat: float,
          relief: float = 0.0):
    c = bore_profile(path)
    if c is None:
        return False, "no bore found"
    w = c[:, 0].max() - c[:, 0].min()
    h = c[:, 1].max() - c[:, 1].min()
    fit = size + 2 * clearance
    tol = 0.12

    if kind in ("round", "bearing"):
        want = fit
        ok = abs(w - want) < tol and abs(h - want) < tol
        return ok, f"{w:.3f} x {h:.3f}, want {want:.3f} both ways"
    if kind == "d-shaft":
        got = max(w, h) - min(w, h)
        return abs(got - flat) < tol, f"flat {got:.3f}mm deep, want {flat:.3f}"
    if kind == "square":
        want = fit + relief
        ok = abs(w - want) < tol and abs(h - want) < tol
        return ok, f"{w:.3f} x {h:.3f}, want {want:.3f} both ways"
    if kind == "hex":
        # $fn=6 puts vertices on the X axis, so width is across CORNERS and
        # height across flats. Each grows by one relief diameter.
        ww, hh = fit / math.cos(math.radians(30)) + relief, fit + relief
        ok = abs(w - ww) < tol and abs(h - hh) < tol
        return ok, f"{w:.3f} x {h:.3f}, want {ww:.3f} x {hh:.3f}"
    if kind == "rex":
        # A hex clipped by a round. The relief is NOT on the hex vertices --
        # those sit outside the round, so it is clamped to the round radius,
        # which means it does not grow the extents by a full relief diameter
        # the way a plain hex does. Assuming it did reads 7.788 as a defect
        # when it is exactly right.
        round_r = (8.0 + 2 * clearance) / 2
        hex_r = (7.3 + 2 * clearance) / (2 * math.cos(math.radians(30)))
        rel_r = min(hex_r, round_r)
        ww = 2 * max(round_r, rel_r + relief / 2)
        hh = 2 * max((7.3 + 2 * clearance) / 2,
                     rel_r * math.sin(math.radians(60)) + relief / 2)
        ok = abs(w - ww) < tol and abs(h - hh) < tol
        return ok, f"{w:.3f} x {h:.3f}, want {ww:.3f} x {hh:.3f}"
    return False, f"unknown kind {kind}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stl", type=Path)
    ap.add_argument("--expect", required=True,
                    choices=["round", "d-shaft", "hex", "square", "rex",
                             "bearing"])
    ap.add_argument("--size", type=float, required=True)
    ap.add_argument("--clearance", type=float, default=0.15)
    ap.add_argument("--flat", type=float, default=0.5)
    ap.add_argument("--relief", type=float, default=0.0,
                    help="corner_relief the part was built with")
    a = ap.parse_args()
    ok, msg = check(a.stl, a.expect, a.size, a.clearance, a.flat, a.relief)
    print(f"{'OK  ' if ok else 'FAIL'}  {a.stl.name} [{a.expect}]: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
