# Validation report — LEOPARD VENT

**Status: CAD-validated. Nothing has been printed.**

Everything below was measured by running the generator and inspecting the
exported meshes. Print quality, stiffness, strength and airflow are all
*unverified* — see "Not verified" at the end.

Reproduce with:

```bash
python3 tools/scadkit.py matrix projects/leopard-vent/validation.json
python3 tools/ribcheck.py        projects/leopard-vent/validation.json
python3 tools/scadkit.py matrix projects/leopard-vent/validation_fan_grille.json
python3 tools/ribcheck.py        projects/leopard-vent/validation_fan_grille.json
```

`ribcheck` reads the STLs the matrix just exported, so run it second.

## Toolchain

| | |
| --- | --- |
| OpenSCAD | 2021.01 — the release MakerWorld's Parametric Model Maker runs |
| trimesh / shapely / numpy | 5.1.1 / 2.1.2 / 2.4.6 |
| Mesh criteria | watertight, consistent winding, expected connected-body count, bounding box, no zero-area faces (no allowance needed anywhere) |
| Web criteria | thinnest web between any two holes ≥ rib, closest hole to the edge ≥ border, smallest hole ≥ `min_hole`, hole count, measured on a section 0.1 mm under the top face |

## What `ribcheck` measures, and its tolerance

It slices the exported STL just under the top face, takes the outline and every
hole loop, and measures the minimum distance between every pair of nearby holes
(the rib), from every hole to the outline (the border), and the largest circle
that fits in each hole (smallest / largest). It is a measurement of the mesh,
not a re-run of the maths that produced it.

The tolerance is 0.002 mm, and it belongs to the file format. OpenSCAD writes
ASCII STL to six significant digits, so past 100 mm from the origin a vertex is
only good to ±0.0005 mm. Measured: a 2 mm rib reads 1.99991 on a 120 mm panel,
whose coordinates all stay under 100, and a 0.8 mm rib reads 0.79901 on a 250 mm
panel, whose coordinates do not — a tenfold jump, which is what the digit count
predicts. That is the "rib= 0.799" and "1.999" in the tables below.

The checker was itself checked: asked for 2.01 / 5.01 / 4.5 on a part built at
2 / 5 / 4, it fails all three.

## Parameter matrix

