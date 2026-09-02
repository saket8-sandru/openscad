# LAMELLA — Parametric Waveform Wall Panel

A generator for ribbed wall sculpture. A continuous mathematical field decides
how far each vertical fin stands off the backing, so many simple fins together
reconstruct one flowing three-dimensional surface. Artwork larger than the
print bed is split into tiles automatically, with the surface running unbroken
across every seam.

One file, `src/waveform_wall.scad`, self-contained, written for OpenSCAD
2021.01 — the release MakerWorld's Parametric Model Maker runs.

## What makes it different

- **The customizer is real.** The field maths runs in OpenSCAD, not in a
  precomputation step, so every control genuinely regenerates the geometry.
  Comparable models in this category are fixed STLs produced by an external
  tool.
- **Vertical seams are invisible.** Fins are pitched globally and each tile
  holds a whole number of them, so a tile edge always lands in the middle of a
  gap rather than through a fin. Measured: a seam gap of 1.8860 mm against an
  interior gap of 1.8857 mm.
- **One rigid part per tile**, not a bag of loose strips to glue down.
- **No supports, by construction.** Printed back-down the fins are a height
  field, so every layer is fully supported by the one below. This is a property
  of the geometry, not a tuning result.
- **Detail follows the fins.** The field's finest detail is capped against the
  fin pitch *and* against how much the swirl compresses space, so coarse panels
  stay clean and fine panels earn more detail automatically.

## Styles

| Style | Character |
| --- | --- |
| **Surprise me** | Picks one of the six for you — from the seed in Seeded mode (so it stays repeatable), or freshly in Surprise mode. |
| **Ripple** (default) | Concentric rings warped into an oval eye. The strongest silhouette of the six. |
| **Flow** | Sweeping diagonal S-curves; calm and architectural. |
| **Vortex** | One dominant swirling wave with large quiet regions. |
| **Dune** | Long smooth ridges, minimal and restrained. |
| **Liquid** | Denser interfering flow with more secondary detail. |
| **Interference** | Optical moiré texture; the busiest and most graphic. |

### Two ways to get a design

`seed_mode` is the first control in the Style group:

- **Seeded (repeatable)** — the seed number *is* the design. Same number, same
  artwork, every time, on any machine. Use this to export.
- **Surprise me (new every render)** — rolls a fresh composition each render.
  Good for browsing. The rolled seed *and style* are printed in the console, so
  when you see one you like you can switch back to Seeded and type them in.

`style` has its own **Surprise me** option, and the two compose rather than
fight. Seeded mode + Surprise style gives a style chosen from the seed, so it is
still fully repeatable; Surprise mode + Surprise style rolls both at once. The
style pick is even across the seed range — 33/34/35/31/31/35 over seeds 1..199.

**Surprise mode and multi-tile do not mix.** Each export re-rolls, so tiles
exported one at a time would each get a different surface and would not meet at
the seams. The generator warns loudly when you are in Surprise mode with more
than one tile — lock the seed first.

`seed` re-composes any style completely. Feature positions come from an R2
low-discrepancy sequence plus a bounded per-feature jitter: measured over 200
seeds that gives 200 distinct layouts (four without the jitter) while no two
swirls come within half a swirl radius of each other. Spread without rigidity.

## Printing

| | |
| --- | --- |
| Orientation | Back face flat on the bed, fins pointing up. Already correct as exported. |
| Supports | **None.** The fins cannot produce an overhang in this orientation — measured on the exported mesh, they contribute no downward-facing faces at all. The only unsupported spans in the part are the key-pocket and keyhole ceilings, enclosed bridges of at most 15.4 mm. |
| Bed | Tiles are capped at 172 mm (A1 mini) or 230 mm (A1/P1/X1), below the bed and below the ~240 mm ceiling where MakerWorld's auto-arrange gets unreliable. |
| Material | PLA or PETG. PLA is stiffer and shows the surface better; PETG is tougher if the piece will be handled. |
| Adhesion | Use a brim. A large flat backing is the classic corner-lift geometry, and a lifted corner shows up as a step at a seam. |
| Fin strength | Fins are printed as standing walls, so a sideways knock loads them across the layers. Fine for wall art; do not use as a step or a shelf. |

