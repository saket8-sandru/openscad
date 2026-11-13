"""
FTC BIOBUZZ (2026-27) shooter robot -- parametric geometry definition.

Pure Python, no CAD dependency. `build()` returns a dict with:
  parts     : list of solid primitives (box / cyl / plate_xz / arc_sheet)
  manifest  : COTS parts list with positions and axes, for swapping placeholders
              with real goBILDA STEP models
  checks    : ball positions along the game-piece path, with the parts that
              are *allowed* to touch the ball at that point
  summary   : key derived numbers (ratios, speeds, envelope)

Coordinate system (mm): +X forward (intake side), +Y left, +Z up.
Origin on the field floor, under the robot centre.

Two CAD back-ends consume this file unchanged:
  cad/build_cadquery.py      -> STEP / STL / PNG + interference check (runs here)
  fusion/build_in_fusion.py  -> native Fusion 360 bodies (runs inside Fusion)

Every dimension that was NOT verified from a manufacturer drawing is marked
ASSUMED in the comments; see docs/README.md for the list.
"""
import math

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
P = dict(
    # ---- game piece: BIOBUZZ POLLEN, ~2.8 in (7.1 cm) polyethylene ball ----
    ball_d=71.1,
    hood_comp=10.0,      # ball compression between flywheel and hood
    feed_comp=10.0,      # compression under the feed roller (on the deck)
    intake_comp=8.0,     # compression under the intake arm roller (ball on the floor)

    # ---- drivetrain ----
    wheel_d=104.0,       # goBILDA GripForce mecanum, 104 mm
    wheel_w=45.0,        # ASSUMED (not published in text; check the STEP)
    wheel_x=130.0,       # half wheelbase
    wheel_y=140.0,       # half track (wheel centre)
    axle_z=52.0,         # = wheel radius
    ground=18.0,         # bottom of the pod plates
    plate_t=3.0,
    wheel_spacer=2.0,    # wheel face to outer plate
    cavity=24.0,         # gear cavity between outer and inner pod plate
    gear_w=8.0,
    pod_x0=-165.0, pod_x1=160.0, pod_top=95.0,

    # 12:1 two-stage spur reduction, MOD 1 (printed or 20DP-equivalent)
    mod=1.0,
    s1=(16, 64),         # motor pinion : intermediate  (4:1)
    s2=(20, 60),         # intermediate : wheel axle    (3:1)
    beta_deg=10.0,       # gear-train lean, up and inboard from the axle

    # bare motor: goBILDA 5000-0002-4008, RS-555 class, 6000 rpm
    motor_d=36.0,        # ASSUMED (RS-555 class)
    motor_l=72.0,        # ASSUMED body incl. encoder cap
    motor_rpm=6000.0,
    shaft_r=4.0,         # 8 mm REX, drawn as a round shaft

    # ---- deck / chassis ----
    deck_t=3.0,
    deck_top=20.0,
    deck_x0=-165.0, deck_x1=115.0,
    lip_angle_deg=35.0, lip_len=22.0,
    tube=24.0,           # square cross tube

    # ---- shooter ----
    fly_d=72.0, fly_w=30.0,     # two 72 mm wheels side by side (placeholder)
    fly_x=30.0,
    hood_t=3.0,
    launch_deg=45.0,
    chan_hw=40.0,        # half-width of ball channel (between shooter plates)
    shooter_gear_mod=0.8, fly_gear=(24, 24), fly_motor_angle_deg=45.0,

    # ---- feed roller (also the intake arm pivot) ----
    feed_wheel_d=48.0, feed_wheel_w=16.0, feed_n=3,
    feed_clear=2.5,      # min gap feed roller <-> flywheel
    feed_gear=(24, 72), feed_motor_angle_deg=30.0,

    # ---- intake swing arm ----
    arm_hw=15.0, arm_boss_r=16.0, arm_plate_y=70.0,   # inner face of arm plates
    arm_roller_x=160.0,
    gecko_d=48.0, gecko_w=16.0, gecko_n=3,
    vector_d=57.0, vector_w=44.0,                     # AndyMark 2.25in vectored intake wheel
    pulley_r=13.5, pulley_y=(-83.0, -75.0),
    arm_angle_deg=0.0,   # 0 = deployed, 90 = stowed

    # ---- electronics placeholders ----
    hub=(30.0, 143.0, 103.0),    # REV Control Hub standing: x, y, z size
    battery=(46.0, 142.0, 25.0),
)


