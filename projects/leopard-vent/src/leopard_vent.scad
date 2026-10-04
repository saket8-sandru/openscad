// =====================================================================
// LEOPARD VENT -- irregular-cell venting and lightening pattern
// =====================================================================
//
// A field of uneven holes separated by ribs of one set thickness. The look
// borrows from leopard print -- scattered spots of differing size and shape
// -- but every spot is simplified to a straight-sided cell: four sides by
// default, three for a triangle web, or six -- uneven Voronoi cells -- for the
// closest thing to the real print.
//
// The rib thickness is a guarantee, not an approximation. The cells tile the
// plane edge to edge, and each one is shrunk inward by half a rib, so wherever
// two holes face each other the web between them is exactly one rib thick.
// Corners and junctions only ever come out thicker, never thinner, and so does
// the solid border.
//
// Two ways to use it:
//   1. Standalone. Open it in OpenSCAD or MakerWorld's Parametric Model Maker
//      and generate a vented panel, a cutter body to subtract in a slicer or
//      in CAD, or a flat outline to export as DXF/SVG.
//   2. As a library. `use <leopard_vent.scad>` and subtract leopard_vent_2d()
//      from your own part. Worked example at the end of this file.
//
// Print flat. Through holes, and pockets with the floor on the bed, are all
// vertical walls, so nothing overhangs and no support is needed.
//
// Self-contained -- no include<>/use<>. Written for OpenSCAD 2021.01, the
// release MakerWorld's Parametric Model Maker runs.
// =====================================================================


/* [Part] */

// Outline of the generated panel. Circle uses the width as its diameter.
panel_shape = "Rectangle"; // [Rectangle, Circle]

// Panel width, or the diameter of a circle.
panel_width = 120;     // [30:1:250]

// Panel height. Ignored for a circle.
panel_height = 80;     // [30:1:250]

// Panel thickness.
thickness = 3.0;       // [1.0:0.2:12.0]

// Rounds the panel's outside corners. Rectangle only.
panel_corner_radius = 4; // [0:0.5:30]

// Solid band around the edge with no holes in it. Never thinner than a rib --
// a smaller value is raised to the rib thickness.
border = 5;            // [1:0.5:30]


/* [Pattern] */

// 4 sides: a jittered grid of quads. 3 sides: a jittered triangle web --
// triangulated like an isogrid, so it braces against in-plane shear instead
// of relying on the ribs bending (truss reasoning, not measured here).
// 6 sides: uneven Voronoi cells, the closest to real leopard print. Some of
// their edges are short enough that the corner rounding swallows them, so
// many read as five-sided. Counted over ten seeds: up to irregularity 0.7
// every inner cell really is a hexagon; at 1, one in five has five or seven
// sides.
cell_shape = "4 sides"; // [3 sides, 4 sides, 6 sides]

// Average cell size. Every cell shape is scaled so a cell covers about the
// area of a square this wide, so switching shape keeps the hole count about
// the same.
cell_size = 14;        // [5:0.5:60]

// Material left between neighbouring holes. Two extrusion widths -- 0.8mm on
// a 0.4 nozzle -- is the least that prints as a solid wall.
rib_thickness = 2.0;   // [0.8:0.1:10]

// How far the cells stray from a regular grid. 0 is perfectly regular -- a
// square grid, an even triangle web, or a honeycomb. 1 is as uneven as the
// cells can get while staying valid.
irregularity = 0.7;    // [0:0.05:1]

// Rounds every hole corner. Round corners print cleaner, and they take out
// the stress concentration a sharp corner puts into a rib. Go easy: a hole
// narrower than twice this radius cannot be rounded and is left solid, so
// large values erase the smaller cells. At 8 on the default panel, 5 of the
// 40 holes go and the open area falls from 61% to 47%.
hole_corner_radius = 1.0; // [0.5:0.25:8]

