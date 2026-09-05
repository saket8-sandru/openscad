# Tooth profile derivation

## Why not just copy a profile

Every printed GT2/HTD pulley in circulation traces back to the same community
point lists. They are fixed-resolution, of unclear licence, and — as the search
for them turns up repeatedly — "many online resources show incorrect tooth
profiles". Copying one would mean shipping geometry whose correctness rests on
someone else's unverified transcription.

Instead the reference points were **measured**, an arc construction was fitted
to them, and the agreement was quantified. The generator builds from arcs, so
the groove resolves as finely as `$fn` asks rather than being frozen at whatever
a point list captured.

## Measured envelope

| | GT2 2 mm | HTD 5 M |
| --- | --- | --- |
| Pitch | 2.000 mm | 5.000 mm |
| Pitch line differential | 0.254 mm | 0.5715 mm |
| Groove depth | 0.7645 mm (spec 0.764) | 2.1985 mm |
| Width at pitch line | 1.4944 mm (spec 1.494) | 3.7807 mm |

## Fitted arc construction

| | GT2 2 mm | HTD 5 M |
| --- | --- | --- |
| Crown arc | R 0.57060 @ (0, +0.20111) | R 1.44350 @ (0, +0.74443) |
| Root fillet | R 0.28843 @ (±0.84294, +0.26340) | R 0.42982 @ (±1.89039, +0.42982) |
| Straight flank | none | (1.467026, 0.3556) → (1.427162, 0.960967) |
| Apex | 0.77171 | 2.18793 |

GT2 is a root fillet running straight into a crown arc. HTD has a genuine
straight section on the flank between the two — the reference represents it
with only two points, which is what makes it look at first glance like a gap in
the data. Fitting circles to the surrounding points and measuring segment
lengths confirmed it is a real straight flank, not a defect.

For HTD the two arc centres were fitted while the flank endpoints were taken
from the reference, so the joins are exact: `|flank_hi − crown_centre|` equals
the crown radius and `|flank_lo − root_centre|` equals the root radius, both to
five decimals.

## Agreement with the reference

Worst perpendicular distance from every reference point to the generated
outline, measured on the profile the `.scad` actually emits:

| Profile | Deviation |
| --- | --- |
| GT2 2 mm | **22.8 µm** |
| HTD 5 M | **10.6 µm** |

For scale: a 0.4 mm nozzle lays a bead about 420 µm wide, and printer XY
repeatability is around 100 µm. Both profiles are inside the noise floor of the
process that will make them.

A tighter GT2 fit (10.7 µm) exists if the apex is left free, but pinning the
apex to the spec depth of 0.7645 mm separates the two arcs by 1.6 µm so they no
longer meet, and would need a bridging segment. That was not worth adding: 22.8
µm is a eighteenth of an extrusion bead.

## Verified on the exported mesh

Cross-sectioning a default 20-tooth GT2 pulley through the belt channel:

- arc per tooth on the pitch circle: **2.000000 mm** against a belt pitch of
  2.0 — error 0.00e+00, which is the property that decides whether a belt
  meshes at all;
- dominant angular harmonic of the radius: **20**, matching the tooth count
  (checked by FFT, because a run-counting detector miscounts the wraparound);
- outside and root diameters within 20 µm of the formulas, the residue being
  `$fn` faceting.

## Shaft profiles

`REX 8mm` follows goBILDA's published definition — an 8 mm round combined with a
7 mm hex — implemented as the intersection of the two. Corner radii and
tolerances could not be read from the primary source (gobilda.com is blocked
from this environment), so the bore is the exact intersection plus the user's
clearance, with no corner relief.
