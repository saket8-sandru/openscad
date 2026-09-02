#!/usr/bin/env python3
"""
fieldlab -- fast exploration of the scalar depth field behind the rib panel.

The OpenSCAD generator is the product; this is the design instrument. Rendering
a candidate field in OpenSCAD costs tens of seconds, which is far too slow to
iterate on the *look*. Here the same field maths runs in NumPy and renders in
well under a second, so architectures can be compared honestly before any of it
is committed to .scad.

The maths in `field()` is the reference implementation. The OpenSCAD port must
agree with it numerically -- tools/crosscheck.py proves that it does.

Coordinates are global artwork millimetres: x across the panel, z up it. Tiling
never rebases them, which is what keeps the field continuous across seams.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field

import numpy as np

TAU = 2.0 * math.pi


# --------------------------------------------------------------------------
# deterministic pseudo-randomness
# --------------------------------------------------------------------------
# Feature placement must be reproducible from a seed alone, and must produce
# identical numbers in OpenSCAD, which has no RNG. A hash of the index is the
# portable way to do that: fract(sin(n) * k) is exactly reproducible in both
# languages using only functions OpenSCAD 2021.01 has.

def hash01(n: float, seed: float) -> float:
    """Deterministic pseudo-random in [0,1). Portable to OpenSCAD."""
    v = math.sin((n + 1.0) * 127.1 + seed * 311.7) * 43758.5453123
    return v - math.floor(v)


def hash_range(n: float, seed: float, lo: float, hi: float) -> float:
    return lo + (hi - lo) * hash01(n, seed)


# --------------------------------------------------------------------------
# field configuration
# --------------------------------------------------------------------------

@dataclass
class FieldSpec:
    width: float = 400.0          # artwork width, mm
    height: float = 400.0         # artwork height, mm
    seed: float = 7.0

    # --- vortex / swirl layer: macrostructure, the "eye" formations ---
    vortex_count: int = 2
    vortex_strength: float = 1.0   # ~radians of rotation at the core
    vortex_radius: float = 0.38    # fraction of the panel's short side

    # --- harmonic layer: optical movement and interference ---
    wave_count: int = 3
    wave_amplitude: float = 1.0
    wave_length: float = 0.55      # fraction of short side, primary wavelength
    harmonic_ratio: float = 1.9    # each extra wave is this much shorter
    harmonic_falloff: float = 0.55 # and this much weaker
    flow_direction: float = 25.0   # degrees
    direction_spread: float = 34.0 # degrees between successive waves
    phase: float = 0.0

    # --- landscape layer: peaks, valleys, calm vs intense ---
    peak_count: int = 3
    peak_strength: float = 1.0
    valley_strength: float = 0.8
    feature_scale: float = 0.42    # fraction of short side

    # --- shaping ---
    envelope_strength: float = 0.55  # how strongly calm/intense regions vary
    terrace_steps: int = 0           # 0 = smooth; >1 = topographic banding
    gamma: float = 1.0               # <1 lifts valleys, >1 deepens them


def _short_side(spec: FieldSpec) -> float:
    return min(spec.width, spec.height)


def _vortices(spec: FieldSpec):
    """Placed pseudo-randomly but biased away from the extreme edges, so the
    swirl cores land inside the artwork where they can actually be seen."""
    out = []
    s = _short_side(spec)
    for k in range(spec.vortex_count):
        cx = hash_range(k * 3 + 0, spec.seed, 0.22, 0.78) * spec.width
        cz = hash_range(k * 3 + 1, spec.seed, 0.22, 0.78) * spec.height
        sign = 1.0 if hash01(k * 3 + 2, spec.seed) < 0.5 else -1.0
        out.append((cx, cz, sign * spec.vortex_strength, spec.vortex_radius * s))
    return out


def _peaks(spec: FieldSpec):
    out = []
    s = _short_side(spec)
    for m in range(spec.peak_count):
        cx = hash_range(m * 4 + 40, spec.seed, 0.12, 0.88) * spec.width
        cz = hash_range(m * 4 + 41, spec.seed, 0.12, 0.88) * spec.height
        # Alternate peaks and hollows so the surface has both, not just bumps.
        up = hash01(m * 4 + 42, spec.seed) < 0.55
        amp = spec.peak_strength if up else -spec.valley_strength
        amp *= hash_range(m * 4 + 43, spec.seed, 0.6, 1.0)
        sigma = spec.feature_scale * s * hash_range(m * 4 + 44, spec.seed, 0.7, 1.3)
        out.append((cx, cz, amp, sigma))
    return out


def warp(spec: FieldSpec, x: np.ndarray, z: np.ndarray):
    """Single-step tangential displacement -- the swirl layer.

    Summing displacements evaluated at the *original* point (rather than
    warping iteratively, vortex after vortex) keeps the map order-independent
    and smooth, and stops strong vortices from folding space over itself.
    """
    dx = np.zeros_like(x)
    dz = np.zeros_like(z)
    for cx, cz, strength, radius in _vortices(spec):
        ox, oz = x - cx, z - cz
        r2 = ox * ox + oz * oz
        fall = np.exp(-r2 / (2.0 * radius * radius))
        # Tangential unit vector, times r, times falloff: near the core this is
        # a rigid rotation by `strength` radians, decaying smoothly outward.
        dx += strength * fall * (-oz)
        dz += strength * fall * (ox)
    return x + dx, z + dz


def harmonics(spec: FieldSpec, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Sum of plane waves at related-but-not-identical angles.

    Fanning the directions apart is what turns a plain corrugation into
    interference: crests of successive waves cross rather than reinforce.
    """
    s = _short_side(spec)
    total = np.zeros_like(x)
    norm = 0.0
    for j in range(max(1, spec.wave_count)):
        angle = math.radians(spec.flow_direction + j * spec.direction_spread)
        lam = spec.wave_length * s / (spec.harmonic_ratio ** j)
        amp = spec.harmonic_falloff ** j
        ux, uz = math.cos(angle), math.sin(angle)
        proj = x * ux + z * uz
        total += amp * np.sin(TAU * proj / lam + spec.phase + j * 1.7)
        norm += amp
    return total / max(norm, 1e-9)


