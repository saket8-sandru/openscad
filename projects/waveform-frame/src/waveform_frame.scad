// =====================================================================
// LAMELLA FRAME -- framed waveform relief, one piece, no assembly
// =====================================================================
//
// A single framed panel of vertical fins whose depths follow a natural
// terrain field: scattered peaks and hollows at several scales, gently
// swirled. One print, no tiles, no keys, no glue.
//
// Eight controls. Everything else is derived and guarded.
//
// Print: back face flat on the bed, fins and frame pointing up. In that
// orientation the fins are a height field and the frame narrows as it rises,
// so nothing overhangs and no support is needed.
//
// Self-contained -- no include<>/use<>. Written for OpenSCAD 2021.01, the
// release MakerWorld's Parametric Model Maker runs.
// =====================================================================


/* [Panel] */

// Outside edge of the finished square, including the frame. Keep at or below
// 170 for an A1 mini, 240 for a 256mm bed.
panel_size = 170;      // [100:5:250]

// How far the tallest fins stand off the back panel.
relief_depth = 18;     // [6:1:40]

// Spacing between fin centres. Smaller is finer and prints slower.
fin_pitch = 7.0;       // [4.0:0.5:14.0]


/* [Design] */

// Off repeats exactly from the seed below. On rolls a new landscape on every
// render -- the seed it picked is printed in the console so you can keep it.
randomize = "Off - repeat the seed below"; // [Off - repeat the seed below, On - new every render]

// Which landscape to generate, when randomize is Off.
seed = 7;              // [1:1:199]

// Fine detail. Low is smooth and dune-like, high is craggier.
texture = 1.0;         // [0.40:0.05:1.60]


/* [Frame] */

// Width of the frame border. 0 removes the frame entirely.
frame_width = 10;      // [0:1:25]

// How far the frame stands off the back panel. Set it BELOW the relief depth
// and the tallest peaks break out past the frame, which reads as a sculpture
// in a frame; set it above and the relief sits sunk inside a box, which is
// what the average fin -- around 55% of the relief depth -- makes it look like.
frame_depth = 11;      // [4:1:50]


// =====================================================================
// CONSTANTS AND DERIVED VALUES
// =====================================================================

EPS = 0.02;
BACK_THICKNESS = 3.0;    // fixed: thick enough to stay flat, thin enough to be cheap
NOZZLE = 0.4;
FIN_CONVEXITY = 12;      // preview only; a wavy fin crosses a ray many times
FRAME_TAPER = 2.2;       // frame narrows toward the front: moulding look, and
                         // it means the frame can never overhang while printing

function clamp(v, lo, hi) = max(lo, min(hi, v));
function clamp01(v) = clamp(v, 0, 1);
function vsum(v, i = 0) = i >= len(v) ? 0 : v[i] + vsum(v, i + 1);

// Angles are reduced before sin() so the hash gives identical results on every
// OpenSCAD build. Without this, two platforms' range reduction differ by ~1e-10,
// which this hash multiplies by 44000 into visibly different artwork.
function wrap360(a) = a - 360 * floor(a / 360);

function hash01(n, s) =
    let (a0 = sin(wrap360(n * 12.9898 + s * 78.233 + 41.7)) * 43758.5453,
         a  = a0 - floor(a0),
         c0 = sin(wrap360(a * 311.7 + n * 74.7 + s * 19.19)) * 24634.6345)
    c0 - floor(c0);

// Surprise mode uses OpenSCAD's own unseeded rands(). Rolled once, here, so a
// single render is internally consistent.
active_seed = randomize == "On - new every render"
    ? floor(rands(1, 200, 1)[0])
    : seed;

frame_w   = clamp(frame_width, 0, panel_size / 4);
has_frame = frame_w >= 3;

// The art area inside the frame.
opening   = panel_size - 2 * frame_w;

