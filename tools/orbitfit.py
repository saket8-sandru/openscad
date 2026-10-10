#!/usr/bin/env python3
"""
orbitfit -- derive and check the geometry of a twist "orbit ball" fidget.

The toy (sold as Orbit Ball / Track Pinball / Three Bead Orbit) has no drawing
that a search could reach. Listings agree only on the envelope (about
50 x 50 x 56 mm), three metal balls, ABS, and two halves that twist to
"switch the track". So this does not pretend to measure the ball, groove,
wall or track. It builds them from a few master values, derives everything
else, and checks that the result works as a printed part.

The track is 2N semicircles on the ball-centre sphere (radius Rc). The
crossings sit on the equator, 180/N degrees apart. Each semicircle joins two
neighbouring crossings, lies in a vertical plane Rc*cos(90/N) off the twist
axis, has radius Rc*sin(90/N), and crosses the equator vertically. The top
half carries N of them and the bottom half (the same part flipped 180 degrees
about X) carries the other N. Twist 0 gives one closed loop. Twist 180/N
gives N separate circles.

    N = 2: a tennis-seam loop that reads as an S / yin-yang, splitting into 2
    N = 3: a wavy equator loop, splitting into 3 (one per ball)

Each semicircle is a torus segment whose axis passes through the sphere
centre, so in CAD it is an ordinary Revolve (cut).

Groove retention is checked with the lip rounded by a fillet. A sharp lip
cannot be printed, and it is the fillet that sets the real interference.
The balls go in through the open groove ends at the parting face before the
halves are joined, so no snap force is ever needed.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, replace

import numpy as np

STEEL = 7.85e-3     # g/mm3
ABS = 1.05e-3
PLA = 1.24e-3

BOLTS = (30, 35, 40, 45, 50)        # ISO 4762 M4 stock lengths
WASHER_T, NUT_H = 0.8, 5.0          # DIN 125 M4 washer; DIN 985 M4 nylock
SHCS_K = 4.0                        # ISO 4762 M4 head height
MU_DRY = 0.3


@dataclass(frozen=True)
class Params:
    sphere_dia: float = 50.0      # listing width (49.8-52); assumes a true sphere
    ball_dia: float = 12.0        # NOT sourced -- see docs
    ball_count: int = 3
    lobes: int = 2                # N: 2 = S / tennis seam, 3 = three-loop wave
    groove_clr: float = 0.30      # radial, ball to groove wall
    ball_sink: float = 3.9        # ball centre below the shell surface
    lip_fillet: float = 0.3       # modelled on the groove lip; sets the real snap
    sleeve_od: float = 6.0        # brass/alu tube 6 x 4 is the axle
    bore_dia: float = 6.2         # modelled; drill/ream to 6.05-6.1 after printing
    pocket_dia: float = 9.6       # round, both poles: M4 washer (9.0) / head (7.0) / nut (7.0 AF, 8.1 AC)
    pocket_depth: float = 9.0
    magnet_hole: float = 4.2      # 4 x 2 mm discs
    magnet_depth: float = 2.4     # 2 mm magnet + 0.3 recess + 0.1 glue
    magnet_r: float = 0.0         # 0 = place automatically
    lead_in: float = 1.0          # 45 deg chamfer on groove ends at the parting face
    rim_chamfer: float = 0.5      # each half; the visible seam is the 1 mm V


@dataclass(frozen=True)
class Derived:
    Ro: float          # sphere radius
    r: float           # ball radius
    rg: float          # groove radius
    Rc: float          # ball-centre sphere radius
    off: float         # arc-plane offset from the twist axis = track-sketch "u"
    arc_r: float       # arc radius = apex height above the parting plane = sketch "v"
    mouth_w: float     # sharp-edged mouth width
    interf: float      # sharp-edged interference per side
    interf_eff: float  # with the lip fillet
    lip_angle: float   # material wedge angle at the lip, deg
    proud_rest: float  # ball above shell, resting on the groove floor
    proud_max: float   # ball above shell, pulled against the (filleted) lips
    floor_r: float
    depth: float
    loop_len: float
    step_deg: float    # twist detent step, deg


def _circle_x(d, ra, rb):
    """Intersection of circles (0,0,ra) and (d,0,rb): its x and its +y."""
    x = (d * d + ra * ra - rb * rb) / (2 * d)
    return x, math.sqrt(max(ra * ra - x * x, 0.0))


def derive(p: Params) -> Derived:
    Ro, r = p.sphere_dia / 2, p.ball_dia / 2
    rg = r + p.groove_clr
    Rc = Ro - p.ball_sink
    half = math.pi / (2 * p.lobes)
    # Every groove cross-section contains the sphere centre (the path lies on a
    # sphere), so the lip is the meeting of two circles in that plane.
    x, y = _circle_x(Rc, Ro, rg)
    n1 = np.array([x, y]) / Ro
    n2 = (np.array([x, y]) - [Rc, 0]) / rg
    lip_angle = math.degrees(math.acos(float(n1 @ n2)))       # normals: out of sphere, out of groove
    # Lip rounded by a fillet f: its centre is f inside the sphere and f
    # outside the groove. The ball must pass between the two fillet circles.
    f = p.lip_fillet
    cx, cy = _circle_x(Rc, Ro - f, rg + f)
    gap_half = cy - f
    out = cx - math.sqrt((r + f) ** 2 - cy ** 2) if gap_half < r else float("nan")
    return Derived(
        Ro=Ro, r=r, rg=rg, Rc=Rc,
        off=Rc * math.cos(half), arc_r=Rc * math.sin(half),
        mouth_w=2 * y, interf=r - y, interf_eff=r - gap_half, lip_angle=lip_angle,
        proud_rest=(Rc - p.groove_clr) + r - Ro, proud_max=out + r - Ro,
        floor_r=Rc - rg, depth=Ro - (Rc - rg),
        loop_len=2 * p.lobes * math.pi * Rc * math.sin(half),
        step_deg=180 / p.lobes,
    )


# --- track ------------------------------------------------------------------

def arcs(p: Params, d: Derived, twist_deg=0.0, n=721):
    """[(points, top?)]: the 2N semicircles; the top half's N turn with the twist."""
    N = p.lobes
    out = []
    for k in range(2 * N):
        top = k % 2 == 0
        az = math.radians((k + 0.5) * 180 / N + (twist_deg if top else 0))
        a = np.array([math.cos(az), math.sin(az), 0.0])
        b = np.array([-a[1], a[0], 0.0])
        sz = 1 if top else -1
        ph = np.linspace(-math.pi / 2, math.pi / 2, n)[:, None]
        pts = d.off * a + d.arc_r * (np.sin(ph) * b + sz * np.cos(ph) * np.array([0, 0, 1.0]))
        out.append((pts, top))
    return out


