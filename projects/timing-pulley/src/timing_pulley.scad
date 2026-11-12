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
//
// The ceiling is a render-time limit, not a geometry one. Tooth count is the
// only parameter that really drives render cost: 150T took 394s with the old
// per-groove cutter and 50s with the current one, and 75T lands around 17-34s
// depending on how loaded the machine is. And 75T HTD 5M is already 121mm
// across, so past here the plate runs out before the render budget does.
teeth = 20;            // [8:1:75]

// Belt width. Common: GT2 6, 9 or 12mm; HTD 5M 9, 15 or 25mm.
//
// This is what the BELT GETS: the channel is built taller than this so the
// flange chamfers sit outside it, not inside. Earlier it was the channel
// height, so two 1.4mm chamfers ate into it and a "6mm" pulley left about
// 3.2mm of full-depth tooth for a 6mm belt. That was wrong.
belt_width = 6;        // [3:1:30]

// Side play between the belt and the flanges. The belt must not be pinched,
// and a printed flange is never perfectly flat.
belt_clearance = 0.5;  // [0:0.1:2.0]

// Tooth counts generated side by side when output = "Size set". 0 skips a slot.
// These are four pulleys on one plate, so the total width is checked against
// the plate as well -- four legal counts can still be an illegal plate.
set_teeth_1 = 16;      // [0:1:75]
set_teeth_2 = 20;      // [0:1:75]
set_teeth_3 = 30;      // [0:1:75]
set_teeth_4 = 40;      // [0:1:75]


/* [Flanges] */

// Rims that stop the belt walking off. There is no "none": an unflanged pulley
// is an idler, and this is not one.
flanges = "Both sides"; // [Both sides, One side]

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

// Corner relief for the cornered bores -- hex, square and REX. A nozzle cannot
// turn a sharp inside corner, so it leaves a fillet of material exactly where
// a shaft's corner needs to go, and the shaft will not seat. A small circle
// cut at each corner gives the nozzle somewhere to turn into. The slider does
// not reach zero: a cornered bore without relief does not fit its shaft, so
// there is nothing to offer.
corner_relief = 0.6;   // [0.20:0.05:1.5]

// Fillet radius on the bore's top and bottom edges -- the edges a shaft meets
// going in. A printed hole has a lip at each mouth whatever the bore measures,
// the first layer squashing outward and the last sagging inward, and without
// this the shaft lands on that lip instead of on the bore. The slider does not
// reach zero, for the same reason the relief does not.
bore_fillet = 0.6;     // [0.20:0.1:3.0]

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
clamp = "Split clamp"; // [Split clamp, Collet shell, None]

// Screw size used by the chosen clamp.
clamp_screw = "M3";    // [M3, M4, M5]

// Depth of the flat seats counterbored into the hub for the screw head and the
// nut. Without them both land on the hub's curved, steeply angled outside and
// cannot pull square -- which is no clamp at all. Nothing under 2mm gives a
// head anything real to pull against.
screw_seat_depth = 2.0; // [1.0:0.1:6.0]


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
//
// 0.4 over nominal: M3 3.4, M4 4.4, M5 5.4. The M4 figure is the user's, and
// the others follow it. Note the hole prints on its side here, since the part
// prints axis-up, so expect it a little under nominal and a little oval at the
// top. Open it with a 4.4mm bit if a screw binds rather than growing the model.
screw_free = screw_dia + 0.4;

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

// Socket head cap screw head diameter (ISO 4762).
head_dia = clamp_screw == "M5" ? 8.5 : clamp_screw == "M4" ? 7.0 : 5.5;

// A seat has to take whichever is bigger, a head or a nut measured across its
// corners, plus a little slop.
seat_dia  = max(head_dia, nut_af / cos(30)) + 0.4;
SEAT_WALL = 1.4;     // material between a seat and the bore, and around a seat
NUT_SLACK = 0.3;     // across flats, so a nut drops in without being forced

