#!/usr/bin/env python3
"""
fieldlab -- NumPy mirror of the OpenSCAD field engine in
projects/waveform-wall/src/waveform_wall.scad.

The .scad file is the product and the reference. This module exists to make
design iteration fast: evaluating a field here takes milliseconds where a full
OpenSCAD render takes minutes. That is only worth anything if the two agree, so
every quirk of the OpenSCAD version is reproduced here -- including that
OpenSCAD's sin()/cos() take DEGREES, which the hash and every wave term depend
on. tools/crosscheck.py proves the agreement.

Change the .scad first, then mirror it here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

R2_A1 = 0.7548776662   # 1 / plastic number
R2_A2 = 0.5698402910   # 1 / plastic number squared
NORM_N = 26


def sind(x):
    """OpenSCAD sin(): argument in degrees."""
    return np.sin(np.radians(x))


def cosd(x):
    return np.cos(np.radians(x))


def frac(x):
    return x - np.floor(x)


def hash01(n, s):
    a0 = sind(n * 12.9898 + s * 78.233 + 41.7) * 43758.5453
    a = frac(a0)
    c0 = sind(a * 311.7 + n * 74.7 + s * 19.19) * 24634.6345
    return frac(c0)


def hash_range(n, s, lo, hi):
    return lo + (hi - lo) * hash01(n, s)


def r2_frac(k, offset, alpha):
    return frac(offset + (k + 1) * alpha)


COLS = ("wave_count", "wave_amp", "wave_len", "harm_ratio", "harm_fall",
        "dir_spread", "vortex_n", "vortex_str", "vortex_rad", "peak_n",
        "peak_str", "valley_str", "feature", "envelope", "terrace", "gamma")

STYLE_TABLE = {
    "Flow":         (3, 1.00, 0.55, 1.9, 0.55, 34, 2, 1.00, 0.38, 3, 1.00, 0.80, 0.42, 0.55, 0, 1.00),
    "Vortex":       (2, 0.75, 0.70, 2.1, 0.45, 28, 3, 1.60, 0.34, 2, 0.70, 0.90, 0.38, 0.35, 0, 0.95),
    "Dune":         (2, 0.90, 0.90, 2.4, 0.35, 14, 1, 0.55, 0.50, 4, 1.10, 0.60, 0.50, 0.65, 0, 1.15),
    "Liquid":       (4, 1.00, 0.48, 1.7, 0.62, 41, 2, 1.15, 0.42, 3, 0.85, 0.85, 0.36, 0.45, 0, 0.90),
    "Interference": (5, 1.20, 0.42, 1.5, 0.72, 47, 1, 0.45, 0.55, 2, 0.55, 0.55, 0.55, 0.25, 0, 1.00),
    "Topographic":  (3, 0.85, 0.62, 2.0, 0.50, 31, 2, 0.95, 0.40, 4, 1.00, 0.80, 0.40, 0.50, 7, 1.00),
}


@dataclass
class FieldSpec:
    artwork_width: float = 400.0
    artwork_height: float = 400.0
    style: str = "Flow"
    seed: float = 7.0
    intensity: float = 1.0
    flow_angle: float = 25.0
    extra_vortices: int = 0
    swirl_scale: float = 1.0
    detail_scale: float = 1.0
    relief_gamma: float = 1.0

    def sp(self, name):
        return STYLE_TABLE[self.style][COLS.index(name)]

    @property
    def short_side(self):  return min(self.artwork_width, self.artwork_height)
    @property
    def wave_count(self):  return max(1, int(self.sp("wave_count")))
    @property
    def wave_amp(self):    return self.sp("wave_amp") * self.intensity * self.detail_scale
    @property
    def wave_len(self):    return self.sp("wave_len") * self.short_side
    @property
    def harm_ratio(self):  return self.sp("harm_ratio")
    @property
    def harm_fall(self):   return self.sp("harm_fall")
    @property
    def dir_spread(self):  return self.sp("dir_spread")
    @property
    def vortex_n(self):    return max(0, int(self.sp("vortex_n")) + self.extra_vortices)
    @property
    def vortex_str(self):  return self.sp("vortex_str") * self.swirl_scale
    @property
    def vortex_rad(self):  return self.sp("vortex_rad") * self.short_side
    @property
    def peak_n(self):      return max(0, int(self.sp("peak_n")))
    @property
    def peak_str(self):    return self.sp("peak_str") * self.intensity
    @property
    def valley_str(self):  return self.sp("valley_str") * self.intensity
    @property
    def feature(self):     return self.sp("feature") * self.short_side
    @property
    def envelope_s(self):  return min(max(self.sp("envelope"), 0.0), 0.95)
    @property
    def terrace(self):     return self.sp("terrace")
    @property
    def gamma(self):       return min(max(self.sp("gamma") * self.relief_gamma, 0.4), 2.5)


def spread_point(spec, k, seed_offset, inset):
    ox = hash01(spec.seed * 3 + seed_offset, spec.seed)
    oz = hash01(spec.seed * 5 + seed_offset, spec.seed)
    return ((inset + (1 - 2 * inset) * r2_frac(k, ox, R2_A1)) * spec.artwork_width,
            (inset + (1 - 2 * inset) * r2_frac(k, oz, R2_A2)) * spec.artwork_height)


def vortices(spec):
    if spec.vortex_n <= 0:
        return []
    flip = 1 if hash01(spec.seed * 7 + 3, spec.seed) < 0.5 else -1
    return [(*spread_point(spec, k, 13, 0.22),
             (1 if k % 2 == 0 else -1) * flip * spec.vortex_str,
             spec.vortex_rad) for k in range(spec.vortex_n)]


def peaks(spec):
    if spec.peak_n <= 0:
        return []
    pflip = hash01(spec.seed * 11 + 5, spec.seed) < 0.5
    out = []
    for m in range(spec.peak_n):
        up = (m % 2 == 0) == pflip
        amp = ((spec.peak_str if up else -spec.valley_str)
               * hash_range(m * 4 + 43, spec.seed, 0.6, 1.0))
        cx, cz = spread_point(spec, m, 29, 0.12)
        out.append((cx, cz, amp,
                    spec.feature * hash_range(m * 4 + 44, spec.seed, 0.7, 1.3)))
    return out


def warp(x, z, vs):
    if not vs:
        return x, z
    dx = np.zeros_like(x, dtype=float)
    dz = np.zeros_like(z, dtype=float)
    for cx, cz, strength, radius in vs:
        ox, oz = x - cx, z - cz
        fall = np.exp(-(ox * ox + oz * oz) / (2 * radius * radius))
        dx = dx + strength * fall * (-oz)
        dz = dz + strength * fall * ox
    return x + dx, z + dz


def harmonics(spec, x, z):
    num = np.zeros_like(x, dtype=float)
    den = 0.0
    for j in range(spec.wave_count):
        ang = spec.flow_angle + j * spec.dir_spread
        lam = max(4.0, spec.wave_len / (spec.harm_ratio ** j))
        amp = spec.harm_fall ** j
        proj = x * cosd(ang) + z * sind(ang)
        num = num + amp * sind(360 * proj / lam + j * 97.4)
        den += amp
    return num / max(den, 1e-9)


def landscape(spec, x, z, ps):
    if not ps:
        return np.zeros_like(x, dtype=float)
    num = np.zeros_like(x, dtype=float)
    den = 0.0
    for cx, cz, amp, sigma in ps:
        num = num + amp * np.exp(-((x - cx) ** 2 + (z - cz) ** 2) / (2 * sigma * sigma))
        den += abs(amp)
    return num / max(den, 1e-9)


def envelope(spec, x, z):
    if spec.envelope_s <= 0:
        return np.ones_like(x, dtype=float)
    e = 0.5 + 0.5 * sind(360 * (x * 0.37 + z * 0.62)
                         / (2.15 * spec.short_side) + spec.seed * 57.3)
    return 1 - spec.envelope_s * (1 - e)


def field_raw(spec, x, z):
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    wx, wz = warp(x, z, vortices(spec))
    return (harmonics(spec, wx, wz) * spec.wave_amp
            + landscape(spec, x, z, peaks(spec))) * envelope(spec, x, z)


def norm_range(spec):
    """Field extremes measured on the same coarse grid the .scad uses."""
    i = np.arange(NORM_N + 1) / NORM_N
    xx, zz = np.meshgrid(i * spec.artwork_width, i * spec.artwork_height, indexing="ij")
    v = field_raw(spec, xx, zz)
    return float(v.min()), float(v.max())


def field(spec, x, z, lohi=None):
    lo, hi = lohi if lohi is not None else norm_range(spec)
    t = np.clip((field_raw(spec, x, z) - lo) / max(hi - lo, 1e-9), 0, 1)
    g = np.power(t, spec.gamma)
    if spec.terrace > 1:
        g = np.clip(np.floor(g * spec.terrace) / (spec.terrace - 1), 0, 1)
    return np.clip(g, 0, 1)