def _meets(A, B):
    return any(np.linalg.norm(e - f) < 1e-6 for e in (A[0], A[-1]) for f in (B[0], B[-1]))


def loops(p, d, twist_deg):
    A = [a for a, _ in arcs(p, d, twist_deg, n=3)]
    parent = list(range(len(A)))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in range(len(A)):
        for j in range(i + 1, len(A)):
            if _meets(A[i], A[j]):
                parent[find(i)] = find(j)
    return len({find(i) for i in range(len(A))})


def arc_wall(p, d, twist_deg):
    """Smallest wall between two arcs that do not meet (meeting arcs run on smoothly)."""
    A = [a for a, _ in arcs(p, d, twist_deg, n=361)]
    best = float("inf")
    for i in range(len(A)):
        for j in range(i + 1, len(A)):
            if not _meets(A[i], A[j]):
                best = min(best, float(np.linalg.norm(A[i][:, None] - A[j][None], axis=2).min()))
    return best - 2 * d.rg


def overhang(p, d, limit=45.0):
    """
    Printed parting-face down, the groove ceiling on the pole side of each top
    arc faces downward. For every section along the arc, measure how much of the
    groove wall (inside the shell) is flatter than `limit` from horizontal.
    Returns (worst width in mm, fraction of track length affected).
    """
    worst, hit = 0.0, 0
    th = np.linspace(-math.pi, math.pi, 1441)
    pts = [a for a, top in arcs(p, d, 0, n=721) if top][0]
    tang = np.gradient(pts, axis=0)
    for P, t in zip(pts, tang):
        u = P / np.linalg.norm(P)
        t = t / np.linalg.norm(t)
        w = np.cross(u, t)
        Q = d.Rc * u + d.rg * (np.outer(np.cos(th), u) + np.outer(np.sin(th), w))
        wall = np.linalg.norm(Q, axis=1) <= d.Ro
        up = (np.outer(np.cos(th), u) + np.outer(np.sin(th), w)) @ np.array([0, 0, 1.0])
        bad = wall & (up > math.cos(math.radians(limit)))
        width = bad.sum() * (th[1] - th[0]) * d.rg
        worst = max(worst, width)
        hit += width > 0
    return worst, hit / len(pts)


