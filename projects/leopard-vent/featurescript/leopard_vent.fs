FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");

// =====================================================================
// LEOPARD VENT -- irregular-cell venting and lightening pattern (Onshape)
// =====================================================================
//
// Cuts a field of uneven polygon holes into one or more planar faces, with
// ribs of one set thickness between them. The look borrows from leopard print
// -- scattered spots of differing size and shape -- simplified to straight-
// sided cells: four sides, three for a triangle web, or six for uneven
// Voronoi cells.
//
// The rib is exact, by construction. The cells tile the plane edge to edge
// and each is shrunk by half a rib, so facing holes are exactly one rib apart
// and junctions only come out thicker. The corner rounding is exact the same
// way: each hole is worked out shrunk by the corner radius -- its "core" --
// and sketched grown back by it, every edge pushed out by the radius and
// every corner a true arc.
//
// Exact bands (on by default): the material left round the outline (the
// border) and round every hole already in the face (the band width) is an
// exact offset of those edges -- lines parallel to straight edges, arcs
// concentric with round ones, arcs round inside corners -- and each cell's
// hole is its core with that taken out. Where a hole meets a band it follows
// it, so ribs run into the band and nothing beyond it is filled in. This is
// worked out in maths, not with Onshape's offset, which fails as soon as the
// border is bigger than one of the face's fillets. Lines and arcs of the face
// are used exactly; any other curve is sampled into chords, and its loop is
// kept a 0.005 mm chord allowance further off. A cell whose bands cannot be
// drawn cleanly is tried again 0.05 mm smaller (1 hole in 170 across the test
// faces) and failing that (1 in 6000) gets the straight cuts below, which
// only ever leave more material.
//
// Struts (6-sided cells): a circular hole of at least a set size gets a ring
// of cells round it, so the ribs between them run straight out from its band
// into the web, like spokes, and a knock on the bolt has a straight path into
// the plate. They are ordinary cell edges, one rib thick like every other.
//
// With bands off, every hole is cut straight: by the outline's chords, and by
// one straight cut per hole in the face, chosen to keep the most of the hole
// -- exact beside a straight edge, conservative elsewhere.
//
// Tested outside Onshape, in the repository this ships with: tools/fsmirror.py
// mirrors this geometry function for function and measures it against the
// true face outline, and tools/fsinterp.py runs this file's own maths --
// type annotations included -- and matches the mirror point for point. What
// that cannot cover is the Onshape calls themselves: reading the face, and
// the sketch, extrude and boolean. See ../docs/featurescript.md.
//
// Paste over everything in a new Feature Studio: the first two lines are the
// ones Onshape 3083 writes itself. Every std call here was checked against the
// std library source at 2960, and every one is reachable through common.fs.
// =====================================================================


export enum LeopardCellShape
{
    annotation { "Name" : "4 sides" }
    QUAD,
    annotation { "Name" : "3 sides" }
    TRI,
    annotation { "Name" : "6 sides" }
    HEX
}

export enum LeopardHoleType
{
    annotation { "Name" : "Through" }
    THROUGH,
    annotation { "Name" : "Pocket" }
    POCKET
}

const CELL_SIZE_BOUNDS =
{
    (millimeter) : [1, 14, 10000],
    (centimeter) : 1.4,
    (meter) : 0.014,
    (inch) : 0.55,
    (foot) : 0.046,
    (yard) : 0.015
} as LengthBoundSpec;

const RIB_BOUNDS =
{
    (millimeter) : [0.1, 2, 1000],
    (centimeter) : 0.2,
    (meter) : 0.002,
    (inch) : 0.08,
    (foot) : 0.0066,
    (yard) : 0.0022
} as LengthBoundSpec;

const BORDER_BOUNDS =
{
    (millimeter) : [0, 5, 10000],
    (centimeter) : 0.5,
    (meter) : 0.005,
    (inch) : 0.2,
    (foot) : 0.016,
    (yard) : 0.0055
} as LengthBoundSpec;

const CORNER_BOUNDS =
{
    (millimeter) : [0, 1, 1000],
    (centimeter) : 0.1,
    (meter) : 0.001,
    (inch) : 0.04,
    (foot) : 0.0033,
    (yard) : 0.0011
} as LengthBoundSpec;

const MIN_HOLE_BOUNDS =
{
    (millimeter) : [0, 4, 10000],
    (centimeter) : 0.4,
    (meter) : 0.004,
    (inch) : 0.16,
    (foot) : 0.013,
    (yard) : 0.0044
} as LengthBoundSpec;

const DEPTH_BOUNDS =
{
    (millimeter) : [0.01, 2, 100000],
    (centimeter) : 0.2,
    (meter) : 0.002,
    (inch) : 0.08,
    (foot) : 0.0066,
    (yard) : 0.0022
} as LengthBoundSpec;

const RING_BOUNDS =
{
    (millimeter) : [0, 5, 10000],
    (centimeter) : 0.5,
    (meter) : 0.005,
    (inch) : 0.2,
    (foot) : 0.016,
    (yard) : 0.0055
} as LengthBoundSpec;

const STRUT_MIN_BOUNDS =
{
    (millimeter) : [0, 10, 10000],
    (centimeter) : 1,
    (meter) : 0.01,
    (inch) : 0.4,
    (foot) : 0.033,
    (yard) : 0.011
} as LengthBoundSpec;

const IRREGULARITY_BOUNDS = { (unitless) : [0, 0.7, 1] } as RealBoundSpec;

const SEED_BOUNDS = { (unitless) : [1, 1, 1000000] } as IntegerBoundSpec;


// ---------------------------------------------------------------- constants
//
// Everything below works in plain numbers, in millimetres, in the face's own
// coordinate system: z out of the face, x along its longest straight edge.

// Lattice pitch per unit of cell size, so a cell covers about cellSize^2
// whatever its shape: an equilateral triangle of side s covers s^2 sqrt(3)/4,
// a honeycomb cell at spacing s covers s^2 sqrt(3)/2.
const PITCH_TRI = sqrt(4 / sqrt(3));
const PITCH_HEX = sqrt(2 / sqrt(3));

// Width of the nominal hole per unit of pitch: twice a triangle's inradius,
// or 1 for a square side or across a hexagon's flats.
const ACROSS_TRI = 1 / sqrt(3);

// Largest jitter radius at irregularity 1, as a fraction of the pitch. A
// quad turns non-convex once a corner moves 0.354 of a pitch; a triangle
// turns inside out once two corners close its 0.866 altitude; a Voronoi
// cell cannot go invalid, so its cap only keeps seeds from crowding.
const JITTER_QUAD = 0.35;
const JITTER_TRI = 0.28;
const JITTER_HEX = 0.35;

const MARGIN = 4;          // extra lattice rows round a cropped pattern
const SAG = 0.005;         // mm: allowed chord error when sampling a curved edge
const SPLINE_STEP = 0.5;   // mm between samples on an edge neither line nor arc
const MAX_EDGE_SAMPLES = 4000;
const TINY_EDGE = 0.01;    // mm: shorter hole edges are merged before sketching
const TINY_TURN = 1e-3;    // sine of the smallest corner turn kept as a corner
const MIN_RADIUS = 0.01;   // mm: a corner radius below this is drawn sharp
const TINY_AREA = 1e-6;    // mm^2
const CHAIN_TOL = 1e-3;    // mm: how close an edge end must be to the next start
const START_ABOVE = 0.05;  // mm: cutters start this far outside the face
const MIN_TURN = 0.02;     // sine of the smallest corner a hole may turn where an arc meets anything
const TAU = 1e-9;          // mm: lengths and distances this close are equal
const LINK = 1e-7;         // mm: ends this close are one point when pieces are joined into loops
const PEPS = 1e-9;         // parameter slack at the ends of a piece
const SMOOTH = 1e-6;       // sine below which two pieces meet tangentially, with no corner
const NUDGE = 0.05;        // mm: how much a core that will not come out cleanly is shrunk to try again


annotation { "Feature Type Name" : "Leopard vent",
             "Feature Type Description" : "Irregular 3-, 4- or 6-sided vent or lightening holes with an exact rib thickness." }
export const leopardVent = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Faces", "Filter" : EntityType.FACE && GeometryType.PLANE && ConstructionObject.NO && BodyType.SOLID }
        definition.faces is Query;

        annotation { "Name" : "Cell shape", "UIHint" : UIHint.SHOW_LABEL }
        definition.cellShape is LeopardCellShape;

        annotation { "Name" : "Cell size" }
        isLength(definition.cellSize, CELL_SIZE_BOUNDS);

        annotation { "Name" : "Rib thickness" }
        isLength(definition.ribThickness, RIB_BOUNDS);

        annotation { "Name" : "Border" }
        isLength(definition.border, BORDER_BOUNDS);

        annotation { "Name" : "Irregularity" }
        isReal(definition.irregularity, IRREGULARITY_BOUNDS);

        annotation { "Name" : "Hole corner radius" }
        isLength(definition.cornerRadius, CORNER_BOUNDS);

        annotation { "Name" : "Smallest hole kept" }
        isLength(definition.minHole, MIN_HOLE_BOUNDS);

        annotation { "Name" : "Seed" }
        isInteger(definition.seed, SEED_BOUNDS);

        annotation { "Name" : "Fit cells to the face", "Default" : true }
        definition.fit is boolean;

        // The ids roundRings, ringWidth, spokes and spokeMinD are kept from
        // the version with rings and spoked wheels, so features made with it
        // keep their settings.
        annotation { "Name" : "Exact bands round holes and edges", "Default" : true }
        definition.roundRings is boolean;

        if (definition.roundRings)
        {
            annotation { "Name" : "Band width round holes" }
            isLength(definition.ringWidth, RING_BOUNDS);

            if (definition.cellShape == LeopardCellShape.HEX)
            {
                annotation { "Name" : "Struts round circular holes", "Default" : true }
                definition.spokes is boolean;

                if (definition.spokes)
                {
                    annotation { "Name" : "Struts only on holes from" }
                    isLength(definition.spokeMinD, STRUT_MIN_BOUNDS);
                }
            }
        }

        annotation { "Name" : "Hole type", "UIHint" : UIHint.HORIZONTAL_ENUM }
        definition.holeType is LeopardHoleType;

        if (definition.holeType == LeopardHoleType.POCKET)
        {
            annotation { "Name" : "Pocket depth" }
            isLength(definition.pocketDepth, DEPTH_BOUNDS);
        }

        annotation { "Name" : "Pattern direction (optional)", "Filter" : GeometryType.LINE, "MaxNumberOfPicks" : 1 }
        definition.direction is Query;
    }
    {
        const shape = definition.cellShape;
        const cell = definition.cellSize / millimeter;
        const rib = definition.ribThickness / millimeter;
        const corner = definition.cornerRadius / millimeter;
        const minHole = definition.minHole / millimeter;

        const hw = cell * pitchOf(shape) * acrossOf(shape) - rib;
        if (hw <= 0.1)
            throw regenError("The rib is too thick for the cell size: there is no room left for a hole.",
                             ["ribThickness", "cellSize"]);

        // Same limits as the OpenSCAD version: past these, ordinary cells start
        // vanishing rather than just the slivers the settings are meant for.
        var r = min(corner, 0.4 * hw);
        const keepR = min(minHole / 2, 0.4 * hw);
        var notes = [];
        if (r < corner - 1e-9)
            notes = append(notes, "corner radius limited to " ~ roundToPrecision(r, 2) ~ " mm");
        if (keepR < minHole / 2 - 1e-9)
            notes = append(notes, "smallest hole limited to " ~ roundToPrecision(2 * keepR, 2) ~ " mm");
        if (r < MIN_RADIUS)
            r = 0;

        var settings = {
                "shape" : shape, "cell" : cell, "rib" : rib, "r" : r, "keepR" : keepR,
                "border" : max(definition.border / millimeter, rib),
                "irregular" : definition.irregularity, "seed" : definition.seed,
                "fit" : definition.fit, "struts" : false
            };
        // ring: undefined for straight cuts round each hole in the face.
        if (definition.roundRings)
        {
            settings.ring = max(definition.ringWidth / millimeter, rib);
            if (shape == LeopardCellShape.HEX && definition.spokes)
            {
                settings.struts = true;
                settings.strutMinD = definition.spokeMinD / millimeter;
            }
        }

        const faces = evaluateQuery(context, definition.faces);
        if (size(faces) == 0)
            throw regenError("Select one or more planar faces.", ["faces"]);

        // Plan every face before cutting any, so that one face's holes cannot
        // change the outline the next face is measured from.
        var plans = [];
        for (var fi = 0; fi < size(faces); fi += 1)
            plans = append(plans, planFace(context, faces[fi], definition.direction, settings));

        var holeTotal = 0;
        var openArea = 0;
        var faceArea = 0;
        for (var fi = 0; fi < size(plans); fi += 1)
        {
            const plan = plans[fi];
            faceArea += plan.faceArea;
            if (size(plan.holes) == 0)
                continue;

            const sketchId = id + ("sketch" ~ fi);
            const sketch = newSketchOnPlane(context, sketchId, { "sketchPlane" : plan.sketchPlane });
            for (var hi = 0; hi < size(plan.holes); hi += 1)
            {
                drawHole(sketch, "h" ~ hi, plan.holes[hi], r);
                openArea += holeArea(plan.holes[hi], r);
            }
            skSolve(sketch);

            const depth = definition.holeType == LeopardHoleType.POCKET
                ? definition.pocketDepth
                : (plan.below + 1) * millimeter;

            opExtrude(context, id + ("cut" ~ fi), {
                        "entities" : qSketchRegion(sketchId),
                        "direction" : -plan.sketchPlane.normal,
                        "endBound" : BoundingType.BLIND,
                        "endDepth" : depth,
                        "startBound" : BoundingType.BLIND,
                        "startDepth" : START_ABOVE * millimeter
                    });
            opBoolean(context, id + ("subtract" ~ fi), {
                        "tools" : qCreatedBy(id + ("cut" ~ fi), EntityType.BODY),
                        "targets" : qOwnerBody(faces[fi]),
                        "operationType" : BooleanOperationType.SUBTRACTION
                    });
            opDeleteBodies(context, id + ("deleteSketch" ~ fi), {
                        "entities" : qCreatedBy(sketchId, EntityType.BODY)
                    });
            holeTotal += size(plan.holes);
        }

        if (holeTotal == 0)
        {
            reportFeatureWarning(context, id, "No holes fit. Try a smaller border, cell size or rib.");
            return;
        }

        var message = "Leopard vent: " ~ holeTotal ~ " holes, " ~
                      roundToPrecision(100 * openArea / faceArea, 1) ~ "% open";
        if (size(notes) > 0)
        {
            message = message ~ " (";
            for (var k = 0; k < size(notes); k += 1)
                message = message ~ (k > 0 ? "; " : "") ~ notes[k];
            message = message ~ ")";
        }
        reportFeatureInfo(context, id, message);
    });


