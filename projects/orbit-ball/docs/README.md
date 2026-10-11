# Orbit Ball — dimensions for an Onshape model

**Status: research plus derived geometry. Nothing here was measured on a
physical toy, and nothing has been printed.**

What is sourced and what is not:
- **Sourced** from retail and wholesale listings: the outer envelope, the ball
  count and the twist action.
- **Not found**: the ball diameter, groove, wall and track path. The search
  was not exhaustive:
  - it ran ~180 listing queries in English and Chinese;
  - its query budget ran out before the patent, teardown-video and
    printable-replica searches;
  - Taobao and 1688 detail pages were not reachable.

Those missing values are derived here and checked by `tools/orbitfit.py`.
Every value below is labelled with which of these it is.

Two review rounds went into this document. In round 1, five independent
reviewers attacked numbers, kinematics, printability, the Onshape steps and
the evidence. In round 2, two more checked the fixes. Their findings are
folded in.

![section](../previews/orbit-ball-section.png)
![track, two lobes](../previews/orbit-ball-track.png)
![track, three lobes](../previews/orbit-ball-n3-track.png)

## Which toy

The target is the white, diamond-pattern "Orbit Ball" with a blue/teal track
and three metal balls. The white-and-blue diamond version is Walmart
3692433535 / 3651449451 (Innotech, "Pattern: Diamond").

Listings that probably share its mould. This is likely from matching sizes
and copy, but not confirmed:

| Seller or brand | Name / model | Note |
| --- | --- | --- |
| ONCOFAN | DIMI DM-17, "track pinball" | |
| Etokfoks | | |
| AHEYE | "Three Bead Orbit" | |
| Gear Elevation | | |
| Made-in-China wholesalers | "Bead Orbit" | |
| EPROLO (a dropship platform) | "Diamond Pattern Ball Track Gyroscope Magic Cube" | |
| TRACYCY | | possibly a different mould (listed 2.32 × 2.24 × 2.2 in) |
| EMPHASISY | | possibly a different mould |

Your alias "Spiral Orbit Marble Puzzle Ball" is also used by Curious Minds
for a 1.75 × 2 in one-piece toy, which may be a different product.

US design patent D1056062 "Orbit ball toy" (filed 2021-12-15) may show this
family:
- Its 10 drawing views could confirm or rule out the track path used here.
  They were not retrieved; the USPTO PDF is at
  `image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/D1056062`.
- It gives no dimensions.
- It cites a TRACYCY listing as prior art, so it is not confirmed to show the
  diamond version.

## What the sources say

