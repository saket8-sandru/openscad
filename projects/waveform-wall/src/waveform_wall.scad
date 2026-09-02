// =====================================================================
// LAMELLA -- Parametric Waveform Wall Panel Generator
// =====================================================================
//
// Generates ribbed wall sculpture of any size. A continuous mathematical
// field decides how far each vertical fin stands off the backing, so many
// simple fins together reconstruct one flowing three-dimensional surface.
//
// Artwork larger than the print bed is split into tiles automatically. The
// field is always evaluated in GLOBAL artwork coordinates, so the surface
// runs unbroken across every seam, and tile edges are placed to land in the
// gap between two fins -- which makes vertical seams invisible from the front.
//
// Self-contained by design: no include<>/use<>, because MakerWorld's
// Parametric Model Maker does not handle local include trees reliably.
// Written against OpenSCAD 2021.01, the release PMM runs.
//
// Print orientation: back face flat on the bed, fins pointing up. In that
// orientation the fins are a height field, so every layer is fully supported
// by the one below and the part needs no support material at all.
// =====================================================================


/* [Artwork] */

// Overall artwork width in mm. Anything larger than the bed is split into
// tiles automatically; the default is a single tile, so a first print needs
// no assembly at all.
artwork_width = 170;   // [80:10:1600]

// Overall artwork height in mm.
artwork_height = 170;  // [80:10:1600]

// How far the tallest fins stand off the backing. The single biggest driver of how dramatic the piece looks.
max_relief = 20;       // [8:1:60]


/* [Style] */

// Overall character of the surface.
style = "Ripple"; // [Flow, Vortex, Dune, Liquid, Interference, Ripple]

// Changes the composition completely while keeping the chosen style. Every value is a different artwork.
seed = 7;       // [1:1:199]

// Boldness of the relief. Below 1 calms the surface, above 1 exaggerates it.
intensity = 1.0; // [0.40:0.05:1.60]

// Rotates the whole flow direction.
flow_angle = 25; // [0:5:355]


/* [Fins] */

// Target spacing between fin centres. Smaller = finer, more optical, longer print.
fin_pitch = 8.0;    // [4.0:0.5:20.0]

// Share of each pitch left open as a gap. Low reads as one sculpted surface; high reads as stripes.
gap_fraction = 0.24; // [0.12:0.01:0.45]

// Vertical resolution of the fin edge. Higher is smoother and slower.
fin_smoothness = 1.6; // [0.8:0.1:4.0]


/* [Printing] */

// Sets the largest tile that will be generated.
printer = "A1 mini (180 x 180)"; // [A1 mini (180 x 180), A1 / P1 / X1 (256 x 256), Custom]

// Largest tile edge when printer is set to Custom.
custom_tile_max = 200; // [80:5:240]

// Nozzle diameter, used to guard minimum fin thickness.
nozzle = 0.4;  // [0.2:0.2:0.8]

// Backing plate thickness.
back_thickness = 2.4; // [1.6:0.2:5.0]


/* [Assembly] */

// Hidden dovetail keys join tiles behind the panel, with no glue.
joint_style = "Hidden dovetail keys"; // [Hidden dovetail keys, None (butt joint)]

// Extra clearance on the keys. Raise if keys are tight, lower if loose.
key_fit = 0.20; // [0.00:0.05:0.60]

// Keyhole slots let the panel hang straight onto screw heads.
wall_mount = "Keyhole slots"; // [Keyhole slots, None]


/* [Output] */

// What to generate.
output = "Assembled preview"; // [Assembled preview, Single tile, All tiles laid out, Joining keys, Fit coupon]

// Which tile column to export (Single tile only), counting from the left.
tile_col = 1; // [1:1:16]

// Which tile row to export (Single tile only), counting from the bottom.
tile_row = 1; // [1:1:16]


/* [Advanced] */
// These are neutral at their defaults; the Style preset drives the field.

// Adds or removes swirl centres.
extra_vortices = 0;      // [-2:1:3]

// Scales the swirl strength.
swirl_scale = 1.0;       // [0.0:0.05:2.0]

// Scales the fine secondary detail.
detail_scale = 1.0;      // [0.0:0.05:2.0]

// Lifts valleys (below 1) or deepens them (above 1).
relief_gamma = 1.0;      // [0.60:0.05:1.80]

