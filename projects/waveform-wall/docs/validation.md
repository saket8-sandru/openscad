# Validation report — LAMELLA waveform wall panel

**Status: CAD-validated. No physical print has been made.**

Everything below was measured by running the generator and inspecting the
exported meshes. Nothing about real-world fit, key tightness, warping, surface
finish or fin strength has been confirmed on a printer, and none of it should
be claimed until it has.

Reproduce with:

```bash
python3 tools/scadkit.py matrix projects/waveform-wall/validation.json
python3 tools/crosscheck.py
python3 tools/seamcheck.py --width 330 --height 170 --style Flow
python3 tools/seamcheck.py --width 300 --height 300 --style Ripple
python3 tools/overhangcheck.py projects/waveform-wall/exports/*.stl
```

## Toolchain

| | |
| --- | --- |
| OpenSCAD | 2021.01 — the release MakerWorld's Parametric Model Maker runs |
| trimesh / scipy / numpy | 5.1.0 / 1.17.1 / 2.4.6 |
| Mesh criteria | watertight, consistent winding, expected connected-body count, bounding box within build volume, bounded zero-area faces |

## Parameter matrix

```
== LAMELLA waveform wall panel :: 25 cases ==
  default_tile                 PASS  WT bodies=1 bbox=170.0x22.1x170.0 vol=317.2cm3 faces=9632  [15.5s]
  default_assembled            PASS  WT bodies=1 bbox=170.0x22.1x170.0 vol=317.2cm3 faces=9632  [14.9s]
  multitile_2x2_assembled      PASS  WT bodies=1 bbox=300.0x22.2x300.0 vol=984.9cm3 faces=31020  [58.7s]
  multitile_2x2_corner         PASS  WT bodies=1 bbox=150.0x21.2x150.0 vol=258.6cm3 faces=7912  [12.5s]
  multitile_3x1_middle         PASS  WT bodies=1 bbox=160.0x22.4x160.0 vol=271.9cm3 faces=8836  [13.3s]
  style_flow                   PASS  WT bodies=1 bbox=170.0x22.4x170.0 vol=321.2cm3 faces=9644  [14.6s]
  style_vortex                 PASS  WT bodies=1 bbox=170.0x22.4x170.0 vol=345.0cm3 faces=9628  [14.1s]
  style_dune                   PASS  WT bodies=1 bbox=170.0x22.4x170.0 vol=319.5cm3 faces=9644  [14.5s]
  style_liquid                 PASS  WT bodies=1 bbox=170.0x22.4x170.0 vol=328.0cm3 faces=9628  [14.4s]
  style_interference           PASS  WT bodies=1 bbox=170.0x22.4x170.0 vol=328.0cm3 faces=9636  [13.8s]
  style_ripple                 PASS  WT bodies=1 bbox=170.0x22.1x170.0 vol=317.2cm3 faces=9632  [14.6s]
  min_everything               PASS  WT bodies=1 bbox=80.0x9.4x80.0 vol=37.5cm3 faces=2668  [4.1s]
  max_relief_deep              PASS  WT bodies=1 bbox=170.0x61.5x170.0 vol=801.3cm3 faces=9636  [13.9s]
  coarse_nozzle_thick_wall     PASS  WT bodies=1 bbox=170.0x24.8x170.0 vol=333.2cm3 faces=4288  [4.8s]
  fine_pitch_smooth            PASS  WT bodies=1 bbox=170.0x22.3x170.0 vol=356.1cm3 faces=37564  [87.7s]
  big_artwork_one_tile         PASS  WT bodies=1 bbox=171.4x20.5x150.0 vol=322.9cm3 faces=8760  [19.3s]
  wide_aspect_tile             PASS  WT bodies=1 bbox=140.0x20.7x100.0 vol=156.8cm3 faces=5260  [7.8s]
  printer_x1_large_tile        PASS  WT bodies=1 bbox=230.0x22.3x230.0 vol=612.9cm3 faces=17596  [33.2s]
  single_tile_no_joints_no_mount PASS  WT bodies=1 bbox=160.0x22.1x160.0 vol=281.1cm3 faces=8244  [10.1s]
  loose_key_fit                PASS  WT bodies=1 bbox=170.0x22.1x170.0 vol=317.2cm3 faces=9632  [16.4s]
  advanced_extremes            PASS  WT bodies=1 bbox=170.0x21.4x170.0 vol=261.5cm3 faces=9644  [14.3s]
  advanced_terraced            PASS  WT bodies=1 bbox=170.0x22.4x170.0 vol=318.7cm3 faces=5068  [7.5s]
  zero_swirl                   PASS  WT bodies=1 bbox=170.0x22.1x170.0 vol=323.2cm3 faces=9640  [14.3s]
  joining_keys                 PASS  WT bodies=1 bbox=26.0x13.0x1.6 vol=0.4cm3 faces=20  [0.1s]
  fit_coupon                   PASS  WT bodies=3 bbox=98.6x21.6x46.0 vol=26.3cm3 faces=2692  [2.9s]
== 25/25 passed ==
```

