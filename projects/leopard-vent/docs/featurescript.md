# LEOPARD VENT for Onshape — FeatureScript

The same venting / lightening pattern as the OpenSCAD generator, as an Onshape
custom feature: pick one or more planar faces, and it cuts irregular 3-, 4- or
6-sided holes into them with an exact rib between every pair.

File: [`featurescript/leopard_vent.fs`](../featurescript/leopard_vent.fs)

![Six face shapes](../previews/featurescript_faces.png)

*Rendered from `tools/fsmirror.py`, the Python mirror of the feature's
geometry — not a screenshot from Onshape. See "What has and has not been
tested" below.*

## Status — read this first

**The geometry is tested. The Onshape side has never been run.** I had no
Onshape access while writing it. Here is what that means in practice:

- Every Onshape call it makes was checked by name and argument against the
  FeatureScript standard library source, version 2960 (May 2026).
- All the maths — cells, outline handling, clipping, rounding, the exact lines
  and arcs it sketches — was executed outside Onshape and measured. See below.
- Nobody has pasted it into a Feature Studio yet. The first run may still turn
  up a mistake of the kind only Onshape can report. If it does, the Feature
  Studio's error panel gives a line number; that plus the message is enough to
  fix it.

## Installing

1. In any Onshape document, create a **Feature Studio**.
2. Replace its contents with `leopard_vent.fs`. If your Feature Studio opened
   with a newer `FeatureScript` / `import` version on its first two lines,
   keep the newer pair. 2960 is just the version this file was checked
   against.
3. In a Part Studio, add the feature to the toolbar through **Custom
   features**, choosing the document and Feature Studio you used. It appears
   as **Leopard vent**.

## Controls

| Control | Default | What it does |
| --- | --- | --- |
| Faces | — | One or more planar faces of solid parts. Each gets its own pattern. |
| Cell shape | 4 sides | 4 sides: jittered grid. 3 sides: jittered triangle web. 6 sides: uneven Voronoi cells, closest to real leopard print. |
| Cell size | 14 mm | Average cell width. Every shape is scaled so a cell has about the area of a square this wide. |
| Rib thickness | 2 mm | The web between neighbouring holes — guaranteed minimum. Down to 0.1 mm is allowed for laser or CNC; for FDM, stay at 0.8 mm (two extrusion widths) or more. |
| Border | 5 mm | Solid band kept along every edge of the face, including round any holes already in it. Raised to the rib thickness if set below it. |
| Irregularity | 0.7 | 0 is a regular grid, triangle web or honeycomb; 1 is as uneven as the cells can get while staying valid. |
| Hole corner radius | 1 mm | Rounds every hole corner, as true arcs. 0 leaves them sharp. |
| Smallest hole kept | 4 mm | A hole that cannot hold a circle this wide is left solid. |
| Seed | 1 | Which arrangement. |
| Fit cells to the face | on | Stretches the cells slightly so whole cells fill the face's bounding rectangle, with edge holes running straight along it. Off: the pattern runs past the face and is cut off at the border. |
| Hole type | Through | Through the part, or a pocket of a set depth. **Through cuts everything of that part beneath each hole** — a boss or rib under the face gets cut too. Use Pocket to stop short of it. |
| Pocket depth | 2 mm | Pocket only. Measured from the face. |
| Pattern direction | — | Optional straight edge to align the pattern with. Left empty, it follows the face's longest straight edge — which is what lets a rectangular face be fitted exactly. |

When it finishes, the feature reports the hole count and open area (holes over
face area). It also says when the corner radius or smallest hole was limited.
As in the OpenSCAD version, those two are capped at 0.4 and 0.8 of the nominal
hole width, because past that whole cells start to vanish.

## How it handles the face outline

The OpenSCAD version crops the pattern with 2D booleans. Onshape has no
dependable way to shrink a face's outline by the border: offsetting a boundary
inward fails as soon as the border is bigger than one of the outline's
fillets. So the outline is handled in maths instead:

- Each boundary edge is sampled into chords, at most 0.005 mm off a curve,
  with the face kept on the left — so the outer loop runs one way, holes in
  the face the other, and the feature can tell them apart.
- Every hole is a convex polygon. It is clipped by the boundary chords near
  it, each moved in by the border (plus that 0.005 mm). That is **exact for a
  convex outline** — rectangles, rounded rectangles, circles.
- On an outline with **inside corners** (an L-shape, a notch), only chords
  facing the hole's centre are applied. Near the corner itself this trims
  holes a little more than strictly needed, never less: there is a solid
  block under the notch in the picture above.
- **Holes already in the face** (screws, slots) are kept clear with one
  straight cut per hole, chosen from several candidate directions to keep the
  most of it. Exact beside a round hole, and alongside the straight sides of a
  slot; conservative at a slot's rounded ends.

Then each hole's polygon is sketched as its edges pushed out by the corner
radius, joined by arcs of that radius. That is the exact rounded shape, not an
approximation. The arc and line endpoints are computed by the same expression,
so every loop closes exactly. All holes on a face go into one sketch, are
extruded together and subtracted in one boolean, and the sketch is deleted.

## What has and has not been tested

Reproduce with:

```bash
python3 tools/fsmirror.py check        # the geometry, measured
python3 tools/fsmirror.py crosscheck   # the .fs file's own code, against it
```