// Quantises the relief into flat contour bands. 0 is off. Terracing fights the
// fins -- the surface is already quantised across the panel, and quantising it
// in depth too reads as digital error rather than contours unless the fins are
// coarse. Kept as an option, deliberately not used by any preset.
terrace_steps = 0;       // [0:1:10]


// =====================================================================
// CONSTANTS
// =====================================================================

EPS = 0.02;          // boolean overlap; never rely on coplanar contact
// Cutter size. Deliberately modest: at 1e6 the ratio between coordinate and
// feature size is seven orders of magnitude, and CGAL was emitting zero-area
// triangles. It only has to exceed the artwork.
function big() = 4 * (artwork_width + artwork_height + max_relief + 100);

// Style table columns. Named so the table stays readable.
I_WAVE_COUNT   = 0;
I_WAVE_AMP     = 1;
I_WAVE_LEN     = 2;   // fraction of the artwork's short side
I_HARM_RATIO   = 3;   // each successive wave is this much shorter
I_HARM_FALLOFF = 4;   // ...and this much weaker
I_DIR_SPREAD   = 5;   // degrees between successive wave directions
I_RADIAL_AMP   = 6;   // concentric ring component
I_RADIAL_LEN   = 7;   // ring spacing, fraction of short side
I_VORTEX_N     = 8;
I_VORTEX_STR   = 9;
I_VORTEX_RAD   = 10;  // fraction of short side
I_PEAK_N       = 11;
I_PEAK_STR     = 12;
I_VALLEY_STR   = 13;
I_FEATURE      = 14;  // fraction of short side
I_ENVELOPE     = 15;
I_GAMMA        = 16;

//                    wav  amp   len  rat   fal  spr  rAmp rLen  vn  vstr vrad  pn  pstr vstr feat  env  gam
STYLE_TABLE = [
/* Flow         */ [  3, 1.00, 0.55, 1.9, 0.55, 34, 0.00, 0.40,  2, 1.00, 0.38,  3, 1.00, 0.80, 0.42, 0.55, 1.00 ],
/* Vortex       */ [  2, 0.75, 0.70, 2.1, 0.45, 28, 0.00, 0.40,  3, 1.25, 0.34,  2, 0.70, 0.90, 0.38, 0.35, 0.95 ],
/* Dune         */ [  3, 0.95, 0.68, 2.2, 0.42, 22, 0.00, 0.40,  2, 0.85, 0.44,  4, 1.10, 0.95, 0.44, 0.40, 1.10 ],
/* Liquid       */ [  4, 1.00, 0.48, 1.7, 0.62, 41, 0.00, 0.40,  2, 1.15, 0.42,  3, 0.85, 0.85, 0.36, 0.45, 0.90 ],
/* Interference */ [  5, 1.20, 0.42, 1.5, 0.72, 47, 0.00, 0.40,  1, 0.45, 0.55,  2, 0.55, 0.55, 0.55, 0.25, 1.00 ],
/* Ripple       */ [  2, 0.38, 0.80, 2.0, 0.50, 30, 1.00, 0.24,  1, 0.70, 0.45,  3, 0.80, 0.80, 0.42, 0.30, 1.00 ],
];

function style_index() =
      style == "Flow"         ? 0
    : style == "Vortex"       ? 1
    : style == "Dune"         ? 2
    : style == "Liquid"       ? 3
    : style == "Interference" ? 4
    : style == "Ripple"       ? 5
    :                           0;

function sp(i) = STYLE_TABLE[style_index()][i];


// =====================================================================
// SMALL UTILITIES
// =====================================================================

function clamp(v, lo, hi) = max(lo, min(hi, v));
function clamp01(v) = clamp(v, 0, 1);

// OpenSCAD 2021.01 has no sum(); recursion depth here is the number of
// field features, which is single digits.
function vsum1(v, i = 0) = i >= len(v) ? 0      : v[i] + vsum1(v, i + 1);
function vsum2(v, i = 0) = i >= len(v) ? [0, 0] : v[i] + vsum2(v, i + 1);

