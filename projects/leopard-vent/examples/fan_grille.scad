// =====================================================================
// LEOPARD VENT example -- fan grille
// =====================================================================
//
// Worked example of using leopard_vent.scad as a library. The vent region is
// a ring: the fan's blade circle with a solid disc left over the motor hub,
// which moves no air. That is the point of the example -- any 2D shape can be
// the region, holes in it included, and the border is kept off every edge of
// it, inner edge as well as outer.
//
// For desktop OpenSCAD: it pulls the library in from a second file with
// use<>. The main leopard_vent.scad is the one kept self-contained for
// MakerWorld's Parametric Model Maker. Not print-tested.
// =====================================================================

use <../src/leopard_vent.scad>

/* [Fan] */

// Nominal fan frame size.
fan_size = 80;         // [40, 60, 80, 92, 120, 140]

// Grille plate thickness.
thickness = 2.0;       // [1.2:0.2:4.0]

/* [Pattern] */

cell_shape = "6 sides"; // [3 sides, 4 sides, 6 sides]
cell_size = 9;         // [5:0.5:20]
rib_thickness = 1.6;   // [0.8:0.1:4]
irregularity = 0.8;    // [0:0.05:1]
seed = 3;              // [1:1:999]

// Solid band kept inside the blade opening, and around the hub disc.
border = 2.5;          // [1:0.5:8]

// Solid disc over the motor hub, as a fraction of the fan size. 0 vents
// right across the middle.
hub = 0.38;            // [0:0.02:0.5]


// Screw hole spacing and diameter for the common square fan sizes. These are
// the usual figures, not a standard this file can vouch for -- measure your
// fan before trusting them.
// [ frame, hole spacing, hole diameter ]
FANS = [ [40, 32.0, 3.4], [60, 50.0, 4.3], [80, 71.5, 4.3],
         [92, 82.5, 4.3], [120, 105.0, 4.3], [140, 124.5, 4.3] ];

fan = [ for (f = FANS) if (f[0] == fan_size) f ][0];
assert(fan != undef, str("no screw data for a ", fan_size, "mm fan"));

spacing = fan[1];
screw_d = fan[2];
opening = fan_size - 4;
hub_d = hub * fan_size;
corner_r = fan_size / 20;

$fa = 2;
$fs = 0.3;

module screw_holes() {
    for (sx = [-1, 1], sy = [-1, 1])
        translate([sx, sy] * spacing / 2) circle(d = screw_d);
}

// Blade circle less the hub disc. The vents stay a border's width off both
// edges of the ring.
module vent_region() {
    difference() {
        circle(d = opening);
        if (hub_d > 0) circle(d = hub_d);
    }
}

linear_extrude(height = thickness)
    difference() {
        offset(r = corner_r) offset(delta = -corner_r)
            square(fan_size, center = true);
        screw_holes();
        leopard_vent_2d(bounds = [[-opening / 2, -opening / 2], [opening / 2, opening / 2]],
                        cell_size = cell_size, rib = rib_thickness, shape = cell_shape,
                        irregularity = irregularity, seed = seed, border = border)
            vent_region();
    }

echo(str("FAN GRILLE  ", fan_size, "mm  screws ", screw_d, "mm at ", spacing,
         "mm  opening ", opening, "mm  hub ", hub_d, "mm"));
