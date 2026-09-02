# MakerWorld listing package

> Draft copy. Everything below is written to match what has actually been
> verified. Claims about print time, filament weight, warping and key fit are
> marked as untested and MUST be replaced with measured values after a real
> print, or removed.

## Title

**Parametric Wave Wall Art — LAMELLA Panel Generator**

Searchable first ("wave wall art", "parametric", "panel"), product name second.

## One-line hook

> You are not downloading a wall panel — you are downloading the generator that
> makes them, at any size, with seams you cannot find.

## Description

**The problem.** Ribbed wave panels look superb and print badly. The popular
ones arrive as a bag of loose strips to glue down one at a time, or as square
tiles you are told to number on the back and line up by eye. Scale past one
build plate and the pattern breaks at every joint.

**The solution.** LAMELLA treats the whole artwork as one continuous
mathematical surface and *then* decides where to cut it. The field is evaluated
in global artwork coordinates, so the surface runs unbroken across every seam.
Fins are pitched globally and each tile holds a whole number of them, so a tile
edge always lands in the middle of a gap between fins — never through one.

Measured on exported geometry: the gap straddling a seam is **1.8860 mm**
against an interior gap of **1.8857 mm**. There is nothing there to see.

**What you actually get.**

- Six styles — Ripple, Flow, Vortex, Dune, Liquid, Interference — that are
  genuinely different surfaces, not the same wave at different amplitudes.
- A seed control that recomposes any style completely. Feature positions come
  from a low-discrepancy sequence, so seeds spread instead of clumping and
  every one composes.
- Any size from 80 mm to 1.6 m. Tiling, joints and mounting are worked out for
  you.
- Hidden dovetail keys that join tiles behind the panel with no glue, and in
  any order.
- Keyhole slots so a tile hangs straight onto a screw head.
- **No supports** — printed back-down the fins are a height field, so every
  layer is fully supported by the one below. That is a property of the shape,
  not a slicer setting.

**A real customizer.** The mathematics runs inside OpenSCAD, so every control
regenerates the geometry for real. This is not a fixed model with sliders
bolted on.

**Detail that matches your fins.** The generator measures how much its own
swirl compresses space and caps the surface detail against what your chosen fin
pitch can physically resolve. Choose coarse fins and it stays clean; choose fine
fins and it gives you more detail. You cannot accidentally ask it for a noisy,
jagged surface.

**Compatibility.** Tiles are capped at 172 mm for the A1 mini and 230 mm for
A1 / P1 / X1, with a custom option. Any printer of that build volume works —
nothing here is Bambu-specific beyond the bed presets.

**Hardware.** None for a single tile. Multi-tile pieces use printed dovetail
keys (also generated). Wall mounting needs two screws per tile.

**Limitations, honestly.**

- Vertical seams are invisible. **Horizontal seams are not** — a row seam
  crosses every fin and leaves a fine horizontal line. Prefer splitting into
  columns where you can; a panel up to one tile tall and any width has no
  visible seam at all.
- Fins are printed as standing walls, so a sideways knock loads them across
  the layers. This is wall art, not a shelf.
- A large flat backing is classic corner-lift geometry. Use a brim.
- Terracing is available as an advanced option but no preset uses it: it fights
  the fins and tends to read as digital error rather than contours.

## Print settings

| | |
| --- | --- |
| Orientation | As exported — back face on the plate, fins up. Do not rotate. |
| Supports | **None.** |
| Layer height | 0.2 mm |
| Walls | 2–3 |
| Infill | 10–15 % (the fins are thick; infill is what keeps the weight sane) |
| Brim | Recommended |
| Material | PLA (stiffer, crisper surface) or PETG (tougher if handled) |
| Nozzle | 0.4 mm; set the `nozzle` parameter if you use another size |

**Print time and filament: not yet measured.** A default 170 × 170 mm tile is
about 317 cm³ of solid volume; real filament is far lower because the slicer
fills the 6 mm fins with perimeters and infill. Slice it yourself before
committing to a large set — and reduce `max_relief` first if you want it
lighter, since material scales with it almost linearly.

## Assembly

1. Print one tile per cell, plus the **Joining keys** output.
2. Lay the tiles face down.
3. Drop a key into each pair of half-pockets bridging a seam.
4. Hang each tile on two screws using its keyhole slots.

Order does not matter — the keys are separate parts, so tiles never have to be
slid together in a sequence.

**Print the Fit coupon first.** It is a short strip of the real panel with one
real key pocket and a key, and it costs a few grams. If the key is tight, raise
`key_fit`; if loose, lower it.

## Search terms

wave wall art, parametric wall art, 3d wall panel, ribbed wall panel, fluted
wall panel, wall sculpture, modular wall art, customizable wall art, generative
art, wall decor, acoustic-look panel, slat wall art, large format wall art,
openscad customizer, seamless tiling

Deliberately **not** included: "acoustic panel", "sound diffuser", "sound
absorption". The geometry has not been analysed for acoustic performance and
must not be marketed as treatment.

## Image plan

1. **Hero** — assembled multi-tile Ripple panel on a wall, raking light, shot
   at three-quarters so the relief reads.
2. **Differentiator** — close-up across a seam with a caption pointing at it:
   the seam is in frame and invisible.
3. **Variants** — the six styles as one grid, showing what the customizer buys.
4. **Mechanism** — back of two tiles with a dovetail key going in, plus the
   keyhole slots.
5. **Scale** — the same design at 170 mm and at 600 mm, side by side.
6. **Print** — tiles on the plate in their exported orientation, captioned
   "no supports".

Hero must be a photograph of a real print, not a render.