// The hub has to clear the bore AND carry the clamp screw beside it, since a
// screw through the middle would just hit the shaft. What sets the offset is
// not the screw but its SEAT: a counterbore wide enough for a head or a nut
// breaks into the bore long before the screw itself would, and a head sitting
// in the shaft's way is worse than no clamp. So the offset is measured from
// the seat, and the hub follows from it -- 27.4mm on an 8mm REX bore with M3,
// against 19.9mm when only the screw shank had to clear. Clamping hubs are
// chunky for this exact reason.
clamp_offset = bore_fit / 2 + seat_dia / 2 + SEAT_WALL;
hub_dia = (clamp == "None")
    ? max(bore_fit + 4, min(root_dia, bore_fit + 8))
    : 2 * (clamp_offset + seat_dia / 2 + SEAT_WALL);

// A lug carried right across the hub, so each end is a flat face square to the
// screw. It reaches exactly the hub radius, so it costs no extra width: the
// hub's own curve falls away at that offset and the lug fills back out to it.
boss_dia = seat_dia + 2 * SEAT_WALL;

// A clamping hub is wider than the pulley it stands on, so its underside is a
// bare horizontal ledge all the way round: 6.2mm of it on an 8mm REX bore with
// M3, measured as a 19.4mm unsupported span over 14% of the part's area. That
// is not printable without support, and this part claims not to need any.
//
// A 45-degree skirt carries the hub down to the pulley's own diameter instead.
// It is extra height rather than borrowed from the hub, so hub_length still
// means the length of full-width hub the clamp actually uses.
//
// Taken per tooth count, because a Size set puts different diameters under the
// same hub and each one needs its own skirt.
function hub_base_dia_of(n) = outside_dia_of(n) + 2 * flange_rise;
function hub_skirt_of(n) =
    (hub_h > 0 && hub_dia > hub_base_dia_of(n))
        ? (hub_dia - hub_base_dia_of(n)) / 2 : 0;

// A 45-degree chamfer rises as far as it stands proud, so each flange's
// chamfer reaches flange_rise into the toothed channel and blocks the belt
// over that stretch. The channel is therefore built as the belt seat PLUS
// however much the chamfers take, instead of the belt seat being whatever the
// chamfers leave behind.
//
// This replaces a cap that limited flange_rise so the chamfers could not eat
// the whole channel. The cap kept the mesh valid -- without it, flange_height
// 10 on a 6mm belt produced 21 disconnected bodies and hung below the plate --
// but it was treating the symptom. It still left a nominally 6mm pulley with
// about 3.2mm of full-depth tooth under a 6mm belt, which is the defect, and
// no mesh check would ever have reported it. Growing the channel makes the
// overlap impossible by construction, so no cap is needed at all.
flange_rise = flange_height;

chamfers_in_channel = (flanges == "Both sides") ? 2 : 1;

// What the belt actually gets, at full groove depth.
belt_seat = belt_width + belt_clearance;
body_h    = belt_seat + chamfers_in_channel * flange_rise;

flange_dia = outside_dia + 2 * flange_rise;

// --- Size set versus the plate -----------------------------------------
//
// Four wheels stand side by side on one plate, so four legal tooth counts can
// still be an illegal plate: a single 75T HTD 5M is 121mm across, and four of
// them come to nearly half a metre. Nothing downstream catches it either --
// the mesh is four perfectly good pulleys, just not on any printer.
//
// Measured from the same running offset the layout uses, and from the HUB as
// well as the flange, because on a small wheel with a clamping hub the hub is
// the wider of the two. Checked against the default set (16/20/30/40 GT2):
// predicted 88.46mm, exported 88.5mm.
SET_GAP   = 6;     // clear air the layout leaves between neighbouring wheels
PLATE_MAX = 240;   // MakerWorld's auto-arrange gets unreliable past about here