// A hole that cannot hold a circle this wide is left solid instead. This is
// what clears the slivers where the border cuts across a cell. 0 keeps every
// fragment that survives the corner rounding.
min_hole = 4;          // [0:0.5:20]

// Which arrangement. The same seed gives the same pattern every time.
seed = 1;              // [1:1:999]

// Fit: the cells are stretched slightly so whole cells fill the panel, and
// every edge hole has a straight side one border-width from the edge. Crop:
// the pattern runs on past the edge and is cut off there, like fabric -- more
// random-looking, but the edge holes are fragments, and the ones too small to
// keep leave solid patches. A circle is always cropped.
edges = "Fit";         // [Fit, Crop]


/* [Holes] */

// Through cuts all the way, for venting. Pocket keeps a closed floor, for
// lightening a part that still has to seal or carry a face.
hole_type = "Through"; // [Through, Pocket]

// Floor left under each pocket. Pocket only.
floor_thickness = 1.0; // [0.4:0.2:6.0]


/* [Output] */

// Panel: the finished part. Cutter: only the hole bodies, to use as a
// slicer's negative part or a CAD subtract -- it lines up with the panel the
// same settings would make. 2D holes: a flat outline for File > Export as
// DXF or SVG; desktop OpenSCAD only, as it has no 3D body to export as STL.
output = "Panel";      // [Panel, Cutter, 2D holes]


// =====================================================================
// CONSTANTS
// =====================================================================

EPS = 0.02;
NOZZLE = 0.4;
MIN_RIB = 2 * NOZZLE;  // narrower than two extrusion widths will not print as a wall
MIN_HOLE = 2.0;        // a nominal hole narrower than this is not worth cutting
MIN_POCKET = 0.4;      // two layers; any shallower and the pocket is a texture
CUTTER_OVERSHOOT = 1.0;

// Lattice pitch per unit of cell_size, chosen so a cell's area is
// cell_size^2 whatever the shape. An equilateral triangle of side s covers
// s^2 * sqrt(3)/4; a honeycomb cell at seed spacing s covers s^2 * sqrt(3)/2.
PITCH_QUAD = 1;
PITCH_TRI  = sqrt(4 / sqrt(3));
PITCH_HEX  = sqrt(2 / sqrt(3));

// Width of the nominal hole -- the regular cell, before jitter -- per unit of
// lattice pitch. Square: its side. Equilateral triangle: twice the inradius.
// Honeycomb: across flats.
ACROSS_QUAD = 1;
ACROSS_TRI  = 1 / sqrt(3);
ACROSS_HEX  = 1;

// Largest jitter radius at irregularity = 1, as a fraction of lattice pitch.
// Quads: a jittered quad can only fold over itself once a corner moves half a
// pitch, so 0.35 keeps a wide margin. Triangles: a triangle turns inside out
// once its corners close the 0.866-pitch altitude between them, so two
// corners moving 0.28 each still leave a third of it. Voronoi cells cannot
// go invalid at all; the cap only stops two seeds landing so close that their
// cells come out as slivers.
JITTER_QUAD = 0.35;
JITTER_TRI  = 0.28;
JITTER_HEX  = 0.35;

// Lattice cells added beyond the bounds on every side. A Voronoi cell near
// the edge needs all its true neighbours to exist, and they can sit nearly
// three rows out.
MARGIN = 4;

$fa = 2;
$fs = 0.3;


// =====================================================================
// HASH -- platform-stable pseudo-random numbers
// =====================================================================

// Angles are reduced before sin() so the hash gives identical results on every
// OpenSCAD build. Without this, two platforms' range reduction differ by ~1e-10,
// which this hash multiplies by 44000 into a visibly different pattern.
function wrap360(a) = a - 360 * floor(a / 360);

function hash01(n, s) =
    let (a0 = sin(wrap360(n * 12.9898 + s * 78.233 + 41.7)) * 43758.5453,
         a  = a0 - floor(a0),
         c0 = sin(wrap360(a * 311.7 + n * 74.7 + s * 19.19)) * 24634.6345)
    c0 - floor(c0);