def magnet_angles(p):
    """On every arc axis: 180/N apart, so they meet at every detent and survive the X-flip."""
    return [(k + 0.5) * 180 / p.lobes for k in range(2 * p.lobes)]


def feature_walls(p, d, mr):
    """3D wall from the top-half grooves to the pole pocket, sleeve bore and magnet holes."""
    P = np.vstack([a for a, top in arcs(p, d, 0, n=2001) if top])
    rxy = np.hypot(P[:, 0], P[:, 1])
    z = P[:, 2]
    zf = d.Ro - p.pocket_depth
    pocket = np.hypot(np.maximum(rxy - p.pocket_dia / 2, 0), np.maximum(zf - z, 0)).min() - d.rg
    bore = (rxy - p.bore_dia / 2).min() - d.rg
    mag = float("inf")
    for ang in magnet_angles(p):
        c = mr * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        rho = np.hypot(P[:, 0] - c[0], P[:, 1] - c[1])
        mag = min(mag, float(np.hypot(np.maximum(rho - p.magnet_hole / 2, 0),
                                      np.maximum(z - p.magnet_depth, 0)).min() - d.rg))
    return float(pocket), float(bore), mag


def place_magnets(p, d):
    """Largest radius, in 0.5 mm steps, with >= 2 mm to every groove and >= 2 mm inside the rim chamfer."""
    if p.magnet_r:
        return p.magnet_r
    best, r = 0.0, math.ceil((p.bore_dia / 2 + p.magnet_hole / 2 + 2) * 2) / 2
    while r + p.magnet_hole / 2 <= d.Ro - p.rim_chamfer - 2:
        if feature_walls(p, d, r)[2] >= 2.0:
            best = r
        r += 0.5
    return best


def bolt_stack(p, d):
    """M4 bolt through a 6x4 sleeve. The sleeve is 0.1 longer than the halves, so the
    bolt clamps the sleeve and the halves keep 0.1 mm end play (the magnets hold them)."""
    sleeve = 2 * (d.Ro - p.pocket_depth) + 0.1
    need = sleeve + 2 * WASHER_T + NUT_H + 1.0
    L = next(b for b in BOLTS if b >= need)
    tip = L - (sleeve + 2 * WASHER_T + NUT_H)
    rim = math.sqrt(d.Ro ** 2 - (p.pocket_dia / 2) ** 2)      # pocket rim sits below the pole
    # the nut-end cap carries a 4.6 mm recess for the bolt tip, so its room
    # is measured to the nut face
    return dict(sleeve=sleeve, bolt=L, tip=tip,
                head_cap=rim - (sleeve / 2 + WASHER_T + SHCS_K),
                nut_cap=rim - (sleeve / 2 + WASHER_T + NUT_H))


# --- volume / mass ------------------------------------------------------------

def half_volume(p, d, mr, step=0.25, shell=None):
    """One half in mm3, by voxels. shell=w counts only material within w of a surface."""
    g = np.arange(-d.Ro, d.Ro + step, step) + step / 2
    zg = np.arange(0, d.Ro + step, step) + step / 2
    X, Y, Z = np.meshgrid(g, g, zg, indexing="ij")
    rxy = np.hypot(X, Y)
    solid = (X**2 + Y**2 + Z**2 <= d.Ro**2) & (rxy >= p.bore_dia / 2)
    solid &= ~((rxy <= p.pocket_dia / 2) & (Z >= d.Ro - p.pocket_depth))
    for ang in magnet_angles(p):
        c = mr * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        solid &= ~((np.hypot(X - c[0], Y - c[1]) <= p.magnet_hole / 2) & (Z <= p.magnet_depth))
    for k in range(0, 2 * p.lobes, 2):
        az = math.radians((k + 0.5) * 180 / p.lobes)
        along = X * math.cos(az) + Y * math.sin(az)
        w = np.sqrt(np.maximum(X**2 + Y**2 + Z**2 - along**2, 0))
        solid &= np.hypot(along - d.off, w - d.arc_r) > d.rg
    if shell is None:
        return float(solid.sum()) * step**3
    from scipy.ndimage import distance_transform_edt
    dist = distance_transform_edt(np.pad(solid, 1), sampling=step)[1:-1, 1:-1, 1:-1]
    return float((solid & (dist <= shell)).sum()) * step**3


