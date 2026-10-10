# Orbit Ball — dimensions for an Onshape model

**Status: research plus derived geometry. Nothing here was measured on a
physical toy, and nothing has been printed.** The outer envelope, the ball
count and the twist action are sourced from retail and wholesale listings.
The ball diameter, groove, wall and track path are **not published anywhere
that a search could reach**. They are derived, and checked by
`tools/orbitfit.py`. Labels in every table say which is which.

Target: the white, raised-diamond-texture "Orbit Ball" with a blue/teal track
and three steel balls. It is also sold as Track Pinball, Three Bead Orbit, and
Orbit Ball Fidget Cubes Top Spinning Toy. Brands include Innotech, ONCOFAN
(DIMI DM-17), Etokfoks, AHEYE, TRACYCY and EMPHASISY. The white-and-blue
diamond version is Walmart 3692433535 / 3651449451. The factory listing is
titled "Diamond Pattern Ball Track Gyroscope Magic Cube". A related US design
patent is D1056062 "Orbit ball toy" (filed 2021-12-15). Its drawings could not
be retrieved here, and a design patent carries no dimensions anyway.

![section](../previews/orbit-ball-section.png)
![track](../previews/orbit-ball-track.png)

## What the sources establish

| Fact | Value | Basis |
| --- | --- | --- |
| Envelope | 50 × 50 × 56 mm (1.96 × 1.96 × 2.2 in; 5 × 5 × 5.6 cm; 50.0 × 50.0 × 56.4 mm) | ~10 listings: ONCOFAN B09XN555KR / B0DH4P9345, Lowe's 8219706, eBay 306659652468, B0BLV43KYG, Etsy 4362748570, Alibaba 1600481553290, Made-in-China ctwj2018, B0DPDH7KY4. Many resellers copy one factory spec, so these are less independent than the count suggests. A 52 mm figure also circulates; one wholesaler labels 5.6 × 5.2 × 5.2 cm as *packing* size. |
| Balls | 3, ferrous ("steel ball", "iron beads") | EPROLO diamond-pattern listing ("three iron beads on the diamond surface"), eBay 235678383048 ("With 3 Balls", Blue & White), AHEYE B0981ZKYML ("Three Bead Orbit"), Autastic review ("3 balls into 3 different levels"). One listing says "aluminum bead". |
| Action | two halves twist; the balls roll along a grooved track; twisting "toggles"/"switches" the track and "creates new paths" | EMPHASISY B0DK36WK9V, Amazon Q&A Tx3ND6QIUJ2SE9Q, Autastic, Sensory Toolhouse "Bead Orbit" ("altogether or on 3 individual tracks"). |
| Balls visible, track at the surface | "silver-colored metal balls are visible between the [white diamond] segments" and "blue curved sections"; a ball can be "knock[ed] out of the track… very easy to put back in" | Etsy 4362748570 image caption, EPROLO, an Amazon reviewer. Each source is weak on its own, but they agree. |
| Body | ABS, matte raised-diamond texture | Walmart Innotech, Lowe's, Gear Elevation, Etsy |
| Joined | "unable to be disassembled" | Walmart 3254741685 |
| Mass | ~50 g per unit (1.76 oz) | ONCOFAN, B0BLV43KYG, EMPHASISY 4- and 8-pack totals (~50 g each), 18 kg / 360 pcs carton. Possibly including the retail box. Outliers: 23, 68 and 109 g. |

**No source states** the ball diameter, the wall, the groove depth or width,
the track path, the axle, or any clearance. A search in English and Chinese
(轨道球 / 钢珠 直径) and of patents and printable replicas found none.

## Why one Revolve cannot make this toy, and what can

Two parts that share a spherical outside can only rotate against each other if
the boundary between them is a circle about the twist axis. So the parting
line on the surface is a plain equator. **The S / yin-yang curve you see is
the track, not the split.** A track that changes topology when twisted cannot
be axisymmetric about the twist axis.

What *is* possible, and is used here, is a track of four semicircles on the
ball-centre sphere:

