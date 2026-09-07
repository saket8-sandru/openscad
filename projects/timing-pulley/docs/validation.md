# Validation report — timing pulley generator

**Status: CAD-validated. No physical print has been made, and no belt has ever
been run on one of these.**

Everything below was measured by running the generator and inspecting the
exported meshes. Tooth engagement, shaft fit, clamp grip and flange retention
are all *unverified* — see "Not verified" at the end.

Reproduce with:

```bash
python3 tools/scadkit.py matrix projects/timing-pulley/validation.json
python3 tools/toothfit.py
```

## Toolchain

| | |
| --- | --- |
| OpenSCAD | 2021.01 — the release MakerWorld's Parametric Model Maker runs |
| trimesh / scipy / numpy | 5.1.0 / 1.17.1 / 2.4.6 |
| Mesh criteria | watertight, consistent winding, expected connected-body count, bounding box within build volume, bounded zero-area faces |

## Parameter matrix

```
== TIMING PULLEY (GT2 2mm / HTD 5M) :: 42 cases ==
  default                      PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=2.3cm3 faces=12712 degen=0  [7.5s]
  bore_round                   PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=2.3cm3 faces=12712 degen=0  [7.8s]
  bore_d                       PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=2.3cm3 faces=12712 degen=0  [7.1s]
  bore_hex_8                   PASS  WT bodies=1 bbox=19.9x19.9x16.4 vol=2.9cm3 faces=14192 degen=0  [7.2s]
  bore_hex_12                  PASS  WT bodies=1 bbox=23.9x23.9x16.4 vol=3.6cm3 faces=16784 degen=0  [8.2s]
  bore_square_8                PASS  WT bodies=1 bbox=19.9x19.9x16.4 vol=2.7cm3 faces=14184 degen=0  [7.4s]
  bore_rex8                    PASS  WT bodies=1 bbox=19.9x19.9x16.4 vol=2.6cm3 faces=12400 degen=0  [7.9s]
  bore_bearing_16              PASS  WT bodies=1 bbox=27.9x27.9x16.4 vol=4.7cm3 faces=19936 degen=0  [9.7s]
  bore_solid                   PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=2.7cm3 faces=12324 degen=0  [6.7s]
  bore_tight_clearance         PASS  WT bodies=1 bbox=16.6x16.6x16.4 vol=2.3cm3 faces=12704 degen=0  [7.2s]
  bore_loose_clearance         PASS  WT bodies=1 bbox=17.8x17.8x16.4 vol=2.4cm3 faces=12712 degen=0  [8.1s]
  clamp_split                  PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=2.3cm3 faces=12712 degen=0  [7.9s]
  clamp_nut                    PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=2.3cm3 faces=12744 degen=0  [7.3s]
  clamp_collet                 PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=1.9cm3 faces=13180 degen=0  [8.1s]
  clamp_none                   PASS  WT bodies=1 bbox=15.0x15.0x16.4 vol=1.4cm3 faces=12368 degen=0  [6.6s]
  clamp_m5                     PASS  WT bodies=1 bbox=20.9x20.9x16.4 vol=3.0cm3 faces=12736 degen=0  [7.3s]
  hub_none                     PASS  WT bodies=1 bbox=15.0x15.0x8.4 vol=0.9cm3 faces=11984 degen=0  [5.5s]
  hub_none_with_clamp          PASS  WT bodies=1 bbox=15.0x15.0x8.4 vol=0.9cm3 faces=11984 degen=0  [5.6s]
  hub_long                     PASS  WT bodies=1 bbox=16.9x16.9x38.4 vol=6.6cm3 faces=12712 degen=0  [7.3s]
  flange_one_side              PASS  WT bodies=1 bbox=16.9x16.9x15.2 vol=2.1cm3 faces=11580 degen=0  [5.5s]
  flange_none                  PASS  WT bodies=1 bbox=16.9x16.9x14.0 vol=1.9cm3 faces=9316 degen=0  [3.9s]
  flange_tall_narrow_belt      PASS  WT bodies=1 bbox=17.4x17.4x20.0 vol=3.4cm3 faces=12652 degen=0  [7.2s]
  flange_tall_wide_belt        PASS  WT bodies=1 bbox=45.0x45.0x40.4 vol=27.0cm3 faces=21340 degen=0  [10.0s]
  flange_tall_one_side         PASS  WT bodies=1 bbox=22.6x22.6x15.2 vol=2.9cm3 faces=11516 degen=0  [5.6s]
  flange_thin                  PASS  WT bodies=1 bbox=16.9x16.9x15.2 vol=2.1cm3 faces=11816 degen=0  [6.7s]
  belt_narrow                  PASS  WT bodies=1 bbox=16.9x16.9x13.4 vol=2.0cm3 faces=12712 degen=0  [7.2s]
  belt_wide                    PASS  WT bodies=1 bbox=27.8x27.8x40.4 vol=16.0cm3 faces=21468 degen=0  [9.9s]
  teeth_small                  PASS  WT bodies=1 bbox=16.9x16.9x16.4 vol=1.9cm3 faces=10904 degen=0  [6.6s]
  teeth_150                    PASS  WT bodies=1 bbox=97.8x97.8x16.4 vol=61.3cm3 faces=71156 degen=12  [50.3s]
  htd_20t                      PASS  WT bodies=1 bbox=33.5x33.5x19.4 vol=9.0cm3 faces=13804 degen=0  [7.1s]
  htd_60t                      PASS  WT bodies=1 bbox=97.2x97.2x25.4 vol=118.9cm3 faces=33164 degen=0  [14.6s]
  htd_bore_rex                 PASS  WT bodies=1 bbox=33.5x33.5x19.4 vol=9.2cm3 faces=13492 degen=0  [6.8s]
  out_fit_gauge                PASS  WT bodies=1 bbox=6.6x12.0x16.4 vol=0.6cm3 faces=3220 degen=0  [7.5s]
  out_collet                   PASS  WT bodies=1 bbox=10.1x10.1x8.0 vol=0.4cm3 faces=740 degen=0  [0.2s]
  out_size_set                 PASS  WT bodies=4 bbox=88.5x27.8x16.4 vol=13.4cm3 faces=62240 degen=0  [54.1s]
  out_size_set_htd             PASS  WT bodies=4 bbox=184.9x65.3x19.4 vol=69.8cm3 faces=67624 degen=0  [58.0s]
  out_size_set_gaps            PASS  WT bodies=2 bbox=45.3x21.4x16.4 vol=5.6cm3 faces=28060 degen=0  [19.1s]
  reject_bore_eats_8t          PASS  rejected as expected
  reject_hex12_on_20t          PASS  rejected as expected
  reject_bearing16_on_20t      PASS  rejected as expected
  reject_bore30_on_20t         PASS  rejected as expected
  reject_size_set_smallest_governs PASS  rejected as expected
== 42/42 passed ==
```