function set_prev(v, i) = i <= 0 ? 0
    : set_prev(v, i - 1) + outside_dia_of(v[i - 1]) + SET_GAP;
function set_ctr(v, i)  = set_prev(v, i) + outside_dia_of(v[i]) / 2
                          + 2 * flange_rise;
function set_half(v, i) = max(outside_dia_of(v[i]) + 2 * flange_rise,
                              hub_dia) / 2;

set_span_x = len(set_ok) == 0 ? 0
    : max([ for (i = [0 : len(set_ok) - 1]) set_ctr(set_ok, i) + set_half(set_ok, i) ])
    - min([ for (i = [0 : len(set_ok) - 1]) set_ctr(set_ok, i) - set_half(set_ok, i) ]);
set_span_y = len(set_ok) == 0 ? 0
    : max([ for (i = [0 : len(set_ok) - 1]) 2 * set_half(set_ok, i) ]);

assert(output != "Size set" || max(set_span_x, set_span_y) <= PLATE_MAX,
       str("Size set comes to ", r2(set_span_x), " x ", r2(set_span_y),
           "mm, which is over the ", PLATE_MAX, "mm plate. Lower a tooth ",
           "count, or set a slot to 0 to drop that wheel and print it ",
           "separately."));

flange_bottom = flange_thickness;   // there is always at least one flange
flange_top    = (flanges == "Both sides") ? flange_thickness : 0;
total_h = flange_bottom + body_h + flange_top;
// The lug carrying the seats is boss_dia across, and it lies on its side in
// the hub, so the hub has to be at least that tall. Shorter and the seats cut
// straight out through the hub's top and bottom faces: at the stock 8mm hub
// every screw size did, the hex pocket losing the corners that hold a nut from
// turning, which is the one thing it is there for.
//
// Raised rather than refused. A hub too short to hold its own clamp is a
// mistake with one right answer, and asking the user to discover 11.28 for
// themselves helps nobody.
min_hub_h = (clamp == "None") ? 0 : boss_dia;
hub_h   = (hub == "Extended hub") ? max(max(0, hub_length), min_hub_h) : 0;


// =====================================================================
// BORE PROFILES
// =====================================================================

module hex_2d(across_flats) { circle(d = across_flats / cos(30), $fn = 6); }
module square_2d(across_flats) { square([across_flats, across_flats], center = true); }

// REX: an 8mm round combined with a hex, so it passes through a standard 8mm
// bearing but still drives positively. The across-flats figure is the user's,
// measured off the goBILDA hardware this is built for -- it was 7.0 here,
// which is 0.3mm tight on the real shaft.
REX_ROUND = 8.0;
REX_HEX   = 7.3;

module rex_2d(round_d, hex_af) {
    intersection() { circle(d = round_d); hex_2d(hex_af); }
}

// --- corner relief ------------------------------------------------------
//
// An extrusion nozzle has a radius and cannot turn a sharp inside corner. On
// a hex or square hole it rounds every corner off, leaving material precisely
// where the shaft's own corner has to go, and the shaft will not seat -- the
// hole measures right across the flats and still does not fit. Cutting a
// small circle at each corner gives the nozzle somewhere to turn into and
// puts the leftover material where nothing needs to be.
//
// The corners are computed from each profile rather than listed, so they stay
// correct when clearance changes the size.

// $fn=6 puts the first vertex at 0 degrees, so they run 0, 60, ... 300.
function hex_corners(af) =
    let (r = af / (2 * cos(30)))
    [ for (k = [0 : 5]) let (a = 60 * k) [r * cos(a), r * sin(a)] ];

function square_corners(af) =
    [ for (sx = [-1, 1]) for (sy = [-1, 1]) [sx * af / 2, sy * af / 2] ];

