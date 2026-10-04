#!/usr/bin/env python3
"""
fsmirror -- Python mirror of the LEOPARD VENT FeatureScript geometry.

FeatureScript only runs inside Onshape, so the geometry in
projects/leopard-vent/featurescript/leopard_vent.fs cannot be tested from
here. This file is a line-for-line mirror of its pure-maths half -- cell
generation, face-boundary handling, hole clipping, corner rounding, the
min-hole test -- written so each function maps onto one FeatureScript
function of the same name. What it cannot mirror is the Onshape plumbing:
reading the face, the sketch, the extrude, the boolean.

    fsmirror.py check              run every test face, measure every hole
    fsmirror.py png  out.png ...   draw one face (see --help)

The check builds holes exactly as the feature would (core polygon grown by
the corner radius), then measures them with shapely against the TRUE face
outline -- real circles, not the sampled chords the feature works from:
thinnest web between holes, closest approach to the outline and to every
inner loop, smallest hole, and that every hole lies inside the face.
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


# Chains sampled edges into closed loops by matching each end to the next start.
def chain_loops(polys):
    tol = 1e-3
    used = [False] * len(polys)
    loops = []
    for k in range(len(polys)):
        if used[k]:
            continue
        used[k] = True
        loop = list(polys[k][0][:-1])
        sag = polys[k][1]
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
            end = polys[nxt][0][-1]
        loops.append((loop, sag))
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
    inners: list = field(default_factory=list)  # (hull, centre, radius, sag)
    lo: tuple = (0, 0)
    hi: tuple = (0, 0)
    grid: dict = field(default_factory=dict)
    gs: float = 1.0


def build_region(edges, grid_size):
    loops = chain_loops([sample_edge(e) for e in edges])
    R = Region(gs=grid_size)
    xs = [p[0] for lp, _ in loops for p in lp]
    ys = [p[1] for lp, _ in loops for p in lp]
    R.lo, R.hi = (min(xs), min(ys)), (max(xs), max(ys))
    for lp, sag in loops:
        inner = -1
        if signed_area(lp) < 0:
            hull = convex_hull(lp)
            c = centroid(hull)
            R.inners.append((hull, c, max(vlen(sub(q, c)) for q in hull), sag))
            inner = len(R.inners) - 1
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


def hole_core(cell, R, rib, r, border, keep_r):
    """The convex core of one hole: the hole is this grown by r."""
    c = centroid(cell)
    core = inset_convex(cell, rib / 2 + r)
    if not core:
        return []
    cell_r = max(vlen(sub(q, c)) for q in cell)
    reach = cell_r + border + r + SAG + 1e-6
    near = near_segments(R, c, reach)
    inside = inside_region(R, c)
    if not near:
        if not inside:
            return []
    else:
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
                hull, hc, _, isag = R.inners[inner]
                core = inner_clip(core, c, hull, border + r + isag)
            if len(core) < 3:
                return []
    core = tidy(ccw(core))
    if not core:
        return []
    if keep_r > r and not inset_convex(core, keep_r - r):
        return []
    return core


def plan_face(edges, shape="QUAD", cell=14.0, rib=2.0, border=5.0, irregular=0.7,
              corner=1.0, min_hole=4.0, seed=1, fit=True):
    """Everything the feature computes for one face, before it touches Onshape."""
    across = cell * PITCH[shape] * ACROSS[shape]
    hw = across - rib
    if hw <= 0.1:
        raise ValueError(f"rib {rib} leaves no hole in a {cell} cell")
    r = min(corner, 0.4 * hw)
    if r < MIN_RADIUS:
        r = 0.0
    keep_r = min(min_hole / 2, 0.4 * hw)
    bw = max(border, rib)
    R = build_region(edges, grid_size=max(cell * PITCH[shape], 1.0))
    if fit:
        ins = bw - rib / 2
        lo, hi = add(R.lo, (ins, ins)), sub(R.hi, (ins, ins))
        if hi[0] <= lo[0] or hi[1] <= lo[1]:
            return dict(cores=[], r=r, keep_r=keep_r, border=bw, hw=hw)
        cells = fit_cells(shape, lo, hi, cell, irregular, seed)
    else:
        cells = crop_cells(shape, R.lo, R.hi, cell, irregular, seed)
    cores = [k for k in (hole_core(c, R, rib, r, bw, keep_r) for c in cells) if k]
    return dict(cores=cores, r=r, keep_r=keep_r, border=bw, hw=hw)


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


def true_region(edges):
    """The face as shapely geometry, with arcs at fine resolution."""
    import shapely
    loops = []
    for lp, _ in chain_loops([(fine(e), 0) for e in edges]):
        loops.append(lp)
    outer = max(loops, key=signed_area)
    holes = [lp for lp in loops if lp is not outer]
    return shapely.Polygon(outer, holes)


def fine(e):
    if e.kind == "line":
        return [e.at(0), e.at(1)]
    n = max(8, math.ceil(abs(e.t1 - e.t0) * 8))
    return [e.at(k / n) for k in range(n + 1)]


def hole_polygon(core, r):
    import shapely
    p = shapely.Polygon(core)
    return p.buffer(r, quad_segs=64) if r > 0 else p


def measure(edges, plan):
    import shapely
    from shapely.strtree import STRtree
    region = true_region(edges)
    holes = [hole_polygon(c, plan["r"]) for c in plan["cores"]]
    res = dict(holes=len(holes), rib=math.inf, border=math.inf, smallest=math.inf,
               outside=0, open=0.0)
    if not holes:
        return res
    tree = STRtree(holes)
    for i, h in enumerate(holes):
        for j in tree.query(h, predicate="dwithin", distance=50.0):
            if j != i:
                res["rib"] = min(res["rib"], h.distance(holes[j]))
    rb = region.boundary
    res["border"] = min(h.distance(rb) for h in holes)
    res["outside"] = sum(1 for h in holes if not region.buffer(1e-6).contains(h))
    res["smallest"] = min(2 * shapely.maximum_inscribed_circle(h, tolerance=0.005).length
                          for h in holes)
    res["open"] = 100 * sum(hole_area(c, plan["r"]) for c in plan["cores"]) / region.area
    return res


def run_checks(verbose=True):
    shapes = ["QUAD", "TRI", "HEX"]
    settings = [
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
    tol = 1e-6
    fails = n = 0
    for fname, edges in FACES.items():
        for shape in shapes:
            for st in settings:
                for seed in (1, 7, 23):
                    kw = dict(shape=shape, seed=seed, **st)
                    plan = plan_face(edges, **kw)
                    m = measure(edges, plan)
                    rib = kw.get("rib", 2.0)
                    bw = plan["border"]
                    errs = []
                    if m["rib"] < rib - tol:
                        errs.append(f"rib {m['rib']:.6f} < {rib}")
                    if m["border"] < bw - tol:
                        errs.append(f"border {m['border']:.6f} < {bw}")
                    if m["outside"]:
                        errs.append(f"{m['outside']} holes outside the face")
                    if m["holes"] and m["smallest"] < 2 * min(plan["keep_r"], plan["hw"]) - 0.02 \
                            and plan["keep_r"] > plan["r"]:
                        errs.append(f"smallest {m['smallest']:.3f} < {2 * plan['keep_r']:.3f}")
                    n += 1
                    if errs:
                        fails += 1
                        print(f"FAIL {fname} {kw}: {'; '.join(errs)}")
            if verbose:
                plan = plan_face(edges, shape=shape)
                m = measure(edges, plan)
                print(f"  {fname:<15} {shape:<4} holes={m['holes']:<4} rib={m['rib']:.4f} "
                      f"border={m['border']:.4f} smallest={m['smallest']:.3f} open={m['open']:.1f}%")
    print(f"== {n - fails}/{n} cases passed ==")
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
    for c in plan["cores"]:
        hp = hole_polygon(c, plan["r"])
        d.polygon([tf(p) for p in hp.exterior.coords], fill=(248, 248, 248))
    img.save(path)


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
        polys = [sample_edge(e) for e in edges]
        fs_polys = [{"pts": [Vec(p) for p in pts], "sag": sag} for pts, sag in polys]
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
                            if abs(hole_area(mc, r) - it.call("holeArea", fc, r)) > 1e-9:
                                errs.append(f"hole area {k} differs")
                                break
                            recorded.clear()
                            it.call("drawHole", None, "h", fc, r)
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
    print(f"== crosscheck: {n - fails}/{n} cases agree, {holes} holes compared point by point ==")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub_ = ap.add_subparsers(dest="cmd", required=True)
    sub_.add_parser("check")
    cc = sub_.add_parser("crosscheck")
    cc.add_argument("fs", nargs="?", default="projects/leopard-vent/featurescript/leopard_vent.fs")
    p = sub_.add_parser("png")
    p.add_argument("out")
    p.add_argument("--face", default="rect_120x80", choices=sorted(FACES))
    p.add_argument("--shape", default="QUAD", choices=["QUAD", "TRI", "HEX"])
    p.add_argument("--crop", action="store_true")
    p.add_argument("--irregular", type=float, default=0.7)
    p.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "check":
        return run_checks()
    if a.cmd == "crosscheck":
        return run_crosscheck(a.fs)
    edges = FACES[a.face]
    plan = plan_face(edges, shape=a.shape, fit=not a.crop, irregular=a.irregular, seed=a.seed)
    draw(edges, plan, a.out)
    print(a.out, len(plan["cores"]), "holes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
