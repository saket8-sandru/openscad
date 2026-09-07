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

// Tooth counts generated side by side when output = "Size set". 0 skips a slot.
set_teeth_1 = 16;      // [0:1:150]
set_teeth_2 = 20;      // [0:1:150]
set_teeth_3 = 30;      // [0:1:150]
set_teeth_4 = 40;      // [0:1:150]


/* [Flanges] */

// Rims that stop the belt walking off.
flanges = "Both sides"; // [Both sides, One side, None]

// How far the flange stands above the tooth tips.
flange_height = 1.4;   // [1.0:0.5:10.0]

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
bore_clearance = 0.15; // [0.000:0.025:0.600]


/* [Hub] */

// A hub adds length for the grub screw to bite on.
hub = "Extended hub"; // [Extended hub, None]

// Hub length beyond the pulley body.
hub_length = 8;        // [0:1:30]

// How the hub grips the shaft. A plain screw hole does nothing in plastic --
// there is no thread to hold it -- so every option here uses real hardware or
// real elasticity instead.
clamp = "Split clamp"; // [Split clamp, Captive nut, Collet shell, None]

// Screw size used by the chosen clamp.
clamp_screw = "M3";    // [M3, M4, M5]


/* [Output] */

// What to generate.
output = "Pulley"; // [Pulley, Fit gauge, Collet only, Size set]


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
function pitch_dia_of(n)   = n * pitch / PI;
function outside_dia_of(n) = pitch_dia_of(n) - 2 * pld;

pitch_dia   = pitch_dia_of(teeth);
outside_dia = outside_dia_of(teeth);
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

// All the grooves are laid out as one 2D drawing and extruded once, rather
// than extruded one at a time. Geometrically it is the same cutter -- measured
// against the per-groove version at 150 teeth, the two surfaces agree to 0.14
// microns and the volumes to 1.6e-7 relative -- but CGAL then has a single
// solid to subtract instead of one per tooth. A 150T pulley went from 394s to
// 50s, which is the difference between rendering on MakerWorld and timing out.
module teeth_cut(height, n = 0) {
    nn = (n == 0) ? teeth : n;
    r  = outside_dia_of(nn) / 2;
    translate([0, 0, -EPS])
        linear_extrude(height = height + 2 * EPS, convexity = 6)
            for (i = [0 : nn - 1])
                rotate(i * 360 / nn) translate([0, r]) rotate(180)
                    polygon(groove_profile());
}


// =====================================================================
// DERIVED / GUARDED
// =====================================================================

screw_dia = clamp_screw == "M5" ? 5 : clamp_screw == "M4" ? 4 : 3;
// Across-flats and thickness of the matching hex nut (ISO 4032 nominal).
nut_af    = clamp_screw == "M5" ? 8.0 : clamp_screw == "M4" ? 7.0 : 5.5;
nut_thick = clamp_screw == "M5" ? 4.7 : clamp_screw == "M4" ? 3.2 : 2.4;
// Clearance hole, so the screw pulls the two halves together rather than
// threading into the near half and jacking them apart.
screw_free = screw_dia + 0.6;

bore_d = bore_type == "REX 8mm" ? 8 : bore_size;
// Clearance is applied to the bore, so it is added to a hole's size.
bore_fit = bore_d + 2 * bore_clearance;

// --- bore versus tooth count -------------------------------------------
//
// A bore wider than the tooth roots eats the toothed body outright. What comes
// back is a bare ring with no teeth on it -- watertight, single-bodied, so no
// mesh check catches it -- or, once the bore reaches through the flanges too, a
// ring plus loose fragments. Measured: 8T GT2 with the default 5mm bore exported
// as 2 disconnected bodies; a 16mm bearing seat on 20T exported as a plain hub.
//
// The bore is deliberately NOT clamped to fit. A pulley whose bore quietly
// shrank would not go on the shaft it was printed for, and a part that fits
// nothing is worse than a render that stops and says why.
function r2(x) = round(x * 100) / 100;