def landscape(spec: FieldSpec, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Smooth blobs: the large peaks and hollows that set overall composition."""
    total = np.zeros_like(x)
    norm = 0.0
    for cx, cz, amp, sigma in _peaks(spec):
        r2 = (x - cx) ** 2 + (z - cz) ** 2
        total += amp * np.exp(-r2 / (2.0 * sigma * sigma))
        norm += abs(amp)
    return total / max(norm, 1e-9)


def field(spec: FieldSpec, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """The composed field, normalised to roughly [0,1]."""
    wx, wz = warp(spec, x, z)

    # Harmonics read the warped space, so the swirl bends the wave crests into
    # S-curves and eyes. The landscape reads unwarped space, so the large
    # composition stays put instead of being smeared by the vortices.
    fh = harmonics(spec, wx, wz) * spec.wave_amplitude
    fl = landscape(spec, x, z)

    combined = fh + fl

    # Envelope: modulate amplitude with a slow function so the panel has calm
    # regions as well as busy ones, instead of uniform activity everywhere.
    if spec.envelope_strength > 0:
        s = _short_side(spec)
        env = 0.5 + 0.5 * np.sin(TAU * (x * 0.37 + z * 0.62) / (2.15 * s)
                                 + spec.seed)
        env = 1.0 - spec.envelope_strength * (1.0 - env)
        combined = combined * env

    # Normalise to [0,1] using the actual observed range, so max_depth means
    # what it says regardless of how the layers happened to add up.
    lo, hi = combined.min(), combined.max()
    out = (combined - lo) / max(hi - lo, 1e-9)

    if spec.gamma != 1.0:
        out = np.power(out, spec.gamma)

    if spec.terrace_steps and spec.terrace_steps > 1:
        n = spec.terrace_steps
        out = np.floor(out * n) / (n - 1)
        out = np.clip(out, 0.0, 1.0)

    return out