### Material and time

The generator reports solid volume, which is a geometric measure, not filament.
A default 170 × 170 mm tile is about 260 cm³ solid; actual filament is far
lower because the slicer fills the 6 mm-thick fins with perimeters and infill
rather than solid plastic. At 2 walls and 15 % infill expect very roughly 40 %
of solid volume for the fins and near-solid for the 2.4 mm backing.

**These are estimates from geometry, not from a slicer, and no test print has
been made yet.** Slice before committing to a large piece.

The two controls that move material most:

- `max_relief` — material scales close to linearly with it.
- `gap_fraction` — a bigger gap removes fin material, at the cost of the panel
  reading more like stripes and less like a surface.

## Assembly (multi-tile only)

Tiles join with hidden dovetail keys that drop into pockets in the back face.
Print the keys from the **Joining keys** output. The keys sit entirely behind
the panel and resist the tiles pulling apart in plane; no glue is needed. Mount
each tile to the wall with the keyhole slots.

Assembly is order-independent — the keys are separate parts, so tiles do not
have to be slid together in a sequence.

## Customizer parameters

### Artwork
| Parameter | Default | Notes |
| --- | --- | --- |
| `artwork_width` / `artwork_height` | 170 × 170 mm | Total artwork. Tiled automatically past the bed limit. The default is a single tile, so a first print needs no assembly. |
| `max_relief` | 20 mm | Depth of the tallest fins. The biggest driver of how dramatic the piece looks, and of material. |

### Style
| Parameter | Default | Notes |
| --- | --- | --- |
| `style` | Ripple | See the table above. |
| `seed` | 7 | Recomposes the artwork within the chosen style. |
| `intensity` | 1.0 | Overall boldness of the relief. |
| `flow_angle` | 25° | Rotates the whole flow direction. |

### Fins
| Parameter | Default | Notes |
| --- | --- | --- |
| `fin_pitch` | 8.0 mm | Target fin spacing. Finer is more optical and slower, and unlocks finer field detail. |
| `gap_fraction` | 0.24 | Share of each pitch left open. Below ~0.30 the fins read as one surface; near 0.45 they read as stripes. |
| `fin_smoothness` | 1.6 mm | Vertical sampling of the fin edge. Smaller is smoother and slower. |

### Printing
`printer`, `custom_tile_max`, `nozzle`, `back_thickness`.

### Assembly
`joint_style`, `key_fit` (raise if keys are tight), `wall_mount`.

### Output
`output` selects Assembled preview / Single tile / All tiles laid out /
Joining keys / Fit coupon. `tile_col` and `tile_row` pick which tile to export.

### Advanced
`extra_vortices`, `swirl_scale`, `detail_scale`, `relief_gamma`,
`terrace_steps`. All neutral at their defaults. `terrace_steps` quantises the
relief into contour bands; it is off by default and no preset uses it, because
terracing fights the fins — the surface is already quantised across the panel,
and quantising depth too tends to read as digital error rather than contours.

## Guards

Customizer ranges are not protection on their own, so the generator constrains
its own geometry:

- fins never thinner than two extrusion widths, and never closer together than
  a slot the slicer can resolve — the fin pitch is capped so both fit;
- a relief floor keeps every fin attached to the backing with real material
  rather than tapering to a knife edge;
- the backing is raised to a workable thickness whenever dovetail keys are
  actually generated, so a thin backing cannot silently produce a paper-thin key;
- the harmonic series is truncated below the fins' resolving power;
- ring spacing gets the same anti-alias floor as the harmonics.

## Testing status

**CAD-validated.** Compiles, renders, exports, and passes a 25-case parameter
matrix plus a geometric seam check. See `validation.md`.

**No physical print has been made.** Nothing here about fit, key tightness,
warping, or fin strength has been confirmed on a real printer. Print the
**Fit coupon** output before committing to a full set — it is a short strip of
the real panel plus one real key pocket and a key.
