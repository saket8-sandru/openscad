// A stand-in plaque, so the text generator and tools/plaquefit.py can both be
// tested without needing anyone's private artwork in the repository.
//
// Deliberately awkward in the two ways a real CAD export is awkward:
//   - the origin is at a CORNER, not the centre, the way Onshape exports;
//   - a raised border means the bounding-box top is NOT the face the
//     lettering lands on, so anything that assumes "top = bbox top" is wrong.
//
// 4.5 x 3 inches, the size quoted for the real plaque.

W = 114.3;
H = 76.2;
SLAB = 5.0;      // field height above the back
BORDER_W = 6.0;
BORDER_H = 1.8;  // border stands this much proud of the field

module chamfered_slab(w, h, t, c) {
    hull() {
        translate([c, c, 0]) cube([w - 2 * c, h - 2 * c, 0.001]);
        translate([0, 0, c]) cube([w, h, t - c]);
    }
}

difference() {
    union() {
        chamfered_slab(W, H, SLAB, 1.2);
        // border ring
        difference() {
            translate([0, 0, SLAB - 0.001]) cube([W, H, BORDER_H]);
            translate([BORDER_W, BORDER_W, SLAB - 0.5])
                cube([W - 2 * BORDER_W, H - 2 * BORDER_W, BORDER_H + 1]);
        }
    }
    // two keyhole-ish hangers, so the mesh is not a trivial box
    for (x = [W * 0.3, W * 0.7])
        translate([x, H - 10, -0.5]) cylinder(h = 3, d = 6, $fn = 32);
}
