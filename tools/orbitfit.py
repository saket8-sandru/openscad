#!/usr/bin/env python3
"""
orbitfit -- derive and check the cross-section of a twist "orbit ball" fidget.

The toy (sold as Orbit Ball / Track Pinball / Three Bead Orbit) has no published
drawing. Retail listings agree on the envelope (about 50 x 50 x 56 mm), on
three steel balls, and on two halves that twist. Nothing public gives the ball
diameter, the groove or the wall. So this does not pretend to measure them.
It builds the geometry from a few master values, derives everything else from
them, and checks that the result actually works:

  * the ball is captured (groove mouth narrower than the ball), but only by an
    interference a thumb can push past;
  * every revolve profile is valid (no profile crosses its axis);
  * grooves never get too close to each other, in either twist position;
  * the joint, the land and the pole pocket stay clear of the grooves;
  * the mass is computed, to compare against the ~50 g that listings quote.

Track construction. The track is four semicircles on the ball-centre sphere
(radius Rc). Each lies in a vertical plane set Rc/sqrt(2) off the twist axis,
and each passes through two equator points 90 degrees apart, crossing the
equator vertically. The top half carries two of them and the bottom half
(the same part flipped) the other two. Twisted 0 or 180 degrees they join
into one S-shaped, tennis-seam loop. Twisted 90 or 270 degrees they become
two separate circular loops.

Each semicircle is a torus segment whose axis passes through the sphere
centre, so in CAD it is a plain Revolve (cut) about a 45-degree axis. No
sweep or equation curve is needed.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, replace

import numpy as np

STEEL = 7.85e-3     # g/mm3
ABS = 1.05e-3
PLA = 1.24e-3


@dataclass(frozen=True)
class Params:
    sphere_dia: float = 50.0      # over the shell; listings: 49.8-50.0
    overall_h: float = 56.4       # pole tip to pole tip; listings: 55.9-56.4
    ball_dia: float = 12.0        # not published anywhere -- see docs
    ball_count: int = 3
    groove_clr: float = 0.30      # radial, ball to groove wall
    ball_sink: float = 3.5        # ball centre below the sphere surface
    gap: float = 0.30             # visible seam between halves (0.15 relief per face)
    land_r: float = 11.0          # thrust land radius; faces touch only inside it
    bore_dia: float = 4.5         # M4 axle, 0.25 mm radial clearance
    pocket_af: float = 7.2        # hex pocket at each pole: M4 nylock 7.0 AF / SHCS head 7.0
    pocket_depth: float = 8.0     # M4x40: head 4 + cap 4 one end, nut 5 + 1 + cap 2 the other
    wall: float = 2.0             # injection-moulded wall, for the mass comparison only


@dataclass(frozen=True)
class Derived:
    Ro: float          # sphere radius
    rg: float          # groove radius
    Rc: float          # ball-centre sphere radius
    T: float           # arc radius == arc-plane offset from axis == apex height
    mouth_w: float     # groove mouth width at the sphere surface
    interf: float      # per-side snap interference at the mouth
    proud_rest: float  # ball above surface when resting on the groove floor
    proud_max: float   # ball above surface when pulled out against the lips
    sunk_frac: float   # fraction of the diameter below the surface, centred ball
    floor_r: float     # groove floor radius (from sphere centre)
    depth: float       # groove depth below surface, measured radially
    nub_h: float       # pole nub height above the sphere, each end
    loop_len: float    # one-loop track length (ball-centre path)


def derive(p: Params) -> Derived:
    Ro = p.sphere_dia / 2
    rg = p.ball_dia / 2 + p.groove_clr
    Rc = Ro - p.ball_sink
    # groove circle (centre Rc, radius rg) meets the sphere circle (radius Ro)
    # in the groove's cross-section plane, which always contains the sphere
    # centre because the path lies on a sphere.
    x = (Rc**2 + Ro**2 - rg**2) / (2 * Rc)
    half = math.sqrt(max(Ro**2 - x**2, 0.0))
    r = p.ball_dia / 2
    # ball pulled outward until it touches the two lip edges (x, +-half)
    out = x - math.sqrt(max(r**2 - half**2, 0.0)) if half < r else float("nan")
    return Derived(
        Ro=Ro, rg=rg, Rc=Rc, T=Rc / math.sqrt(2),
        mouth_w=2 * half, interf=r - half,
        proud_rest=(Rc - p.groove_clr) + r - Ro,
        proud_max=out + r - Ro,
        sunk_frac=(Ro - (Rc - r)) / p.ball_dia,
        floor_r=Rc - rg, depth=Ro - (Rc - rg),
        nub_h=(p.overall_h - p.sphere_dia) / 2,
        loop_len=4 * math.pi * Rc / math.sqrt(2),
    )


# --- track path -----------------------------------------------------------

def arc_axes(twist_deg: float):
    """The four arcs as (axis unit vector, sign of z). Top arcs turn with the twist."""
    out = []
    for k, (ax, sz) in enumerate([((1, 1), +1), ((-1, -1), +1), ((1, -1), -1), ((-1, 1), -1)]):
        a = np.array([ax[0], ax[1], 0.0]) / math.sqrt(2)
        if sz > 0 and twist_deg:
            t = math.radians(twist_deg)
            c, s = math.cos(t), math.sin(t)
            a = np.array([c * a[0] - s * a[1], s * a[0] + c * a[1], 0.0])
        out.append((a, sz))
    return out


def arc_points(a, sz, Rc, n=721):
    """Semicircle of radius Rc/sqrt2 about axis a, through the top (or bottom) apex."""
    T = Rc / math.sqrt(2)
    C = T * a
    z = np.array([0.0, 0.0, 1.0])
    b = np.cross(z, a)                     # horizontal, in the arc plane
    ph = np.linspace(-math.pi / 2, math.pi / 2, n)
    return C + T * (np.outer(np.sin(ph), b) + sz * np.outer(np.cos(ph), z))


def min_pass_distance(Rc: float, rg: float, twist_deg: float) -> float:
    """
    Smallest centre-line distance between two arcs that do not meet. Arcs
    that share an end continue through it as one smooth line (both cross the
    equator vertically), so their only close approach is that junction. That
    is not a wall, and they are skipped.
    """
    arcs = [arc_points(a, sz, Rc) for a, sz in arc_axes(twist_deg)]
    best = float("inf")
    for i in range(4):
        for j in range(i + 1, 4):
            A, B = arcs[i], arcs[j]
            if any(np.linalg.norm(e - f) < 1e-6 for e in (A[0], A[-1]) for f in (B[0], B[-1])):
                continue
            d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
            best = min(best, float(d.min()))
    return best


def loops(twist_deg: float, Rc: float) -> int:
    """Count closed loops by chaining arc end points."""
    arcs = [arc_points(a, sz, Rc, n=3) for a, sz in arc_axes(twist_deg)]
    ends = [(A[0], A[-1]) for A in arcs]
    parent = list(range(4))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in range(4):
        for j in range(i + 1, 4):
            if any(np.linalg.norm(e - f) < 1e-6 for e in ends[i] for f in ends[j]):
                parent[find(i)] = find(j)
    return len({find(i) for i in range(4)})


# --- volume / mass ----------------------------------------------------------

def half_volume(p: Params, d: Derived, step=0.25, shell=None):
    """
    Volume of one half (z >= 0) in mm3, by voxels. With shell=w, counts only
    material within w of a surface: an injection-moulded part cored out to
    wall w, ribs ignored.
    """
    g = np.arange(-d.Ro, d.Ro + step, step) + step / 2
    zg = np.arange(0, d.Ro + step, step) + step / 2
    X, Y, Z = np.meshgrid(g, g, zg, indexing="ij")
    rxy = np.hypot(X, Y)
    solid = (X**2 + Y**2 + Z**2 <= d.Ro**2)
    solid &= (Z >= p.gap / 2) | (rxy <= p.land_r)
    solid &= rxy >= p.bore_dia / 2
    # hex pocket at the pole, approximated by its inscribed + circumscribed mean
    rp = p.pocket_af / 2 * (1 + 2 / math.sqrt(3)) / 2
    solid &= ~((rxy <= rp) & (Z >= d.Ro - p.pocket_depth))
    for a, sz in arc_axes(0):
        if sz < 0:
            continue
        C = d.T * a
        V = np.stack([X - C[0], Y - C[1], Z - C[2]], axis=-1)
        h = V @ a
        w = np.linalg.norm(V - h[..., None] * a, axis=-1)
        solid &= np.hypot(h, w - d.T) > d.rg
    if shell is None:
        return float(solid.sum()) * step**3
    from scipy.ndimage import distance_transform_edt
    pad = np.pad(solid, 1)
    dist = distance_transform_edt(pad, sampling=step)[1:-1, 1:-1, 1:-1]
    return float((solid & (dist <= shell)).sum()) * step**3


def ball_mass(dia: float) -> float:
    return STEEL * math.pi / 6 * dia**3


# --- reporting --------------------------------------------------------------

def checks(p: Params, d: Derived):
    """(name, value, limit, ok) rows. Limits are design rules, stated in the docs."""
    pass0 = min_pass_distance(d.Rc, d.rg, 0) - 2 * d.rg
    pass90 = min_pass_distance(d.Rc, d.rg, 90) - 2 * d.rg
    near_axis = d.T - d.rg                      # closest groove wall to the twist axis
    rim_land = (math.pi / 2) * d.Ro - d.mouth_w  # white rim between crossings, at the equator
    return [
        ("ball captured: mouth < ball", f"{d.mouth_w:.2f} < {p.ball_dia:.2f}", "", d.mouth_w < p.ball_dia),
        ("snap interference per side", f"{d.interf:.2f} mm", "0.25-0.60", 0.25 <= d.interf <= 0.60),
        ("ball proud of shell (max)", f"{d.proud_max:.2f} mm", "> 0", d.proud_max > 0),
        ("track revolve: T > groove r", f"{d.T:.2f} > {d.rg:.2f}", "", d.T > d.rg + 1),
        ("wall between separate arcs, 1 loop", f"{pass0:.2f} mm", ">= 2.0", pass0 >= 2.0),
        ("wall between separate arcs, 2 loops", f"{pass90:.2f} mm", ">= 2.0", pass90 >= 2.0),
        ("land clear of groove floor", f"{p.land_r:.2f} < {d.floor_r:.2f}", "1 mm margin", p.land_r <= d.floor_r - 1),
        ("pole pocket clear of grooves", f"{near_axis:.2f} > {p.pocket_af / math.sqrt(3):.2f}", "", near_axis > p.pocket_af / math.sqrt(3) + 2),
        ("rim land between crossings", f"{rim_land:.1f} mm", ">= 10", rim_land >= 10),
        ("loops at twist 0 / 90 deg", f"{loops(0, d.Rc)} / {loops(90, d.Rc)}", "1 / 2", loops(0, d.Rc) == 1 and loops(90, d.Rc) == 2),
    ]


def report(p: Params, mass: bool):
    d = derive(p)
    print(f"=== orbit ball: ball {p.ball_dia:g} mm, sink {p.ball_sink:g} mm, groove clr {p.groove_clr:g} mm ===")
    rows = [
        ("Sphere radius Ro", d.Ro), ("Groove radius rg", d.rg), ("Ball-centre radius Rc", d.Rc),
        ("Arc radius = plane offset = apex height T", d.T), ("Groove floor radius", d.floor_r),
        ("Groove depth below surface", d.depth), ("Mouth width", d.mouth_w),
        ("Snap interference / side", d.interf), ("Ball proud, resting on floor", d.proud_rest),
        ("Ball proud, against the lips", d.proud_max), ("Fraction of ball below surface", d.sunk_frac),
        ("Envelope across two opposite balls", p.sphere_dia + 2 * d.proud_max),
        ("Pole nub height (each), if nubs explain 56.4", d.nub_h), ("One-loop track length", d.loop_len),
        ("Twist misalignment for 0.25 mm step (deg)", math.degrees(0.25 / d.Rc)),
    ]
    for k, v in rows:
        print(f"  {k:<44} {v:8.3f}")
    print("  checks:")
    ok_all = True
    for name, val, lim, ok in checks(p, d):
        ok_all &= ok
        print(f"    {'PASS' if ok else 'FAIL'}  {name:<32} {val:<18} {lim}")
    if mass:
        solid = half_volume(p, d)
        moulded = half_volume(p, d, shell=p.wall)
        balls = p.ball_count * ball_mass(p.ball_dia)
        print("  mass:")
        print(f"    one half, solid             {solid / 1000:6.2f} cm3")
        print(f"    toy as moulded ABS, {p.wall:g} mm wall: {2 * moulded * ABS:5.1f} g body + {balls:4.1f} g balls"
              f" = {2 * moulded * ABS + balls:5.1f} g")
        print(f"    toy printed solid PLA       {2 * solid * PLA:5.1f} g body + {balls:4.1f} g balls"
              f" = {2 * solid * PLA + balls:5.1f} g")
    return ok_all


def sweep_balls(base: Params, interf: float):
    """For each candidate ball, pick the sink that gives the same snap interference."""
    print(f"\n=== candidate balls at {interf:.2f} mm/side snap interference ===")
    print("  ball   sink    Rc     T   mouth  proud  depth  wall1  wall2   ABS toy (g)  checks")
    for dia in (6.0, 8.0, 10.0, 11.0, 12.0, 12.7):
        lo, hi = 0.0, dia / 2
        for _ in range(60):                       # interference rises with sink
            mid = (lo + hi) / 2
            if derive(replace(base, ball_dia=dia, ball_sink=mid)).interf < interf:
                lo = mid
            else:
                hi = mid
        p = replace(base, ball_dia=dia, ball_sink=round((lo + hi) / 2, 2))
        d = derive(p)
        w1 = min_pass_distance(d.Rc, d.rg, 0) - 2 * d.rg
        w2 = min_pass_distance(d.Rc, d.rg, 90) - 2 * d.rg
        body = 2 * half_volume(p, d, step=0.4, shell=p.wall) * ABS
        ok = all(c[3] for c in checks(p, d))
        print(f"  {dia:5.1f}  {p.ball_sink:4.2f}  {d.Rc:5.2f}  {d.T:5.2f}  {d.mouth_w:5.2f}"
              f"  {d.proud_max:4.2f}  {d.depth:5.2f}  {w1:5.1f}  {w2:5.1f}"
              f"   {body:4.1f}+{p.ball_count * ball_mass(dia):4.1f}={body + p.ball_count * ball_mass(dia):4.1f}"
              f"   {'PASS' if ok else 'FAIL'}")


def plot(p: Params, out_prefix: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = derive(p)

    # 1: body revolve profile (XZ half-section) with the track circles drawn in
    #    the 45-degree plane, rotated into view.
    fig, ax = plt.subplots(figsize=(7, 8))
    t = np.linspace(0, math.pi / 2, 200)
    rp = p.bore_dia / 2
    zt = math.sqrt(d.Ro**2 - rp**2)
    # outer arc from rim to bore
    a0 = math.asin(p.gap / 2 / d.Ro)
    a1 = math.acos(rp / d.Ro)
    aa = np.linspace(a0, a1, 200)
    prof = np.vstack([[rp, 0], [p.land_r, 0], [p.land_r, p.gap / 2],
                      np.c_[d.Ro * np.cos(aa), d.Ro * np.sin(aa)], [rp, zt], [rp, 0]])
    ax.fill(prof[:, 0], prof[:, 1], color="#dfe6ee", ec="#335", lw=1.2, label="top half revolve profile")
    ax.fill(prof[:, 0], -prof[:, 1], color="#eef0f3", ec="#99a", lw=0.8, ls="--", label="bottom half (same part, flipped)")
    # pole pocket and nub
    ax.add_patch(plt.Rectangle((0, d.Ro - p.pocket_depth), p.pocket_af / 2, p.pocket_depth, fc="white", ec="#335", lw=0.8))
    ax.plot([0, 0], [-d.Ro - d.nub_h - 2, d.Ro + d.nub_h + 2], "k-.", lw=0.8)
    # spheres used for construction
    ax.plot(d.Rc * np.cos(t), d.Rc * np.sin(t), ":", color="#c60", lw=0.8, label=f"ball-centre sphere R{d.Rc:.2f}")
    ax.plot(d.floor_r * np.cos(t), d.floor_r * np.sin(t), ":", color="#888", lw=0.8, label=f"groove floor R{d.floor_r:.2f}")
    # groove section where the track crosses this view plane: apex of an arc,
    # rotated into the XZ plane (true size, since the section contains the centre)
    cx, cz = d.T, d.T
    th = np.linspace(0, 2 * math.pi, 200)
    ax.plot(cx + d.rg * np.cos(th), cz + d.rg * np.sin(th), color="#06c", lw=1.2, label=f"track circle R{d.rg:.2f} @ ({d.T:.2f}, {d.T:.2f})")
    ax.add_patch(plt.Circle((cx + p.groove_clr / math.sqrt(2), cz + p.groove_clr / math.sqrt(2)), p.ball_dia / 2, fc="#bbb", ec="#555"))
    ax.plot([0, d.Ro * 1.1 / math.sqrt(2)], [0, d.Ro * 1.1 / math.sqrt(2)], color="#06c", lw=0.6, ls="--")
    ax.set_aspect("equal")
    ax.set_xlim(-3, 31)
    ax.set_ylim(-d.Ro - 5, d.Ro + 5)
    ax.set_title("Body revolve profile (XZ, axis = Z) with the track circle\n"
                 "rotated in from the 45-degree track plane", fontsize=10)
    ax.legend(fontsize=7, loc="lower left")
    ax.grid(alpha=0.3)
    fig.savefig(f"{out_prefix}-section.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # 2: the track loop in 3D, at twist 0 and 90
    fig = plt.figure(figsize=(11, 5))
    for k, tw in enumerate((0, 90)):
        a3 = fig.add_subplot(1, 2, k + 1, projection="3d")
        u, v = np.mgrid[0:2 * np.pi:40j, 0:np.pi:20j]
        a3.plot_wireframe(d.Ro * np.cos(u) * np.sin(v), d.Ro * np.sin(u) * np.sin(v), d.Ro * np.cos(v),
                          color="#ccc", lw=0.3)
        for (a, sz), col in zip(arc_axes(tw), ("#06c", "#06c", "#c33", "#c33")):
            P = arc_points(a, sz, d.Rc) * d.Ro / d.Rc
            a3.plot(P[:, 0], P[:, 1], P[:, 2], color=col, lw=2.5)
        a3.set_box_aspect((1, 1, 1))
        a3.view_init(elev=8, azim=0)
        a3.set_axis_off()
        a3.set_title(f"twist {tw} deg: {loops(tw, d.Rc)} loop(s)  (blue = top half, red = bottom)", fontsize=9)
    fig.savefig(f"{out_prefix}-track.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ball", type=float, default=Params.ball_dia)
    ap.add_argument("--sink", type=float, default=Params.ball_sink)
    ap.add_argument("--clr", type=float, default=Params.groove_clr)
    ap.add_argument("--mass", action="store_true", help="voxel mass estimate (a few seconds)")
    ap.add_argument("--sweep", action="store_true", help="compare candidate ball sizes")
    ap.add_argument("--plot", metavar="PREFIX", help="write PREFIX-section.png and PREFIX-track.png")
    args = ap.parse_args()
    p = Params(ball_dia=args.ball, ball_sink=args.sink, groove_clr=args.clr)
    ok = report(p, args.mass)
    if args.sweep:
        sweep_balls(p, derive(p).interf)
    if args.plot:
        plot(p, args.plot)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
