#!/usr/bin/env python3
"""
fsmirror -- Python mirror of the LEOPARD VENT FeatureScript geometry.

FeatureScript only runs inside Onshape, so the geometry in
projects/leopard-vent/featurescript/leopard_vent.fs cannot be tested from
here. This file is a line-for-line mirror of its pure-maths half -- cell
generation, face-boundary handling, hole clipping, round rings and wheels
round round holes, corner rounding, the min-hole test -- written so each
function maps onto one FeatureScript function of the same name (snake_case
here, camelCase there). What it cannot mirror is the Onshape plumbing:
reading the face, the sketch, the extrude, the boolean.

    fsmirror.py check [--only classic|round]   run every test face, measure every hole
    fsmirror.py crosscheck                     run the .fs file's own maths against this
    fsmirror.py png  out.png ...               draw one face (see --help)
    fsmirror.py preview out.png                the round-holes picture in the docs
    fsmirror.py fallbacks                      where round holes get a straight cut instead

The check builds holes exactly as the feature would, then measures them with
shapely against the TRUE face outline -- real circles, not the sampled chords
the feature works from: thinnest web between holes, closest approach to the
outline and to every inner loop, ring width round round holes, spoke width,
smallest hole, that every hole lies inside the face, that no piece of the
plate is left loose, and that every sketched outline is exactly the rounded
shape it stands for.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------- constants

PITCH = {"QUAD": 1.0, "TRI": math.sqrt(4 / math.sqrt(3)), "HEX": math.sqrt(2 / math.sqrt(3))}
ACROSS = {"QUAD": 1.0, "TRI": 1 / math.sqrt(3), "HEX": 1.0}
JITTER = {"QUAD": 0.35, "TRI": 0.28, "HEX": 0.35}
MARGIN = 4
SAG = 0.005          # mm: chord-to-arc error allowed when sampling curved edges
SPLINE_STEP = 0.5    # mm between samples on edges that are neither line nor arc
TINY_EDGE = 0.01     # mm: shorter edges are merged before sketching
TINY_TURN = 1e-3     # sine of the smallest corner turn kept as a corner
MIN_RADIUS = 0.01    # mm: a corner radius below this is drawn sharp
TINY_AREA = 1e-6     # mm^2
EPS = 1e-9


def fs_round(x):
    # FeatureScript's round() is floor(x + 0.5); Python's rounds halves to even.
    return math.floor(x + 0.5)


# ---------------------------------------------------------------- hash

def wrap360(a):
    return a - 360 * math.floor(a / 360)


def sind(a):
    return math.sin(math.radians(a))


def hash01(n, s):
    a0 = sind(wrap360(n * 12.9898 + s * 78.233 + 41.7)) * 43758.5453
    a = a0 - math.floor(a0)
    c0 = sind(wrap360(a * 311.7 + n * 74.7 + s * 19.19)) * 24634.6345
    return c0 - math.floor(c0)


def jitter(i, j, a, s):
    n = (i * 977 + j) * 2
    r = a * math.sqrt(hash01(n, s))
    t = 360 * hash01(n + 1, s)
    return (r * math.cos(math.radians(t)), r * math.sin(math.radians(t)))


# ---------------------------------------------------------------- 2D helpers

def add(a, b): return (a[0] + b[0], a[1] + b[1])
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def mul(a, k): return (a[0] * k, a[1] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1]
def cross2(a, b): return a[0] * b[1] - a[1] * b[0]
def vlen(a): return math.hypot(a[0], a[1])


def unit(a):
    n = vlen(a)
    return (a[0] / n, a[1] / n)


def signed_area(poly):
    s = 0.0
    for k in range(len(poly)):
        a, b = poly[k], poly[(k + 1) % len(poly)]
        s += a[0] * b[1] - b[0] * a[1]
    return s / 2


def centroid(poly):
    sx = sy = 0.0
    for p in poly:
        sx += p[0]
        sy += p[1]
    return (sx / len(poly), sy / len(poly))


def ccw(poly):
    return poly if signed_area(poly) >= 0 else list(reversed(poly))


# Keep the part of a polygon where (x - m) . d < 0. Strict, so a corner lying
# exactly on the line is emitted once, as a crossing.
def clip_half(poly, m, d):
    n = len(poly)
    if n < 3:
        return []
    out = []
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        fa, fb = dot(sub(a, m), d), dot(sub(b, m), d)
        if fa < 0:
            out.append(a)
        if (fa < 0) != (fb < 0):
            out.append(add(a, mul(sub(b, a), fa / (fa - fb))))
    return out


# Keep the part of a polygon at least `dist` to the left of the directed line
# a -> b (the left being the inside, for a counter-clockwise boundary).
def clip_left_of(poly, a, b, dist):
    t = unit(sub(b, a))
    left = (-t[1], t[0])
    return clip_half(poly, add(a, mul(left, dist)), mul(left, -1))


# Shrink a convex polygon by dist: clip it by each of its own edges, moved in.
def inset_convex(poly, dist):
    p = ccw(poly)
    out = p
    for k in range(len(p)):
        out = clip_left_of(out, p[k], p[(k + 1) % len(p)], dist)
        if len(out) < 3:
            return []
    return out


# Drop corners that would make sketch entities too small to be safe: an edge
# under TINY_EDGE, or a corner that barely turns (its arc would be a sliver).
# On a convex polygon, dropping a corner replaces two edges by the chord
# inside them, so the hole can only shrink and a rib only thicken.
def tidy(poly):
    p = list(poly)
    changed = True
    while changed and len(p) >= 3:
        changed = False
        n = len(p)
        for k in range(n):
            a, b, c = p[(k + n - 1) % n], p[k], p[(k + 1) % n]
            e1, e2 = sub(b, a), sub(c, b)
            l1, l2 = vlen(e1), vlen(e2)
            if l1 < TINY_EDGE or l2 < TINY_EDGE or abs(cross2(e1, e2)) < TINY_TURN * l1 * l2:
                p = p[:k] + p[k + 1:]
                changed = True
                break
    return p if len(p) >= 3 and abs(signed_area(p)) > TINY_AREA else []


# ---------------------------------------------------------------- cropped cells

def lattice_frame(lo, hi, p, h):
    hx = 2 * math.ceil((math.ceil((hi[0] - lo[0]) / (2 * p)) + MARGIN) / 2)
    hy = 2 * math.ceil((math.ceil((hi[1] - lo[1]) / (2 * h)) + MARGIN) / 2)
    c = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
    return (c[0] - hx * p, c[1] - hy * h), 2 * hx, 2 * hy


def lattice(o, p, nx, ny, stagger, a, s):
    h = p * math.sqrt(3) / 2 if stagger else p
    V = []
    for i in range(nx + 1):
        col = []
        for j in range(ny + 1):
            d = jitter(i - nx / 2, j - ny / 2, a, s)
            col.append((o[0] + (i + ((j % 2) / 2 if stagger else 0)) * p + d[0],
                        o[1] + j * h + d[1]))
        V.append(col)
    return V


def touches(c, lo, hi):
    xs = [q[0] for q in c]
    ys = [q[1] for q in c]
    return max(xs) > lo[0] and min(xs) < hi[0] and max(ys) > lo[1] and min(ys) < hi[1]


def quad_cells(V, nx, ny, lo, hi):
    out = []
    for i in range(nx):
        for j in range(ny):
            c = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
            if touches(c, lo, hi):
                out.append(c)
    return out


def tri_cells(V, nx, ny, lo, hi):
    out = []
    for i in range(nx):
        for j in range(ny):
            if j % 2 == 0:
                cs = [[V[i][j], V[i + 1][j], V[i][j + 1]],
                      [V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]]
            else:
                cs = [[V[i][j], V[i + 1][j], V[i + 1][j + 1]],
                      [V[i][j], V[i + 1][j + 1], V[i][j + 1]]]
            out += [c for c in cs if touches(c, lo, hi)]
    return out


def clip_all(poly, s, nbrs):
    for q in nbrs:
        poly = clip_half(poly, mul(add(s, q), 0.5), sub(q, s))
        if len(poly) < 3:
            return []
    return poly


def voronoi_cells(S, nx, ny, p, a, lo, hi):
    rc = p / math.sqrt(3) + a + 1e-6
    out = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            s = S[i][j]
            if not (lo[0] - rc < s[0] < hi[0] + rc and lo[1] - rc < s[1] < hi[1] + rc):
                continue
            nbrs = []
            for di in range(-3, 4):
                for dj in range(-3, 4):
                    ii, jj = i + di, j + dj
                    if (di or dj) and 0 <= ii <= nx and 0 <= jj <= ny \
                            and vlen(sub(S[ii][jj], s)) < 2 * rc:
                        nbrs.append(S[ii][jj])
            box = [(s[0] - rc, s[1] - rc), (s[0] + rc, s[1] - rc),
                   (s[0] + rc, s[1] + rc), (s[0] - rc, s[1] + rc)]
            c = clip_all(box, s, nbrs)
            if len(c) >= 3:
                out.append(c)
    return out


def crop_cells(shape, lo, hi, cell, irregular, s):
    p = cell * PITCH[shape]
    st = shape != "QUAD"
    h = p * math.sqrt(3) / 2 if st else p
    a = min(1, max(0, irregular)) * JITTER[shape] * p
    o, nx, ny = lattice_frame(lo, hi, p, h)
    V = lattice(o, p, nx, ny, st, a, s)
    if shape == "TRI":
        return tri_cells(V, nx, ny, lo, hi)
    if shape == "HEX":
        return voronoi_cells(V, nx, ny, p, a, lo, hi)
    return quad_cells(V, nx, ny, lo, hi)


# ---------------------------------------------------------------- fitted cells

def quad_fit(lo, hi, cell, irregular, s):
    W = sub(hi, lo)
    nx = max(1, fs_round(W[0] / cell))
    ny = max(1, fs_round(W[1] / cell))
    px, py = W[0] / nx, W[1] / ny
    a = min(1, max(0, irregular)) * JITTER["QUAD"] * min(px, py)
    V = []
    for i in range(nx + 1):
        col = []
        for j in range(ny + 1):
            d = jitter(i, j, a, s)
            col.append((lo[0] + i * px + (0 if i in (0, nx) else d[0]),
                        lo[1] + j * py + (0 if j in (0, ny) else d[1])))
        V.append(col)
    return [[V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
            for i in range(nx) for j in range(ny)]


def tri_row_x(j, nx):
    if j % 2 == 0:
        return [float(k) for k in range(nx + 1)]
    return [0.0] + [k + 0.5 for k in range(nx)] + [float(nx)]


def zipper(B, T, bx, tx):
    out = []
    ib = it = 0
    while not (ib == len(B) - 1 and it == len(T) - 1):
        up = ib == len(B) - 1 or (it < len(T) - 1 and tx[it] + tx[it + 1] < bx[ib] + bx[ib + 1])
        if up:
            out.append([B[ib], T[it + 1], T[it]])
            it += 1
        else:
            out.append([B[ib], B[ib + 1], T[it]])
            ib += 1
    return out


def tri_fit(lo, hi, cell, irregular, s):
    p0 = cell * PITCH["TRI"]
    W = sub(hi, lo)
    nx = max(1, fs_round(W[0] / p0))
    ny = max(1, fs_round(W[1] / (p0 * math.sqrt(3) / 2)))
    px, h = W[0] / nx, W[1] / ny
    a = min(1, max(0, irregular)) * JITTER["TRI"] * min(px, 2 * h / math.sqrt(3))
    R = []
    for j in range(ny + 1):
        xs = tri_row_x(j, nx)
        row = []
        for k, x in enumerate(xs):
            d = mul(jitter(k, j, a, s), min(1, x, nx - x))
            row.append((lo[0] + x * px + d[0], lo[1] + j * h + (0 if j in (0, ny) else d[1])))
        R.append(row)
    out = []
    for j in range(ny):
        out += zipper(R[j], R[j + 1], tri_row_x(j, nx), tri_row_x(j + 1, nx))
    return out


def hex_row_x(j, nx):
    if j % 2 == 0:
        return [k + 0.5 for k in range(nx)]
    return [float(k) for k in range(nx + 1)]


def voronoi_fit(lo, hi, cell, irregular, s):
    p0 = cell * PITCH["HEX"]
    W = sub(hi, lo)
    nx = max(1, fs_round(W[0] / p0))
    ny = max(1, fs_round(W[1] / (p0 * math.sqrt(3) / 2)))
    px, h = W[0] / nx, W[1] / ny
    a = min(1, max(0, irregular)) * JITTER["HEX"] * min(px, 2 * h / math.sqrt(3))
    S = []
    for j in range(ny):
        row = []
        for k, x in enumerate(hex_row_x(j, nx)):
            d = jitter(k, j, a, s)
            wall = x == 0 or x == nx
            row.append((lo[0] + x * px + (0 if wall else d[0]), lo[1] + (j + 0.5) * h + d[1]))
        S.append(row)
    rc = max((h * h + px * px / 4) / (2 * h), math.hypot(px, h) / 2) + 2 * a + 1e-6
    dj = math.ceil((2 * rc + 2 * a) / h) + 1
    out = []
    for j in range(ny):
        for sd in S[j]:
            nbrs = [q for jj in range(max(0, j - dj), min(ny - 1, j + dj) + 1) for q in S[jj]
                    if q != sd and vlen(sub(q, sd)) < 2 * rc]
            b0 = (max(lo[0], sd[0] - rc), max(lo[1], sd[1] - rc))
            b1 = (min(hi[0], sd[0] + rc), min(hi[1], sd[1] + rc))
            c = clip_all([b0, (b1[0], b0[1]), b1, (b0[0], b1[1])], sd, nbrs)
            if len(c) >= 3:
                out.append(c)
    return out


def fit_cells(shape, lo, hi, cell, irregular, s):
    if shape == "TRI":
        return tri_fit(lo, hi, cell, irregular, s)
    if shape == "HEX":
        return voronoi_fit(lo, hi, cell, irregular, s)
    return quad_fit(lo, hi, cell, irregular, s)


# ---------------------------------------------------------------- face boundary
#
# Onshape hands the feature a face as a bag of edges. Sampled with the face
# option set, every edge runs with the face on its left, so loops chain end to
# start, the outer loop comes out counter-clockwise and every inner loop
# clockwise -- which is how they are told apart.

@dataclass
class Edge:
    kind: str                     # "line" | "arc"
    a: tuple = (0, 0)             # line start / arc centre
    b: tuple = (0, 0)             # line end
    r: float = 0.0                # arc radius
    t0: float = 0.0               # arc start angle, degrees
    t1: float = 0.0               # arc end angle, degrees (t1 > t0 = counter-clockwise)

    def length(self):
        if self.kind == "line":
            return vlen(sub(self.b, self.a))
        return abs(math.radians(self.t1 - self.t0)) * self.r

    def at(self, t):              # t in 0..1, arc-length parameter
        if self.kind == "line":
            return add(self.a, mul(sub(self.b, self.a), t))
        ang = math.radians(self.t0 + (self.t1 - self.t0) * t)
        return (self.a[0] + self.r * math.cos(ang), self.a[1] + self.r * math.sin(ang))


# Points along one edge, and the worst gap between chord and curve.
def sample_edge(e: Edge):
    if e.kind == "line":
        return [e.at(0), e.at(1)], 0.0
    ang = abs(math.radians(e.t1 - e.t0))
    step = 2 * math.acos(max(-1.0, 1 - SAG / e.r)) if e.r > SAG else ang
    n = max(2, math.ceil(ang / step))
    return [e.at(k / n) for k in range(n + 1)], SAG


# The circle an edge lies on, or None: what lets a loop be recognised as a
# round hole, so it can get a round ring instead of a straight cut.
def edge_circle(e: Edge):
    return (e.a, e.r) if e.kind == "arc" else None


def same_circle(p, q):
    return p is not None and q is not None and vlen(sub(p[0], q[0])) < 1e-6 and abs(p[1] - q[1]) < 1e-6


# Chains sampled edges into closed loops by matching each end to the next start.
# Each poly is (points, sag) or (points, sag, circle); a loop whose every edge
# lies on one circle comes back as that circle.
def chain_loops(polys):
    return [(lp, sag) for lp, sag, _ in chain_loops_c(polys)]


def chain_loops_c(polys):
    tol = 1e-3
    used = [False] * len(polys)
    loops = []
    circ_of = lambda m: polys[m][2] if len(polys[m]) > 2 else None
    for k in range(len(polys)):
        if used[k]:
            continue
        used[k] = True
        loop = list(polys[k][0][:-1])
        sag = polys[k][1]
        circ = circ_of(k)
        start, end = polys[k][0][0], polys[k][0][-1]
        while vlen(sub(end, start)) > tol:
            nxt = -1
            for m in range(len(polys)):
                if not used[m] and vlen(sub(polys[m][0][0], end)) <= tol:
                    nxt = m
                    break
            if nxt < 0:
                raise ValueError("face boundary does not close")
            used[nxt] = True
            loop += polys[nxt][0][:-1]
            sag = max(sag, polys[nxt][1])
            if not same_circle(circ, circ_of(nxt)):
                circ = None
            end = polys[nxt][0][-1]
        loops.append((loop, sag, circ))
    return loops


def convex_hull(pts):
    p = sorted(set(pts))
    if len(p) <= 2:
        return p
    lower, upper = [], []
    for q in p:
        while len(lower) >= 2 and cross2(sub(lower[-1], lower[-2]), sub(q, lower[-1])) <= 0:
            lower.pop()
        lower.append(q)
    for q in reversed(p):
        while len(upper) >= 2 and cross2(sub(upper[-1], upper[-2]), sub(q, upper[-1])) <= 0:
            upper.pop()
        upper.append(q)
    return lower[:-1] + upper[:-1]


@dataclass
class Region:
    segs: list = field(default_factory=list)    # (a, b, sag, inner_index or -1)
    inners: list = field(default_factory=list)  # (hull, centre, radius, sag, circle or None)
    circles: list = field(default_factory=list) # (centre, radius, inner index) of each round inner loop
    lo: tuple = (0, 0)
    hi: tuple = (0, 0)
    grid: dict = field(default_factory=dict)
    gs: float = 1.0


def build_region(edges, grid_size):
    loops = chain_loops_c([sample_edge(e) + (edge_circle(e),) for e in edges])
    R = Region(gs=grid_size)
    xs = [p[0] for lp, _, _ in loops for p in lp]
    ys = [p[1] for lp, _, _ in loops for p in lp]
    R.lo, R.hi = (min(xs), min(ys)), (max(xs), max(ys))
    for lp, sag, circ in loops:
        inner = -1
        if signed_area(lp) < 0:
            hull = convex_hull(lp)
            c = centroid(hull)
            R.inners.append((hull, c, max(vlen(sub(q, c)) for q in hull), sag, circ))
            inner = len(R.inners) - 1
            if circ is not None:
                R.circles.append((circ[0], circ[1], inner))
        for k in range(len(lp)):
            R.segs.append((lp[k], lp[(k + 1) % len(lp)], sag, inner))
    # Bucket segments on a grid, so each cell only looks at segments near it.
    for idx, (a, b, _, _) in enumerate(R.segs):
        for gx in range(math.floor(min(a[0], b[0]) / R.gs), math.floor(max(a[0], b[0]) / R.gs) + 1):
            for gy in range(math.floor(min(a[1], b[1]) / R.gs), math.floor(max(a[1], b[1]) / R.gs) + 1):
                R.grid.setdefault((gx, gy), []).append(idx)
    return R


def near_segments(R, c, reach):
    found = set()
    g0x, g1x = math.floor((c[0] - reach) / R.gs), math.floor((c[0] + reach) / R.gs)
    g0y, g1y = math.floor((c[1] - reach) / R.gs), math.floor((c[1] + reach) / R.gs)
    for gx in range(g0x, g1x + 1):
        for gy in range(g0y, g1y + 1):
            for idx in R.grid.get((gx, gy), []):
                if idx not in found and seg_dist(c, R.segs[idx][0], R.segs[idx][1]) < reach:
                    found.add(idx)
    return sorted(found)


def seg_dist(p, a, b):
    ab = sub(b, a)
    L2 = dot(ab, ab)
    t = 0 if L2 == 0 else max(0, min(1, dot(sub(p, a), ab) / L2))
    return vlen(sub(p, add(a, mul(ab, t))))


# Ray-cast parity, along +x. Only the grid row the ray runs through can hold a
# segment that crosses it, since segments are filed under every bucket their
# bounding box touches.
def inside_region(R, p):
    gy = math.floor(p[1] / R.gs)
    gx_max = math.floor(R.hi[0] / R.gs)
    seen = set()
    crossings = 0
    for gx in range(math.floor(p[0] / R.gs), gx_max + 1):
        for idx in R.grid.get((gx, gy), []):
            if idx in seen:
                continue
            seen.add(idx)
            a, b = R.segs[idx][0], R.segs[idx][1]
            if (a[1] > p[1]) != (b[1] > p[1]):
                x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if x > p[0]:
                    crossings += 1
    return crossings % 2 == 1


# ---------------------------------------------------------------- holes

def nearest_on_loop(pts, c):
    if len(pts) == 1:
        return pts[0]
    best_d, best = math.inf, pts[0]
    for k in range(len(pts)):
        a, b = pts[k], pts[(k + 1) % len(pts)]
        ab = sub(b, a)
        L2 = dot(ab, ab)
        t = 0 if L2 == 0 else max(0, min(1, dot(sub(c, a), ab) / L2))
        p = add(a, mul(ab, t))
        if vlen(sub(c, p)) < best_d:
            best_d, best = vlen(sub(c, p)), p
    return best


# Keeps a core clear of an inner loop (a screw hole, a slot) by `clearance`,
# using one straight cut. Any half-plane x . u >= support(u) + clearance
# misses the loop's convex hull grown by the clearance, so every candidate
# direction u is safe; the one kept is whichever leaves the most core. The
# candidates are the way out from the nearest point of the hull -- exact for a
# round hole -- and each hull edge's outward normal, which is exact alongside
# a straight side, such as a slot's.
def inner_clip(core, c, hull, clearance):
    n = len(hull)
    cands = []
    inside = n >= 3
    for k in range(n):
        if cross2(sub(hull[(k + 1) % n], hull[k]), sub(c, hull[k])) < 0:
            inside = False
    if not inside:
        q = nearest_on_loop(hull, c)
        if vlen(sub(c, q)) > EPS:
            cands.append(unit(sub(c, q)))
    if n >= 3:
        for k in range(n):
            e = sub(hull[(k + 1) % n], hull[k])
            if vlen(e) > EPS:
                t = unit(e)
                cands.append((t[1], -t[0]))
    best, best_area = [], 0.0
    for u in cands:
        support = max(dot(q, u) for q in hull)
        kept = clip_half(core, mul(u, support + clearance), mul(u, -1))
        area = abs(signed_area(kept)) if len(kept) >= 3 else 0.0
        if area > best_area:
            best, best_area = kept, area
    return best


# Clips a core to the face: the border along the outline, and one straight cut
# per inner loop. With ring set, round inner loops are left alone here; they
# get round rings later, in finish_hole.
def region_clip(core, c, R, reach, border, r, ring=None):
    near = near_segments(R, c, reach)
    inside = inside_region(R, c)
    if not near:
        return core if inside else []
    seen_inner = set()
    for idx in near:
        a, b, sag, inner = R.segs[idx]
        if inner < 0:
            # With the centre inside the face, only segments that face it
            # count. A segment whose inside lies away from the centre is
            # behind some nearer boundary, which does the clipping -- and
            # applying it too would empty any cell that straddles a notch.
            # With the centre outside, every segment counts.
            if inside and cross2(sub(b, a), sub(c, a)) <= 0:
                continue
            core = clip_left_of(core, a, b, border + r + sag)
        elif inner not in seen_inner:
            seen_inner.add(inner)
            hull, _, _, isag, circ = R.inners[inner]
            if ring is not None and circ is not None:
                continue
            core = inner_clip(core, c, hull, border + r + isag)
        if len(core) < 3:
            return []
    return core


def hole_core(cell, R, rib, r, border, keep_r):
    """The convex core of one hole: the hole is this grown by r."""
    c = centroid(cell)
    core = inset_convex(cell, rib / 2 + r)
    if not core:
        return []
    cell_r = max(vlen(sub(q, c)) for q in cell)
    core = region_clip(core, c, R, cell_r + border + r + SAG + 1e-6, border, r)
    if not core:
        return []
    core = tidy(ccw(core))
    if not core:
        return []
    if keep_r > r and not inset_convex(core, keep_r - r):
        return []
    return core


# ---------------------------------------------------------------- round holes
#
# A round hole already in the face -- a bolt, a bearing -- can get a round
# ring of material instead of a straight cut. Every hole next to it is bitten
# by a disc, so the edge facing the circle is an arc about the same centre. In
# core terms (the hole shrunk by r) that is the core minus the disc of radius
# rho = Rc + ring + r. Grown back by r it is exactly the rounded hole kept
# `ring` clear of the circle, the disc's edge becoming an arc of radius
# Rc + ring: the same opening argument that makes the corner rounding exact.

MIN_SWEEP = 0.02     # radians: a shallower bite is cut straight instead
MIN_TURN = 0.02      # sine of the sharpest, and flattest, corner a bite may make


def point_in_convex(poly, p):
    n = len(poly)
    return n >= 3 and all(cross2(sub(poly[(k + 1) % n], poly[k]), sub(p, poly[k])) > 0 for k in range(n))


def poly_point_dist(poly, p):
    """Distance from a point to a convex polygon; 0 inside it."""
    return 0.0 if point_in_convex(poly, p) else vlen(sub(p, nearest_on_loop(poly, p)))


def circle_bite(core, C, rho):
    """A convex counter-clockwise core minus the disc (C, rho), when that is
    one shape the feature can draw: pts runs E ... X along the core, and the
    arc from X back to E, clockwise about C, closes it. Otherwise "none" (the
    disc misses), "gone" (the disc covers the core), "split" or "cut".
    "split": the disc's centre inside the core would leave the circle on an
    island, and a disc through the middle would split the core in two -- so
    the core is split by a rib through the circle first. "cut": a sliver of a
    bite, or of what is left, not worth its tiny sketch entities -- cut it
    straight instead, which costs next to nothing."""
    if poly_point_dist(core, C) >= rho:
        return "none"
    if max(vlen(sub(q, C)) for q in core) <= rho:
        return "gone"
    if point_in_convex(core, C):
        return "split"
    n = len(core)
    xs = []
    for k in range(n):
        a = core[k]
        d = sub(core[(k + 1) % n], a)
        f = sub(a, C)
        A, B, Q = dot(d, d), 2 * dot(f, d), dot(f, f) - rho * rho
        disc = B * B - 4 * A * Q
        if A <= 0 or disc <= 0:
            continue
        sq = math.sqrt(disc)
        t_in, t_out = (-B - sq) / (2 * A), (-B + sq) / (2 * A)
        if 0 <= t_in < 1:
            xs.append((k, 1, add(a, mul(d, t_in))))
        if 0 <= t_out < 1:
            xs.append((k, -1, add(a, mul(d, t_out))))
    if len(xs) != 2 or xs[0][1] == xs[1][1]:
        return "split"
    kX, _, X = xs[0] if xs[0][1] == 1 else xs[1]
    kE, _, E = xs[1] if xs[0][1] == 1 else xs[0]
    m = (kX - kE) % n
    if m == 0:
        m = n
    pts = [E] + [core[(kE + j) % n] for j in range(1, m + 1)] + [X]
    for k in range(len(pts) - 1):
        if vlen(sub(pts[k + 1], pts[k])) < TINY_EDGE:
            return "cut"
    uX, uE = unit(sub(X, C)), unit(sub(E, C))
    if -cross2(uX, uE) < math.sin(MIN_SWEEP):
        return "cut"
    if not point_in_convex(core, add(C, mul(unit(add(uX, uE)), rho))):
        return "cut"
    t_in = unit(sub(X, pts[-2]))
    t_out = unit(sub(pts[1], E))
    if cross2((t_in[1], -t_in[0]), mul(uX, -1)) < MIN_TURN or \
            cross2(mul(uE, -1), (t_out[1], -t_out[0])) < MIN_TURN:
        return "cut"
    return dict(C=C, rho=rho, pts=pts, sweep=math.acos(max(-1.0, min(1.0, dot(uX, uE)))))


# A straight cut keeping a core clear of the disc (C, rho): of a few
# half-planes that miss the disc, the one keeping the most core. The fallback
# when a bite will not do, and for every disc but the deepest.
def disc_cut(core, C, rho):
    cands = []
    g = sub(centroid(core), C)
    if vlen(g) > EPS:
        cands.append(unit(g))
    if not point_in_convex(core, C):
        q = sub(nearest_on_loop(core, C), C)
        if vlen(q) > EPS:
            cands.append(unit(q))
    for k in range(16):
        t = math.radians(22.5 * k)
        cands.append((math.cos(t), math.sin(t)))
    best, best_area = [], 0.0
    for u in cands:
        kept = clip_half(core, add(C, mul(u, rho)), mul(u, -1))
        area = abs(signed_area(kept)) if len(kept) >= 3 else 0.0
        if area > best_area:
            best, best_area = kept, area
    return tidy(ccw(best)) if best else []


# Tidies a core, keeps it out of every disc (C, rho) in discs -- one bite from
# the disc reaching deepest into it, a straight cut for any other -- and
# applies the smallest-hole test. Returns a list of holes {core, bite, cut}:
# none, one, or two when the core had to be split by a rib through a circle,
# split_d (rib / 2 + r) either side of it.
def finish_hole(core, discs, r, keep_r, split_d, depth=0):
    core = tidy(ccw(core))
    if not core:
        return []
    bite = None
    cut = False
    near = []
    for k, (C, rho) in enumerate(discs):
        dk = poly_point_dist(core, C)
        if dk < rho:
            near.append((dk - rho, k))
    near.sort()
    for _, k in near[1:]:
        core = disc_cut(core, *discs[k])
        cut = True
        if not core:
            return []
    if near:
        C, rho = discs[near[0][1]]
        b = circle_bite(core, C, rho)
        if b == "gone":
            return []
        if b == "split" and depth == 0:
            return split_hole(core, C, discs, r, keep_r, split_d)
        if b in ("cut", "split"):
            core = disc_cut(core, C, rho)
            cut = True
            if not core:
                return []
        elif b != "none":
            bite = b
    if keep_r > r:
        inner = inset_convex(core, keep_r - r)
        if not inner:
            return []
        # Bitten: a circle of keep_r fits iff some corner of the core shrunk
        # by keep_r - r stays keep_r - r clear of the disc.
        if bite and max(vlen(sub(q, bite["C"])) for q in inner) < bite["rho"] + keep_r - r:
            return []
    return [dict(core=core, bite=bite, sector=None, cut=cut)]


# A core holding a circle's centre, or cut through by its disc: split it by a
# rib through the centre, so that each side gets a true round bite, and take
# whichever of six directions keeps the most hole.
def split_hole(core, C, discs, r, keep_r, split_d):
    best, best_area = [], -1.0
    for k in range(6):
        t = math.radians(30 * k)
        u = (math.cos(t), math.sin(t))
        holes = []
        for piece in (keep_left(core, C, u, split_d), keep_right(core, C, u, split_d)):
            if len(piece) >= 3:
                holes += finish_hole(piece, discs, r, keep_r, split_d, 1)
        area = sum(shape_area(h, r) for h in holes)
        if area > best_area + 1e-9:
            best, best_area = holes, area
    return best


# ---------------------------------------------------------------- wheels
#
# With spokes on, each round hole gets a wheel: its ring, then a ring of
# sector-shaped holes split by straight spokes, then a hoop one rib wide, and
# the ordinary cells beyond, bitten round to meet it. A load on the bolt or
# bearing goes straight out along the spokes into the hoop, and from the hoop
# into the web all round.
#
#   Rc   the circle          Ra = Rc + ring     inner edge of the sectors
#   Rb = Ra + spoke length   outer edge         Rb + rib: cells start here
#
# A sector is exact -- two straight sides w/2 off the spokes, arcs of radius
# Ra and Rb, corners rounded by r -- wherever nothing else touches it. One that
# the border, an inner loop or another wheel reaches into is built as a
# polygon with its outer arc replaced by the chord (so only ever smaller) and
# goes through the same clipping and bite as an ordinary cell.

def left_normal(u):
    return (-u[1], u[0])


def keep_left(p, C, u, d):
    nv = left_normal(u)
    return clip_half(p, add(C, mul(nv, d)), mul(nv, -1))


def keep_right(p, C, u, d):
    nv = left_normal(u)
    return clip_half(p, sub(C, mul(nv, d)), nv)


def spoke_count(Ra, depth, cell, count):
    """Spokes round one circle: as asked, or about one per cell of
    circumference, halfway along the spokes."""
    if count > 0:
        return max(3, count)
    return max(3, fs_round(2 * math.pi * (Ra + depth / 2) / cell))


def spoke_dirs(n, angle):
    out = []
    for k in range(n):
        t = math.radians(angle + 360 * k / n)
        out.append((math.cos(t), math.sin(t)))
    return out


def sector_shape(C, u0, u1, d, ri, ro):
    """The eroded sector between spoke u0 (on its left) and spoke u1 (on its
    right), from ri to ro off C, or None when it is not a proper four-sided
    one. Corners: A0, B0 on spoke u0's side, B1, A1 on spoke u1's."""
    if ri <= d or ro <= ri:
        return None
    n0, n1 = left_normal(u0), left_normal(u1)
    si, so = math.sqrt(ri * ri - d * d), math.sqrt(ro * ro - d * d)
    if so - si < TINY_EDGE:
        return None
    A0, B0 = add(C, add(mul(n0, d), mul(u0, si))), add(C, add(mul(n0, d), mul(u0, so)))
    B1, A1 = add(C, add(mul(n1, -d), mul(u1, so))), add(C, add(mul(n1, -d), mul(u1, si)))
    a0, a1 = unit(sub(A0, C)), unit(sub(A1, C))
    b0, b1 = unit(sub(B0, C)), unit(sub(B1, C))
    # The inner arc runs clockwise from A1 to A0: it must turn a little at least.
    if cross2(a0, a1) < math.sin(MIN_SWEEP) or vlen(sub(A0, A1)) < TINY_EDGE:
        return None
    return dict(C=C, u0=u0, u1=u1, d=d, ri=ri, ro=ro, A0=A0, B0=B0, B1=B1, A1=A1,
                phi_i=math.acos(max(-1.0, min(1.0, dot(a0, a1)))),
                phi_o=math.acos(max(-1.0, min(1.0, dot(b0, b1)))))


def sector_keeps(s, k):
    """Does a circle k larger than the eroded sector's edges fit in it? Its
    best centre is on the bisector, ri + k .. ro - k out and far enough from
    the spokes."""
    if k <= 0:
        return True
    half = math.acos(max(-1.0, min(1.0, dot(s["u0"], s["u1"])))) / 2
    return max(s["ri"] + k, (s["d"] + k) / math.sin(half)) <= s["ro"] - k


def sector_polys(C, u0, u1, d, ro):
    """The wedge between two spokes cut off past ro: by the tangent to the
    outer arc (a polygon holding the true sector, to test it against) and by
    the chord (one inside it, to build a clipped sector from)."""
    h = ro + 1.0
    big = [(C[0] - h, C[1] - h), (C[0] + h, C[1] - h), (C[0] + h, C[1] + h), (C[0] - h, C[1] + h)]
    wedge = keep_right(keep_left(big, C, u0, d), C, u1, d)
    if len(wedge) < 3 or ro <= d:
        return [], []
    b = unit(add(u0, u1))
    tangent = clip_half(wedge, add(C, mul(b, ro)), b)
    so = math.sqrt(ro * ro - d * d)
    pl = add(C, add(mul(left_normal(u0), d), mul(u0, so)))
    pr = add(C, add(mul(left_normal(u1), -d), mul(u1, so)))
    chord = clip_left_of(wedge, pl, pr, 0.0)
    return tangent, chord


def wheel_holes(i, ros, zones, R, rib, r, border, keep_r):
    """The sector holes round circle i."""
    w = ros[i]
    C, dirs, d = w["C"], w["dirs"], w["d"]
    ri, ro = w["Ra"] + r, w["Rb"] - r
    holes = []
    n = len(dirs)
    for k in range(n):
        u0, u1 = dirs[k], dirs[(k + 1) % n]
        tangent, chord = sector_polys(C, u0, u1, d, ro)
        if len(tangent) < 3:
            continue
        others = [z for j, z in enumerate(zones) if j != i and poly_point_dist(tangent, z[0]) < z[1]]
        c = centroid(tangent)
        reach = max(vlen(sub(q, c)) for q in tangent) + border + r + SAG + 1e-6
        clipped = region_clip(tangent, c, R, reach, border, r, ring=True)
        s = sector_shape(C, u0, u1, d, ri, ro)
        if s and not others and clipped and \
                abs(abs(signed_area(clipped)) - abs(signed_area(tangent))) <= TINY_AREA:
            if sector_keeps(s, keep_r - r):
                holes.append(dict(core=None, bite=None, sector=s, cut=False))
            continue
        if len(chord) < 3:
            continue
        c = centroid(chord)
        core = region_clip(chord, c, R, reach, border, r, ring=True)
        if not core:
            continue
        holes += finish_hole(core, [(C, ri)] + others, r, keep_r, rib / 2 + r)
    return holes


def cell_holes(cell, R, rib, r, border, keep_r, ring=None, discs=()):
    """The holes one cell makes (none, one, or two split round a circle):
    a list of {core, bite, sector, cut}."""
    c = centroid(cell)
    core = inset_convex(cell, rib / 2 + r)
    if not core:
        return []
    cell_r = max(vlen(sub(q, c)) for q in cell)
    core = region_clip(core, c, R, cell_r + border + r + SAG + 1e-6, border, r, ring)
    if not core:
        return []
    return finish_hole(core, discs, r, keep_r, rib / 2 + r)


SPOKE_DEFAULTS = dict(count=0, width=3.0, length=10.0, angle=90.0)


def plan_face(edges, shape="QUAD", cell=14.0, rib=2.0, border=5.0, irregular=0.7,
              corner=1.0, min_hole=4.0, seed=1, fit=True, ring=None, spokes=None):
    """Everything the feature computes for one face, before it touches Onshape.
    ring: None for one straight cut round each inner loop, as before; else the
    width of the round ring kept round each round one. spokes: None, or a dict
    of count (0 = auto), width, length (ring to hoop) and angle (degrees) for
    a wheel round each round hole."""
    across = cell * PITCH[shape] * ACROSS[shape]
    hw = across - rib
    if hw <= 0.1:
        raise ValueError(f"rib {rib} leaves no hole in a {cell} cell")
    r = min(corner, 0.4 * hw)
    if r < MIN_RADIUS:
        r = 0.0
    keep_r = min(min_hole / 2, 0.4 * hw)
    bw = max(border, rib)
    if ring is not None:
        ring = max(ring, rib)
    R = build_region(edges, grid_size=max(cell * PITCH[shape], 1.0))
    plan = dict(holes=[], cores=[], r=r, keep_r=keep_r, border=bw, hw=hw, ring=ring,
                wheels=[], spoke_w=0.0, circles=R.circles)
    holes, discs = [], []
    if ring is not None:
        discs = [(C, Rc + ring + r) for C, Rc, _ in R.circles]
        if spokes is not None:
            sp = dict(SPOKE_DEFAULTS, **spokes)
            w = max(sp["width"], rib)
            depth = sp["length"]
            ros = []
            for C, Rc, _ in R.circles:
                Ra = Rc + ring
                n = spoke_count(Ra, depth, cell, sp["count"])
                ros.append(dict(C=C, Rc=Rc, Ra=Ra, Rb=Ra + depth, d=w / 2 + r, dirs=spoke_dirs(n, sp["angle"])))
            zones = [(w_["C"], w_["Rb"] + rib + r) for w_ in ros]
            # Wheels that overlap a lot would only cancel out into a solid
            # lump, so the larger circle keeps its wheel and the smaller one
            # just its ring: a centre inside an accepted wheel loses its own.
            order = sorted(range(len(ros)), key=lambda i: (-ros[i]["Rc"], i))
            on = [False] * len(ros)
            for i in order:
                on[i] = all(not on[j] or vlen(sub(ros[i]["C"], ros[j]["C"])) >= max(zones[i][1], zones[j][1])
                            for j in range(len(ros)))
            keep_out = [zones[j] if on[j] else discs[j] for j in range(len(ros))]
            for i in range(len(ros)):
                hs = wheel_holes(i, ros, keep_out, R, rib, r, bw, keep_r) if on[i] else []
                ros[i]["sectors"] = len(hs)
                holes += hs
                # A wheel with no sector left is no wheel: cells only keep
                # their ring clear of that circle.
                if hs:
                    discs[i] = zones[i]
            plan["wheels"] = ros
            plan["spoke_w"] = w
    if fit:
        ins = bw - rib / 2
        lo, hi = add(R.lo, (ins, ins)), sub(R.hi, (ins, ins))
        cells = fit_cells(shape, lo, hi, cell, irregular, seed) if hi[0] > lo[0] and hi[1] > lo[1] else []
    else:
        cells = crop_cells(shape, R.lo, R.hi, cell, irregular, seed)
    holes += [h for c in cells for h in cell_holes(c, R, rib, r, bw, keep_r, ring, discs)]
    plan["holes"] = holes
    plan["cores"] = [h["core"] for h in holes if h["core"]]
    return plan


# The outline the feature sketches for a core grown by r: straight edges moved
# out by r, joined by arcs of radius r about each corner. Returned as entities
# [("line", p0, p1) | ("arc", start, mid, end)] -- skLineSegment and skArc.
def outline(core, r):
    if r <= 0:
        return [("line", core[k], core[(k + 1) % len(core)]) for k in range(len(core))]
    n = len(core)
    normals = []
    for k in range(n):
        t = unit(sub(core[(k + 1) % n], core[k]))
        normals.append((t[1], -t[0]))         # outward, for counter-clockwise
    ents = []
    for k in range(n):
        a, b = core[k], core[(k + 1) % n]
        nk, nn = normals[k], normals[(k + 1) % n]
        ents.append(("line", add(a, mul(nk, r)), add(b, mul(nk, r))))
        ents.append(("arc", add(b, mul(nk, r)), add(b, mul(unit(add(nk, nn)), r)), add(b, mul(nn, r))))
    return ents


# The same for a bitten core: the lines and corner arcs along pts as above,
# then an arc of radius r about X onto the circle, the concave arc of radius
# rho - r = Rc + ring about the circle's centre, and an arc about E back onto
# the first edge. Shared endpoints come from one expression each, so the loop
# closes exactly.
def bite_outline(b, r):
    pts, C, rho = b["pts"], b["C"], b["rho"]
    X, E = pts[-1], pts[0]
    uX, uE = unit(sub(X, C)), unit(sub(E, C))
    mid = unit(add(uX, uE))
    if r <= 0:
        ents = [("line", pts[k], pts[k + 1]) for k in range(len(pts) - 1)]
        ents.append(("arc", X, add(C, mul(mid, rho)), E))
        return ents
    m = len(pts) - 1
    normals = []
    for k in range(m):
        t = unit(sub(pts[k + 1], pts[k]))
        normals.append((t[1], -t[0]))
    ents = []
    for k in range(m):
        nk = normals[k]
        ents.append(("line", add(pts[k], mul(nk, r)), add(pts[k + 1], mul(nk, r))))
        if k + 1 < m:
            nn = normals[k + 1]
            q = pts[k + 1]
            ents.append(("arc", add(q, mul(nk, r)), add(q, mul(unit(add(nk, nn)), r)), add(q, mul(nn, r))))
    aX, aE = sub(X, mul(uX, r)), sub(E, mul(uE, r))
    nl, n0 = normals[m - 1], normals[0]
    ents.append(("arc", add(X, mul(nl, r)), add(X, mul(unit(sub(nl, uX)), r)), aX))
    ents.append(("arc", aX, add(C, mul(mid, rho - r)), aE))
    ents.append(("arc", aE, add(E, mul(unit(sub(n0, uE)), r)), add(E, mul(n0, r))))
    return ents


# An exact sector: side lines w/2 off the spokes, the outer arc of radius
# ro + r = Rb and the inner one of radius ri - r = Ra, about the circle's
# centre, and a corner arc of radius r at each of its four corners.
def sector_outline(s, r):
    C, A0, B0, B1, A1 = s["C"], s["A0"], s["B0"], s["B1"], s["A1"]
    n0, n1 = left_normal(s["u0"]), left_normal(s["u1"])
    b = unit(add(s["u0"], s["u1"]))
    if r <= 0:
        return [("line", A0, B0), ("arc", B0, add(C, mul(b, s["ro"])), B1),
                ("line", B1, A1), ("arc", A1, add(C, mul(b, s["ri"])), A0)]
    a0, a1 = unit(sub(A0, C)), unit(sub(A1, C))
    b0, b1 = unit(sub(B0, C)), unit(sub(B1, C))
    pA0, pB0 = sub(A0, mul(n0, r)), sub(B0, mul(n0, r))
    qB0, qB1 = add(B0, mul(b0, r)), add(B1, mul(b1, r))
    pB1, pA1 = add(B1, mul(n1, r)), add(A1, mul(n1, r))
    qA1, qA0 = sub(A1, mul(a1, r)), sub(A0, mul(a0, r))
    return [("line", pA0, pB0),
            ("arc", pB0, add(B0, mul(unit(sub(b0, n0)), r)), qB0),
            ("arc", qB0, add(C, mul(b, s["ro"] + r)), qB1),
            ("arc", qB1, add(B1, mul(unit(add(b1, n1)), r)), pB1),
            ("line", pB1, pA1),
            ("arc", pA1, add(A1, mul(unit(sub(n1, a1)), r)), qA1),
            ("arc", qA1, add(C, mul(b, s["ri"] - r)), qA0),
            ("arc", qA0, add(A0, mul(unit(add(a0, n0)), -r)), pA0)]


def hole_outline(h, r):
    if h["sector"]:
        return sector_outline(h["sector"], r)
    return outline(h["core"], r) if h["bite"] is None else bite_outline(h["bite"], r)


def hole_area(core, r):
    per = sum(vlen(sub(core[(k + 1) % len(core)], core[k])) for k in range(len(core)))
    return abs(signed_area(core)) + per * r + math.pi * r * r


# A bitten hole: the polygon E ... X less the circular segment beyond its
# chord X-E, grown by r. Steiner's formula, area + perimeter r + pi r^2, holds
# for it as for a convex shape: its outline turns through one full turn, and
# grown by r it stays simple.
def bite_area(b, r):
    pts, rho, sw = b["pts"], b["rho"], b["sweep"]
    per = sum(vlen(sub(pts[k + 1], pts[k])) for k in range(len(pts) - 1)) + rho * sw
    area = abs(signed_area(pts)) - rho * rho / 2 * (sw - math.sin(sw))
    return area + per * r + math.pi * r * r


# A sector: its four corners' polygon, plus the outer circular segment, less
# the inner one; then Steiner's formula as above.
def sector_area(s, r):
    ri, ro, pi_, po = s["ri"], s["ro"], s["phi_i"], s["phi_o"]
    side = vlen(sub(s["B0"], s["A0"])) + vlen(sub(s["A1"], s["B1"]))
    area = abs(signed_area([s["A0"], s["B0"], s["B1"], s["A1"]])) \
        + ro * ro / 2 * (po - math.sin(po)) - ri * ri / 2 * (pi_ - math.sin(pi_))
    return area + (side + ro * po + ri * pi_) * r + math.pi * r * r


def shape_area(h, r):
    if h["sector"]:
        return sector_area(h["sector"], r)
    return hole_area(h["core"], r) if h["bite"] is None else bite_area(h["bite"], r)


# ---------------------------------------------------------------- test faces

def rect(x0, y0, x1, y1):
    return [Edge("line", (x0, y0), (x1, y0)), Edge("line", (x1, y0), (x1, y1)),
            Edge("line", (x1, y1), (x0, y1)), Edge("line", (x0, y1), (x0, y0))]


def rounded_rect(x0, y0, x1, y1, rr):
    return [Edge("line", (x0 + rr, y0), (x1 - rr, y0)), Edge("arc", (x1 - rr, y0 + rr), r=rr, t0=-90, t1=0),
            Edge("line", (x1, y0 + rr), (x1, y1 - rr)), Edge("arc", (x1 - rr, y1 - rr), r=rr, t0=0, t1=90),
            Edge("line", (x1 - rr, y1), (x0 + rr, y1)), Edge("arc", (x0 + rr, y1 - rr), r=rr, t0=90, t1=180),
            Edge("line", (x0, y1 - rr), (x0, y0 + rr)), Edge("arc", (x0 + rr, y0 + rr), r=rr, t0=180, t1=270)]


def circle_loop(cx, cy, r, hole=False):
    # An inner loop runs clockwise, keeping the face on its left.
    return [Edge("arc", (cx, cy), r=r, t0=360, t1=0)] if hole else [Edge("arc", (cx, cy), r=r, t0=0, t1=360)]


def slot_loop(x0, x1, y, w):
    # A clockwise stadium: an inner loop.
    rr = w / 2
    return [Edge("line", (x0, y + rr), (x1, y + rr)), Edge("arc", (x1, y), r=rr, t0=90, t1=-90),
            Edge("line", (x1, y - rr), (x0, y - rr)), Edge("arc", (x0, y), r=rr, t0=270, t1=90)]


def l_shape():
    return [Edge("line", (0, 0), (120, 0)), Edge("line", (120, 0), (120, 40)),
            Edge("line", (120, 40), (50, 40)), Edge("line", (50, 40), (50, 90)),
            Edge("line", (50, 90), (0, 90)), Edge("line", (0, 90), (0, 0))]


def notched():
    # A rectangle with a narrow slot cut in from the top edge.
    return [Edge("line", (0, 0), (100, 0)), Edge("line", (100, 0), (100, 70)),
            Edge("line", (100, 70), (55, 70)), Edge("line", (55, 70), (55, 25)),
            Edge("line", (55, 25), (45, 25)), Edge("line", (45, 25), (45, 70)),
            Edge("line", (45, 70), (0, 70)), Edge("line", (0, 70), (0, 0))]


def side_plate():
    # A robot drive side plate: 260 x 110, 6 mm corners, a row of 5.1 mm bolt
    # holes round the edge, two 22 mm bearing bores and an 8 mm hole between.
    bolts = [(8, 8), (8, 55), (8, 102), (95, 8), (95, 102), (165, 8), (165, 102),
             (252, 8), (252, 55), (252, 102)]
    return (rounded_rect(0, 0, 260, 110, 6)
            + sum((circle_loop(x, y, 2.55, hole=True) for x, y in bolts), [])
            + circle_loop(60, 55, 11, hole=True) + circle_loop(200, 55, 11, hole=True)
            + circle_loop(130, 55, 4, hole=True))


def cluster():
    # Three holes close enough that their rings overlap, and one by an edge.
    return (rect(0, 0, 120, 90) + circle_loop(40, 45, 3, hole=True)
            + circle_loop(52, 45, 3, hole=True) + circle_loop(46, 56, 4, hole=True)
            + circle_loop(100, 9, 3, hole=True))


FACES = {
    "rect_120x80": rect(0, 0, 120, 80),
    "rounded_rect": rounded_rect(0, 0, 120, 80, 8),
    "circle_d100": circle_loop(0, 0, 50),
    "rect_4_screws": rect(0, 0, 100, 100) + sum((circle_loop(x, y, 2.2, hole=True)
                                               for x in (6, 94) for y in (6, 94)), []),
    "plate_big_hole": rect(0, 0, 140, 100) + circle_loop(70, 50, 22, hole=True),
    "plate_slot": rect(0, 0, 120, 80) + slot_loop(30, 90, 40, 8),
    "l_shape": l_shape(),
    "notched": notched(),
    "annulus": circle_loop(0, 0, 60) + circle_loop(0, 0, 25, hole=True),
}

# Faces for the round rings and spokes: the four above with round holes, the
# slot (not round: must be left to the straight cut), and two new ones.
ROUND_FACES = dict(
    rect_4_screws=FACES["rect_4_screws"], plate_big_hole=FACES["plate_big_hole"],
    annulus=FACES["annulus"], plate_slot=FACES["plate_slot"], side_plate=side_plate(),
    cluster=cluster())


# Sampling for measurement, on the safe side: an arc the face lies inside
# (counter-clockwise, face on the left) by chords, which fall inside the face;
# an arc round a hole in the face (clockwise) by tangents, which fall outside
# the hole. Either way the sampled face is slightly smaller than the true one,
# so every clearance measured to it comes out slightly small, never large.
def fine(e):
    if e.kind == "line":
        return [e.at(0), e.at(1)]
    n = max(8, math.ceil(abs(e.t1 - e.t0) * 8))
    if e.t1 > e.t0:
        return [e.at(k / n) for k in range(n + 1)]
    h = math.radians(e.t1 - e.t0) / n
    out = [e.at(0)]
    for k in range(n):
        t = math.radians(e.t0) + (k + 0.5) * h
        out.append((e.a[0] + e.r / math.cos(h / 2) * math.cos(t), e.a[1] + e.r / math.cos(h / 2) * math.sin(t)))
    return out + [e.at(1)]


def true_loops(edges):
    return chain_loops_c([(fine(e), 0, edge_circle(e)) for e in edges])


def true_region(edges):
    """The face as shapely geometry, sampled on the safe side (see fine)."""
    import shapely
    loops = [lp for lp, _, _ in true_loops(edges)]
    outer = max(loops, key=signed_area)
    holes = [lp for lp in loops if lp is not outer]
    return shapely.Polygon(outer, holes)


def p_shape(h):
    """The hole shrunk by r, as a polygon. Exact for a plain core. A bite's arc
    is sampled with chords 1e-7 mm inside its disc, so the shape is that much
    larger than the truth and clearances from it come out that much small."""
    import shapely
    if h["sector"]:
        # Outer arc by tangents (outside it), inner arc by chords (inside the
        # disc): again a touch larger than the truth, never smaller.
        sc = h["sector"]
        C, ri, ro = sc["C"], sc["ri"], sc["ro"]
        ang = lambda q: math.atan2(q[1] - C[1], q[0] - C[0])
        no = max(2, math.ceil(sc["phi_o"] / (2 * math.acos(1 - 1e-7 / ro))))
        ni = max(2, math.ceil(sc["phi_i"] / (2 * math.acos(1 - 1e-7 / ri))))
        tB, ho = ang(sc["B0"]), sc["phi_o"] / no
        tA = ang(sc["A1"])
        outer = [(C[0] + ro / math.cos(ho / 2) * math.cos(tB + (k + 0.5) * ho),
                  C[1] + ro / math.cos(ho / 2) * math.sin(tB + (k + 0.5) * ho)) for k in range(no)]
        inner = [(C[0] + ri * math.cos(tA - sc["phi_i"] * k / ni), C[1] + ri * math.sin(tA - sc["phi_i"] * k / ni))
                 for k in range(1, ni)]
        return shapely.Polygon([sc["A0"], sc["B0"]] + outer + [sc["B1"], sc["A1"]] + inner)
    if h["bite"] is None:
        return shapely.Polygon(h["core"])
    b = h["bite"]
    C, rho, sw = b["C"], b["rho"], b["sweep"]
    X = b["pts"][-1]
    n = max(2, math.ceil(sw / (2 * math.acos(1 - 1e-7 / rho))))
    tX = math.atan2(X[1] - C[1], X[0] - C[0])
    arc = [(C[0] + rho * math.cos(tX - sw * k / n), C[1] + rho * math.sin(tX - sw * k / n)) for k in range(1, n)]
    return shapely.Polygon(b["pts"] + arc)


def arc_centre(s, m, e):
    ax, ay = s
    bx, by = m
    cx, cy = e
    dd = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    return ((a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / dd,
            (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / dd)


def ent_points(e, k):
    """k + 1 points along one sketch entity, ends included -- the arc through
    its three points, as Onshape would draw it."""
    if e[0] == "line":
        return [add(e[1], mul(sub(e[2], e[1]), j / k)) for j in range(k + 1)]
    s, m, f = e[1], e[2], e[3]
    O = arc_centre(s, m, f)
    rad = vlen(sub(s, O))
    ang = lambda p: math.atan2(p[1] - O[1], p[0] - O[0])
    a0, am, a1 = ang(s), ang(m), ang(f)
    tau = 2 * math.pi
    sweep = (a1 - a0) % tau if (am - a0) % tau < (a1 - a0) % tau else -((a0 - a1) % tau)
    return [(O[0] + rad * math.cos(a0 + sweep * j / k), O[1] + rad * math.sin(a0 + sweep * j / k))
            for j in range(k + 1)]


def hole_polygon(h, r, k=24):
    """The hole as sketched: its outline entities, sampled."""
    import shapely
    pts = []
    for e in hole_outline(h, r):
        pts += ent_points(e, k if e[0] == "arc" else 1)[:-1]
    return shapely.Polygon(pts)


def outline_error(h, r, P):
    """How far the sketched outline is from exact: gaps between consecutive
    entities, and how far points along it are from distance r off the core.
    Every point of a closed simple loop lying at distance r from the core
    makes the loop the core's r-offset -- the rounded hole -- exactly."""
    ents = hole_outline(h, r)
    err = 0.0
    for k, e in enumerate(ents):
        nxt = ents[(k + 1) % len(ents)]
        err = max(err, vlen(sub(e[-1], nxt[1])))
        import shapely
        for p in ent_points(e, 8):
            dist = P.exterior.distance(shapely.Point(p)) if r <= 0 else P.distance(shapely.Point(p))
            err = max(err, abs(dist - r))
    return err


