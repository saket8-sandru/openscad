// =====================================================================
// TEXT ONTO AN EXISTING PLAQUE STL
// =====================================================================
//
// Imports a finished plaque and adds the four text lines on top.
//
// OpenSCAD 2021.01 cannot measure an imported STL, so it cannot find your
// plaque's size or where its top face sits. You supply those two numbers
// once, and "Align check" makes it obvious when they are right.
//
// EASIEST: save this .scad next to your STL and just use the file name --
// "base.stl" -- because a relative path resolves against the folder this file
// is in, not the working directory.
//
// If you do use a full path, forward slashes only:
//   good:  "C:/Users/saket/Downloads/base.stl"
//   good:  "C:\\Users\\saket\\Downloads\\base.stl"
//   bad:   "C:\Users\saket\Downloads\base.stl"   -- \U is an escape, not a folder
//
// If nothing appears: set output = "Base only" to test the import by itself,
// and read the console. OpenSCAD names the exact path it tried to open.
// =====================================================================


/* [Base file] */

// Path to your plaque STL.
base_file = "base.stl";

// Height of the plaque's TOP face above the STL's own origin. If the text
// floats or sinks, this is the number to change. Align check shows it.
base_top_z = 5.0;      // [0:0.1:60]

// Nudge the base so its centre lands on the origin. Align check shows it.
base_shift_x = 0;      // [-200:0.5:200]
base_shift_y = 0;      // [-200:0.5:200]


/* [Text] */

line_1 = "Eagle Scout Project";
line_2 = "Ishaan Ashok";
line_3 = "October 2025";
line_4 = "Troop 273";

// Sizes derived from the reference plaque by measuring how wide each line
// RUNS, not how tall the capitals look -- the cap-height reading came out
// around 12 and rendered 136mm wide on a 114.3mm plaque.
size_1 = 9.0;          // [4:0.1:24]
size_2 = 8.0;          // [4:0.1:24]
size_3 = 6.0;          // [3:0.1:20]
size_4 = 6.2;          // [3:0.1:20]

// Text is kept inside this much of the plaque width. Whatever sizes are set
// above, the block is scaled down together if the longest line would run off
// the edge -- so a long name can never push lettering into thin air.
text_max_width = 0.86; // [0.50:0.01:1.00]

// Closest safe match to the reference lettering. Anything not installed
// silently falls back to a default face, so check the render.
font_face = "Liberation Serif:style=Bold"; // [Liberation Serif:style=Bold, Liberation Serif, Liberation Sans:style=Bold, DejaVu Serif:style=Bold, Georgia:style=Bold, Times New Roman:style=Bold]

// Raised stands proud of the face; recessed is cut into it.
text_style = "Raised"; // [Raised, Recessed]

// How far the lettering stands proud, or sinks in.
text_depth = 1.2;      // [0.3:0.1:4.0]


/* [Layout] */

// Plaque size, used only to place the lines. Match your STL.
plaque_w = 114.3;      // [40:0.1:400]
plaque_h = 76.2;       // [30:0.1:400]

// Baselines as a fraction of height, measured from the BOTTOM edge.
// These came off the reference image, not from guesswork.
base_1 = 0.775;        // [0:0.005:1]
base_2 = 0.645;        // [0:0.005:1]
base_3 = 0.550;        // [0:0.005:1]
base_4 = 0.450;        // [0:0.005:1]

// Horizontal centre of the text block, as a fraction of width.
text_center = 0.50;    // [0:0.005:1]


/* [Output] */

// Align check draws the text flat over a ghost of the base so you can line
// it up before committing to a full render.
output = "Plaque with text"; // [Base only, Plaque with text, Align check, Text only]


// =====================================================================

EPS = 0.05;
$fn = 48;

lines = [line_1, line_2, line_3, line_4];
raw_sizes = [size_1, size_2, size_3, size_4];
bases = [base_1, base_2, base_3, base_4];

// Measured for Liberation Serif Bold: "Eagle Scout Project" renders 113.31mm
// wide at size 10, i.e. 0.5964 per character per unit size. 0.62 leaves margin
// for wider faces and capital-heavy strings.
CHAR_W = 0.62;
field_w = plaque_w * text_max_width;
widest = max([ for (i = [0 : 3]) len(lines[i]) * raw_sizes[i] * CHAR_W ]);
fit_k = widest > field_w ? field_w / widest : 1;
sizes = [ for (i = [0 : 3]) raw_sizes[i] * fit_k ];

raised = (text_style == "Raised");

module base_model() {
    translate([base_shift_x, base_shift_y, 0]) import(base_file, convexity = 10);
}

module text_2d() {
    for (i = [0 : 3])
        if (lines[i] != "")
            translate([(text_center - 0.5) * plaque_w,
                       (bases[i] - 0.5) * plaque_h])
                text(lines[i], size = sizes[i], font = font_face,
                     halign = "center", valign = "baseline", $fn = 32);
}

// Raised sits on the face and overlaps it slightly so the union is solid.
// Recessed starts below the face so the cut never ends flush with it.
module text_3d() {
    z = raised ? base_top_z - EPS : base_top_z - text_depth;
    translate([0, 0, z]) linear_extrude(text_depth + EPS) text_2d();
}

if (output == "Base only") {
    // Nothing but the import. If this is empty, the problem is the path or the
    // file -- not the text, the sizes or the alignment.
    base_model();
} else if (output == "Text only") {
    text_3d();
} else if (output == "Align check") {
    // The base is drawn solid, not with %, so it survives a full F6 render.
    // As a background object it showed on F5 and then vanished on F6, which
    // looks exactly like the import having failed.
    color("silver") base_model();
    color("red") translate([0, 0, base_top_z]) linear_extrude(0.4) text_2d();
} else {
    if (raised) union()      { base_model(); text_3d(); }
    else        difference() { base_model(); text_3d(); }
}

// Windows paths with single backslashes are escape sequences, not folders.
// Printing the string back is the quickest way to see that has happened.
echo(str("PLAQUE TEXT  importing >>", base_file, "<<"));
echo(str("PLAQUE TEXT  top_z=", base_top_z, "  ", text_style, " ", text_depth, "mm"));
echo("PLAQUE TEXT  nothing visible? set output = \"Base only\" to test the import alone");
echo("PLAQUE TEXT  if the text floats or sinks, change base_top_z");
echo("PLAQUE TEXT  if it sits off to one side, change base_shift_x / base_shift_y");
if (fit_k < 1)
    echo(str("PLAQUE TEXT  scaled to ", round(fit_k * 100),
             "% so the longest line fits the plaque"));