// ---------------------------------------------------------------- one face

// Reads one face, and works out every hole it gets: the cores, the plane to
// sketch them on, and how far the part reaches below the face.
function planFace(context is Context, face is Query, directionQuery is Query, settings is map) returns map
{
    const facePlane = evPlane(context, { "face" : face });
    const edges = evaluateQuery(context, qAdjacent(face, AdjacencyType.EDGE, EntityType.EDGE));

    // Pattern x axis: the picked edge if any, else the longest straight edge
    // of the face, else whatever the plane offers. Following a straight edge
    // is what lets a rectangular face be fitted exactly.
    var curves = [];
    var lengths = [];
    var xDir = facePlane.x;
    var best = 0;
    for (var e in edges)
    {
        const curve = evCurveDefinition(context, { "edge" : e, "returnBSplinesAsOther" : true });
        const len = evLength(context, { "entities" : e }) / millimeter;
        curves = append(curves, curve);
        lengths = append(lengths, len);
        if (curve is Line && len > best)
        {
            best = len;
            xDir = curve.direction;
        }
    }
    if (!isQueryEmpty(context, directionQuery))
        xDir = evLine(context, { "edge" : directionQuery }).direction;
    xDir = xDir - facePlane.normal * dot(xDir, facePlane.normal);
    if (norm(xDir) < 1e-6)
        throw regenError("The pattern direction edge is perpendicular to the face.", ["direction"]);
    xDir = normalize(xDir);

    const sketchPlane = plane(facePlane.origin, facePlane.normal, xDir);
    const cSys = planeToCSys(sketchPlane);

    // Sample every edge with the face on its left, so each loop chains end to
    // start, the outer loop runs counter-clockwise and inner loops clockwise.
    var polys = [];
    for (var k = 0; k < size(edges); k += 1)
        polys = append(polys, sampleEdge(context, edges[k], face, curves[k], lengths[k], cSys));

    const region = buildRegion(polys, max(settings.cell * pitchOf(settings.shape), 1));
    const holes = planHoles(region, polys, settings);

    const partBox = evBox3d(context, { "topology" : qOwnerBody(face), "cSys" : cSys, "tight" : false });
    return {
            "holes" : holes,
            "sketchPlane" : sketchPlane,
            "below" : max(-partBox.minCorner[2] / millimeter, 0),
            "faceArea" : evArea(context, { "entities" : face }) / (millimeter * millimeter)
        };
}

// Points along one edge in face coordinates, and the worst chord error.
function sampleEdge(context is Context, edge is Query, face is Query, curve, len is number, cSys is CoordSystem) returns map
{
    var n = 1;
    var sag = 0;
    var circle = undefined;
    if (curve is Circle)
    {
        const rad = curve.radius / millimeter;
        const o = fromWorld(cSys, curve.coordSystem.origin) / millimeter;
        circle = { "c" : vector(o[0], o[1]), "r" : rad };
        const step = rad > SAG ? 2 * (acos(1 - SAG / rad) / radian) : len / rad;
        n = max(2, ceil((len / rad) / step));
        sag = SAG;
    }
    else if (!(curve is Line))
    {
        n = max(2, ceil(len / SPLINE_STEP));
        sag = SAG;
    }
    n = min(n, MAX_EDGE_SAMPLES);
    var params = [];
    for (var k = 0; k <= n; k += 1)
        params = append(params, k / n);
    const lines = evEdgeTangentLines(context, { "edge" : edge, "parameters" : params, "face" : face });
    var pts = [];
    for (var ln in lines)
    {
        const p = fromWorld(cSys, ln.origin) / millimeter;
        pts = append(pts, vector(p[0], p[1]));
    }
    // The bands use the circle itself, so it had better be where the edge
    // is. If any sample is off it, work from the chords instead -- a band
    // SAG wider and no struts, but never one too thin.
    if (circle != undefined)
    {
        for (var q in pts)
        {
            if (abs(norm(q - circle.c) - circle.r) > 1e-5)
            {
                circle = undefined;
                break;
            }
        }
    }
    return { "pts" : pts, "sag" : sag, "circle" : circle };
}


// ---------------------------------------------------------------- hashing

function pitchOf(shape is LeopardCellShape) returns number
{
    return shape == LeopardCellShape.TRI ? PITCH_TRI : (shape == LeopardCellShape.HEX ? PITCH_HEX : 1);
}

function acrossOf(shape is LeopardCellShape) returns number
{
    return shape == LeopardCellShape.TRI ? ACROSS_TRI : 1;
}

function jitterCapOf(shape is LeopardCellShape) returns number
{
    return shape == LeopardCellShape.TRI ? JITTER_TRI : (shape == LeopardCellShape.HEX ? JITTER_HEX : JITTER_QUAD);
}

function wrap360(a is number) returns number
{
    return a - 360 * floor(a / 360);
}

function hash01(n is number, s is number) returns number
{
    const a0 = sin(wrap360(n * 12.9898 + s * 78.233 + 41.7) * degree) * 43758.5453;
    const a = a0 - floor(a0);
    const c0 = sin(wrap360(a * 311.7 + n * 74.7 + s * 19.19) * degree) * 24634.6345;
    return c0 - floor(c0);
}

// Uniform over a disc of radius a, so no direction is favoured.
function jitterVec(i is number, j is number, a is number, s is number) returns Vector
{
    const n = (i * 977 + j) * 2;
    const r = a * sqrt(hash01(n, s));
    const t = 360 * hash01(n + 1, s);
    return vector(r * cos(t * degree), r * sin(t * degree));
}


// ---------------------------------------------------------------- 2D helpers

function cross2(a is Vector, b is Vector) returns number
{
    return a[0] * b[1] - a[1] * b[0];
}

function signedArea(poly is array) returns number
{
    var s = 0;
    const n = size(poly);
    for (var k = 0; k < n; k += 1)
        s += poly[k][0] * poly[(k + 1) % n][1] - poly[(k + 1) % n][0] * poly[k][1];
    return s / 2;
}

function centroid2(poly is array) returns Vector
{
    var s = vector(0, 0);
    for (var p in poly)
        s = s + p;
    return s / size(poly);
}

function ccw(poly is array) returns array
{
    return signedArea(poly) >= 0 ? poly : reverse(poly);
}

// Keep the part of a polygon where (x - m) . d < 0. Strict, so a corner
// lying exactly on the line is emitted once, as a crossing.
function clipHalf(poly is array, m is Vector, d is Vector) returns array
{
    const n = size(poly);
    if (n < 3)
        return [];
    var out = [];
    for (var k = 0; k < n; k += 1)
    {
        const a = poly[k];
        const b = poly[(k + 1) % n];
        const fa = dot(a - m, d);
        const fb = dot(b - m, d);
        if (fa < 0)
            out = append(out, a);
        if ((fa < 0) != (fb < 0))
            out = append(out, a + (b - a) * (fa / (fa - fb)));
    }
    return out;
}

// Keep the part of a polygon at least dist to the left of the line a -> b.
function clipLeftOf(poly is array, a is Vector, b is Vector, dist is number) returns array
{
    const t = normalize(b - a);
    const left = vector(-t[1], t[0]);
    return clipHalf(poly, a + left * dist, left * -1);
}

// Shrink a convex polygon by dist: clip it by each of its own edges, moved in.
function insetConvex(poly is array, dist is number) returns array
{
    const p = ccw(poly);
    var out = p;
    for (var k = 0; k < size(p); k += 1)
    {
        out = clipLeftOf(out, p[k], p[(k + 1) % size(p)], dist);
        if (size(out) < 3)
            return [];
    }
    return out;
}

// Drop corners that would make sketch entities too small to be safe: an edge
// under TINY_EDGE, or a corner that barely turns. On a convex polygon that
// replaces two edges by the chord inside them, so a rib can only thicken.
function tidy(poly is array) returns array
{
    var p = poly;
    var changed = true;
    while (changed && size(p) >= 3)
    {
        changed = false;
        const n = size(p);
        for (var k = 0; k < n; k += 1)
        {
            const e1 = p[k] - p[(k + n - 1) % n];
            const e2 = p[(k + 1) % n] - p[k];
            const l1 = norm(e1);
            const l2 = norm(e2);
            if (l1 < TINY_EDGE || l2 < TINY_EDGE || abs(cross2(e1, e2)) < TINY_TURN * l1 * l2)
            {
                p = concatenateArrays([subArray(p, 0, k), subArray(p, k + 1, n)]);
                changed = true;
                break;
            }
        }
    }
    if (size(p) < 3 || abs(signedArea(p)) <= TINY_AREA)
        return [];
    return p;
}

function segDist(p is Vector, a is Vector, b is Vector) returns number
{
    const ab = b - a;
    const l2 = dot(ab, ab);
    const t = l2 == 0 ? 0 : clamp(dot(p - a, ab) / l2, 0, 1);
    return norm(p - (a + ab * t));
}


// ---------------------------------------------------------------- cropped cells

function latticeFrame(lo is Vector, hi is Vector, p is number, h is number) returns map
{
    const hx = 2 * ceil((ceil((hi[0] - lo[0]) / (2 * p)) + MARGIN) / 2);
    const hy = 2 * ceil((ceil((hi[1] - lo[1]) / (2 * h)) + MARGIN) / 2);
    return { "origin" : (lo + hi) / 2 - vector(hx * p, hy * h), "nx" : 2 * hx, "ny" : 2 * hy };
}

// Jitter is keyed to the position relative to the centre, so a bigger face
// shows more of the same pattern round the middle.
function lattice(o is Vector, p is number, nx is number, ny is number, stagger is boolean, a is number, s is number) returns array
{
    const h = stagger ? p * sqrt(3) / 2 : p;
    var V = [];
    for (var i = 0; i <= nx; i += 1)
    {
        var col = [];
        for (var j = 0; j <= ny; j += 1)
        {
            const shift = stagger ? (j % 2) / 2 : 0;
            col = append(col, o + vector((i + shift) * p, j * h) + jitterVec(i - nx / 2, j - ny / 2, a, s));
        }
        V = append(V, col);
    }
    return V;
}