| Fact | Value | Basis and strength |
| --- | --- | --- |
| Envelope | ≈ 50 × 50 × 56 mm (1.96 × 1.96 × 2.2 in; 5 × 5 × 5.6 cm) | Most listings: ONCOFAN B09XN555KR / B0DH4P9345, Lowe's 8219706, B0BLV43KYG, Etsy 4362748570, Alibaba 1600481553290, Made-in-China ctwj2018. Many resellers copy one supplier spec, so these are not independent. |
| Other envelope figures | 52 × 52 × 56 · 52 × 56 × 56 · 50.8–51 · 56.4 × 50 × 50 mm | 52 × 52 × 56: Alibaba Shantou Yaxin "product size" and Amazon UK (Tombo calls it *packing* size). 52 × 56 × 56: EPROLO diamond listing, Amazon.sa. 50.8–51: EMPHASISY, WUQID. 56.4 × 50 × 50: B0DPDH7KY4, which a second search could not find again. |
| Shape | Also described as "polyhedron ball", "Cube ball", "rounded corners", "arch-shaped grip" | Innotech, Autastic, listing copy. The body **may not be a true sphere**; this model assumes it is. |
| Balls | **3**, metal | EPROLO ("three iron beads on the diamond surface"); eBay 235678383048 ("With 3 Balls", though that could mean three toys); AHEYE ("Three Bead Orbit"); Autastic ("3 balls into 3 different levels"). Against: one Q&A guess says 1, and generic copy says "the metal ball". |
| Ball material | **Unresolved**: steel or aluminium | "plastic + steel ball" (ONCOFAN) and "iron beads" (EPROLO) against "aluminum bead" (EMPHASISY, Coolbe and others) |
| Action | Two halves twist; the balls roll along a grooved track; twisting "switches" or "toggles" the track and "creates new paths" | EMPHASISY B0DK36WK9V, Amazon Q&A Tx3ND6QIUJ2SE9Q, Autastic, "polyhedron ball" listing copy |
| Track count | "altogether or on **3 individual tracks**"; "3 balls into 3 different levels" | Sensory Toolhouse "Bead Orbit" (the same family as the 5 × 5 × 5.6 cm wholesale "Bead Orbit"); Autastic review |
| Balls visible at the surface | "metal balls visible between the [white diamond] segments", "blue curved sections"; a ball can be "knock[ed] out of the track" | Etsy auto-generated image caption, EPROLO machine-translated summary, one Amazon reviewer on an unidentified listing. **All weak, none a photo.** You described an *internal* track. This design assumes the surface version. |
| Body | ABS; matte, "Pattern: Diamond" | ABS: Innotech, Lowe's, Gear Elevation, Etsy. Pattern: Innotech. "Raised" is from your description. Etsy also lists silicone (perhaps the blue track); one wholesaler says PVC. |
| Assembly | "unable to be disassembled" | Walmart 3254741685 |
| Mass | ~50 g, given as 0.05 kg / 1.76 oz | Rounded (45–55 g); possibly a template value or boxed weight. Other single-unit figures: 23, 41, 53, 68, ~100, 109 g. |
| Magnets | some related listings say "magnetic" | Amazon.sa B0CFXXL9BT, Alibaba 1600263193337. Role unknown. |

## Why a single Revolve cannot make it, and what can

**The rule.** Two parts with a shared spherical outside can only twist
against each other if the boundary between them is a circle about the twist
axis. This model puts that circle on the equator, so the parting face is
flat. **The S / yin-yang you see is the track, not the split.** A track that
changes when twisted cannot be axisymmetric about the twist axis.

**The construction.** The track is `2·Lobes` semicircles on the ball-centre
sphere:
- Each joins two equator crossings `180/Lobes` degrees apart, crossing the
  equator vertically.
- Each lies in a vertical plane `Track_Offset` from the twist axis, with
  radius and apex height `Arc_R`.
- The top half carries `Lobes` of them. The bottom half carries the rest, and
  is the same body flipped 180° about X.
- At 0° twist they make **one loop**. At `180/Lobes` degrees they make
  **`Lobes` separate rings**.
- Each semicircle is a torus segment whose axis runs through the sphere
  centre. So each groove is an **ordinary Revolve cut about an axis lying in
  the parting plane**.
- These are the "track circles offset from the central axis" you asked about:
  the circle sits `Track_Offset` out along that axis and `Arc_R` above it.

| | `Lobes = 2` (**recommended**) | `Lobes = 3` |
| --- | --- | --- |
| Looks like | the classic yin-yang S (each lobe half the diameter) | a wave round the equator; also an S when viewed face-on to a crossing |
| Twist to split | 90° → 2 rings | 60° → **3 rings, one per ball** |
| Fits | your S / yin-yang description | the two sources that count tracks |
| Track geometry checks | all pass; walls ≥ 17 mm | all pass; walls ≥ 8.5 mm |
| Magnet detent | works: ball pull 3 % of its weight | **does not work with steel balls** (below) |

**Why the magnet detent fails with three lobes.** The two symmetric magnet
positions are on the arc axes or at the crossings. On the arc axes, magnets
either pull the balls with 12–60 % of their weight at the arc apexes, or sit
so far in that they no longer index (`orbitfit --lobes 3 --magnet-r …`). The
crossings are worse: that is where balls already jam. A 3-lobe build needs a
mechanical detent (for example a spring plunger into notches), which is not
designed here.

**This path is a reconstruction, not a copy of a drawing.** I chose it
because it reproduces the sourced behaviour, makes each groove a plain
Revolve, and gives your yin-yang. Another plausible layout is three stacked
latitude rings ("levels") joined by gaps that line up when twisted; that is
not modelled.