def measure(edges, plan):
    import shapely
    from shapely.strtree import STRtree
    r = plan["r"]
    region = true_region(edges)
    ring = plan.get("ring")
    res = dict(holes=len(plan["holes"]), rib=math.inf, border=math.inf, ring=math.inf, spoke=math.inf,
               smallest=math.inf, outside=0, invalid=0, islands=0, outline=0.0, open=0.0,
               bites=sum(1 for h in plan["holes"] if h["bite"]), cuts=sum(1 for h in plan["holes"] if h.get("cut")))
    if not plan["holes"]:
        return res
    P = [p_shape(h) for h in plan["holes"]]
    tree = STRtree(P)
    for i, p in enumerate(P):
        for j in tree.query(p, predicate="dwithin", distance=50.0):
            if j > i:
                res["rib"] = min(res["rib"], p.distance(P[j]) - 2 * r)
    # Border: to the outline and every inner loop -- or, with round rings, to
    # every inner loop but the round ones, which are measured as true circles.
    lines = [shapely.LinearRing(lp) for lp, _, circ in true_loops(edges)
             if ring is None or circ is None or signed_area(lp) > 0]
    bnd = shapely.MultiLineString([list(l.coords) for l in lines])
    res["border"] = min(p.distance(bnd) for p in P) - r
    if ring is not None:
        for C, Rc, _ in plan["circles"]:
            pc = shapely.Point(C)
            res["ring"] = min(res["ring"], min(p.distance(pc) for p in P) - r - Rc)
        w = plan["spoke_w"]
        for wh in plan["wheels"]:
            if not wh["sectors"]:
                continue
            C = wh["C"]
            for u in wh["dirs"]:
                seg = shapely.LineString([add(C, mul(u, wh["Rc"])), add(C, mul(u, wh["Rb"]))])
                for j in tree.query(seg, predicate="dwithin", distance=w / 2 + r + 1.0):
                    res["spoke"] = min(res["spoke"], 2 * (P[j].distance(seg) - r))
    polys = []
    for h, p in zip(plan["holes"], P):
        hp = hole_polygon(h, r)
        polys.append(hp)
        if not hp.is_valid:
            res["invalid"] += 1
        if not region.contains(p.representative_point()):
            res["outside"] += 1
        res["outline"] = max(res["outline"], outline_error(h, r, p))
        mic = shapely.maximum_inscribed_circle(p, tolerance=0.005).length if p.area > 0 else 0.0
        res["smallest"] = min(res["smallest"], 2 * (mic + r))
    left = region.difference(shapely.unary_union(polys))
    res["islands"] = len(getattr(left, "geoms", [left])) - 1
    res["open"] = 100 * sum(shape_area(h, r) for h in plan["holes"]) / region.area
    return res


