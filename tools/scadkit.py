#!/usr/bin/env python3
"""
scadkit -- render/validate harness for the studio's OpenSCAD projects.

Wraps the OpenSCAD CLI and trimesh so every project can be driven the same way:

    scadkit.py render  src/part.scad out.stl [-D name=value ...]
    scadkit.py preview src/part.scad out.png [--camera ...] [-D ...]
    scadkit.py check   out.stl [--watertight] [--bodies N] [--max-bbox X,Y,Z]
    scadkit.py matrix  projects/<name>/validation.json

`matrix` is the one that matters: it runs a project's whole parameter matrix
(CLAUDE.md section 41), exports each case, checks each mesh, and prints a
PASS/FAIL table. It exits non-zero if any case fails, so it works in CI.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

OPENSCAD = os.environ.get("OPENSCAD", "openscad")

# OpenSCAD 2021.01 needs an X server for PNG export. STL export does not.
XVFB = shutil.which("xvfb-run")

# Gimbal cameras: translate_x,y,z, rot_x,y,z, dist. Paired with --viewall the
# distance is recomputed to fit, so the trailing 0 is a placeholder.
VIEWS = {
    "iso":    "0,0,0,60,0,315,0",
    "iso_rear": "0,0,0,60,0,135,0",
    "front":  "0,0,0,90,0,0,0",
    "rear":   "0,0,0,90,0,180,0",
    "left":   "0,0,0,90,0,90,0",
    "right":  "0,0,0,90,0,270,0",
    "top":    "0,0,0,0,0,0,0",
    "bottom": "0,0,0,180,0,0,0",
}


class ScadError(RuntimeError):
    pass


def _defines(params: dict | None) -> list[str]:
    """Turn a param dict into OpenSCAD -D flags.

    Strings must reach OpenSCAD quoted, numbers and booleans bare. Lists are
    emitted as OpenSCAD vectors.
    """
    out: list[str] = []
    for key, value in (params or {}).items():
        out += ["-D", f"{key}={_scad_literal(value)}"]
    return out


def _scad_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_scad_literal(v) for v in value) + "]"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise ScadError(f"cannot express {value!r} as an OpenSCAD literal")


def _run(cmd: list[str], timeout: int) -> tuple[int, str, float]:
    start = time.monotonic()
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    return proc.returncode, (proc.stdout + proc.stderr), time.monotonic() - start


def render(scad: Path, out: Path, params: dict | None = None,
           hardwarnings: bool = True, timeout: int = 1800) -> float:
    """Export geometry (.stl/.3mf/.off/...) from a .scad file. Returns seconds."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [OPENSCAD, "-o", str(out), *_defines(params)]
    if hardwarnings:
        cmd.append("--hardwarnings")
    cmd.append(str(scad))

    code, log, secs = _run(cmd, timeout)
    if code != 0 or not out.exists():
        raise ScadError(f"openscad failed ({code}) on {scad}:\n{log.strip()[-2000:]}")
    return secs


