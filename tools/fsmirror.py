#!/usr/bin/env python3
"""
fsmirror -- Python mirror of the LEOPARD VENT FeatureScript geometry.

FeatureScript only runs inside Onshape, so the geometry in
projects/leopard-vent/featurescript/leopard_vent.fs cannot be tested from
here. This file is a line-for-line mirror of its pure-maths half -- cell
generation, face-boundary handling, straight cuts, the exact bands round the
outline and every hole in the face, struts, corner rounding, the min-hole
test -- written so each function maps onto one FeatureScript function of the
same name (snake_case here, camelCase there). What it cannot mirror is the
Onshape plumbing: reading the face, the sketch, the extrude, the boolean.

    fsmirror.py check [--only classic|bands|plate]   every test face, every hole measured
    fsmirror.py crosscheck [--only ...] [--face F]   the .fs file's own maths against this
    fsmirror.py png out.png ...                      draw one face (see --help)
    fsmirror.py preview bands.png plate.png faces.png   the pictures in the docs
    fsmirror.py fallbacks                            how often bands fall back to straight cuts

The check builds holes exactly as the feature would, then measures them with
shapely against the TRUE face outline -- real circles, not the sampled chords
the feature works from: thinnest web between holes, closest approach to the
outline and to every hole in the face, smallest hole, that every hole lies
inside the face, that no piece of the plate is left loose, and that every
sketched outline is exactly the rounded shape it stands for.
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
    kind: str                     # "line" | "arc" | "ell"
    a: tuple = (0, 0)             # line start / arc or ellipse centre
    b: tuple = (0, 0)             # line end
    r: float = 0.0                # arc radius / ellipse semi-axis along x
    t0: float = 0.0               # arc start angle, degrees
    t1: float = 0.0               # arc end angle, degrees (t1 > t0 = counter-clockwise)
    r2: float = 0.0               # ellipse semi-axis along y

    def length(self):
        if self.kind == "line":
            return vlen(sub(self.b, self.a))
        if self.kind == "ell":
            return sum(vlen(sub(self.at((k + 1) / 4000), self.at(k / 4000))) for k in range(4000))
        return abs(math.radians(self.t1 - self.t0)) * self.r

    def at(self, t):              # t in 0..1: arc-length parameter, angle for an ellipse
        if self.kind == "line":
            return add(self.a, mul(sub(self.b, self.a), t))
        ang = math.radians(self.t0 + (self.t1 - self.t0) * t)
        r2 = self.r2 if self.kind == "ell" else self.r
        return (self.a[0] + self.r * math.cos(ang), self.a[1] + r2 * math.sin(ang))


# Points along one edge, and the worst gap between chord and curve. An
# ellipse stands in for every edge that is neither line nor arc -- splines,
# conics -- which the feature samples every SPLINE_STEP with no circle to
# work from. (The test ellipses are round enough that SAG covers the chords.)
def sample_edge(e: Edge):
    if e.kind == "line":
        return [e.at(0), e.at(1)], 0.0
    if e.kind == "ell":
        n = max(2, math.ceil(e.length() / SPLINE_STEP))
        return [e.at(k / n) for k in range(n + 1)], SAG
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
    return [(lp, sag) for lp, sag, _, _ in chain_loops_c(polys)]


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
        idx = [k]
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
            idx.append(nxt)
            loop += polys[nxt][0][:-1]
            sag = max(sag, polys[nxt][1])
            if not same_circle(circ, circ_of(nxt)):
                circ = None
            end = polys[nxt][0][-1]
        loops.append((loop, sag, circ, idx))
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
    inners: list = field(default_factory=list)  # (hull, centre, radius, sag, circle or None, parts or None)
    circles: list = field(default_factory=list) # (centre, radius, inner index) of each round inner loop
    lo: tuple = (0, 0)
    hi: tuple = (0, 0)
    grid: dict = field(default_factory=dict)
    gs: float = 1.0


def build_region(edges, grid_size):
    loops = chain_loops_c([sample_edge(e) + (edge_circle(e),) for e in edges])
    R = Region(gs=grid_size)
    xs = [p[0] for lp, _, _, _ in loops for p in lp]
    ys = [p[1] for lp, _, _, _ in loops for p in lp]
    R.lo, R.hi = (min(xs), min(ys)), (max(xs), max(ys))
    for lp, sag, circ, _ in loops:
        inner = -1
        if signed_area(lp) < 0:
            hull = convex_hull(lp)
            c = centroid(hull)
            R.inners.append((hull, c, max(vlen(sub(q, c)) for q in hull), sag, circ, loop_parts(lp, hull)))
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


# A hole in the face that is not convex -- a curved slot, an L-shaped cutout --
# cannot be kept clear by one straight cut against its convex hull: the hull
# of a curved slot covers the whole region inside the curve, which then stays
# solid. Such a loop is split into triangles instead, and each hole is kept
# clear of each triangle near it, one straight cut apiece. The triangles cover
# the loop exactly, so clearing every one clears the loop. Returns None for a
# convex loop (the hull is then exact) or when the split fails, which leaves
# the hull: conservative, as before.
def loop_parts(lp, hull):
    area = abs(signed_area(lp))
    if abs(signed_area(hull)) - area <= 1e-6 * area:
        return None
    tris = triangulate(list(reversed(lp)))
    if not tris:
        return None
    parts = []
    for t in tris:
        c = centroid(t)
        parts.append((t, c, max(vlen(sub(q, c)) for q in t)))
    return parts


def point_in_triangle(p, a, b, c):
    return cross2(sub(b, a), sub(p, a)) >= 0 and cross2(sub(c, b), sub(p, b)) >= 0 and \
        cross2(sub(a, c), sub(p, c)) >= 0


# Ear clipping of a simple counter-clockwise polygon into counter-clockwise
# triangles. [] if it gets stuck, which only a degenerate polygon can do.
def triangulate(poly):
    pts = []
    n = len(poly)
    for k in range(n):
        a, b, c = poly[k - 1], poly[k], poly[(k + 1) % n]
        if abs(cross2(sub(b, a), sub(c, b))) > 1e-12 * (dot(sub(b, a), sub(b, a)) + dot(sub(c, b), sub(c, b))):
            pts.append(b)
    idx = list(range(len(pts)))
    tris = []
    while len(idx) > 3:
        m = len(idx)
        cut = -1
        for i in range(m):
            a, b, c = pts[idx[i - 1]], pts[idx[i]], pts[idx[(i + 1) % m]]
            if cross2(sub(b, a), sub(c, b)) <= 0:
                continue
            ear = True
            for j in idx:
                if j != idx[i - 1] and j != idx[i] and j != idx[(i + 1) % m] and point_in_triangle(pts[j], a, b, c):
                    ear = False
                    break
            if ear:
                cut = i
                break
        if cut < 0:
            return []
        tris.append([pts[idx[cut - 1]], pts[idx[cut]], pts[idx[(cut + 1) % m]]])
        idx = idx[:cut] + idx[cut + 1:]
    if len(idx) == 3:
        tris.append([pts[k] for k in idx])
    return tris


def seg_seg_dist(a, b, c, d):
    d1, d2 = cross2(sub(b, a), sub(c, a)), cross2(sub(b, a), sub(d, a))
    d3, d4 = cross2(sub(d, c), sub(a, c)), cross2(sub(d, c), sub(b, c))
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0:
        return 0.0
    return min(seg_dist(a, c, d), seg_dist(b, c, d), seg_dist(c, a, b), seg_dist(d, a, b))


# Distance between two convex counter-clockwise polygons; 0 if they overlap.
def poly_dist(A, B):
    if point_in_convex(A, B[0]) or point_in_convex(B, A[0]):
        return 0.0
    best = math.inf
    for i in range(len(A)):
        for j in range(len(B)):
            best = min(best, seg_seg_dist(A[i], A[(i + 1) % len(A)], B[j], B[(j + 1) % len(B)]))
    return best


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


# Clips a core to the face with straight cuts: the border along the outline,
# and one cut per inner loop (one per triangle of a non-convex one), kept
# `inner` clear of it -- the border too, unless given.
def region_clip(core, c, R, reach, border, r, inner_d=None):
    ib = border if inner_d is None else inner_d
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
            hull, _, _, isag, circ, parts = R.inners[inner]
            if parts is None:
                core = inner_clip(core, c, hull, ib + r + isag)
            else:
                core = parts_clip(core, c, parts, reach, ib + r + isag)
        if len(core) < 3:
            return []
    return core


# Keeps a core clear of every triangle of a non-convex inner loop that comes
# within clearance of it, nearest first, one straight cut each. Neighbouring
# triangles share corners, so after one cut the next is often exactly at the
# clearance: the 1e-9 settles that tie the safe way, the same way in any
# arithmetic.
def parts_clip(core, c, parts, reach, clearance):
    near = []
    for k, (t, tc, tr) in enumerate(parts):
        if vlen(sub(tc, c)) < reach + tr + clearance:
            near.append((poly_point_dist(t, c), k))
    near.sort()
    for _, k in near:
        t = parts[k][0]
        if poly_dist(core, t) < clearance + 1e-9:
            core = inner_clip(core, c, t, clearance)
            if len(core) < 3:
                return []
    return core


# ---------------------------------------------------------------- exact bands
#
# With bands on, the material kept round the face's edges is an exact offset
# of them: everything within the border of the outline, and within the band
# width of every hole already in the face -- round, slotted, curved or square.
# Its edge is lines parallel to straight edges, arcs concentric with round
# ones, and arcs round every inside corner. A hole is its cell's core with
# that taken out, so where a hole meets the band it follows it exactly, and
# the ribs between holes run on into the band as they meet it.
#
# In core terms (the hole shrunk by r): E = everything inside the face at
# least D = clearance + r from every edge; a core's holes are core n E, grown
# by r. core n E is worked out cell by cell as an arrangement: every offset
# curve near the core and every core edge, split where they cross, keeping the
# pieces that lie on the boundary of core n E, joined end to end into loops.

TAU = 1e-9          # mm: lengths and distances this close are equal
LINK = 1e-7         # mm: ends this close are one point when pieces are joined into loops
PEPS = 1e-9         # parameter slack at the ends of a piece
MIN_TURN = 0.02     # sine of the smallest corner a hole may turn where an arc meets anything
SMOOTH = 1e-6       # sine below which two pieces meet tangentially, with no corner
NUDGE = 0.05        # mm: how much a core that will not come out cleanly is shrunk to try again


def point_in_convex(poly, p):
    n = len(poly)
    return n >= 3 and all(cross2(sub(poly[(k + 1) % n], poly[k]), sub(p, poly[k])) > 0 for k in range(n))


def poly_point_dist(poly, p):
    """Distance from a point to a convex polygon; 0 inside it."""
    return 0.0 if point_in_convex(poly, p) else vlen(sub(p, nearest_on_loop(poly, p)))


def rot90(u):
    return (-u[1], u[0])


def ang_dir(u0, u1, d):
    """Angle turned going from direction u0 to u1 in direction d (+1
    counter-clockwise, -1 clockwise), in [0, 2 pi)."""
    a = math.atan2(cross2(u0, u1), dot(u0, u1))
    if d > 0:
        return a if a >= 0 else a + 2 * math.pi
    return -a if a <= 0 else 2 * math.pi - a


# A piece is a line {kind L, a, b} or an arc {kind A, c, rho, a, b, dir, sweep}
# from a to b about c: counter-clockwise for dir 1, clockwise for -1, through
# sweep radians (up to 2 pi, a whole circle).

def line_piece(a, b):
    return {"kind": "L", "a": a, "b": b}


def arc_piece(c, rho, a, b, d, sweep):
    return {"kind": "A", "c": c, "rho": rho, "a": a, "b": b, "dir": d, "sweep": sweep}


def piece_at(p, t):
    if p["kind"] == "L":
        return add(p["a"], mul(sub(p["b"], p["a"]), t))
    u = sub(p["a"], p["c"])
    th = p["dir"] * p["sweep"] * t
    ct, st = math.cos(th), math.sin(th)
    return add(p["c"], (u[0] * ct - u[1] * st, u[0] * st + u[1] * ct))


def piece_len(p):
    return vlen(sub(p["b"], p["a"])) if p["kind"] == "L" else p["rho"] * p["sweep"]


def arc_param(p, X):
    """Where X, on p's circle, falls along arc p, as a fraction -- or None."""
    phi = ang_dir(unit(sub(p["a"], p["c"])), unit(sub(X, p["c"])), p["dir"])
    tol = TAU / max(p["rho"], TAU)
    if phi <= p["sweep"] + tol:
        return min(phi, p["sweep"]) / p["sweep"]
    if phi >= 2 * math.pi - tol:
        return 0.0
    return None