MIN_RIM = 0.8;   // two extrusion widths of material between bore and tooth root

// "Size set" prints several tooth counts at once, so the smallest one decides.
set_ok = [ for (n = [set_teeth_1, set_teeth_2, set_teeth_3, set_teeth_4])
               if (n >= 8) n ];
governing_teeth = (output == "Size set" && len(set_ok) > 0) ? min(set_ok) : teeth;
governing_root  = outside_dia_of(governing_teeth) - 2 * depth;

// The collet sleeve is a separate part with no teeth, so the rule does not
// apply to it; neither does it to a solid blank.
bore_matters = bore_type != "None (solid)" && output != "Collet only";
max_bore     = governing_root - 2 * MIN_RIM - 2 * bore_clearance;
min_teeth_for_bore = ceil((bore_fit + 2 * MIN_RIM + 2 * pld + 2 * depth) * PI / pitch);

assert(!bore_matters || bore_fit + 2 * MIN_RIM <= governing_root,
       str("Bore too wide for this pulley. ", governing_teeth, "T ", belt_profile,
           " has a ", r2(governing_root), "mm root circle, which leaves room for a ",
           r2(max_bore), "mm bore. Lower bore_size to that, or raise teeth to ",
           min_teeth_for_bore, "."));

// The hub has to clear the bore AND carry the clamp screw beside it, since a
// screw through the middle would just hit the shaft. That makes a clamping hub
// noticeably fatter than a plain one -- real clamping pulleys are the same.
clamp_offset = bore_fit / 2 + screw_free / 2 + 0.8;  // screw axis, off centre
hub_dia = (clamp == "None")
    ? max(bore_fit + 4, min(root_dia, bore_fit + 8))
    : 2 * (clamp_offset + screw_free / 2 + 1.4);

body_h  = belt_width;

// A 45-degree chamfer rises as far as it stands proud, so a flange taller than
// half the belt channel drives its chamfer through the middle of the channel and
// out the far side. The tooth cutter then slices the overlap into loose
// fragments -- flange_height 10 on a 6mm belt gave 21 disconnected bodies, one
// per tooth, and the top flange hung 1mm below the plate. The height is capped
// rather than the chamfer alone: capping just the chamfer would steepen it past
// 45 degrees, which is the thing that makes this part printable without support.
max_flange_height = ((flanges == "Both sides") ? body_h / 2 : body_h) - 0.4;
fh = min(flange_height, max_flange_height);

flange_dia = outside_dia + 2 * fh;

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

// --- clamping ----------------------------------------------------------
//
// Split clamp: a slot through the hub wall to the bore lets the hub flex, and
// one screw pulls the two sides together. Grip is round the whole shaft rather
// than one dent from a grub screw point, and it cannot mar a steel shaft.
//
// Captive nut: same slot, but the far side holds a hex nut so the screw has a
// real thread to pull against.
//
// Collet shell: a separate split sleeve drops inside the hub and the screw
// squeezes it onto the shaft. Costs a second part, but the grip is a full
// circumference and the shaft never touches printed threads at all.

clamp_z   = total_h + hub_h / 2;
slot_w    = 1.2;                     // flex gap; must be > one extrusion width
collet_t  = 2.4;                     // sleeve wall
collet_od = bore_fit + 2 * collet_t;

module clamp_slot() {
    // Runs from the bore out through the hub wall, on one side only.
    translate([-slot_w / 2, 0, clamp_z - hub_h / 2 - EPS])
        cube([slot_w, hub_dia, hub_h + 2 * EPS]);
}