def case_errors(plan, m, kw):
    tol = 1e-6
    rib = kw.get("rib", 2.0)
    errs = [f"{k} measured as NaN" for k, v in m.items() if isinstance(v, float) and math.isnan(v)]
    if m["rib"] < rib - tol:
        errs.append(f"rib {m['rib']:.6f} < {rib}")
    if m["border"] < plan["border"] - tol:
        errs.append(f"border {m['border']:.6f} < {plan['border']}")
    if plan.get("ring") is not None and m["ring"] < plan["ring"] - tol:
        errs.append(f"ring {m['ring']:.6f} < {plan['ring']}")
    if plan.get("wheels") and m["spoke"] < plan["spoke_w"] - tol:
        errs.append(f"spoke {m['spoke']:.6f} < {plan['spoke_w']}")
    if m["outside"]:
        errs.append(f"{m['outside']} holes outside the face")
    if m["invalid"]:
        errs.append(f"{m['invalid']} self-intersecting outlines")
    if m["islands"]:
        errs.append(f"{m['islands']} loose islands")
    if m["outline"] > 1e-6:
        errs.append(f"outline off by {m['outline']:.2e}")
    if m["holes"] and m["smallest"] < 2 * min(plan["keep_r"], plan["hw"]) - 0.02 and plan["keep_r"] > plan["r"]:
        errs.append(f"smallest {m['smallest']:.3f} < {2 * plan['keep_r']:.3f}")
    return errs