// Deterministic pseudo-random in [0,1). OpenSCAD has no RNG, and feature
// placement must be reproducible from the seed alone -- including in the
// NumPy reference implementation, which mirrors this exactly (degrees and all).
function hash01(n, s) =
    let (a0 = sin(n * 12.9898 + s * 78.233 + 41.7) * 43758.5453,
         a  = a0 - floor(a0),
         c0 = sin(a * 311.7 + n * 74.7 + s * 19.19) * 24634.6345)
    c0 - floor(c0);

function hash_range(n, s, lo, hi) = lo + (hi - lo) * hash01(n, s);

// R2 low-discrepancy sequence (the 2D generalisation of the golden ratio).
// Independent random draws clump: at seed 33 two counter-rotating swirls
// landed 25mm apart with a 152mm radius and cancelled each other out. R2
// guarantees well-spread points for ANY count, so every seed composes --
// the seed shifts the whole sequence rather than re-rolling each point.
R2_A1 = 0.7548776662;   // 1 / plastic number
R2_A2 = 0.5698402910;   // 1 / plastic number squared

function r2_frac(k, offset, alpha) =
    let (v = offset + (k + 1) * alpha) v - floor(v);

// A point on the artwork, inset from the edges so features read as features
// rather than as things falling off the corners.
function spread_point(k, seed_offset, inset) =
    [ (inset + (1 - 2 * inset) * r2_frac(k, hash01(seed * 3 + seed_offset, seed), R2_A1)) * artwork_width,
      (inset + (1 - 2 * inset) * r2_frac(k, hash01(seed * 5 + seed_offset, seed), R2_A2)) * artwork_height ];


// =====================================================================
// DERIVED / GUARDED PARAMETERS
//
// Everything below is computed. The Customizer sliders above are bounded,
// but bounds alone are not protection -- these guards are what keep the
// geometry valid for every combination a user can reach.
// =====================================================================

short_side = min(artwork_width, artwork_height);

// A fin thinner than two extrusion widths will not print as a solid wall.
min_fin_thickness = max(2 * nozzle, 0.8);

// --- tiling -------------------------------------------------------------
// PMM's auto-arrange gets unreliable past roughly 240 x 235mm, so tiles are
// held below the bed size rather than at it.
tile_limit =
      printer == "A1 mini (180 x 180)"      ? 172
    : printer == "A1 / P1 / X1 (256 x 256)" ? 230
    :                                         clamp(custom_tile_max, 80, 240);

tile_cols = max(1, ceil(artwork_width  / tile_limit));
tile_rows = max(1, ceil(artwork_height / tile_limit));

tile_w = artwork_width  / tile_cols;
tile_h = artwork_height / tile_rows;

// --- fins ---------------------------------------------------------------
// Fins per tile is an integer, so a tile edge always falls exactly on a fin
// pitch boundary -- i.e. in the middle of a gap, never through a fin. That
// is what makes vertical seams disappear.
fins_per_tile = max(4, round(tile_w / fin_pitch));
pitch         = tile_w / fins_per_tile;
fin_count     = fins_per_tile * tile_cols;

fin_thickness = max(min_fin_thickness, pitch * (1 - clamp(gap_fraction, 0.10, 0.60)));
fin_gap       = pitch - fin_thickness;

// --- relief -------------------------------------------------------------
// A floor under the relief keeps every fin attached to the backing with real
// material, instead of tapering to a knife edge where the field bottoms out.
min_relief = max(1.2, 0.12 * max_relief);
relief_span = max(0.5, max_relief - min_relief);

// Vertical sampling of the fin edge.
z_samples = clamp(round(tile_h / max(0.4, fin_smoothness)), 24, 400);

// --- field ---------------------------------------------------------------
f_wave_amp   = sp(I_WAVE_AMP) * intensity * detail_scale;
f_wave_len   = sp(I_WAVE_LEN) * short_side;
f_harm_ratio = sp(I_HARM_RATIO);
f_harm_fall  = sp(I_HARM_FALLOFF);
f_dir_spread = sp(I_DIR_SPREAD);
f_radial_amp = sp(I_RADIAL_AMP) * intensity * detail_scale;

f_vortex_n   = max(0, sp(I_VORTEX_N) + extra_vortices);
f_vortex_str = sp(I_VORTEX_STR) * swirl_scale;
f_vortex_rad = sp(I_VORTEX_RAD) * short_side;

f_peak_n     = max(0, sp(I_PEAK_N));
f_peak_str   = sp(I_PEAK_STR) * intensity;
f_valley_str = sp(I_VALLEY_STR) * intensity;
f_feature    = sp(I_FEATURE) * short_side;

