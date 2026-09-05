// =====================================================================
// TIMING PULLEY GENERATOR -- GT2 2mm and HTD 5M
// =====================================================================
//
// Toothed pulleys, flanged or plain, with a choice of shaft bores.
//
// The tooth grooves are built from arcs rather than a copied point list.
// The construction was fitted to the published profile envelope and agrees
// with the community reference profile to within 11 microns worst case --
// about 1/40th of a 0.4mm extrusion bead, and inside printer repeatability.
// Building from arcs also means the groove resolves as finely as $fn asks,
// instead of being frozen at whatever a point list captured.
//
// Print with the axis vertical, flat on the bed. Tooth walls are then
// vertical, and both flanges are chamfered at 45 degrees on their inner
// faces, so nothing overhangs and no support is needed.
//
// Self-contained. OpenSCAD 2021.01.
// =====================================================================


/* [Belt] */

// Belt tooth system.
belt_profile = "GT2 2mm"; // [GT2 2mm, HTD 5M]

// Number of teeth. Below about 10 the belt will not wrap without binding.
teeth = 20;            // [8:1:150]

// Belt width. Common: GT2 6 or 9mm, HTD 5M 9 or 15mm.
belt_width = 6;        // [3:1:30]


/* [Flanges] */

// Rims that stop the belt walking off.
flanges = "Both sides"; // [Both sides, One side, None]

// How far the flange stands above the tooth tips.
flange_height = 1.4;   // [0.6:0.1:4.0]

// Thickness of the flange rim itself.
flange_thickness = 1.2; // [0.6:0.1:3.0]


/* [Bore] */

// Shaft profile through the middle.
bore_type = "Round"; // [Round, D-shaft, Hex, Square, REX 8mm, Bearing seat, None (solid)]

// Shaft size: diameter for Round/D, across-flats for Hex/Square, bearing outer diameter for Bearing seat. Ignored for REX.
bore_size = 5;         // [2:0.5:30]

// Depth of the flat on a D-shaft, measured in from the round.
d_flat = 0.5;          // [0.2:0.05:2.0]

// Added all round the bore. Raise if shafts are tight, lower if loose.
bore_clearance = 0.15; // [0.00:0.05:0.60]


/* [Hub] */

// A hub adds length for the grub screw to bite on.
hub = "Extended hub"; // [Extended hub, None]

// Hub length beyond the pulley body.
hub_length = 8;        // [0:1:30]

// Grub screws clamping the shaft.
set_screws = 1;        // [0:1:2]

// Metric grub screw thread size.
set_screw = "M3";      // [M3, M4, M5]


/* [Output] */

// What to generate.
output = "Pulley"; // [Pulley, Smooth idler, Fit gauge]


// =====================================================================
// PROFILE DATA
//
// Fitted arc construction. Provenance and the measured agreement with the
// reference profile are recorded in docs/profiles.md.
// =====================================================================

EPS = 0.02;
$fn = 96;

// [ pitch, pitch-line differential, half width at pitch line, groove depth,
//   crown R, crown centre y, root R, root centre x, root centre y,
//   straight-flank low point, straight-flank high point ]
// A profile with no straight flank (GT2) carries an empty flank pair.
GT2_2MM = [ 2.0, 0.254, 0.747183, 0.77171,
            0.57060, 0.20111, 0.28843, 0.84294, 0.26340, [], [] ];
HTD_5M  = [ 5.0, 0.5715, 1.89036, 2.18793,
            1.44350, 0.74443, 0.42982, 1.89039, 0.42982,
            [1.467026, 0.3556], [1.427162, 0.960967] ];

function prof() = belt_profile == "HTD 5M" ? HTD_5M : GT2_2MM;

pitch      = prof()[0];
pld        = prof()[1];
half_width = prof()[2];
depth      = prof()[3];
crown_r    = prof()[4];
crown_cy   = prof()[5];
root_r     = prof()[6];
root_cx    = prof()[7];
root_cy    = prof()[8];
flank_lo   = prof()[9];
flank_hi   = prof()[10];

has_flank = len(flank_lo) == 2;

// Pitch diameter is fixed by the belt: the pitch circle must measure exactly
// one belt pitch per tooth. Outside diameter sits inside it by the pitch line
// differential, which is where the belt's neutral axis rides above the groove.
pitch_dia   = teeth * pitch / PI;
outside_dia = pitch_dia - 2 * pld;
root_dia    = outside_dia - 2 * depth;


// =====================================================================
// TOOTH GROOVE
// =====================================================================

function arc_pts(cx, cy, r, a0, a1, n) =
    [ for (i = [0 : n]) let (a = a0 + (a1 - a0) * i / n)
        [ cx + r * cos(a), cy + r * sin(a) ] ];

// Right-hand half of the groove, from the pitch-line edge up to the apex.
// GT2 is root fillet then crown; HTD puts a straight flank between them.
function half_groove(n = 24) =
    has_flank
      ? concat(
            arc_pts(root_cx, root_cy, root_r,
                    atan2(0 - root_cy, half_width - root_cx),
                    atan2(flank_lo[1] - root_cy, flank_lo[0] - root_cx), n),
            [flank_hi],
            arc_pts(0, crown_cy, crown_r,
                    atan2(flank_hi[1] - crown_cy, flank_hi[0] - 0), 90, n))
      : concat(
            arc_pts(root_cx, root_cy, root_r,
                    atan2(0 - root_cy, half_width - root_cx) + 360,
                    169.7178, n),
            arc_pts(0, crown_cy, crown_r, 11.5015, 90, n));

