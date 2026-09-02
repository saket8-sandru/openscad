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

import math
import pathlib
import re
from dataclasses import dataclass

import numpy as np

FINS_PER_WAVE = 3.2   # anti-alias guard; see the .scad
WARP_N = 17
TERRACE_RISER = 0.34
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
        "dir_spread", "radial_amp", "radial_len", "vortex_n", "vortex_str",
        "vortex_rad", "peak_n", "peak_str", "valley_str", "feature",
        "envelope", "gamma")

# The style table lives in the .scad -- that file is the product, and keeping a
# second hand-maintained copy here caused exactly the drift you would expect
# (an edit to two rows silently invalidated this mirror until crosscheck caught
# it). Parsing it out of the source makes the duplication impossible.
SCAD_PATH = (pathlib.Path(__file__).resolve().parent.parent
             / "projects/waveform-wall/src/waveform_wall.scad")

_ROW_RE = re.compile(r"/\*\s*(\w[\w ]*?)\s*\*/\s*\[([^\]]*)\]")


def load_style_table(path=None):
    """Read STYLE_TABLE out of the OpenSCAD source."""
    text = pathlib.Path(path or SCAD_PATH).read_text()
    body = text.split("STYLE_TABLE = [", 1)[1].split("];", 1)[0]
    table = {}
    for name, nums in _ROW_RE.findall(body):
        values = tuple(float(v) for v in nums.split(","))
        if len(values) != len(COLS):
            raise ValueError(f"style {name!r} has {len(values)} columns, "
                             f"expected {len(COLS)}")
        table[name] = values
    if not table:
        raise ValueError("no styles parsed from STYLE_TABLE")
    return table


STYLE_TABLE = load_style_table()


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
    # Needed because the anti-alias guard ties field detail to the fin pitch,
    # and the pitch falls out of the tiling. Mirrors the .scad derivation.
    printer: str = "A1 mini (180 x 180)"
    custom_tile_max: float = 200.0
    fin_pitch: float = 8.0
    terrace_steps: int = 0

    def sp(self, name):
        return STYLE_TABLE[self.style][COLS.index(name)]

    @property
    def short_side(self):  return min(self.artwork_width, self.artwork_height)

    # --- tiling, mirroring the .scad -------------------------------------
    @property
    def tile_limit(self):
        if self.printer == "A1 mini (180 x 180)":
            return 172.0
        if self.printer == "A1 / P1 / X1 (256 x 256)":
            return 230.0
        return min(max(self.custom_tile_max, 80.0), 240.0)

    @property
    def tile_cols(self):
        return max(1, math.ceil(self.artwork_width / self.tile_limit))

    @property
    def tile_w(self):
        return self.artwork_width / self.tile_cols

    @property
    def fins_per_tile(self):
        # OpenSCAD round() is half-away-from-zero; Python's round() is
        # banker's rounding and would disagree on exact .5 cases.
        return max(4, math.floor(self.tile_w / self.fin_pitch + 0.5))

    @property
    def pitch(self):
        return self.tile_w / self.fins_per_tile

    @property
    def warp_amp(self):
        """Worst-case frequency multiplication from the domain warp.

        Largest singular value of the warp Jacobian over a coarse grid --
        the same measurement the .scad makes, on the same grid.
        """
        vs = vortices(self)
        if not vs:
            return 1.0
        g = np.arange(WARP_N + 1) / WARP_N
        xx, zz = np.meshgrid(g * self.artwork_width, g * self.artwork_height,
                             indexing="ij")
        h = 0.25
        px, pz = warp(xx + h, zz, vs)
        mx, mz = warp(xx - h, zz, vs)
        qx, qz = warp(xx, zz + h, vs)
        nx, nz = warp(xx, zz - h, vs)
        a = (px - mx) / (2 * h); b = (qx - nx) / (2 * h)
        c = (pz - mz) / (2 * h); d = (qz - nz) / (2 * h)
        t = a * a + b * b + c * c + d * d
        u = (a * a + b * b - c * c - d * d) ** 2 + 4 * (a * c + b * d) ** 2
        return float(np.sqrt(np.maximum(0, 0.5 * (t + np.sqrt(np.maximum(0, u))))).max())

    @property
    def wave_count(self):
        """Harmonic series truncated to what the fins can actually resolve."""
        min_wavelength = self.min_wavelength
        ratio = self.sp("harm_ratio")
        allowed = math.floor(
            math.log(max(self.sp("wave_len") * self.short_side / min_wavelength, 1.0))
            / math.log(ratio)) + 1
        return max(1, min(int(self.sp("wave_count")), allowed))
    @property
    def wave_amp(self):    return self.sp("wave_amp") * self.intensity * self.detail_scale
    @property
    def radial_amp(self):  return self.sp("radial_amp") * self.intensity * self.detail_scale
    @property
    def min_wavelength(self):
        return FINS_PER_WAVE * self.pitch * max(1.0, self.warp_amp)
    @property
    def radial_len(self):
        return max(self.sp("radial_len") * self.short_side, self.min_wavelength)
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
    def terrace(self):     return max(0, self.terrace_steps)
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


def radial(spec, x, z):
    """Concentric rings, read in warped space like the harmonics."""
    if spec.radial_amp <= 0:
        return np.zeros_like(x, dtype=float)
    cx, cz = spread_point(spec, 0, 53, 0.28)
    r = np.sqrt((x - cx) ** 2 + (z - cz) ** 2)
    return sind(360 * r / spec.radial_len)


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
            + radial(spec, wx, wz) * spec.radial_amp
            + landscape(spec, x, z, peaks(spec))) * envelope(spec, x, z)


def norm_range(spec):
    """Field extremes measured on the same coarse grid the .scad uses."""
    i = np.arange(NORM_N + 1) / NORM_N
    xx, zz = np.meshgrid(i * spec.artwork_width, i * spec.artwork_height, indexing="ij")
    v = field_raw(spec, xx, zz)
    return float(v.min()), float(v.max())


def terrace(g, n):
    """Flat plateaus with finite-width risers; identity for n <= 1."""
    if n <= 1:
        return g
    t = g * n
    i = np.floor(t)
    f = t - i
    fs = np.clip((f - 0.5) / TERRACE_RISER + 0.5, 0, 1)
    return np.clip((i + fs) / n, 0, 1)


def field(spec, x, z, lohi=None):
    lo, hi = lohi if lohi is not None else norm_range(spec)
    t = np.clip((field_raw(spec, x, z) - lo) / max(hi - lo, 1e-9), 0, 1)
    g = np.power(t, spec.gamma)
    return np.clip(terrace(g, spec.terrace), 0, 1)