Every case is watertight with consistent winding and the expected body count.

Three results that look odd but are correct:

- **`out_size_set` reports 4 bodies, `out_size_set_gaps` reports 2.** That count
  is itself the test. An earlier build had all four slots reading the global
  tooth count, so it printed the same wheel four times; the body count and the
  differing bounding boxes are what would catch that returning.
- **`teeth_150` carries 12 zero-area faces where every other case has none.**
  Extruding all 150 groove outlines as one drawing leaves a few collinear
  slivers where neighbours meet. They carry no area, the mesh stays watertight
  and single-bodied, and slicers drop them. The per-groove version left none —
  and took 394 s instead of 50 s.
- **`out_collet` renders in 0.2 s.** It is a split sleeve, not a pulley: no
  teeth to cut, so there is no boolean work to do.

`flange_tall_one_side` failed on its first run and the mesh was right -- the
expectation was not. A one-sided flange capped at 5.2 mm rise measures
12.22 + 2 x 5.2 = 22.62 mm across, and the cap had been guessed at 22 rather
than computed. Worth recording, because a matrix that only ever confirms what
its author already believed is not testing anything.

## Guards

Five cases assert that the generator **refuses** a parameter set. A guard is
only worth something if its refusal is tested too, so `"rejected"` in the matrix
inverts the render check, and the string match makes the guard fail for the
right reason rather than any reason.

| Case | What it asks for | Why it must be refused |
| --- | --- | --- |
| `reject_bore_eats_8t` | 8T GT2, stock 5 mm bore | Bore 5.3 mm vs a 3.04 mm root circle |
| `reject_hex12_on_20t` | 12 mm hex in 20T | Bore 12.3 mm vs a 10.68 mm root circle |
| `reject_bearing16_on_20t` | 16 mm bearing seat in 20T | Bore 16.3 mm vs a 10.68 mm root circle |
| `reject_bore30_on_20t` | 30 mm bore in 20T | Slider maximum against slider minimum |
| `reject_size_set_smallest_governs` | 8 mm bore, set including 10T | The smallest wheel in the set is the one that decides |