Every case is watertight with consistent winding and the expected body count,
and every tile fits its target build volume.

Notes on two results that look odd but are correct:

- **An assembled multi-tile artwork reports ONE body, not one per tile.**
  Adjacent tiles butt on exactly coincident planes, so loading the STL welds
  the shared vertices. That is evidence the seams close with no gap and no
  overlap; the tiles are still separate printed parts.
- **A small number of zero-area faces is allowed.** CGAL emits collinear
  slivers where a planar face meets many inserted vertices — here the backing's
  front plane along a tile's top edge, one vertex per fin. They were traced to
  a single line (`y=0, z=tile_h`) with total area exactly 0.000e+00, leave the
  mesh watertight and genus-0, and slicers discard them. The fit coupon, which
  has no such edge, exports with zero.

## Field engine cross-validation

The NumPy mirror in `tools/fieldlab.py` is what makes design iteration
affordable, so it has to compute the same numbers as the shipped `.scad`.
`crosscheck.py` drives OpenSCAD's echo export over ten probe points and
compares.

**15/15 configurations agree at a 2e-5 tolerance** — the default, all six
styles, three seeds, `intensity`, `flow_angle`, `swirl_scale` +
`extra_vortices`, `relief_gamma`, and a non-square artwork. Worst observed
difference is 1.25e-5 on the raw field and 4.2e-6 on the normalised field.

That tolerance is the **measurement floor, not a comfort margin**: OpenSCAD's
echo prints six significant figures, so a field value of order 1 can only be
read back to about 5e-6.

The check has earned its place three times over:

1. It caught a silent divergence the moment two style-table rows were edited in
   the `.scad` but not in Python. The table is now parsed out of the `.scad`.
2. It caught the same class of drift again when the `.scad` default artwork
   changed to 170 x 170 while Python still assumed 400 x 400. Customizer
   defaults are now parsed out of the `.scad` too, so neither can drift.
3. It exposed a genuine reproducibility defect in the generator itself, below.

### Angle reduction (a real defect, not a harness artefact)

Agreement was stuck at 1.3e-3 — a hundred times worse than echo precision.
Probing the internals isolated it: `hash01(43, 137)` returned 0.227067 in
OpenSCAD and 0.227047 in NumPy.

The hash multiplies `sin`'s result by ~44000, so any difference between two
`sin` implementations is amplified by the same factor. With seeds reaching
angles above 11000 degrees, the two libraries' range reduction differed by
around 5e-10 — which the hash turned into 2e-5 in its output, and which then
moved field feature positions by roughly 0.01 mm.

That is physically negligible, but it means **the generator was not reproducible
across OpenSCAD builds or platforms** — a real problem for a model whose whole
value is that a given seed makes a given artwork.

Fixed by reducing every angle into [0, 360) explicitly, on both sides, before
calling `sin`. Agreement improved from 1.3e-3 to 1.25e-5 — a hundredfold, and
now limited only by echo precision.

## Seam continuity

The central claim — that a tiled artwork keeps one continuous surface, and that
a vertical seam is invisible — checked against exported geometry rather than
against the source making the claim.

| Configuration | Interior fin gap | Gap across the seam | Error |
| --- | --- | --- | --- |
| 330 × 170 mm, 2 × 1 tiles, Flow | 1.8857 mm | 1.8860 mm | **0.0003 mm** |
| 300 × 300 mm, 2 × 2 tiles, Ripple | 1.8947 mm | 1.8940 mm | **0.0007 mm** |