// Uniform over a disc of radius a, so no direction is favoured. A square
// jitter box pulls the pattern toward the diagonals.
function jitter(i, j, a, s) =
    let (n = (i * 977 + j) * 2,
         r = a * sqrt(hash01(n, s)),
         t = 360 * hash01(n + 1, s))
    [r * cos(t), r * sin(t)];


// =====================================================================
// CELLS
//
// Every shape is built the same way: a lattice of points, jittered, then
// joined into cells that share their edges exactly. Sharing edges is what
// makes the rib exact -- both neighbours are shrunk off the same line.
// =====================================================================

function shape_pitch(shape) =
    shape == "3 sides" ? PITCH_TRI : shape == "6 sides" ? PITCH_HEX : PITCH_QUAD;
function shape_across(shape) =
    shape == "3 sides" ? ACROSS_TRI : shape == "6 sides" ? ACROSS_HEX : ACROSS_QUAD;
function shape_jitter(shape) =
    shape == "3 sides" ? JITTER_TRI : shape == "6 sides" ? JITTER_HEX : JITTER_QUAD;
function staggered(shape) = shape != "4 sides";

// The nominal hole width a setting produces, before jitter and rounding.
function hole_width(shape, cell, rib) =
    cell * shape_pitch(shape) * shape_across(shape) - rib;

// Lattice centred on the bounds, so a regular pattern sits symmetrically.
// Returns [origin, nx, ny]. The centre point's indices, nx/2 and ny/2, are
// kept even, so the centre row is never a shifted one whatever the size.
function lattice_frame(lo, hi, p, h) =
    let (hx = 2 * ceil((ceil((hi[0] - lo[0]) / (2 * p)) + MARGIN) / 2),
         hy = 2 * ceil((ceil((hi[1] - lo[1]) / (2 * h)) + MARGIN) / 2))
    [ (lo + hi) / 2 - [hx * p, hy * h], 2 * hx, 2 * hy ];

// Square lattice, or staggered: odd rows shifted half a pitch, rows packed to
// 0.866 pitch, which is the triangular lattice.
//
// Jitter is keyed to the position relative to the centre, not to the corner
// of the lattice. A bigger region then shows more of the same pattern round
// the middle, like a wider cut of the same cloth, instead of a new one.
function lattice(o, p, nx, ny, stagger, a, s) =
    let (h = stagger ? p * sqrt(3) / 2 : p)
    [ for (i = [0 : nx])
        [ for (j = [0 : ny])
            o + [(i + (stagger ? (j % 2) / 2 : 0)) * p, j * h]
              + jitter(i - nx / 2, j - ny / 2, a, s) ] ];

function touches(c, lo, hi) =
    let (xs = [ for (q = c) q[0] ], ys = [ for (q = c) q[1] ])
    max(xs) > lo[0] && min(xs) < hi[0] && max(ys) > lo[1] && min(ys) < hi[1];

function quad_cells(V, nx, ny, lo, hi) =
    [ for (i = [0 : nx - 1], j = [0 : ny - 1])
        let (c = [ V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1] ])
        if (touches(c, lo, hi)) c ];

// Each band between two staggered rows splits into alternating up- and
// down-pointing triangles. Which corners they use depends on which of the two
// rows carries the half-pitch shift.
function tri_cells(V, nx, ny, lo, hi) =
    [ for (i = [0 : nx - 1], j = [0 : ny - 1], up = [true, false])
        let (c = j % 2 == 0
                 ? (up ? [ V[i][j], V[i + 1][j], V[i][j + 1] ]
                       : [ V[i + 1][j], V[i + 1][j + 1], V[i][j + 1] ])
                 : (up ? [ V[i][j], V[i + 1][j], V[i + 1][j + 1] ]
                       : [ V[i][j], V[i + 1][j + 1], V[i][j + 1] ]))
        if (touches(c, lo, hi)) c ];