CLASSIC_SETTINGS = [
    dict(),
    dict(irregular=1.0),
    dict(irregular=0.0),
    dict(fit=False),
    dict(fit=False, irregular=1.0),
    dict(rib=0.8, cell=8, border=3, min_hole=3),
    dict(corner=0.0, min_hole=0.0),
    dict(corner=4.0),
    dict(rib=4.0, cell=20, border=6),
]

ROUND_SETTINGS = [
    dict(ring=5.0),
    dict(ring=5.0, spokes={}),
    dict(ring=3.0, spokes=dict(width=2.0)),
    dict(ring=5.0, spokes=dict(count=4, length=40.0)),
    dict(ring=5.0, spokes=dict(count=12, width=4.0)),
    dict(ring=5.0, spokes=dict(angle=17.0), irregular=1.0),
    dict(ring=8.0, spokes={}, corner=4.0),
    dict(ring=2.0, spokes={}, corner=0.0, min_hole=0.0),
    dict(ring=5.0, spokes={}, fit=False),
    dict(ring=1.0, spokes=dict(width=0.8, length=8.0), rib=0.8, cell=8, border=3, min_hole=3),
    dict(ring=6.0, spokes=dict(width=5.0), rib=4.0, cell=20, border=6),
]


def run_block(job):
    """One face and cell shape, every setting and seed. Returns (lines, cases, fails)."""
    group, fname, shape, verbose = job
    faces, settings = MATRICES[group]
    edges = faces[fname]
    lines, n, fails = [], 0, 0
    for st in settings:
        for seed in (1, 7, 23):
            kw = dict(shape=shape, seed=seed, **st)
            plan = plan_face(edges, **kw)
            m = measure(edges, plan)
            errs = case_errors(plan, m, kw)
            n += 1
            if errs:
                fails += 1
                lines.append(f"FAIL {fname} {kw}: {'; '.join(errs)}")
    if verbose:
        kw = dict(shape=shape, **settings[verbose - 1])
        plan = plan_face(edges, **kw)
        m = measure(edges, plan)
        extra = ""
        if plan.get("ring") is not None:
            extra = (f" ring={m['ring']:.4f}" + (f" spoke={m['spoke']:.4f}" if plan["wheels"] else "")
                     + f" bites={m['bites']} cuts={m['cuts']}")
        lines.append(f"  {fname:<15} {shape:<4} holes={m['holes']:<4} rib={m['rib']:.4f} "
                     f"border={m['border']:.4f}{extra} smallest={m['smallest']:.3f} open={m['open']:.1f}%")
    return lines, n, fails


