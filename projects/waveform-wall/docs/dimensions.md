# Design reference — coordinates, derivations, tolerances

Everything the generator computes, and why. Parameter names match
`src/waveform_wall.scad`.

## Coordinate system

Model space is the artwork's own frame, in millimetres:

| Axis | Meaning | Range |
| --- | --- | --- |
| **X** | across the artwork; fins are distributed along it | `0 .. artwork_width` |
| **Y** | depth, away from the wall | `-back_t .. max_relief` |
| **Z** | up the artwork | `0 .. artwork_height` |

The origin is the bottom-left-back corner of the whole artwork, **not** of a
tile. Tiles keep global coordinates, which is what lets the field stay
continuous across them.

### Print orientation

The tile is exported ready to print: back face on the plate, fins up.

| Model | Printer |
| --- | --- |
| X (artwork width) | X |
| Z (artwork height) | Y |
| Y (depth) | **Z** |

So a tile's bed footprint is `tile_w x tile_h` and its printed height is
`back_t + max_relief`. The model bounding box is
`[tile_w, back_t + max_relief, tile_h]`, which is why a single box check in
`validation.json` covers all three build-volume axes at once.

**Why this orientation is support-free.** Depth becomes printer-Z, so each fin
is a wall whose top edge rises and falls. At printer height `h` the fin exists
wherever `back_t + relief(x, z) >= h`. Those are superlevel sets of a height
field, and superlevel sets are nested: every layer's footprint lies inside the
layer below it. No overhang can exist. Measured on the exported mesh, the fins
contribute **no** downward-facing shallow faces at all; the only unsupported
spans in the part are the deliberate pocket ceilings (15.4 mm keyhole, 13.2 mm
key pocket), which are enclosed bridges anchored on every side.

## Derived geometry

```
short_side   = min(artwork_width, artwork_height)

tile_limit   = 172 (A1 mini) | 230 (A1/P1/X1) | clamp(custom, 80, 240)
tile_cols    = ceil(artwork_width  / tile_limit)
tile_rows    = ceil(artwork_height / tile_limit)
tile_w       = artwork_width  / tile_cols
tile_h       = artwork_height / tile_rows

min_fin_thickness = max(2 * nozzle, 0.8)     -- thinner will not print as a wall
min_fin_gap       = max(0.6, 1.4 * nozzle)   -- narrower and the fins fuse
min_pitch         = min_fin_thickness + min_fin_gap

fins_per_tile = max(4, min(round(tile_w / fin_pitch),
                           floor(tile_w / min_pitch)))    -- INTEGER
pitch         = tile_w / fins_per_tile
fin_count     = fins_per_tile * tile_cols
fin_thickness = clamp(pitch * (1 - gap_fraction),
                      min_fin_thickness, pitch - min_fin_gap)
fin_gap       = pitch - fin_thickness

min_relief    = max(1.2, 0.12 * max_relief)
relief_at(x,z)= min_relief + (max_relief - min_relief) * field01(x, z)
```

`tile_limit` sits below the actual bed, not at it, because MakerWorld's
auto-arrange becomes unreliable past roughly 240 x 235 mm.

## Why a seam is invisible

Fin *i* is centred at `(i + 0.5) * pitch` in global coordinates, and the column
boundary between tile *c* and *c+1* is at `c * fins_per_tile * pitch` — an exact
multiple of the pitch, because `fins_per_tile` is an integer.

The last fin of a tile therefore ends at

```
(fins_per_tile - 0.5) * pitch + fin_thickness/2
```

leaving `(pitch - fin_thickness)/2 = fin_gap/2` of clear space to the boundary.
The next tile is symmetric, so the two halves add to exactly one normal
`fin_gap`. A seam sits at the bottom of an ordinary slot.

Measured on exported meshes (`tools/seamcheck.py`, 330 x 170 mm, 2 columns):

| | |
| --- | --- |
| interior fin gap | 1.8857 mm |
| gap across the seam | 1.8860 mm |
| error | **0.0003 mm** |
| assembled volume vs sum of tiles | 5.8e-16 relative |

Row seams are a different matter: a horizontal seam crosses every fin and is
visible as a fine line. Split into columns wherever the artwork allows it.

## Field detail limit

The fins sample the field discretely, so detail finer than they can represent
turns into fin-to-fin chatter. Two things set the limit:

```
min_wavelength = FINS_PER_WAVE * pitch * WARP_AMP     -- FINS_PER_WAVE = 3.2
```

`WARP_AMP` is the largest singular value of the domain warp's Jacobian, sampled
on an 18 x 18 grid. It is not a fudge factor — a swirl physically compresses
space, so a wavelength that is legal before warping can be illegal after. It
ranges from 1.17 to 3.01 across the shipped styles at default settings.

The harmonic series is then truncated at the last term still above
`min_wavelength`, and the Ripple style's ring spacing gets the same floor.
Guarding only the pre-warp wavelength left four of six styles aliasing.

Consequence worth knowing: **the same artwork can carry slightly different
detail at different tile counts**, because tiling changes `pitch`. That is the
guard doing its job, not a bug.

## Tolerances and clearances

Different interfaces get different allowances; there is no single global value.

| Interface | Value | Reasoning |
| --- | --- | --- |
| Dovetail key in its pocket | `key_fit` = 0.20 mm, applied as a 0.10 mm offset per face | A sliding-but-retained fit. Exposed because it is the one dimension a printer's XY compensation will move. |
| Fin to fin | `fin_gap`, ≥ 1.0 mm typical at defaults | Must stay well clear of fusing; it is also the dominant visual parameter. |
| Fin minimum thickness | `max(2 * nozzle, 0.8)` | Below two extrusion widths a wall does not print as a solid. |
| Fin minimum gap | `max(0.6, 1.4 * nozzle)` | A slot narrower than about one and a half nozzle widths cannot carry a wall on each side; the slicer bridges or drops it. Without this the finest settings gave a 0.48 mm gap, which prints as a solid block with faint scoring — valid geometry, wrong object. |
| Backing under a key pocket | `key_skin = max(0.8, 0.35 * back_t)` | Skin left toward the front so a pocket never shows through. |
| Screw head clearance | 8.4 mm circle, 4.4 mm slot | Sized for a #6 / 4 mm screw head. **Not verified against real hardware.** |
| Boolean cutter overlap | `EPS` = 0.02 mm | Cutters always overshoot; no coplanar Boolean faces anywhere. |

## Guards

Customizer ranges are not protection. The generator constrains itself:

- `fin_thickness` cannot fall below two extrusion widths;
- `min_relief` keeps every fin merged into the backing with real material;
- `back_t` is raised to at least 2.4 mm whenever keys are generated, so a thin
  backing cannot silently produce a paper-thin key;
- the fin's back edge stops half-way into the backing, giving a genuine
  volumetric overlap instead of a coplanar contact;
- `WARP_AMP` and the harmonic truncation cap detail against the fin pitch;
- `f_terrace` defaults to 0 and no preset uses it;
- extrusions declare `convexity`, so OpenSCAD's F5 preview does not show back
  faces through the fins. This affects display only — CGAL export is exact and
  the mesh is byte-identical either way.