// Keep the part of a polygon on the seed's side of the bisector between seed
// s and neighbour n: points x with (x - m) . d < 0. Strict, so a corner lying
// exactly on the line is emitted once, as a crossing, instead of twice.
function clip_half(poly, m, d) =
    let (n = len(poly))
    n < 3 ? [] :
    [ for (k = [0 : n - 1])
        let (a = poly[k], b = poly[(k + 1) % n],
             fa = (a - m) * d, fb = (b - m) * d)
        each concat(fa < 0 ? [a] : [],
                    (fa < 0) != (fb < 0) ? [ a + (b - a) * (fa / (fa - fb)) ] : []) ];

function clip_all(poly, s, nbrs, k = 0) =
    k >= len(nbrs) ? poly
    : clip_all(clip_half(poly, (s + nbrs[k]) / 2, nbrs[k] - s), s, nbrs, k + 1);

// Voronoi cells of the jittered seeds, by clipping a box around each seed
// against the bisector of every seed that could be a neighbour.
//
// Bound: every point is within rc = (lattice covering radius + jitter) of
// some seed, so a cell fits inside a disc of radius rc round its own seed,
// and only seeds within 2 * rc can share an edge with it. That keeps the
// search to a 7x7 index window and lets the start box be finite.
function voronoi_cells(S, nx, ny, p, a, lo, hi) =
    let (rc = p / sqrt(3) + a + EPS)
    [ for (i = [0 : nx], j = [0 : ny])
        let (s = S[i][j])
        if (s[0] > lo[0] - rc && s[0] < hi[0] + rc && s[1] > lo[1] - rc && s[1] < hi[1] + rc)
        let (nbrs = [ for (di = [-3 : 3], dj = [-3 : 3])
                        let (ii = i + di, jj = j + dj)
                        if ((di != 0 || dj != 0) && ii >= 0 && ii <= nx && jj >= 0 && jj <= ny
                            && norm(S[ii][jj] - s) < 2 * rc)
                        S[ii][jj] ],
             c = clip_all([ s + [-rc, -rc], s + [rc, -rc], s + [rc, rc], s + [-rc, rc] ],
                          s, nbrs))
        if (len(c) >= 3) c ];

// All cells that can reach the bounds, as polygons (lists of [x, y]).
function vent_cells(shape, lo, hi, cell, irregular, s) =
    let (p  = cell * shape_pitch(shape),
         st = staggered(shape),
         h  = st ? p * sqrt(3) / 2 : p,
         a  = clamp01(irregular) * shape_jitter(shape) * p,
         fr = lattice_frame(lo, hi, p, h),
         V  = lattice(fr[0], p, fr[1], fr[2], st, a, s))
    shape == "3 sides"        ? tri_cells(V, fr[1], fr[2], lo, hi)
  : shape == "6 sides" ? voronoi_cells(V, fr[1], fr[2], p, a, lo, hi)
  :                             quad_cells(V, fr[1], fr[2], lo, hi);


// =====================================================================
// FITTED CELLS
//
// The cells above run on past the region and are cropped by it, which leaves
// fragments of cells along the edge -- slivers, or solid patches where a
// sliver was too small to keep. When the region is a rectangle the cells can
// be built to fit it instead: the lattice is stretched slightly so a whole
// number of cells spans it, and every point on the boundary stays on the
// boundary. Each edge hole is then a whole cell with one straight side, and
// the border comes out exactly as asked all the way round.
//
// F is the rectangle the cells tile. It is half a rib outside the border
// line, so that shrinking a cell by half a rib lands its hole on that line.
// =====================================================================

function clamp01(v) = max(0, min(1, v));