function touches(c is array, lo is Vector, hi is Vector) returns boolean
{
    var x0 = inf;
    var x1 = -inf;
    var y0 = inf;
    var y1 = -inf;
    for (var q in c)
    {
        x0 = min(x0, q[0]);
        x1 = max(x1, q[0]);
        y0 = min(y0, q[1]);
        y1 = max(y1, q[1]);
    }
    return x1 > lo[0] && x0 < hi[0] && y1 > lo[1] && y0 < hi[1];
}

function quadCells(V is array, nx is number, ny is number, lo is Vector, hi is Vector) returns array
{
    var out = [];
    for (var i = 0; i < nx; i += 1)
        for (var j = 0; j < ny; j += 1)
        {
            const c = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]];
            if (touches(c, lo, hi))
                out = append(out, c);
        }
    return out;
}

function triCells(V is array, nx is number, ny is number, lo is Vector, hi is Vector) returns array
{
    var out = [];
    for (var i = 0; i < nx; i += 1)
        for (var j = 0; j < ny; j += 1)
        {
            const pair = j % 2 == 0
                ? [[V[i][j], V[i + 1][j], V[i][j + 1]], [V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]]
                : [[V[i][j], V[i + 1][j], V[i + 1][j + 1]], [V[i][j], V[i + 1][j + 1], V[i][j + 1]]];
            for (var c in pair)
                if (touches(c, lo, hi))
                    out = append(out, c);
        }
    return out;
}

function clipAll(poly is array, s is Vector, nbrs is array) returns array
{
    var out = poly;
    for (var q in nbrs)
    {
        out = clipHalf(out, (s + q) / 2, q - s);
        if (size(out) < 3)
            return [];
    }
    return out;
}

// Voronoi cells by clipping a box round each seed against the bisector of
// every seed that could share an edge with it. Every point is within rc of
// some seed, so a cell fits within rc of its own seed and only seeds within
// 2 rc can neighbour it -- a 7 x 7 index window.
function voronoiCells(S is array, nx is number, ny is number, p is number, a is number, lo is Vector, hi is Vector) returns array
{
    const rc = p / sqrt(3) + a + 1e-6;
    var out = [];
    for (var i = 0; i <= nx; i += 1)
        for (var j = 0; j <= ny; j += 1)
        {
            const s = S[i][j];
            if (!(s[0] > lo[0] - rc && s[0] < hi[0] + rc && s[1] > lo[1] - rc && s[1] < hi[1] + rc))
                continue;
            var nbrs = [];
            for (var di = -3; di <= 3; di += 1)
                for (var dj = -3; dj <= 3; dj += 1)
                {
                    const ii = i + di;
                    const jj = j + dj;
                    if ((di != 0 || dj != 0) && ii >= 0 && ii <= nx && jj >= 0 && jj <= ny && norm(S[ii][jj] - s) < 2 * rc)
                        nbrs = append(nbrs, S[ii][jj]);
                }
            const startBox = [s + vector(-rc, -rc), s + vector(rc, -rc), s + vector(rc, rc), s + vector(-rc, rc)];
            const c = clipAll(startBox, s, nbrs);
            if (size(c) >= 3)
                out = append(out, c);
        }
    return out;
}

function cropCells(shape is LeopardCellShape, lo is Vector, hi is Vector, cell is number, irregular is number, s is number) returns array
{
    const p = cell * pitchOf(shape);
    const stagger = shape != LeopardCellShape.QUAD;
    const h = stagger ? p * sqrt(3) / 2 : p;
    const a = clamp(irregular, 0, 1) * jitterCapOf(shape) * p;
    const fr = latticeFrame(lo, hi, p, h);
    const V = lattice(fr.origin, p, fr.nx, fr.ny, stagger, a, s);
    if (shape == LeopardCellShape.TRI)
        return triCells(V, fr.nx, fr.ny, lo, hi);
    if (shape == LeopardCellShape.HEX)
        return voronoiCells(V, fr.nx, fr.ny, p, a, lo, hi);
    return quadCells(V, fr.nx, fr.ny, lo, hi);
}


// ---------------------------------------------------------------- fitted cells
//
// The lattice is stretched so a whole number of cells spans the rectangle
// lo..hi exactly, and corners on its edge stay on its edge. That rectangle is
// half a rib outside the border line, so shrinking a cell by half a rib lands
// its hole on the line.

function quadFit(lo is Vector, hi is Vector, cell is number, irregular is number, s is number) returns array
{
    const W = hi - lo;
    const nx = max(1, round(W[0] / cell));
    const ny = max(1, round(W[1] / cell));
    const px = W[0] / nx;
    const py = W[1] / ny;
    const a = clamp(irregular, 0, 1) * JITTER_QUAD * min(px, py);
    var V = [];
    for (var i = 0; i <= nx; i += 1)
    {
        var col = [];
        for (var j = 0; j <= ny; j += 1)
        {
            const d = jitterVec(i, j, a, s);
            col = append(col, lo + vector(i * px + ((i == 0 || i == nx) ? 0 : d[0]),
                                          j * py + ((j == 0 || j == ny) ? 0 : d[1])));
        }
        V = append(V, col);
    }
    var out = [];
    for (var i = 0; i < nx; i += 1)
        for (var j = 0; j < ny; j += 1)
            out = append(out, [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]);
    return out;
}

// Odd rows are shifted half a pitch and gain a corner on each wall, so every
// row starts and ends exactly on the edge.
function triRowX(j is number, nx is number) returns array
{
    var xs = [];
    if (j % 2 == 0)
    {
        for (var k = 0; k <= nx; k += 1)
            xs = append(xs, k);
    }
    else
    {
        xs = [0];
        for (var k = 0; k < nx; k += 1)
            xs = append(xs, k + 0.5);
        xs = append(xs, nx);
    }
    return xs;
}

// Triangulates the band between two rows of corners by walking along both,
// always stepping along the row whose next edge is further behind -- judged
// on nominal positions, so jitter cannot change which triangles are made.
function zipper(B is array, T is array, bx is array, tx is array) returns array
{
    var out = [];
    var ib = 0;
    var it = 0;
    while (!(ib == size(B) - 1 && it == size(T) - 1))
    {
        const up = ib == size(B) - 1 || (it < size(T) - 1 && tx[it] + tx[it + 1] < bx[ib] + bx[ib + 1]);
        if (up)
        {
            out = append(out, [B[ib], T[it + 1], T[it]]);
            it += 1;
        }
        else
        {
            out = append(out, [B[ib], B[ib + 1], T[it]]);
            ib += 1;
        }
    }
    return out;
}

function triFit(lo is Vector, hi is Vector, cell is number, irregular is number, s is number) returns array
{
    const p0 = cell * PITCH_TRI;
    const W = hi - lo;
    const nx = max(1, round(W[0] / p0));
    const ny = max(1, round(W[1] / (p0 * sqrt(3) / 2)));
    const px = W[0] / nx;
    const h = W[1] / ny;
    const a = clamp(irregular, 0, 1) * JITTER_TRI * min(px, 2 * h / sqrt(3));
    // Jitter tapers off within a pitch of either wall: the half-triangles at
    // the ends of odd rows start half as wide as the rest.
    var R = [];
    for (var j = 0; j <= ny; j += 1)
    {
        const xs = triRowX(j, nx);
        var row = [];
        for (var k = 0; k < size(xs); k += 1)
        {
            const d = jitterVec(k, j, a, s) * min(1, min(xs[k], nx - xs[k]));
            row = append(row, lo + vector(xs[k] * px + d[0], j * h + ((j == 0 || j == ny) ? 0 : d[1])));
        }
        R = append(R, row);
    }
    var out = [];
    for (var j = 0; j < ny; j += 1)
        out = concatenateArrays([out, zipper(R[j], R[j + 1], triRowX(j, nx), triRowX(j + 1, nx))]);
    return out;
}

// Odd rows put a seed on each wall: the half-cells a honeycomb has against a
// straight edge.
function hexRowX(j is number, nx is number) returns array
{
    var xs = [];
    if (j % 2 == 0)
    {
        for (var k = 0; k < nx; k += 1)
            xs = append(xs, k + 0.5);
    }
    else
    {
        for (var k = 0; k <= nx; k += 1)
            xs = append(xs, k);
    }
    return xs;
}

// Voronoi cells of seeds that all lie inside lo..hi, each clipped to it.
// With no seed outside, every point belongs to some inside seed, so the
// clipped cells tile the rectangle exactly.
function voronoiFit(lo is Vector, hi is Vector, cell is number, irregular is number, s is number) returns array
{
    const p0 = cell * PITCH_HEX;
    const W = hi - lo;
    const nx = max(1, round(W[0] / p0));
    const ny = max(1, round(W[1] / (p0 * sqrt(3) / 2)));
    const px = W[0] / nx;
    const h = W[1] / ny;
    const a = clamp(irregular, 0, 1) * JITTER_HEX * min(px, 2 * h / sqrt(3));
    var S = [];
    for (var j = 0; j < ny; j += 1)
    {
        const xs = hexRowX(j, nx);
        var row = [];
        for (var k = 0; k < size(xs); k += 1)
        {
            const d = jitterVec(k, j, a, s);
            const wall = xs[k] == 0 || xs[k] == nx;
            row = append(row, lo + vector(xs[k] * px + (wall ? 0 : d[0]), (j + 0.5) * h + d[1]));
        }
        S = append(S, row);
    }
    // Reach of a cell: the lattice triangle's circumradius (which grows as
    // rows squash flat) or corner-to-first-seed, plus both seeds' jitter.
    // Every row within 2 rc is searched: a neighbour missed here would leave
    // two cells overlapping, and the rib between them would vanish.
    const rc = max((h * h + px * px / 4) / (2 * h), sqrt(px * px + h * h) / 2) + 2 * a + 1e-6;
    const dj = ceil((2 * rc + 2 * a) / h) + 1;
    var out = [];
    for (var j = 0; j < ny; j += 1)
        for (var k = 0; k < size(S[j]); k += 1)
        {
            const sd = S[j][k];
            var nbrs = [];
            for (var jj = max(0, j - dj); jj <= min(ny - 1, j + dj); jj += 1)
                for (var kk = 0; kk < size(S[jj]); kk += 1)
                    if (!(jj == j && kk == k) && norm(S[jj][kk] - sd) < 2 * rc)
                        nbrs = append(nbrs, S[jj][kk]);
            const b0 = vector(max(lo[0], sd[0] - rc), max(lo[1], sd[1] - rc));
            const b1 = vector(min(hi[0], sd[0] + rc), min(hi[1], sd[1] + rc));
            const c = clipAll([b0, vector(b1[0], b0[1]), b1, vector(b0[0], b1[1])], sd, nbrs);
            if (size(c) >= 3)
                out = append(out, c);
        }
    return out;
}

function fitCells(shape is LeopardCellShape, lo is Vector, hi is Vector, cell is number, irregular is number, s is number) returns array
{
    if (shape == LeopardCellShape.TRI)
        return triFit(lo, hi, cell, irregular, s);
    if (shape == LeopardCellShape.HEX)
        return voronoiFit(lo, hi, cell, irregular, s);
    return quadFit(lo, hi, cell, irregular, s);
}


// ---------------------------------------------------------------- face outline

// Do two edges lie on the same circle? Either may be undefined: not an arc.
function sameCircle(p, q) returns boolean
{
    return p != undefined && q != undefined && norm(p.c - q.c) < 1e-6 && abs(p.r - q.r) < 1e-6;
}

// Chains sampled edges into closed loops, end to next start: each loop's
// points, worst chord error, the indices of its edges in order, and -- when
// its every edge lies on one circle, a round hole -- that circle.
function chainLoops(polys is array) returns array
{
    var used = [];
    for (var k = 0; k < size(polys); k += 1)
        used = append(used, false);
    var loops = [];
    for (var k = 0; k < size(polys); k += 1)
    {
        if (used[k])
            continue;
        used[k] = true;
        var chain = subArray(polys[k].pts, 0, size(polys[k].pts) - 1);
        var sag = polys[k].sag;
        var circle = polys[k].circle;
        var idx = [k];
        const start = polys[k].pts[0];
        var end = polys[k].pts[size(polys[k].pts) - 1];
        while (norm(end - start) > CHAIN_TOL)
        {
            var nxt = -1;
            for (var m = 0; m < size(polys); m += 1)
            {
                if (!used[m] && norm(polys[m].pts[0] - end) <= CHAIN_TOL)
                {
                    nxt = m;
                    break;
                }
            }
            if (nxt < 0)
                throw regenError("Could not follow the outline of a selected face.", ["faces"]);
            used[nxt] = true;
            idx = append(idx, nxt);
            chain = concatenateArrays([chain, subArray(polys[nxt].pts, 0, size(polys[nxt].pts) - 1)]);
            sag = max(sag, polys[nxt].sag);
            if (!sameCircle(circle, polys[nxt].circle))
                circle = undefined;
            end = polys[nxt].pts[size(polys[nxt].pts) - 1];
        }
        loops = append(loops, { "pts" : chain, "sag" : sag, "circle" : circle, "idx" : idx });
    }
    return loops;
}

