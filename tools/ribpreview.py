#!/usr/bin/env python3
"""
ribpreview -- 2.5D preview of how a rib field will actually read as an object.

A grayscale plot of the scalar field is misleading: it shows the maths, not the
sculpture. What a viewer sees is a row of fins, each a flat face at a different
depth, with shaded side walls and shadowed gaps between them. This renders that
directly, which is the only way to catch the failure mode that matters -- a
field that looks lovely as a heightmap but reads as |||||||| once ribbed.

Not a replacement for real OpenSCAD renders; a fast filter before them.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import fieldlab
from fieldlab import FieldSpec


def rib_positions(spec: FieldSpec, rib_count: int, rib_thickness: float):
    """Rib centre lines, evenly pitched across the artwork width."""
    pitch = spec.width / rib_count
    centres = (np.arange(rib_count) + 0.5) * pitch
    return centres, pitch


def sample_ribs(spec: FieldSpec, rib_count: int, rows: int) -> np.ndarray:
    """Field sampled at every rib centre, down the full artwork height.

    Shape (rows, rib_count), values in [0,1]. Sampling at the rib *centre* is
    what the OpenSCAD generator does too, so this previews the real geometry
    rather than an idealised continuous surface.
    """
    centres, _ = rib_positions(spec, rib_count, 0.0)
    z = np.linspace(0.0, spec.height, rows)
    xx, zz = np.meshgrid(centres, z)
    return fieldlab.field(spec, xx, zz)


def render(spec: FieldSpec, rib_count: int = 64, rib_thickness: float = 2.6,
           max_depth: float = 22.0, px_w: int = 900, px_h: int = 900,
           view_angle: float = 26.0) -> Image.Image:
    """Render the ribbed panel as seen from slightly off-axis.

    The off-axis view is deliberate: face-on, every fin front is parallel to the
    wall and the relief nearly vanishes. The side walls revealed by a ~25 degree
    view are what make the depth legible, and they are what a listing photo
    would show.
    """
    rows = px_h
    depth01 = sample_ribs(spec, rib_count, rows)
    depth_mm = depth01 * max_depth

    pitch_px = px_w / rib_count
    thick_px = max(1.0, pitch_px * (rib_thickness / (spec.width / rib_count)))
    tan_view = math.tan(math.radians(view_angle))
    # mm of depth -> px of revealed side wall
    mm_to_px = (px_w / spec.width) * tan_view

    img = np.zeros((rows, px_w, 3), dtype=np.float32)

    # Palette: a warm off-white filament under a soft key light from the left.
    face_col = np.array([0.93, 0.91, 0.87])
    side_col = np.array([0.52, 0.50, 0.48])
    back_col = np.array([0.13, 0.13, 0.15])

    xs = np.arange(px_w)
    for i in range(rib_count):
        left = i * pitch_px
        face_lo, face_hi = left, left + thick_px

        d = depth_mm[:, i]
        # Ambient occlusion proxy: a fin sunk between deeper neighbours sees
        # less light. Uses the true neighbour depths, so valleys go dark as a
        # group -- which is what produces readable macrostructure.
        dl = depth_mm[:, i - 1] if i > 0 else d
        dr = depth_mm[:, i + 1] if i < rib_count - 1 else d
        occl = np.clip(1.0 - 0.55 * np.clip((np.maximum(dl, dr) - d) / max(max_depth, 1e-6), 0, 1), 0.25, 1.0)
        lift = 0.45 + 0.55 * (d / max(max_depth, 1e-6))
        face_shade = np.clip(lift * occl, 0.0, 1.0)

        m_face = (xs >= face_lo) & (xs < face_hi)
        img[:, m_face, :] = (face_col[None, None, :] * face_shade[:, None, None])

        # Side wall revealed in the gap to the right of this fin, proportional
        # to how much this fin stands proud of its right-hand neighbour.
        step = np.clip(d - dr, 0.0, None)
        wall_px = np.clip(step * mm_to_px, 0.0, max(pitch_px - thick_px, 0.0))
        gap_lo = face_hi
        gap_hi = left + pitch_px

        gap_mask = (xs >= gap_lo) & (xs < gap_hi)
        if not gap_mask.any():
            continue
        gap_idx = xs[gap_mask]
        rel = (gap_idx - gap_lo)[None, :]                  # (1, gapw)
        is_wall = rel < wall_px[:, None]                   # (rows, gapw)

        wall_shade = np.clip(0.55 + 0.45 * (d / max(max_depth, 1e-6)), 0, 1)[:, None]
        # Floor of the slot: not flat black. A shallow slot between two fins of
        # similar depth stays open to the light; a deep one self-shadows. Using
        # the deeper neighbour as the occluder keeps this physical, and stops
        # the preview from punishing wide gaps harder than reality does.
        slot = np.clip(np.maximum(d, dr) - np.minimum(d, dr), 0.0, None)
        openness = np.clip(1.0 - slot / max(0.45 * max_depth, 1e-6), 0.0, 1.0)
        floor_shade = (0.18 + 0.52 * openness)[:, None]
        gap_px = np.where(
            is_wall[:, :, None],
            side_col[None, None, :] * wall_shade[:, :, None],
            back_col[None, None, :] + (side_col - back_col)[None, None, :] * floor_shade[:, :, None],
        )
        img[:, gap_mask, :] = gap_px

    img = np.clip(img, 0.0, 1.0)
    img = np.power(img, 1 / 2.2)  # to sRGB-ish
    return Image.fromarray((img * 255).astype(np.uint8))


def contact_sheet(entries, cols: int = 3, cell: int = 440,
                  label_h: int = 30) -> Image.Image:
    """Grid of labelled previews, for comparing candidates side by side."""
    rows = math.ceil(len(entries) / cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (24, 24, 27))
    draw = ImageDraw.Draw(sheet)
    for n, (label, im) in enumerate(entries):
        r, c = divmod(n, cols)
        y = r * (cell + label_h)
        sheet.paste(im.resize((cell, cell), Image.LANCZOS), (c * cell, y))
        draw.text((c * cell + 8, y + cell + 8), label, fill=(235, 235, 235))
    return sheet


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ribs", type=int, default=64)
    ap.add_argument("--depth", type=float, default=22.0)
    args = ap.parse_args()
    render(FieldSpec(), rib_count=args.ribs, max_depth=args.depth).save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
