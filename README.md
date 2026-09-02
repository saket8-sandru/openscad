# MakerWorld CAD Studio

Parametric, print-ready product design in OpenSCAD, built to the standards in
the studio brief (`CLAUDE.md`, supplied via session config).

Each product lives under `projects/` and is validated by a scripted parameter
matrix before it is called finished.

## Products

| Project | What it is | Status |
| --- | --- | --- |
| [`waveform-wall`](projects/waveform-wall/docs/README.md) | **LAMELLA** — parametric ribbed wave wall-art generator. Any size, tiled automatically, with vertical seams that measure invisible. 22 controls. | CAD-validated, not yet print-tested |
| [`waveform-frame`](projects/waveform-frame/docs/README.md) | **LAMELLA FRAME** — the simple sibling. One framed piece off one plate, natural terrain field, 8 controls. | CAD-validated, not yet print-tested |

The two share a field engine in spirit but not in code: the frame version uses
scattered terrain points rather than interfering waves, because independent
placement is what reads as natural, and it drops tiling entirely.

## Layout

```
tools/                     shared harness
    scadkit.py             render + mesh validation, and the matrix runner
    fieldlab.py            NumPy mirror of the OpenSCAD field engine
    ribpreview.py          fast 2.5D preview of how a field reads as fins
    crosscheck.py          proves fieldlab agrees with the .scad
    seamcheck.py           proves tiles of one artwork actually join
    overhangcheck.py       proves a part prints without support
projects/<product>/
    src/<product>.scad     the model; self-contained so it drops straight into
                           MakerWorld's Parametric Model Maker
    validation.json        the parameter matrix and its pass/fail expectations
    exports/               generated meshes
    previews/              generated PNGs for design review
    docs/                  README, dimensions, validation, listing copy
```

## Toolchain

| Tool | Version | Notes |
| --- | --- | --- |
| OpenSCAD | 2021.01 | Stable release; the one MakerWorld's Parametric Model Maker runs. Nightly-only features are deliberately avoided. |
| trimesh | 5.1.0 | Mesh validation. |
| scipy / numpy / networkx | 1.17.1 / 2.4.6 / 3.6.1 | Connected components, field maths, mesh splitting. |
| xvfb | — | OpenSCAD 2021.01 needs an X server for PNG export; STL export does not. |

```bash
apt-get install -y openscad xvfb
pip3 install numpy scipy trimesh pillow networkx
```

## Using the harness

```bash
# the gate a design must pass
python3 tools/scadkit.py matrix projects/<product>/validation.json

# one-offs
python3 tools/scadkit.py render  src/part.scad out.stl -D wall_thickness=3.0
python3 tools/scadkit.py preview src/part.scad out.png --camera iso
python3 tools/scadkit.py check   out.stl --watertight --bodies 1
```

Named cameras: `iso`, `iso_rear`, `front`, `rear`, `left`, `right`, `top`,
`bottom`.

`render` sets `--hardwarnings`; `preview` does not. A warning that only breaks
export therefore shows up in the matrix rather than in a preview — which is the
right way round, but worth knowing when a preview looks fine and an export
fails.

### validation.json

```json
{
  "name": "product name",
  "scad": "src/product.scad",
  "cases": [
    {
      "name": "default",
      "params": { "wall_thickness": 2.4 },
      "expect": { "watertight": true, "bodies": 1, "max_bbox": [180, 180, 180] }
    }
  ]
}
```

Expectations: `watertight`, `bodies`, `max_bbox`, `min_bbox`, `max_volume_cm3`,
`no_degenerate` (default on), `max_degenerate` (explicit allowance). The matrix
should cover the corners of the parameter space and every shipped preset, not
just the default.

## Validation status vocabulary

Kept honest deliberately:

- **CAD-validated** — compiles, renders, exports, mesh checks pass.
- **Prototype-ready** — CAD-validated, and design review found no blocking issues.
- **Print-tested** — an actual print exists and was measured or used.

A model is never described as fitting a real object until a physical print says
so.