MATRICES = {}


def run_matrix(group, verbose, label, jobs=4):
    from multiprocessing import Pool
    faces, _ = MATRICES[group]
    work = [(group, f, sh, verbose) for f in faces for sh in ("QUAD", "TRI", "HEX")]
    n = fails = 0
    with Pool(jobs) as pool:
        for lines, bn, bf in pool.imap(run_block, work):
            for ln in lines:
                print(ln, flush=True)
            n += bn
            fails += bf
    print(f"== {label}: {n - fails}/{n} cases passed ==")
    return fails


def run_checks(verbose=True, only=None, jobs=4):
    MATRICES.update(classic=(FACES, CLASSIC_SETTINGS), round=(ROUND_FACES, ROUND_SETTINGS))
    fails = 0
    if only in (None, "classic"):
        print("Straight cuts round inner loops (round rings off):")
        fails += run_matrix("classic", 1 if verbose else 0, "straight cuts", jobs)
    if only in (None, "round"):
        print("Round rings and wheels (defaults: ring 5, spokes 3 mm thick, 10 mm long, auto count):")
        fails += run_matrix("round", 2 if verbose else 0, "round rings and wheels", jobs)
    return 1 if fails else 0


def draw(edges, plan, path, scale=6):
    from PIL import Image, ImageDraw
    region = true_region(edges)
    x0, y0, x1, y1 = region.bounds
    pad = 6
    W, H = int((x1 - x0) * scale) + 2 * pad, int((y1 - y0) * scale) + 2 * pad
    img = Image.new("RGB", (W, H), (248, 248, 248))
    d = ImageDraw.Draw(img)
    tf = lambda p: (pad + (p[0] - x0) * scale, H - pad - (p[1] - y0) * scale)
    d.polygon([tf(p) for p in region.exterior.coords], fill=(47, 120, 125))
    for ring in region.interiors:
        d.polygon([tf(p) for p in ring.coords], fill=(248, 248, 248))
    for h in plan["holes"]:
        hp = hole_polygon(h, plan["r"])
        d.polygon([tf(p) for p in hp.exterior.coords], fill=(248, 248, 248))
    img.save(path)


