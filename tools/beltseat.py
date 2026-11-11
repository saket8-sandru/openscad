#!/usr/bin/env python3
"""Measure the usable belt seat on an exported pulley.

`belt_width` claims to be what the belt gets. This checks it against the mesh
rather than the arithmetic that produced it.

A belt rides with its teeth in the grooves and its BACK on the tooth-tip
circle, so what limits it is not groove depth -- the tooth cutter runs the
full channel and grooves the chamfers too -- but anything standing proud of
the tip circle. A flange chamfer does exactly that, tapering from the flange
diameter down to the tips, so over its run the belt's back has nowhere to go.

So: slice the solid at a series of heights and ask how far out the material
reaches. The belt seat is the unbroken run of heights where nothing stands
outside the tooth tips.

    python3 tools/beltseat.py <pulley.stl> --tip-dia 12.224 --expect 6.5
"""
import argparse
from pathlib import Path


def measure(stl: Path, tip_dia: float, step: float = 0.05):
    import numpy as np
    import trimesh

    mesh = trimesh.load(str(stl), force="mesh")
    z0, z1 = mesh.bounds[0][2], mesh.bounds[1][2]
    tip_r = tip_dia / 2
    # Slop, so the answer measures the chamfer and not the facets the tip
    # circle is drawn with. At $fn=96 a 12mm tip circle is faceted by about
    # 0.003mm, so 0.02 clears that with room and still resolves the chamfer:
    # at 0.10 the seat read 0.2mm wide, one tol at each end.
    tol = 0.02

    seat_z = []
    z = z0 + step
    while z < z1:
        try:
            sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        except Exception:
            sec = None
        if sec is not None:
            pts = np.asarray(sec.vertices)
            rad = np.hypot(pts[:, 0], pts[:, 1])
            if rad.size and rad.max() <= tip_r + tol:
                seat_z.append(z)
        z += step

    if not seat_z:
        return None
    # longest unbroken run, so a stray slice cannot inflate the answer
    best = run = 1
    lo = best_lo = seat_z[0]
    for a, b in zip(seat_z, seat_z[1:]):
        if b - a < step * 1.5:
            run += 1
        else:
            run, lo = 1, b
        if run > best:
            best, best_lo = run, lo
    return best_lo, best_lo + (best - 1) * step


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stl", type=Path)
    ap.add_argument("--tip-dia", type=float, required=True)
    ap.add_argument("--expect", type=float, default=None,
                    help="belt seat the generator claims, in mm")
    a = ap.parse_args()

    got = measure(a.stl, a.tip_dia)
    if got is None:
        print("no clear belt seat at all -- something stands proud everywhere")
        return 1
    lo, hi = got
    width = hi - lo
    print(f"{a.stl.name}")
    print(f"  clear belt seat: z {lo:.2f} .. {hi:.2f}   = {width:.2f} mm")
    if a.expect is not None:
        err = width - a.expect
        verdict = "OK" if abs(err) <= 0.15 else "** SHORT **" if err < 0 else "over"
        print(f"  claimed belt seat: {a.expect:.2f} mm   difference {err:+.2f} mm   {verdict}")
        return 0 if abs(err) <= 0.15 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