function convexHull(pts is array) returns array
{
    const p = sort(pts, function(a, b) { return a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]; });
    if (size(p) <= 2)
        return p;
    var lower = [];
    for (var q in p)
    {
        while (size(lower) >= 2 && cross2(lower[size(lower) - 1] - lower[size(lower) - 2], q - lower[size(lower) - 1]) <= 0)
            lower = subArray(lower, 0, size(lower) - 1);
        lower = append(lower, q);
    }
    var upper = [];
    for (var k = size(p) - 1; k >= 0; k -= 1)
    {
        const q = p[k];
        while (size(upper) >= 2 && cross2(upper[size(upper) - 1] - upper[size(upper) - 2], q - upper[size(upper) - 1]) <= 0)
            upper = subArray(upper, 0, size(upper) - 1);
        upper = append(upper, q);
    }
    return concatenateArrays([subArray(lower, 0, size(lower) - 1), subArray(upper, 0, size(upper) - 1)]);
}

function gridKey(gx is number, gy is number) returns string
{
    return gx ~ "," ~ gy;
}

// The face outline as directed segments with the face on their left, filed in
// a grid so each cell only looks at segments near it. Inner loops also get a
// convex hull, for the tangent clip.
function buildRegion(polys is array, gs is number) returns map
{
    const loops = chainLoops(polys);
    var segs = [];
    var inners = [];
    var circles = [];
    var lo = vector(inf, inf);
    var hi = vector(-inf, -inf);
    for (var lp in loops)
    {
        const pts = lp.pts;
        for (var q in pts)
        {
            lo = vector(min(lo[0], q[0]), min(lo[1], q[1]));
            hi = vector(max(hi[0], q[0]), max(hi[1], q[1]));
        }
        var inner = -1;
        if (signedArea(pts) < 0)
        {
            const hull = convexHull(pts);
            const c = centroid2(hull);
            inners = append(inners, { "hull" : hull, "centre" : c, "sag" : lp.sag, "circle" : lp.circle,
                        "parts" : loopParts(pts, hull) });
            inner = size(inners) - 1;
            if (lp.circle != undefined)
                circles = append(circles, { "c" : lp.circle.c, "r" : lp.circle.r, "inner" : inner });
        }
        for (var k = 0; k < size(pts); k += 1)
            segs = append(segs, { "a" : pts[k], "b" : pts[(k + 1) % size(pts)], "sag" : lp.sag, "inner" : inner });
    }
    var grid = {};
    for (var idx = 0; idx < size(segs); idx += 1)
    {
        const a = segs[idx].a;
        const b = segs[idx].b;
        for (var gx = floor(min(a[0], b[0]) / gs); gx <= floor(max(a[0], b[0]) / gs); gx += 1)
            for (var gy = floor(min(a[1], b[1]) / gs); gy <= floor(max(a[1], b[1]) / gs); gy += 1)
            {
                const key = gridKey(gx, gy);
                grid[key] = append(grid[key] == undefined ? [] : grid[key], idx);
            }
    }
    return { "segs" : segs, "inners" : inners, "circles" : circles, "lo" : lo, "hi" : hi, "grid" : grid, "gs" : gs };
}

// A hole in the face that is not convex -- a curved slot, an L-shaped cutout --
// cannot be kept clear by one straight cut against its convex hull: the hull
// of a curved slot covers the whole region inside the curve, which then stays
// solid. Such a loop is split into triangles instead, and each hole is kept
// clear of each triangle near it, one straight cut apiece. The triangles cover
// the loop exactly, so clearing every one clears the loop. undefined for a
// convex loop (the hull is then exact) or when the split fails, which leaves
// the hull: conservative, as before.
function loopParts(lp is array, hull is array)
{
    const area = abs(signedArea(lp));
    if (abs(signedArea(hull)) - area <= 1e-6 * area)
        return undefined;
    const tris = triangulate(reverse(lp));
    if (size(tris) == 0)
        return undefined;
    var parts = [];
    for (var t in tris)
    {
        const c = centroid2(t);
        var rad = 0;
        for (var q in t)
            rad = max(rad, norm(q - c));
        parts = append(parts, { "pts" : t, "c" : c, "r" : rad });
    }
    return parts;
}

function pointInTriangle(p is Vector, a is Vector, b is Vector, c is Vector) returns boolean
{
    return cross2(b - a, p - a) >= 0 && cross2(c - b, p - b) >= 0 && cross2(a - c, p - c) >= 0;
}

// Ear clipping of a simple counter-clockwise polygon into counter-clockwise
// triangles. [] if it gets stuck, which only a degenerate polygon can do.
function triangulate(poly is array) returns array
{
    var pts = [];
    const n = size(poly);
    for (var k = 0; k < n; k += 1)
    {
        const a = poly[(k + n - 1) % n];
        const b = poly[k];
        const c = poly[(k + 1) % n];
        if (abs(cross2(b - a, c - b)) > 1e-12 * (dot(b - a, b - a) + dot(c - b, c - b)))
            pts = append(pts, b);
    }
    var idx = [];
    for (var k = 0; k < size(pts); k += 1)
        idx = append(idx, k);
    var tris = [];
    while (size(idx) > 3)
    {
        const m = size(idx);
        var cut = -1;
        for (var i = 0; i < m; i += 1)
        {
            const ia = idx[(i + m - 1) % m];
            const ib = idx[i];
            const ic = idx[(i + 1) % m];
            if (cross2(pts[ib] - pts[ia], pts[ic] - pts[ib]) <= 0)
                continue;
            var ear = true;
            for (var j in idx)
            {
                if (j != ia && j != ib && j != ic && pointInTriangle(pts[j], pts[ia], pts[ib], pts[ic]))
                {
                    ear = false;
                    break;
                }
            }
            if (ear)
            {
                cut = i;
                break;
            }
        }
        if (cut < 0)
            return [];
        tris = append(tris, [pts[idx[(cut + m - 1) % m]], pts[idx[cut]], pts[idx[(cut + 1) % m]]]);
        idx = concatenateArrays([subArray(idx, 0, cut), subArray(idx, cut + 1, m)]);
    }
    if (size(idx) == 3)
        tris = append(tris, [pts[idx[0]], pts[idx[1]], pts[idx[2]]]);
    return tris;
}

function nearSegments(region is map, c is Vector, reach is number) returns array
{
    var seen = {};
    var found = [];
    const gs = region.gs;
    for (var gx = floor((c[0] - reach) / gs); gx <= floor((c[0] + reach) / gs); gx += 1)
        for (var gy = floor((c[1] - reach) / gs); gy <= floor((c[1] + reach) / gs); gy += 1)
        {
            const bucket = region.grid[gridKey(gx, gy)];
            if (bucket == undefined)
                continue;
            for (var idx in bucket)
            {
                if (seen[idx] == true)
                    continue;
                seen[idx] = true;
                if (segDist(c, region.segs[idx].a, region.segs[idx].b) < reach)
                    found = append(found, idx);
            }
        }
    return sort(found, function(a, b) { return a - b; });
}

// Ray-cast parity along +x. Only the grid row the ray runs through can hold a
// segment that crosses it.
function insideRegion(region is map, p is Vector) returns boolean
{
    const gs = region.gs;
    const gy = floor(p[1] / gs);
    var seen = {};
    var crossings = 0;
    for (var gx = floor(p[0] / gs); gx <= floor(region.hi[0] / gs); gx += 1)
    {
        const bucket = region.grid[gridKey(gx, gy)];
        if (bucket == undefined)
            continue;
        for (var idx in bucket)
        {
            if (seen[idx] == true)
                continue;
            seen[idx] = true;
            const a = region.segs[idx].a;
            const b = region.segs[idx].b;
            if ((a[1] > p[1]) != (b[1] > p[1]))
            {
                const x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]);
                if (x > p[0])
                    crossings += 1;
            }
        }
    }
    return crossings % 2 == 1;
}


// ---------------------------------------------------------------- holes

function nearestOnLoop(pts is array, c is Vector) returns Vector
{
    if (size(pts) == 1)
        return pts[0];
    var bestD = inf;
    var best = pts[0];
    for (var k = 0; k < size(pts); k += 1)
    {
        const a = pts[k];
        const ab = pts[(k + 1) % size(pts)] - a;
        const l2 = dot(ab, ab);
        const t = l2 == 0 ? 0 : clamp(dot(c - a, ab) / l2, 0, 1);
        const p = a + ab * t;
        if (norm(c - p) < bestD)
        {
            bestD = norm(c - p);
            best = p;
        }
    }
    return best;
}

// Keeps a core clear of an inner loop (a screw hole, a slot) by clearance,
// with one straight cut. Any half-plane x . u >= support(u) + clearance misses
// the loop's convex hull grown by the clearance, so every candidate direction
// u is safe; the one kept is whichever leaves the most core. The candidates
// are the way out from the nearest point of the hull -- exact for a round
// hole -- and each hull edge's outward normal, exact alongside a straight
// side such as a slot's.
function innerClip(core is array, c is Vector, hull is array, clearance is number) returns array
{
    const n = size(hull);
    var cands = [];
    var inside = n >= 3;
    for (var k = 0; k < n; k += 1)
        if (cross2(hull[(k + 1) % n] - hull[k], c - hull[k]) < 0)
            inside = false;
    if (!inside)
    {
        const q = nearestOnLoop(hull, c);
        if (norm(c - q) > 1e-9)
            cands = append(cands, normalize(c - q));
    }
    if (n >= 3)
    {
        for (var k = 0; k < n; k += 1)
        {
            const e = hull[(k + 1) % n] - hull[k];
            if (norm(e) > 1e-9)
            {
                const t = normalize(e);
                cands = append(cands, vector(t[1], -t[0]));
            }
        }
    }
    var best = [];
    var bestArea = 0;
    for (var u in cands)
    {
        var support = -inf;
        for (var q in hull)
            support = max(support, dot(q, u));
        const kept = clipHalf(core, u * (support + clearance), u * -1);
        const area = size(kept) >= 3 ? abs(signedArea(kept)) : 0;
        if (area > bestArea)
        {
            best = kept;
            bestArea = area;
        }
    }
    return best;
}

// Clips a core to the face with straight cuts: the border along the outline,
// and one cut per inner loop (one per triangle of a non-convex one), kept
// innerD clear of it.
function regionClip(coreIn is array, c is Vector, region is map, reach is number, border is number, r is number, innerD is number) returns array
{
    var core = coreIn;
    const near = nearSegments(region, c, reach);
    const inside = insideRegion(region, c);
    if (size(near) == 0)
        return inside ? core : [];
    var seenInner = {};
    for (var idx in near)
    {
        const seg = region.segs[idx];
        if (seg.inner < 0)
        {
            // With the centre inside the face, only segments facing it
            // count: one whose inside lies away from the centre is behind
            // a nearer boundary, which does the clipping -- and applying
            // it as well would empty any cell straddling a notch.
            if (inside && cross2(seg.b - seg.a, c - seg.a) <= 0)
                continue;
            core = clipLeftOf(core, seg.a, seg.b, border + r + seg.sag);
        }
        else if (seenInner[seg.inner] != true)
        {
            seenInner[seg.inner] = true;
            const innerLoop = region.inners[seg.inner];
            if (innerLoop.parts == undefined)
                core = innerClip(core, c, innerLoop.hull, innerD + r + innerLoop.sag);
            else
                core = partsClip(core, c, innerLoop.parts, reach, innerD + r + innerLoop.sag);
        }
        if (size(core) < 3)
            return [];
    }
    return core;
}