// REX relieves once per hex vertex -- the shaft has one corner there, so two
// scallops at the places the round clips the point off is one too many.
//
// But the hex vertex itself sits OUTSIDE the round that clips it (4.388mm
// against 4.150mm at stock clearance), so a circle centred exactly there sits
// mostly in solid material behind the bore wall: further back than the corner
// it is supposed to relieve, which is what it looked like on the part. The
// radius is therefore clamped to the round, putting the circle on the bore's
// own edge at the vertex angle, which is where the corner actually is.
function rex_corners(round_d, hex_af) =
    let (r = min(hex_af / (2 * cos(30)), round_d / 2))
    [ for (k = [0 : 5]) let (a = 60 * k) [r * cos(a), r * sin(a)] ];

module corner_cuts(pts) {
    if (corner_relief > 0)
        for (pt = pts) translate(pt) circle(d = corner_relief, $fn = 16);
}

module bore_2d() {
    if (bore_type == "Round")        circle(d = bore_fit);
    else if (bore_type == "D-shaft")
        // The cut plane sits d_flat above the bottom of the circle, so the flat
        // is d_flat deep. It used to read -bore_fit/2 - (bore_fit/2 - d_flat),
        // which takes the radius off twice and puts the plane clear BELOW the
        // circle: on a 6mm bore it landed at -5.80 against a circle reaching
        // -3.15, so nothing was cut and a D-shaft bore came out perfectly
        // round. Measured at 0.033mm of flat, which is the facet noise on a
        // circle, where 0.5 was asked for.
        intersection() {
            circle(d = bore_fit);
            translate([-bore_fit, d_flat - bore_fit / 2])
                square([2 * bore_fit, 2 * bore_fit]);
        }
    else if (bore_type == "Hex")
        union() {
            hex_2d(bore_d + 2 * bore_clearance);
            corner_cuts(hex_corners(bore_d + 2 * bore_clearance));
        }
    else if (bore_type == "Square")
        union() {
            square_2d(bore_d + 2 * bore_clearance);
            corner_cuts(square_corners(bore_d + 2 * bore_clearance));
        }
    else if (bore_type == "REX 8mm")
        union() {
            rex_2d(REX_ROUND + 2 * bore_clearance, REX_HEX + 2 * bore_clearance);
            corner_cuts(rex_corners(REX_ROUND + 2 * bore_clearance,
                                    REX_HEX + 2 * bore_clearance));
        }
    else if (bore_type == "Bearing seat") circle(d = bore_d + 2 * bore_clearance);
}

// A real fillet on the bore mouth: a quarter round swept along the bore's own
// outline, so it follows the hexagon's flats and corners instead of bulging
// past them.
//
// Two things the first attempt got wrong, both visible on the rendered part.
// It used offset(r=), which ROUNDS convex corners, so the mouth opened as a
// blob that ignored the hex. And it hulled straight between two profiles,
// which is a chamfer, not a fillet. This steps the offset along a circular arc
// instead, and uses offset(delta=), which miters: the outline keeps its own
// corners and simply moves outward by a constant distance.
//
// The arc is walked by ANGLE, not by depth. At angle a the ring stands off by
// R(1 - sin a) and sits R(1 - cos a) deep, so a = 0 is the face at full width
// and a = 90 is where it meets the bore wall, both tangentially. Stepping
// uniformly in depth instead bunches the samples where the arc is flat and
// starves them where it turns hardest: measured, that overshot by 0.038mm near
// the face. Even steps in angle put the chord error at R(1 - cos(45/STEPS)),
// which is under two microns here.
FILLET_STEPS = 10;
// The sample slabs must be thinner than the shallowest step they sit in, or
// they set the shape instead of the arc. The first step is only
// R(1 - cos(90/STEPS)) deep -- 0.0074mm at a 0.6mm fillet -- so EPS at 0.02
// was fourteen times too thick and held the mouth at full width.
FILLET_SLAB = 0.001;