f_envelope   = clamp(sp(I_ENVELOPE), 0, 0.95);
f_terrace    = max(0, terrace_steps);
f_gamma      = clamp(sp(I_GAMMA) * relief_gamma, 0.4, 2.5);


// =====================================================================
// FIELD ENGINE
//
// Three layers, each doing a job the others cannot:
//   warp      -- swirl centres that bend space, producing the large
//                S-curves and eye formations (the macrostructure)
//   harmonics -- interfering plane waves read in warped space, producing
//                optical movement and secondary detail
//   landscape -- smooth peaks and hollows in unwarped space, setting the
//                overall composition of calm and busy regions
//
// Coordinates are always GLOBAL artwork millimetres. Nothing here knows
// about tiles, which is precisely why the surface survives being cut up.
// =====================================================================

// Swirl centres, kept away from the extreme edges so they read as features
// rather than as corner artefacts.
function vortices() =
    f_vortex_n <= 0 ? [] :
    // Swirl directions ALTERNATE rather than being drawn independently. Three
    // independent coin flips leave a quarter of all seeds co-rotating, which
    // reads as one lopsided smear; counter-rotating neighbours shear against
    // each other and produce the S-curves this design is built around. The
    // hash only chooses which way the alternation starts.
    let (flip = hash01(seed * 7 + 3, seed) < 0.5 ? 1 : -1)
    [ for (k = [0 : f_vortex_n - 1])
        let (c = spread_point(k, 13, 0.22))
        [ c[0], c[1],
          (k % 2 == 0 ? 1 : -1) * flip * f_vortex_str,
          f_vortex_rad ] ];

// Peaks and hollows. Alternating the sign gives the surface both, instead of
// a field of bumps sitting on a flat plain.
function peaks() =
    f_peak_n <= 0 ? [] :
    // Same reasoning as the swirls: alternating guarantees the surface has
    // hollows as well as peaks, instead of a field of bumps on a flat plain.
    let (pflip = hash01(seed * 11 + 5, seed) < 0.5)
    [ for (m = [0 : f_peak_n - 1])
        let (up  = (m % 2 == 0) == pflip,
             amp = (up ? f_peak_str : -f_valley_str)
                   * hash_range(m * 4 + 43, seed, 0.6, 1.0),
             c   = spread_point(m, 29, 0.12))
        [ c[0], c[1],
          amp,
          f_feature * hash_range(m * 4 + 44, seed, 0.7, 1.3) ] ];

VORTICES = vortices();
PEAKS    = peaks();

// Tangential displacement summed at the ORIGINAL point. Warping iteratively,
// one vortex after another, would be order-dependent and can fold space over
// itself; this single-step form stays smooth however strong the swirl gets.
function warp(p) =
    len(VORTICES) == 0 ? p :
    p + vsum2([ for (v = VORTICES)
        let (ox = p[0] - v[0],
             oz = p[1] - v[1],
             r2 = ox * ox + oz * oz,
             fall = exp(-r2 / (2 * v[3] * v[3])))
        [ v[2] * fall * (-oz), v[2] * fall * ox ] ]);

// --- anti-aliasing ------------------------------------------------------
// The fins sample the field at discrete positions, so the field must carry no
// detail finer than the fins can represent. Two things set that limit, and
// only measuring both gets it right:
//
//   1. the shortest harmonic wavelength, and
//   2. how much the domain warp COMPRESSES space -- a swirl squeezes a legal
//      wavelength into an illegal one, and measured amplification runs from
//      1.2x up to 3.0x at the strongest swirl settings.
//
// Guarding on (1) alone left four of six styles aliasing, with neighbouring
// fins jumping instead of flowing. So the warp's Jacobian is sampled on a
// coarse grid and its largest singular value taken as the worst-case
// frequency multiplier.
//
// The harmonic series is then truncated wherever the next term would fall
// below FINS_PER_WAVE fins. Resolution therefore follows the fins: a finer
// pitch earns finer detail, and a coarse panel stays clean automatically.
FINS_PER_WAVE = 3.2;