What does and does not depend on the path:
- The groove section, retention and joint numbers hold for any path.
- `Track_Offset` and `Arc_R` depend on the path.

## Onshape variables

How to enter them:
- One variable per row in a Variable Studio, inserted with *Variable table →
  Insert Variable Studio*. Or use Variable features above the first feature
  that uses them.
- Names have **no `#`**. Write `#` only when referring to a variable.
- Set the type to Length, Angle or Number; put the basis in the Description.

Basis: **S** sourced · **D** derived · **E** engineering choice ·
**R** reference.

| Name | Expression | Value | Basis |
| --- | --- | --- | --- |
| `Sphere_Dia` | `50 mm` | 50 | S/D listing width (49.8–52), assumes a true sphere |
| `Lobes` | `2` | 2 | E (see above) |
| `Ball_Count` | `3` | 3 | S |
| `Ball_Dia` | `12 mm` | 12 | **E, not sourced** (see "Ball diameter") |
| `Groove_Clr` | `0.3 mm` | 0.3 | E. Radial clearance, steel ball to printed groove |
| `Ball_Sink` | `3.9 mm` | 3.9 | E. Ball centre below the shell |
| `Lip_Fillet` | `0.3 mm` | 0.3 | E. Modelled on the lip; with Ball_Sink it sets retention |
| `Sphere_R` | `#Sphere_Dia / 2` | 25 | D |
| `Groove_R` | `#Ball_Dia / 2 + #Groove_Clr` | 6.3 | D. Groove Ø12.6 |
| `Track_R` | `#Sphere_R - #Ball_Sink` | 21.1 | D. Ball-centre sphere |
| `Track_Angle` | `90 deg / #Lobes` | 45° | D. Track sketch plane, measured from Front |
| `Track_Offset` | `#Track_R * cos(#Track_Angle)` | **14.920** | D. Arc-plane offset from Z (sketch u) |
| `Arc_R` | `#Track_R * sin(#Track_Angle)` | **14.920** | D. Arc radius = apex height (sketch v) |
| `Floor_R` | `#Track_R - #Groove_R` | 14.8 | D. Groove floor, 10.2 below the shell |
| `Mouth_W` | `2 * sqrt(#Sphere_R^2 - ((#Track_R^2 + #Sphere_R^2 - #Groove_R^2) / (2 * #Track_R))^2)` | 10.709 | R. Sharp-edge mouth; the filleted lips open to 11.28 |
| `Bore_Dia` | `5.8 mm` | 5.8 | E. Undersize on purpose; drill to 6.0 (6.1 if the tube is tight) |
| `Pocket_Dia` | `9.6 mm` | 9.6 | E. Round: head + washer, and the cap seats |
| `Nut_AF` | `7.3 mm` | 7.3 | E. Hex, nut-end half only (DIN 985 M4 is 7.0 AF) |
| `Pocket_Depth` | `9 mm` | 9 | E. Pole to the floor the sleeve stands on |
| `Seat_Depth` | `3.5 mm` | 3.5 | E. Round cap seat at both poles (pole to z = ±21.5) |
| `End_Play` | `0.3 mm` | 0.3 | E. Sleeve longer than the two halves |
| `Sleeve_L` | `2 * (#Sphere_R - #Pocket_Depth) + #End_Play` | 32.3 | D. **Cut to measured halves + 0.25 ± 0.05** (see Assembly) |
| `Magnet_R` | `20 mm` | 20 | E. Lobes = 2 only |
| `Magnet_Hole` | `4.2 mm` | 4.2 | E. Ø4 × 2 mm N42 discs |
| `Magnet_Depth` | `2.6 mm` | 2.6 | E. 2.0 magnet + 0.1 glue + 0.5 recess, so the magnet faces are 1.0 apart |
| `Lead_In` | `1 mm` | 1 | E. 45° chamfer where the grooves meet the parting face |
| `Rim_Chamfer` | `0.5 mm` | 0.5 | E. 1 mm V seam |
| `Nub_H` | `0 mm` | 0 | E. 2.95 on **both** caps reaches 55.9 pole to pole, if the listed length is on the twist axis |