// Keeps a core clear of every triangle of a non-convex inner loop that comes
// within clearance of it, nearest first, one straight cut each. Neighbouring
// triangles share corners, so after one cut the next is often exactly at the
// clearance: the 1e-9 settles that tie the safe way, the same way in any
// arithmetic.
function partsClip(coreIn is array, c is Vector, parts is array, reach is number, clearance is number) returns array
{
    var core = coreIn;
    var near = [];
    for (var k = 0; k < size(parts); k += 1)
        if (norm(parts[k].c - c) < reach + parts[k].r + clearance)
            near = append(near, { "d" : polyPointDist(parts[k].pts, c), "k" : k });
    near = sort(near, function(a, b) { return a.d != b.d ? a.d - b.d : a.k - b.k; });
    for (var e in near)
    {
        const t = parts[e.k].pts;
        if (polyDist(core, t) < clearance + 1e-9)
        {
            core = innerClip(core, c, t, clearance);
            if (size(core) < 3)
                return [];
        }
    }
    return core;
}

function segSegDist(a is Vector, b is Vector, c is Vector, d is Vector) returns number
{
    const d1 = cross2(b - a, c - a);
    const d2 = cross2(b - a, d - a);
    const d3 = cross2(d - c, a - c);
    const d4 = cross2(d - c, b - c);
    if (((d1 > 0) != (d2 > 0)) && ((d3 > 0) != (d4 > 0)) && d1 != 0 && d2 != 0 && d3 != 0 && d4 != 0)
        return 0;
    return min(min(segDist(a, c, d), segDist(b, c, d)), min(segDist(c, a, b), segDist(d, a, b)));
}

// Distance between two convex counter-clockwise polygons; 0 if they overlap.
function polyDist(A is array, B is array) returns number
{
    if (pointInConvex(A, B[0]) || pointInConvex(B, A[0]))
        return 0;
    var best = inf;
    for (var i = 0; i < size(A); i += 1)
        for (var j = 0; j < size(B); j += 1)
            best = min(best, segSegDist(A[i], A[(i + 1) % size(A)], B[j], B[(j + 1) % size(B)]));
    return best;
}


// ---------------------------------------------------------------- exact bands
//
// With bands on, the material kept round the face's edges is an exact offset
// of them: everything within the border of the outline, and within the band
// width of every hole already in the face -- round, slotted, curved or square.
// Its edge is lines parallel to straight edges, arcs concentric with round
// ones, and arcs round every inside corner. A hole is its cell's core with
// that taken out, so where a hole meets the band it follows it exactly, and
// the ribs between holes run on into the band as they meet it.
//
// In core terms (the hole shrunk by r): E = everything inside the face at
// least D = clearance + r from every edge; a core's holes are core n E, grown
// by r. core n E is worked out cell by cell as an arrangement: every offset
// curve near the core and every core edge, split where they cross, keeping the
// pieces that lie on the boundary of core n E, joined end to end into loops.

function pointInConvex(poly is array, p is Vector) returns boolean
{
    const n = size(poly);
    if (n < 3)
        return false;
    for (var k = 0; k < n; k += 1)
        if (cross2(poly[(k + 1) % n] - poly[k], p - poly[k]) <= 0)
            return false;
    return true;
}

// Distance from a point to a convex polygon; 0 inside it.
function polyPointDist(poly is array, p is Vector) returns number
{
    return pointInConvex(poly, p) ? 0 : norm(p - nearestOnLoop(poly, p));
}

function rot90(u is Vector) returns Vector
{
    return vector(-u[1], u[0]);
}

// Angle turned going from direction u0 to u1 in direction d (1 counter-
// clockwise, -1 clockwise), in [0, 2 pi).
function angDir(u0 is Vector, u1 is Vector, d is number) returns number
{
    const a = atan2(cross2(u0, u1), dot(u0, u1)) / radian;
    if (d > 0)
        return a >= 0 ? a : a + 2 * PI;
    return a <= 0 ? -a : 2 * PI - a;
}

// A piece is a line { kind L, a, b } or an arc { kind A, c, rho, a, b, dir,
// sweep } from a to b about c: counter-clockwise for dir 1, clockwise for -1,
// through sweep radians (up to 2 pi, a whole circle).

function linePiece(a is Vector, b is Vector) returns map
{
    return { "kind" : "L", "a" : a, "b" : b };
}

function arcPiece(c is Vector, rho is number, a is Vector, b is Vector, d is number, sweep is number) returns map
{
    return { "kind" : "A", "c" : c, "rho" : rho, "a" : a, "b" : b, "dir" : d, "sweep" : sweep };
}

function pieceAt(p is map, t is number) returns Vector
{
    if (p.kind == "L")
        return p.a + (p.b - p.a) * t;
    const u = p.a - p.c;
    const th = p.dir * p.sweep * t;
    const ct = cos(th * radian);
    const st = sin(th * radian);
    return p.c + vector(u[0] * ct - u[1] * st, u[0] * st + u[1] * ct);
}

function pieceLen(p is map) returns number
{
    return p.kind == "L" ? norm(p.b - p.a) : p.rho * p.sweep;
}

// Where X, on p's circle, falls along arc p, as a fraction -- or undefined.
function arcParam(p is map, X is Vector)
{
    const phi = angDir(normalize(p.a - p.c), normalize(X - p.c), p.dir);
    const tol = TAU / max(p.rho, TAU);
    if (phi <= p.sweep + tol)
        return min(phi, p.sweep) / p.sweep;
    if (phi >= 2 * PI - tol)
        return 0;
    return undefined;
}

function tangentAt(p is map, X is Vector) returns Vector
{
    if (p.kind == "L")
        return normalize(p.b - p.a);
    return rot90(normalize(X - p.c)) * p.dir;
}

// The normal to the right of the direction of travel: outward, on a loop
// that keeps its inside on the left.
function normalAt(p is map, X is Vector) returns Vector
{
    if (p.kind == "L")
    {
        const t = normalize(p.b - p.a);
        return vector(t[1], -t[0]);
    }
    return normalize(X - p.c) * p.dir;
}

// [x0, y0, x1, y1] round a piece.
function pieceBox(p is map) returns array
{
    var pts = [p.a, p.b];
    if (p.kind == "A")
        for (var u in [vector(1, 0), vector(0, 1), vector(-1, 0), vector(0, -1)])
            if (angDir(normalize(p.a - p.c), u, p.dir) <= p.sweep)
                pts = append(pts, p.c + u * p.rho);
    var bb = [inf, inf, -inf, -inf];
    for (var q in pts)
        bb = [min(bb[0], q[0]), min(bb[1], q[1]), max(bb[2], q[0]), max(bb[3], q[1])];
    return bb;
}

function pieceDist(p is map, x is Vector) returns number
{
    if (p.kind == "L")
        return segDist(x, p.a, p.b);
    const v = x - p.c;
    const len = norm(v);
    if (len > 1e-12 && angDir(normalize(p.a - p.c), v * (1 / len), p.dir) <= p.sweep)
        return abs(len - p.rho);
    return min(norm(x - p.a), norm(x - p.b));
}

function subPiece(p is map, t0 is number, t1 is number, X0 is Vector, X1 is Vector) returns map
{
    if (p.kind == "L")
        return linePiece(X0, X1);
    return arcPiece(p.c, p.rho, X0, X1, p.dir, p.sweep * (t1 - t0));
}

function clamp01(t is number) returns number
{
    return min(1, max(0, t));
}

// Where two pieces meet: [{ t on p, u on q, x }], ends included. Two pieces
// on one line or one circle meet where they overlap, at its two ends.

function isectLL(p is map, q is map) returns array
{
    const a = p.a;
    const d1 = p.b - p.a;
    const c = q.a;
    const d2 = q.b - q.a;
    const l1 = norm(d1);
    const l2 = norm(d2);
    if (l1 <= TAU || l2 <= TAU)
        return [];
    const den = cross2(d1, d2);
    if (abs(den) <= 1e-12 * l1 * l2)
    {
        if (abs(cross2(d1, c - a)) / l1 > TAU)
            return [];
        var out = [];
        for (var e in [{ "x" : q.a, "u" : 0 }, { "x" : q.b, "u" : 1 }])
        {
            const t = dot(e.x - a, d1) / (l1 * l1);
            if (t >= -PEPS && t <= 1 + PEPS)
                out = append(out, { "t" : clamp01(t), "u" : e.u, "x" : e.x });
        }
        for (var e in [{ "x" : p.a, "t" : 0 }, { "x" : p.b, "t" : 1 }])
        {
            const u = dot(e.x - c, d2) / (l2 * l2);
            if (u >= -PEPS && u <= 1 + PEPS)
                out = append(out, { "t" : e.t, "u" : clamp01(u), "x" : e.x });
        }
        return out;
    }
    const t = cross2(c - a, d2) / den;
    const u = cross2(c - a, d1) / den;
    if (t >= -PEPS && t <= 1 + PEPS && u >= -PEPS && u <= 1 + PEPS)
    {
        const tc = clamp01(t);
        return [{ "t" : tc, "u" : clamp01(u), "x" : a + d1 * tc }];
    }
    return [];
}

// A line and an arc. One that comes within TAU of just touching the circle
// is taken not to meet it at all: a touch splits nothing, and a crossing that
// shallow is lost in rounding -- worked out either way, it leaves slivers of
// piece a fraction of a micrometre long, on one side of the tangent point or
// the other.
function isectLA(p is map, q is map) returns array
{
    const a = p.a;
    const d = p.b - p.a;
    const dd = dot(d, d);
    if (dd <= TAU * TAU)
        return [];
    const len = sqrt(dd);
    const f = q.c - a;
    const h = abs(cross2(d, f)) / len;
    if (h >= q.rho - TAU)
        return [];
    const t0 = dot(f, d) / dd;
    const w = sqrt(q.rho * q.rho - h * h) / len;
    var out = [];
    for (var root in [t0 - w, t0 + w])
    {
        if (root >= -PEPS && root <= 1 + PEPS)
        {
            const t = clamp01(root);
            const X = a + d * t;
            const u = arcParam(q, X);
            if (u != undefined)
                out = append(out, { "t" : t, "u" : u, "x" : X });
        }
    }
    return out;
}

function isectAA(p is map, q is map) returns array
{
    const v = q.c - p.c;
    const d = norm(v);
    const r1 = p.rho;
    const r2 = q.rho;
    var out = [];
    if (d <= TAU)
    {
        if (abs(r1 - r2) > TAU)
            return [];
        for (var e in [{ "x" : q.a, "u" : 0 }, { "x" : q.b, "u" : 1 }])
        {
            const t = arcParam(p, e.x);
            if (t != undefined)
                out = append(out, { "t" : t, "u" : e.u, "x" : e.x });
        }
        for (var e in [{ "x" : p.a, "t" : 0 }, { "x" : p.b, "t" : 1 }])
        {
            const u = arcParam(q, e.x);
            if (u != undefined)
                out = append(out, { "t" : e.t, "u" : u, "x" : e.x });
        }
        return out;
    }
    if (d >= r1 + r2 - TAU || d <= abs(r1 - r2) + TAU)
        return [];                      // apart, one inside the other, or touching: as for a line
    const al = (r1 * r1 - r2 * r2 + d * d) / (2 * d);
    const h = sqrt(max(0, r1 * r1 - al * al));
    const P = p.c + v * (al / d);
    const w = rot90(v) * (1 / d);
    const pts = [P + w * h, P - w * h];
    for (var X in pts)
    {
        const t = arcParam(p, X);
        const u = arcParam(q, X);
        if (t != undefined && u != undefined)
            out = append(out, { "t" : t, "u" : u, "x" : X });
    }
    return out;
}

function isect(p is map, q is map) returns array
{
    if (p.kind == "L")
        return q.kind == "L" ? isectLL(p, q) : isectLA(p, q);
    if (q.kind == "L")
    {
        var out = [];
        for (var e in isectLA(q, p))
            out = append(out, { "t" : e.u, "u" : e.t, "x" : e.x });
        return out;
    }
    return isectAA(p, q);
}


// ---------------------------------------------------------------- the face's edges, offset

// The exact pieces of one sampled edge: one arc for an edge on a circle, one
// line for a straight edge, a line per chord for anything else.
function edgePieces(poly is map) returns array
{
    const pts = poly.pts;
    if (poly.circle != undefined)
    {
        const c = poly.circle.c;
        const a = pts[0];
        const b = pts[size(pts) - 1];
        const d = cross2(pts[0] - c, pts[1] - c) > 0 ? 1 : -1;
        var sw = angDir(normalize(a - c), normalize(b - c), d);
        if (sw <= 1e-9)
            sw = 2 * PI;
        return [arcPiece(c, poly.circle.r, a, b, d, sw)];
    }
    var out = [];
    for (var k = 0; k < size(pts) - 1; k += 1)
        out = append(out, linePiece(pts[k], pts[k + 1]));
    return out;
}