// Largest singular value of the 2x2 Jacobian [[a,b],[c,d]], in closed form.
function jacobian_gain(a, b, c, d) =
    let (t = a * a + b * b + c * c + d * d,
         u = pow(a * a + b * b - c * c - d * d, 2) + 4 * pow(a * c + b * d, 2))
    sqrt(max(0, 0.5 * (t + sqrt(max(0, u)))));

function warp_gain_at(x, z, h) =
    let (px = warp([x + h, z]), mx = warp([x - h, z]),
         pz = warp([x, z + h]), mz = warp([x, z - h]))
    jacobian_gain((px[0] - mx[0]) / (2 * h), (pz[0] - mz[0]) / (2 * h),
                  (px[1] - mx[1]) / (2 * h), (pz[1] - mz[1]) / (2 * h));

WARP_N = 17;
WARP_AMP = len(VORTICES) == 0 ? 1 :
    max([ for (i = [0 : WARP_N], j = [0 : WARP_N])
          warp_gain_at(i / WARP_N * artwork_width,
                       j / WARP_N * artwork_height,
                       0.25) ]);

min_wavelength = FINS_PER_WAVE * pitch * max(1, WARP_AMP);

f_wave_count = max(1, min(sp(I_WAVE_COUNT),
    floor(ln(max(sp(I_WAVE_LEN) * short_side / min_wavelength, 1))
          / ln(sp(I_HARM_RATIO))) + 1));


// Plane waves fanned apart in direction. Fanning is what turns a plain
// corrugation into interference: successive crests cross instead of stacking.
function harmonics(p) =
    let (terms = [ for (j = [0 : f_wave_count - 1])
            let (ang  = flow_angle + j * f_dir_spread,
                 lam  = max(4, f_wave_len / pow(f_harm_ratio, j)),
                 amp  = pow(f_harm_fall, j),
                 proj = p[0] * cos(ang) + p[1] * sin(ang))
            [ amp * sin(360 * proj / lam + j * 97.4), amp ] ],
         num = vsum1([ for (t = terms) t[0] ]),
         den = vsum1([ for (t = terms) t[1] ]))
    num / max(den, 1e-9);

// Concentric rings. Read in warped space like the harmonics, so the swirl
// bends them into the ovals and hooks that make this style read as flow rather
// than as a bullseye. The ring spacing gets the same anti-alias floor as the
// harmonics -- rings tighter than the fins can resolve would alias just as
// badly.
f_radial_len = max(sp(I_RADIAL_LEN) * short_side, min_wavelength);
RADIAL_CENTRE = spread_point(0, 53, 0.28);

function radial(p) =
    f_radial_amp <= 0 ? 0 :
    sin(360 * norm(p - RADIAL_CENTRE) / f_radial_len);

function landscape(p) =
    len(PEAKS) == 0 ? 0 :
    let (terms = [ for (q = PEAKS)
            let (r2 = pow(p[0] - q[0], 2) + pow(p[1] - q[1], 2))
            [ q[2] * exp(-r2 / (2 * q[3] * q[3])), abs(q[2]) ] ],
         num = vsum1([ for (t = terms) t[0] ]),
         den = vsum1([ for (t = terms) t[1] ]))
    num / max(den, 1e-9);

// Slow amplitude modulation, so the panel has quiet regions as well as busy
// ones rather than uniform activity edge to edge.
function envelope(p) =
    f_envelope <= 0 ? 1 :
    let (e = 0.5 + 0.5 * sin(360 * (p[0] * 0.37 + p[1] * 0.62)
                             / (2.15 * short_side) + seed * 57.3))
    1 - f_envelope * (1 - e);

function field_raw(x, z) =
    let (p = [x, z])
    let (w = warp(p))
    (harmonics(w) * f_wave_amp + radial(w) * f_radial_amp + landscape(p)) * envelope(p);

// --- normalisation -------------------------------------------------------
// The layers are summed, so their combined range depends on the style, the
// seed and every slider. Normalising against the field's ACTUAL range is what
// makes max_relief mean what it says in every configuration.
//
// The range is measured on a coarse global grid: fixed cost regardless of how
// large the artwork is, and identical for every tile -- which matters, because
// two tiles normalised differently would not meet at the seam.
NORM_N = 26;
NORM_SAMPLES = [ for (i = [0 : NORM_N], j = [0 : NORM_N])
                 field_raw(i / NORM_N * artwork_width,
                           j / NORM_N * artwork_height) ];