def preview(scad: Path, out: Path, params: dict | None = None,
            camera: str = VIEWS["iso"], size: str = "1000,750",
            colorscheme: str = "Tomorrow", viewall: bool = True,
            projection: str | None = None, timeout: int = 1800) -> float:
    """Export a PNG preview. Needs xvfb-run on a headless box."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    cmd: list[str] = []
    if XVFB:
        cmd += [XVFB, "-a"]
    cmd += [
        OPENSCAD, "-o", str(out),
        f"--imgsize={size}",
        f"--camera={camera}",
        f"--colorscheme={colorscheme}",
        # NOTE: must be --render=cgal. A bare --render (or --render=) is
        # rejected by this build's option parser and eats the input filename.
        "--render=cgal",
    ]
    if viewall:
        cmd += ["--viewall", "--autocenter"]
    if projection:
        cmd.append(f"--projection={projection}")
    cmd += [*_defines(params), str(scad)]

    code, log, secs = _run(cmd, timeout)
    if code != 0 or not out.exists():
        raise ScadError(f"openscad preview failed ({code}) on {scad}:\n{log.strip()[-2000:]}")
    return secs


@dataclass
class MeshReport:
    path: Path
    watertight: bool = False
    winding_consistent: bool = False
    bodies: int = 0
    volume_cm3: float = 0.0
    area_cm2: float = 0.0
    bbox: tuple[float, float, float] = (0.0, 0.0, 0.0)
    faces: int = 0
    degenerate: int = 0
    euler: int = 0
    problems: list[str] = field(default_factory=list)

    def as_row(self) -> str:
        x, y, z = self.bbox
        return (f"{'WT' if self.watertight else '--'} "
                f"bodies={self.bodies} "
                f"bbox={x:.1f}x{y:.1f}x{z:.1f} "
                f"vol={self.volume_cm3:.1f}cm3 "
                f"faces={self.faces}")


def inspect(stl: Path) -> MeshReport:
    import numpy as np
    import trimesh

    mesh = trimesh.load(str(stl), force="mesh")
    rep = MeshReport(path=stl)
    rep.faces = int(len(mesh.faces))
    rep.watertight = bool(mesh.is_watertight)
    rep.winding_consistent = bool(mesh.is_winding_consistent)
    rep.bodies = int(mesh.body_count)
    rep.volume_cm3 = float(abs(mesh.volume)) / 1000.0
    rep.area_cm2 = float(mesh.area) / 100.0
    rep.bbox = tuple(round(float(v), 4) for v in mesh.extents)  # type: ignore[assignment]
    rep.euler = int(mesh.euler_number)

    # Zero-area triangles: legal in STL, poison for slicers and booleans.
    areas = mesh.area_faces
    rep.degenerate = int((areas <= 1e-9).sum())

    if not rep.watertight:
        rep.problems.append("not watertight")
    if not rep.winding_consistent:
        rep.problems.append("inconsistent winding")
    if rep.degenerate:
        rep.problems.append(f"{rep.degenerate} degenerate faces")
    if rep.volume_cm3 <= 0:
        rep.problems.append("non-positive volume")
    return rep


def apply_expectations(rep: MeshReport, expect: dict) -> list[str]:
    """Compare a report against a case's `expect` block. Returns failures."""
    fails: list[str] = []
    if expect.get("watertight") and not rep.watertight:
        fails.append("expected watertight")
    if "bodies" in expect and rep.bodies != expect["bodies"]:
        fails.append(f"expected {expect['bodies']} bodies, got {rep.bodies}")
    if "max_bbox" in expect:
        for axis, got, cap in zip("XYZ", rep.bbox, expect["max_bbox"]):
            if got > cap + 1e-6:
                fails.append(f"{axis}={got:.2f} exceeds {cap}")
    if "min_bbox" in expect:
        for axis, got, floor in zip("XYZ", rep.bbox, expect["min_bbox"]):
            if got < floor - 1e-6:
                fails.append(f"{axis}={got:.2f} under {floor}")
    if "max_volume_cm3" in expect and rep.volume_cm3 > expect["max_volume_cm3"]:
        fails.append(f"volume {rep.volume_cm3:.1f}cm3 over {expect['max_volume_cm3']}")
    if expect.get("no_degenerate", True) and rep.degenerate:
        fails.append(f"{rep.degenerate} degenerate faces")
    return fails


