#!/usr/bin/env python3
"""
seamcheck -- prove that tiles of one artwork actually join.

The generator's central claim is that a large artwork can be cut into printable
tiles without breaking the surface: the field is evaluated in global artwork
coordinates, normalised against a global range, and fins are pitched globally
so a tile edge lands in the middle of a gap rather than through a fin.

That is a claim about exported geometry, so it is checked against exported
geometry -- not against the source that makes the claim.

Checks, for a multi-tile artwork:
  1. every tile occupies exactly its own cell, to within a tolerance
  2. tiles do not overlap, and leave no gap between backings
  3. the fin gap straddling a seam equals a normal interior fin gap, so the
     seam is not visible as a wider or narrower slot
  4. the assembled artwork's volume equals the sum of its tiles
"""

from __future__ import annotations

import argparse
import itertools
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scadkit import render


def echo_values(scad: Path, overrides: dict) -> dict:
    """Pull the generator's derived values straight out of its own echo line."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "e.echo"
        cmd = ["openscad", "-o", str(out), "--export-format", "echo"]
        for k, v in overrides.items():
            cmd += ["-D", f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"]
        cmd.append(str(scad))
        subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        text = out.read_text() if out.exists() else ""
    m = re.search(r"tiles (\d+)x(\d+) @ ([\d.]+)x([\d.]+)\s+fins (\d+) pitch ([\d.]+)"
                  r" thickness ([\d.]+) gap ([\d.]+)", text)
    if not m:
        raise RuntimeError("could not parse the generator's LAMELLA echo line")
    return {"cols": int(m.group(1)), "rows": int(m.group(2)),
            "tile_w": float(m.group(3)), "tile_h": float(m.group(4)),
            "fins": int(m.group(5)), "pitch": float(m.group(6)),
            "thickness": float(m.group(7)), "gap": float(m.group(8))}


def fin_edges_near(mesh: trimesh.Trimesh, x_lo: float, x_hi: float) -> np.ndarray:
    """X coordinates of vertices lying in a window, sorted and de-duplicated."""
    v = mesh.vertices[:, 0]
    sel = v[(v >= x_lo) & (v <= x_hi)]
    return np.unique(np.round(sel, 4))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scad", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "projects/waveform-wall/src/waveform_wall.scad")
    ap.add_argument("--width", type=float, default=330.0)
    ap.add_argument("--height", type=float, default=170.0)
    ap.add_argument("--style", default="Flow")
    ap.add_argument("--tol", type=float, default=0.02)
    args = ap.parse_args()

    base = {"artwork_width": args.width, "artwork_height": args.height,
            "style": args.style}
    info = echo_values(args.scad, base)
    print(f"artwork {args.width}x{args.height}  tiles {info['cols']}x{info['rows']}"
          f"  tile {info['tile_w']:.2f}x{info['tile_h']:.2f}")
    print(f"fins {info['fins']}  pitch {info['pitch']:.4f}"
          f"  thickness {info['thickness']:.4f}  gap {info['gap']:.4f}")
    if info["cols"] < 2:
        print("FAIL: need at least two tile columns to test a seam")
        return 1

    failures = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        meshes = {}
        for c, r in itertools.product(range(info["cols"]), range(info["rows"])):
            stl = td / f"t{c}{r}.stl"
            render(args.scad, stl, {**base, "output": "Single tile",
                                    "tile_col": c + 1, "tile_row": r + 1})
            meshes[(c, r)] = trimesh.load(str(stl), force="mesh")

        # 1 + 2: each tile occupies exactly its own cell
        print("\n-- tile placement")
        for (c, r), m in sorted(meshes.items()):
            lo, hi = m.bounds[0], m.bounds[1]
            want_x0, want_x1 = c * info["tile_w"], (c + 1) * info["tile_w"]
            want_z0, want_z1 = r * info["tile_h"], (r + 1) * info["tile_h"]
            dx0, dx1 = abs(lo[0] - want_x0), abs(hi[0] - want_x1)
            dz0, dz1 = abs(lo[2] - want_z0), abs(hi[2] - want_z1)
            ok = max(dx0, dx1, dz0, dz1) <= args.tol
            print(f"   tile({c},{r}) x=[{lo[0]:8.3f},{hi[0]:8.3f}] "
                  f"z=[{lo[2]:8.3f},{hi[2]:8.3f}]  err={max(dx0,dx1,dz0,dz1):.4f}  "
                  f"{'ok' if ok else 'FAIL'}")
            if not ok:
                failures.append(f"tile({c},{r}) misplaced")

        # 3: the seam gap must equal an ordinary fin gap
        print("\n-- seam gap vs interior gap")
        for c in range(info["cols"] - 1):
            seam = (c + 1) * info["tile_w"]
            left = meshes[(c, 0)]
            right = meshes[(c + 1, 0)]
            # last fin face left of the seam, first fin face right of it
            lx = fin_edges_near(left, seam - info["pitch"], seam)
            rx = fin_edges_near(right, seam, seam + info["pitch"])
            if len(lx) == 0 or len(rx) == 0:
                failures.append(f"seam {c}: no geometry found near the seam")
                continue
            # backings run to the seam exactly; the fin faces sit back from it
            fin_left = lx[lx < seam - 1e-6].max() if (lx < seam - 1e-6).any() else None
            fin_right = rx[rx > seam + 1e-6].min() if (rx > seam + 1e-6).any() else None
            if fin_left is None or fin_right is None:
                failures.append(f"seam {c}: could not locate fin faces")
                continue
            measured = fin_right - fin_left
            err = abs(measured - info["gap"])
            ok = err <= args.tol
            print(f"   seam x={seam:8.3f}  fin faces {fin_left:.3f} .. {fin_right:.3f}"
                  f"  gap={measured:.4f} (interior {info['gap']:.4f})"
                  f"  err={err:.4f}  {'ok' if ok else 'FAIL'}")
            if not ok:
                failures.append(f"seam {c} gap {measured:.4f} != {info['gap']:.4f}")

        # 4: assembled volume equals the sum of the tiles
        print("\n-- assembled vs sum of tiles")
        asm = td / "asm.stl"
        render(args.scad, asm, {**base, "output": "Assembled preview"})
        a = trimesh.load(str(asm), force="mesh")
        total = sum(abs(m.volume) for m in meshes.values())
        rel = abs(abs(a.volume) - total) / max(total, 1e-9)
        ok = rel < 1e-6
        print(f"   assembled {abs(a.volume)/1000:.3f} cm3   "
              f"sum of tiles {total/1000:.3f} cm3   rel.diff {rel:.2e}  "
              f"{'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append("assembled volume != sum of tiles")
        print(f"   assembled bbox {np.round(a.extents, 3)}")

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("== all seam checks passed ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