def fallback_report():
    """Every straight cut the round-hole code falls back to, on the round test
    faces at ring 5 with and without spokes: why, how often, and how much hole
    it costs against the exact bite (measured with shapely)."""
    import shapely
    global disc_cut, circle_bite
    real_cut, real_bite = disc_cut, circle_bite
    stats = {}
    why = ["a second circle"]

    def bite(core, C, rho):
        b = real_bite(core, C, rho)
        why[0] = {"cut": "a sliver of a bite", "split": "a split half needing a split"}.get(b, "a second circle") \
            if isinstance(b, str) else "a second circle"
        return b

    def cut(core, C, rho):
        out = real_cut(core, C, rho)
        truth = shapely.Polygon(core).difference(shapely.Point(C).buffer(rho, quad_segs=256))
        lost = truth.area - (abs(signed_area(out)) if out else 0.0)
        st = stats.setdefault(why[0], [0, 0.0, 0.0])
        st[0] += 1
        st[1] = max(st[1], lost)
        st[2] += lost
        why[0] = "a second circle"
        return out

    disc_cut, circle_bite = cut, bite
    plans = holes = 0
    try:
        for edges in ROUND_FACES.values():
            for shape in ("QUAD", "TRI", "HEX"):
                for st in (dict(ring=5.0), dict(ring=5.0, spokes={})):
                    for seed in (1, 7, 23):
                        holes += len(plan_face(edges, shape=shape, seed=seed, **st)["holes"])
                        plans += 1
    finally:
        disc_cut, circle_bite = real_cut, real_bite
    print(f"{plans} plans, {holes} holes. Straight cuts instead of an exact bite, because of:")
    for k, (cnt, worst, tot) in sorted(stats.items()):
        print(f"  {k:<30} {cnt:>4} cuts, {cnt / plans:.1f} per plan, "
              f"area lost mean {tot / cnt:.2f} mm^2, worst {worst:.2f} mm^2")


