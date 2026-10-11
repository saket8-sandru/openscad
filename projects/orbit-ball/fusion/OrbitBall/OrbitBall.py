"""
OrbitBall -- builds the twist "orbit ball" fidget natively in Fusion.

Run it from Fusion: Utilities > Add-Ins > Scripts and Add-Ins > + (Script from
device) > pick this OrbitBall folder > Run. It opens a new design and builds a
real, editable timeline: sketches, revolves, cuts, patterns, a copy-and-rotate
for the second half, then the pole pockets, a sleeve and three balls.

All sizes are the derived values in projects/orbit-ball/docs/README.md and are
checked by tools/orbitfit.py. NONE of them was measured on a real toy; the
ball diameter in particular is a design choice. To change a size, edit DIM
below and re-run. The values also land as Fusion user parameters, and several
features (cut depths, fillet, pattern counts) are driven by them.
"""

import math
import traceback

import adsk.core
import adsk.fusion

DIM = {                 # mm / deg -- keep in step with orbitfit.py
    "Sphere_Dia": 50.0,
    "Ball_Dia": 12.0,
    "Groove_Clr": 0.3,
    "Ball_Sink": 3.9,
    "Lip_Fillet": 0.3,
    "Lobes": 2,         # 2 = yin-yang S (recommended); 3 = three rings, magnets do NOT work
    "Bore_Dia": 5.8,    # printed undersize, drill to 6.0 for the 6 mm sleeve
    "Pocket_Dia": 9.6,
    "Nut_AF": 7.3,
    "Pocket_Depth": 9.0,
    "Seat_Depth": 3.5,
    "End_Play": 0.3,
    "Magnet_R": 20.0,
    "Magnet_Hole": 4.2,
    "Magnet_Depth": 2.6,
    "Lead_In": 1.0,
    "Rim_Chamfer": 0.5,
    "Sleeve_OD": 6.0,
    "Sleeve_ID": 4.3,
}

_app = None
_ui = None


def cm(v):
    """Fusion's internal length unit is cm."""
    return v / 10.0


def P(x, y, z):
    return adsk.core.Point3D.create(cm(x), cm(y), cm(z))


def vi(s):
    return adsk.core.ValueInput.createByString(s)


def collection(items):
    c = adsk.core.ObjectCollection.create()
    for i in items:
        c.add(i)
    return c


def derived():
    d = dict(DIM)
    d["Sphere_R"] = d["Sphere_Dia"] / 2
    d["Groove_R"] = d["Ball_Dia"] / 2 + d["Groove_Clr"]
    d["Track_R"] = d["Sphere_R"] - d["Ball_Sink"]
    d["Track_Angle"] = 90.0 / d["Lobes"]
    half = math.radians(d["Track_Angle"])
    d["Track_Offset"] = d["Track_R"] * math.cos(half)
    d["Arc_R"] = d["Track_R"] * math.sin(half)
    d["Sleeve_L"] = 2 * (d["Sphere_R"] - d["Pocket_Depth"]) + d["End_Play"]
    return d


def add_user_parameters(design, d):
    """Reference parameters, so the numbers are visible and editable in Fusion."""
    up = design.userParameters
    rows = [
        ("Sphere_Dia", f'{d["Sphere_Dia"]} mm', "mm", "listing width; assumes a true sphere"),
        ("Ball_Dia", f'{d["Ball_Dia"]} mm', "mm", "design choice -- NOT sourced"),
        ("Groove_Clr", f'{d["Groove_Clr"]} mm', "mm", "radial, ball to groove"),
        ("Ball_Sink", f'{d["Ball_Sink"]} mm', "mm", "ball centre below the shell"),
        ("Lip_Fillet", f'{d["Lip_Fillet"]} mm', "mm", "sets the real retention (0.36 mm/side)"),
        ("Lobes", f'{d["Lobes"]}', "", "2 = S; 3 = three rings"),
        ("Sphere_R", "Sphere_Dia / 2", "mm", ""),
        ("Groove_R", "Ball_Dia / 2 + Groove_Clr", "mm", ""),
        ("Track_R", "Sphere_R - Ball_Sink", "mm", "ball-centre sphere"),
        ("Track_Angle", "90 deg / Lobes", "deg", "track sketch plane from XZ"),
        ("Track_Offset", "Track_R * cos(Track_Angle)", "mm", "sketch u"),
        ("Arc_R", "Track_R * sin(Track_Angle)", "mm", "sketch v = arc radius = apex height"),
        ("Bore_Dia", f'{d["Bore_Dia"]} mm', "mm", "drill to 6.0 after printing"),
        ("Pocket_Dia", f'{d["Pocket_Dia"]} mm', "mm", ""),
        ("Nut_AF", f'{d["Nut_AF"]} mm', "mm", "hex, nut half only"),
        ("Pocket_Depth", f'{d["Pocket_Depth"]} mm', "mm", "pole to sleeve-end floor"),
        ("Seat_Depth", f'{d["Seat_Depth"]} mm', "mm", "cap seat"),
        ("End_Play", f'{d["End_Play"]} mm', "mm", ""),
        ("Sleeve_L", "2 * (Sphere_R - Pocket_Depth) + End_Play", "mm", "cut to measured halves + 0.25"),
        ("Magnet_R", f'{d["Magnet_R"]} mm', "mm", "Lobes = 2 only"),
        ("Magnet_Hole", f'{d["Magnet_Hole"]} mm', "mm", "4 x 2 mm N42"),
        ("Magnet_Depth", f'{d["Magnet_Depth"]} mm', "mm", "0.5 recess + glue"),
        ("Lead_In", f'{d["Lead_In"]} mm', "mm", "45 deg at groove ends"),
        ("Rim_Chamfer", f'{d["Rim_Chamfer"]} mm', "mm", ""),
    ]
    for name, expr, units, comment in rows:
        up.add(name, vi(expr), units, comment)