FIELD_LO = min(NORM_SAMPLES);
FIELD_HI = max(NORM_SAMPLES);

// Terracing with SOFT risers. Hard quantisation put neighbouring fins on
// different levels with nothing in between, which read as broken blocks rather
// than contours. Keeping the plateaus flat but giving each riser a finite
// width restores a continuous surface, and at riser = 1 this is the identity,
// so smooth styles are unaffected.
TERRACE_RISER = 0.34;

function terrace(g, n) =
    n <= 1 ? g :
    let (t = g * n, i = floor(t), f = t - i,
         fs = clamp01((f - 0.5) / TERRACE_RISER + 0.5))
    clamp01((i + fs) / n);

function field01(x, z) =
    let (t = clamp01((field_raw(x, z) - FIELD_LO) / max(FIELD_HI - FIELD_LO, 1e-9)),
         g = pow(t, f_gamma))
    clamp01(terrace(g, f_terrace));

// Relief depth in mm at a point on the artwork.
function relief_at(x, z) = min_relief + relief_span * field01(x, z);


// =====================================================================
// JOINT / MOUNT DERIVED VALUES
// =====================================================================

joints_on = (joint_style == "Hidden dovetail keys") && (tile_cols > 1 || tile_rows > 1);

// A dovetail key needs material to live in. Rather than let a thin backing
// silently produce a paper-thin key, the backing is raised to a workable
// thickness whenever keys are actually being generated.
back_t = joints_on ? max(back_thickness, 2.4) : back_thickness;

key_skin      = max(0.8, back_t * 0.35);          // skin left toward the front
key_thickness = max(1.0, back_t - key_skin);      // pocket depth from the back face

key_reach = 13;    // how far the key extends either side of the seam
key_wide  = 13;    // width at the flared ends
key_waist = 8;     // width at the seam
key_spacing_target = 95;

// Fins are the only thing holding the mount region together, so keyholes sit
// where there is material to carry them: near the top edge of a tile.
mount_on        = (wall_mount == "Keyhole slots");
mount_head_dia  = 8.4;    // clearance for a typical #6 / 4mm screw head
mount_shank_dia = 4.4;
mount_depth     = 3.6;    // recess depth measured from the back face
mount_boss      = max(0, mount_depth + 1.2 - back_t);  // added on the FRONT face
mount_drop      = 9;      // vertical travel from head hole to hanging position


// =====================================================================
// PROFILE / GEOMETRY UTILITIES
// =====================================================================

// The fin's cross-section in (depth, height). The back edge stops part-way
// into the backing rather than flush with it: the two solids then overlap in
// real volume instead of sharing a coplanar face, which is what keeps the
// union robust (and the back face of the panel is defined by the backing
// alone, so it stays dead flat).
fin_back = -back_t * 0.5;

function fin_profile(x, z0, z1, n) =
    let (span = z1 - z0, dz = span / n)
    concat(
        [ [fin_back, 0] ],
        [ for (i = [0 : n]) [ relief_at(x, z0 + dz * i), dz * i ] ],
        [ [fin_back, span] ]
    );

// Global centre line of fin i.
function fin_x(i) = (i + 0.5) * pitch;

// Fins belonging to tile column c. Because fins-per-tile is an integer, the
// tile edge lands exactly on a pitch boundary -- i.e. in the middle of a gap,
// never through a fin. That is what makes a vertical seam invisible.
function fin_range(c) = [ c * fins_per_tile, (c + 1) * fins_per_tile - 1 ];

module fin(x, z0, z1) {
    translate([x - fin_thickness / 2, 0, z0])
        rotate([90, 0, 90])
            linear_extrude(height = fin_thickness)
                polygon(fin_profile(x, z0, z1, z_samples));
}

// Bowtie outline, centred on the origin, waist lying on the seam (x = 0).
// Wide ends resist the tiles pulling apart; the waist is what sits in the joint.
function bowtie_pts(grow) =
    let (r = key_reach + grow, w = key_wide / 2 + grow, t = key_waist / 2 + grow)
    [ [-r, -w], [-r, w], [0, t], [r, w], [r, -w], [0, -t] ];

module bowtie(grow, thickness) {
    linear_extrude(height = thickness) polygon(bowtie_pts(grow));
}