def round_preview(path, face="side_plate", scale=3.0):
    """The docs picture: one face, straight cuts against round rings against
    wheels, for each cell shape."""
    from PIL import Image, ImageDraw, ImageFont
    import tempfile, os
    edges = dict(FACES, **ROUND_FACES)[face]
    cols = [("Before: straight cuts", dict()), ("Round rings", dict(ring=5.0)),
            ("Round rings + spokes (default)", dict(ring=5.0, spokes={}))]
    rows = [("4 sides", "QUAD"), ("3 sides", "TRI"), ("6 sides", "HEX")]
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for _, shape in rows:
            row = []
            for _, st in cols:
                f = os.path.join(tmp, f"{shape}{len(row)}.png")
                draw(edges, plan_face(edges, shape=shape, **st), f, scale=scale)
                row.append(Image.open(f).copy())
            tiles.append(row)
    w, h = tiles[0][0].size
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    left, top, gap = 120, 46, 14
    sheet = Image.new("RGB", (left + 3 * w + 2 * gap, top + 3 * h + 2 * gap), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for c, (label, _) in enumerate(cols):
        d.text((left + c * (w + gap) + 6, 10), label, fill=(30, 30, 30), font=font)
    for r_, (label, _) in enumerate(rows):
        d.text((8, top + r_ * (h + gap) + h // 2 - 14), label, fill=(30, 30, 30), font=font)
        for c in range(3):
            sheet.paste(tiles[r_][c], (left + c * (w + gap), top + r_ * (h + gap)))
    sheet.save(path)


# ---------------------------------------------------------------- crosscheck
#
# Runs the .fs file's own functions through tools/fsinterp.py on the same
# inputs as this mirror, and requires the same answer at every stage. The
# mirror is what `check` measured; agreement carries those measurements over
# to the FeatureScript. What is left untested is only the Onshape I/O:
# reading the face, and the sketch / extrude / boolean calls.

def run_crosscheck(fs_path):
    import fsinterp
    from fsinterp import Vec

    it = fsinterp.Interp(open(fs_path).read())
    shapes = {s: it.globals.get("LeopardCellShape")[s] for s in ("QUAD", "TRI", "HEX")}
    recorded = []
    it.globals.declare("skLineSegment", lambda sk, ident, m: recorded.append(
        ("line", ident, tuple(m["start"]), tuple(m["end"]))))
    it.globals.declare("skArc", lambda sk, ident, m: recorded.append(
        ("arc", ident, tuple(m["start"]), tuple(m["mid"]), tuple(m["end"]))))

    def same_pt(a, b, tol=1e-9):
        return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol

    # Same polygon, allowing a different starting corner: a coordinate that
    # differs in the 16th digit (FeatureScript's cos(t * degree) against
    # Python's cos(radians(t))) can tip a strict comparison on a corner that
    # lies exactly on a clip line, and the clip then starts its output at the
    # next corner. Measured on every such case: same corners, Hausdorff
    # distance ~1e-15 mm.
    def rotation(a, b):
        if len(a) != len(b):
            return None
        if not a:
            return 0
        for k in range(len(b)):
            if all(same_pt(a[i], b[(i + k) % len(b)]) for i in range(len(a))):
                return k
        return None

    def same_poly(a, b):
        return rotation(a, b) is not None

    settings = [dict(), dict(irregular=1.0), dict(irregular=0.0), dict(fit=False),
                dict(rib=0.8, cell=8, border=3, min_hole=3), dict(corner=0.0, min_hole=0.0),
                dict(corner=4.0)]
    n = fails = holes = 0
    for fname, edges in FACES.items():
        fs_polys = fs_polys_of(edges)
        for shape in ("QUAD", "TRI", "HEX"):
            for st in settings:
                kw = dict(shape=shape, cell=14.0, rib=2.0, border=5.0, irregular=0.7,
                          corner=1.0, min_hole=4.0, seed=3, fit=True)
                kw.update(st)
                n += 1
                errs = []
                # settings maths, as in the feature body
                hw = kw["cell"] * PITCH[shape] * ACROSS[shape] - kw["rib"]
                r = min(kw["corner"], 0.4 * hw)
                r = 0.0 if r < MIN_RADIUS else r
                keep_r = min(kw["min_hole"] / 2, 0.4 * hw)
                bw = max(kw["border"], kw["rib"])
                gs = max(kw["cell"] * PITCH[shape], 1.0)
                if abs(it.call("pitchOf", shapes[shape]) * it.call("acrossOf", shapes[shape])
                       - PITCH[shape] * ACROSS[shape]) > 1e-12:
                    errs.append("pitch/across constants differ")

                R = build_region(edges, gs)
                fR = it.call("buildRegion", fs_polys, float(gs))
                if len(fR["segs"]) != len(R.segs) or not all(
                        same_pt(s["a"], m[0]) and same_pt(s["b"], m[1]) and s["sag"] == m[2]
                        and s["inner"] == m[3] for s, m in zip(fR["segs"], R.segs)):
                    errs.append("region segments differ")

                if kw["fit"]:
                    ins = bw - kw["rib"] / 2
                    lo, hi = add(R.lo, (ins, ins)), sub(R.hi, (ins, ins))
                    cells = fit_cells(shape, lo, hi, kw["cell"], kw["irregular"], kw["seed"])
                    fcells = it.call("fitCells", shapes[shape], Vec(lo), Vec(hi), kw["cell"],
                                     kw["irregular"], float(kw["seed"]))
                else:
                    cells = crop_cells(shape, R.lo, R.hi, kw["cell"], kw["irregular"], kw["seed"])
                    fcells = it.call("cropCells", shapes[shape], fR["lo"], fR["hi"], kw["cell"],
                                     kw["irregular"], float(kw["seed"]))
                if len(cells) != len(fcells) or not all(same_poly(a, b) for a, b in zip(cells, fcells)):
                    errs.append(f"cells differ ({len(cells)} vs {len(fcells)})")
                else:
                    for k, c in enumerate(cells):
                        mc = hole_core(c, R, kw["rib"], r, bw, keep_r)
                        fc = it.call("holeCore", fcells[k], fR, kw["rib"], r, bw, keep_r)
                        if not same_poly(mc, fc):
                            errs.append(f"core {k} differs")
                            break
                        if mc:
                            holes += 1
                            if abs(hole_area(mc, r) - it.call("coreArea", fc, r)) > 1e-9:
                                errs.append(f"hole area {k} differs")
                                break
                            recorded.clear()
                            it.call("drawHole", None, "h", {"core": fc}, r)
                            # Entities come one line and one arc per corner, so
                            # a core rotated by k corners rotates them by 2k.
                            want = outline(mc, r)
                            per = 2 if r > 0 else 1
                            # fc[j] is mc[j - k], so entity j is want[j - per*k].
                            k0 = (-rotation(mc, fc) * per) % len(want)
                            want = want[k0:] + want[:k0]
                            got = [(e[0],) + e[2:] for e in recorded]
                            if len(want) != len(got) or not all(
                                    w[0] == g[0] and all(same_pt(p, q) for p, q in zip(w[1:], g[1:]))
                                    for w, g in zip(want, got)):
                                errs.append(f"sketch entities for hole {k} differ")
                                break
                if errs:
                    fails += 1
                    print(f"FAIL {fname} {shape} {st}: {'; '.join(errs)}")
        print(f"  {fname:<15} ok so far: {n - fails}/{n}")
    print(f"== crosscheck, straight cuts: {n - fails}/{n} cases agree, {holes} holes compared point by point ==")
    rfails = run_round_crosscheck(it, shapes, recorded, same_pt, rotation)
    return 1 if fails or rfails else 0


def fs_polys_of(edges):
    from fsinterp import Vec
    out = []
    for e in edges:
        pts, sag = sample_edge(e)
        circ = edge_circle(e)
        out.append({"pts": [Vec(p) for p in pts], "sag": sag,
                    "circle": None if circ is None else {"c": Vec(circ[0]), "r": float(circ[1])}})
    return out


# The round rings and wheels: planHoles, the .fs file's whole hole plan for a
# face, against plan_face, hole by hole; then every hole's sketch entities and
# area, and drawHole's calls for each.
def run_round_crosscheck(it, shapes, recorded, same_pt, rotation):
    from fsinterp import Vec
    settings = [dict(), dict(ring=5.0), dict(ring=5.0, spokes={}), dict(ring=3.0, spokes=dict(width=2.0, count=7)),
                dict(ring=5.0, spokes=dict(angle=17.0), irregular=1.0), dict(ring=8.0, spokes={}, corner=4.0),
                dict(ring=2.0, spokes={}, corner=0.0, min_hole=0.0), dict(ring=5.0, spokes={}, fit=False)]
    n = fails = 0
    counts = dict(core=0, bite=0, sector=0)
    for fname, edges in ROUND_FACES.items():
        fs_polys = fs_polys_of(edges)
        for shape in ("QUAD", "TRI", "HEX"):
            for st in settings:
                kw = dict(shape=shape, cell=14.0, rib=2.0, border=5.0, irregular=0.7,
                          corner=1.0, min_hole=4.0, seed=3, fit=True)
                kw.update(st)
                n += 1
                errs = []
                plan = plan_face(edges, **kw)
                R = build_region(edges, max(kw["cell"] * PITCH[shape], 1.0))
                fR = it.call("buildRegion", fs_polys, float(max(kw["cell"] * PITCH[shape], 1.0)))
                if len(fR["circles"]) != len(R.circles) or not all(
                        same_pt(f["c"], m[0]) and abs(f["r"] - m[1]) < 1e-12 and f["inner"] == m[2]
                        for f, m in zip(fR["circles"], R.circles)):
                    errs.append("round inner loops differ")
                sp = dict(SPOKE_DEFAULTS, **kw["spokes"]) if "spokes" in kw else None
                fset = {"shape": shapes[shape], "cell": kw["cell"], "rib": kw["rib"], "r": plan["r"],
                        "keepR": plan["keep_r"], "border": plan["border"], "irregular": kw["irregular"],
                        "seed": float(kw["seed"]), "fit": kw["fit"], "ring": plan["ring"], "spokes": sp is not None}
                if sp:
                    fset.update(spokeWidth=sp["width"], spokeLength=sp["length"], spokeCount=float(sp["count"]),
                                spokeAngle=sp["angle"])
                fholes = it.call("planHoles", fR, fset)
                r = plan["r"]
                if len(fholes) != len(plan["holes"]):
                    errs.append(f"hole count {len(fholes)} vs {len(plan['holes'])}")
                else:
                    for k, (mh, fh) in enumerate(zip(plan["holes"], fholes)):
                        e = compare_hole(mh, fh, r, it, recorded, same_pt, rotation)
                        if e:
                            errs.append(f"hole {k}: {e}")
                            break
                        counts["sector" if mh["sector"] else "bite" if mh["bite"] else "core"] += 1
                if errs:
                    fails += 1
                    print(f"FAIL {fname} {shape} {st}: {'; '.join(errs)}")
        print(f"  {fname:<15} ok so far: {n - fails}/{n}")
    print(f"== crosscheck, round rings and wheels: {n - fails}/{n} cases agree; compared point by point: "
          f"{counts['core']} plain holes, {counts['bite']} bitten, {counts['sector']} exact sectors ==")
    return fails


def compare_hole(mh, fh, r, it, recorded, same_pt, rotation):
    pts_same = lambda a, b: len(a) == len(b) and all(same_pt(p, q) for p, q in zip(a, b))
    k0 = 0
    if mh["sector"]:
        fs_ = fh.get("sector")
        if fs_ is None:
            return "sector in the mirror only"
        ms = mh["sector"]
        if not all(same_pt(ms[q], fs_[q]) for q in ("A0", "B0", "B1", "A1", "C")) or \
                abs(ms["phi_i"] - fs_["phiI"]) > 1e-9 or abs(ms["phi_o"] - fs_["phiO"]) > 1e-9:
            return "sector differs"
    elif mh["bite"]:
        fb = fh.get("bite")
        if fb is None:
            return "bite in the mirror only"
        mb = mh["bite"]
        if not pts_same(mb["pts"], fb["pts"]) or not same_pt(mb["C"], fb["C"]) or \
                abs(mb["rho"] - fb["rho"]) > 1e-9 or abs(mb["sweep"] - fb["sweep"]) > 1e-9:
            return "bite differs"
    else:
        if fh.get("sector") is not None or fh.get("bite") is not None:
            return "plain in the mirror only"
        rot = rotation(mh["core"], fh["core"])
        if rot is None:
            return "core differs"
        k0 = rot
    want = hole_outline(mh, r)
    if k0:
        per = 2 if r > 0 else 1
        s0 = (-k0 * per) % len(want)
        want = want[s0:] + want[:s0]
    got = it.call("holeOutline", fh, r)
    norm_ = lambda e: ("line", e["start"], e["end"]) if e["line"] else ("arc", e["start"], e["mid"], e["end"])
    got = [norm_(e) for e in got]
    if len(want) != len(got) or not all(w[0] == g[0] and all(same_pt(p, q) for p, q in zip(w[1:], g[1:]))
                                        for w, g in zip(want, got)):
        return "sketch entities differ"
    if abs(shape_area(mh, r) - it.call("holeArea", fh, r)) > 1e-9:
        return "area differs"
    recorded.clear()
    it.call("drawHole", None, "h", fh, r)
    if [(e[0],) + e[2:] for e in recorded] != [tuple(g) for g in got]:
        return "drawHole calls differ from holeOutline"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub_ = ap.add_subparsers(dest="cmd", required=True)
    ck = sub_.add_parser("check")
    ck.add_argument("--only", choices=["classic", "round"])
    ck.add_argument("--jobs", type=int, default=4)
    cc = sub_.add_parser("crosscheck")
    cc.add_argument("fs", nargs="?", default="projects/leopard-vent/featurescript/leopard_vent.fs")
    sub_.add_parser("fallbacks", help="where round holes get a straight cut, and what it costs")
    pv = sub_.add_parser("preview", help="the round-holes picture in the docs")
    pv.add_argument("out")
    pv.add_argument("--face", default="side_plate")
    p = sub_.add_parser("png")
    p.add_argument("out")
    allfaces = dict(FACES, **ROUND_FACES)
    p.add_argument("--face", default="rect_120x80", choices=sorted(allfaces))
    p.add_argument("--shape", default="QUAD", choices=["QUAD", "TRI", "HEX"])
    p.add_argument("--crop", action="store_true")
    p.add_argument("--irregular", type=float, default=0.7)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--ring", type=float, help="round rings of this width round round holes")
    p.add_argument("--spokes", action="store_true", help="spokes from round holes (needs --ring)")
    p.add_argument("--spoke-count", type=int, default=SPOKE_DEFAULTS["count"])
    p.add_argument("--spoke-width", type=float, default=SPOKE_DEFAULTS["width"])
    p.add_argument("--spoke-length", type=float, default=SPOKE_DEFAULTS["length"])
    p.add_argument("--spoke-angle", type=float, default=SPOKE_DEFAULTS["angle"])
    p.add_argument("--scale", type=float, default=6)
    a = ap.parse_args()
    if a.cmd == "check":
        return run_checks(only=a.only, jobs=a.jobs)
    if a.cmd == "crosscheck":
        return run_crosscheck(a.fs)
    if a.cmd == "fallbacks":
        fallback_report()
        return 0
    if a.cmd == "preview":
        round_preview(a.out, a.face)
        print(a.out)
        return 0
    edges = allfaces[a.face]
    spokes = dict(count=a.spoke_count, width=a.spoke_width, length=a.spoke_length,
                  angle=a.spoke_angle) if a.spokes else None
    plan = plan_face(edges, shape=a.shape, fit=not a.crop, irregular=a.irregular, seed=a.seed,
                     ring=a.ring, spokes=spokes)
    draw(edges, plan, a.out, scale=a.scale)
    print(a.out, len(plan["holes"]), "holes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