- Each semicircle lies in a vertical plane set `Track_Offset = Track_R/√2`
  from the twist axis. The planes face 45°, 135°, 225° and 315°.
- Each semicircle runs between two equator points 90° apart and crosses the
  equator vertically.
- The top half carries two of them and the bottom half the other two. The
  bottom half is **the same part flipped** 180° about X.
- At 0°/180° twist they form **one closed S / tennis-seam loop**. At 90°/270°
  they form **two separate loops**, which read as ∞ from the front.

That matches the evidence, which describes the track as "toggled", "switched"
or "split into individual tracks".

Each semicircle is a torus segment whose axis passes through the sphere
centre. So **each one is an ordinary Revolve cut**, about a 45° axis instead
of Z. The "track circles offset from the central axis" you asked about are
real: the groove circle sits `Track_Offset` from Z and `Track_Offset` above the
parting plane.

This track path is a reconstruction that fits every sourced fact. It is not a
copy of a drawing. The commercial part may use a different path, for example
three lobes for three separate loops. Either way, the groove section and
retention numbers below do not depend on the path.

## Onshape variable table

`S` = sourced, `D` = derived from S by formula, `E` = engineering choice
(changeable), `R` = reference/check only.

```
#Sphere_Dia   = 50 mm                                   // S  over the shell
#Overall_H    = 56.4 mm                                 // S  listing envelope (reference)
#Ball_Count   = 3                                       // S
#Ball_Dia     = 12 mm                                   // E  NOT sourced -- see "Ball diameter"
#Groove_Clr   = 0.3 mm                                  // E  radial, ball to groove
#Ball_Sink    = 3.5 mm                                  // E  ball centre below the shell surface
#Sphere_R     = #Sphere_Dia / 2                         // D  25
#Groove_R     = #Ball_Dia / 2 + #Groove_Clr             // D  6.3   (groove dia 12.6)
#Track_R      = #Sphere_R - #Ball_Sink                  // D  21.5  ball-centre sphere
#Track_Offset = #Track_R / sqrt(2)                      // D  15.203 arc radius = plane offset = apex height
#Floor_R      = #Track_R - #Groove_R                    // D  15.2  groove floor radius
#Groove_Depth = #Sphere_R - #Floor_R                    // D  9.8   below the surface
#Mouth_W      = 2 * sqrt(#Sphere_R^2 - ((#Track_R^2 + #Sphere_R^2 - #Groove_R^2) / (2 * #Track_R))^2)
                                                        // R  11.225 -> 0.39 mm/side snap
#Gap          = 0.3 mm                                  // E  visible seam; each face relieved #Gap/2
#Land_R       = 11 mm                                   // E  faces touch only inside this radius
#Axle_Clr     = 0.25 mm                                 // E  radial, on the M4 axle
#Bore_Dia     = 4 mm + 2 * #Axle_Clr                    // D  4.5
#Pocket_AF    = 7.2 mm                                  // E  hex, takes M4 nylock (7.0 AF) and M4 SHCS head (Ø7.0)
#Pocket_Depth = 8 mm                                    // E  sized for an M4x40 bolt
#Magnet_R     = 7.5 mm                                  // E  4 detent magnets per face, at 45°+90°k
#Magnet_Hole  = 4.2 mm                                  // E  for Ø4 x 2 mm magnets
#Magnet_Depth = 2.1 mm                                  // E
#Rim_Chamfer  = 0.4 mm                                  // E  beats elephant's foot on the parting face
#Nub_H        = 0 mm                                    // E  3.2 mm makes 56.4 pole to pole -- see below
```

All values regenerate from `#Ball_Dia`, `#Ball_Sink` and `#Groove_Clr`. Run
`python3 tools/orbitfit.py --ball <d> --sink <s>` before changing either of
the first two. Retention is sensitive: each 0.25 mm of sink moves the snap
interference by about 0.14 mm.