// Each loop of the face: its pieces (face on their left), and its clearance
// -- outerD for the outline, innerD for a hole, plus the chord allowance
// where the loop has a sampled curve.
function faceLoops(polys is array, outerD is number, innerD is number) returns array
{
    var out = [];
    for (var lp in chainLoops(polys))
    {
        var pieces = [];
        var csag = 0;
        for (var k in lp.idx)
        {
            pieces = concatenateArrays([pieces, edgePieces(polys[k])]);
            if (polys[k].circle == undefined && size(polys[k].pts) > 2)
                csag = max(csag, polys[k].sag);
        }
        out = append(out, { "pieces" : pieces, "D" : (signedArea(lp.pts) > 0 ? outerD : innerD) + csag });
    }
    return out;
}

// The raw offset of one loop: each piece moved its clearance (+ extra) to its
// left, and an arc of that radius round each inside corner -- which includes
// every joint where a sampled curve bends away from the face, so the offset
// of a sampled curve is exact for its chords, a chain of lines and short arcs
// that meet smoothly. At an outside corner neighbours cross; the arrangement
// trims them.
function offsetLoop(lp is map, extra is number) returns array
{
    const D = lp.D + extra;
    const P = lp.pieces;
    const n = size(P);
    var out = [];
    for (var p in P)
    {
        if (p.kind == "L")
        {
            const nv = rot90(normalize(p.b - p.a));
            out = append(out, linePiece(p.a + nv * D, p.b + nv * D));
        }
        else
        {
            const rho = p.rho - p.dir * D;
            if (rho <= 1e-6)
                continue;           // a convex arc tighter than D: its neighbours meet instead
            const na = normalize(p.a - p.c) * -p.dir;
            const nb = normalize(p.b - p.c) * -p.dir;
            out = append(out, arcPiece(p.c, rho, p.a + na * D, p.b + nb * D, p.dir, p.sweep));
        }
    }
    for (var i = 0; i < n; i += 1)
    {
        const p = P[i];
        const q = P[(i + 1) % n];
        const tIn = tangentAt(p, p.b);
        const tOut = tangentAt(q, q.a);
        const s = cross2(tIn, tOut);
        if (s < -SMOOTH || (abs(s) <= SMOOTH && dot(tIn, tOut) < 0))
        {
            const v = p.b;
            const nIn = rot90(tIn);
            const nOut = rot90(tOut);
            out = append(out, arcPiece(v, D, v + nIn * D, v + nOut * D, -1, angDir(nIn, nOut, -1)));
        }
    }
    for (var i = 0; i < size(out); i += 1)
        out[i].bbox = pieceBox(out[i]);
    return out;
}

// Each box's index, filed under every grid square the box touches. Built in
// one place, so the map is never handed to a function to be added to -- in
// FeatureScript that could copy all of it each time.
function gridOf(boxes is array, gs is number) returns map
{
    var grid = {};
    for (var idx = 0; idx < size(boxes); idx += 1)
    {
        const bb = boxes[idx];
        for (var gx = floor(bb[0] / gs); gx <= floor(bb[2] / gs); gx += 1)
            for (var gy = floor(bb[1] / gs); gy <= floor(bb[3] / gs); gy += 1)
            {
                const key = gridKey(gx, gy);
                grid[key] = append(grid[key] == undefined ? [] : grid[key], idx);
            }
    }
    return grid;
}

function gridFind(grid is map, gs is number, bb is array) returns array
{
    var seen = {};
    var found = [];
    for (var gx = floor(bb[0] / gs); gx <= floor(bb[2] / gs); gx += 1)
        for (var gy = floor(bb[1] / gs); gy <= floor(bb[3] / gs); gy += 1)
        {
            const bucket = grid[gridKey(gx, gy)];
            if (bucket == undefined)
                continue;
            for (var i in bucket)
            {
                if (seen[i] == true)
                    continue;
                seen[i] = true;
                found = append(found, i);
            }
        }
    return sort(found, function(a, b) { return a - b; });
}

// Everything about one face that the bands need: its edges as exact pieces
// with their clearances, and the raw offsets at D and at D + k (for the
// smallest-hole test), each filed in a grid.
function bandContext(polys is array, region is map, outerD is number, innerD is number, k is number) returns map
{
    const loops = faceLoops(polys, outerD, innerD);
    var feats = [];
    var fboxes = [];
    for (var lp in loops)
        for (var p in lp.pieces)
        {
            var f = p;
            f.D = lp.D;
            const b = pieceBox(p);
            const g = lp.D + k;
            f.bbox = [b[0] - g, b[1] - g, b[2] + g, b[3] + g];
            feats = append(feats, f);
            fboxes = append(fboxes, f.bbox);
        }
    var raws = [];
    var rgrids = [];
    for (var e in [0, k])
    {
        var rs = [];
        for (var lp in loops)
            rs = concatenateArrays([rs, offsetLoop(lp, e)]);
        var rboxes = [];
        for (var p in rs)
            rboxes = append(rboxes, p.bbox);
        raws = append(raws, rs);
        rgrids = append(rgrids, gridOf(rboxes, region.gs));
    }
    return { "region" : region, "feats" : feats, "fgrid" : gridOf(fboxes, region.gs), "raws" : raws,
             "rgrids" : rgrids, "k" : k };
}

function inBox(b is array, x is Vector) returns boolean
{
    return b[0] <= x[0] && x[0] <= b[2] && b[1] <= x[1] && x[1] <= b[3];
}

function boxesMeet(a is array, b is array) returns boolean
{
    return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
}

// Is x in E: inside the face, and at least its clearance from every edge?
function bandValid(ctx is map, x is Vector, extra is number) returns boolean
{
    const gs = ctx.region.gs;
    const bucket = ctx.fgrid[gridKey(floor(x[0] / gs), floor(x[1] / gs))];
    if (bucket != undefined)
    {
        for (var i in bucket)
        {
            const f = ctx.feats[i];
            if (inBox(f.bbox, x) && pieceDist(f, x) < f.D + extra - TAU)
                return false;
        }
    }
    return insideRegion(ctx.region, x);
}

function strictlyInside(core is array, x is Vector) returns boolean
{
    const n = size(core);
    for (var k = 0; k < n; k += 1)
    {
        const e = core[(k + 1) % n] - core[k];
        if (cross2(e, x - core[k]) <= TAU * norm(e))
            return false;
    }
    return true;
}

function loopArea(lp is array) returns number
{
    var s = 0;
    for (var p in lp)
    {
        s += cross2(p.a, p.b) / 2;
        if (p.kind == "A")
        {
            const sg = p.dir * p.sweep;
            s += p.rho * p.rho / 2 * (sg - sin(sg * radian));
        }
    }
    return s;
}

// core n E: status "plain" when all of the core is in E, "empty" when none
// is, "fail" when it cannot be worked out cleanly, or "ok" with comps,
// counter-clockwise loops of pieces, and holes, clockwise loops of anything
// inside them.
function bandClip(core is array, ctx is map, extra is number) returns map
{
    const n = size(core);
    var bb = [inf, inf, -inf, -inf];
    for (var q in core)
        bb = [min(bb[0], q[0]), min(bb[1], q[1]), max(bb[2], q[0]), max(bb[3], q[1])];
    bb = [bb[0] - TAU, bb[1] - TAU, bb[2] + TAU, bb[3] + TAU];
    const lv = extra == 0 ? 0 : 1;
    const raws = ctx.raws[lv];
    var allp = [];
    for (var k = 0; k < n; k += 1)
        allp = append(allp, linePiece(core[k], core[(k + 1) % n]));
    for (var i in gridFind(ctx.rgrids[lv], ctx.region.gs, bb))
        if (boxesMeet(raws[i].bbox, bb))
            allp = append(allp, raws[i]);
    const m = size(allp);
    if (m == n)
        return { "status" : bandValid(ctx, centroid2(core), extra) ? "plain" : "empty" };
    var ev = [];
    for (var i = 0; i < m; i += 1)
        ev = append(ev, []);
    for (var i = 0; i < m; i += 1)
        for (var j = max(i + 1, n); j < m; j += 1)
            for (var e in isect(allp[i], allp[j]))
            {
                ev[i] = append(ev[i], { "t" : e.t, "x" : e.x });
                ev[j] = append(ev[j], { "t" : e.u, "x" : e.x });
            }
    var kept = [];
    for (var i = 0; i < m; i += 1)
    {
        const p = allp[i];
        const evs = sort(concatenateArrays([[{ "t" : 0, "x" : p.a }], ev[i], [{ "t" : 1, "x" : p.b }]]),
                         function(a, b) { return a.t - b.t; });
        const len = pieceLen(p);
        for (var k = 0; k < size(evs) - 1; k += 1)
        {
            const t0 = evs[k].t;
            const t1 = evs[k + 1].t;
            if ((t1 - t0) * len <= TAU)
                continue;
            const mid = pieceAt(p, (t0 + t1) / 2);
            if (i >= n && !strictlyInside(core, mid))
                continue;
            if (bandValid(ctx, mid, extra))
                kept = append(kept, subPiece(p, t0, t1, evs[k].x, evs[k + 1].x));
        }
    }
    const mk = size(kept);
    if (mk == 0)
        return { "status" : "empty" };
    // Each piece must lead on to exactly one other, and each be led to once.
    var nxt = [];
    var hits = [];
    for (var i = 0; i < mk; i += 1)
        hits = append(hits, 0);
    for (var i = 0; i < mk; i += 1)
    {
        var cand = -1;
        var count = 0;
        for (var j = 0; j < mk; j += 1)
        {
            if (norm(kept[j].a - kept[i].b) <= LINK)
            {
                cand = j;
                count += 1;
            }
        }
        if (count != 1)
            return { "status" : "fail" };
        nxt = append(nxt, cand);
        hits[cand] += 1;
    }
    for (var h in hits)
        if (h != 1)
            return { "status" : "fail" };
    var seen = [];
    for (var i = 0; i < mk; i += 1)
        seen = append(seen, false);
    var comps = [];
    var holes = [];
    for (var i = 0; i < mk; i += 1)
    {
        if (seen[i])
            continue;
        var lp = [];
        var j = i;
        while (!seen[j])
        {
            seen[j] = true;
            lp = append(lp, kept[j]);
            j = nxt[j];
        }
        if (j != i)
            return { "status" : "fail" };
        const nl = size(lp);
        for (var k = 0; k < nl; k += 1)         // one point at each junction
            lp[(k + 1) % nl].a = lp[k].b;
        if (loopArea(lp) > 0)
            comps = append(comps, lp);
        else
            holes = append(holes, lp);
    }
    return { "status" : "ok", "comps" : comps, "holes" : holes };
}


// ---------------------------------------------------------------- loops

function loopPerimeter(lp is array) returns number
{
    var s = 0;
    for (var p in lp)
        s += pieceLen(p);
    return s;
}

// Arcs over 0.9 of half a turn are drawn as two, so no arc's ends meet.
function splitBigArcs(lp is array) returns array
{
    var out = [];
    for (var p in lp)
    {
        if (p.kind == "A" && p.sweep > 0.9 * PI)
        {
            const m = pieceAt(p, 0.5);
            out = append(out, arcPiece(p.c, p.rho, p.a, m, p.dir, p.sweep / 2));
            out = append(out, arcPiece(p.c, p.rho, m, p.b, p.dir, p.sweep / 2));
        }
        else
            out = append(out, p);
    }
    return out;
}

function smoothJoin(n1 is Vector, n2 is Vector) returns boolean
{
    return abs(cross2(n1, n2)) <= SMOOTH && dot(n1, n2) > 0;
}

// Every piece long enough to draw; every corner turning enough to round, or
// not at all where two pieces meet tangentially.
function loopOk(lp is array) returns boolean
{
    const n = size(lp);
    for (var k = 0; k < n; k += 1)
    {
        const p = lp[k];
        if (pieceLen(p) < TINY_EDGE)
            return false;
        const q = lp[(k + 1) % n];
        const n1 = normalAt(p, p.b);
        const n2 = normalAt(q, q.a);
        if (smoothJoin(n1, n2))
            continue;
        if (cross2(n1, n2) < ((p.kind == "L" && q.kind == "L") ? TINY_TURN : MIN_TURN))
            return false;
    }
    return true;
}

// Is x in the circular segment between arc p (under half a turn) and its chord?
function arcSegmentHolds(p is map, x is Vector) returns boolean
{
    if (norm(x - p.c) >= p.rho)
        return false;
    const side = cross2(p.b - p.a, x - p.a);
    return p.dir > 0 ? side < 0 : side > 0;
}

