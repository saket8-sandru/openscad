# Build the FTC BIOBUZZ robot natively in Fusion 360 from spec/robot_spec.py.
#
# Two ways to run it:
#   1. Fusion: Utilities > Add-Ins > Scripts tab > green "+" > pick this folder > Run.
#   2. Through the FusionMCP bridge:  fusion_run_script_file("<repo>/projects/ftc-biobuzz-bot/fusion/build_in_fusion.py")
#
# It creates one component per sub-assembly (pod_L, pod_R, chassis, shooter, feed,
# intake_arm, electronics) with named bodies. The design is switched to Direct
# Modeling so temporary B-Rep primitives can be added directly; plates with
# outlines are made with sketches + extrudes so they stay editable.
#
# Units: the spec is in mm; the Fusion API is in cm (divided by 10 here).
import math, os, sys, traceback
import adsk.core, adsk.fusion

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
import importlib
import robot_spec
importlib.reload(robot_spec)

CM = 0.1  # mm -> cm


def P3(x, y, z):
    return adsk.core.Point3D.create(x * CM, y * CM, z * CM)


def V3(x, y, z):
    return adsk.core.Vector3D.create(x, y, z)


def make_box(tbm, part):
    cx, cy, cz = part["center"]
    sx, sy, sz = part["size"]
    obb = adsk.core.OrientedBoundingBox3D.create(P3(cx, cy, cz), V3(1, 0, 0), V3(0, 1, 0),
                                                 sx * CM, sy * CM, sz * CM)
    return tbm.createBox(obb)


def make_cyl(tbm, part):
    p1, p2 = part["p1"], part["p2"]
    return tbm.createCylinderOrCone(P3(*p1), part["r"] * CM, P3(*p2), part["r"] * CM)


def extrude_xz_profile(comp, draw, y0, y1, name):
    """draw(sketch) adds closed curves at model y=0; the profile is extruded to y0..y1."""
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.name = name
    draw(sk)
    prof = sk.profiles.item(sk.profiles.count - 1)
    ext = comp.features.extrudeFeatures
    inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByReal((y1 - y0) * CM), True)
    feat = ext.add(inp)
    body = feat.bodies.item(0)
    yc = (y0 + y1) / 2
    if abs(yc) > 1e-9:
        mv = comp.features.moveFeatures
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        m = adsk.core.Matrix3D.create()
        m.translation = V3(0, yc * CM, 0)
        mv.add(mv.createInput(coll, m))
    sk.isVisible = False
    return body


def draw_polyline(sk, poly):
    pts = [sk.modelToSketchSpace(P3(x, 0, z)) for x, z in poly]
    lines = sk.sketchCurves.sketchLines
    n = len(pts)
    for i in range(n):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % n])


def draw_arc_sheet(sk, part):
    cx, cz, r0, r1, a0, a1 = part["cx"], part["cz"], part["r_in"], part["r_out"], part["a0"], part["a1"]
    am = (a0 + a1) / 2
    def pt(r, a):
        return sk.modelToSketchSpace(P3(cx + r * math.cos(math.radians(a)), 0, cz + r * math.sin(math.radians(a))))
    arcs, lines = sk.sketchCurves.sketchArcs, sk.sketchCurves.sketchLines
    arcs.addByThreePoints(pt(r1, a0), pt(r1, am), pt(r1, a1))
    lines.addByTwoPoints(pt(r1, a1), pt(r0, a1))
    arcs.addByThreePoints(pt(r0, a1), pt(r0, am), pt(r0, a0))
    lines.addByTwoPoints(pt(r0, a0), pt(r1, a0))


def combine_join(comp, target, tools):
    if not tools:
        return target
    coll = adsk.core.ObjectCollection.create()
    for t in tools:
        coll.add(t)
    cf = comp.features.combineFeatures
    inp = cf.createInput(target, coll)
    inp.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    inp.isKeepToolBodies = False
    cf.add(inp)
    return target


def build(arm_angle_deg=0.0, progress=None):
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Open a Fusion design document first.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = design.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()

    spec = robot_spec.build(arm_angle_deg=arm_angle_deg)
    comps = {}
    top = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    top.component.name = "ftc_biobuzz_bot"

    def comp_for(group):
        if group not in comps:
            occ = top.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            occ.component.name = group
            comps[group] = occ.component
        return comps[group]

    made = 0
    for i, part in enumerate(spec["parts"]):
        comp = comp_for(part["group"])
        k = part["kind"]
        if k == "box":
            body = comp.bRepBodies.add(make_box(tbm, part))
        elif k == "cyl":
            body = comp.bRepBodies.add(make_cyl(tbm, part))
        elif k == "plate_xz":
            bodies = [extrude_xz_profile(comp, lambda sk, poly=poly: draw_polyline(sk, poly),
                                         part["y0"], part["y1"], part["name"] + "_sk%d" % j)
                      for j, poly in enumerate(part["polys"])]
            body = combine_join(comp, bodies[0], bodies[1:])
        elif k == "arc_sheet":
            body = extrude_xz_profile(comp, lambda sk: draw_arc_sheet(sk, part),
                                      part["y0"], part["y1"], part["name"] + "_sk")
        else:
            continue
        body.name = part["name"]
        made += 1
        if progress and i % 10 == 0:
            progress(i, len(spec["parts"]))

    # POLLEN markers along the ball path, in their own component
    pc = comp_for("pollen_path")
    for c in spec["checks"]:
        x, y, z = c["center"]
        sph = tbm.createSphere(P3(x, y, z), c["r"] * CM)
        b = pc.bRepBodies.add(sph)
        b.name = "ball_" + c["name"]
        b.opacity = 0.4
    app.activeViewport.fit()
    return dict(bodies=made, summary=spec["summary"], manifest=spec["manifest"])


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        s, ok = ui.inputBox("Intake arm angle (0 = deployed, 90 = stowed):", "FTC BIOBUZZ bot", "0")
        if not ok:
            return
        res = build(float(s))
        ui.messageBox("Built %d bodies.\nFlywheel centre (mm): %s\nHood wrap: %.0f deg" % (
            res["bodies"], res["summary"]["fly_center"], res["summary"]["hood_wrap_deg"]))
        return res
    except Exception:
        ui.messageBox("Build failed:\n" + traceback.format_exc())