| `#Ball_Sink` (12 mm ball) | 3.0 | 3.25 | **3.5** | 3.75 | 4.0 |
| --- | --- | --- | --- | --- | --- |
| mouth width | 11.73 | 11.50 | **11.22** | 10.92 | 10.56 |
| snap interference / side | 0.14 (falls out) | 0.25 (PLA) | **0.39** (PETG/ABS) | 0.54 | 0.72 (won't go in) |
| ball proud of shell, max | 4.03 | 3.61 | **3.24** | 2.90 | 2.59 |

## Answers to the three questions

**1. Ball diameter: 12 mm, as an engineering estimate, not a sourced figure.**
No listing, Q&A, review, patent or wholesale page in any language states it.
`orbitfit --sweep` shows the geometry works for any ball from 6 to 12.7 mm, so
geometry cannot decide. Two weaker clues lean towards the 12–12.7 mm end:

- **Mass.** A 2 mm-wall ABS body computes to ~23.5 g. Three 12 mm balls add
  21.3 g, for 44.8 g; three 12.7 mm balls give 48.4 g. Both are near the
  ~50 g listed. With 10 mm balls the total is 36.5 g, which only reaches 50 g
  if the listed weight includes ~13 g of box. That is plausible, which is why
  this clue is only a lean.
- **Envelope.** At the 3.5 mm sink, 12 mm balls stand 3.24 mm proud.
  50 + 2 × 3.24 = 56.5 mm, close to the 56.4 mm listed. That is consistent
  with, but not proof of, the 56 mm being measured across two balls rather
  than across pole tips.

12 mm is also a stock metric ball (钢珠) for the Chinese factories that make
this toy, and is easy to buy. **If you buy ½″ balls, set `#Ball_Dia = 12.7 mm`.**
Keep the same snap at `#Ball_Sink = 3.67 mm`. Everything else follows.

**2. Sphere profile.**
- OD: **50 mm** (sourced).
- Wall: **no published value**. An injection-moulded ABS part of this size
  would normally be ~2 mm, and that figure is used only for the mass check.
  For FDM, print it solid-walled (4 perimeters, 15 % infill). There is ≥ 4.9 mm
  of material between any groove and the pole pocket.
- Track depth: the groove floor is **9.8 mm** below the surface.
- **The ball does not sit 50 % deep.** A ball sunk exactly to its equator has a
  mouth as wide as itself and falls out. Here the ball centre is **3.5 mm below
  the surface**, so ~79 % of the ball is below the shell line. It is held by
  lips 11.22 mm apart (0.39 mm per side), and it stands 2.2–3.2 mm proud,
  which is what "beads on the diamond surface" describes.

**3. "S" curve and gap.**
- Track circle offset from the central axis: **15.203 mm** (`#Track_Offset`).
  The same value is the arc radius and the apex height above the parting
  plane.
- The parting line is flat (the equator), not an S.
- Clearances:
  - Visible seam: **0.3 mm** (0.15 mm relief per face; the thrust land sets
    the spacing).
  - Axle: **0.25 mm radial**.
  - Ball to groove: **0.3 mm radial**.
- On 0.2 vs 0.5 mm: 0.2–0.3 mm is right for parts assembled after printing.
  0.5 mm is a print-in-place figure and would make this joint wobble.
- The commercial moulded clearances are unknown.

## Building it in Onshape

1. **Variables**: paste the table into a Variable Studio, or as Variable
   features at the top of the Part Studio.
2. **Body sketch** on the *Front* plane (XZ):
   - A construction line on Z.
   - Bore line `x = #Bore_Dia/2` from `z = 0` up to the arc.
   - Bottom edge from `x = #Bore_Dia/2` to `#Land_R` at `z = 0`, a riser to
     `z = #Gap/2`, then out to the arc.
   - Arc centred on the origin, radius `#Sphere_R`.
   - **Revolve**, full, about Z. This gives the top half.
3. **Track plane**: Plane → *Line angle*, through the Z construction line,
   45° from Front.
4. **Track sketch** on that plane:
   - A construction line through the origin, perpendicular to Z. This is the
     45° axis.
   - A circle of radius `#Groove_R`, centred `#Track_Offset` from that line and
     `#Track_Offset` from Z, on the upper side.
   - **Revolve → Remove**, *Symmetric*, **180°**, about the 45° line. The cut
     ends exactly on the parting plane.
5. **Circular pattern** the cut about Z: 2 instances, 360°.
6. **Pole pocket**:
   - Sketch on a plane offset `#Sphere_R` up from Top.
   - Regular hexagon, inscribed diameter `#Pocket_AF`.
   - Extrude Remove `#Pocket_Depth`.
7. **Magnet holes**:
   - Sketch on Top: 4 circles of diameter `#Magnet_Hole` at radius
     `#Magnet_R`, at 45°, 135°, 225° and 315°.
   - Extrude Remove `#Magnet_Depth` into the half.
   - Polarity: all N out on one half, all S out on the other. The halves are
     then the same part but still attract at every 90°.
8. **Chamfer** the outer rim edge of the parting face by `#Rim_Chamfer`.
9. **Bottom half**: Transform → *Copy part* → Rotate 180° about X. The lower
   arcs come out in the correct planes automatically.
10. **Balls**: three Ø`#Ball_Dia` spheres on the track centre-line, for the
    assembly.
11. **Optional extras**:
    - Pole caps that plug the hex pockets. Make them flush, or proud by
      `#Nub_H = 3.2 mm` for a spin tip and the listed 56.4 mm length.
    - A diamond knurl. It is cosmetic, and its size is unknown. Onshape has
      no native knurl, so a slicer texture or fuzzy skin is the practical
      route.

Hardware:
- 1 × M4 × 40 socket-head cap screw (ISO 4762), with the head in the top
  pocket.
- 1 × M4 nylon-insert lock nut (DIN 985, 5 mm tall), in the bottom pocket.
  Snug it until twisting feels right.
- 8 × Ø4 × 2 mm magnets.
- 3 × steel balls.

Print each half parting-face down, with no supports. The groove lips near the
arc apex are short overhangs. If they droop, the snap tightens; lower
`#Ball_Sink` by 0.1–0.2 mm. Use PETG for the 0.39 mm snap. For PLA, use
`#Ball_Sink = 3.25` (0.25 mm). Press the balls in after assembly.

## Checks (`python3 tools/orbitfit.py --mass --sweep`)

```
checks:
  PASS  ball captured: mouth < ball      11.22 < 12.00
  PASS  snap interference per side       0.39 mm            0.25-0.60
  PASS  ball proud of shell (max)        3.24 mm            > 0
  PASS  track revolve: T > groove r      15.20 > 6.30
  PASS  wall between separate arcs, 1 loop 17.81 mm         >= 2.0
  PASS  wall between separate arcs, 2 loops 17.81 mm        >= 2.0
  PASS  land clear of groove floor       11.00 < 15.20      1 mm margin
  PASS  pole pocket clear of grooves     8.90 > 4.16
  PASS  rim land between crossings       28.0 mm            >= 10
  PASS  loops at twist 0 / 90 deg        1 / 2              1 / 2
```

Twist misalignment that leaves a 0.25 mm step at a crossing: 0.67°. That is
why the halves index on magnets rather than by eye.

## Not verified

- Ball diameter, wall, groove and track path of the real toy. All derived.
- Whether the 56 mm length comes from pole tips or from protruding balls.
- Whether the commercial part uses this four-arc path or a three-lobe variant.
- Snap force, roll feel and magnet pull on the balls. Nothing has been
  printed.

**Five measurements on a real unit would replace most of this:**
1. Ball diameter, or weigh all three: 21.3 g means 12 mm, 25.3 g means ½″.
2. OD across the shell, avoiding the balls.
3. Pole-to-pole length.
4. How far a ball stands proud. This gives `#Ball_Sink`.
5. Clicks per revolution: 4 means this 90° layout, 6 means a three-lobe path.