// Quads: a stretched grid. Edge corners slide along their edge only, and the
// four outer corners do not move at all.
function quad_fit(F, cell, irregular, s) =
    let (lo = F[0], W = F[1] - F[0],
         nx = max(1, round(W[0] / cell)), ny = max(1, round(W[1] / cell)),
         px = W[0] / nx, py = W[1] / ny,
         a  = clamp01(irregular) * JITTER_QUAD * min(px, py),
         V  = [ for (i = [0 : nx])
                  [ for (j = [0 : ny])
                      let (d = jitter(i, j, a, s))
                      lo + [ i * px + (i == 0 || i == nx ? 0 : d[0]),
                             j * py + (j == 0 || j == ny ? 0 : d[1]) ] ] ])
    [ for (i = [0 : nx - 1], j = [0 : ny - 1])
        [ V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1] ] ];

// Nominal x positions, in pitches, of row j of a fitted triangle web. Odd
// rows are shifted half a pitch, and gain a corner on each wall so that the
// row still starts and ends exactly on the edge.
function tri_row_x(j, nx) =
    j % 2 == 0 ? [ for (k = [0 : nx]) k ]
               : concat([0], [ for (k = [0 : nx - 1]) k + 0.5 ], [nx]);

// Triangulates the band between two rows of corners, B below and T above,
// walking along both and always stepping along the row whose next edge is
// further behind -- judged on nominal positions, so jitter cannot change
// which triangles are made. On the regular web this gives the even
// triangles, with a right-angled half-triangle at each end of odd bands.
function zipper(B, T, bx, tx, ib = 0, it = 0) =
    ib == len(B) - 1 && it == len(T) - 1 ? []
    : let (up = ib == len(B) - 1
                || (it < len(T) - 1 && tx[it] + tx[it + 1] < bx[ib] + bx[ib + 1]))
      up ? concat([ [ B[ib], T[it + 1], T[it] ] ], zipper(B, T, bx, tx, ib, it + 1))
         : concat([ [ B[ib], B[ib + 1], T[it] ] ], zipper(B, T, bx, tx, ib + 1, it));

function tri_fit(F, cell, irregular, s) =
    let (p0 = cell * PITCH_TRI, lo = F[0], W = F[1] - F[0],
         nx = max(1, round(W[0] / p0)),
         ny = max(1, round(W[1] / (p0 * sqrt(3) / 2))),
         px = W[0] / nx, h = W[1] / ny,
         a  = clamp01(irregular) * JITTER_TRI * min(px, 2 * h / sqrt(3)),
         // Jitter tapers off within a pitch of either wall. The half-triangles
         // at the ends of odd rows start half as wide as the rest, and at full
         // jitter their inner corner can run nearly into the wall.
         R  = [ for (j = [0 : ny])
                  let (xs = tri_row_x(j, nx), last = len(xs) - 1)
                  [ for (k = [0 : last])
                      let (d = jitter(k, j, a, s) * min(1, xs[k], nx - xs[k]))
                      lo + [ xs[k] * px + d[0],
                             j * h + (j == 0 || j == ny ? 0 : d[1]) ] ] ])
    [ for (j = [0 : ny - 1])
        each zipper(R[j], R[j + 1], tri_row_x(j, nx), tri_row_x(j + 1, nx)) ];

// 6 sides: Voronoi cells of seeds that all lie inside F, each cell
// clipped to F. With no seed outside, every point of F belongs to some inside
// seed, so the clipped cells tile F exactly. Odd rows put a seed on each wall,
// which gives the half-cells a honeycomb has against a straight edge.
function hex_row_x(j, nx) =
    j % 2 == 0 ? [ for (k = [0 : nx - 1]) k + 0.5 ] : [ for (k = [0 : nx]) k ];