```
== LEOPARD VENT (irregular-cell vent / lightening pattern) :: 47 cases ==
  default                      PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.1cm3 faces=4496 degen=0  [0.1s]
  shape_3_sides                PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.4cm3 faces=4768 degen=0  [0.1s]
  shape_6_sides                PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.2cm3 faces=5264 degen=0  [0.1s]
  shape_unknown                PASS  rejected as expected
  regular_grid                 PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.0cm3 faces=4348 degen=0  [0.1s]
  regular_isogrid              PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.4cm3 faces=4748 degen=0  [0.1s]
  regular_honeycomb            PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.1cm3 faces=5108 degen=0  [0.1s]
  irregular_max_quads          PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.2cm3 faces=4508 degen=0  [0.1s]
  irregular_max_tris           PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.4cm3 faces=4768 degen=0  [0.1s]
  irregular_max_hexes          PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.3cm3 faces=5232 degen=0  [0.1s]
  seed_999                     PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.1cm3 faces=4536 degen=0  [0.1s]
  crop_quads                   PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.9cm3 faces=5372 degen=0  [0.1s]
  crop_tris                    PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.8cm3 faces=4784 degen=0  [0.1s]
  crop_hexes                   PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.5cm3 faces=5004 degen=0  [0.1s]
  crop_regular_honeycomb       PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.9cm3 faces=4640 degen=0  [0.1s]
  fit_thin_strip               PASS  WT bodies=1 bbox=200.0x30.0x3.0 vol=8.2cm3 faces=3700 degen=0  [0.1s]
  fit_awkward_size             PASS  WT bodies=1 bbox=97.0x41.0x3.0 vol=5.5cm3 faces=4368 degen=0  [0.1s]
  circle                       PASS  WT bodies=1 bbox=120.0x120.0x3.0 vol=13.3cm3 faces=7040 degen=0  [0.1s]
  circle_max_hexes             PASS  WT bodies=1 bbox=250.0x250.0x3.0 vol=46.5cm3 faces=28780 degen=0  [0.4s]
  panel_min                    PASS  WT bodies=1 bbox=30.0x30.0x3.0 vol=1.0cm3 faces=1360 degen=0  [0.0s]
  panel_max_fine_tris          PASS  WT bodies=1 bbox=250.0x250.0x3.0 vol=102.5cm3 faces=177556 degen=0  [2.2s]
  panel_corner_clamped         PASS  WT bodies=1 bbox=60.0x40.0x3.0 vol=3.1cm3 faces=2568 degen=0  [0.0s]
  panel_corner_sharp           PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.2cm3 faces=4160 degen=0  [0.1s]
  cell_min                     PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=15.0cm3 faces=26976 degen=0  [0.3s]
  cell_max                     PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=6.1cm3 faces=556 degen=0  [0.0s]
  rib_min                      PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=8.0cm3 faces=4496 degen=0  [0.1s]
  rib_max                      PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=16.8cm3 faces=972 degen=0  [0.0s]
  rib_leaves_no_hole           PASS  rejected as expected
  rib_unprintable              PASS  rejected as expected
  border_raised_to_rib         PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.6cm3 faces=5388 degen=0  [0.1s]
  border_max                   PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=25.9cm3 faces=1184 degen=0  [0.0s]
  border_fills_panel           PASS  rejected as expected
  corner_radius_min            PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.0cm3 faces=2908 degen=0  [0.1s]
  corner_radius_clamped        PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=15.3cm3 faces=15144 degen=0  [0.1s]
  min_hole_off                 PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.1cm3 faces=4496 degen=0  [0.1s]
  min_hole_off_crop            PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=11.9cm3 faces=5372 degen=0  [0.1s]
  min_hole_clamped             PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=12.8cm3 faces=3980 degen=0  [0.0s]
  thickness_min                PASS  WT bodies=1 bbox=120.0x80.0x1.0 vol=3.7cm3 faces=4496 degen=0  [0.1s]
  thickness_max                PASS  WT bodies=1 bbox=120.0x80.0x12.0 vol=44.4cm3 faces=4496 degen=0  [0.1s]
  pocket                       PASS  WT bodies=1 bbox=120.0x80.0x3.0 vol=17.0cm3 faces=4336 degen=0  [3.0s]
  pocket_shallowest            PASS  WT bodies=1 bbox=120.0x80.0x1.0 vol=7.2cm3 faces=4336 degen=0  [3.4s]
  pocket_too_shallow           PASS  rejected as expected
  cutter_default               PASS  WT bodies=40 bbox=110.0x70.0x5.0 vol=29.4cm3 faces=3828 degen=0  [0.1s]
  cutter_crop                  PASS  WT bodies=48 bbox=110.0x70.0x5.0 vol=28.1cm3 faces=4640 degen=0  [0.1s]
  cutter_pocket                PASS  WT bodies=40 bbox=110.0x70.0x3.0 vol=17.6cm3 faces=3828 degen=0  [0.1s]
  everything_max               PASS  WT bodies=1 bbox=250.0x250.0x12.0 vol=588.1cm3 faces=10416 degen=0  [9.5s]
  everything_min               PASS  WT bodies=1 bbox=30.0x30.0x1.0 vol=0.3cm3 faces=2460 degen=0  [0.0s]
== 47/47 passed ==
```

## Measured webs

