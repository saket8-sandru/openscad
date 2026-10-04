#!/usr/bin/env python3
"""
ribcheck -- measure the webs of a perforated plate from its exported mesh.

A vent or lightening pattern promises three numbers: no web between two holes
thinner than the rib, no hole closer to the edge than the border, and no hole
too small to be worth cutting. This sections the STL just under its top face
and measures all three on the real geometry, rather than trusting the maths
that was supposed to produce them.

    ribcheck.py part.stl [--rib 2.0] [--border 5] [--min-hole 4]
    ribcheck.py projects/<name>/validation.json

The second form reads the matrix the way scadkit does and checks every case
that carries a "ribcheck" block, against the STL the matrix already exported:

    { "name": "default", "params": {...}, "expect": {...},
      "ribcheck": { "rib": 2.0, "border": 5.0, "min_hole": 4.0 } }

Run `scadkit.py matrix` first; this does not render anything.

Tolerance is 2e-3 mm, and it is the file format's, not the model's. OpenSCAD
writes ASCII STL to six significant digits, so a vertex past 100mm from the
origin is only good to 0.0005mm per axis, and a gap between two of them to
about 0.0014mm. Measured: a 2mm rib reads 1.99991 on a 120mm panel, whose
coordinates all stay under 100, and a 0.8mm rib reads 0.79901 on a 250mm
panel, whose coordinates do not -- a tenfold jump, as the digit count
predicts. The geometry itself
is built on a fixed-point grid far finer than that, and its rounded corners
are chords inside the true arc, which can only make a web thicker.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

TOL = 2e-3


@dataclass
class WebReport:
    holes: int
    min_rib: float           # inf when fewer than two holes
    min_border: float        # inf when no holes
    min_hole: float          # smallest hole's inscribed-circle diameter
    max_hole: float          # largest hole's -- what a finger or a screw fits through
    open_pct: float          # hole area / outline area, at the section

    def row(self) -> str:
        def f(v):
            return "  --  " if v in (float("inf"), 0.0) else f"{v:6.3f}"
        return (f"holes={self.holes:<4d} rib={f(self.min_rib)} "
                f"border={f(self.min_border)} smallest={f(self.min_hole)} "
                f"largest={f(self.max_hole)} open={self.open_pct:5.1f}%")


def section_loops(stl: Path, depth: float = 0.1):
    """Closed loops of the cross-section `depth` below the top face, as
    shapely polygons, largest first. No nesting is worked out -- trimesh
    needs rtree for that, and a perforated plate has only one level of it."""
    import numpy as np
    import shapely
    import trimesh

    mesh = trimesh.load(str(stl), force="mesh")
    z = float(mesh.bounds[1][2]) - depth
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        raise RuntimeError(f"{stl}: nothing at z={z:.3f}")
    # Identity transform keeps section coordinates equal to model XY.
    planar, _ = sec.to_2D(to_2D=np.eye(4))
    loops = [shapely.Polygon(d) for d in planar.discrete if len(d) >= 3]
    return sorted(loops, key=lambda p: -p.area)


def measure(stl: Path) -> WebReport:
    import shapely
    from shapely.strtree import STRtree

    loops = section_loops(stl)
    if not loops:
        raise RuntimeError(f"{stl}: empty section")
    plate, holes = loops[0], loops[1:]
    stray = [h for h in holes if not plate.contains(h)]
    if stray:
        raise RuntimeError(f"{stl}: {len(stray)} loops outside the outline -- "
                           "more than one body, or not a perforated plate")
    outer = plate.exterior

    if not holes:
        return WebReport(0, float("inf"), float("inf"), float("inf"), 0.0, 0.0)

    # Nearest other hole for each hole. A web is the gap between two holes, so
    # the thinnest one is the smallest of these.
    tree = STRtree(holes)
    min_rib = float("inf")
    for i, h in enumerate(holes):
        for j in tree.query(h, predicate="dwithin", distance=50.0):
            if j != i:
                min_rib = min(min_rib, h.distance(holes[j]))

    min_border = min(h.distance(outer) for h in holes)
    # maximum_inscribed_circle returns the radius as a line from the centre.
    widths = [2 * shapely.maximum_inscribed_circle(h, tolerance=0.01).length
              for h in holes]

    hole_area = sum(h.area for h in holes)
    open_pct = 100.0 * hole_area / plate.area
    return WebReport(len(holes), min_rib, min_border, min(widths), max(widths), open_pct)


def judge(rep: WebReport, rib: float | None, border: float | None,
          min_hole: float | None) -> list[str]:
    fails = []
    if rib is not None and rep.min_rib < rib - TOL:
        fails.append(f"rib {rep.min_rib:.4f} under {rib}")
    if border is not None and rep.min_border < border - TOL:
        fails.append(f"border {rep.min_border:.4f} under {border}")
    # The inscribed circle is found to within its own 0.01 tolerance.
    if min_hole is not None and rep.holes and rep.min_hole < min_hole - 0.02:
        fails.append(f"a hole only {rep.min_hole:.3f} wide survived (min {min_hole})")
    return fails


def run_spec(spec_path: Path) -> int:
    spec = json.loads(spec_path.read_text())
    outdir = spec_path.parent / spec.get("outdir", "exports")
    cases = [c for c in spec["cases"] if "ribcheck" in c]
    print(f"== ribcheck {spec.get('name', '')} :: {len(cases)} cases ==")
    failures = 0
    for case in cases:
        stl = outdir / f"{case['name']}.stl"
        label = f"  {case['name']:<28}"
        if not stl.exists():
            print(f"{label} FAIL  {stl.name} missing -- run scadkit matrix first")
            failures += 1
            continue
        want = case["ribcheck"]
        try:
            rep = measure(stl)
        except RuntimeError as exc:
            print(f"{label} FAIL  {exc}")
            failures += 1
            continue
        fails = judge(rep, want.get("rib"), want.get("border"), want.get("min_hole"))
        if "min_holes" in want and rep.holes < want["min_holes"]:
            fails.append(f"only {rep.holes} holes, expected at least {want['min_holes']}")
        if "max_hole" in want and rep.max_hole > want["max_hole"] + 0.02:
            fails.append(f"a hole {rep.max_hole:.3f} wide, over {want['max_hole']}")
        print(f"{label} {'FAIL' if fails else 'PASS'}  {rep.row()}")
        for f in fails:
            print(f"        - {f}")
        failures += bool(fails)
    print(f"== {len(cases) - failures}/{len(cases)} passed ==")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", type=Path, help="an .stl, or a validation.json")
    ap.add_argument("--rib", type=float)
    ap.add_argument("--border", type=float)
    ap.add_argument("--min-hole", type=float)
    args = ap.parse_args()

    if args.target.suffix == ".json":
        return run_spec(args.target)

    rep = measure(args.target)
    print(f"{args.target}: {rep.row()}")
    fails = judge(rep, args.rib, args.border, args.min_hole)
    for f in fails:
        print(f"  - {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