module clamp_cuts() {
    if (hub_h > 0 && clamp != "None") {
        clamp_slot();
        // Screw runs beside the bore, crossing the slot. Through the middle it
        // would foul the shaft and clamp nothing.
        translate([0, clamp_offset, clamp_z]) rotate([0, 90, 0])
            cylinder(h = hub_dia * 1.4, d = screw_free, center = true, $fn = 32);
        if (clamp == "Captive nut")
            translate([hub_dia / 2 - nut_thick - 0.6, clamp_offset, clamp_z])
                rotate([0, 90, 0])
                    cylinder(h = nut_thick + 0.4, d = nut_af / cos(30), $fn = 6);
        if (clamp == "Collet shell")
            translate([0, 0, total_h - EPS])
                cylinder(h = hub_h + 2 * EPS, d = collet_od + 2 * bore_clearance);
    }
}

// The separate sleeve for the collet option. Printed upright, split on one side.
module collet() {
    difference() {
        cylinder(h = hub_h, d = collet_od);
        translate([0, 0, -EPS]) linear_extrude(hub_h + 2 * EPS, convexity = 6) bore_2d();
        translate([-slot_w / 2, 0, -EPS]) cube([slot_w, collet_od, hub_h + 2 * EPS]);
    }
}


// =====================================================================
// BODY
// =====================================================================

// Flanges are chamfered at 45 degrees on the belt-facing side. That is what
// lets the whole part print axis-up with no support: an unchamfered upper
// flange would be a flat horizontal overhang all the way round.
module flange(z, flip, n = 0) {
    od = (n == 0) ? outside_dia : outside_dia_of(n);
    fd = od + 2 * fh;
    translate([0, 0, z]) mirror([0, 0, flip ? 1 : 0])
        union() {
            cylinder(h = flange_thickness, d = fd);
            translate([0, 0, flange_thickness - EPS])
                cylinder(h = fh, d1 = fd, d2 = od);
        }
}

module pulley_body(n = 0) {
    nn = (n == 0) ? teeth : n;
    difference() {
        union() {
            if (flange_bottom > 0) flange(0, false, nn);
            translate([0, 0, flange_bottom])
                cylinder(h = body_h, d = outside_dia_of(nn));
            if (flange_top > 0) flange(total_h, true, nn);
            if (hub_h > 0)
                translate([0, 0, total_h - EPS])
                    cylinder(h = hub_h + EPS, d = hub_dia);
        }
        translate([0, 0, flange_bottom]) teeth_cut(body_h, nn);
        bore_cut(total_h + hub_h);
        clamp_cuts();
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

// Several tooth counts laid out on one plate. Each is a full pulley at the
// current settings, spaced by its own diameter so nothing collides.
set_counts = [ set_teeth_1, set_teeth_2, set_teeth_3, set_teeth_4 ];

module size_set() {
    gap = 6;
    for (i = [0 : len(set_counts) - 1])
        if (set_counts[i] >= 8) {
            n = set_counts[i];
            od_i = n * pitch / PI - 2 * pld;
            // running offset: sum of the earlier diameters plus gaps
            prev = (i == 0) ? 0 :
                   vsum_d([ for (j = [0 : i - 1])
                       (set_counts[j] >= 8 ? set_counts[j] * pitch / PI - 2 * pld
                                           : 0) + gap ]);
            translate([prev + od_i / 2 + 2 * flange_height, 0, 0])
                pulley_body(n);
        }
}

function vsum_d(v, i = 0) = i >= len(v) ? 0 : v[i] + vsum_d(v, i + 1);

if (output == "Fit gauge")        fit_gauge();
else if (output == "Collet only") collet();
else if (output == "Size set")    size_set();
else                              pulley_body();

// The collet is a second printed part; say so rather than leaving it implicit.
if (clamp == "Collet shell" && output == "Pulley")
    echo("PULLEY  Collet shell selected: also export output = \"Collet only\"");

echo(str("PULLEY  ", belt_profile, "  ", teeth, "T  belt ", belt_width, "mm"));
echo(str("PULLEY  pitch dia ", pitch_dia, "  outside dia ", outside_dia,
         "  root dia ", root_dia));
echo(str("PULLEY  flange dia ", flange_dia, "  total height ", total_h + hub_h,
         "  bore ", bore_type, " ", bore_fit));