def tangent_at(p, X):
    if p["kind"] == "L":
        return unit(sub(p["b"], p["a"]))
    return mul(rot90(unit(sub(X, p["c"]))), p["dir"])


def normal_at(p, X):
    """The normal to the right of the direction of travel: outward, on a loop
    that keeps its inside on the left."""
    if p["kind"] == "L":
        t = unit(sub(p["b"], p["a"]))
        return (t[1], -t[0])
    return mul(unit(sub(X, p["c"])), p["dir"])


def piece_box(p):
    pts = [p["a"], p["b"]]
    if p["kind"] == "A":
        for u in ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)):
            if ang_dir(unit(sub(p["a"], p["c"])), u, p["dir"]) <= p["sweep"]:
                pts.append(add(p["c"], mul(u, p["rho"])))
    return (min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts))


def piece_dist(p, x):
    if p["kind"] == "L":
        return seg_dist(x, p["a"], p["b"])
    v = sub(x, p["c"])
    L = vlen(v)
    if L > 1e-12 and ang_dir(unit(sub(p["a"], p["c"])), mul(v, 1 / L), p["dir"]) <= p["sweep"]:
        return abs(L - p["rho"])
    return min(vlen(sub(x, p["a"])), vlen(sub(x, p["b"])))


def sub_piece(p, t0, t1, X0, X1):
    if p["kind"] == "L":
        return line_piece(X0, X1)
    return arc_piece(p["c"], p["rho"], X0, X1, p["dir"], p["sweep"] * (t1 - t0))


def clamp01(t):
    return min(1.0, max(0.0, t))


# Where two pieces meet: [(t on p, t on q, point)], ends included. Two pieces
# on one line or one circle meet where they overlap, at its two ends.

def isect_ll(p, q):
    a, d1 = p["a"], sub(p["b"], p["a"])
    c, d2 = q["a"], sub(q["b"], q["a"])
    L1, L2 = vlen(d1), vlen(d2)
    if L1 <= TAU or L2 <= TAU:
        return []
    den = cross2(d1, d2)
    if abs(den) <= 1e-12 * L1 * L2:
        if abs(cross2(d1, sub(c, a))) / L1 > TAU:
            return []
        out = []
        for X, u in ((q["a"], 0.0), (q["b"], 1.0)):
            t = dot(sub(X, a), d1) / (L1 * L1)
            if -PEPS <= t <= 1 + PEPS:
                out.append((clamp01(t), u, X))
        for X, t in ((p["a"], 0.0), (p["b"], 1.0)):
            u = dot(sub(X, c), d2) / (L2 * L2)
            if -PEPS <= u <= 1 + PEPS:
                out.append((t, clamp01(u), X))
        return out
    t = cross2(sub(c, a), d2) / den
    u = cross2(sub(c, a), d1) / den
    if -PEPS <= t <= 1 + PEPS and -PEPS <= u <= 1 + PEPS:
        t = clamp01(t)
        return [(t, clamp01(u), add(a, mul(d1, t)))]
    return []


def isect_la(p, q):
    """A line and an arc. One that comes within TAU of just touching the
    circle is taken not to meet it at all: a touch splits nothing, and a
    crossing that shallow is lost in rounding -- worked out either way, it
    leaves slivers of piece a fraction of a micrometre long, on one side of
    the tangent point or the other."""
    a, d = p["a"], sub(p["b"], p["a"])
    A = dot(d, d)
    if A <= TAU * TAU:
        return []
    L = math.sqrt(A)
    f = sub(q["c"], a)
    h = abs(cross2(d, f)) / L
    if h >= q["rho"] - TAU:
        return []
    t0 = dot(f, d) / A
    w = math.sqrt(q["rho"] * q["rho"] - h * h) / L
    out = []
    for t in (t0 - w, t0 + w):
        if -PEPS <= t <= 1 + PEPS:
            t = clamp01(t)
            X = add(a, mul(d, t))
            u = arc_param(q, X)
            if u is not None:
                out.append((t, u, X))
    return out


def isect_aa(p, q):
    v = sub(q["c"], p["c"])
    d = vlen(v)
    r1, r2 = p["rho"], q["rho"]
    if d <= TAU:
        if abs(r1 - r2) > TAU:
            return []
        out = []
        for X, u in ((q["a"], 0.0), (q["b"], 1.0)):
            t = arc_param(p, X)
            if t is not None:
                out.append((t, u, X))
        for X, t in ((p["a"], 0.0), (p["b"], 1.0)):
            u = arc_param(q, X)
            if u is not None:
                out.append((t, u, X))
        return out
    if d >= r1 + r2 - TAU or d <= abs(r1 - r2) + TAU:
        return []                       # apart, one inside the other, or touching: as for a line
    al = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - al * al))
    P = add(p["c"], mul(v, al / d))
    w = mul(rot90(v), 1 / d)
    pts = [add(P, mul(w, h)), sub(P, mul(w, h))]
    out = []
    for X in pts:
        t, u = arc_param(p, X), arc_param(q, X)
        if t is not None and u is not None:
            out.append((t, u, X))
    return out


def isect(p, q):
    if p["kind"] == "L":
        return isect_ll(p, q) if q["kind"] == "L" else isect_la(p, q)
    if q["kind"] == "L":
        return [(t, u, X) for u, t, X in isect_la(q, p)]
    return isect_aa(p, q)


# ---------------------------------------------------------------- the face's edges, offset