function voronoi_fit(F, cell, irregular, s) =
    let (p0 = cell * PITCH_HEX, lo = F[0], hi = F[1], W = hi - lo,
         nx = max(1, round(W[0] / p0)),
         ny = max(1, round(W[1] / (p0 * sqrt(3) / 2))),
         px = W[0] / nx, h = W[1] / ny,
         // Jitter stays under half a row and half a pitch, so no seed can
         // leave F; seeds on a wall move along it only.
         a  = clamp01(irregular) * JITTER_HEX * min(px, 2 * h / sqrt(3)),
         S  = [ for (j = [0 : ny - 1])
                  let (xs = hex_row_x(j, nx), last = len(xs) - 1)
                  [ for (k = [0 : last])
                      let (d = jitter(k, j, a, s), wall = xs[k] == 0 || xs[k] == nx)
                      lo + [ xs[k] * px + (wall ? 0 : d[0]), (j + 0.5) * h + d[1] ] ] ],
         // Reach: no point of F is further than rc from its nearest seed, so
         // no cell reaches further than rc from its own seed. Two bounds, as
         // the stretched lattice is not equilateral: the circumradius of one
         // lattice triangle (the open-lattice covering radius, which grows
         // without limit as rows squash flat), and a corner of F to the first
         // seed in from it. Plus the jitter of both seeds involved.
         rc = max((h * h + px * px / 4) / (2 * h), norm([px, h]) / 2) + 2 * a + EPS,
         // Only seeds within 2 * rc can share an edge. Searching every row
         // that close matters: a neighbour missed here leaves two cells
         // overlapping, and the rib between them simply vanishes.
         dj = ceil((2 * rc + 2 * a) / h) + 1)
    [ for (j = [0 : ny - 1], k = [0 : len(S[j]) - 1])
        let (sd = S[j][k],
             nbrs = [ for (jj = [max(0, j - dj) : min(ny - 1, j + dj)], q = S[jj])
                        if (q != sd && norm(q - sd) < 2 * rc) q ],
             box = [ [max(lo[0], sd[0] - rc), max(lo[1], sd[1] - rc)],
                     [min(hi[0], sd[0] + rc), min(hi[1], sd[1] + rc)] ],
             c = clip_all([ box[0], [box[1][0], box[0][1]], box[1], [box[0][0], box[1][1]] ],
                          sd, nbrs))
        if (len(c) >= 3) c ];

function fitted_cells(shape, F, cell, irregular, s) =
    shape == "3 sides"        ? tri_fit(F, cell, irregular, s)
  : shape == "6 sides" ? voronoi_fit(F, cell, irregular, s)
  :                             quad_fit(F, cell, irregular, s);


// =====================================================================
// LIBRARY MODULE
// =====================================================================