For `Lobes = 3`: `Track_Offset` = 18.273 and `Arc_R` = 10.550; the magnet
detent does not apply.

Before changing `Ball_Dia`, `Ball_Sink`, `Lip_Fillet`, `Lobes` or
`Magnet_R`, run:

```
python3 tools/orbitfit.py --ball … --sink … --fillet … --lobes … --magnet-r … --magnets
```

Copy its "Magnet radius" line into `Magnet_R`. For a 12.7 mm ball (sink 4.07)
or an 11 mm ball (sink 3.66), the 2-lobe magnet radius stays at 20.
Retention is sensitive to the sink:

| `Ball_Sink` (12 mm ball, 0.3 fillet) | 3.8 | **3.9** | 4.0 |
| --- | --- | --- | --- |
| Retention per side | 0.31 | **0.36** | 0.42 |
| Ball proud of shell | 1.9–3.0 | **1.8–2.9** | 1.7–2.7 |

## Answers to your three questions

### 1. Ball diameter

**I cannot give you the specific figure, because no source that the search
reached states it.** That covers every listing, Q&A, review and wholesale
page in English or Chinese. Anyone quoting 11, 12 or 12.7 mm without
measuring a unit is guessing.

What the evidence allows:
- **Geometry does not decide it.** Balls from 6 to 12.7 mm pass every 2-lobe
  check (`orbitfit --sweep`).
- **Mass leans, weakly, towards the larger sizes.** The ~50 g figure is
  reached by a moulded ABS body with these walls:

  | Ball | 2 lobes | 3 lobes |
  | --- | --- | --- |
  | 12–12.7 mm | ~2.5 mm | 2.5–3 mm |
  | 11 mm | ~3 mm | ~3.5 mm |
  | 10 mm | ~3.5 mm | ~4 mm |
  | 6–8 mm | ~5 mm | ~5 mm |

  Typical moulded toy walls are 2–2.5 mm, which favours 12–12.7 mm. But the
  wall is unknown, and each 1 mm of wall adds ~9 g, as much as going from
  10 mm to 12 mm balls. The listed weight is ±5 g and may include a box. A
  separate blue insert would push the answer smaller.
- **The envelope tells you nothing.** How far the balls stand proud is set by
  `Ball_Sink`, a design choice. Balls also cannot add to the pole-to-pole
  length: the highest ball point is below the pole.

**Design value: `Ball_Dia = 12 mm`.**
- It sits in the 10–12.7 mm band that the weight and proportions allow.
- It is stock; so are 10, 11 and 12.7 mm, so that is convenience, not
  evidence.
- For ½″ balls set 12.7 mm and `Ball_Sink = 4.07`; for 11 mm set
  `Ball_Sink = 3.66`. Both keep 0.36 mm/side retention.

### 2. Sphere profile

- **OD: 50 mm.** This is the listing width (52 mm in some listings). It was
  not measured on a bare shell.
- **Wall: no published value.** Moulded ABS toys are usually 1.5–2.5 mm; that
  figure is used only in the mass estimate.
- **For FDM:** 4 perimeters (≥ 1.6 mm), 15 % infill.
  - Body ~28 g, balls 21.3 g, hardware ~11 g: **about 61 g assembled**.
  - Groove to pocket is ≥ 3.8 mm with 12 mm balls (3.4 mm with ½″).
- **Groove depth: the floor is 10.2 mm below the shell.** This follows from
  the 12 mm / 3.9 mm choices, not from the commercial toy.
- **Ball seating, in this design: not 50 %.** An open groove sunk to the
  ball's equator has a mouth as wide as the ball, and the ball falls out.
  - The centre sits 3.9 mm below the shell, so 82 % of the diameter (92 % of
    the volume) is inside the shell sphere.
  - Filleted lips open to 11.28 mm (sharp-edge mouth 10.71), which holds the
    ball with 0.36 mm per side.
  - It stands 1.8–2.9 mm proud.

  How the commercial toy seats its balls is **unknown**. If they are captured
  between the halves, or held by magnets, 50 % is possible.