function winding(lp is array, x is Vector) returns number
{
    var w = 0;
    for (var p in lp)
    {
        const u = p.a - x;
        const v = p.b - x;
        w += atan2(cross2(u, v), dot(u, v)) / radian;
        if (p.kind == "A" && arcSegmentHolds(p, x))
            w += 2 * PI * p.dir;
    }
    return round(w / (2 * PI));
}

// How close two pieces come: their ends against each other, and for an arc
// its point that faces the other piece square on.
function piecePieceDist(p is map, q is map) returns number
{
    var best = min(min(pieceDist(q, p.a), pieceDist(q, p.b)), min(pieceDist(p, q.a), pieceDist(p, q.b)));
    for (var st in [[p, q], [q, p]])
    {
        const s = st[0];
        const t = st[1];
        if (s.kind != "A")
            continue;
        var dirs = [];
        if (t.kind == "L")
        {
            const nv = rot90(normalize(t.b - t.a));
            dirs = [nv, nv * -1];
        }
        else
        {
            const w = t.c - s.c;
            if (norm(w) > TAU)
                dirs = [normalize(w), normalize(w) * -1];
        }
        for (var u in dirs)
        {
            const Y = s.c + u * s.rho;
            if (arcParam(s, Y) != undefined)
                best = min(best, pieceDist(t, Y));
        }
    }
    return best;
}

function loopPoints(lp is array) returns array
{
    var out = [];
    for (var p in lp)
    {
        const k = p.kind == "L" ? 8 : max(8, ceil(p.sweep * 16));
        for (var j = 0; j < k; j += 1)
            out = append(out, pieceAt(p, j / k));
    }
    return out;
}

// Points along one piece, both ends included.
function piecePoints(p is map) returns array
{
    const k = p.kind == "L" ? 8 : max(8, ceil(p.sweep * 16));
    var out = [];
    for (var j = 0; j <= k; j += 1)
        out = append(out, pieceAt(p, j / k));
    return out;
}

// Where a loop comes back within 2d of itself across the plate -- a hole
// wrapped round a boss whose band only just reaches past the core's edge. The
// web joining the boss to the rest would be thinner than a rib, or shut off
// altogether once the hole is grown by the corner radius. Returns { s, t },
// the two nearest points across the narrowest such neck, or undefined. Only a
// gap with nothing else of the loop nearer its middle than its ends counts:
// the ends of a short arc round a band are close too, but the arc runs
// between them; and so do the sides of a sharp corner, but across the hole.
function neck(lp is array, d is number)
{
    const n = size(lp);
    var best = undefined;
    for (var i = 0; i < n; i += 1)
        for (var j = i + 2; j < n; j += 1)
        {
            if ((i == 0 && j == n - 1) || piecePieceDist(lp[i], lp[j]) >= 2 * d - TAU)
                continue;
            var g = inf;
            var s = undefined;
            var t = undefined;
            for (var x in piecePoints(lp[i]))
                for (var y in piecePoints(lp[j]))
                {
                    const gap = norm(x - y);
                    if (gap < g - 1e-12)        // first of a tie, in any arithmetic
                    {
                        g = gap;
                        s = x;
                        t = y;
                    }
                }
            const m = (s + t) * 0.5;
            if (winding(lp, m) != 0)
                continue;
            var between = false;
            for (var k = 0; k < n; k += 1)
                if (k != i && k != j && pieceDist(lp[k], m) < g / 2 - 1e-9 * (1 + g))
                    between = true;
            if (between)
                continue;
            if (best == undefined || g < best.g)
                best = { "g" : g, "s" : s, "t" : t };
        }
    return best;
}


// ---------------------------------------------------------------- holes from bands

// The fallback, for the rare core the arrangement cannot settle cleanly: the
// old straight cuts, convex and always drawable, kept the band width off
// every hole -- conservative, so never less material.
function straightCore(core is array, ctx is map, r is number, border is number, ring is number, keepR is number) returns array
{
    const c = centroid2(core);
    var cr = 0;
    for (var q in core)
        cr = max(cr, norm(q - c));
    const reach = cr + max(border, ring) + r + SAG + 1e-6;
    var k = regionClip(core, c, ctx.region, reach, border, r, ring);
    k = size(k) > 0 ? tidy(ccw(k)) : [];
    if (size(k) == 0 || (keepR > r && size(insetConvex(k, keepR - r)) == 0))
        return [];
    return [{ "core" : k, "cut" : true }];
}

// A core whose bands cannot be drawn cleanly -- a piece too short to sketch,
// a corner too shallow to round, ends that do not meet -- is tried once more
// shrunk by NUDGE, which moves every crossing; then it gets the straight
// cuts. Either way the hole only gets smaller.
function retryCore(core is array, ctx is map, rib is number, r is number, border is number, ring is number, keepR is number, depth is number, nudged is boolean) returns array
{
    if (!nudged)
    {
        const k = insetConvex(core, NUDGE);
        if (size(k) > 0)
            return bandHoles(k, ctx, rib, r, border, ring, keepR, depth, true);
    }
    return straightCore(core, ctx, r, border, ring, keepR);
}

// The holes one convex core makes against the bands: [{ core }] where
// nothing touches it, or [{ loop }, ...].
function bandHoles(coreIn is array, ctx is map, rib is number, r is number, border is number, ring is number, keepR is number, depth is number, nudged is boolean) returns array
{
    const core = tidy(ccw(coreIn));
    if (size(core) == 0)
        return [];
    const k = ctx.k;
    const res = bandClip(core, ctx, 0);
    if (res.status == "empty")
        return [];
    if (res.status == "plain")
        return (k <= 0 || size(insetConvex(core, k)) > 0) ? [{ "core" : core }] : [];
    if (res.status == "fail")
        return retryCore(core, ctx, rib, r, border, ring, keepR, depth, nudged);
    const d = rib / 2 + r;
    if (size(res.holes) > 0)
    {
        // A hole wrapped round something -- a bolt hole and its band -- would
        // leave it loose: split the core by a rib through it instead.
        if (depth >= 2)
            return straightCore(core, ctx, r, border, ring, keepR);
        const h0 = res.holes[0];
        var pts = [];
        for (var p in h0)
            pts = append(pts, p.a);
        const X = (size(pts) > 2 || h0[0].kind != "A") ? centroid2(pts) : h0[0].c;
        var angles = [];
        for (var j = 0; j < 6; j += 1)
            angles = append(angles, (30 * j) * (PI / 180));
        return bestSplit(core, X, angles, ctx, rib, r, border, ring, keepR, depth);
    }
    const comps0 = res.comps;
    for (var i = 0; i < size(comps0); i += 1)
        for (var j = i + 1; j < size(comps0); j += 1)
        {
            var dmin = inf;
            for (var p in comps0[i])
                for (var q in comps0[j])
                    dmin = min(dmin, piecePieceDist(p, q));
            if (dmin < 2 * d - TAU)
            {
                // Two pieces of one cell closer than a rib: split between them.
                if (depth >= 2)
                    return straightCore(core, ctx, r, border, ring, keepR);
                const pa = loopPoints(comps0[i]);
                const pb = loopPoints(comps0[j]);
                var best = inf;
                var x = pa[0];
                var y = pb[0];
                for (var s in pa)
                    for (var t in pb)
                        if (norm(s - t) < best)
                        {
                            best = norm(s - t);
                            x = s;
                            y = t;
                        }
                const u = norm(y - x) > TAU ? normalize(y - x) : vector(1, 0);
                return bestSplit(core, (x + y) * 0.5, [atan2(-u[0], u[1]) / radian], ctx, rib, r, border, ring, keepR, depth);
            }
        }
    var comps = [];
    for (var c in comps0)
        comps = append(comps, splitBigArcs(c));
    for (var c in comps)
    {
        const nk = neck(c, d);
        if (nk != undefined)
        {
            // A boss held by a web thinner than a rib: split the core by a rib
            // through the web instead -- across the gap, so through the boss.
            if (depth >= 2)
                return straightCore(core, ctx, r, border, ring, keepR);
            const u = norm(nk.t - nk.s) > TAU ? normalize(nk.t - nk.s) : vector(1, 0);
            return bestSplit(core, (nk.s + nk.t) * 0.5, [atan2(-u[0], u[1]) / radian], ctx, rib, r, border, ring, keepR, depth);
        }
    }
    for (var c in comps)
        if (!loopOk(c))
            return retryCore(core, ctx, rib, r, border, ring, keepR, depth, nudged);
    var out = [];
    if (k <= 0)
    {
        for (var c in comps)
            out = append(out, { "loop" : c });
        return out;
    }
    // Smallest hole: a circle of keepR fits in a piece iff the core shrunk by
    // k = keepR - r, less the bands grown by k, has some of it in that piece.
    var inner = insetConvex(core, k);
    inner = size(inner) > 0 ? tidy(ccw(inner)) : [];
    if (size(inner) == 0)
        return [];
    const res2 = bandClip(inner, ctx, k);
    if (res2.status == "empty" || res2.status == "fail")
        return [];
    var probes = [];
    if (res2.status == "plain")
        probes = [centroid2(inner)];
    else
        for (var lp in res2.comps)
            probes = append(probes, pieceAt(lp[0], 0.5));
    for (var c in comps)
        for (var x in probes)
            if (winding(c, x) != 0)
            {
                out = append(out, { "loop" : c });
                break;
            }
    return out;
}

// Splits a core in two by a rib through X, at each angle in turn, and keeps
// the split whose holes cover the most.
function bestSplit(core is array, X is Vector, angles is array, ctx is map, rib is number, r is number, border is number, ring is number, keepR is number, depth is number) returns array
{
    const d = rib / 2 + r;
    var best = [];
    var bestArea = -1;
    for (var th in angles)
    {
        const nv = rot90(vector(cos(th * radian), sin(th * radian)));
        var holes = [];
        for (var piece in [clipHalf(core, X + nv * d, nv * -1), clipHalf(core, X - nv * d, nv)])
            if (size(piece) >= 3)
                holes = concatenateArrays([holes, bandHoles(piece, ctx, rib, r, border, ring, keepR, depth + 1, false)]);
        var area = 0;
        for (var h in holes)
            area += holeArea(h, r);
        if (area > bestArea + 1e-9)
        {
            best = holes;
            bestArea = area;
        }
    }
    return best;
}


// ---------------------------------------------------------------- struts
//
// With 6-sided cells, a round hole of at least strutMinD gets a ring of
// Voronoi seeds round it, and the lattice seeds inside that ring go. Cells of
// seeds in a ring are wedges, so the ribs between them -- ordinary cell
// edges, one rib wide like every other -- run straight out from the hole's
// band and join the web where the ring meets the rest of the pattern.

// The round holes that get a ring of cells: { c, rc, rs (ring radius),
// rcl (clear radius), n (seeds), t0 (first angle) } each. Big holes first; a
// hole whose ring would overlap a bigger one's by much goes without.
function rosettes(circles is array, ring is number, p is number, minD is number, s is number) returns array
{
    var cand = [];
    for (var i = 0; i < size(circles); i += 1)
    {
        const rc = circles[i].r;
        if (2 * rc >= minD)
        {
            const rs = rc + ring + 0.45 * p;
            cand = append(cand, { "i" : i, "c" : circles[i].c, "rc" : rc, "rs" : rs, "rcl" : rs + 0.75 * p });
        }
    }
    cand = sort(cand, function(a, b) { return a.rc != b.rc ? b.rc - a.rc : a.i - b.i; });
    var out = [];
    for (var e in cand)
    {
        var ok = true;
        for (var o in out)
            if (norm(e.c - o.c) < 0.8 * (e.rcl + o.rcl))
                ok = false;
        if (ok)
            out = append(out, { "c" : e.c, "rc" : e.rc, "rs" : e.rs, "rcl" : e.rcl,
                        "n" : max(5, round(2 * PI * e.rs / p)), "t0" : 360 * hash01(e.i * 31 + 7, s) });
    }
    return out;
}