// The holes, as 2D geometry, confined to the 2D region given as children.
//
//   bounds         [[xmin, ymin], [xmax, ymax]] enclosing the region. OpenSCAD
//                  cannot measure geometry, so the pattern needs telling where
//                  to grow. With no children, this box is the region.
//   cell_size      average cell width (see the customizer note above)
//   rib            web left between neighbouring holes, guaranteed minimum
//   shape          "4 sides", "3 sides" or "6 sides"
//   irregularity   0..1
//   corner_radius  hole corner rounding
//   min_hole       a hole that cannot hold a circle this wide is dropped
//   seed           pattern selector
//   border         solid band kept inside the region's edge; raised to rib
//   fit            true: build the cells to fit the bounds rectangle, so the
//                  edge holes are whole cells. Only right when the region IS
//                  that rectangle -- rounded corners are fine, they are still
//                  cropped. false: grow the pattern past the region and crop
//                  it, which suits any shape. Default: fit when there are no
//                  children, crop when there are.
//
// Subtract the result from your own part. It is 2D, so extrude it first.
module leopard_vent_2d(bounds, cell_size = 14, rib = 2, shape = "4 sides",
                       irregularity = 0.7, corner_radius = 1, min_hole = 4,
                       seed = 1, border = 0, fit = undef) {
    assert(is_list(bounds) && len(bounds) == 2,
           "leopard_vent_2d: bounds must be [[xmin, ymin], [xmax, ymax]]");
    assert(shape == "4 sides" || shape == "3 sides" || shape == "6 sides",
           str("leopard_vent_2d: unknown shape \"", shape, "\""));
    assert(rib >= MIN_RIB,
           str("leopard_vent_2d: rib ", rib, " is under ", MIN_RIB,
               "mm, two extrusion widths, and will not print as a wall"));
    hw = hole_width(shape, cell_size, rib);
    assert(hw >= MIN_HOLE,
           str("leopard_vent_2d: a ", rib, "mm rib in a ", cell_size, "mm ", shape,
               " cell leaves holes only ", hw, "mm wide -- raise cell_size or lower the rib"));

    // A radius past 0.4 of the nominal hole erases the smaller jittered cells
    // outright and turns the rest into circles. Clamped, not refused: it is a
    // look, not a structural value.
    r = min(max(corner_radius, EPS), 0.4 * hw);
    if (r < corner_radius)
        echo(str("LEOPARD VENT  corner radius ", corner_radius, " clamped to ", r,
                 " -- the nominal hole is only ", hw, "mm wide"));

    // Same reasoning, a little looser: past 0.8 of the nominal hole, ordinary
    // jittered cells start failing the test, not just border fragments.
    keep_r = min(max(min_hole, 0) / 2, 0.4 * hw);
    if (keep_r < min_hole / 2)
        echo(str("LEOPARD VENT  min_hole ", min_hole, " clamped to ", 2 * keep_r,
                 " -- the nominal hole is only ", hw, "mm wide"));

    bw = max(border, rib);
    lo = bounds[0];
    hi = bounds[1];
    assert(min(hi - lo) > 2 * bw,
           str("leopard_vent_2d: a ", bw, "mm border leaves no room inside bounds ",
               bounds));
    fitted = is_undef(fit) ? $children == 0 : fit;
    inset = (bw - rib / 2) * [1, 1];
    cells = fitted ? fitted_cells(shape, [lo + inset, hi - inset], cell_size, irregularity, seed)
                   : vent_cells(shape, lo, hi, cell_size, irregularity, seed);

    // Per cell, not on the union, so that the size test below sees one hole
    // at a time. The holes never touch, so the result is the same union.
    // Every hole lies inside the bounds, so their diagonal is reach enough.
    for (c = cells)
        keep_if_fits(keep_r, norm(hi - lo))
            // Opening: shrink then grow by r. Rounds every convex corner to r
            // and drops anything narrower than 2r. It only ever removes hole,
            // so a rib can only come out thicker than asked.
            offset(r = r) offset(r = -r)
                intersection() {
                    offset(delta = -bw)
                        if ($children > 0) children(); else translate(lo) square(hi - lo);
                    offset(delta = -rib / 2) polygon(c);
                }
}

// Passes its child through whole if a circle of radius R fits inside it, and
// drops it entirely if not. Shrinking by R leaves nothing exactly when no such
// circle fits; growing what is left by at least the hole's own width (reach)
// then covers the whole hole again. Unlike a plain opening at R, a hole that
// passes keeps its exact shape -- corners and all.
module keep_if_fits(R, reach) {
    if (R <= 0)
        children();
    else
        intersection() {
            children();
            offset(delta = reach) offset(r = -R) children();
        }
}


// =====================================================================
// STANDALONE PART
// =====================================================================

is_circle = panel_shape == "Circle";
panel_w = panel_width;
panel_h = is_circle ? panel_width : panel_height;
panel_r = max(0, min(panel_corner_radius, min(panel_w, panel_h) / 2 - EPS));
panel_bounds = [ [-panel_w / 2, -panel_h / 2], [panel_w / 2, panel_h / 2] ];

border_w = max(border, rib_thickness);
nominal_hole = hole_width(cell_shape, cell_size, rib_thickness);
inner_span = min(panel_w, panel_h) - 2 * border_w;

