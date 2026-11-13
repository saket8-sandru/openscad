# Validation log

Run with `python3 cad/build_cadquery.py --arm {0,90}` (CadQuery 2.8.0, OCP 7.8).

| Case | Solids | Pairs tested | Interferences | Ball-path violations (3 mm) | Mass | CG (mm) |
| --- | --- | --- | --- | --- | --- | --- |
| arm 0 (deployed) | 71 | 99 | 0 | 0 of 20 positions | 6.14 kg | (-5, 1, 67) |
| arm 90 (stowed) | 71 | 103 | 0 | 0 of 20 positions | 6.14 kg | (-7, 1, 70) |

Ball positions checked: on the floor under the arm roller, climbing the lip,
on the deck at the lip, under the feed roller, at the flywheel grab point,
eight points around the hood (-90 to -225 deg), seven points along the 45 deg
launch line up to 200 mm past the exit.

Defects found and fixed by the checker during design (kept here because they
are the kind the next edit will reintroduce):

1. Flywheel drive gear pair placed outboard of the right shooter plate instead
   of inboard: 657 mm3 into the plate and 490 mm3 into the motor face.
2. Flywheel shaft ran into the off-axis flywheel motor can (59 mm3): the shaft
   now stops 0.1 mm short of the motor faceplate.
3. Feed-roller hand-over was 1 mm short of the flywheel grab point with 8 mm
   feed compression and a 3 mm roller-to-flywheel gap; now 10 mm / 2.5 mm
   gives +3.2 mm overlap.

Close pairs (< 2 mm) are all intended: 1 mm motor-mount gap at every motor
faceplate, 0.6 mm gear pitch gaps, 1 mm from arm plates to vectored wheels,
1.5 mm from gecko to vectored wheels, 1 mm idler-shaft end to wheel face, 1.5 mm
from the arm-roller shaft end to the right inner pod plate.