def pd(n, mod):
    return n * mod


def build(**over):
    p = dict(P)
    p.update(over)
    parts, manifest, checks = [], [], []
    S = {}  # summary

    def add(kind, name, group, **kw):
        d = dict(kind=kind, name=name, group=group)
        d.update(kw)
        parts.append(d)
        return d

    def box(name, group, x0, x1, y0, y1, z0, z1, **kw):
        return add("box", name, group,
                   center=[(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
                   size=[x1 - x0, y1 - y0, z1 - z0], **kw)

    def cyl_y(name, group, x, z, y0, y1, r, **kw):
        if "shaft" in name or name.endswith("_8REX"):
            kw.setdefault("shaft", True)
        return add("cyl", name, group, p1=[x, y0, z], p2=[x, y1, z], r=r, **kw)

    ball_r = p["ball_d"] / 2

    # ======================================================================
    # DRIVE PODS (left/right, each with a front and rear wheel module)
    # ======================================================================
    wr = p["wheel_d"] / 2
    y_wheel_in = p["wheel_y"] - p["wheel_w"] / 2
    y_outer1 = y_wheel_in - p["wheel_spacer"]          # outer plate, outer face
    y_outer0 = y_outer1 - p["plate_t"]
    y_inner1 = y_outer0 - p["cavity"]                  # inner plate, outer face
    y_inner0 = y_inner1 - p["plate_t"]
    # gear planes inside the cavity
    yA1 = y_outer0 - 1.0
    yA0 = yA1 - p["gear_w"]                            # plane A: motor pinion + 64T
    yB0 = y_inner1 + 2.0
    yB1 = yB0 + p["gear_w"]                            # plane B: 20T + axle 60T

    m = p["mod"]
    cd1 = (pd(p["s1"][0], m) + pd(p["s1"][1], m)) / 2
    cd2 = (pd(p["s2"][0], m) + pd(p["s2"][1], m)) / 2
    beta = math.radians(p["beta_deg"])
    gr = lambda n: pd(n, m) / 2 - 0.3                  # drawn slightly under pitch radius
    ratio = (p["s1"][1] / p["s1"][0]) * (p["s2"][1] / p["s2"][0])
    S["drive_ratio"] = ratio
    S["wheel_rpm"] = p["motor_rpm"] / ratio
    S["drive_speed_m_s"] = S["wheel_rpm"] / 60 * math.pi * p["wheel_d"] / 1000
    motor_r = p["motor_d"] / 2
    S["motor_to_wheel_gap"] = (cd1 + cd2) - wr - motor_r

    for side, sy in (("L", 1), ("R", -1)):
        g = f"pod_{side}"
        Y = lambda y: sy * y
        yo = sorted([Y(y_outer0), Y(y_outer1)])
        yi = sorted([Y(y_inner0), Y(y_inner1)])
        add("plate_xz", f"{g}_outer_plate", g,
            polys=[rect(p["pod_x0"], p["pod_x1"], p["ground"], p["pod_top"])],
            y0=yo[0], y1=yo[1], mat="al")
        add("plate_xz", f"{g}_inner_plate", g,
            polys=[rect(p["pod_x0"], p["pod_x1"], p["ground"], p["pod_top"])],
            y0=yi[0], y1=yi[1], mat="al")
        for pos, sx in (("F", 1), ("B", -1)):
            n = f"{g}_{pos}"
            xw = sx * p["wheel_x"]
            # intermediate shaft and motor lean up & inboard from the axle
            xi = xw - sx * cd2 * math.cos(beta)
            zi = p["axle_z"] + cd2 * math.sin(beta)
            xm = xi - sx * cd1 * math.cos(beta)
            zm = zi + cd1 * math.sin(beta)
            # wheel
            yw = sorted([Y(y_wheel_in), Y(p["wheel_y"] + p["wheel_w"] / 2)])
            cyl_y(f"{n}_mecanum_104", n, xw, p["axle_z"], yw[0], yw[1], wr, mat="cots", mass=236)
            manifest.append(dict(part="GripForce Mecanum Wheel 104mm (3625-0202-0104)",
                                 instance=f"{n}_mecanum_104", axis="Y",
                                 center=[xw, sy * p["wheel_y"], p["axle_z"]],
                                 note="set of 4: two left-roller, two right-roller; X pattern viewed from above"))
            # axle: inner plate -> 5 mm past wheel face
            ya = sorted([Y(y_inner0 - 2.5), Y(p["wheel_y"] + p["wheel_w"] / 2 + 5)])
            cyl_y(f"{n}_axle_8REX", n, xw, p["axle_z"], ya[0], ya[1], p["shaft_r"], mat="steel")
            # intermediate shaft: through both plates
            ys = sorted([Y(y_inner0 - 1.5), Y(y_outer1 + 1.0)])      # 1 mm short of the wheel face
            cyl_y(f"{n}_idler_shaft_8REX", n, xi, zi, ys[0], ys[1], p["shaft_r"], mat="steel")
            # gears, plane A (near outer plate)
            ya_ = sorted([Y(yA0), Y(yA1)])
            cyl_y(f"{n}_pinion_{p['s1'][0]}T", n, xm, zm, ya_[0], ya_[1], gr(p["s1"][0]), mat="gear")
            cyl_y(f"{n}_gear_{p['s1'][1]}T", n, xi, zi, ya_[0], ya_[1], gr(p["s1"][1]), mat="gear")
            # gears, plane B (near inner plate)
            yb_ = sorted([Y(yB0), Y(yB1)])
            cyl_y(f"{n}_gear_{p['s2'][0]}T", n, xi, zi, yb_[0], yb_[1], gr(p["s2"][0]), mat="gear")
            cyl_y(f"{n}_gear_{p['s2'][1]}T", n, xw, p["axle_z"], yb_[0], yb_[1], gr(p["s2"][1]), mat="gear")
            # motor, outboard of the outer plate, body beside the wheel
            yf = y_outer1 + 1.0                       # faceplate (1 mm mount gap)
            ym = sorted([Y(yf), Y(yf + p["motor_l"])])
            cyl_y(f"{n}_motor_5000", n, xm, zm, ym[0], ym[1], motor_r, mat="cots", mass=254)
            ysh = sorted([Y(yA0 - 1.0), Y(yf)])
            cyl_y(f"{n}_motor_shaft", n, xm, zm, ysh[0], ysh[1], p["shaft_r"], mat="steel")
            manifest.append(dict(part="5000 Series 12VDC Motor, 8mm REX pinion shaft (5000-0002-4008)",
                                 instance=f"{n}_motor_5000", axis="Y",
                                 face_center=[xm, sy * yf, zm],
                                 shaft_dir=[0, -sy, 0],
                                 note="faceplate on the OUTER pod plate, body outboard beside the wheel"))

    # ======================================================================
    # DECK, LIP, CROSS TUBE, ELECTRONICS
    # ======================================================================
    dz1 = p["deck_top"]; dz0 = dz1 - p["deck_t"]
    box("deck", "chassis", p["deck_x0"], p["deck_x1"], -y_inner0, y_inner0, dz0, dz1, mat="al")
    # entry lip: deck front edge bent down
    la = math.radians(p["lip_angle_deg"])
    ux, uz = math.cos(la), -math.sin(la)       # along the lip, forward-down
    nx, nz = -uz, ux                           # normal, up-forward
    x0, z0 = p["deck_x1"], dz1
    L, t = p["lip_len"], p["deck_t"]
    lip_poly = [[x0, z0], [x0 + ux * L, z0 + uz * L],
                [x0 + ux * L - nx * t, z0 + uz * L - nz * t], [x0 - nx * t, z0 - nz * t]]
    # drop the lip's rear-bottom corner onto the deck's front face so the two sheets meet cleanly
    lip_poly[3] = [x0, dz0]
    add("plate_xz", "entry_lip", "chassis", polys=[lip_poly],
        y0=-(p["chan_hw"] + 5), y1=p["chan_hw"] + 5, mat="al")
    S["lip_tip_z"] = z0 + uz * L - nz * t
    # rear cross tube (above the deck, in front of the control hub)
    hub_x, hub_y, hub_z = p["hub"]
    hx1 = p["deck_x0"] + hub_x
    box("rear_cross_tube", "chassis", hx1 + 1, hx1 + 1 + p["tube"], -y_inner0, y_inner0,
        dz1, dz1 + p["tube"], mat="al_tube")
    box("control_hub_placeholder", "electronics", p["deck_x0"], hx1, -hub_y / 2, hub_y / 2,
        dz1, dz1 + hub_z, mat="cots", mass=300)
    bx, by, bz = p["battery"]
    bx0 = hx1 + 1 + p["tube"] + 2
    box("battery_placeholder", "electronics", bx0, bx0 + bx, -by / 2, by / 2, dz1, dz1 + bz,
        mat="cots", mass=550)

    # ======================================================================
    # SHOOTER: flywheel over a curved hood (the "curved ramp")
    # ======================================================================
    fr = p["fly_d"] / 2
    R_hood = fr + p["ball_d"] - p["hood_comp"]         # hood inner radius
    R_ball = fr + ball_r - p["hood_comp"]              # ball-centre orbit radius
    xf = p["fly_x"]
    zf = dz1 + p["hood_t"] + R_hood                    # hood sheet lies on the deck at the nip
    th_in = -90.0
    th_out = p["launch_deg"] - 270.0
    S.update(fly_center=[xf, zf], hood_R=R_hood, ball_orbit_R=R_ball,
             hood_wrap_deg=th_in - th_out, fly_tip_speed_m_s=p["motor_rpm"] / 60 * math.pi * p["fly_d"] / 1000)
    hw = p["chan_hw"]
    add("arc_sheet", "hood", "shooter", cx=xf, cz=zf, r_in=R_hood, r_out=R_hood + p["hood_t"],
        a0=th_out, a1=th_in, y0=-hw, y1=hw, mat="pc")
    cyl_y("flywheel_72x30", "shooter", xf, zf, -p["fly_w"] / 2, p["fly_w"] / 2, fr, mat="cots", mass=120)
    manifest.append(dict(part="Flywheel: 2x 72mm wheel, 8mm REX bore (e.g. goBILDA 72mm wheel of choice)",
                         instance="flywheel_72x30", axis="Y", center=[xf, 0, zf]))
    # shaft stops 0.1 mm short of the flywheel-motor faceplate on the right (motor sits 19.2 mm off-axis)
    cyl_y("flywheel_shaft_8REX", "shooter", xf, zf, -(hw + p["plate_t"] + 0.9), hw + 8, p["shaft_r"], mat="steel")
    # flywheel drive: 1:1 MOD 0.8 gears inside the right plate, motor outboard right
    gm = p["shooter_gear_mod"]
    g_out = -(hw - 2) ; g_in = g_out + p["gear_w"]          # gear plane just inside the right plate (y -38..-30)
    cyl_y("flywheel_gear_24T", "shooter", xf, zf, g_out, g_in, pd(p["fly_gear"][1], gm) / 2 - 0.3, mat="gear")
    cdf = (pd(p["fly_gear"][0], gm) + pd(p["fly_gear"][1], gm)) / 2
    a = math.radians(p["fly_motor_angle_deg"])
    xfm, zfm = xf + cdf * math.cos(a), zf + cdf * math.sin(a)
    cyl_y("flywheel_motor_pinion_24T", "shooter", xfm, zfm, g_out, g_in, pd(p["fly_gear"][0], gm) / 2 - 0.3, mat="gear")
    yface = -(hw + p["plate_t"] + 1.0)
    cyl_y("flywheel_motor_5000", "shooter", xfm, zfm, yface - p["motor_l"], yface, motor_r, mat="cots", mass=254)
    cyl_y("flywheel_motor_shaft", "shooter", xfm, zfm, yface, g_in + 1.0, p["shaft_r"], mat="steel")   # face -> past the pinion
    manifest.append(dict(part="5000 Series 12VDC Motor (5000-0002-4008) - flywheel",
                         instance="flywheel_motor_5000", axis="Y",
                         face_center=[xfm, yface, zfm], shaft_dir=[0, 1, 0]))

    # ======================================================================
    # FEED ROLLER (fixed, also the intake-arm pivot)
    # ======================================================================
    fwr = p["feed_wheel_d"] / 2
    z_feed = dz1 + p["ball_d"] + fwr - p["feed_comp"]
    need = fr + fwr + p["feed_clear"]
    dx = math.sqrt(max(need ** 2 - (z_feed - zf) ** 2, 0))
    x_feed = xf + dx
    S["feed_center"] = [x_feed, z_feed]
    # hand-over check: feed roller release point vs flywheel grab point on the deck line
    zb = dz1 + ball_r
    reach_feed = math.sqrt((ball_r + fwr) ** 2 - (z_feed - zb) ** 2)
    grab_fly = math.sqrt((fr + ball_r) ** 2 - (zf - zb) ** 2)
    S["handover_overlap_mm"] = (xf + grab_fly) - (x_feed - reach_feed)
    # feed wheels
    tot = p["feed_n"] * p["feed_wheel_w"]
    for i in range(p["feed_n"]):
        y0 = -tot / 2 + i * p["feed_wheel_w"]
        cyl_y(f"feed_gecko48_{i}", "feed", x_feed, z_feed, y0 + 0.5, y0 + p["feed_wheel_w"] - 0.5, fwr,
              mat="cots", mass=17)
    manifest.append(dict(part=f"{p['feed_n']}x GripForce Gecko Wheel 48mm, 8mm REX (3613-4008-0048) - feed roller",
                         instance="feed_gecko48_*", axis="Y", center=[x_feed, 0, z_feed]))
    # feed shaft spans: right belt pulley .. left feed gear
    py0, py1 = p["pulley_y"]
    yg0 = p["arm_plate_y"] - p["plate_t"] - 1.0 - 8.0      # feed gear between shooter plate and arm plate
    yg1 = yg0 + 8.0
    # (shooter plate outer face is at hw+plate_t; keep 1 mm from it)
    yg0 = max(yg0, hw + p["plate_t"] + 1.0)
    yg1 = yg0 + p["gear_w"]
    cyl_y("feed_shaft_8REX", "feed", x_feed, z_feed, py0 - 1.0, p["arm_plate_y"] + p["plate_t"] + 2.0,
          p["shaft_r"], mat="steel")
    cyl_y("feed_gear_72T", "feed", x_feed, z_feed, yg0, yg1, pd(p["feed_gear"][1], gm) / 2 - 0.3, mat="gear")
    cdd = (pd(p["feed_gear"][0], gm) + pd(p["feed_gear"][1], gm)) / 2
    a = math.radians(180 - p["feed_motor_angle_deg"])        # up and rearward
    xdm, zdm = x_feed + cdd * math.cos(a), z_feed + cdd * math.sin(a)
    cyl_y("feed_motor_pinion_24T", "feed", xdm, zdm, yg0, yg1, pd(p["feed_gear"][0], gm) / 2 - 0.3, mat="gear")
    yface = yg1 + 1.0
    cyl_y("feed_motor_5000", "feed", xdm, zdm, yface, yface + p["motor_l"], motor_r, mat="cots", mass=254)
    cyl_y("feed_motor_shaft", "feed", xdm, zdm, yg0 - 1.0, yface, p["shaft_r"], mat="steel")
    manifest.append(dict(part="5000 Series 12VDC Motor (5000-0002-4008) - feed roller + intake",
                         instance="feed_motor_5000", axis="Y",
                         face_center=[xdm, yface, zdm], shaft_dir=[0, -1, 0]))
    S["feed_ratio"] = p["feed_gear"][1] / p["feed_gear"][0]
    S["feed_surface_m_s"] = p["motor_rpm"] / S["feed_ratio"] / 60 * math.pi * p["feed_wheel_d"] / 1000

    # ======================================================================
    # SHOOTER SIDE PLATES (stand on the deck, carry flywheel, motors, feed shaft)
    # ======================================================================
    R_plate = R_hood + p["hood_t"] + 10.0
    sector = arc_poly(xf, zf, 0.0, R_plate, th_out - 10.0, th_in + 5.0)
    hub_disc = circle_poly(xf, zf, 45.0)
    strip = stadium_poly(xf, zf, x_feed, z_feed, 20.0)
    pivot_disc = circle_poly(x_feed, z_feed, 22.0)
    polys = [clip_zmin(q, dz1) for q in (sector, hub_disc, strip, pivot_disc)]
    for side, sy in (("L", 1), ("R", -1)):
        ys = sorted([sy * hw, sy * (hw + p["plate_t"])])
        add("plate_xz", f"shooter_plate_{side}", "shooter", polys=polys, y0=ys[0], y1=ys[1], mat="al")

    # ======================================================================
    # INTAKE SWING ARM (pivots on the feed shaft)
    # ======================================================================
    ang = math.radians(p["arm_angle_deg"])
    gr_ = p["gecko_d"] / 2
    z_roller_dep = p["ball_d"] + gr_ - p["intake_comp"]      # ball on the floor under the roller
    vx, vz = p["arm_roller_x"] - x_feed, z_roller_dep - z_feed
    arm_len = math.hypot(vx, vz)
    # rotate the deployed vector by arm_angle (positive = up / stow)
    rx = vx * math.cos(ang) - vz * math.sin(ang)
    rz = vx * math.sin(ang) + vz * math.cos(ang)
    xr, zr = x_feed + rx, z_feed + rz
    S.update(arm_len=arm_len, arm_roller=[xr, zr], arm_roller_deployed=[p["arm_roller_x"], z_roller_dep])
    bar = stadium_poly(x_feed, z_feed, xr, zr, p["arm_hw"])
    boss1 = circle_poly(x_feed, z_feed, p["arm_boss_r"])
    boss2 = circle_poly(xr, zr, p["arm_boss_r"])
    for side, sy in (("L", 1), ("R", -1)):
        ys = sorted([sy * p["arm_plate_y"], sy * (p["arm_plate_y"] + p["plate_t"])])
        add("plate_xz", f"arm_plate_{side}", "intake_arm", polys=[bar, boss1, boss2], y0=ys[0], y1=ys[1], mat="al")
    # roller shaft
    cyl_y("arm_roller_shaft_8REX", "intake_arm", xr, zr, py0 - 1.0, p["arm_plate_y"] + p["plate_t"] + 2.0,
          p["shaft_r"], mat="steel")
    # centre gecko wheels
    tot = p["gecko_n"] * p["gecko_w"]
    for i in range(p["gecko_n"]):
        y0 = -tot / 2 + i * p["gecko_w"]
        cyl_y(f"arm_gecko48_{i}", "intake_arm", xr, zr, y0 + 0.5, y0 + p["gecko_w"] - 0.5, gr_, mat="cots", mass=17)
    manifest.append(dict(part=f"{p['gecko_n']}x GripForce Gecko Wheel 48mm (3613-4008-0048) - intake roller centre",
                         instance="arm_gecko48_*", axis="Y", center=[xr, 0, zr]))
    # vectored wheels at the ends, pulling toward centre
    vy0 = tot / 2 + 1.0
    for side, sy in (("L", 1), ("R", -1)):
        ys = sorted([sy * vy0, sy * (vy0 + p["vector_w"])])
        cyl_y(f"arm_vector_wheel_{side}", "intake_arm", xr, zr, ys[0], ys[1], p["vector_d"] / 2, mat="cots", mass=60)
    manifest.append(dict(part="AndyMark 2.25in HD Mecanum Vectored Intake Wheel, L+R pair - intake roller ends",
                         instance="arm_vector_wheel_*", axis="Y", center=[xr, 0, zr],
                         note="left-hand wheel on +Y side, right-hand on -Y, so both pull toward the centre"))
    S["vector_wheel_fits"] = vy0 + p["vector_w"] < p["arm_plate_y"] - 0.5
    # belt drive, right side: pulleys + belt drawn as one stadium (placeholder)
    add("plate_xz", "arm_belt_drive_placeholder", "intake_arm",
        polys=[stadium_poly(x_feed, z_feed, xr, zr, p["pulley_r"])], y0=py0, y1=py1, mat="misc")

    # ======================================================================
    # BALL PATH CHECKS
    # ======================================================================
    def chk(name, x, z, allow):
        checks.append(dict(name=name, center=[x, 0.0, z], r=ball_r, allow=allow))

    rollers = ["arm_gecko48_", "arm_vector_wheel_"]
    feeders = ["feed_gecko48_"]
    chk("floor_under_arm_roller", p["arm_roller_x"], ball_r, rollers + ["entry_lip"])
    chk("climbing_lip", p["deck_x1"] + 12, ball_r + 8, rollers + ["entry_lip", "deck"])
    chk("on_deck_front_edge", p["deck_x1"] - 10, zb, rollers + feeders + ["deck", "entry_lip"])
    chk("under_feed_roller", x_feed, zb, feeders + ["deck"] + rollers)
    chk("flywheel_grab", xf + grab_fly - 2, zb, feeders + ["deck", "flywheel_72x30"])
    for th in (-90, -110, -130, -150, -170, -190, -210, th_out):
        t = math.radians(th)
        chk(f"hood_{int(th)}", xf + R_ball * math.cos(t), zf + R_ball * math.sin(t),
            ["hood", "flywheel_72x30", "deck", "feed_gecko48_"])
    t = math.radians(th_out)
    ex, ez = xf + R_ball * math.cos(t), zf + R_ball * math.sin(t)
    L = math.radians(p["launch_deg"])
    for d in (25, 50, 75, 100, 130, 160, 200):
        chk(f"launch_{d}", ex + d * math.cos(L), ez + d * math.sin(L), ["hood"])

    # envelope summary
    S["ball_r"] = ball_r
    S["zf"] = zf
    S["hood_exit_lip"] = [xf + (R_hood + p["hood_t"]) * math.cos(t), zf + (R_hood + p["hood_t"]) * math.sin(t)]
    return dict(params=p, parts=parts, manifest=manifest, checks=checks, summary=S)


# --------------------------------------------------------------------------
# 2D helpers (polygons in the XZ plane as [[x, z], ...], counter-clockwise)
# --------------------------------------------------------------------------
def rect(x0, x1, z0, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def circle_poly(cx, cz, r, n=72):
    return [[cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


def arc_poly(cx, cz, r0, r1, a0, a1, step=2.5):
    """Annular sector from angle a0 to a1 (degrees, a0 < a1)."""
    n = max(2, int(math.ceil((a1 - a0) / step)))
    outer = [[cx + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
              cz + r1 * math.sin(math.radians(a0 + (a1 - a0) * i / n))] for i in range(n + 1)]
    if r0 <= 0:
        return outer + [[cx, cz]]
    inner = [[cx + r0 * math.cos(math.radians(a1 - (a1 - a0) * i / n)),
              cz + r0 * math.sin(math.radians(a1 - (a1 - a0) * i / n))] for i in range(n + 1)]
    return outer + inner


def stadium_poly(x0, z0, x1, z1, hw, n=18):
    """Rounded bar of half-width hw between two centres."""
    dx, dz = x1 - x0, z1 - z0
    L = math.hypot(dx, dz)
    ux, uz = dx / L, dz / L
    base = math.atan2(uz, ux)
    pts = []
    for i in range(n + 1):           # cap at end 1: from -90 to +90 around the direction
        a = base - math.pi / 2 + math.pi * i / n
        pts.append([x1 + hw * math.cos(a), z1 + hw * math.sin(a)])
    for i in range(n + 1):           # cap at end 0
        a = base + math.pi / 2 + math.pi * i / n
        pts.append([x0 + hw * math.cos(a), z0 + hw * math.sin(a)])
    return pts


def clip_zmin(poly, zmin):
    """Sutherland-Hodgman clip of a polygon against the half-plane z >= zmin."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina, inb = a[1] >= zmin, b[1] >= zmin
        if ina:
            out.append(list(a))
        if ina != inb:
            t = (zmin - a[1]) / (b[1] - a[1])
            out.append([a[0] + t * (b[0] - a[0]), zmin])
    return out


if __name__ == "__main__":
    import json
    r = build()
    print(json.dumps(r["summary"], indent=1))
    print(len(r["parts"]), "parts;", len(r["checks"]), "ball checks")
