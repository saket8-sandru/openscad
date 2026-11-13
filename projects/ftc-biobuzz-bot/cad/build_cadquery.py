#!/usr/bin/env python3
"""
Render the robot spec with CadQuery, run the interference / clearance checks,
and export STEP + STL + previews.

    python3 cad/build_cadquery.py [--arm 0|90] [--out exports] [--no-export]
"""
import argparse, itertools, json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spec"))
import robot_spec
import cadquery as cq

COLORS = dict(al=(0.75, 0.76, 0.78), al_tube=(0.6, 0.62, 0.65), pc=(0.3, 0.6, 0.9),
              steel=(0.4, 0.4, 0.42), gear=(0.9, 0.7, 0.2), cots=(0.2, 0.2, 0.2), misc=(0.5, 0.3, 0.6))
DENSITY = dict(al=2.7e-3, al_tube=1.2e-3, pc=1.2e-3, steel=7.8e-3, gear=1.4e-3, misc=1.0e-3)  # g/mm3


def make_solid(part):
    k = part["kind"]
    if k == "box":
        cx, cy, cz = part["center"]; sx, sy, sz = part["size"]
        return cq.Workplane("XY").box(sx, sy, sz).translate((cx, cy, cz)).val()
    if k == "cyl":
        p1, p2 = cq.Vector(*part["p1"]), cq.Vector(*part["p2"])
        d = p2 - p1
        return cq.Solid.makeCylinder(part["r"], d.Length, p1, d.normalized())
    if k == "plate_xz":
        y0, y1 = part["y0"], part["y1"]
        solid = None
        for poly in part["polys"]:
            # XZ workplane: local x -> X, local y -> Z, normal -> -Y (CadQuery convention)
            pts = [(x, z) for x, z in poly]
            s = cq.Workplane("XZ").polyline(pts).close().extrude(-(y1 - y0)).translate((0, y0, 0)).val()
            solid = s if solid is None else solid.fuse(s)
        return solid.clean() if solid is not None else None
    if k == "arc_sheet":
        cx, cz, r0, r1, a0, a1 = part["cx"], part["cz"], part["r_in"], part["r_out"], part["a0"], part["a1"]
        y0, y1 = part["y0"], part["y1"]
        am = (a0 + a1) / 2
        P = lambda r, a: (cx + r * math.cos(math.radians(a)), cz + r * math.sin(math.radians(a)))
        wp = (cq.Workplane("XZ").moveTo(*P(r1, a0)).threePointArc(P(r1, am), P(r1, a1))
              .lineTo(*P(r0, a1)).threePointArc(P(r0, am), P(r0, a0)).close())
        return wp.extrude(-(y1 - y0)).translate((0, y0, 0)).val()
    raise ValueError(k)


