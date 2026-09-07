#!/usr/bin/env python3
"""Measure a plaque STL and print the parameter block to paste into the .scad.

OpenSCAD 2021.01 cannot measure an imported mesh -- there is no way to ask a
solid how big it is -- so `plaque_text_on_base.scad` has to be TOLD the
plaque's size, where its top face sits, and where its origin is. Four numbers,
each of which renders as "broken" when wrong, and none of which announces
which one is wrong.

Nothing about that is hard, it is just not something OpenSCAD can do. This
reads the file directly and prints the answers.

    python3 tools/plaquefit.py ~/Downloads/Base.stl
"""
import sys
from pathlib import Path


def describe(path: Path) -> int:
    import numpy as np
    import trimesh

    mesh = trimesh.load(str(path), force="mesh")
    lo, hi = mesh.bounds
    size = hi - lo

    print(f"\n{path.name}  --  {len(mesh.faces)} faces, "
          f"{'watertight' if mesh.is_watertight else 'NOT watertight'}, "
          f"{mesh.body_count} body/bodies")
    print(f"  spans X {lo[0]:9.3f} .. {hi[0]:9.3f}   ({size[0]:.3f} mm)")
    print(f"        Y {lo[1]:9.3f} .. {hi[1]:9.3f}   ({size[1]:.3f} mm)")
    print(f"        Z {lo[2]:9.3f} .. {hi[2]:9.3f}   ({size[2]:.3f} mm)")

    # The plaque is a flat slab, so the top face is far and away the largest
    # patch of upward-facing area. Find the Z that the most upward area sits at,
    # rather than assuming the bounding-box top -- a raised border or a bezel
    # would put the bbox top above the face the lettering actually lands on.
    normals = mesh.face_normals
    areas = mesh.area_faces
    up = normals[:, 2] > 0.99
    if up.any():
        z_of = mesh.triangles[up][:, :, 2].mean(axis=1)
        a_of = areas[up]
        order = np.argsort(-a_of)
        z_sorted, a_sorted = z_of[order], a_of[order]
        # bucket to 0.01mm so a face split into many triangles counts as one
        buckets: dict[float, float] = {}
        for z, a in zip(z_sorted, a_sorted):
            buckets[round(float(z), 2)] = buckets.get(round(float(z), 2), 0.0) + float(a)
        ranked = sorted(buckets.items(), key=lambda kv: -kv[1])
        top_z, top_a = ranked[0]
        print(f"\n  flat upward faces, largest first:")
        for z, a in ranked[:4]:
            flag = "  <-- the lettering face" if z == top_z else ""
            print(f"    z = {z:8.2f}   {a / 100:8.2f} cm2{flag}")
    else:
        top_z, top_a = float(hi[2]), 0.0
        print("\n  no flat upward face found; falling back to the bounding-box top")

    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    cornerish = abs(lo[0]) < 0.51 and abs(lo[1]) < 0.51
    centred = abs(cx) < 0.51 and abs(cy) < 0.51
    origin = ("Corner at 0,0" if cornerish else
              "Centred on 0,0" if centred else None)

    print("\n  ---- paste into plaque_text_on_base.scad ----")
    print(f'  base_file  = "{path.name}";')
    print(f"  plaque_w   = {size[0]:.2f};")
    print(f"  plaque_h   = {size[1]:.2f};")
    print(f"  base_top_z = {top_z:.2f};")
    if origin:
        print(f'  base_origin = "{origin}";')
        print("  base_shift_x = 0;")
        print("  base_shift_y = 0;")
    else:
        # Neither preset lands it on the origin, so say exactly how far off it
        # is instead of leaving the user to hunt for it with a slider.
        print('  base_origin  = "Centred on 0,0";   // then nudge:')
        print(f"  base_shift_x = {-cx:.2f};")
        print(f"  base_shift_y = {-cy:.2f};")
        print(f"  // (its centre sits at {cx:.2f}, {cy:.2f}, which is neither"
              " corner nor centre)")
    print("  --------------------------------------------\n")

    if not mesh.is_watertight:
        print("  NOTE: the mesh is not watertight. OpenSCAD can still import and\n"
              "  union with it, but a boolean may produce artefacts. If the text\n"
              "  comes out ragged, that is where to look first.\n")
    if top_a > 0 and top_a / 100 < size[0] * size[1] / 100 * 0.25:
        print("  NOTE: the largest flat top face covers under a quarter of the\n"
              "  footprint, so this may not be a plain slab. Check base_top_z on\n"
              "  the Align check before committing to a full render.\n")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1]).expanduser()
    if not p.exists():
        print(f"no such file: {p}")
        return 1
    return describe(p)


if __name__ == "__main__":
    raise SystemExit(main())