def ball_mass(dia):
    return STEEL * math.pi / 6 * dia**3


# --- report -------------------------------------------------------------------

def checks(p, d):
    mr = place_magnets(p, d)
    pocket, bore, mag = feature_walls(p, d, mr if mr else 1e3)
    if not mr:
        mag = -1.0
    w0, w1 = arc_wall(p, d, 0), arc_wall(p, d, d.step_deg)
    l0, l1 = loops(p, d, 0), loops(p, d, d.step_deg)
    rim = (math.pi / p.lobes) * d.Ro - d.mouth_w
    bs = bolt_stack(p, d)
    return mr, bs, [
        ("ball captured (sharp mouth < ball)", f"{d.mouth_w:.2f} < {p.ball_dia:.2f}", "", d.mouth_w < p.ball_dia),
        ("retention, lip filleted", f"{d.interf_eff:.2f} mm/side", "0.25-0.50", 0.25 <= d.interf_eff <= 0.50),
        ("ball enters at groove end", f"{d.rg:.2f} > {d.r:.2f}", "", d.rg > d.r),
        ("ball proud of shell", f"{d.proud_rest:.2f}-{d.proud_max:.2f} mm", "> 0", d.proud_rest > 0),
        ("track revolve valid (arc_r > rg+1)", f"{d.arc_r:.2f} > {d.rg + 1:.2f}", "", d.arc_r > d.rg + 1),
        ("wall between arcs, one loop", f"{w0:.2f} mm", ">= 2.0", w0 >= 2.0),
        (f"wall between arcs, {l1} loops", f"{w1:.2f} mm", ">= 2.0", w1 >= 2.0),
        ("wall groove-pole pocket", f"{pocket:.2f} mm", ">= 2.0", pocket >= 2.0),
        ("wall groove-sleeve bore", f"{bore:.2f} mm", ">= 2.0", bore >= 2.0),
        (f"wall groove-magnets (r {mr:g})", f"{mag:.2f} mm", ">= 2.0", mag >= 2.0),
        ("rim land between crossings", f"{rim:.1f} mm", ">= 8", rim >= 8),
        (f"loops at 0 / {d.step_deg:g} deg", f"{l0} / {l1}", f"1 / {p.lobes}", l0 == 1 and l1 == p.lobes),
        (f"M4x{bs['bolt']} past nylock", f"{bs['tip']:.2f} mm", "0.5-2.5", 0.5 <= bs["tip"] <= 2.5),
        ("cap room, head / nut end", f"{bs['head_cap']:.2f} / {bs['nut_cap']:.2f}", ">= 1.5", min(bs["head_cap"], bs["nut_cap"]) >= 1.5),
    ]