def sketch_on(root, plane, name):
    sk = root.sketches.add(plane)
    sk.name = name
    return sk


def to_sk(sk, x, y, z):
    return sk.modelToSketchSpace(P(x, y, z))


def axis_line(sk, a, b):
    ln = sk.sketchCurves.sketchLines.addByTwoPoints(to_sk(sk, *a), to_sk(sk, *b))
    ln.isConstruction = True
    return ln


def polyline(sk, pts):
    """Closed polygon through model-space points; returns the lines."""
    lines = sk.sketchCurves.sketchLines
    sp = [to_sk(sk, *p) for p in pts]
    out = [lines.addByTwoPoints(sp[0], sp[1])]
    for p in sp[2:]:
        out.append(lines.addByTwoPoints(out[-1].endSketchPoint, p))
    out.append(lines.addByTwoPoints(out[-1].endSketchPoint, out[0].startSketchPoint))
    return out


def revolve(root, profiles, axis, op, bodies=None, angle="360 deg"):
    rev = root.features.revolveFeatures
    inp = rev.createInput(profiles, axis, op)
    inp.setAngleExtent(False, vi(angle))
    if bodies:
        inp.participantBodies = bodies
    return rev.add(inp)


def extrude_cut(root, profiles, distance, body, negative=False):
    ext = root.features.extrudeFeatures
    inp = ext.createInput(profiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
    direction = (adsk.fusion.ExtentDirections.NegativeExtentDirection if negative
                 else adsk.fusion.ExtentDirections.PositiveExtentDirection)
    inp.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(vi(distance)), direction)
    inp.participantBodies = [body]
    return ext.add(inp)


def pattern_about_z(root, feature, count):
    cp = root.features.circularPatternFeatures
    inp = cp.createInput(collection([feature]), root.zConstructionAxis)
    inp.quantity = vi(str(count))
    inp.totalAngle = vi("360 deg")
    inp.isSymmetric = False
    return cp.add(inp)


def copy_rotate(root, body, axis, angle, name):
    new = root.features.copyPasteBodies.add(body).bodies.item(0)
    mv = root.features.moveFeatures
    inp = mv.createInput2(collection([new]))
    inp.defineAsRotate(axis, vi(angle))
    mv.add(inp)
    new.name = name
    return new


def offset_plane(root, mm):
    pl = root.constructionPlanes
    inp = pl.createInput()
    inp.setByOffset(root.xYConstructionPlane, vi(f"{mm} mm"))
    return pl.add(inp)