def bbox_overlap(a, b, tol=0.0):
    return not (a.xmax < b.xmin - tol or b.xmax < a.xmin - tol or
                a.ymax < b.ymin - tol or b.ymax < a.ymin - tol or
                a.zmax < b.zmin - tol or b.zmax < a.zmin - tol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", type=float, default=0.0, help="intake arm angle, 0 deployed, 90 stowed")
    ap.add_argument("--out", default="exports")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    t0 = time.time()
    spec = robot_spec.build(arm_angle_deg=args.arm)
    solids = []
    for part in spec["parts"]:
        s = make_solid(part)
        if s is None or not s.isValid():
            print("INVALID solid:", part["name"]); sys.exit(2)
        solids.append((part, s, s.BoundingBox()))
    # Shafts pass through bearings and bores: cut a 0.1 mm clearance bore through every
    # non-shaft part each shaft crosses (plates, gears, wheels, pulleys). Motor bodies are
    # never bored: a shaft entering a motor body would be a real clash.
    bored = 0
    shafts = [(pp, ss) for pp, ss, _ in solids if pp.get("shaft")]
    for i, (part, s, b) in enumerate(solids):
        if part.get("shaft") or part["kind"] == "box" or "motor_5000" in part["name"]:
            continue
        for sp, ss in shafts:
            if sp["group"].split("_")[0] != part["group"].split("_")[0] and not (
                    sp["group"] in ("feed",) and part["group"] in ("shooter", "intake_arm")):
                continue
            if not bbox_overlap(ss.BoundingBox(), b):
                continue
            p1, p2 = cq.Vector(*sp["p1"]), cq.Vector(*sp["p2"])
            d = p2 - p1
            bore = cq.Solid.makeCylinder(sp["r"] + 0.1, d.Length + 2, p1 - d.normalized(), d.normalized())
            if s.intersect(bore).Volume() > 1e-3:
                s = s.cut(bore).clean()
                bored += 1
        solids[i] = (part, s, s.BoundingBox())
    print(f"built {len(solids)} solids ({bored} bores cut) in {time.time()-t0:.1f}s")

    # ---------------- interference check: every pair of distinct parts ----------------
    bad = []
    pairs = 0
    for (pa, sa, ba), (pb, sb, bb) in itertools.combinations(solids, 2):
        if not bbox_overlap(ba, bb):
            continue
        pairs += 1
        try:
            v = sa.intersect(sb).Volume()
        except Exception as e:  # OCC failure on exact tangency: treat as suspicious
            v = float("nan")
        if not (v <= 1e-3):
            bad.append((pa["name"], pb["name"], v))
    print(f"interference: {pairs} bbox-overlapping pairs tested, {len(bad)} interfering")
    for a, b, v in bad:
        print(f"   XX {a} <-> {b}: {v:.2f} mm3")

    # ---------------- minimum clearance between all non-touching neighbours ----------------
    # (distance between solids; report anything under 2 mm that is not an intended contact)
    close = []
    for (pa, sa, ba), (pb, sb, bb) in itertools.combinations(solids, 2):
        if not bbox_overlap(ba, bb, tol=3.0):
            continue
        if pa["group"] == pb["group"] and (pa["name"].rsplit("_", 1)[0] == pb["name"].rsplit("_", 1)[0]):
            continue
        try:
            d = sa.distance(sb)
        except Exception:
            continue
        if d < 2.0:
            close.append((pa["name"], pb["name"], d))
    print(f"close pairs (<2 mm, incl. intended contacts): {len(close)}")
    for a, b, d in close:
        print(f"   .. {a} <-> {b}: {d:.2f} mm")

    # ---------------- ball path clearance ----------------
    ball_bad = []
    CLR = 3.0
    for c in spec["checks"]:
        ball = cq.Solid.makeSphere(c["r"] + CLR, cq.Vector(*c["center"]))
        bb = ball.BoundingBox()
        for part, s, b in solids:
            if any(part["name"].startswith(a) for a in c["allow"]):
                continue
            if not bbox_overlap(bb, b):
                continue
            v = ball.intersect(s).Volume()
            if v > 1e-3:
                ball_bad.append((c["name"], part["name"], v))
    print(f"ball path: {len(spec['checks'])} positions x all parts, {len(ball_bad)} violations (clearance {CLR} mm)")
    for c, n, v in ball_bad:
        print(f"   XX ball@{c} <-> {n}: {v:.1f} mm3")

    # ---------------- mass / CG estimate ----------------
    M, Mx, My, Mz = 0.0, 0.0, 0.0, 0.0
    for part, s, b in solids:
        mass = part.get("mass")
        if mass is None:
            mass = s.Volume() * DENSITY.get(part["mat"], 1e-3)
        c = s.Center()
        M += mass; Mx += mass * c.x; My += mass * c.y; Mz += mass * c.z
    allbb = cq.Compound.makeCompound([s for _, s, _ in solids]).BoundingBox()
    env = dict(x=[round(allbb.xmin, 1), round(allbb.xmax, 1)], y=[round(allbb.ymin, 1), round(allbb.ymax, 1)],
               z=[round(allbb.zmin, 1), round(allbb.zmax, 1)])
    print(f"mass estimate {M/1000:.2f} kg, CG = ({Mx/M:.0f}, {My/M:.0f}, {Mz/M:.0f}) mm")
    print("envelope:", env)

    report = dict(arm_angle=args.arm, parts=len(solids), interferences=[dict(a=a, b=b, mm3=v) for a, b, v in bad],
                  close_pairs=[dict(a=a, b=b, mm=round(d, 2)) for a, b, d in close],
                  ball_violations=[dict(ball=c, part=n, mm3=v) for c, n, v in ball_bad],
                  mass_kg=round(M / 1000, 3), cg_mm=[round(Mx / M, 1), round(My / M, 1), round(Mz / M, 1)],
                  envelope_mm=env, summary=spec["summary"])

    if not args.no_export:
        os.makedirs(args.out, exist_ok=True)
        tag = args.tag or f"arm{int(args.arm)}"
        asm = cq.Assembly(name="ftc_biobuzz_bot")
        groups = {}
        for part, s, b in solids:
            g = part["group"]
            if g not in groups:
                groups[g] = cq.Assembly(name=g)
            groups[g].add(s, name=part["name"], color=cq.Color(*COLORS.get(part["mat"], (0.5, 0.5, 0.5))))
        for g, sub in groups.items():
            asm.add(sub, name=g)
        # ball path markers as their own component
        balls = cq.Assembly(name="pollen_path")
        for c in spec["checks"]:
            balls.add(cq.Solid.makeSphere(c["r"], cq.Vector(*c["center"])), name="ball_" + c["name"],
                      color=cq.Color(1.0, 0.85, 0.1, 0.5))
        asm.add(balls, name="pollen_path")
        step = os.path.join(args.out, f"ftc_biobuzz_bot_{tag}.step")
        asm.save(step)
        comp = cq.Compound.makeCompound([s for _, s, _ in solids])
        cq.exporters.export(comp, os.path.join(args.out, f"ftc_biobuzz_bot_{tag}.stl"), tolerance=0.05, angularTolerance=0.1)
        json.dump(spec["manifest"], open(os.path.join(args.out, "parts_manifest.json"), "w"), indent=1)
        print("exported", step)
    json.dump(report, open(os.path.join(args.out if not args.no_export else ".", f"check_arm{int(args.arm)}.json"), "w"), indent=1)
    print(f"done in {time.time()-t0:.1f}s")
    return 1 if (bad or ball_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
