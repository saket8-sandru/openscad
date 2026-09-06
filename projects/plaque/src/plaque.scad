// =====================================================================
// PROJECT PLAQUE -- customisable text, swappable artwork
// =====================================================================
//
// A 4.5 x 3 inch dedication plaque: raised border, four mounting holes,
// four lines of editable text, and two artwork slots.
//
// ARTWORK AND TRADEMARKS
// The artwork slots take SVG files you supply. They ship EMPTY on purpose.
// Organisation emblems -- scouting marks among them -- are registered
// trademarks, and baking one into a model that anyone can download and
// generate is redistributing that mark. Drop your own artwork in locally for
// your own plaque; leave the slots empty in anything you publish.
//
// Print face-up, flat on the bed. Everything is raised or recessed from a
// flat back, so no support is needed.
//
// OpenSCAD 2021.01.
// =====================================================================


/* [Text] */

// Top line, largest.
line_1 = "Eagle Scout Project";
// Second line -- usually the name.
line_2 = "Ishaan Ashok";
// Third line -- usually the date.
line_3 = "October 2025";
// Fourth line.
line_4 = "Troop 273";

// Height of the top line. The rest scale from it.
title_size = 11;       // [5:0.5:20]

// How much smaller each following line is.
line_scale = 0.78;     // [0.50:0.02:1.00]

// Raised text stands proud; recessed is cut in. Recessed prints cleaner in a
// second colour, raised reads better in a single colour.
text_style = "Raised"; // [Raised, Recessed]

// How far the text stands proud of (or sinks into) the face.
text_depth = 1.2;      // [0.4:0.1:3.0]

// Font. Keep to fonts MakerWorld actually has, or it silently falls back.
font_face = "Liberation Serif:style=Bold"; // [Liberation Serif:style=Bold, Liberation Serif, Liberation Sans:style=Bold, Liberation Sans, DejaVu Serif:style=Bold, DejaVu Sans:style=Bold]


/* [Plaque] */

// Overall width (4.5 inch default).
plaque_w = 114.3;      // [60:0.1:300]

// Overall height (3 inch default).
plaque_h = 76.2;       // [40:0.1:300]

// Base thickness behind everything.
plaque_t = 4.0;        // [2.0:0.5:12.0]

// Corner rounding.
corner_r = 6;          // [0:0.5:20]


/* [Border] */

// Raised frame around the face. 0 removes it.
border_width = 3.0;    // [0:0.5:10]

// How far the border stands proud.
border_height = 1.2;   // [0.4:0.1:4.0]

// Gap between the plaque edge and the border.
border_inset = 3.5;    // [0:0.5:15]


/* [Mounting] */

// Screw holes in the corners.
holes = "Four corners"; // [Four corners, None]

// Screw shank clearance.
hole_dia = 4.5;        // [2:0.1:8]

// How far the hole centres sit in from each edge.
hole_inset = 7.5;      // [4:0.5:20]


/* [Artwork] */

// Left-hand artwork SVG. Leave blank for none. See the trademark note above.
art_left = "";         // .svg

// Right-hand artwork SVG. Leave blank for none.
art_right = "";        // .svg

// Width the left artwork is scaled to.
art_left_w = 34;       // [0:1:80]

// Height the right artwork is scaled to.
art_right_h = 52;      // [0:1:90]

// Artwork relief, same convention as the text.
art_depth = 1.0;       // [0.4:0.1:3.0]


/* [Output] */

output = "Plaque"; // [Plaque, Text only, Layout check]


// =====================================================================
// DERIVED
// =====================================================================

EPS = 0.02;
$fn = 64;

// The text field is defined by its actual edges, not by a centre plus a
// guessed width. Getting that wrong put the title through the left border:
// the block was centred at 46% of the width while the fit was computed as if
// it were centred at 50%. When right-hand artwork is present the field stops
// short of it, so text and art cannot collide.
inner_l = -plaque_w / 2 + border_inset + border_width + 2;
inner_r =  plaque_w / 2 - border_inset - border_width - 2;
art_r_edge = (art_right == "")
    ? inner_r
    : (art_right_c[0] - plaque_w / 2) - art_right_h * 0.42 - 2;
text_l = inner_l;
text_r = min(inner_r, art_r_edge);
text_cx_abs = (text_l + text_r) / 2;
lines = [ line_1, line_2, line_3, line_4 ];