def run_matrix(spec_path: Path, previews: bool = False) -> int:
    spec = json.loads(spec_path.read_text())
    root = spec_path.parent
    scad = root / spec["scad"]
    outdir = root / spec.get("outdir", "exports")
    prevdir = root / spec.get("previewdir", "previews")

    print(f"== {spec.get('name', scad.stem)} :: {len(spec['cases'])} cases ==")
    failures = 0

    for case in spec["cases"]:
        name = case["name"]
        params = case.get("params", {})
        stl = outdir / f"{name}.stl"
        label = f"  {name:<28}"
        try:
            secs = render(scad, stl, params)
        except ScadError as exc:
            print(f"{label} FAIL  render\n{_indent(str(exc))}")
            failures += 1
            continue
        except subprocess.TimeoutExpired:
            print(f"{label} FAIL  render timeout")
            failures += 1
            continue

        rep = inspect(stl)
        fails = rep.problems + apply_expectations(rep, case.get("expect", {}))
        # `problems` and `expect` overlap; keep the message list unique.
        fails = list(dict.fromkeys(fails))

        status = "PASS" if not fails else "FAIL"
        print(f"{label} {status}  {rep.as_row()}  [{secs:.1f}s]")
        for f in fails:
            print(f"        - {f}")
        if fails:
            failures += 1

        if previews:
            for view in spec.get("views", [{"name": "iso", "camera": VIEWS["iso"]}]):
                cam = view.get("camera") or VIEWS[view["name"]]
                png = prevdir / f"{name}_{view['name']}.png"
                try:
                    preview(scad, png, params, camera=cam)
                except (ScadError, subprocess.TimeoutExpired) as exc:
                    print(f"        ! preview {view['name']}: {str(exc)[:200]}")

    print(f"== {len(spec['cases']) - failures}/{len(spec['cases'])} passed ==")
    return 1 if failures else 0


def _indent(text: str, pad: str = "        ") -> str:
    return "\n".join(pad + line for line in text.splitlines())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_defines(p):
        p.add_argument("-D", dest="defines", action="append", default=[],
                       metavar="NAME=VALUE",
                       help="OpenSCAD variable override; VALUE is parsed as JSON "
                            "when possible, else treated as a string")

    r = sub.add_parser("render", help="export geometry")
    r.add_argument("scad", type=Path)
    r.add_argument("out", type=Path)
    add_defines(r)

    p = sub.add_parser("preview", help="export a PNG")
    p.add_argument("scad", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--camera", default=VIEWS["iso"],
                   help=f"gimbal camera string, or one of: {', '.join(VIEWS)}")
    p.add_argument("--size", default="1000,750")
    p.add_argument("--colorscheme", default="Tomorrow")
    add_defines(p)

    c = sub.add_parser("check", help="validate an exported mesh")
    c.add_argument("stl", type=Path)
    c.add_argument("--watertight", action="store_true")
    c.add_argument("--bodies", type=int)
    c.add_argument("--max-bbox", help="X,Y,Z")

    m = sub.add_parser("matrix", help="run a project's validation.json")
    m.add_argument("spec", type=Path)
    m.add_argument("--previews", action="store_true",
                   help="also export PNG previews for each case")

    args = ap.parse_args()

    def parsed_defines() -> dict:
        out = {}
        for item in getattr(args, "defines", []):
            key, _, raw = item.partition("=")
            try:
                out[key] = json.loads(raw)
            except json.JSONDecodeError:
                out[key] = raw
        return out

    try:
        if args.cmd == "render":
            secs = render(args.scad, args.out, parsed_defines())
            print(f"{args.out} ({args.out.stat().st_size/1024:.0f} KiB) in {secs:.1f}s")
            return 0

        if args.cmd == "preview":
            cam = VIEWS.get(args.camera, args.camera)
            secs = preview(args.scad, args.out, parsed_defines(), camera=cam,
                           size=args.size, colorscheme=args.colorscheme)
            print(f"{args.out} in {secs:.1f}s")
            return 0

        if args.cmd == "check":
            rep = inspect(args.stl)
            print(f"{args.stl}: {rep.as_row()}")
            print(f"  winding_consistent={rep.winding_consistent} "
                  f"euler={rep.euler} degenerate={rep.degenerate} "
                  f"area={rep.area_cm2:.1f}cm2")
            expect = {}
            if args.watertight:
                expect["watertight"] = True
            if args.bodies is not None:
                expect["bodies"] = args.bodies
            if args.max_bbox:
                expect["max_bbox"] = [float(v) for v in args.max_bbox.split(",")]
            fails = list(dict.fromkeys(rep.problems + apply_expectations(rep, expect)))
            for f in fails:
                print(f"  - {f}")
            return 1 if fails else 0

        if args.cmd == "matrix":
            return run_matrix(args.spec, previews=args.previews)

    except ScadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