def report(p, mass):
    d = derive(p)
    mr, bs, rows = checks(p, d)
    print(f"=== orbit ball: N={p.lobes}, ball {p.ball_dia:g}, sink {p.ball_sink:g}, "
          f"clr {p.groove_clr:g}, lip fillet {p.lip_fillet:g} ===")
    for k, v in [
        ("Sphere radius", d.Ro), ("Groove radius", d.rg), ("Ball-centre sphere radius", d.Rc),
        ("Arc-plane offset from axis (sketch u)", d.off), ("Arc radius = apex height (sketch v)", d.arc_r),
        ("Groove floor radius", d.floor_r), ("Groove depth below shell", d.depth),
        ("Mouth width, sharp lip", d.mouth_w), ("Interference/side, sharp lip", d.interf),
        ("Interference/side, filleted lip", d.interf_eff), ("Lip wedge angle (deg)", d.lip_angle),
        ("Ball proud, resting on floor", d.proud_rest), ("Ball proud, against the lips", d.proud_max),
        ("Track length, one loop", d.loop_len), ("Twist detent step (deg)", d.step_deg),
        ("Magnet radius (auto)", mr), ("Sleeve length (6x4 tube)", bs["sleeve"]),
    ]:
        print(f"  {k:<42} {v:8.3f}")
    # A ball within r of the parting plane straddles both halves; within
    # r*sin(atan mu) the two groove edges wedge it if the halves are twisted.
    zc = np.abs(np.vstack([a for a, _ in arcs(p, d, 0, n=2001)])[:, 2])
    lock = d.r * math.sin(math.atan(MU_DRY))
    print(f"  ball straddles the seam over {100 * (zc < d.r).mean():.0f}% of the loop; "
          f"wedges (mu {MU_DRY}) within {lock:.2f} mm of it, {100 * (zc < lock).mean():.0f}% of the loop")
    ow, of = overhang(p, d)
    print(f"  printed face down: groove ceiling flatter than 45 deg, up to {ow:.1f} mm wide, "
          f"over {100 * of:.0f}% of each top arc")
    print(f"  passable step at a crossing {2 * p.groove_clr:.2f} mm = "
          f"{math.degrees(2 * p.groove_clr / d.Rc):.2f} deg of twist, before the {p.lead_in:g} mm lead-in")
    print("  checks:")
    ok = True
    for name, val, lim, good in rows:
        ok &= good
        print(f"    {'PASS' if good else 'FAIL'}  {name:<36} {val:<20} {lim}")
    if mass:
        solid = half_volume(p, d, mr)
        balls = p.ball_count * ball_mass(p.ball_dia)
        skin = half_volume(p, d, mr, shell=1.6)
        printed = 2 * (skin + 0.15 * (solid - skin)) * PLA
        print(f"  mass (one half solid {solid / 1000:.2f} cm3):")
        print(f"    {'printed PLA, 4 walls + 15% infill':<35}{printed:5.1f} g body + {balls:4.1f} g balls = {printed + balls:5.1f} g")
        for w in (1.5, 2.0, 2.5, 3.0, 4.0):
            body = 2 * half_volume(p, d, mr, step=0.4, shell=w) * ABS
            print(f"    {f'moulded ABS, {w:g} mm walls':<35}{body:5.1f} g body + {balls:4.1f} g balls = {body + balls:5.1f} g")
    return ok


def sweep_balls(base, target_eff):
    """Each candidate ball at the sink that gives the same filleted retention."""
    print(f"\n=== candidate balls at {target_eff:.2f} mm/side filleted retention (N={base.lobes}) ===")
    print("  ball   sink     Rc    off  arc_r      proud   ABS 2mm toy   wall for 50 g  checks")
    for dia in (6.0, 8.0, 10.0, 11.0, 12.0, 12.7):
        lo, hi = 0.5, dia / 2 + 1
        for _ in range(60):
            mid = (lo + hi) / 2
            if derive(replace(base, ball_dia=dia, ball_sink=mid)).interf_eff < target_eff:
                lo = mid
            else:
                hi = mid
        p = replace(base, ball_dia=dia, ball_sink=round((lo + hi) / 2, 2))
        d = derive(p)
        mr, _, rows = checks(p, d)
        balls = p.ball_count * ball_mass(dia)
        walls = [(w, 2 * half_volume(p, d, mr, step=0.5, shell=w) * ABS) for w in (1.5, 2, 2.5, 3, 3.5, 4, 5)]
        b2 = dict(walls)[2]
        w50 = next((f"{w:g} mm" for w, b in walls if b + balls >= 50), "> 5 mm")
        print(f"  {dia:5.1f}  {p.ball_sink:5.2f}  {d.Rc:5.2f}  {d.off:5.2f}  {d.arc_r:5.2f}  {d.proud_rest:4.2f}-{d.proud_max:4.2f}"
              f"  {b2:4.1f}+{balls:4.1f}={b2 + balls:4.1f}   {w50:>8}       {'PASS' if all(r[3] for r in rows) else 'FAIL'}")