module bore_fillet_at(z_face, dir) {
    r = bore_fillet;
    // Carry the widest ring out past the face, outward only -- straddling the
    // face would hold the mouth at full width a little way into the part.
    translate([0, 0, z_face + (dir > 0 ? -2 * EPS : 0)])
        linear_extrude(2 * EPS, convexity = 6) offset(delta = r) bore_2d();


    for (i = [0 : FILLET_STEPS - 1]) {
        a0 = 90 * i / FILLET_STEPS;
        a1 = 90 * (i + 1) / FILLET_STEPS;
        hull() {
            translate([0, 0, z_face + dir * r * (1 - cos(a0))])
                linear_extrude(FILLET_SLAB, convexity = 6)
                    offset(delta = r * (1 - sin(a0))) bore_2d();
            translate([0, 0, z_face + dir * r * (1 - cos(a1))])
                linear_extrude(FILLET_SLAB, convexity = 6)
                    offset(delta = r * (1 - sin(a1))) bore_2d();
        }
    }
}

module bore_cut(height) {
    if (bore_type != "None (solid)") {
        translate([0, 0, -EPS])
            linear_extrude(height = height + 2 * EPS, convexity = 6) bore_2d();
        if (bore_fillet > 0) {
            bore_fillet_at(0, 1);
            bore_fillet_at(height, -1);
        }
    }
}

// --- clamping ----------------------------------------------------------
//
// Split clamp: a slot through the hub wall to the bore lets the hub flex, and
// one screw pulls the two sides together. Grip is round the whole shaft rather
// than one dent from a grub screw point, and it cannot mar a steel shaft.
//
// The nut is captive in a hex pocket, always. It used to be a separate option
// with a plain round seat as the alternative, and that alternative was no
// option at all: a nut sunk 2mm into a round recess cannot be reached with a
// wrench and simply spins when the screw is turned. If there is a screw there
// is a captive nut.
//
// Collet shell: a separate split sleeve drops inside the hub and the screw
// squeezes it onto the shaft. Costs a second part, but the grip is a full
// circumference and the shaft never touches printed threads at all.

slot_w    = 1.2;                     // flex gap; must be > one extrusion width
collet_t  = 2.4;                     // sleeve wall
collet_od = bore_fit + 2 * collet_t;

// z_base is the top of the skirt, where the full-width hub starts.
module clamp_slot(z_base) {
    // Runs from the bore out through the hub wall, on one side only.
    translate([-slot_w / 2, 0, z_base - EPS])
        cube([slot_w, hub_dia, hub_h + 2 * EPS]);
}

// The lug the seats are cut into. Added with the hub, not cut from it.
module clamp_boss(z_base) {
    cz = z_base + hub_h / 2;
    if (hub_h > 0 && clamp != "None")
        // Clipped in HEIGHT only, so the lug cannot stand proud of the hub top
        // or hang below where the skirt has already narrowed. The clip has to
        // be a box: a cylinder about the axis also trims the lug's ends, whose
        // corners sit at radius sqrt(clamp_offset^2 + (hub_dia/2)^2) -- 16.35mm
        // against a 13.70mm hub radius. That took the seat down to 38% of a
        // full annulus, which is a nut bearing on a crescent.
        intersection() {
            translate([0, clamp_offset, cz]) rotate([0, 90, 0])
                cylinder(h = hub_dia, d = boss_dia, center = true, $fn = 48);
            translate([-hub_dia, -hub_dia, z_base])
                cube([2 * hub_dia, 2 * hub_dia, hub_h]);
        }
}

