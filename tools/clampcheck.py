#!/usr/bin/env python3
"""Check a pulley's clamp seats are fully enclosed in the hub.

The nut pocket only holds a nut from turning if its corners are there. If the
hub is shorter than the lug the seats are cut into, the pocket's top and bottom
vertices cut straight out through the hub's faces -- the mesh stays watertight
and single-bodied, so nothing else notices, and the nut spins.

Tested by slicing across the screw and asking whether the pocket is still a
CLOSED loop. A pocket that has burst out of the hub is no longer a loop: it is
part of the outside.

The slices are SEARCHED for rather than taken at the part's end face. On a big
pulley the widest thing is the flange, not the hub -- slicing at the part's own
extreme cuts through teeth 19mm away from the pocket and finds nothing, which
reads identically to a broken pocket.

    python3 tools/clampcheck.py <pulley.stl> --flats 7.3
"""
import argparse
from pathlib import Path


def seg_dist(p, a, b):
    import numpy as np
    ab = b - a
    t = np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0, 1)
    return float(np.linalg.norm(p - (a + t * ab)))


def rings_at(mesh, x):
    import numpy as np
    from shapely.geometry import Polygon
    sec = mesh.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
    if sec is None:
        return []
    pl, _ = sec.to_2D()
    out = []
    for poly in pl.polygons_full:
        for ring in poly.interiors:
            out.append(np.asarray(ring.coords))
    return out


def check(path: Path, flats: float, depth: float = 1.0, tol: float = 0.08):
    import numpy as np
    import trimesh

    mesh = trimesh.load(str(path), force="mesh")
    x0 = mesh.bounds[0][0]

    best = None
    rings = []
    x = x0 + depth
    while x < -0.5 and best is None:
        rings = rings_at(mesh, x)
        best = scan(rings, flats)
        x += 0.5
    if best is None:
        return False, ("no closed hexagonal pocket at any depth -- "
                       "it has broken out of the hub")
    got, n = best
    if abs(got - flats) > tol:
        return False, f"pocket is {got:.3f}mm across flats, wanted {flats:.3f}"
    return True, f"closed hexagon, {got:.3f}mm across flats, {n} corners"


def scan(rings, flats):
    import numpy as np
    best = None
    for ring in rings:
        c = ring[:-1] if np.allclose(ring[0], ring[-1]) else ring
        ctr = c.mean(axis=0)
        d = np.hypot(*(c - ctr).T)
        if d.max() < 1e-6:
            continue
        # The loop's VERTICES are the hexagon's corners, all at one radius --
        # there is no vertex on a flat, so across-flats has to come from the
        # EDGES. Measuring it from vertices makes every polygon look like a
        # circle and finds nothing.
        e = np.vstack([c, c[:1]])
        flats_r = min(seg_dist(ctr, e[i], e[i + 1]) for i in range(len(c)))
        if flats_r < 1e-6:
            continue
        # Corner radius against flat radius. NOT the mean radius: triangulation
        # drops extra vertices along each edge, so a hexagon comes back with 12
        # points or more and its mean radius sits between the two. The corners
        # are the maximum, and the flats come from the edges.
        if abs(d.max() / flats_r - 2 / np.sqrt(3)) < 0.03:
            best = (2 * flats_r, len(c))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stl", type=Path)
    ap.add_argument("--flats", type=float, required=True,
                    help="expected across-flats of the nut pocket, in mm")
    ap.add_argument("--depth", type=float, default=1.0,
                    help="how far inside the end face to slice")
    a = ap.parse_args()
    ok, msg = check(a.stl, a.flats, a.depth)
    print(f"{'OK  ' if ok else 'FAIL'}  {a.stl.name}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