def edge_pieces(poly):
    """The exact pieces of one sampled edge: one arc for an edge on a circle,
    one line for a straight edge, a line per chord for anything else."""
    pts, circ = poly[0], poly[2]
    if circ is not None:
        c, R = circ
        a, b = pts[0], pts[-1]
        d = 1 if cross2(sub(pts[0], c), sub(pts[1], c)) > 0 else -1
        sw = ang_dir(unit(sub(a, c)), unit(sub(b, c)), d)
        if sw <= 1e-9:
            sw = 2 * math.pi
        return [arc_piece(c, R, a, b, d, sw)]
    return [line_piece(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]


def face_loops(polys, outer_d, inner_d):
    """Each loop of the face: its pieces (face on their left), and its
    clearance -- outer_d for the outline, inner_d for a hole, plus the chord
    allowance where the loop has a sampled curve."""
    out = []
    for lp, sag, _, idx in chain_loops_c(polys):
        pieces = []
        csag = 0.0
        for k in idx:
            pieces += edge_pieces(polys[k])
            if polys[k][2] is None and len(polys[k][0]) > 2:
                csag = max(csag, polys[k][1])
        D = (outer_d if signed_area(lp) > 0 else inner_d) + csag
        out.append(dict(pieces=pieces, D=D))
    return out


def offset_loop(lp, extra):
    """The raw offset of one loop: each piece moved its clearance (+ extra) to
    its left, and an arc of that radius round each inside corner -- which
    includes every joint where a sampled curve bends away from the face, so
    the offset of a sampled curve is exact for its chords, a chain of lines
    and short arcs that meet smoothly. At an outside corner neighbours cross;
    the arrangement trims them."""
    D = lp["D"] + extra
    P = lp["pieces"]
    n = len(P)
    out = []
    for p in P:
        if p["kind"] == "L":
            nv = rot90(unit(sub(p["b"], p["a"])))
            out.append(line_piece(add(p["a"], mul(nv, D)), add(p["b"], mul(nv, D))))
        else:
            rho = p["rho"] - p["dir"] * D
            if rho <= 1e-6:
                continue                  # a convex arc tighter than D: its neighbours meet instead
            na = mul(unit(sub(p["a"], p["c"])), -p["dir"])
            nb = mul(unit(sub(p["b"], p["c"])), -p["dir"])
            out.append(arc_piece(p["c"], rho, add(p["a"], mul(na, D)), add(p["b"], mul(nb, D)), p["dir"], p["sweep"]))
    for i in range(n):
        p, q = P[i], P[(i + 1) % n]
        t_in, t_out = tangent_at(p, p["b"]), tangent_at(q, q["a"])
        s, cs = cross2(t_in, t_out), dot(t_in, t_out)
        if s < -SMOOTH or (abs(s) <= SMOOTH and cs < 0):
            v = p["b"]
            n_in, n_out = rot90(t_in), rot90(t_out)
            out.append(arc_piece(v, D, add(v, mul(n_in, D)), add(v, mul(n_out, D)), -1, ang_dir(n_in, n_out, -1)))
    for p in out:
        p["box"] = piece_box(p)
    return out


def grid_of(boxes, gs):
    """Each box's index, filed under every grid square the box touches."""
    grid = {}
    for idx, box in enumerate(boxes):
        for gx in range(math.floor(box[0] / gs), math.floor(box[2] / gs) + 1):
            for gy in range(math.floor(box[1] / gs), math.floor(box[3] / gs) + 1):
                grid.setdefault((gx, gy), []).append(idx)
    return grid


def grid_find(grid, gs, box):
    found = set()
    for gx in range(math.floor(box[0] / gs), math.floor(box[2] / gs) + 1):
        for gy in range(math.floor(box[1] / gs), math.floor(box[3] / gs) + 1):
            found.update(grid.get((gx, gy), []))
    return sorted(found)


def band_context(polys, R, outer_d, inner_d, k):
    """Everything about one face that the bands need: its edges as exact
    pieces with their clearances, and the raw offsets at D and at D + k (for
    the smallest-hole test), each filed in a grid."""
    loops = face_loops(polys, outer_d, inner_d)
    feats = []
    for lp in loops:
        for p in lp["pieces"]:
            f = dict(p)
            f["D"] = lp["D"]
            b, g = piece_box(p), lp["D"] + k
            f["box"] = (b[0] - g, b[1] - g, b[2] + g, b[3] + g)
            feats.append(f)
    ctx = dict(R=R, feats=feats, fgrid=grid_of([f["box"] for f in feats], R.gs), raws={}, rgrid={}, k=k)
    for e in (0.0, k):
        rs = [p for lp in loops for p in offset_loop(lp, e)]
        ctx["raws"][e], ctx["rgrid"][e] = rs, grid_of([p["box"] for p in rs], R.gs)
    return ctx


def in_box(b, x):
    return b[0] <= x[0] <= b[2] and b[1] <= x[1] <= b[3]


def boxes_meet(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def band_valid(ctx, x, extra):
    """Is x in E: inside the face, and at least its clearance from every edge?"""
    for i in ctx["fgrid"].get((math.floor(x[0] / ctx["R"].gs), math.floor(x[1] / ctx["R"].gs)), []):
        f = ctx["feats"][i]
        if in_box(f["box"], x) and piece_dist(f, x) < f["D"] + extra - TAU:
            return False
    return inside_region(ctx["R"], x)


def strictly_inside(core, x):
    n = len(core)
    for k in range(n):
        e = sub(core[(k + 1) % n], core[k])
        if cross2(e, sub(x, core[k])) <= TAU * vlen(e):
            return False
    return True


def loop_area(loop):
    s = 0.0
    for p in loop:
        s += cross2(p["a"], p["b"]) / 2
        if p["kind"] == "A":
            sg = p["dir"] * p["sweep"]
            s += p["rho"] * p["rho"] / 2 * (sg - math.sin(sg))
    return s


def band_clip(core, ctx, extra):
    """core n E: ("plain",) when all of the core is in E, ("empty",) when
    none is, ("fail", why) when it cannot be worked out cleanly, or ("ok",
    components, holes): counter-clockwise loops of pieces, and clockwise loops
    of anything inside them."""
    n = len(core)
    box = (min(q[0] for q in core) - TAU, min(q[1] for q in core) - TAU,
           max(q[0] for q in core) + TAU, max(q[1] for q in core) + TAU)
    raws = ctx["raws"][extra]
    sel = [raws[i] for i in grid_find(ctx["rgrid"][extra], ctx["R"].gs, box) if boxes_meet(raws[i]["box"], box)]
    if not sel:
        return ("plain",) if band_valid(ctx, centroid(core), extra) else ("empty",)
    allp = [line_piece(core[k], core[(k + 1) % n]) for k in range(n)] + sel
    ev = [[] for _ in allp]
    for i in range(len(allp)):
        for j in range(max(i + 1, n), len(allp)):
            for ti, tj, X in isect(allp[i], allp[j]):
                ev[i].append((ti, X))
                ev[j].append((tj, X))
    kept = []
    for i, p in enumerate(allp):
        evs = sorted([(0.0, p["a"])] + ev[i] + [(1.0, p["b"])], key=lambda e: e[0])
        L = piece_len(p)
        for k in range(len(evs) - 1):
            (t0, X0), (t1, X1) = evs[k], evs[k + 1]
            if (t1 - t0) * L <= TAU:
                continue
            m = piece_at(p, (t0 + t1) / 2)
            if i >= n and not strictly_inside(core, m):
                continue
            if band_valid(ctx, m, extra):
                kept.append(sub_piece(p, t0, t1, X0, X1))
    if not kept:
        return ("empty",)
    m = len(kept)
    nxt = []
    for i in range(m):
        cands = [j for j in range(m) if vlen(sub(kept[j]["a"], kept[i]["b"])) <= LINK]
        if len(cands) != 1:
            return ("fail", "junction")
        nxt.append(cands[0])
    if sorted(nxt) != list(range(m)):
        return ("fail", "junction")
    seen = [False] * m
    comps, holes = [], []
    for i in range(m):
        if seen[i]:
            continue
        loop = []
        j = i
        while not seen[j]:
            seen[j] = True
            loop.append(kept[j])
            j = nxt[j]
        if j != i:
            return ("fail", "junction")
        for k in range(len(loop)):              # one point at each junction
            loop[(k + 1) % len(loop)]["a"] = loop[k]["b"]
        (comps if loop_area(loop) > 0 else holes).append(loop)
    return ("ok", comps, holes)


# ---------------------------------------------------------------- loops

def loop_perimeter(loop):
    return sum(piece_len(p) for p in loop)


def split_big_arcs(loop):
    """Arcs over 0.9 of half a turn are drawn as two, so no arc's ends meet."""
    out = []
    for p in loop:
        if p["kind"] == "A" and p["sweep"] > 0.9 * math.pi:
            m = piece_at(p, 0.5)
            out.append(arc_piece(p["c"], p["rho"], p["a"], m, p["dir"], p["sweep"] / 2))
            out.append(arc_piece(p["c"], p["rho"], m, p["b"], p["dir"], p["sweep"] / 2))
        else:
            out.append(p)
    return out


def smooth_join(n1, n2):
    return abs(cross2(n1, n2)) <= SMOOTH and dot(n1, n2) > 0


def loop_ok(loop):
    """Every piece long enough to draw; every corner turning enough to round,
    or not at all where two pieces meet tangentially."""
    for k, p in enumerate(loop):
        if piece_len(p) < TINY_EDGE:
            return False
        q = loop[(k + 1) % len(loop)]
        n1, n2 = normal_at(p, p["b"]), normal_at(q, q["a"])
        if smooth_join(n1, n2):
            continue
        if cross2(n1, n2) < (TINY_TURN if p["kind"] == "L" and q["kind"] == "L" else MIN_TURN):
            return False
    return True


def loop_outline(loop, r):
    """Sketch entities for a loop grown by r: each line moved out by r, each
    arc's radius grown (inside it) or shrunk (outside it) by r, about the same
    centre, and an arc of radius r round every corner."""
    m = len(loop)
    if r <= 0:
        return [("line", p["a"], p["b"]) if p["kind"] == "L" else ("arc", p["a"], piece_at(p, 0.5), p["b"])
                for p in loop]
    starts = [add(p["a"], mul(normal_at(p, p["a"]), r)) for p in loop]
    ends = [add(p["b"], mul(normal_at(p, p["b"]), r)) for p in loop]
    for k in range(m):
        q = loop[(k + 1) % m]
        if smooth_join(normal_at(loop[k], loop[k]["b"]), normal_at(q, q["a"])):
            starts[(k + 1) % m] = ends[k]
    ents = []
    for k, p in enumerate(loop):
        if p["kind"] == "L":
            ents.append(("line", starts[k], ends[k]))
        else:
            mid = piece_at(p, 0.5)
            ents.append(("arc", starts[k], add(mid, mul(normal_at(p, mid), r)), ends[k]))
        q = loop[(k + 1) % m]
        n1, n2 = normal_at(p, p["b"]), normal_at(q, q["a"])
        if not smooth_join(n1, n2):
            ents.append(("arc", ends[k], add(p["b"], mul(unit(add(n1, n2)), r)), starts[(k + 1) % m]))
    return ents


def loop_hole_area(loop, r):
    """Steiner's formula: the loop's area, plus perimeter x r, plus pi r^2."""
    return loop_area(loop) + loop_perimeter(loop) * r + math.pi * r * r


def arc_segment_holds(p, x):
    """Is x in the circular segment between arc p (under half a turn) and its chord?"""
    if vlen(sub(x, p["c"])) >= p["rho"]:
        return False
    side = cross2(sub(p["b"], p["a"]), sub(x, p["a"]))
    return side < 0 if p["dir"] > 0 else side > 0


def winding(loop, x):
    w = 0.0
    for p in loop:
        u, v = sub(p["a"], x), sub(p["b"], x)
        w += math.atan2(cross2(u, v), dot(u, v))
        if p["kind"] == "A" and arc_segment_holds(p, x):
            w += 2 * math.pi * p["dir"]
    return fs_round(w / (2 * math.pi))


def piece_piece_dist(p, q):
    best = min(piece_dist(q, p["a"]), piece_dist(q, p["b"]), piece_dist(p, q["a"]), piece_dist(p, q["b"]))
    for s, t in ((p, q), (q, p)):
        if s["kind"] != "A":
            continue
        if t["kind"] == "L":
            nv = rot90(unit(sub(t["b"], t["a"])))
            dirs = [nv, mul(nv, -1)]
        else:
            w = sub(t["c"], s["c"])
            dirs = [unit(w), mul(unit(w), -1)] if vlen(w) > TAU else []
        for u in dirs:
            Y = add(s["c"], mul(u, s["rho"]))
            if arc_param(s, Y) is not None:
                best = min(best, piece_dist(t, Y))
    return best


def loop_points(loop):
    out = []
    for p in loop:
        k = 8 if p["kind"] == "L" else max(8, math.ceil(p["sweep"] * 16))
        out += [piece_at(p, j / k) for j in range(k)]
    return out


# ---------------------------------------------------------------- holes from bands

def straight_core(core, ctx, r, border, ring, keep_r):
    """The fallback, for the rare core the arrangement cannot settle cleanly:
    the old straight cuts, convex and always drawable, kept the band width off
    every hole -- conservative, so never less material."""
    c = centroid(core)
    reach = max(vlen(sub(q, c)) for q in core) + max(border, ring) + r + SAG + 1e-6
    k = region_clip(core, c, ctx["R"], reach, border, r, inner_d=ring)
    k = tidy(ccw(k)) if k else []
    if not k or (keep_r > r and not inset_convex(k, keep_r - r)):
        return []
    return [{"core": k, "cut": True}]


def retry(core, ctx, rib, r, border, ring, keep_r, depth, nudged):
    """A core whose bands cannot be drawn cleanly -- a piece too short to
    sketch, a corner too shallow to round, ends that do not meet -- is tried
    once more shrunk by NUDGE, which moves every crossing; then it gets the
    straight cuts. Either way the hole only gets smaller."""
    if not nudged:
        k = inset_convex(core, NUDGE)
        if k:
            return band_holes(k, ctx, rib, r, border, ring, keep_r, depth, True)
    return straight_core(core, ctx, r, border, ring, keep_r)


def band_holes(core, ctx, rib, r, border, ring, keep_r, depth=0, nudged=False):
    """The holes one convex core makes against the bands: [{"core": polygon}]
    where nothing touches it, or [{"loop": pieces}, ...]."""
    core = tidy(ccw(core))
    if not core:
        return []
    k = ctx["k"]
    res = band_clip(core, ctx, 0.0)
    if res[0] == "empty":
        return []
    if res[0] == "plain":
        return [{"core": core}] if k <= 0 or inset_convex(core, k) else []
    if res[0] == "fail":
        return retry(core, ctx, rib, r, border, ring, keep_r, depth, nudged)
    comps, holes = res[1], res[2]
    d = rib / 2 + r
    if holes:
        # A hole wrapped round something -- a bolt hole and its band -- would
        # leave it loose: split the core by a rib through it instead.
        if depth >= 2:
            return straight_core(core, ctx, r, border, ring, keep_r)
        pts = [p["a"] for p in holes[0]]
        X = centroid(pts) if len(pts) > 2 or holes[0][0]["kind"] != "A" else holes[0][0]["c"]
        return best_split(core, X, [math.radians(30 * j) for j in range(6)], ctx, rib, r, border, ring,
                          keep_r, depth)
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            if min(piece_piece_dist(p, q) for p in comps[i] for q in comps[j]) < 2 * d - TAU:
                # Two pieces of one cell closer than a rib: split between them.
                if depth >= 2:
                    return straight_core(core, ctx, r, border, ring, keep_r)
                pa, pb = loop_points(comps[i]), loop_points(comps[j])
                best, x, y = math.inf, pa[0], pb[0]
                for s in pa:
                    for t in pb:
                        if vlen(sub(s, t)) < best:
                            best, x, y = vlen(sub(s, t)), s, t
                u = unit(sub(y, x)) if vlen(sub(y, x)) > TAU else (1.0, 0.0)
                return best_split(core, mul(add(x, y), 0.5), [math.atan2(-u[0], u[1])], ctx, rib, r, border,
                                  ring, keep_r, depth)
    comps = [split_big_arcs(c) for c in comps]
    if not all(loop_ok(c) for c in comps):
        return retry(core, ctx, rib, r, border, ring, keep_r, depth, nudged)
    if k <= 0:
        return [{"loop": c} for c in comps]
    # Smallest hole: a circle of keep_r fits in a piece iff the core shrunk by
    # k = keep_r - r, less the bands grown by k, has some of it in that piece.
    inner = inset_convex(core, k)
    inner = tidy(ccw(inner)) if inner else []
    if not inner:
        return []
    res2 = band_clip(inner, ctx, k)
    if res2[0] in ("empty", "fail"):
        return []
    probes = [centroid(inner)] if res2[0] == "plain" else [piece_at(L[0], 0.5) for L in res2[1]]
    return [{"loop": c} for c in comps if any(winding(c, x) != 0 for x in probes)]


def best_split(core, X, angles, ctx, rib, r, border, ring, keep_r, depth):
    d = rib / 2 + r
    best, best_area = [], -1.0
    for th in angles:
        nv = rot90((math.cos(th), math.sin(th)))
        holes = []
        for piece in (clip_half(core, add(X, mul(nv, d)), mul(nv, -1)), clip_half(core, sub(X, mul(nv, d)), nv)):
            if len(piece) >= 3:
                holes += band_holes(piece, ctx, rib, r, border, ring, keep_r, depth + 1)
        area = sum(shape_area(h, r) for h in holes)
        if area > best_area + 1e-9:
            best, best_area = holes, area
    return best


# ---------------------------------------------------------------- struts
#
# With 6-sided cells, a round hole of at least min_d gets a ring of Voronoi
# seeds round it, and the lattice seeds inside that ring go. Cells of seeds in
# a ring are wedges, so the ribs between them -- ordinary cell edges, one rib
# wide like every other -- run straight out from the hole's band and join the
# web where the ring meets the rest of the pattern.

def rosettes(circles, ring, p, min_d, s):
    """The round holes that get a ring of cells: (centre, Rc, ring radius,
    clear radius, seeds, first angle) each. Big holes first; a hole whose
    ring would overlap a bigger one's by much goes without."""
    cand = []
    for i, (C, Rc, _) in enumerate(circles):
        if 2 * Rc >= min_d:
            Rs = Rc + ring + 0.45 * p
            cand.append((i, C, Rc, Rs, Rs + 0.75 * p))
    cand.sort(key=lambda t: (-t[2], t[0]))
    out = []
    for i, C, Rc, Rs, Rcl in cand:
        if all(vlen(sub(C, o[0])) >= 0.8 * (Rcl + o[3]) for o in out):
            out.append((C, Rc, Rs, Rcl, max(5, fs_round(2 * math.pi * Rs / p)), 360 * hash01(i * 31 + 7, s)))
    return out


def voronoi_seeds(seeds, lo, hi, rc0):
    """Voronoi cells of any seeds, each clipped to the rectangle [lo, hi]. A
    cell is right once every seed within twice its radius has cut it, so each
    starts from the seeds within 2 rc0 and widens the search until its own
    radius says nothing further can reach it. The rectangle keeps every cell
    bounded -- a seed on the edge of the pattern has an open cell otherwise --
    and the seeds are filed in a grid, so each only looks at those near it."""
    g = 2 * rc0
    grid = grid_of([(q[0], q[1], q[0], q[1]) for q in seeds], g)
    out = []
    for i, sd in enumerate(seeds):
        Rn = 2 * rc0
        while True:
            h = Rn / 2
            b0 = (max(lo[0], sd[0] - h), max(lo[1], sd[1] - h))
            b1 = (min(hi[0], sd[0] + h), min(hi[1], sd[1] + h))
            c = []
            if b1[0] > b0[0] and b1[1] > b0[1]:
                near = grid_find(grid, g, (sd[0] - Rn, sd[1] - Rn, sd[0] + Rn, sd[1] + Rn))
                c = clip_all([b0, (b1[0], b0[1]), b1, (b0[0], b1[1])], sd,
                             [seeds[j] for j in near if j != i and vlen(sub(seeds[j], sd)) < Rn])
            if len(c) < 3:
                break
            reach = 2 * max(vlen(sub(q, sd)) for q in c)
            if reach <= Rn * (1 + 1e-9):
                break
            Rn = reach * (1 + 1e-6)
        c = [q for k, q in enumerate(c) if vlen(sub(q, c[k - 1])) > 1e-9]
        if len(c) >= 3:
            out.append(c)
    return out


def hex_seeds_fit(lo, hi, cell, irregular, s):
    """The seeds voronoi_fit uses, and its cell radius and pitch."""
    p0 = cell * PITCH["HEX"]
    W = sub(hi, lo)
    nx = max(1, fs_round(W[0] / p0))
    ny = max(1, fs_round(W[1] / (p0 * math.sqrt(3) / 2)))
    px, h = W[0] / nx, W[1] / ny
    a = min(1, max(0, irregular)) * JITTER["HEX"] * min(px, 2 * h / math.sqrt(3))
    S = []
    for j in range(ny):
        for k, x in enumerate(hex_row_x(j, nx)):
            d = jitter(k, j, a, s)
            wall = x == 0 or x == nx
            S.append((lo[0] + x * px + (0 if wall else d[0]), lo[1] + (j + 0.5) * h + d[1]))
    rc = max((h * h + px * px / 4) / (2 * h), math.hypot(px, h) / 2) + 2 * a + 1e-6
    return S, rc, px


def strut_cells(lo, hi, cell, irregular, s, circles, ring, min_d, fit):
    """6-sided cells with a ring of cells round each big round hole; None
    where no hole gets one (the ordinary cells are then used). Fitted cells
    are clipped to lo..hi, as voronoi_fit's are; cropped ones to that grown by
    a cell's reach, which keeps them bounded without touching any hole -- a
    cut that far out, shrunk by half a rib and the corner radius, still lies
    outside the face."""
    if fit:
        S, rc, p = hex_seeds_fit(lo, hi, cell, irregular, s)
        b0, b1 = lo, hi
    else:
        p = cell * PITCH["HEX"]
        h = p * math.sqrt(3) / 2
        a = min(1, max(0, irregular)) * JITTER["HEX"] * p
        o, nx, ny = lattice_frame(lo, hi, p, h)
        V = lattice(o, p, nx, ny, True, a, s)
        rc = p / math.sqrt(3) + a + 1e-6
        S = [V[i][j] for i in range(nx + 1) for j in range(ny + 1)
             if lo[0] - rc < V[i][j][0] < hi[0] + rc and lo[1] - rc < V[i][j][1] < hi[1] + rc]
        b0, b1 = sub(lo, (rc, rc)), add(hi, (rc, rc))
    ros = rosettes(circles, ring, p, min_d, s)
    if not ros:
        return None, ros
    seeds = [q for q in S if all(vlen(sub(q, o[0])) >= o[3] for o in ros)]
    for C, Rc, Rs, Rcl, n, t0 in ros:
        for k in range(n):
            t = math.radians(t0 + 360 * k / n)
            seeds.append(add(C, (Rs * math.cos(t), Rs * math.sin(t))))
    return voronoi_seeds(seeds, b0, b1, rc), ros


# ---------------------------------------------------------------- one face

def cell_holes(cell, R, rib, r, border, keep_r):
    """The holes one cell makes with straight cuts (bands off): none or one."""
    c = centroid(cell)
    core = inset_convex(cell, rib / 2 + r)
    if not core:
        return []
    cell_r = max(vlen(sub(q, c)) for q in cell)
    core = region_clip(core, c, R, cell_r + border + r + SAG + 1e-6, border, r)
    if not core:
        return []
    core = tidy(ccw(core))
    if not core or (keep_r > r and not inset_convex(core, keep_r - r)):
        return []
    return [{"core": core}]


def plan_face(edges, shape="QUAD", cell=14.0, rib=2.0, border=5.0, irregular=0.7,
              corner=1.0, min_hole=4.0, seed=1, fit=True, ring=None, struts=False, min_d=10.0):
    """Everything the feature computes for one face, before it touches Onshape.
    ring: None for straight cuts (the first version); else exact bands, ring
    wide round every hole in the face. struts: rings of cells round round
    holes from min_d across (6-sided cells only)."""
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
                circles=R.circles, rosettes=[])
    cells = None
    if fit:
        ins = bw - rib / 2
        lo, hi = add(R.lo, (ins, ins)), sub(R.hi, (ins, ins))
    else:
        lo, hi = R.lo, R.hi
    if fit and (hi[0] <= lo[0] or hi[1] <= lo[1]):
        cells = []
    elif ring is not None and struts and shape == "HEX":
        cells, plan["rosettes"] = strut_cells(lo, hi, cell, irregular, seed, R.circles, ring, min_d, fit)
    if cells is None:
        cells = fit_cells(shape, lo, hi, cell, irregular, seed) if fit else \
            crop_cells(shape, lo, hi, cell, irregular, seed)
    holes = []
    if ring is None:
        for c in cells:
            holes += cell_holes(c, R, rib, r, bw, keep_r)
    else:
        polys = [sample_edge(e) + (edge_circle(e),) for e in edges]
        ctx = band_context(polys, R, bw + r, ring + r, max(0.0, keep_r - r))
        for c in cells:
            core = inset_convex(c, rib / 2 + r)
            if core:
                holes += band_holes(core, ctx, rib, r, bw, ring, keep_r)
    plan["holes"] = holes
    plan["cores"] = [h["core"] for h in holes if "core" in h]
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


def hole_area(core, r):
    per = sum(vlen(sub(core[(k + 1) % len(core)], core[k])) for k in range(len(core)))
    return abs(signed_area(core)) + per * r + math.pi * r * r


def hole_outline(h, r):
    return outline(h["core"], r) if "core" in h else loop_outline(h["loop"], r)


def shape_area(h, r):
    return hole_area(h["core"], r) if "core" in h else loop_hole_area(h["loop"], r)


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


def loop_of(pts, hole=False):
    """Straight-sided loop through pts, given counter-clockwise; a hole runs the other way."""
    pts = list(reversed(pts)) if hole else list(pts)
    return [Edge("line", pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def arc_slot(c, r1, r2, a0, a1):
    """A curved slot, an inner loop: the band between radii r1 and r2 about c
    from angle a0 to a1 (degrees), with round ends."""
    rm, w = (r1 + r2) / 2, (r2 - r1) / 2
    p0 = (c[0] + rm * math.cos(math.radians(a0)), c[1] + rm * math.sin(math.radians(a0)))
    p1 = (c[0] + rm * math.cos(math.radians(a1)), c[1] + rm * math.sin(math.radians(a1)))
    return [Edge("arc", c, r=r2, t0=a1, t1=a0), Edge("arc", p0, r=w, t0=a0, t1=a0 - 180),
            Edge("arc", c, r=r1, t0=a0, t1=a1), Edge("arc", p1, r=w, t0=a1 + 180, t1=a1)]


def slots_plate():
    # Holes that are not convex: a curved slot, whose inside must not be left
    # solid, and an L-shaped cutout.
    return (rect(0, 0, 160, 120) + arc_slot((60, 50), 40, 46, -60, 80)
            + loop_of([(110, 70), (145, 70), (145, 80), (120, 80), (120, 105), (110, 105)], hole=True))


def robot_plate():
    # Modelled on a real FRC side plate: an odd outline with a notch, ~90
    # bolt holes in rows, a 40 mm bore, a row of 18 mm holes, four 14 mm
    # holes, a curved slot, a rectangular and a rounded cutout. 630 x 420 mm.
    px = lambda x, y: (round(x / 2.4, 2), round((1100 - y) / 2.4, 2))
    outer = [px(130, 950), px(165, 200), px(245, 20), px(450, 100), px(560, 60), px(690, 70),
             px(890, 190), px(895, 290), px(1520, 580), px(1525, 700), px(1300, 740),
             px(1290, 1025), px(920, 1000), px(925, 845), px(750, 845), px(745, 800),
             px(510, 800), px(495, 975)]
    edges = loop_of(list(reversed(outer)))
    circ = lambda c, d: circle_loop(c[0], c[1], d / 2, hole=True)
    edges += circ(px(230, 650), 40)
    for q in [(810, 430), (870, 455), (945, 490), (1020, 520), (1080, 545), (1165, 590), (1240, 620)]:
        edges += circ(px(*q), 18)
    for q in [(580, 265), (265, 800), (400, 855), (1085, 935)]:
        edges += circ(px(*q), 14)
    edges += arc_slot(px(560, 300), 77, 83, -74, 36)
    edges += loop_of([px(805, 345), px(870, 345), px(870, 210), px(805, 210)], hole=True)
    edges += slot_loop(140, 180, px(0, 690)[1], 25)
    rows = [((150, 930), (185, 230), 18), ((260, 60), (440, 130), 5), ((700, 110), (860, 200), 4),
            ((930, 330), (1480, 600), 14), ((190, 937), (470, 955), 7), ((940, 985), (1270, 1005), 8),
            ((1495, 610), (1495, 680), 3), ((300, 380), (300, 600), 5), ((700, 500), (700, 760), 6),
            ((1268, 660), (1262, 950), 7)]
    for a, b, n in rows:
        for k in range(n):
            t = k / (n - 1)
            q = px(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            edges += circle_loop(q[0], q[1], 2.55, hole=True)
    return edges


def ellipses():
    # Edges that are neither line nor arc, sampled as a spline would be: a
    # domed top, an oval hole and an oval notch in the bottom edge -- a
    # sampled curve the face lies inside, one round a hole, and one that
    # bulges into the face.
    return [Edge("line", (0, 0), (100, 0)), Edge("ell", (115, 0), r=15, r2=10, t0=180, t1=0),
            Edge("line", (130, 0), (160, 0)), Edge("line", (160, 0), (160, 60)),
            Edge("ell", (80, 60), r=80, r2=35, t0=0, t1=180), Edge("line", (0, 60), (0, 0)),
            Edge("ell", (55, 40), r=22, r2=15, t0=360, t1=0)]


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
    "slots_plate": slots_plate(),
}

# Faces for the exact bands: all of the above, the side plate at the top of
# the docs, three round holes close enough to crowd each other, and a face
# with edges that are neither line nor arc.
BAND_FACES = dict(FACES, side_plate=side_plate(), cluster=cluster(), ellipses=ellipses())

# A whole robot plate, at a cell size that suits it.
PLATE_FACES = dict(robot_plate=robot_plate())


# Sampling for measurement, on the safe side: an arc the face lies inside
# (counter-clockwise, face on the left) by chords, which fall inside the face;
# an arc round a hole in the face (clockwise) by tangents, which fall outside
# the hole. Either way the sampled face is slightly smaller than the true one,
# so every clearance measured to it comes out slightly small, never large --
# by at most FINE_SAG. Round holes are measured as true circles instead.
FINE_SAG = 5e-7


def fine(e, sag=FINE_SAG):
    if e.kind == "line":
        return [e.at(0), e.at(1)]
    r2 = e.r2 if e.kind == "ell" else e.r
    if e.kind == "ell":
        # An angle step h bends a chord off an ellipse by at most
        # A^3 h^2 / (8 B^2), A and B its longer and shorter semi-axes.
        A, B = max(e.r, r2), min(e.r, r2)
        step = math.sqrt(8 * sag * B * B / A ** 3)
    else:
        step = 2 * math.acos(1 - sag / e.r)
    n = max(8, math.ceil(abs(math.radians(e.t1 - e.t0)) / step))
    if e.t1 > e.t0:
        return [e.at(k / n) for k in range(n + 1)]
    # Tangents meet at the mid-angle, 1 / cos(h / 2) out -- on an ellipse as
    # on a circle, an ellipse being a stretched circle.
    h = math.radians(e.t1 - e.t0) / n
    out = [e.at(0)]
    for k in range(n):
        t = math.radians(e.t0) + (k + 0.5) * h
        out.append((e.a[0] + e.r / math.cos(h / 2) * math.cos(t), e.a[1] + r2 / math.cos(h / 2) * math.sin(t)))
    return out + [e.at(1)]


def true_loops(edges, sag=FINE_SAG):
    return chain_loops_c([(fine(e, sag), 0, edge_circle(e)) for e in edges])


def true_region(edges):
    """The face as shapely geometry, for telling inside from outside and for
    finding loose pieces -- which need no fine sampling, so this takes 1e-4 mm
    and keeps faces with many round holes quick. Clearances are measured
    against the finely sampled loops instead."""
    import shapely
    loops = [lp for lp, _, _, _ in true_loops(edges, 1e-4)]
    outer = max(loops, key=signed_area)
    holes = [lp for lp in loops if lp is not outer]
    return shapely.Polygon(outer, holes)


def p_shape(h):
    """The hole shrunk by r, as a polygon, on the safe side. Exact for a plain
    core. An arc the hole lies inside is sampled by tangents, outside it; an
    arc it lies outside, by chords, inside the circle -- so the shape is at
    most 1e-7 mm larger than the truth, never smaller, and every clearance
    measured from it comes out that much small, never large."""
    import shapely
    if "core" in h:
        return shapely.Polygon(h["core"])
    pts = []
    for p in h["loop"]:
        pts.append(p["a"])
        if p["kind"] == "L":
            continue
        n = max(2, math.ceil(p["sweep"] / (2 * math.acos(1 - 1e-7 / p["rho"]))))
        hh = p["sweep"] / n
        u = sub(p["a"], p["c"])
        t0 = math.atan2(u[1], u[0])
        if p["dir"] > 0:
            rr = p["rho"] / math.cos(hh / 2)
            pts += [(p["c"][0] + rr * math.cos(t0 + (k + 0.5) * hh), p["c"][1] + rr * math.sin(t0 + (k + 0.5) * hh))
                    for k in range(n)]
        else:
            pts += [(p["c"][0] + p["rho"] * math.cos(t0 - k * hh), p["c"][1] + p["rho"] * math.sin(t0 - k * hh))
                    for k in range(1, n)]
    return shapely.Polygon(pts)


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
    import shapely
    ents = hole_outline(h, r)
    err = 0.0
    for k, e in enumerate(ents):
        nxt = ents[(k + 1) % len(ents)]
        err = max(err, vlen(sub(e[-1], nxt[1])))
        for q in ent_points(e, 8):
            dist = P.exterior.distance(shapely.Point(q)) if r <= 0 else P.distance(shapely.Point(q))
            err = max(err, abs(dist - r))
    return err


def measure(edges, plan):
    import shapely
    from shapely.strtree import STRtree
    r = plan["r"]
    region = true_region(edges)
    ring = plan.get("ring")
    res = dict(holes=len(plan["holes"]), rib=math.inf, border=math.inf, ring=math.inf,
               smallest=math.inf, outside=0, invalid=0, islands=0, outline=0.0, open=0.0,
               curved=sum(1 for h in plan["holes"] if "loop" in h), cuts=sum(1 for h in plan["holes"] if h.get("cut")))
    if not plan["holes"]:
        return res
    P = [p_shape(h) for h in plan["holes"]]
    tree = STRtree(P)
    for i, p in enumerate(P):
        for j in tree.query(p, predicate="dwithin", distance=50.0):
            if j > i:
                res["rib"] = min(res["rib"], p.distance(P[j]) - 2 * r)
    # The outline against the border; every hole in the face against the band
    # width with bands on, the border with them off. Round holes are measured
    # as true circles, everything else finely sampled.
    loops = true_loops(edges)
    outer = [lp for lp, _, _, _ in loops if signed_area(lp) > 0]
    inner = [lp for lp, _, c, _ in loops if signed_area(lp) < 0 and c is None]
    circles = [c for lp, _, c, _ in loops if signed_area(lp) < 0 and c is not None]
    ob = shapely.MultiLineString([list(shapely.LinearRing(lp).coords) for lp in outer])
    res["border"] = min(p.distance(ob) for p in P) - r
    hole_clear = math.inf
    if inner:
        ib = shapely.MultiLineString([list(shapely.LinearRing(lp).coords) for lp in inner])
        hole_clear = min(p.distance(ib) for p in P) - r
    for C, Rc in circles:
        pc = shapely.Point(C)
        hole_clear = min(hole_clear, min(p.distance(pc) for p in P) - r - Rc)
    if ring is None:
        res["border"] = min(res["border"], hole_clear)
    else:
        res["ring"] = hole_clear
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
        errs.append(f"band {m['ring']:.6f} < {plan['ring']}")
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

BAND_SETTINGS = [
    dict(ring=5.0),
    dict(ring=5.0, struts=True),
    dict(ring=3.0, struts=True, min_d=0.0),
    dict(ring=5.0, irregular=1.0, struts=True),
    dict(ring=5.0, irregular=0.0, struts=True, min_d=0.0),
    dict(ring=8.0, corner=4.0, struts=True),
    dict(ring=2.0, corner=0.0, min_hole=0.0, struts=True),
    dict(ring=5.0, fit=False, struts=True),
    dict(ring=1.0, rib=0.8, cell=8, border=3, min_hole=3, struts=True),
    dict(ring=6.0, rib=4.0, cell=20, border=6, struts=True),
    dict(ring=10.0, border=3.0, struts=True, min_d=0.0),
]

PLATE_SETTINGS = [
    dict(cell=30.0),
    dict(cell=30.0, ring=5.0),
    dict(cell=30.0, ring=5.0, struts=True),
    dict(cell=30.0, ring=5.0, struts=True, min_hole=10.0),
    dict(cell=30.0, ring=5.0, struts=True, min_d=0.0),
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
            extra = f" band={m['ring']:.4f} curved={m['curved']} straight={m['cuts']}"
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
    print(f"== {label}: {n - fails}/{n} cases passed ==", flush=True)
    return fails


def run_checks(verbose=True, only=None, jobs=4):
    MATRICES.update(classic=(FACES, CLASSIC_SETTINGS), bands=(BAND_FACES, BAND_SETTINGS),
                    plate=(PLATE_FACES, PLATE_SETTINGS))
    fails = 0
    if only in (None, "classic"):
        print("Straight cuts (exact bands off):")
        fails += run_matrix("classic", 1 if verbose else 0, "straight cuts", jobs)
    if only in (None, "bands"):
        print("Exact bands, struts on (defaults: band 5, struts on round holes from 10 mm):")
        fails += run_matrix("bands", 2 if verbose else 0, "exact bands", jobs)
    if only in (None, "plate"):
        print("A whole robot plate, 30 mm cells (bands and struts at defaults):")
        fails += run_matrix("plate", 3 if verbose else 0, "robot plate", jobs)
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
    """How often a cell's bands could not be drawn cleanly at the first try
    and were tried again smaller, and how often they then fell back to
    straight cuts, on every band test face at the default settings."""
    global retry
    first = retry
    tries = [0]

    def counting(*a):
        if not a[-1]:                     # not already nudged: a first try that failed
            tries[0] += 1
        return first(*a)

    retry = counting
    try:
        plans = holes = cuts = 0
        for fname, edges in BAND_FACES.items():
            for shape in ("QUAD", "TRI", "HEX"):
                for st in (dict(ring=5.0), dict(ring=5.0, struts=True)):
                    for seed in (1, 7, 23):
                        plan = plan_face(edges, shape=shape, seed=seed, **st)
                        plans += 1
                        holes += len(plan["holes"])
                        cuts += sum(1 for h in plan["holes"] if h.get("cut"))
    finally:
        retry = first
    print(f"{plans} plans, {holes} holes: {tries[0]} tried again {NUDGE} mm smaller "
          f"({100 * tries[0] / holes:.2f}%), {cuts} cut straight in the end ({100 * cuts / holes:.2f}%)")


def sheet(path, panels, ncol, scale, font_size=26):
    """Plans drawn side by side with a label over each: panels = [(label, edges, plan)]."""
    from PIL import Image, ImageDraw, ImageFont
    import tempfile, os
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for k, (label, edges, plan) in enumerate(panels):
            f = os.path.join(tmp, f"{k}.png")
            draw(edges, plan, f, scale=scale)
            tiles.append((label, Image.open(f).copy()))
    w = max(t.size[0] for _, t in tiles)
    h = max(t.size[1] for _, t in tiles)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    top, gap = font_size + 18, 14
    nrow = (len(tiles) + ncol - 1) // ncol
    img = Image.new("RGB", (ncol * w + (ncol - 1) * gap, nrow * (h + top) + (nrow - 1) * gap), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, (label, t) in enumerate(tiles):
        x, y = (k % ncol) * (w + gap), (k // ncol) * (h + top + gap)
        d.text((x + 6, y + 8), label, fill=(30, 30, 30), font=font)
        img.paste(t, (x, y + top))
    img.save(path)


def band_preview(path, face="side_plate", scale=3.0):
    """The docs picture: straight cuts against exact bands, without and with struts."""
    edges = dict(FACES, **BAND_FACES)[face]
    panels = []
    for shape, name in (("QUAD", "4 sides"), ("HEX", "6 sides")):
        panels += [(f"{name}: straight cuts", edges, plan_face(edges, shape=shape)),
                   (f"{name}: exact bands", edges, plan_face(edges, shape=shape, ring=5.0)),
                   (f"{name}: bands + struts" + (" (default)" if shape == "HEX" else " (6 sides only)"),
                    edges, plan_face(edges, shape=shape, ring=5.0, struts=True))]
    sheet(path, panels, 3, scale)


def faces_preview(path, scale=3.0):
    """Six face shapes at the defaults (6 sides, exact bands, struts)."""
    names = [("rounded_rect", "rounded rectangle"), ("rect_4_screws", "four screw holes"), ("plate_slot", "slot"),
             ("l_shape", "L-shape"), ("notched", "notch"), ("annulus", "ring")]
    sheet(path, [(label, FACES[f], plan_face(FACES[f], shape="HEX", ring=5.0, struts=True)) for f, label in names],
          3, scale)


def plate_preview(path, scale=1.6):
    """The robot plate: straight cuts against bands and struts."""
    edges = PLATE_FACES["robot_plate"]
    sheet(path, [("Straight cuts (bands off)", edges, plan_face(edges, shape="HEX", cell=30.0)),
                 ("Exact bands + struts (default)", edges,
                  plan_face(edges, shape="HEX", cell=30.0, ring=5.0, struts=True))], 2, scale, 24)


# ---------------------------------------------------------------- crosscheck
#
# Runs the .fs file's own functions through tools/fsinterp.py on the same
# inputs as this mirror, and requires the same answer at every stage. The
# mirror is what `check` measured; agreement carries those measurements over
# to the FeatureScript. What is left untested is only the Onshape I/O:
# reading the face, and the sketch / extrude / boolean calls.

XC_CLASSIC = [dict(), dict(irregular=1.0), dict(irregular=0.0), dict(fit=False),
              dict(rib=0.8, cell=8, border=3, min_hole=3), dict(corner=0.0, min_hole=0.0),
              dict(corner=4.0)]

XC_BANDS = [dict(), dict(ring=5.0), dict(ring=5.0, struts=True), dict(ring=3.0, struts=True, min_d=0.0),
            dict(ring=5.0, irregular=1.0, struts=True), dict(ring=8.0, corner=4.0, struts=True),
            dict(ring=2.0, corner=0.0, min_hole=0.0, struts=True), dict(ring=5.0, fit=False, struts=True),
            dict(ring=6.0, rib=4.0, cell=20, border=6, struts=True)]

XC_PLATE = [dict(), dict(ring=5.0), dict(ring=5.0, struts=True), dict(ring=5.0, struts=True, min_d=0.0)]

# The one case where the bands fall back to straight cuts in the test faces
# (see `fallbacks`), run by name since the matrix above misses it; and the
# faces whose every cell is also put through the fallback directly, which
# keeps the band width, not the border, off their holes.
XC_FALLBACK = [("circle_d100", "QUAD", dict(ring=5.0, seed=23))]
XC_STRAIGHT = ["rect_4_screws", "plate_slot", "slots_plate", "side_plate"]


def same_pt(a, b, tol=1e-9):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# Same polygon, allowing a different starting corner: a coordinate that
# differs in the 16th digit (FeatureScript's cos(t * degree) against
# Python's cos(radians(t)), its norm against Python's hypot) can tip a strict
# comparison on a corner that lies exactly on a clip line, and the clip then
# starts its output at the next corner. Measured on every such case: same
# corners, Hausdorff distance ~1e-15 mm.
def rotation(a, b):
    if len(a) != len(b):
        return None
    if not a:
        return 0
    for k in range(len(b)):
        if all(same_pt(a[i], b[(i + k) % len(b)]) for i in range(len(a))):
            return k
    return None


def xc_interp(fs_path):
    import fsinterp
    it = fsinterp.Interp(open(fs_path).read())
    recorded = []
    it.globals.declare("skLineSegment", lambda sk, ident, m: recorded.append(
        ("line", ident, tuple(m["start"]), tuple(m["end"]))))
    it.globals.declare("skArc", lambda sk, ident, m: recorded.append(
        ("arc", ident, tuple(m["start"]), tuple(m["mid"]), tuple(m["end"]))))
    shapes = {sh: it.globals.get("LeopardCellShape")[sh] for sh in ("QUAD", "TRI", "HEX")}
    return it, shapes, recorded


def fs_polys_of(edges):
    from fsinterp import Vec
    out = []
    for e in edges:
        pts, sag = sample_edge(e)
        circ = edge_circle(e)
        out.append({"pts": [Vec(p) for p in pts], "sag": sag,
                    "circle": None if circ is None else {"c": Vec(circ[0]), "r": float(circ[1])}})
    return out


def same_pieces(ml, fl):
    """Two loops of pieces, piece by piece: kind, ends, and for an arc its
    centre, radius, direction and sweep."""
    if len(ml) != len(fl):
        return False
    for m, f in zip(ml, fl):
        if m["kind"] != f["kind"] or not same_pt(m["a"], f["a"]) or not same_pt(m["b"], f["b"]):
            return False
        if m["kind"] == "A" and (not same_pt(m["c"], f["c"]) or abs(m["rho"] - f["rho"]) > 1e-9
                                 or m["dir"] != f["dir"] or abs(m["sweep"] - f["sweep"]) > 1e-9):
            return False
    return True


def compare_hole(mh, fh, r, it, recorded):
    """One hole, mirror against FeatureScript: its shape, its sketch
    entities, its area, and the calls drawHole makes. None if they agree."""
    k0 = 0
    if "loop" in mh:
        if fh.get("loop") is None:
            return "curved in the mirror only"
        if not same_pieces(mh["loop"], fh["loop"]):
            return "loop differs"
    else:
        if fh.get("loop") is not None or fh.get("core") is None:
            return "plain in the mirror only"
        if bool(mh.get("cut")) != bool(fh.get("cut")):
            return "straight-cut fallback in one only"
        k0 = rotation(mh["core"], fh["core"])
        if k0 is None:
            return "core differs"
    want = hole_outline(mh, r)
    if k0:
        # A core rotated by k corners rotates its entities by k (r = 0) or
        # 2k (a line and an arc per corner).
        per = 2 if r > 0 else 1
        s0 = (-k0 * per) % len(want)
        want = want[s0:] + want[:s0]
    got = it.call("holeOutline", fh, r)
    got = [("line", e["start"], e["end"]) if e["line"] else ("arc", e["start"], e["mid"], e["end"]) for e in got]
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


def xc_classic(fs_path, fname):
    """Straight cuts, stage by stage: the region, the cells, every cell's core
    (cellHoles), and its entities, area and sketch calls."""
    from fsinterp import Vec
    it, shapes, recorded = xc_interp(fs_path)
    edges = FACES[fname]
    fs_polys = fs_polys_of(edges)
    lines, n, fails, holes = [], 0, 0, 0
    for shape in ("QUAD", "TRI", "HEX"):
        for st in XC_CLASSIC:
            kw = dict(shape=shape, cell=14.0, rib=2.0, border=5.0, irregular=0.7,
                      corner=1.0, min_hole=4.0, seed=3, fit=True)
            kw.update(st)
            n += 1
            errs = []
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
                    same_pt(sg["a"], m[0]) and same_pt(sg["b"], m[1]) and sg["sag"] == m[2]
                    and sg["inner"] == m[3] for sg, m in zip(fR["segs"], R.segs)):
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
            if len(cells) != len(fcells) or not all(rotation(a, b) is not None for a, b in zip(cells, fcells)):
                errs.append(f"cells differ ({len(cells)} vs {len(fcells)})")
            else:
                for k, c in enumerate(cells):
                    mh = cell_holes(c, R, kw["rib"], r, bw, keep_r)
                    fh = it.call("cellHoles", fcells[k], fR, kw["rib"], r, bw, keep_r)
                    if len(mh) != len(fh):
                        errs.append(f"cell {k}: {len(mh)} holes vs {len(fh)}")
                        break
                    if mh:
                        e = compare_hole(mh[0], fh[0], r, it, recorded)
                        if e:
                            errs.append(f"cell {k}: {e}")
                            break
                        holes += 1
            if errs:
                fails += 1
                lines.append(f"FAIL classic {fname} {shape} {st}: {'; '.join(errs)}")
    return lines, n, fails, dict(plain=holes)


def xc_bands(fs_path, fname, faces, cases, cell):
    """planHoles, the .fs file's whole plan for a face, against plan_face,
    hole by hole -- straight cuts, exact bands and struts alike. cases:
    [(shape, settings)]."""
    it, shapes, recorded = xc_interp(fs_path)
    edges = faces[fname]
    fs_polys = fs_polys_of(edges)
    lines, n, fails = [], 0, 0
    counts = dict(plain=0, curved=0, cut=0)
    for shape, st in cases:
        if True:
            kw = dict(shape=shape, cell=cell, rib=2.0, border=5.0, irregular=0.7,
                      corner=1.0, min_hole=4.0, seed=3, fit=True)
            kw.update(st)
            n += 1
            errs = []
            plan = plan_face(edges, **kw)
            gs = max(kw["cell"] * PITCH[shape], 1.0)
            R = build_region(edges, gs)
            fR = it.call("buildRegion", fs_polys, float(gs))
            if len(fR["circles"]) != len(R.circles) or not all(
                    same_pt(f["c"], m[0]) and abs(f["r"] - m[1]) < 1e-12 and f["inner"] == m[2]
                    for f, m in zip(fR["circles"], R.circles)):
                errs.append("round holes differ")
            fset = {"shape": shapes[shape], "cell": kw["cell"], "rib": kw["rib"], "r": plan["r"],
                    "keepR": plan["keep_r"], "border": plan["border"], "irregular": kw["irregular"],
                    "seed": float(kw["seed"]), "fit": kw["fit"], "ring": plan["ring"],
                    "struts": bool(kw.get("struts")) and shape == "HEX", "strutMinD": float(kw.get("min_d", 10.0))}
            fholes = it.call("planHoles", fR, fs_polys, fset)
            r = plan["r"]
            if len(fholes) != len(plan["holes"]):
                errs.append(f"hole count {len(fholes)} vs {len(plan['holes'])}")
            else:
                for k, (mh, fh) in enumerate(zip(plan["holes"], fholes)):
                    e = compare_hole(mh, fh, r, it, recorded)
                    if e:
                        errs.append(f"hole {k}: {e}")
                        break
                    counts["curved" if "loop" in mh else "cut" if mh.get("cut") else "plain"] += 1
            if errs:
                fails += 1
                lines.append(f"FAIL bands {fname} {shape} {st}: {'; '.join(errs)}")
    return lines, n, fails, counts


def xc_straight(fs_path, fname):
    """straightCore, the fallback, on every cell of a face, with a band width
    unlike the border so the two cannot be mixed up."""
    from fsinterp import Vec
    it, shapes, recorded = xc_interp(fs_path)
    edges = BAND_FACES[fname]
    fs_polys = fs_polys_of(edges)
    lines, n, fails, holes = [], 0, 0, 0
    for shape in ("QUAD", "TRI", "HEX"):
        n += 1
        rib, r, bw, ring, keep_r = 2.0, 1.0, 5.0, 3.0, 2.0
        gs = max(14.0 * PITCH[shape], 1.0)
        R = build_region(edges, gs)
        fR = it.call("buildRegion", fs_polys, float(gs))
        polys = [sample_edge(e) + (edge_circle(e),) for e in edges]
        ctx = band_context(polys, R, bw + r, ring + r, keep_r - r)
        fctx = it.call("bandContext", fs_polys, fR, bw + r, ring + r, keep_r - r)
        cells = crop_cells(shape, R.lo, R.hi, 14.0, 0.7, 3)
        err = None
        for k, c in enumerate(cells):
            core = inset_convex(c, rib / 2 + r)
            if not core:
                continue
            mh = straight_core(core, ctx, r, bw, ring, keep_r)
            fh = it.call("straightCore", [Vec(q) for q in core], fctx, r, bw, ring, keep_r)
            if len(mh) != len(fh):
                err = f"cell {k}: {len(mh)} holes vs {len(fh)}"
            elif mh:
                err = compare_hole(mh[0], fh[0], r, it, recorded)
                holes += 1
            if err:
                break
        if err:
            fails += 1
            lines.append(f"FAIL straight {fname} {shape}: {err}")
    return lines, n, fails, dict(cut=holes)


def xc_job(job):
    kind, fs_path, fname = job
    every = lambda settings: [(sh, st) for sh in ("QUAD", "TRI", "HEX") for st in settings]
    if kind == "classic":
        return kind, fname, xc_classic(fs_path, fname)
    if kind == "bands":
        return kind, fname, xc_bands(fs_path, fname, BAND_FACES, every(XC_BANDS), 14.0)
    if kind == "fallback":
        return kind, fname, xc_bands(fs_path, fname, BAND_FACES,
                                     [(sh, st) for f, sh, st in XC_FALLBACK if f == fname], 14.0)
    if kind == "straight":
        return kind, fname, xc_straight(fs_path, fname)
    return kind, fname, xc_bands(fs_path, fname, PLATE_FACES, every(XC_PLATE), 30.0)


def run_crosscheck(fs_path, plate=True, jobs=4, only=None, face=None):
    from multiprocessing import Pool
    work = []
    if only in (None, "classic"):
        work += [("classic", fs_path, f) for f in FACES]
    if only in (None, "bands"):
        work += [("bands", fs_path, f) for f in BAND_FACES]
        work += [("fallback", fs_path, f) for f in dict.fromkeys(f for f, _, _ in XC_FALLBACK)]
        work += [("straight", fs_path, f) for f in XC_STRAIGHT]
    if only in (None, "plate") and plate:
        work += [("plate", fs_path, f) for f in PLATE_FACES]
    if face:
        work = [w for w in work if w[2] == face]
    tot = {}
    with Pool(jobs) as pool:
        for kind, fname, (lines, n, fails, counts) in pool.imap_unordered(xc_job, work):
            for ln in lines:
                print(ln, flush=True)
            t = tot.setdefault(kind, dict(n=0, fails=0, plain=0, curved=0, cut=0))
            t["n"] += n
            t["fails"] += fails
            for key, v in counts.items():
                t[key] += v
            print(f"  {kind:<8} {fname:<15} {n - fails}/{n} agree", flush=True)
    bad = 0
    for kind, t in tot.items():
        bad += t["fails"]
        print(f"== crosscheck, {kind}: {t['n'] - t['fails']}/{t['n']} cases agree; compared point by point: "
              f"{t['plain']} plain holes, {t['curved']} curved, {t['cut']} straight-cut fallbacks ==")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub_ = ap.add_subparsers(dest="cmd", required=True)
    ck = sub_.add_parser("check")
    ck.add_argument("--only", choices=["classic", "bands", "plate"])
    ck.add_argument("--jobs", type=int, default=4)
    cc = sub_.add_parser("crosscheck")
    cc.add_argument("fs", nargs="?", default="projects/leopard-vent/featurescript/leopard_vent.fs")
    cc.add_argument("--no-plate", action="store_true", help="skip the robot plate, the slow part")
    cc.add_argument("--only", choices=["classic", "bands", "plate"])
    cc.add_argument("--face", help="one face only")
    cc.add_argument("--jobs", type=int, default=4)
    sub_.add_parser("fallbacks", help="how often a cell falls back to straight cuts")
    pv = sub_.add_parser("preview", help="the pictures in the docs")
    pv.add_argument("bands_png")
    pv.add_argument("plate_png")
    pv.add_argument("faces_png")
    p = sub_.add_parser("png")
    p.add_argument("out")
    allfaces = dict(FACES, **BAND_FACES, **PLATE_FACES)
    p.add_argument("--face", default="rect_120x80", choices=sorted(allfaces))
    p.add_argument("--shape", default="QUAD", choices=["QUAD", "TRI", "HEX"])
    p.add_argument("--cell", type=float, default=14.0)
    p.add_argument("--crop", action="store_true")
    p.add_argument("--irregular", type=float, default=0.7)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--ring", type=float, help="exact bands, this wide round every hole in the face")
    p.add_argument("--struts", action="store_true", help="rings of cells round round holes (6 sides)")
    p.add_argument("--min-d", type=float, default=10.0)
    p.add_argument("--scale", type=float, default=6)
    a = ap.parse_args()
    if a.cmd == "check":
        return run_checks(only=a.only, jobs=a.jobs)
    if a.cmd == "crosscheck":
        return run_crosscheck(a.fs, plate=not a.no_plate, jobs=a.jobs, only=a.only, face=a.face)
    if a.cmd == "fallbacks":
        fallback_report()
        return 0
    if a.cmd == "preview":
        band_preview(a.bands_png)
        plate_preview(a.plate_png)
        faces_preview(a.faces_png)
        print(a.bands_png, a.plate_png, a.faces_png)
        return 0
    edges = allfaces[a.face]
    plan = plan_face(edges, shape=a.shape, cell=a.cell, fit=not a.crop, irregular=a.irregular, seed=a.seed,
                     ring=a.ring, struts=a.struts, min_d=a.min_d)
    draw(edges, plan, a.out, scale=a.scale)
    print(a.out, len(plan["holes"]), "holes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