def plot(p, prefix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = derive(p)
    mr, bs, _ = checks(p, d)

    fig, ax = plt.subplots(figsize=(7, 8))
    rb, rp = p.bore_dia / 2, p.pocket_dia / 2
    zp = d.Ro - p.pocket_depth
    aa = np.linspace(0, math.acos(rp / d.Ro), 200)
    prof = np.vstack([[rb, 0], np.c_[d.Ro * np.cos(aa), d.Ro * np.sin(aa)], [rp, zp], [rb, zp], [rb, 0]])
    ax.fill(prof[:, 0], prof[:, 1], color="#dfe6ee", ec="#335", lw=1.2, label="top half revolve profile")
    ax.fill(prof[:, 0], -prof[:, 1], color="#eef0f3", ec="#99a", lw=0.8, ls="--", label="bottom half = same part, flipped")
    ax.add_patch(plt.Rectangle((p.sleeve_od / 2 - 1, -bs["sleeve"] / 2), 1, bs["sleeve"], fc="#c9a24a", ec="#7a5", lw=0.6,
                               label=f"6x4 sleeve, {bs['sleeve']:.1f} long"))
    ax.plot([0, 0], [-d.Ro - 3, d.Ro + 3], "k-.", lw=0.8)
    t = np.linspace(0, math.pi / 2, 200)
    ax.plot(d.Rc * np.cos(t), d.Rc * np.sin(t), ":", color="#c60", lw=0.8, label=f"ball-centre sphere R{d.Rc:.2f}")
    ax.plot(d.floor_r * np.cos(t), d.floor_r * np.sin(t), ":", color="#888", lw=0.8, label=f"groove floor R{d.floor_r:.2f}")
    th = np.linspace(0, 2 * math.pi, 200)
    ax.plot(d.off + d.rg * np.cos(th), d.arc_r + d.rg * np.sin(th), color="#06c", lw=1.2,
            label=f"track circle R{d.rg:.2f} at u={d.off:.2f}, v={d.arc_r:.2f}\n(lies in the {90 / p.lobes:g}-deg track plane)")
    ax.add_patch(plt.Circle((d.off, d.arc_r), d.r, fc="#bbb", ec="#555"))
    ax.axhline(0, color="#06c", lw=0.6, ls="--")
    ax.set_aspect("equal")
    ax.set_xlim(-3, 31)
    ax.set_ylim(-d.Ro - 4, d.Ro + 4)
    ax.set_title(f"Body revolve profile (axis Z) + track section, N={p.lobes}", fontsize=10)
    ax.legend(fontsize=7, loc="lower left")
    ax.grid(alpha=0.3)
    fig.savefig(f"{prefix}-section.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # hidden-line views from an equator crossing (+X), at twist 0 and one step
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))
    for ax, tw in zip(axs, (0, d.step_deg)):
        ax.add_patch(plt.Circle((0, 0), d.Ro, fc="#f4f4f4", ec="#999"))
        ax.plot([-d.Ro, d.Ro], [0, 0], color="#bbb", lw=0.8)
        for pts, top in arcs(p, d, tw):
            P = pts * d.Ro / d.Rc
            vis = P[:, 0] >= 0
            for mask, ls, lw in ((vis, "-", 3.0), (~vis, ":", 0.8)):
                Q = np.where(mask[:, None], P, np.nan)
                ax.plot(Q[:, 1], Q[:, 2], ls, color="#06c" if top else "#c33", lw=lw)
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(f"twist {tw:g} deg: {loops(p, d, tw)} loop(s), seen from a crossing\n"
                     "blue = top half, red = bottom, dotted = far side", fontsize=9)
    fig.savefig(f"{prefix}-track.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ball", type=float, default=Params.ball_dia)
    ap.add_argument("--sink", type=float, default=Params.ball_sink)
    ap.add_argument("--clr", type=float, default=Params.groove_clr)
    ap.add_argument("--lobes", type=int, default=Params.lobes)
    ap.add_argument("--fillet", type=float, default=Params.lip_fillet)
    ap.add_argument("--mass", action="store_true", help="voxel mass estimates (tens of seconds)")
    ap.add_argument("--sweep", action="store_true", help="compare candidate ball sizes")
    ap.add_argument("--plot", metavar="PREFIX", help="write PREFIX-section.png and PREFIX-track.png")
    a = ap.parse_args()
    p = Params(ball_dia=a.ball, ball_sink=a.sink, groove_clr=a.clr, lobes=a.lobes, lip_fillet=a.fillet)
    ok = report(p, a.mass)
    if a.sweep:
        sweep_balls(p, derive(p).interf_eff)
    if a.plot:
        plot(p, a.plot)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