Also verified in both: every tile occupies its own cell to 0.0000 mm, and the
assembled volume equals the sum of the tiles to within 1e-15 relative — so the
tiles neither overlap nor leave a gap.

A rendered 2 × 2 assembly is in `previews/hero_assembled.png`; the seams are at
x = 150 and z = 150 and are not findable by eye.

**Horizontal seams are a different matter** and are not claimed to be
invisible: a row seam crosses every fin and leaves a fine horizontal line.

## Support-free printing

Claimed as a property of the geometry: printed back-face-down the fins are a
height field, so each layer's footprint lies inside the layer below and no
overhang can exist. Verified by measuring downward-facing faces of the exported
meshes (`overhangcheck.py`, 45° threshold).

| Export | Internal downward area | Longest unsupported span |
| --- | --- | --- |
| default_tile | 0.12 % | 15.40 mm (keyhole slot) |
| multitile_2x2_corner | 0.48 % | 15.40 mm (keyhole), 13.2 mm (key pockets) |
| max_relief_deep (60 mm relief) | 0.05 % | 15.40 mm |
| fine_pitch_smooth (4 mm pitch) | 0.07 % | 15.40 mm |
| fit_coupon | 2.03 % | 13.20 mm |

**The fins contribute no downward-facing faces at all**, at any setting tested
including the extremes. The only unsupported spans anywhere in the part are the
deliberate pocket ceilings — enclosed bridges anchored on every side, all under
16 mm.

This check found a real defect: the fit coupon originally carried a whole
bowtie pocket and so bridged 26.2 mm, testing a harder print than the product
ever asks for, since a real tile only contains half a pocket. Rebuilt as two
butting half-strips, it now bridges 13.20 mm — exactly the production condition
— and tests the seam as well as the key.

## Defects found and fixed

| Defect | How it surfaced | Resolution |
| --- | --- | --- |
| Field aliased into fin-to-fin chatter | Real-lit renders of all six styles | Guard now measures the warp Jacobian (1.17–3.01× frequency gain) and truncates harmonics below 3.2 fins per wave |
| Terraced style read as broken pixel art | Render review | Style replaced by Ripple; terracing demoted to an advanced option |
| Keyhole slot punched through the backing | Euler number went to −2 (genus 2) | Boss extended to cover the whole keyhole including slot travel |
| Swirl/peak signs left to coin flips | Probing feature lists across seeds | Signs alternate deterministically; every seed gets a counter-rotating pair |
| Feature positions clumped (two swirls 25 mm apart at seed 33, cancelling) | Probing feature lists across seeds | Placement moved to an R2 low-discrepancy sequence; separation at that seed went to 212 mm |
| Duplicate `f_wave_amp` assignment | `--hardwarnings` during STL export | Removed. Previews do not set that flag, so they had been masking a hard export failure |
| Generator not reproducible across platforms: `sin` range reduction differed, amplified ~44000x by the hash | Cross-check stuck at 1.3e-3 | Angles reduced into [0,360) explicitly before every `sin`; agreement improved 100x |
| Fit coupon's key merged into the strip | Body count 1 instead of 2 | Offset now includes the bowtie's reach; key also rotated to lie flat on the same plate |
| Fit coupon bridged 26.2 mm | Overhang check | Rebuilt as two butting half-strips |

## Not verified

- **Any physical print.** Nothing here has been on a printer.
- **Key fit.** `key_fit` = 0.20 mm is a reasoned starting value, not a measured
  one. Print the fit coupon first.
- **Screw hardware.** The keyhole is sized for a typical #6 / 4 mm screw head
  from nominal figures, not from a measured screw.
- **Warping.** A large flat backing is classic corner-lift geometry. Untested.
- **Fin strength.** Fins are printed as standing walls and are loaded across
  the layers by a sideways knock. Not tested.
- **Print time and filament.** Solid volumes are reported above; real filament
  depends on the slicer and is substantially lower. No slicer has been run.
- **Acoustic behaviour.** Not analysed at all, and deliberately absent from the
  listing copy.
