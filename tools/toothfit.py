#!/usr/bin/env python3
"""
toothfit -- derive an arc construction for GT2 / HTD tooth grooves.

The community reference profiles circulate as fixed point lists of unclear
provenance and licence. Rather than copy one, this fits the arc construction
the standard actually describes -- a crown arc, a root fillet arc, and (for
HTD) a straight flank between them -- and reports the worst deviation from the
reference points, so the substitution is justified by measurement rather than
by assertion.

An arc construction is also better geometry: it resolves to any smoothness the
model asks for, instead of being frozen at whatever the point list captured.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

GT2 = np.array([[0.747183,0],[0.647876,0.037218],[0.598311,0.130528],[0.578556,0.238423],
[0.547158,0.343077],[0.504649,0.443762],[0.451556,0.53975],[0.358229,0.636924],
[0.2484,0.707276],[0.127259,0.750044],[0,0.76447],[-0.127259,0.750044],[-0.2484,0.707276],
[-0.358229,0.636924],[-0.451556,0.53975],[-0.504797,0.443762],[-0.547291,0.343077],
[-0.578605,0.238423],[-0.598311,0.130528],[-0.648009,0.037218],[-0.747183,0]])

HTD = np.array([[-1.89036,0],[-1.741168,0.02669],[-1.61387,0.100806],[-1.518984,0.21342],
[-1.467026,0.3556],[-1.427162,0.960967],[-1.398568,1.089602],[-1.359437,1.213531],
[-1.310296,1.332296],[-1.251672,1.445441],[-1.184092,1.552509],[-1.108081,1.653042],
[-1.024167,1.746585],[-0.932877,1.832681],[-0.834736,1.910872],[-0.730271,1.980701],
[-0.62001,2.041713],[-0.504478,2.09345],[-0.384202,2.135455],[-0.259708,2.167271],
[-0.131524,2.188443],[-0.000176,2.198511],[0.131296,2.188504],[0.259588,2.167387],
[0.384174,2.135616],[0.504527,2.093648],[0.620123,2.04194],[0.730433,1.980949],
[0.834934,1.911132],[0.933097,1.832945],[1.024398,1.746846],[1.108311,1.653291],
[1.184308,1.552736],[1.251865,1.445639],[1.310455,1.332457],[1.359552,1.213647],
[1.39863,1.089664],[1.427162,0.960967],[1.467026,0.3556],[1.518984,0.21342],
[1.61387,0.100806],[1.741168,0.02669],[1.89036,0]])


def fit_circle(pts):
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(pts))]
    c, *_ = np.linalg.lstsq(A, x**2 + y**2, rcond=None)
    cx, cy = c[0], c[1]
    return cx, cy, float(np.sqrt(c[2] + cx * cx + cy * cy))


def deviation(model_pts, ref):
    """Worst distance from each reference point to the model polyline."""
    seg_a, seg_b = model_pts[:-1], model_pts[1:]
    d = seg_b - seg_a
    L2 = (d ** 2).sum(axis=1)
    worst = 0.0
    for p in ref:
        t = np.clip(((p - seg_a) * d).sum(axis=1) / np.maximum(L2, 1e-12), 0, 1)
        proj = seg_a + t[:, None] * d
        worst = max(worst, float(np.hypot(*(p - proj).T).min()))
    return worst


def arc(cx, cy, r, a0, a1, n=200):
    a = np.linspace(a0, a1, n)
    return np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]


def build_gt2(crown_r, crown_y, root_r, root_x, root_y, n=200):
    """Root fillet sweeping up into a crown arc, mirrored about x=0."""
    # tangent point between the two circles: they touch where the line of
    # centres crosses, since the fillet is internally tangent to the crown.
    dx, dy = root_x - 0.0, root_y - crown_y
    d = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    # external tangency point along the centre line
    tx = crown_y * 0 + crown_r * np.cos(ang)
    ty = crown_y + crown_r * np.sin(ang)
    a_root_start = np.arctan2(0 - root_y, root_x * 0 + 1.0 * (0.747183 - root_x))
    a_root_end = np.arctan2(ty - root_y, tx - root_x)
    right = np.vstack([
        arc(root_x, root_y, root_r, a_root_start, a_root_end, n // 2),
        arc(0.0, crown_y, crown_r, ang, np.pi / 2, n // 2),
    ])
    left = right[::-1] * np.array([-1, 1])
    return np.vstack([right[::-1], left[1:]])


def main():
    print("=== GT2 2mm groove ===")
    crown = GT2[GT2[:, 1] > 0.42]
    root = GT2[GT2[:, 1] <= 0.42]
    cx, cy, cr = fit_circle(crown)
    print(f"  crown circle : centre ({cx:+.5f}, {cy:+.5f})  R {cr:.5f}")
    rr_pts = root[root[:, 0] > 0]
    rx, ry, rr = fit_circle(rr_pts)
    print(f"  root  circle : centre ({rx:+.5f}, {ry:+.5f})  R {rr:.5f}")

    def resid(p):
        crown_r, crown_y, root_r, root_x, root_y = p
        model = build_gt2(crown_r, crown_y, root_r, root_x, root_y)
        return [deviation(model, GT2)]

    x0 = [cr, cy, rr, rx, ry]
    sol = least_squares(resid, x0, diff_step=1e-4)
    crown_r, crown_y, root_r, root_x, root_y = sol.x
    dev = deviation(build_gt2(*sol.x), GT2)
    print(f"  FITTED: crown R {crown_r:.5f} @ y {crown_y:+.5f} | "
          f"root R {root_r:.5f} @ ({root_x:+.5f}, {root_y:+.5f})")
    print(f"  worst deviation from reference points: {dev*1000:.1f} micron")
    print(f"  (a 0.4mm nozzle lays a ~420 micron bead; printer XY repeatability is ~100 micron)")


if __name__ == "__main__":
    main()


# --- HTD: root fillet, straight flank, crown arc -------------------------
#
# The joints are read straight off the profile rather than solved for: the
# reference marks exactly where the straight flank starts and ends, and a
# construction reusing those points is simpler and exact at the joins. Only the
# two arc centres are fitted.

HTD_FLANK_LO = np.array([1.467026, 0.3556])     # root fillet -> straight
HTD_FLANK_HI = np.array([1.427162, 0.960967])   # straight -> crown arc
HTD_HALF_W = 1.89036


def arc_through(p0, p1, cx, cy, n):
    r = float(np.hypot(*(p0 - np.array([cx, cy]))))
    a0 = np.arctan2(p0[1] - cy, p0[0] - cx)
    a1 = np.arctan2(p1[1] - cy, p1[0] - cx)
    return arc(cx, cy, r, a0, a1, n)


def build_htd(crown_cy, root_cx, root_cy, n=120):
    crown_r = float(np.hypot(*(HTD_FLANK_HI - np.array([0.0, crown_cy]))))
    crown_top = np.array([0.0, crown_cy + crown_r])
    right = np.vstack([
        arc_through(np.array([HTD_HALF_W, 0.0]), HTD_FLANK_LO, root_cx, root_cy, n),
        np.linspace(HTD_FLANK_LO, HTD_FLANK_HI, n // 3),
        arc_through(HTD_FLANK_HI, crown_top, 0.0, crown_cy, n),
    ])
    left = right[::-1] * np.array([-1.0, 1.0])
    return np.vstack([right[::-1], left[1:]])


def fit_htd():
    print("\n=== HTD 5M groove ===")
    crown = HTD[HTD[:, 1] > 0.96]
    cx, cy, cr = fit_circle(crown)
    root = HTD[(HTD[:, 1] <= 0.36) & (HTD[:, 0] > 0)]
    rx, ry, rr = fit_circle(root)
    print(f"  crown circle : centre ({cx:+.5f}, {cy:+.5f})  R {cr:.5f}")
    print(f"  root  circle : centre ({rx:+.5f}, {ry:+.5f})  R {rr:.5f}")

    sol = least_squares(lambda p: [deviation(build_htd(*p), HTD)],
                        [cy, rx, ry], diff_step=1e-4)
    crown_cy, root_cx, root_cy = sol.x
    crown_r = float(np.hypot(*(HTD_FLANK_HI - np.array([0.0, crown_cy]))))
    root_r = float(np.hypot(*(np.array([HTD_HALF_W, 0.0]) - np.array([root_cx, root_cy]))))
    print(f"  FITTED: crown R {crown_r:.5f} @ y {crown_cy:+.5f} | "
          f"root R {root_r:.5f} @ ({root_cx:+.5f}, {root_cy:+.5f})")
    print(f"  depth {crown_cy + crown_r:.5f}  half-width {HTD_HALF_W:.5f}")
    print(f"  worst deviation: {deviation(build_htd(*sol.x), HTD)*1000:.1f} micron")


if __name__ == "__main__":
    main()
    fit_htd()
