# LAMELLA FRAME — framed waveform relief

One piece. One print. No tiles, no keys, no glue.

A square framed panel of vertical fins whose depths follow a natural terrain
field — scattered peaks and hollows at three scales, gently swirled. Change the
seed and you get a different landscape.

This is the simple sibling of [`waveform-wall`](../../waveform-wall/docs/README.md),
which does large multi-tile artwork. If you want one framed piece off one plate,
use this.

## The eight controls

### Panel
| Control | Default | Range | What it does |
| --- | --- | --- | --- |
| `panel_size` | 170 mm | 100–250 | Outside edge including the frame. Keep ≤170 for an A1 mini, ≤240 for a 256 mm bed. |
| `relief_depth` | 18 mm | 6–40 | How far the tallest fins stand off the back. |
| `fin_pitch` | 7.0 mm | 4–14 | Fin spacing. Finer is more detailed and slower. |

### Design
| Control | Default | Range | What it does |
| --- | --- | --- | --- |
| `randomize` | Off | Off / On | Off repeats the seed exactly. On rolls a new landscape every render and prints the seed it used. |
| `seed` | 7 | 1–199 | Which landscape, when randomize is Off. |
| `texture` | 1.0 | 0.4–1.6 | Fine detail. Low is smooth and dune-like, high is craggier. |

### Frame
| Control | Default | Range | What it does |
| --- | --- | --- | --- |
| `frame_width` | 10 mm | 0–25 | Border width. **0 removes the frame.** |
| `frame_depth` | 11 mm | 4–50 | How far the frame stands off the back. |

**The one proportion worth understanding:** `frame_depth` versus `relief_depth`.
Set the frame *shallower* than the relief (the default: 11 against 18) and the
tallest peaks break out past it — it reads as a sculpture in a frame. Set it
deeper and the relief sinks into a box, because the average fin only stands
about 55 % as proud as the deepest one. Rendered side by side, 9–12 mm reads as
sculpture and 16–21 mm reads as an empty box.

## Printing

| | |
| --- | --- |
| Orientation | As exported — back flat on the plate, frame and fins up. Do not rotate. |
| Supports | **None.** Measured: the fins produce no downward-facing faces at all, and the frame narrows as it rises so it cannot overhang. The only unsupported spans in the whole part are the two keyhole ceilings, ≤15.4 mm. With `frame_width = 0` there are none at all. |
| Layer height | 0.2 mm |
| Walls | 2–3 |
| Infill | 10–15 % — the fins are thick, so infill is what keeps the weight sane |
| Brim | Recommended; a large flat back is classic corner-lift geometry |
| Material | PLA (crisper) or PETG (tougher) |

**Filament and time are not measured.** The default is about 342 cm³ of *solid*
volume; real filament is far lower because the slicer fills the fins with
perimeters and infill. Slice it before committing. `relief_depth` is the control
that moves material most.

## Hanging

Two keyhole slots are recessed into the back of the **side** rails — the side
rails run the full height, so the slot has room to drop onto a screw head. (A
vertical keyhole cannot fit in the top rail, which is only as tall as the frame
is wide.)

Keyholes need `frame_width` of about 9 mm or more. Below that they are omitted
automatically and the console says so — use adhesive strips on the flat back
instead. With `frame_width = 0` there is no frame and no keyhole.

## Testing status

**CAD-validated. Nothing has been printed.**

17/17 parameter matrix — every corner of all eight controls, both randomize
modes, with and without the frame. Every case watertight, one connected body,
inside its build volume. Support-freedom verified by measuring downward-facing
faces of the exported meshes.

Unverified: key fit, screw sizing, warping, fin strength, filament, print time.