// Text must not run off the plaque. OpenSCAD 2021.01 cannot measure a string,
// so width is estimated from character count and the whole block is scaled
// down by one common factor if the widest line would overflow. Scaling every
// line together keeps the relative sizes the designer chose.
// Measured, not guessed: "Eagle Scout Project" renders 113.31mm wide at size
// 10 in Liberation Serif Bold, i.e. 0.5964 per character per unit size. The
// first estimate of 0.55 was 8% low and pushed the title through the border.
// 0.62 adds a little margin for wider fonts and capital-heavy strings.
CHAR_W = 0.62;
text_field_w = text_r - text_l;

raw_sizes = [ title_size,
              title_size * line_scale,
              title_size * line_scale * line_scale,
              title_size * line_scale * line_scale ];

function est_w(i) = len(lines[i]) * raw_sizes[i] * CHAR_W;
widest = max([ for (i = [0 : 3]) est_w(i) ]);
fit_k  = widest > text_field_w ? text_field_w / widest : 1;

sizes = [ for (i = [0 : 3]) raw_sizes[i] * fit_k ];

// Baselines measured down from the top, proportioned like the reference art.
base_y = [ plaque_h * 0.795, plaque_h * 0.635, plaque_h * 0.515, plaque_h * 0.405 ];

art_left_c  = [ plaque_w * 0.215, plaque_h * 0.31 ];
art_right_c = [ plaque_w * 0.845, plaque_h * 0.42 ];

raised = (text_style == "Raised");


// =====================================================================
// SHAPES
// =====================================================================

module rounded_rect(w, h, r) {
    if (r <= 0) square([w, h], center = true);
    else offset(r = r) offset(r = -r) square([w, h], center = true);
}

module base() {
    linear_extrude(plaque_t)
        rounded_rect(plaque_w, plaque_h, corner_r);
}

module border() {
    if (border_width > 0)
        translate([0, 0, plaque_t - EPS])
            linear_extrude(border_height + EPS)
                difference() {
                    rounded_rect(plaque_w - 2 * border_inset,
                                 plaque_h - 2 * border_inset,
                                 max(0, corner_r - border_inset));
                    rounded_rect(plaque_w - 2 * (border_inset + border_width),
                                 plaque_h - 2 * (border_inset + border_width),
                                 max(0, corner_r - border_inset - border_width));
                }
}

module text_2d() {
    for (i = [0 : 3])
        if (lines[i] != "")
            translate([text_cx_abs, base_y[i] - plaque_h / 2])
                text(lines[i], size = sizes[i], font = font_face,
                     halign = "center", valign = "baseline", $fn = 32);
}

module art_2d() {
    if (art_left != "")
        translate([art_left_c[0] - plaque_w / 2, art_left_c[1] - plaque_h / 2])
            resize([art_left_w, 0], auto = true) import(file = art_left, center = true);
    if (art_right != "")
        translate([art_right_c[0] - plaque_w / 2, art_right_c[1] - plaque_h / 2])
            resize([0, art_right_h], auto = true) import(file = art_right, center = true);
}

module holes_cut() {
    if (holes == "Four corners")
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (plaque_w / 2 - hole_inset),
                       sy * (plaque_h / 2 - hole_inset), -EPS])
                cylinder(h = plaque_t + border_height + 2 * EPS, d = hole_dia);
}

module relief(depth, is_raised) {
    // Raised sits on the face; recessed is subtracted from it. The recessed
    // cutter is grown a touch so it never ends flush with the surface.
    if (is_raised) translate([0, 0, plaque_t - EPS]) linear_extrude(depth + EPS) children();
    else translate([0, 0, plaque_t - depth]) linear_extrude(depth + EPS) children();
}

module plaque() {
    difference() {
        union() {
            base();
            border();
            if (raised) { relief(text_depth, true) text_2d();
                          relief(art_depth, true) art_2d(); }
        }
        if (!raised) { relief(text_depth, false) text_2d();
                       relief(art_depth, false) art_2d(); }
        holes_cut();
    }
}

// Text and artwork alone, for checking the layout fits before a full render.
module layout_check() {
    linear_extrude(1) { text_2d(); art_2d(); }
    %linear_extrude(0.1) rounded_rect(plaque_w, plaque_h, corner_r);
}

if (output == "Text only")        linear_extrude(text_depth) text_2d();
else if (output == "Layout check") layout_check();
else                               plaque();

echo(str("PLAQUE  ", plaque_w, " x ", plaque_h, " x ",
         plaque_t + border_height, "mm  text ", text_style));
if (fit_k < 1)
    echo(str("PLAQUE  text scaled to ", round(fit_k * 100),
             "% so the longest line fits inside the border"));
if (art_left == "" && art_right == "")
    echo("PLAQUE  artwork slots empty -- set art_left / art_right to your own SVG");