**`fsmirror.py check` — the geometry is right.** `tools/fsmirror.py` is a
Python mirror of the feature's maths, function for function. `check` runs nine
test faces: rectangle, rounded rectangle, circle, plate with four screw holes,
plate with a big centre hole, plate with a slot, L-shape, notched plate, and
ring. On each it runs 3 shapes × 9 settings × 3 seeds — **729 cases** — and
measures every hole with shapely against the *true* outline (real circles, not
the chords the feature uses). It checks:

- the thinnest web between any two holes;
- the closest any hole comes to any edge, inner loops included;
- that no hole leaves the face;
- the smallest hole.

Result: **729/729 pass**, to 1e-6 mm: no web thinner than the rib, no hole
nearer than the border to any edge or inner loop, none outside the face.
Default settings on each face (rib 2 mm, border 5 mm, smallest hole 4 mm):

```
  rect_120x80     QUAD holes=40   rib=2.0000 border=5.0000 smallest=8.719 open=61.3%
  rect_120x80     TRI  holes=44   rib=2.0000 border=5.0000 smallest=5.011 open=56.8%
  rect_120x80     HEX  holes=45   rib=2.0000 border=5.0000 smallest=5.547 open=61.0%
  rounded_rect    QUAD holes=40   rib=2.0000 border=5.0050 smallest=8.719 open=61.6%
  rounded_rect    TRI  holes=44   rib=2.0000 border=5.0050 smallest=5.007 open=57.1%
  rounded_rect    HEX  holes=45   rib=2.0000 border=5.0050 smallest=5.543 open=61.3%
  circle_d100     QUAD holes=40   rib=2.0000 border=5.0057 smallest=4.472 open=57.0%
  circle_d100     TRI  holes=35   rib=2.0000 border=5.0056 smallest=4.032 open=56.4%
  circle_d100     HEX  holes=37   rib=2.0000 border=5.0056 smallest=5.055 open=61.6%
  rect_4_screws   QUAD holes=48   rib=2.0000 border=5.0000 smallest=4.877 open=57.3%
  rect_4_screws   TRI  holes=43   rib=2.0000 border=5.0000 smallest=5.757 open=55.8%
  rect_4_screws   HEX  holes=45   rib=2.0000 border=5.0000 smallest=4.459 open=59.7%
  plate_big_hole  QUAD holes=54   rib=2.0000 border=5.0000 smallest=4.679 open=57.0%
  plate_big_hole  TRI  holes=56   rib=2.0000 border=5.0000 smallest=5.065 open=52.2%
  plate_big_hole  HEX  holes=56   rib=2.0000 border=5.0000 smallest=4.829 open=57.3%
  plate_slot      QUAD holes=34   rib=2.0000 border=5.0000 smallest=8.719 open=53.4%
  plate_slot      TRI  holes=44   rib=2.0000 border=5.0000 smallest=4.643 open=49.8%
  plate_slot      HEX  holes=42   rib=2.0000 border=5.0000 smallest=4.438 open=51.8%
  l_shape         QUAD holes=31   rib=2.0000 border=5.0000 smallest=4.154 open=52.3%
  l_shape         TRI  holes=31   rib=2.0000 border=5.0000 smallest=4.865 open=49.6%
  l_shape         HEX  holes=30   rib=2.0000 border=5.0000 smallest=4.611 open=53.9%
  notched         QUAD holes=25   rib=2.0000 border=5.0000 smallest=7.842 open=52.8%
  notched         TRI  holes=25   rib=2.0000 border=5.0000 smallest=6.016 open=47.2%
  notched         HEX  holes=28   rib=2.0000 border=5.0000 smallest=4.012 open=45.9%
  annulus         QUAD holes=43   rib=2.0000 border=5.0001 smallest=4.042 open=51.5%
  annulus         TRI  holes=46   rib=2.0000 border=5.0001 smallest=4.417 open=50.5%
  annulus         HEX  holes=47   rib=2.0000 border=5.0001 smallest=4.469 open=51.2%
```

The border reads a few microns over 5 on curved outlines. That is the
0.005 mm chord allowance, added on the safe side.

**`fsmirror.py crosscheck` — the `.fs` file does the same thing.**
`tools/fsinterp.py` is a small interpreter for the subset of FeatureScript the
feature's maths is written in. `crosscheck` runs the actual functions in
`leopard_vent.fs`: outline handling, cells, every hole, hole areas, and the
exact `skLineSegment` / `skArc` calls `drawHole` makes. It requires the
answer to match the mirror point for point at every stage.

Result: **189/189 cases, 9,791 holes, identical.** That run is where two
mistakes in the first port were caught. One was a constant I had mistyped after its
tenth digit, now computed in the code instead. The other turned out
to be harmless: the same polygon listed from a different corner.

**Not tested — needs Onshape:**

- That the file loads at all.
- That a solid's planar face reports its normal pointing out of the material
  (standard B-rep convention). The cut runs against that normal; if it were
  reversed, the cutters would miss the part.
- That Onshape finds the sketch regions from loops of lines and arcs whose
  endpoints match exactly but carry no coincidence constraints.
- Speed with many holes. Each hole is one line and one arc per corner —
  typically 6 to 16 sketch entities — so a few hundred holes is a few
  thousand entities in one sketch.
- Selecting several faces of one part, and faces on opposite sides of a part.

## Same pattern as the OpenSCAD version

Both use the same hash, lattices and cell construction. On a matching
rectangle they produce the same pattern for the same seed. Checked: on a
120 × 80 face with default settings, the mirror gives the same 40 holes and the
same 8.719 mm smallest hole that `ribcheck.py` measured on the OpenSCAD
export. A design can be roughed out in either and carried to the other.