// Voronoi cells of any seeds, each clipped to the rectangle lo..hi. A cell is
// right once every seed within twice its radius has cut it, so each starts
// from the seeds within 2 rc0 and widens the search until its own radius says
// nothing further can reach it. The rectangle keeps every cell bounded -- a
// seed on the edge of the pattern has an open cell otherwise -- and the seeds
// are filed in a grid, so each only looks at those near it.
function voronoiSeeds(seeds is array, lo is Vector, hi is Vector, rc0 is number) returns array
{
    const g = 2 * rc0;
    var boxes = [];
    for (var q in seeds)
        boxes = append(boxes, [q[0], q[1], q[0], q[1]]);
    const grid = gridOf(boxes, g);
    var out = [];
    for (var i = 0; i < size(seeds); i += 1)
    {
        const sd = seeds[i];
        var reachN = 2 * rc0;
        var c = [];
        while (true)
        {
            const h = reachN / 2;
            const b0 = vector(max(lo[0], sd[0] - h), max(lo[1], sd[1] - h));
            const b1 = vector(min(hi[0], sd[0] + h), min(hi[1], sd[1] + h));
            c = [];
            if (b1[0] > b0[0] && b1[1] > b0[1])
            {
                var nbrs = [];
                for (var j in gridFind(grid, g, [sd[0] - reachN, sd[1] - reachN, sd[0] + reachN, sd[1] + reachN]))
                    if (j != i && norm(seeds[j] - sd) < reachN)
                        nbrs = append(nbrs, seeds[j]);
                c = clipAll([b0, vector(b1[0], b0[1]), b1, vector(b0[0], b1[1])], sd, nbrs);
            }
            if (size(c) < 3)
                break;
            var far = 0;
            for (var q in c)
                far = max(far, norm(q - sd));
            if (2 * far <= reachN * (1 + 1e-9))
                break;
            reachN = 2 * far * (1 + 1e-6);
        }
        var cellPts = [];
        for (var k = 0; k < size(c); k += 1)
            if (norm(c[k] - c[(k + size(c) - 1) % size(c)]) > 1e-9)
                cellPts = append(cellPts, c[k]);
        if (size(cellPts) >= 3)
            out = append(out, cellPts);
    }
    return out;
}

// The seeds voronoiFit uses, its cell reach and its pitch.
function hexSeedsFit(lo is Vector, hi is Vector, cell is number, irregular is number, s is number) returns map
{
    const p0 = cell * PITCH_HEX;
    const W = hi - lo;
    const nx = max(1, round(W[0] / p0));
    const ny = max(1, round(W[1] / (p0 * sqrt(3) / 2)));
    const px = W[0] / nx;
    const h = W[1] / ny;
    const a = clamp(irregular, 0, 1) * JITTER_HEX * min(px, 2 * h / sqrt(3));
    var S = [];
    for (var j = 0; j < ny; j += 1)
    {
        const xs = hexRowX(j, nx);
        for (var k = 0; k < size(xs); k += 1)
        {
            const d = jitterVec(k, j, a, s);
            const wall = xs[k] == 0 || xs[k] == nx;
            S = append(S, lo + vector(xs[k] * px + (wall ? 0 : d[0]), (j + 0.5) * h + d[1]));
        }
    }
    const rc = max((h * h + px * px / 4) / (2 * h), sqrt(px * px + h * h) / 2) + 2 * a + 1e-6;
    return { "seeds" : S, "rc" : rc, "p" : px };
}

// 6-sided cells with a ring of cells round each big round hole: { cells,
// rosettes }, cells undefined where no hole gets one (the ordinary cells are
// then used). Fitted cells are clipped to lo..hi, as voronoiFit's are;
// cropped ones to that grown by a cell's reach, which keeps them bounded
// without touching any hole -- a cut that far out, shrunk by half a rib and
// the corner radius, still lies outside the face.
function strutCells(lo is Vector, hi is Vector, cell is number, irregular is number, s is number, circles is array, ring is number, minD is number, fit is boolean) returns map
{
    var S = [];
    var rc = 0;
    var p = 0;
    var b0 = lo;
    var b1 = hi;
    if (fit)
    {
        const hs = hexSeedsFit(lo, hi, cell, irregular, s);
        S = hs.seeds;
        rc = hs.rc;
        p = hs.p;
    }
    else
    {
        p = cell * PITCH_HEX;
        const h = p * sqrt(3) / 2;
        const a = clamp(irregular, 0, 1) * JITTER_HEX * p;
        const fr = latticeFrame(lo, hi, p, h);
        const V = lattice(fr.origin, p, fr.nx, fr.ny, true, a, s);
        rc = p / sqrt(3) + a + 1e-6;
        for (var i = 0; i <= fr.nx; i += 1)
            for (var j = 0; j <= fr.ny; j += 1)
            {
                const q = V[i][j];
                if (q[0] > lo[0] - rc && q[0] < hi[0] + rc && q[1] > lo[1] - rc && q[1] < hi[1] + rc)
                    S = append(S, q);
            }
        b0 = lo - vector(rc, rc);
        b1 = hi + vector(rc, rc);
    }
    const ros = rosettes(circles, ring, p, minD, s);
    if (size(ros) == 0)
        return { "cells" : undefined, "rosettes" : ros };
    var seeds = [];
    for (var q in S)
    {
        var keep = true;
        for (var o in ros)
            if (norm(q - o.c) < o.rcl)
                keep = false;
        if (keep)
            seeds = append(seeds, q);
    }
    for (var o in ros)
        for (var k = 0; k < o.n; k += 1)
        {
            const t = o.t0 + 360 * k / o.n;
            seeds = append(seeds, o.c + vector(o.rs * cos(t * degree), o.rs * sin(t * degree)));
        }
    return { "cells" : voronoiSeeds(seeds, b0, b1, rc), "rosettes" : ros };
}


// ---------------------------------------------------------------- one face

// The holes one cell makes with straight cuts (bands off): none or one.
function cellHoles(cell is array, region is map, rib is number, r is number, border is number, keepR is number) returns array
{
    const c = centroid2(cell);
    var core = insetConvex(cell, rib / 2 + r);
    if (size(core) < 3)
        return [];
    var cellR = 0;
    for (var q in cell)
        cellR = max(cellR, norm(q - c));
    core = regionClip(core, c, region, cellR + border + r + SAG + 1e-6, border, r, border);
    if (size(core) < 3)
        return [];
    core = tidy(ccw(core));
    if (size(core) == 0 || (keepR > r && size(insetConvex(core, keepR - r)) == 0))
        return [];
    return [{ "core" : core }];
}

// Every hole on one face. ring: undefined for straight cuts; else exact
// bands, ring wide round every hole in the face.
function planHoles(region is map, polys is array, settings is map) returns array
{
    const r = settings.r;
    const rib = settings.rib;
    const border = settings.border;
    const keepR = settings.keepR;
    const ring = settings.ring;
    var lo = region.lo;
    var hi = region.hi;
    if (settings.fit)
    {
        const ins = border - rib / 2;
        lo = region.lo + vector(ins, ins);
        hi = region.hi - vector(ins, ins);
    }
    var cells = undefined;
    if (settings.fit && (hi[0] <= lo[0] || hi[1] <= lo[1]))
        cells = [];
    else if (ring != undefined && settings.struts && settings.shape == LeopardCellShape.HEX)
        cells = strutCells(lo, hi, settings.cell, settings.irregular, settings.seed, region.circles, ring,
                           settings.strutMinD, settings.fit).cells;
    if (cells == undefined)
        cells = settings.fit
            ? fitCells(settings.shape, lo, hi, settings.cell, settings.irregular, settings.seed)
            : cropCells(settings.shape, lo, hi, settings.cell, settings.irregular, settings.seed);
    var holes = [];
    if (ring == undefined)
    {
        for (var cell in cells)
            holes = concatenateArrays([holes, cellHoles(cell, region, rib, r, border, keepR)]);
        return holes;
    }
    const ctx = bandContext(polys, region, border + r, ring + r, max(0, keepR - r));
    for (var cell in cells)
    {
        const core = insetConvex(cell, rib / 2 + r);
        if (size(core) > 0)
            holes = concatenateArrays([holes, bandHoles(core, ctx, rib, r, border, ring, keepR, 0, false)]);
    }
    return holes;
}


// ---------------------------------------------------------------- sketching
//
// Each hole's outline as sketch entities: { line, start, end } for a line,
// { start, mid, end } for an arc through three points. Every shared endpoint
// comes from one expression, so every loop closes exactly.

function lineEnt(a is Vector, b is Vector) returns map
{
    return { "line" : true, "start" : a, "end" : b };
}

function arcEnt(a is Vector, m is Vector, b is Vector) returns map
{
    return { "line" : false, "start" : a, "mid" : m, "end" : b };
}

// A plain core grown by r: its edges pushed out by r, joined by arcs of
// radius r about its corners.
function coreOutline(core is array, r is number) returns array
{
    const n = size(core);
    var ents = [];
    if (r <= 0)
    {
        for (var k = 0; k < n; k += 1)
            ents = append(ents, lineEnt(core[k], core[(k + 1) % n]));
        return ents;
    }
    var normals = [];
    for (var k = 0; k < n; k += 1)
    {
        const t = normalize(core[(k + 1) % n] - core[k]);
        normals = append(normals, vector(t[1], -t[0]));
    }
    for (var k = 0; k < n; k += 1)
    {
        const a = core[k];
        const b = core[(k + 1) % n];
        const nk = normals[k];
        const nn = normals[(k + 1) % n];
        ents = append(ents, lineEnt(a + nk * r, b + nk * r));
        ents = append(ents, arcEnt(b + nk * r, b + normalize(nk + nn) * r, b + nn * r));
    }
    return ents;
}

// A loop of pieces grown by r: each line moved out by r, each arc's radius
// grown (inside it) or shrunk (outside it) by r about the same centre, and an
// arc of radius r round every corner -- none where two pieces meet smoothly.
function loopOutline(lp is array, r is number) returns array
{
    const m = size(lp);
    var ents = [];
    if (r <= 0)
    {
        for (var p in lp)
            ents = append(ents, p.kind == "L" ? lineEnt(p.a, p.b) : arcEnt(p.a, pieceAt(p, 0.5), p.b));
        return ents;
    }
    var starts = [];
    var ends = [];
    for (var p in lp)
    {
        starts = append(starts, p.a + normalAt(p, p.a) * r);
        ends = append(ends, p.b + normalAt(p, p.b) * r);
    }
    for (var k = 0; k < m; k += 1)
    {
        const q = lp[(k + 1) % m];
        if (smoothJoin(normalAt(lp[k], lp[k].b), normalAt(q, q.a)))
            starts[(k + 1) % m] = ends[k];
    }
    for (var k = 0; k < m; k += 1)
    {
        const p = lp[k];
        if (p.kind == "L")
            ents = append(ents, lineEnt(starts[k], ends[k]));
        else
        {
            const mid = pieceAt(p, 0.5);
            ents = append(ents, arcEnt(starts[k], mid + normalAt(p, mid) * r, ends[k]));
        }
        const q = lp[(k + 1) % m];
        const n1 = normalAt(p, p.b);
        const n2 = normalAt(q, q.a);
        if (!smoothJoin(n1, n2))
            ents = append(ents, arcEnt(ends[k], p.b + normalize(n1 + n2) * r, starts[(k + 1) % m]));
    }
    return ents;
}

function holeOutline(hole is map, r is number) returns array
{
    if (hole.loop != undefined)
        return loopOutline(hole.loop, r);
    return coreOutline(hole.core, r);
}

function drawHole(sketch is Sketch, prefix is string, hole is map, r is number)
{
    const ents = holeOutline(hole, r);
    for (var k = 0; k < size(ents); k += 1)
    {
        const e = ents[k];
        if (e.line)
            skLineSegment(sketch, prefix ~ "e" ~ k, {
                        "start" : e.start * millimeter,
                        "end" : e.end * millimeter
                    });
        else
            skArc(sketch, prefix ~ "e" ~ k, {
                        "start" : e.start * millimeter,
                        "mid" : e.mid * millimeter,
                        "end" : e.end * millimeter
                    });
    }
}


// ---------------------------------------------------------------- areas
//
// Steiner's formula, area + perimeter * r + pi r^2, for a shape grown by r.
// It holds for every hole here: each outline turns through exactly one full
// turn, and grown by r stays simple.

function coreArea(core is array, r is number) returns number
{
    var per = 0;
    for (var k = 0; k < size(core); k += 1)
        per += norm(core[(k + 1) % size(core)] - core[k]);
    return abs(signedArea(core)) + per * r + PI * r * r;
}

function loopHoleArea(lp is array, r is number) returns number
{
    return loopArea(lp) + loopPerimeter(lp) * r + PI * r * r;
}

function holeArea(hole is map, r is number) returns number
{
    if (hole.loop != undefined)
        return loopHoleArea(hole.loop, r);
    return coreArea(hole.core, r);
}