// Key stations along a seam of the given length, inset from its ends.
function key_stations(seam_len) =
    let (n = max(2, round(seam_len / key_spacing_target)))
    [ for (i = [0 : n - 1]) seam_len * (i + 0.5) / n ];


// =====================================================================
// KEY POCKETS
//
// Pockets are cut into the BACK face. Printed back-down they are simply a
// void rising from the build plate, closed by a short bridge across the
// widest part of the bowtie -- about 13mm, well inside what bridges cleanly.
// =====================================================================

module vertical_seam_pockets(seam_x) {
    for (s = key_stations(artwork_height))
        translate([seam_x, -back_t - EPS, s])
            rotate([-90, 0, 0])
                bowtie(key_fit / 2, key_thickness + EPS);
}

module horizontal_seam_pockets(seam_z) {
    for (s = key_stations(artwork_width))
        translate([s, -back_t - EPS, seam_z])
            rotate([-90, 0, 0])
                rotate([0, 0, 90])
                    bowtie(key_fit / 2, key_thickness + EPS);
}

module all_key_pockets() {
    if (joints_on) {
        for (c = [1 : max(1, tile_cols - 1)])
            if (c < tile_cols) vertical_seam_pockets(c * tile_w);
        for (r = [1 : max(1, tile_rows - 1)])
            if (r < tile_rows) horizontal_seam_pockets(r * tile_h);
    }
}


// =====================================================================
// WALL MOUNTING
//
// A keyhole recessed from the back, reinforced by a boss added on the FRONT
// of the backing. Putting the reinforcement forward keeps the back face
// perfectly flat, which is what lets the tile print straight onto the bed --
// a boss on the back would lift the whole panel off the plate.
// =====================================================================

module keyhole_cut() {
    // Head passes through here...
    translate([0, -back_t - EPS, 0])
        rotate([-90, 0, 0])
            cylinder(h = mount_depth + EPS, d = mount_head_dia, $fn = 36);
    // ...then the tile drops, and the head is captured behind this slot.
    // Built as a hull of two cylinders rather than an offset() of a
    // two-point polygon: the latter is a degenerate outline and was the
    // source of every zero-area triangle in the exported mesh.
    hull() for (dz = [0, -mount_drop])
        translate([0, -back_t - EPS, dz])
            rotate([-90, 0, 0])
                cylinder(h = mount_depth + EPS, d = mount_shank_dia, $fn = 24);
}

function mount_points(c, r) =
    let (x0 = c * tile_w, z0 = r * tile_h,
         zt = z0 + tile_h - 18)
    [ [x0 + tile_w * 0.25, zt], [x0 + tile_w * 0.75, zt] ];

module mount_bosses(c, r) {
    // The boss follows the WHOLE keyhole, slot travel included. Covering only
    // the head circle leaves the slot cutting clean through the backing, which
    // both breaks the mount and makes the tile a genus-2 solid.
    if (mount_on && mount_boss > 0)
        for (p = mount_points(c, r))
            hull() for (dz = [0, -mount_drop])
                translate([p[0], 0, p[1] + dz])
                    rotate([-90, 0, 0])
                        cylinder(h = mount_boss, d = mount_head_dia + 7, $fn = 36);
}

module mount_cuts(c, r) {
    if (mount_on)
        for (p = mount_points(c, r))
            translate([p[0], 0, p[1]]) keyhole_cut();
}


// =====================================================================
// TILE
// =====================================================================

// Solid body of one tile, before pockets and keyholes are removed.
module tile_body(c, r) {
    x0 = c * tile_w;
    z0 = r * tile_h;
    rng = fin_range(c);

    // Backing.
    translate([x0, -back_t, z0]) cube([tile_w, back_t, tile_h]);

    // Fins, clipped to this tile's z band. Their x positions come from the
    // global pitch, so neighbouring tiles continue the same rhythm exactly.
    for (i = [rng[0] : rng[1]]) fin(fin_x(i), z0, z0 + tile_h);

    mount_bosses(c, r);
}

module tile(c, r) {
    // Clipping by intersection with the tile's own cell, rather than
    // subtracting four oversized slabs: fewer operations, and no huge
    // coordinates for CGAL to lose precision on. It also halves any key
    // pocket that straddles a seam, which is exactly what is wanted.
    intersection() {
        difference() {
            tile_body(c, r);
            all_key_pockets();
            mount_cuts(c, r);
        }
        translate([c * tile_w, -back_t - 1, r * tile_h])
            cube([tile_w, back_t + max_relief + 2, tile_h]);
    }
}