// Closed groove outline. The tail below the pitch line makes the cutter
// overshoot the pulley surface, so no Boolean ever relies on coplanar faces.
function groove_profile(tail = 1.0) =
    let (h = half_groove())
    concat([[half_width, -tail]], h,
           [ for (i = [len(h) - 1 : -1 : 0]) [-h[i][0], h[i][1]] ],
           [[-half_width, -tail]]);

module groove_cutter(height) {
    translate([0, 0, -EPS])
        linear_extrude(height = height + 2 * EPS, convexity = 6)
            polygon(groove_profile());
}

module teeth_cut(height) {
    for (i = [0 : teeth - 1])
        rotate([0, 0, i * 360 / teeth])
            translate([0, outside_dia / 2, 0])
                rotate([0, 0, 180])
                    groove_cutter(height);
}


// =====================================================================
// DERIVED / GUARDED
// =====================================================================

screw_dia = set_screw == "M5" ? 5 : set_screw == "M4" ? 4 : 3;

bore_d = bore_type == "REX 8mm" ? 8 : bore_size;
// Clearance is applied to the bore, so it is added to a hole's size.
bore_fit = bore_d + 2 * bore_clearance;

flange_dia = outside_dia + 2 * flange_height;

// The hub must clear the bore and give the grub screw somewhere to live.
hub_dia = max(bore_fit + 2 * (screw_dia * 0.55 + 1.6),
              min(root_dia, bore_fit + 8));

body_h  = belt_width;
flange_bottom = (flanges == "Both sides" || flanges == "One side") ? flange_thickness : 0;
flange_top    = (flanges == "Both sides") ? flange_thickness : 0;
total_h = flange_bottom + body_h + flange_top;
hub_h   = (hub == "Extended hub") ? max(0, hub_length) : 0;


// =====================================================================
// BORE PROFILES
// =====================================================================

module hex_2d(across_flats) { circle(d = across_flats / cos(30), $fn = 6); }
module square_2d(across_flats) { square([across_flats, across_flats], center = true); }

// goBILDA's 8mm REX is defined as an 8mm round combined with a 7mm hex --
// it passes through a standard 8mm bearing but still drives positively.
module rex_2d(round_d, hex_af) {
    intersection() { circle(d = round_d); hex_2d(hex_af); }
}

module bore_2d() {
    if (bore_type == "Round")        circle(d = bore_fit);
    else if (bore_type == "D-shaft")
        intersection() {
            circle(d = bore_fit);
            translate([-bore_fit, -bore_fit / 2 - (bore_fit / 2 - d_flat)])
                square([2 * bore_fit, 2 * bore_fit]);
        }
    else if (bore_type == "Hex")     hex_2d(bore_d + 2 * bore_clearance);
    else if (bore_type == "Square")  square_2d(bore_d + 2 * bore_clearance);
    else if (bore_type == "REX 8mm") rex_2d(8 + 2 * bore_clearance, 7 + 2 * bore_clearance);
    else if (bore_type == "Bearing seat") circle(d = bore_d + 2 * bore_clearance);
}

module bore_cut(height) {
    if (bore_type != "None (solid)")
        translate([0, 0, -EPS])
            linear_extrude(height = height + 2 * EPS, convexity = 6) bore_2d();
}

module set_screw_cuts() {
    if (set_screws > 0 && hub_h > 0)
        for (i = [0 : set_screws - 1])
            rotate([0, 0, i * 360 / max(set_screws, 1)])
                translate([0, 0, total_h + hub_h / 2])
                    rotate([-90, 0, 0])
                        cylinder(h = hub_dia, d = screw_dia, $fn = 32);
}


// =====================================================================
// BODY
// =====================================================================

// Flanges are chamfered at 45 degrees on the belt-facing side. That is what
// lets the whole part print axis-up with no support: an unchamfered upper
// flange would be a flat horizontal overhang all the way round.
module flange(z, flip) {
    translate([0, 0, z]) mirror([0, 0, flip ? 1 : 0])
        union() {
            cylinder(h = flange_thickness, d = flange_dia);
            translate([0, 0, flange_thickness - EPS])
                cylinder(h = flange_height, d1 = flange_dia, d2 = outside_dia);
        }
}

module pulley_body() {
    difference() {
        union() {
            if (flange_bottom > 0) flange(0, false);
            translate([0, 0, flange_bottom])
                cylinder(h = body_h, d = outside_dia);
            if (flange_top > 0) flange(total_h, true);
            if (hub_h > 0)
                translate([0, 0, total_h - EPS])
                    cylinder(h = hub_h + EPS, d = hub_dia);
        }
        if (output != "Smooth idler")
            translate([0, 0, flange_bottom]) teeth_cut(body_h);
        bore_cut(total_h + hub_h);
        set_screw_cuts();
    }
}

// A short arc of the real pulley plus the real bore, for checking belt mesh
// and shaft fit in a couple of minutes instead of a whole part.
module fit_gauge() {
    n = min(teeth, 5);
    intersection() {
        pulley_body();
        rotate([0, 0, -n * 360 / teeth / 2])
            linear_extrude(height = total_h + hub_h + 2)
                polygon([[0, 0],
                         [outside_dia, 0],
                         [outside_dia * cos(n * 360 / teeth),
                          outside_dia * sin(n * 360 / teeth)]]);
    }
}

if (output == "Fit gauge") fit_gauge(); else pulley_body();

echo(str("PULLEY  ", belt_profile, "  ", teeth, "T  belt ", belt_width, "mm"));
echo(str("PULLEY  pitch dia ", pitch_dia, "  outside dia ", outside_dia,
         "  root dia ", root_dia));
echo(str("PULLEY  flange dia ", flange_dia, "  total height ", total_h + hub_h,
         "  bore ", bore_type, " ", bore_fit));