### 3. "S" curve and gap

- **Track circle offset from the central axis: 14.920 mm (`Track_Offset`).**
  The arc radius and apex height are also 14.920 mm. For 3 lobes they are
  18.273 and 10.550 mm. All follow from the chosen ball, sink and path; none
  was taken from the commercial toy.
- **The parting line is flat** (the equator), not an S.
- **Gap between the halves: 0 at the faces.** They sit face to face, pulled
  together by the magnets.
  - The visible seam is a 1 mm V from two 0.5 mm rim chamfers.
  - My first draft had a 0.15 mm face relief. It cannot be printed: it would
    sit on the bed face and is thinner than one layer. That only suits a
    moulded or resin part.
- **Clearances that matter:**

  | Where | Clearance | Basis |
  | --- | --- | --- |
  | Ball to groove | 0.3 mm radial | printed against a precise steel part |
  | Sleeve to drilled bore | ≤ 0.05 mm radial | so the halves can shift ≤ 0.1 mm relative to each other |
  | Axial end play | 0.15–0.4 mm | set by the sleeve |

  For printed-on-printed moving parts, vendor guidance (JLC3DP; UZH AMF FDM
  guideline) is 0.4–0.5 mm. Nothing here slides printed-on-printed except
  the greased faces.
- **Alignment budget.** A ball crosses the seam if the grooves line up within
  2 × `Groove_Clr` = 0.6 mm. Radial play uses 0.1 of that. The detent is
  below, and the 1 mm lead-ins take up the rest.

## Building it in Onshape

1. **Variables** as above.
2. **Body**: sketch on *Front*.
   - Draw a construction line on Z.
   - Closed profile: from (`Bore_Dia/2`, 0) out to (`Sphere_R`, 0).
   - Then an arc centred on the origin, radius `Sphere_R`, up to
     x = `Pocket_Dia/2`.
   - Then down to z = `Sphere_R − Seat_Depth`, in to x = `Bore_Dia/2`, and
     back to 0.
   - **Revolve, Full**, about the line.
3. **Track plane**:
   - Show Sketch 1.
   - *Plane → Line angle*: select the Z construction line, then *Front* as
     the reference, angle `#Track_Angle`.
4. **Track sketch** on that plane:
   - *Use* (project) the Z line.
   - Draw a construction line from the origin, *Perpendicular* to it. This
     is the revolve axis, in the parting plane.
   - Draw a circle with diameter `2 * #Groove_R`. Put its centre
     `#Track_Offset` from the projected Z line and `#Arc_R` from the axis
     line, on the upper side.
   - No Horizontal or Vertical constraints in this sketch.
   - **Revolve → Remove → Full**, merge scope the body. A Full revolve and a
     ±90° revolve remove the same material, because the lower half of that
     torus lies outside the part.
5. **Circular pattern** (*Feature pattern*) of the Revolve:
   - Axis: the bore face.
   - `#Lobes` instances, 360°, *Equal spacing* ticked.
6. **Lead-in chamfer `#Lead_In`** on the `2·#Lobes` groove-end edges at the
   parting face, **before any fillet**. They are still sharp, so nothing
   propagates.
   - If Chamfer fails, use Extrude Remove from *Top* instead: a circle of
     diameter `2 * #Groove_R + 2 * #Lead_In` at radius `#Track_R` on each
     crossing, 1 mm deep, with 45° draft.
7. **Rim chamfer `#Rim_Chamfer`** on the rim arcs.
8. **Lip fillet `#Lip_Fillet`**, last, on the groove/shell edges (including
   the lead-in/shell edges).
9. **Magnet holes**:
   - Sketch on *Top*: one circle of diameter `#Magnet_Hole` at radius
     `#Magnet_R`, angle `#Track_Angle` from Front.
   - *Extrude Remove* `#Magnet_Depth` into the body.
   - Circular pattern: `2·#Lobes` instances (45°, 135°, 225°, 315°: every arc
     axis).
   - Add a 0.2 mm countersink at each hole mouth against elephant's foot.