// =====================================================================
// KEYS
// =====================================================================

module joining_keys() {
    n_v = joints_on ? (tile_cols - 1) * len(key_stations(artwork_height)) : 0;
    n_h = joints_on ? (tile_rows - 1) * len(key_stations(artwork_width)) : 0;
    // A single-tile artwork needs no keys, but an empty output is an export
    // failure rather than a useful answer, so lay out one spare. Printing a
    // spare or two is good practice for the multi-tile case anyway.
    total = max(1, n_v + n_h);
    per_row = max(1, ceil(sqrt(total)));
    // Keys are flat plates and print lying down, so they are laid out in the
    // XY plane -- a different "up" from the tiles, which print back-down.
    for (i = [0 : total - 1])
        translate([(i % per_row) * (2 * key_reach + 6),
                   floor(i / per_row) * (key_wide + 6), 0])
            bowtie(0, key_thickness);
}


// =====================================================================
// OUTPUT
// =====================================================================

module assembled() {
    for (c = [0 : tile_cols - 1], r = [0 : tile_rows - 1]) tile(c, r);
}

module all_tiles_laid_out() {
    gap = 8;
    // Each tile already sits at its artwork position, so only the extra
    // separation has to be added.
    for (c = [0 : tile_cols - 1], r = [0 : tile_rows - 1])
        translate([c * gap, 0, r * gap]) tile(c, r);
}

// Fit coupon: two short strips that meet at a REAL seam, plus a real key.
//
// An earlier version was one strip with a whole bowtie pocket in the middle.
// That tested a harder print than the product ever asks for -- a tile only
// ever contains half a pocket, so the coupon's bridge was 26mm where the real
// one is 13mm. Splitting it into two halves reproduces the actual printed
// condition, and turns the coupon into a better test as well: butt the strips
// together and it shows the key fit, the seam gap, and whether the surface
// really does continue across the join.
//
// Fins keep their global positions, so the two halves carry the same stretch
// of field they would in the finished piece.
module coupon_strip(i0, n, h, seam_at_right) {
    x0 = i0 * pitch;
    w = n * pitch;
    seam = seam_at_right ? x0 + w : x0;
    intersection() {
        difference() {
            union() {
                translate([x0, -back_t, 0]) cube([w, back_t, h]);
                for (i = [i0 : i0 + n - 1]) fin(fin_x(i), 0, h);
            }
            translate([seam, -back_t - EPS, h / 2])
                rotate([-90, 0, 0]) bowtie(key_fit / 2, key_thickness + EPS);
        }
        translate([x0, -back_t - 1, 0])
            cube([w, back_t + max_relief + 2, h]);
    }
}

module fit_coupon() {
    n = 3;
    h = 46;
    w = n * pitch;
    part_gap = 12;
    coupon_strip(0, n, h, true);
    translate([part_gap, 0, 0]) coupon_strip(n, n, h, false);
    // Loose key, clear of both strips. The bowtie is centred on its own
    // origin and reaches key_reach either side, so that reach is part of the
    // offset; it is rotated so its thickness runs along the depth axis, which
    // is what lets it lie flat on the same plate as the strips.
    translate([2 * w + part_gap + 12 + key_reach, -back_t, key_wide])
        rotate([-90, 0, 0]) bowtie(0, key_thickness);
}

module main() {
    if (output == "Assembled preview")        assembled();
    else if (output == "Single tile")         tile(clamp(tile_col, 1, tile_cols) - 1,
                                                   clamp(tile_row, 1, tile_rows) - 1);
    else if (output == "All tiles laid out")  all_tiles_laid_out();
    else if (output == "Joining keys")        joining_keys();
    else if (output == "Fit coupon")          fit_coupon();
    else                                      assembled();
}

main();

echo(str("LAMELLA  artwork ", artwork_width, "x", artwork_height,
         "  tiles ", tile_cols, "x", tile_rows, " @ ", tile_w, "x", tile_h,
         "  fins ", fin_count, " pitch ", pitch,
         " thickness ", fin_thickness, " gap ", fin_gap,
         "  relief ", min_relief, "..", max_relief));