// Fin count is an integer over the opening, so both end gaps match.
fin_n     = max(4, floor(opening / fin_pitch));
pitch     = opening / fin_n;

// Two floors, as on the tiled version: a fin thinner than two extrusion widths
// will not print as a wall, and a slot narrower than about one and a half
// nozzle widths fuses shut instead of printing as a gap.
min_fin   = max(2 * NOZZLE, 0.8);
min_gap   = max(0.6, 1.4 * NOZZLE);
fin_t     = clamp(pitch * 0.76, min_fin, pitch - min_gap);
fin_gap   = pitch - fin_t;

// A floor under the relief keeps every fin joined to the back panel with real
// material rather than tapering away to nothing.
min_relief  = max(1.2, 0.12 * relief_depth);
relief_span = max(0.5, relief_depth - min_relief);

frame_h   = max(4, frame_depth);
z_samples = clamp(round(opening / 1.6), 24, 300);

// Hanging keyholes live in the SIDE rails, which run the full height of the
// panel, so the slot has room to travel. A vertical keyhole cannot fit in the
// top rail, which is only as tall as the frame is wide.
key_head  = min(8.4, frame_w - 3.5);
key_shank = key_head * 0.52;
key_depth = min(4.0, BACK_THICKNESS + frame_h - 2.0);
key_drop  = 9;
has_keyholes = has_frame && key_head >= 5.5 && frame_h >= 6;


// =====================================================================
// FIELD -- natural terrain from scattered points
//
// Three octaves: a few large landforms, more medium features, more small ones,
// each weaker than the last. That size mixture is what reads as landscape; one
// uniform blob size reads as bubble wrap.
//
// Points are placed independently rather than spread on a sequence. With this
// many of them clumping is not a defect -- real terrain clusters -- and
// spreading them made every seed share one arrangement.
// =====================================================================

// count, size (fraction of the opening), weight
OCTAVES = [ [5, 0.30, 1.00], [9, 0.165, 0.62], [16, 0.092, 0.38] ];

// No feature is allowed to be finer than the fins can represent, or
// neighbouring fins jump instead of flowing.
min_feature = 1.6 * pitch;

function octave_points(oi) =
    let (spec = OCTAVES[oi], n = spec[0], sfrac = spec[1], base = oi * 211)
    [ for (k = [0 : n - 1])
        [ (0.02 + 0.96 * hash01(k * 6 + base + 1, active_seed)) * opening,
          (0.02 + 0.96 * hash01(k * 6 + base + 2, active_seed)) * opening,
          (hash01(k * 6 + base + 4, active_seed) < 0.5 ? 1 : -1)
            * (0.6 + 0.4 * hash01(k * 6 + base + 5, active_seed))
            * (oi == 0 ? 1 : texture),
          max(min_feature,
              sfrac * opening * (0.75 + 0.5 * hash01(k * 6 + base + 3, active_seed))) ] ];

PTS = [ for (oi = [0 : len(OCTAVES) - 1]) octave_points(oi) ];

// One gentle swirl. Enough to pull round blobs into lobes and ridges; not
// enough to read as a vortex.
SWIRL = [ (0.25 + 0.5 * hash01(active_seed * 29 + 7, active_seed)) * opening,
          (0.25 + 0.5 * hash01(active_seed * 31 + 9, active_seed)) * opening ];
SWIRL_R = 0.55 * opening;

function warp(p) =
    let (ox = p[0] - SWIRL[0], oz = p[1] - SWIRL[1],
         f = exp(-(ox * ox + oz * oz) / (2 * SWIRL_R * SWIRL_R)) * 0.5)
    [ p[0] + f * (-oz), p[1] + f * ox ];

function octave_value(w, oi) =
    let (pts = PTS[oi])
    vsum([ for (q = pts)
        q[2] * exp(-(pow(w[0] - q[0], 2) + pow(w[1] - q[1], 2))
                   / (2 * q[3] * q[3])) ]);