pocketed = hole_type == "Pocket";
hole_depth = pocketed ? thickness - floor_thickness : thickness;
hole_floor = thickness - hole_depth;

assert(inner_span >= MIN_HOLE,
       str("border ", border_w, "mm on each side leaves only ", inner_span,
           "mm for holes -- shrink the border or enlarge the panel"));
assert(!pocketed || hole_depth >= MIN_POCKET,
       str("a ", floor_thickness, "mm floor in a ", thickness,
           "mm panel leaves pockets ", hole_depth,
           "mm deep -- thin the floor or thicken the panel"));

module panel_2d() {
    if (is_circle)
        circle(d = panel_w);
    else
        offset(r = panel_r) offset(delta = -panel_r)
            square([panel_w, panel_h], center = true);
}

module holes_2d() {
    leopard_vent_2d(bounds = panel_bounds, cell_size = cell_size, rib = rib_thickness,
                    shape = cell_shape, irregularity = irregularity,
                    corner_radius = hole_corner_radius, min_hole = min_hole,
                    seed = seed, border = border_w, fit = !is_circle && edges == "Fit")
        panel_2d();
}

// Built entirely from 2D booleans and extrusions, never a 3D difference.
// Measured on this file: 47 holes take 0.1s this way and 1.2s by 3D
// difference; 310 holes take 0.4s and 8.8s. The gap widens with hole count.
module panel() {
    if (pocketed) {
        linear_extrude(height = hole_floor) panel_2d();
        translate([0, 0, hole_floor])
            linear_extrude(height = hole_depth)
                difference() { panel_2d(); holes_2d(); }
    } else {
        linear_extrude(height = thickness)
            difference() { panel_2d(); holes_2d(); }
    }
}

module cutter() {
    z0 = pocketed ? hole_floor : -CUTTER_OVERSHOOT;
    translate([0, 0, z0])
        linear_extrude(height = thickness + CUTTER_OVERSHOOT - z0)
            holes_2d();
}

if (output == "Cutter") cutter();
else if (output == "2D holes") holes_2d();
else panel();

echo(str("LEOPARD VENT  ", cell_shape, "  cell ", cell_size, "mm  rib ", rib_thickness,
         "mm  irregularity ", irregularity, "  seed ", seed,
         "  edges ", is_circle ? "Crop (circle)" : edges));
echo(str("LEOPARD VENT  ", panel_shape, " ", panel_w, is_circle ? "" : str(" x ", panel_h),
         " x ", thickness, "mm  border ", border_w, "mm  nominal hole ", nominal_hole,
         "mm  ", hole_type, pocketed ? str(" (floor ", hole_floor, "mm)") : ""));


// =====================================================================
// USING IT IN YOUR OWN PART
//
// `use <>` imports the module and none of the standalone part above. Example:
// an 80 x 50 vent through the 2.5mm lid of a box, kept 4mm off the lid edge.
//
//   use <leopard_vent.scad>
//
//   difference() {
//       my_box();
//       translate([10, 10, lid_z - 1])
//           linear_extrude(height = 2.5 + 2)
//               leopard_vent_2d(bounds = [[0, 0], [80, 50]],
//                               cell_size = 10, rib = 1.6, border = 4);
//   }
//
// Any 2D shape can be the region -- pass it as a child, with bounds that
// enclose it:
//
//   leopard_vent_2d(bounds = [[-30, -30], [30, 30]], shape = "6 sides")
//       circle(d = 60);
//
// That is a 3D difference, which works but costs CGAL time -- about ten to
// twenty times the 2D route at a few dozen to a few hundred holes. Where the
// part allows it, subtract in 2D before extruding, as panel() above does.
//
// With no child, as in the first example, the bounds box is the region and
// the cells are fitted to it. With a child they are cropped to it, since only
// a rectangle can be fitted; pass fit = true if the child is that rectangle.
// =====================================================================
