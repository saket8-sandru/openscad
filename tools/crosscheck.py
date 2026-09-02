#!/usr/bin/env python3
"""
crosscheck -- prove the NumPy mirror agrees with the OpenSCAD field engine.

fieldlab.py is only useful as a design instrument if it computes the same
numbers as the .scad that actually ships. This drives OpenSCAD's echo export
over a probe file, parses the values back, and compares them.

Run it after ANY change to the field maths in either file.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fieldlab
from fieldlab import FieldSpec

PROBE_POINTS = [(0, 0), (37, 91), (123.5, 45.25), (200, 200),
                (311, 88), (399, 399), (75, 320), (250, 17),
                (17.5, 383.25), (256.75, 199.5)]

PROBE_TEMPLATE = """include <{scad}>
PTS = {pts};
for (p = PTS) echo(str("PROBE ", p[0], " ", p[1], " ",
                       field_raw(p[0], p[1]), " ", field01(p[0], p[1])));
echo(str("NORM ", FIELD_LO, " ", FIELD_HI));
"""


def run_openscad(scad: Path, overrides: dict) -> dict:
    pts = "[" + ",".join(f"[{x},{z}]" for x, z in PROBE_POINTS) + "]"
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / "probe.scad"
        probe.write_text(PROBE_TEMPLATE.format(scad=scad.resolve(), pts=pts))
        out = Path(td) / "probe.echo"
        cmd = ["openscad", "-o", str(out), "--export-format", "echo"]
        for k, v in overrides.items():
            cmd += ["-D", f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"]
        cmd.append(str(probe))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if not out.exists():
            raise RuntimeError(f"openscad produced nothing (rc={proc.returncode})\n"
                               f"{proc.stderr[-1500:]}")
        text = out.read_text()

    raw, f01 = {}, {}
    for m in re.finditer(r'PROBE (\S+) (\S+) (\S+) ([^"\s]+)', text):
        key = (float(m.group(1)), float(m.group(2)))
        raw[key] = float(m.group(3))
        f01[key] = float(m.group(4))
    nm = re.search(r'NORM (\S+) ([^"\s]+)', text)
    return {"raw": raw, "f01": f01,
            "norm": (float(nm.group(1)), float(nm.group(2))) if nm else None}


def compare(scad: Path, spec: FieldSpec, overrides: dict, tol: float) -> int:
    got = run_openscad(scad, overrides)
    lo, hi = fieldlab.norm_range(spec)
    olo, ohi = got["norm"]

    label = overrides or "defaults"
    print(f"-- {label}")
    print(f"   norm  scad=({olo:+.6f},{ohi:+.6f})  numpy=({lo:+.6f},{hi:+.6f})  "
          f"d=({abs(olo-lo):.2e},{abs(ohi-hi):.2e})")

    worst_raw = worst_f01 = 0.0
    for (x, z), oraw in got["raw"].items():
        nraw = float(fieldlab.field_raw(spec, np.array(x), np.array(z)))
        nf01 = float(fieldlab.field(spec, np.array(x), np.array(z), lohi=(olo, ohi)))
        worst_raw = max(worst_raw, abs(oraw - nraw))
        worst_f01 = max(worst_f01, abs(got["f01"][(x, z)] - nf01))
    print(f"   worst |d| raw={worst_raw:.3e}  field01={worst_f01:.3e}  tol={tol:.0e}")

    ok = worst_raw < tol and worst_f01 < tol and abs(olo - lo) < tol and abs(ohi - hi) < tol
    print(f"   {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scad", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "projects/waveform-wall/src/waveform_wall.scad")
    # 2e-5 is the measurement floor, not a comfort margin: OpenSCAD's echo
    # prints six significant figures, so a field value of order 1 can only be
    # read back to about 5e-6. Observed worst-case disagreement sits just under
    # that. Before wrap360 was added to both implementations it was 1.3e-3.
    ap.add_argument("--tol", type=float, default=2e-5)
    args = ap.parse_args()

    # Every style, plus seeds and modifiers, so a divergence anywhere in the
    # table or the derived parameters is caught rather than just the default.
    cases = [({}, FieldSpec())]
    for style in fieldlab.STYLE_TABLE:
        cases.append(({"style": style}, FieldSpec(style=style)))
    for seed in (1, 42, 137):
        cases.append(({"seed": seed}, FieldSpec(seed=seed)))
    cases += [
        ({"intensity": 1.45}, FieldSpec(intensity=1.45)),
        ({"flow_angle": 200}, FieldSpec(flow_angle=200)),
        ({"swirl_scale": 1.8, "extra_vortices": 2},
         FieldSpec(swirl_scale=1.8, extra_vortices=2)),
        ({"relief_gamma": 1.6}, FieldSpec(relief_gamma=1.6)),
        ({"artwork_width": 700, "artwork_height": 300},
         FieldSpec(artwork_width=700, artwork_height=300)),
    ]

    failures = sum(compare(args.scad, spec, ov, args.tol) for ov, spec in cases)
    print(f"\n== {len(cases) - failures}/{len(cases)} configurations agree ==")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