```
== ribcheck LEOPARD VENT (irregular-cell vent / lightening pattern) :: 39 cases ==
  default                      PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.4%
  shape_3_sides                PASS  holes=44   rib= 2.000 border= 5.000 smallest= 5.008 largest=12.035 open= 56.9%
  shape_6_sides                PASS  holes=45   rib= 2.000 border= 5.000 smallest= 5.545 largest=14.396 open= 61.1%
  regular_grid                 PASS  holes=40   rib= 2.000 border= 5.000 smallest=12.000 largest=12.000 open= 61.7%
  regular_isogrid              PASS  holes=44   rib= 2.000 border= 5.000 smallest= 5.998 largest=10.437 open= 57.0%
  regular_honeycomb            PASS  holes=45   rib= 2.000 border= 5.000 smallest= 6.000 largest=12.422 open= 61.5%
  irregular_max_quads          PASS  holes=40   rib= 2.000 border= 5.000 smallest= 7.167 largest=13.839 open= 61.0%
  irregular_max_tris           PASS  holes=44   rib= 2.000 border= 5.000 smallest= 4.547 largest=12.826 open= 56.7%
  irregular_max_hexes          PASS  holes=45   rib= 2.000 border= 5.000 smallest= 5.395 largest=15.126 open= 60.7%
  seed_999                     PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.982 largest=14.240 open= 61.4%
  crop_quads                   PASS  holes=48   rib= 2.000 border= 5.000 smallest= 5.398 largest=13.008 open= 58.7%
  crop_tris                    PASS  holes=44   rib= 2.000 border= 5.000 smallest= 5.767 largest=12.570 open= 55.4%
  crop_hexes                   PASS  holes=42   rib= 2.000 border= 5.000 smallest= 4.108 largest=14.134 open= 56.5%
  crop_regular_honeycomb       PASS  holes=37   rib= 2.000 border= 5.000 smallest= 8.868 largest=13.044 open= 55.0%
  fit_thin_strip               PASS  holes=31   rib= 2.000 border= 4.000 smallest= 4.925 largest=11.754 open= 54.5%
  fit_awkward_size             PASS  holes=40   rib= 1.200 border= 3.000 smallest= 4.032 largest= 8.241 open= 53.9%
  circle                       PASS  holes=54   rib= 2.000 border= 5.000 smallest= 4.018 largest=13.769 open= 60.7%
  circle_max_hexes             PASS  holes=246  rib= 1.999 border= 4.999 smallest= 4.178 largest=14.320 open= 68.5%
  panel_min                    PASS  holes=4    rib= 2.000 border= 2.000 smallest= 9.991 largest=12.652 open= 64.1%
  panel_max_fine_tris          PASS  holes=1771 rib= 0.799 border= 5.000 smallest= 2.864 largest= 5.242 open= 45.3%
  panel_corner_clamped         PASS  holes=8    rib= 2.000 border= 5.000 smallest= 8.749 largest=12.835 open= 50.1%
  panel_corner_sharp           PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.3%
  cell_min                     PASS  holes=256  rib= 0.800 border= 5.000 smallest= 3.361 largest= 5.244 open= 47.7%
  cell_max                     PASS  holes=2    rib= 2.000 border= 5.000 smallest=53.354 largest=56.141 open= 78.8%
  rib_min                      PASS  holes=40   rib= 0.800 border= 5.000 smallest= 9.722 largest=14.370 open= 72.2%
  rib_max                      PASS  holes=6    rib=10.000 border=10.000 smallest=19.981 largest=30.222 open= 41.4%
  border_raised_to_rib         PASS  holes=48   rib= 3.000 border= 3.000 smallest= 6.473 largest=12.699 open= 56.3%
  border_max                   PASS  holes=8    rib= 2.000 border=30.000 smallest= 7.474 largest=10.700 open= 10.0%
  corner_radius_min            PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.720 largest=13.397 open= 61.7%
  corner_radius_clamped        PASS  holes=35   rib= 2.000 border= 5.000 smallest= 9.610 largest=13.392 open= 46.6%
  min_hole_off                 PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.4%
  min_hole_off_crop            PASS  holes=48   rib= 2.000 border= 5.000 smallest= 5.398 largest=13.008 open= 58.7%
  min_hole_clamped             PASS  holes=35   rib= 2.000 border= 5.000 smallest= 9.612 largest=13.392 open= 55.5%
  thickness_min                PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.4%
  thickness_max                PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.4%
  pocket                       PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.4%
  pocket_shallowest            PASS  holes=40   rib= 2.000 border= 5.000 smallest= 8.719 largest=13.392 open= 61.4%
  everything_max               PASS  holes=14   rib=10.000 border=30.000 smallest=20.255 largest=49.733 open= 41.2%
  everything_min               PASS  holes=36   rib= 0.800 border= 1.000 smallest= 4.000 largest= 4.000 open= 63.0%
== 39/39 passed ==
```