def build(design, d, notes):
    root = design.rootComponent
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    Ro, N = d["Sphere_R"], int(d["Lobes"])
    rb, rp = d["Bore_Dia"] / 2, d["Pocket_Dia"] / 2
    z_seat = Ro - d["Seat_Depth"]
    z_floor = Ro - d["Pocket_Depth"]
    c = d["Rim_Chamfer"]

    # 1. Body: revolve the half-section about Z (bore, cap seat and rim chamfer included)
    sk = sketch_on(root, root.xZConstructionPlane, "Body section")
    z_axis = axis_line(sk, (0, 0, -Ro - 5), (0, 0, Ro + 5))
    zc = c                                         # chamfer meets the sphere at z = c
    rc = math.sqrt(Ro * Ro - zc * zc)
    zr = math.sqrt(Ro * Ro - rp * rp)
    a0, a1 = math.atan2(zc, rc), math.atan2(zr, rp)
    am = (a0 + a1) / 2
    pole_target = to_sk(sk, rp, 0, zr)
    arc = sk.sketchCurves.sketchArcs.addByThreePoints(
        to_sk(sk, rc, 0, zc), to_sk(sk, Ro * math.cos(am), 0, Ro * math.sin(am)), pole_target)
    # Fusion orders an arc's start/end counter-clockwise about the sketch normal,
    # not in the order the points were given, so find the two ends by position.
    if arc.startSketchPoint.geometry.distanceTo(pole_target) < 1e-6:
        pole_pt, rim_pt = arc.startSketchPoint, arc.endSketchPoint
    else:
        pole_pt, rim_pt = arc.endSketchPoint, arc.startSketchPoint
    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(pole_pt, to_sk(sk, rp, 0, z_seat))
    l2 = lines.addByTwoPoints(l1.endSketchPoint, to_sk(sk, rb, 0, z_seat))
    l3 = lines.addByTwoPoints(l2.endSketchPoint, to_sk(sk, rb, 0, 0))
    l4 = lines.addByTwoPoints(l3.endSketchPoint, to_sk(sk, Ro - c, 0, 0))
    lines.addByTwoPoints(l4.endSketchPoint, rim_pt)
    if sk.profiles.count != 1:
        raise RuntimeError("Body section has %d profiles, expected 1" % sk.profiles.count)
    half = revolve(root, sk.profiles.item(0), z_axis, NEW).bodies.item(0)
    half.name = "Half_Head"

    # 2. Track plane: through Z, Track_Angle from XZ
    pin = root.constructionPlanes.createInput()
    pin.setByAngle(root.zConstructionAxis, vi("Track_Angle"), root.xZConstructionPlane)
    track_plane = root.constructionPlanes.add(pin)
    track_plane.name = "Track plane"
    n = track_plane.geometry.normal
    ax = (-n.y, n.x)                               # z x n: horizontal, in the plane
    s = math.hypot(*ax)
    ax = (ax[0] / s, ax[1] / s)

    # 3. Groove: circle at (Track_Offset along the axis, Arc_R above), revolved about
    #    the in-plane axis line; then patterned Lobes times about Z.
    sk = sketch_on(root, track_plane, "Track section")
    L = Ro + 5
    t_axis = axis_line(sk, (-L * ax[0], -L * ax[1], 0), (L * ax[0], L * ax[1], 0))
    u, v = d["Track_Offset"], d["Arc_R"]
    centre = (u * ax[0], u * ax[1], v)
    sk.sketchCurves.sketchCircles.addByCenterRadius(to_sk(sk, *centre), cm(d["Groove_R"]))
    groove = revolve(root, sk.profiles.item(0), t_axis, CUT, [half])
    groove.name = "Groove"
    pattern_about_z(root, groove, N).name = "Groove pattern"

    # 4. Lead-in: a 45-degree frustum around the groove end at the crossing on +X,
    #    patterned to every crossing (2N of them, 180/N apart).
    Rc, rg, li = d["Track_R"], d["Groove_R"], d["Lead_In"]
    sk = sketch_on(root, root.xZConstructionPlane, "Lead-in section")
    x_axis = axis_line(sk, (Rc, 0, -5), (Rc, 0, 5))
    polyline(sk, [(Rc, 0, 0), (Rc + rg + li, 0, 0), (Rc + rg, 0, li), (Rc, 0, li)])
    lead = revolve(root, sk.profiles.item(0), x_axis, CUT, [half])
    lead.name = "Lead-in"
    pattern_about_z(root, lead, 2 * N).name = "Lead-in pattern"

    # 5. Lip fillet on the groove/shell and lead-in/shell edges (last of the edge work)
    try:
        S = adsk.core.SurfaceTypes
        edges = []
        for e in half.edges:
            geoms = [f.geometry for f in e.faces]
            kinds = {g.surfaceType for g in geoms}
            if S.SphereSurfaceType not in kinds:
                continue
            hit = S.TorusSurfaceType in kinds
            for g in geoms:
                # Lead-in cones sit off the Z axis; the rim chamfer is a cone ON the
                # Z axis and must stay sharp, so leave its edge out.
                if g.surfaceType == S.ConeSurfaceType:
                    cone = adsk.core.Cone.cast(g)
                    if math.hypot(cone.origin.x, cone.origin.y) > 0.1:
                        hit = True
            if hit:
                edges.append(e)
        fil = root.features.filletFeatures
        inp = fil.createInput()
        inp.edgeSetInputs.addConstantRadiusEdgeSet(collection(edges), vi("Lip_Fillet"), True)
        fil.add(inp).name = "Lip fillet"
    except Exception:
        notes.append("Lip fillet failed -- add a 0.3 mm fillet on the groove lip edges by hand. "
                     "Without it the real retention is about 0.65 mm/side instead of 0.36.")

    # 6. Magnet holes on the parting face, on every arc axis (180/N apart)
    if N != 2:
        notes.append("Lobes = 3: the magnet detent does not work with steel balls (see the doc); "
                     "magnet holes are still cut so you can see where they would go.")
    sk = sketch_on(root, root.xYConstructionPlane, "Magnets")
    for k in range(2 * N):
        t = math.radians((k + 0.5) * 180.0 / N)
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            to_sk(sk, d["Magnet_R"] * math.cos(t), d["Magnet_R"] * math.sin(t), 0), cm(d["Magnet_Hole"] / 2))
    extrude_cut(root, collection([sk.profiles.item(i) for i in range(sk.profiles.count)]),
                "Magnet_Depth", half).name = "Magnet holes"

    # 7. Second half: the same body flipped 180 deg about X
    nut_half = copy_rotate(root, half, root.xConstructionAxis, "180 deg", "Half_Nut")

    # 8. Pole pockets, now that the halves differ
    pl = offset_plane(root, z_seat)
    pl.name = "Seat plane (head)"
    sk = sketch_on(root, pl, "Head pocket")
    sk.sketchCurves.sketchCircles.addByCenterRadius(to_sk(sk, 0, 0, z_seat), cm(rp))
    extrude_cut(root, sk.profiles.item(0), "Pocket_Depth - Seat_Depth", half, negative=True).name = "Head pocket"

    pl = offset_plane(root, -z_floor)
    pl.name = "Floor plane (nut)"
    sk = sketch_on(root, pl, "Nut pocket")
    rh = d["Nut_AF"] / math.sqrt(3)                # hex circumradius from across-flats
    polyline(sk, [(rh * math.cos(math.radians(60 * i)), rh * math.sin(math.radians(60 * i)), -z_floor)
                  for i in range(6)])
    extrude_cut(root, sk.profiles.item(0), "Pocket_Depth - Seat_Depth", nut_half, negative=True).name = "Nut pocket"

    # 9. Sleeve: 6 mm OD tube, Sleeve_L long, centred on the parting plane
    sk = sketch_on(root, root.xZConstructionPlane, "Sleeve section")
    zs = d["Sleeve_L"] / 2
    s_axis = axis_line(sk, (0, 0, -zs - 2), (0, 0, zs + 2))
    ri, ro = d["Sleeve_ID"] / 2, d["Sleeve_OD"] / 2
    polyline(sk, [(ri, 0, -zs), (ro, 0, -zs), (ro, 0, zs), (ri, 0, zs)])
    revolve(root, sk.profiles.item(0), s_axis, NEW).bodies.item(0).name = "Sleeve"
    notes.append("The sleeve overlaps the 5.8 mm bores by 0.1 mm on purpose: print at 5.8, drill to 6.0.")

    # 10. Balls: one at a top-arc apex, one at the next top arc, one at a bottom arc
    sk = sketch_on(root, track_plane, "Ball")
    r = d["Ball_Dia"] / 2
    top = (centre[0], centre[1], centre[2] + r)
    bot = (centre[0], centre[1], centre[2] - r)
    side = (centre[0] + r * ax[0], centre[1] + r * ax[1], centre[2])
    barc = sk.sketchCurves.sketchArcs.addByThreePoints(to_sk(sk, *top), to_sk(sk, *side), to_sk(sk, *bot))
    bline = sk.sketchCurves.sketchLines.addByTwoPoints(barc.startSketchPoint, barc.endSketchPoint)
    ball = revolve(root, sk.profiles.item(0), bline, NEW).bodies.item(0)
    ball.name = "Ball_1"
    copy_rotate(root, ball, root.zConstructionAxis, f"{360.0 / N} deg", "Ball_2")
    copy_rotate(root, ball, root.xConstructionAxis, "180 deg", "Ball_3")

    track_plane.isLightBulbOn = False
    return root


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        _app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(_app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        d = derived()
        add_user_parameters(design, d)
        notes = []
        build(design, d, notes)
        _app.activeViewport.fit()
        msg = ("Orbit Ball built: Half_Head, Half_Nut, Sleeve, Ball_1-3.\n\n"
               f"Track_Offset = Arc_R = {d['Track_Offset']:.3f} mm, groove dia {2 * d['Groove_R']:.1f} mm, "
               f"ball {d['Ball_Dia']:g} mm (a design choice, not a measured size).")
        if notes:
            msg += "\n\nNotes:\n- " + "\n- ".join(notes)
        _ui.messageBox(msg)
    except Exception:
        if _ui:
            _ui.messageBox("OrbitBall failed:\n{}".format(traceback.format_exc()))