module clamp_cuts(z_base) {
    cz = z_base + hub_h / 2;
    if (hub_h > 0 && clamp != "None") {
        clamp_slot(z_base);
        // Screw runs beside the bore, crossing the slot. Through the middle it
        // would foul the shaft and clamp nothing.
        translate([0, clamp_offset, cz]) rotate([0, 90, 0])
            // $fn=64, not 32: a polygon is drawn through the circle, so what a
            // screw actually passes is the inscribed size. At 32 facets a
            // 4.4mm hole passes 4.379; at 64 it passes 4.395.
            cylinder(h = hub_dia * 1.4, d = screw_free, center = true, $fn = 64);

        // Head seat, +X end: a flat-bottomed counterbore, so the head pulls
        // against a face square to it instead of skidding on the hub's curve.
        translate([hub_dia / 2 - screw_seat_depth, clamp_offset, cz])
            rotate([0, 90, 0])
                cylinder(h = screw_seat_depth + EPS, d = seat_dia, $fn = 48);

        // Nut seat, -X end: a hex pocket, so the nut cannot turn while the
        // screw is tightened. Deep enough to swallow the nut, so a nyloc sits
        // in it as readily as a plain one.
        //
        // $fn=6 puts vertices at 0 and 180 degrees, which this rotation sends
        // to straight up and straight down -- so the pocket's roof is a point,
        // not a flat bridge, and prints without support like the rest.
        translate([-hub_dia / 2 - EPS, clamp_offset, cz]) rotate([0, 90, 0])
            // Slack applied ACROSS FLATS, which is the dimension a nut is
            // made to. Adding it to the circum-diameter instead scales it by
            // cos(30) on the way back out: asking for 0.30 gave 0.26.
            cylinder(h = nut_thick + 0.4 + EPS,
                     d = (nut_af + NUT_SLACK) / cos(30), $fn = 6);

        if (clamp == "Collet shell")
            translate([0, 0, z_base - EPS])
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
    fd = od + 2 * flange_rise;
    translate([0, 0, z]) mirror([0, 0, flip ? 1 : 0])
        union() {
            cylinder(h = flange_thickness, d = fd);
            translate([0, 0, flange_thickness - EPS])
                cylinder(h = flange_rise, d1 = fd, d2 = od);
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
            if (hub_h > 0) {
                sk = hub_skirt_of(nn);
                if (sk > 0)
                    translate([0, 0, total_h - EPS])
                        cylinder(h = sk + EPS, d1 = hub_base_dia_of(nn),
                                 d2 = hub_dia);
                translate([0, 0, total_h + sk - EPS])
                    cylinder(h = hub_h + EPS, d = hub_dia);
                clamp_boss(total_h + sk);
            }
        }
        translate([0, 0, flange_bottom]) teeth_cut(body_h, nn);
        bore_cut(total_h + hub_skirt_of(nn) + hub_h);
        clamp_cuts(total_h + hub_skirt_of(nn));
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
    gap = SET_GAP;
    for (i = [0 : len(set_counts) - 1])
        if (set_counts[i] >= 8) {
            n = set_counts[i];
            od_i = n * pitch / PI - 2 * pld;
            // running offset: sum of the earlier diameters plus gaps
            prev = (i == 0) ? 0 :
                   vsum_d([ for (j = [0 : i - 1])
                       (set_counts[j] >= 8 ? set_counts[j] * pitch / PI - 2 * pld
                                           : 0) + gap ]);
            translate([prev + od_i / 2 + 2 * flange_rise, 0, 0])
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
if (hub_h > hub_length && clamp != "None")
    echo(str("PULLEY  hub raised from ", hub_length, "mm to ", r2(hub_h),
             "mm, the least that holds an ", clamp_screw,
             " nut pocket without it breaking out of the hub faces."));
if (hub_h > 0 && clamp != "None")
    echo(str("PULLEY  clamp: ", clamp_screw, " x ",
             ceil(hub_dia - screw_seat_depth),
             "mm or longer, plus one ", clamp_screw,
             " nut (plain or nyloc). The nut drops into a hex pocket ",
             r2(nut_af), "mm across flats x ", r2(nut_thick + 0.4),
             "mm deep; the head seats in a ", r2(seat_dia), "mm counterbore ",
             screw_seat_depth, "mm deep."));