10. **Second half**:
    - *Transform*, type *Rotate*, with *Copy part* ticked.
    - Axis: the z = 0 edge of Sketch 1, which lies on X, or an origin mate
      connector's X axis. Angle 180°.
    - Do not rotate about the 45° line. That puts the lower arcs in the wrong
      planes.
11. **Pole pockets**, now that the halves differ. Use part-scoped Extrude
    Removes:
    - **Head half**: a Ø`#Pocket_Dia` round from the seat floor down to the
      pocket floor, z = `#Sphere_R − #Seat_Depth` to `#Sphere_R − #Pocket_Depth`.
    - **Nut half**: a **hex**, `#Nut_AF` across flats (*Inscribed polygon*,
      6 sides), over the same depths. It holds the nut, so the bolt can be
      tightened.
12. **Balls** (visual):
    - In a copy of the track sketch, draw a semicircle of diameter
      `#Ball_Dia` on the groove-circle centre, closed by its diameter line.
    - *Revolve → New → Full*.
    - Copy by Transform, or place in an Assembly.
13. **Caps**: Ø9.5 plugs, flush with the shell, one per seat.
    - The head-end cap butts on the bolt head.
    - The nut-end cap gets a Ø4.6 × 2.7 mm recess for the bolt tip.
    - A spin nub (`Nub_H`) goes on both caps, or on neither.

**Hardware**:
- Sleeve: 6 mm OD **brass** tube with a 4.2–4.5 mm bore. A nominal 4.0 mm
  bore can bind on the M4 thread, which is up to 3.98 mm across.
- M4 × 40 socket-head cap screw (ISO 4762), with **one** M4 washer
  (DIN 125, Ø9 × 0.8) under the head.
- M4 nylon-insert lock nut (DIN 985), sitting directly on the sleeve end.
  The tip passes it by 1.9 mm (2.55 worst).
- 8 × Ø4 × 2 mm N42 magnets.
- 3 balls.
- Dry PTFE or silicone lube.

The bolt clamps only the sleeve. The halves float on it with
`End_Play` / 2 = 0.15 mm clearance at each pocket floor, and the magnets hold
them together. Preload never reaches the plastic, so it cannot drift.

**Assembly**:
1. Glue the magnets in. In one half, every north pole faces the parting face;
   in the other, every south pole. Seat each under a 0.5 mm shim across the
   face and check with a straightedge.
2. **Measure, then cut the sleeve.**
   - Measure each half from parting face to pocket floor.
   - Cut and face the brass tube to the sum + 0.25 ± 0.05 mm.
   - The nominal 32.3 is only a starting point: FDM Z-error of ±0.1 per half
     is as big as the end play.
   - Print with first layer = layer height, so the floor lands on a layer
     boundary.
3. Drill the bores to 6.0 mm, and to 6.1 only if the tube will not slide.
4. Lay one half dome-down with the sleeve in it. **Drop the balls in through
   the open groove ends** at the parting face. They enter freely (groove
   radius 6.3 > ball radius 6.0), so nothing is pressed past a lip.
5. Grease the faces lightly and close the halves.
6. Hold the nut-end half and turn the head with a 3 mm key, to
   **0.5–0.8 N·m**.
7. **Acceptance check**: the halves spin freely with 0.15–0.4 mm of axial
   play at the seam. If they bind, the sleeve is short or the washer is on
   the floor.

**Printing**:
- Each half parting-face down on a smooth sheet, with elephant's-foot
  compensation on.
- **The groove ceiling is the hard part.** On the pole side of each arc, a
  strip up to **3.5 mm (2 lobes) / 5.2 mm (3 lobes)** wide is flatter than
  45° over about half of each arc. It is worst at the apex: **13°** from
  horizontal for 2 lobes, and a flat downward-facing patch for 3 lobes.
  Choose one:
  - PLA with full cooling and slow overhangs, then lap the groove by rolling
    a ball with fine abrasive;
  - tree supports through the groove mouth;
  - resin.
- Expect droop to tighten the pole-side lip.
- **Print a test coupon first**: a 60° wedge of a half, at `Ball_Sink` 3.8,
  3.9 and 4.0 (an Onshape configuration).