function field_raw(x, z) =
    let (w = warp([x, z]))
    vsum([ for (oi = [0 : len(OCTAVES) - 1])
        OCTAVES[oi][2] * octave_value(w, oi) ]);

// Normalised against the field's own range on a coarse grid, so relief_depth
// means what it says whatever the seed rolls.
NORM_N = 22;
NORM = [ for (i = [0 : NORM_N], j = [0 : NORM_N])
         field_raw(i / NORM_N * opening, j / NORM_N * opening) ];
F_LO = min(NORM);
F_HI = max(NORM);

function field01(x, z) = clamp01((field_raw(x, z) - F_LO) / max(F_HI - F_LO, 1e-9));
function relief_at(x, z) = min_relief + relief_span * field01(x, z);


// =====================================================================
// GEOMETRY
// =====================================================================

// Fin cross-section in (depth, height). The back edge stops part-way into the
// back panel so the two overlap in real volume instead of sharing a face.
fin_back = -BACK_THICKNESS * 0.5;

function fin_profile(x) =
    let (dz = opening / z_samples)
    concat([ [fin_back, 0] ],
           [ for (i = [0 : z_samples]) [ relief_at(x, dz * i), dz * i ] ],
           [ [fin_back, opening] ]);

module fin(i) {
    x = (i + 0.5) * pitch;
    translate([frame_w + x - fin_t / 2, 0, frame_w])
        rotate([90, 0, 90])
            linear_extrude(height = fin_t, convexity = FIN_CONVEXITY)
                polygon(fin_profile(x));
}

module back_panel() {
    translate([0, -BACK_THICKNESS, 0])
        cube([panel_size, BACK_THICKNESS, panel_size]);
}

module frame() {
    if (has_frame)
        difference() {
            cube([panel_size, frame_h, panel_size]);
            // Opening widens toward the front, so the frame narrows as it
            // rises: a moulding profile that also cannot overhang.
            hull() {
                translate([frame_w, -EPS, frame_w])
                    cube([opening, EPS, opening]);
                translate([frame_w - FRAME_TAPER, frame_h, frame_w - FRAME_TAPER])
                    cube([opening + 2 * FRAME_TAPER, EPS, opening + 2 * FRAME_TAPER]);
            }
        }
}

// Keyhole recessed into the back of a side rail: the head passes through the
// circle, then the panel drops and the head is captured behind the slot.
module keyhole(cx, cz) {
    translate([cx, -BACK_THICKNESS - EPS, cz])
        rotate([-90, 0, 0])
            cylinder(h = key_depth + EPS, d = key_head, $fn = 36);
    hull() for (dz = [0, -key_drop])
        translate([cx, -BACK_THICKNESS - EPS, cz + dz])
            rotate([-90, 0, 0])
                cylinder(h = key_depth + EPS, d = key_shank, $fn = 24);
}

module keyholes() {
    if (has_keyholes) {
        z = panel_size - frame_w - 14;
        keyhole(frame_w / 2, z);
        keyhole(panel_size - frame_w / 2, z);
    }
}

module panel() {
    difference() {
        union() {
            back_panel();
            frame();
            for (i = [0 : fin_n - 1]) fin(i);
        }
        keyholes();
    }
}

panel();

echo(str("LAMELLA FRAME  seed ", active_seed, "  (", randomize, ")"));
if (randomize == "On - new every render")
    echo(str("LAMELLA FRAME  >> to keep this one: randomize = Off, seed = ",
             active_seed, " <<"));
echo(str("LAMELLA FRAME  panel ", panel_size, "mm  opening ", opening,
         "mm  frame ", frame_w, "x", frame_h, "mm"));
echo(str("LAMELLA FRAME  fins ", fin_n, "  pitch ", pitch,
         "  thickness ", fin_t, "  gap ", fin_gap,
         "  relief ", min_relief, "..", relief_depth,
         "  keyholes ", has_keyholes ? "yes" : "no"));