The refusal names the remedy rather than just failing:

```
Bore too wide for this pulley. 8T GT2 2mm has a 3.04mm root circle, which
leaves room for a 1.14mm bore. Lower bore_size to that, or raise teeth to 15.
```

**The bore is deliberately not clamped to fit.** Every other guard in this
studio quietly clamps its parameter into legality, but a pulley whose bore
silently shrank would not go on the shaft it was printed for. A part that fits
nothing is worse than a render that stops and says why.

## Defects found and fixed

| Defect | How it surfaced | Resolution |
| --- | --- | --- |
| A bore wider than the tooth roots ate the toothed body. 8T GT2 with the stock 5 mm bore exported as **2 disconnected bodies** | Parameter-space probe, body count | Assert on bore vs. root circle, leaving 0.8 mm of rim |
| The same failure at 16 mm bearing seat on 20T exported as **1 watertight body with no teeth on it** | Probe, face count collapsing 12712 → ~1000 | Same guard. Note that no mesh check could have caught this one — it is a perfectly valid ring |
| A flange chamfer taller than half the belt channel ran out the far side; `flange_height` 10 on a 6 mm belt gave **21 disconnected bodies** and hung 1 mm below the plate | Probe, body count and negative Z | Flange rise capped so 0.8 mm of channel stays at full groove depth |
| A 150T pulley took **394 s** — over the MakerWorld render budget at the slider's own maximum | Probe timing | Grooves extruded as one drawing instead of one per tooth: **50 s** |
| Clamp screw passed straight through the shaft bore | Render review | Screw axis moved beside the bore |
| Size-set slots all printed the same wheel | Body inspection | Body modules take the tooth count as an argument instead of reading the global |

### The cutter rewrite is measured, not assumed

Changing how the grooves are cut is changing the tooth geometry until proven
otherwise. The two versions were compared directly at 150 teeth:

| | per-groove (before) | one extrude (after) |
| --- | --- | --- |
| Render time | 394 s | **50 s** |
| Volume | 61258.844139 mm³ | 61258.834233 mm³ |
| Surface area | 20857.3948 mm² | 20857.4107 mm² |
| Bounding box | identical to 1e-4 mm | identical to 1e-4 mm |
| Worst surface deviation | — | **0.14 µm** (mean 0.015 µm) |
| 20T mesh | 12712 faces, 0 degenerate | **12712 faces, 0 degenerate** |

0.14 µm is about 1/3000th of a 0.4 mm extrusion bead. At 20 teeth the two are
identical outright; the difference only appears at 150 teeth, and it is
floating-point ordering, not shape.

## Tooth profile

Derivation, provenance and the fit residuals are in `docs/profiles.md`. In
short: the profiles were **fitted to the published envelope**, not copied from a
community point list of unclear licence, and the arc construction agrees with
the reference to **11 µm worst case** — about 1/40th of an extrusion bead.

Pitch was verified on exported geometry as exactly 2.000000 mm, error 0.00e+00.
Tooth count was confirmed by FFT after a naive run-count miscounted a
wraparound as 21 teeth on a 20T wheel.

## Not verified

- **Any physical print.** Nothing here has been on a printer.
- **Belt engagement.** No belt has been run on any of these. The profile matches
  the published envelope on paper; whether a printed one meshes without ratchet
  or backlash is untested.
- **Shaft fit.** `bore_clearance` = 0.15 mm is a reasoned starting value. Print
  the **Fit gauge** output first — that is what it is for. The REX profile is
  built from goBILDA's published 8 mm spec, not from a measured shaft.
- **Clamp grip.** Split clamp, captive nut and collet shell are all geometrically
  sound and none has held a shaft against real torque. The captive nut pocket is
  sized from ISO 4032 nominal, not from a measured nut.
- **Flange retention.** Untested; flange height is a guess at what keeps a belt on.
- **Layer adhesion under load.** A printed pulley is loaded across its layers by
  belt tension. Not tested, and the failure mode that matters most.
- **MakerWorld render budget.** 50 s for the worst case was measured on this
  machine, not on their farm. It has margin now; it did not before.