**Using it**:
- A ball whose centre is within ~1.7 mm of the seam (~7 % of the loop; 10 %
  for 3 lobes) is wedged by the two groove edges if you twist. The reviewer
  who knocked a ball out of the track was describing this.
- Twist with the poles roughly vertical, so the balls roll off the seam
  first. The lead-ins clear balls that are further off-centre.

**Detent** (`orbitfit --magnets`): Ø4 × 2 N42 discs, 1.0 mm apart,
1.72 N per pair, full-face friction. The step includes the 0.1 mm radial
play.

| 2 lobes, 4 pairs at r 20 | Holds the twist within | Step at a crossing |
| --- | --- | --- |
| greased, μ 0.1 | ±0.56° | 0.30 mm, passes |
| greased, μ 0.15 | ±0.84° | 0.41 mm, passes |
| dry, μ 0.3 | ±1.8° | 0.76 mm, needs the lead-in |

Magnet pull on a ball: at most 3.1 % of its weight, which is negligible. The
field model is Derby & Olbert's closed form, with surface-charge force on
the facing magnet. It reproduces the exact on-axis field.

## Checks (`python3 tools/orbitfit.py`, Lobes = 2)

```
  PASS  ball captured (sharp mouth < ball)   10.71 < 12.00
  PASS  retention, lip filleted              0.36 mm/side           0.25-0.50
  PASS  ball enters at groove end            6.30 > 6.00
  PASS  ball proud of shell                  1.80-2.88 mm           > 0
  PASS  track revolve valid (arc_r > rg+1)   14.92 > 7.30
  PASS  wall between arcs, one loop          17.24 mm               >= 2.0
  PASS  wall between arcs, 2 loops           17.24 mm               >= 2.0
  PASS  wall groove-pole pocket              3.88 mm                >= 2.0
  PASS  wall groove-sleeve bore              5.57 mm                >= 2.0
  PASS  wall groove-magnets (r 20)           6.12 mm                >= 2.0
  PASS  magnet pull on a ball / its weight   3.1 %                  <= 10 %
  PASS  rim land between crossings           28.6 mm                >= 8
  PASS  loops at 0 / 90 deg                  1 / 2                  1 / 2
  PASS  washer/nut clear of pocket floor     0.15 mm                >= 0.1
  PASS  M4x40 past nylock                    1.90 (max 2.55) mm     0.5-3.0
  PASS  cap room, head / nut end (worst)     3.43 / 3.23            >= 1.5
```

`--lobes 3` passes every track and joint check but fails the two magnet
rows, as explained above.

These are design rules, not physics:
- The 0.25–0.50 mm retention window is engineering judgement.
- The magnet model is a model.
- Nothing simulates roll feel or wear.

## Not verified

- Ball diameter and material; wall; groove; track path; and how the real toy
  retains its balls. All of these are derived.
- Whether the body is a true sphere.
- What sets the 56 mm length.
- Whether the commercial toy has detents at all.
- Anything physical. Nothing has been printed.

**Measurements on a real unit that would settle most of this:**
1. **Ball diameter.** The toy is not meant to come apart, but the reviewer
   above knocked a ball out by twisting with it on the seam. If one comes
   out, caliper it.
   - Otherwise, measure the opening `c` between the two lips at a ball, and
     the height `h` of the ball's top above that opening, with the ball
     pushed outward against the lips. Then `d ≈ c²/(4h) + h`. This is
     approximate, because the ball touches the rounded lips rather than
     exactly at the measured opening.
   - Touch a magnet to it first. Steel balls can then be cross-checked by
     weight: three weigh 21.3 g at 12 mm, 25.3 g at ½″, and 16.4 g at 11 mm.
2. OD across the shell avoiding the balls, then pole to pole.
3. How far a ball stands proud. This gives `Ball_Sink`.
4. Twist positions per revolution at which the track lines up. 4 means
   `Lobes = 2`; 6 means `Lobes = 3` or stacked rings.
5. One look along the twist axis and one from the side, compared with the
   track previews. The D1056062 drawings would also settle this.