## Library example — fan grille

Exercises the module through `use <>`, with a ring-shaped child region (blade
circle less a hub disc). `ribcheck` sees the screw holes as holes too; they sit
outside the blade circle, so the closest pair is always two vents. The border
figure is the fan's own geometry — plate edge to screw hole — not a vent border.

```
== LEOPARD VENT example: fan grille (library use) :: 10 cases ==
  fan_40                       PASS  WT bodies=1 bbox=40.0x40.0x2.0 vol=2.9cm3 faces=1672 degen=0  [0.1s]
  fan_60                       PASS  WT bodies=1 bbox=60.0x60.0x2.0 vol=5.4cm3 faces=3876 degen=0  [0.1s]
  fan_80                       PASS  WT bodies=1 bbox=80.0x80.0x2.0 vol=9.0cm3 faces=6464 degen=0  [0.1s]
  fan_92                       PASS  WT bodies=1 bbox=92.0x92.0x2.0 vol=11.9cm3 faces=6908 degen=0  [0.1s]
  fan_120                      PASS  WT bodies=1 bbox=120.0x120.0x2.0 vol=18.5cm3 faces=13248 degen=0  [0.2s]
  fan_140                      PASS  WT bodies=1 bbox=140.0x140.0x2.0 vol=25.2cm3 faces=16256 degen=0  [0.3s]
  fan_80_no_hub                PASS  WT bodies=1 bbox=80.0x80.0x2.0 vol=7.5cm3 faces=7252 degen=0  [0.1s]
  fan_80_quads                 PASS  WT bodies=1 bbox=80.0x80.0x2.0 vol=8.8cm3 faces=6172 degen=0  [0.1s]
  fan_80_tris                  PASS  WT bodies=1 bbox=80.0x80.0x2.0 vol=9.2cm3 faces=6076 degen=0  [0.1s]
  fan_unknown_size             PASS  rejected as expected
== 10/10 passed ==
== ribcheck LEOPARD VENT example: fan grille (library use) :: 9 cases ==
  fan_40                       PASS  holes=8    rib= 1.600 border= 2.300 smallest= 3.387 largest= 4.766 open= 10.0%
  fan_60                       PASS  holes=23   rib= 1.600 border= 2.850 smallest= 4.059 largest= 7.631 open= 24.9%
  fan_80                       PASS  holes=43   rib= 1.600 border= 2.100 smallest= 4.093 largest= 8.568 open= 29.2%
  fan_92                       PASS  holes=53   rib= 1.600 border= 2.600 smallest= 4.005 largest= 8.568 open= 29.3%
  fan_120                      PASS  holes=103  rib= 1.600 border= 4.719 smallest= 4.075 largest= 8.695 open= 35.5%
  fan_140                      PASS  holes=134  rib= 1.600 border= 4.685 smallest= 4.112 largest= 8.695 open= 35.7%
  fan_80_no_hub                PASS  holes=55   rib= 1.600 border= 2.100 smallest= 4.093 largest= 8.568 open= 41.4%
  fan_80_quads                 PASS  holes=44   rib= 1.600 border= 2.100 smallest= 4.251 largest= 8.376 open= 30.8%
  fan_80_tris                  PASS  holes=46   rib= 1.600 border= 2.100 smallest= 4.043 largest= 7.626 open= 28.0%
== 9/9 passed ==
```

Separately measured on the 80 mm grille: vents to hub disc 2.498 mm and vents to
blade edge 2.500 mm, against a 2.5 mm border. The 0.002 is the measurement
using a true circle where OpenSCAD's hub is a 180-gon whose flats sit 0.0023 mm
inside it.

## Seed sweeps

The matrix covers a few seeds; random cells deserve more. Each sweep renders
seeds 1–40 for every shape at **irregularity 1** (the most distorted cells),
then runs the mesh check and `ribcheck` on each.

| Sweep | Renders | Failures | Open area |
| --- | --- | --- | --- |
| Fit, default 120 × 80 panel | 120 | 0 | 56.5–61.3 % |
| Fit, 97 × 41, cell 9, rib 1.2, border 3 | 120 | 0 | — |
| Fit, 200 × 22 strip, cell 12, border 4 | 120 | 0 | — |
| Crop, default 120 × 80 panel | 120 | 0 | 53.1–58.7 % |
| Crop, 100 mm circle, cell 6, rib 1.0, border 3 | 120 | 0 | 39.1–55.4 % |

The first run of the crop sweep reported 40 failures. All 40 were the sweep
script asking for the 6-sided shape by its old name, "Mixed polygons", which the
generator refused as an unknown shape — the guard doing its job. Re-run with the
current name: none.

The strip is there for the 6-sided fit, where the Voronoi search bounds are
derived from the stretched lattice: a squashed row makes the true reach of a
cell much larger than on a regular honeycomb, and an undersized search would
miss a neighbour and let two cells overlap — erasing the rib between them. In
the strip all 40 seeds keep every quad and hexagon hole (16 and 15); the
triangle web drops one or two of its narrow end half-triangles on 15 seeds.

## Cross-checks

| Check | Result |
| --- | --- |
| Cutter bodies = panel holes | 40 = 40 (Fit), 48 = 48 (Crop) |
| Cutter footprint = panel hole area | 5882.10 = 5882.10 mm² (Fit), 5625.68 = 5625.68 mm² (Crop) |
| 2D holes → SVG | 40 subpaths, one per hole |
| 2D holes → DXF | Exports; written as 997 loose `LINE` segments, not polylines |
| Crop pattern stable under resize | Every central hole of a 120 × 80 panel reappears unchanged in a 200 × 150 one: 24/24 quads, 14/14 triangles, 17/17 hexagons |
| 6-sided cells really six-sided | Inner cells over 10 seeds: 339/339 hexagons at irregularity 0.5 and 0.7; 309/339 at 0.85; 267/336 at 1 |
| `use <>` exposes no standalone geometry | The fan grille and a box-lid test render only their own parts |

## Render time

Every standalone case is built from 2D booleans and extrusions, never a 3D
difference. In the matrix, the default takes about 0.1 s, 1771 holes take
about 2 s, and the slowest case is the pocketed 250 mm `everything_max` at
9–10 s — pockets need one 3D union.

The same panel cut by 3D difference instead, as a library user subtracting from
their own solid would: 1.2 s against 0.1 s for 47 holes, 8.8 s against 0.4 s for
310 holes. Slower, not prohibitive, at these sizes.

These are single measurements on a shared container, where timings have been
seen to bounce close to twofold. Read them to one significant figure.

## Not verified

- **No print exists.** Thin ribs (0.8–1.2 mm), small holes, and pocket floors
  are untested on a real machine.
- **No structural test.** The claim that the triangle web braces against shear
  is truss reasoning, not a measurement. Nothing here says how stiff or strong
  any pattern is.
- **No airflow test.** Open area is measured; flow through it is not.
- **Fan grille screw spacings** are the commonly quoted figures, not checked
  against a real fan.
- **MakerWorld** itself has not been tried. The file is self-contained and uses
  nothing past OpenSCAD 2021.01, which is what that requires.
