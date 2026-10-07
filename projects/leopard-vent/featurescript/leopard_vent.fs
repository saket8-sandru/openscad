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
// and junctions only come out thicker. The border and the corner rounding are
// built the same way, by moving straight lines and never by approximation:
// every hole is a convex "core" polygon -- less, beside a round hole, one disc
// -- sketched as its edges pushed out by the corner radius and joined by true
// arcs.
//
// The face outline is handled in maths, not with an offset, because offsetting
// a face boundary inward fails as soon as the border is larger than one of its
// fillets. The outline is sampled into chords (no more than 0.005mm off a
// curve), and each hole is clipped by the chords near it. That is exact for a
// convex outline. Near an inside corner it trims holes a little more than
// strictly necessary -- never less.
//
// Round holes already in the face (bolts, bearings) get a round ring: each
// hole beside one is bitten by a disc, so its edge there is a true arc about
// the same centre, a set ring width off it. With spokes on, each round hole
// also gets a wheel -- its ring, a ring of sector holes split by straight
// spokes, and a hoop one rib wide that the cells beyond meet -- so a load on
// the bolt runs straight out into the web. Other inner loops (slots, odd
// shapes) are kept clear with one straight cut each, chosen to keep the most
// of the hole: exact beside a straight side, conservative elsewhere.
//
// Tested outside Onshape, in the repository this ships with: tools/fsmirror.py
// mirrors this geometry function for function and measures it against the
// true face outline, and tools/fsinterp.py runs this file's own maths --
// type annotations included -- and matches the mirror point for point. The
// Onshape calls themselves have never been run. See ../docs/featurescript.md.
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

const SPOKE_WIDTH_BOUNDS =
{
    (millimeter) : [0.1, 3, 1000],
    (centimeter) : 0.3,
    (meter) : 0.003,
    (inch) : 0.12,
    (foot) : 0.01,
    (yard) : 0.0033
} as LengthBoundSpec;

const SPOKE_LENGTH_BOUNDS =
{
    (millimeter) : [0.1, 10, 10000],
    (centimeter) : 1,
    (meter) : 0.01,
    (inch) : 0.4,
    (foot) : 0.033,
    (yard) : 0.011
} as LengthBoundSpec;

const SPOKE_MIN_BOUNDS =
{
    (millimeter) : [0, 10, 10000],
    (centimeter) : 1,
    (meter) : 0.01,
    (inch) : 0.4,
    (foot) : 0.033,
    (yard) : 0.011
} as LengthBoundSpec;

const SPOKE_ANGLE_BOUNDS =
{
    (degree) : [-360, 90, 360],
    (radian) : 0.5 * PI
} as AngleBoundSpec;

const SPOKE_COUNT_BOUNDS = { (unitless) : [0, 0, 100] } as IntegerBoundSpec;

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
const MIN_SWEEP = 0.02;    // radians: a shallower bite round a circle is cut straight instead
const MIN_TURN = 0.02;     // sine of the sharpest, and flattest, corner such a bite may make


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

        annotation { "Name" : "Round rings around circular holes", "Default" : true }
        definition.roundRings is boolean;

        if (definition.roundRings)
        {
            annotation { "Name" : "Ring width" }
            isLength(definition.ringWidth, RING_BOUNDS);

            annotation { "Name" : "Spokes from circular holes", "Default" : true }
            definition.spokes is boolean;

            if (definition.spokes)
            {
                annotation { "Name" : "Spokes only on holes from" }
                isLength(definition.spokeMinD, SPOKE_MIN_BOUNDS);

                annotation { "Name" : "Spoke thickness" }
                isLength(definition.spokeWidth, SPOKE_WIDTH_BOUNDS);

                annotation { "Name" : "Spoke length" }
                isLength(definition.spokeLength, SPOKE_LENGTH_BOUNDS);

                annotation { "Name" : "Spokes per hole (0 = auto)" }
                isInteger(definition.spokeCount, SPOKE_COUNT_BOUNDS);

                annotation { "Name" : "Spoke angle" }
                isAngle(definition.spokeAngle, SPOKE_ANGLE_BOUNDS);
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
                "fit" : definition.fit, "spokes" : false
            };
        // ring: undefined for one straight cut round each inner loop.
        if (definition.roundRings)
        {
            settings.ring = max(definition.ringWidth / millimeter, rib);
            if (definition.spokes)
            {
                settings.spokes = true;
                settings.spokeMinD = definition.spokeMinD / millimeter;
                settings.spokeWidth = definition.spokeWidth / millimeter;
                settings.spokeLength = definition.spokeLength / millimeter;
                settings.spokeCount = definition.spokeCount;
                settings.spokeAngle = definition.spokeAngle / degree;
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
    const holes = planHoles(region, settings);

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

// Chains sampled edges into closed loops, end to next start. A loop whose
// every edge lies on one circle -- a round hole -- carries that circle.
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
            chain = concatenateArrays([chain, subArray(polys[nxt].pts, 0, size(polys[nxt].pts) - 1)]);
            sag = max(sag, polys[nxt].sag);
            if (!sameCircle(circle, polys[nxt].circle))
                circle = undefined;
            end = polys[nxt].pts[size(polys[nxt].pts) - 1];
        }
        loops = append(loops, { "pts" : chain, "sag" : sag, "circle" : circle });
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

// Clips a core to the face: the border along the outline, and one straight
// cut per inner loop. With skipCircles, round inner loops are left alone
// here: they get round rings, from finishHole.
function regionClip(coreIn is array, c is Vector, region is map, reach is number, border is number, r is number, skipCircles is boolean) returns array
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
            if (skipCircles && innerLoop.circle != undefined)
                continue;
            if (innerLoop.parts == undefined)
                core = innerClip(core, c, innerLoop.hull, border + r + innerLoop.sag);
            else
                core = partsClip(core, c, innerLoop.parts, reach, border + r + innerLoop.sag);
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


// ---------------------------------------------------------------- round holes
//
// A round hole already in the face -- a bolt, a bearing -- gets a round ring
// of material instead of a straight cut. Every hole next to it is bitten by a
// disc, so the edge facing the circle is an arc about the same centre. In core
// terms (the hole shrunk by r) that is the core minus the disc of radius
// rho = Rc + ring + r. Grown back by r it is exactly the rounded hole kept
// `ring` clear of the circle, the disc's edge becoming an arc of radius
// Rc + ring: the same opening argument that makes the corner rounding exact.
// The circle is taken from the edge itself, so the ring is exact too, with no
// chord allowance.

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

// A convex counter-clockwise core minus the disc (C, rho), when that is one
// shape the feature can draw: pts runs E ... X along the core, and the arc
// from X back to E, clockwise about C, closes it. Otherwise kind is "none"
// (the disc misses), "gone" (it covers the core), "split" or "cut".
// "split": the disc's centre inside the core would leave the circle on an
// island, and a disc through the middle would split the core in two -- so the
// core is split by a rib through the circle first. "cut": a sliver of a bite,
// or of what is left, not worth its tiny sketch entities -- cut it straight
// instead, which costs next to nothing.
function circleBite(core is array, C is Vector, rho is number) returns map
{
    if (polyPointDist(core, C) >= rho)
        return { "kind" : "none" };
    var far = 0;
    for (var q in core)
        far = max(far, norm(q - C));
    if (far <= rho)
        return { "kind" : "gone" };
    if (pointInConvex(core, C))
        return { "kind" : "split" };
    const n = size(core);
    var xs = [];
    for (var k = 0; k < n; k += 1)
    {
        const a = core[k];
        const d = core[(k + 1) % n] - a;
        const f = a - C;
        const qa = dot(d, d);
        const qb = 2 * dot(f, d);
        const qc = dot(f, f) - rho * rho;
        const disc = qb * qb - 4 * qa * qc;
        if (qa <= 0 || disc <= 0)
            continue;
        const sq = sqrt(disc);
        const t0 = (-qb - sq) / (2 * qa);
        const t1 = (-qb + sq) / (2 * qa);
        if (t0 >= 0 && t0 < 1)
            xs = append(xs, { "k" : k, "dir" : 1, "p" : a + d * t0 });
        if (t1 >= 0 && t1 < 1)
            xs = append(xs, { "k" : k, "dir" : -1, "p" : a + d * t1 });
    }
    if (size(xs) != 2 || xs[0].dir == xs[1].dir)
        return { "kind" : "split" };
    const xIn = xs[0].dir == 1 ? xs[0] : xs[1];
    const xOut = xs[0].dir == 1 ? xs[1] : xs[0];
    var m = (xIn.k - xOut.k + n) % n;
    if (m == 0)
        m = n;
    var pts = [xOut.p];
    for (var j = 1; j <= m; j += 1)
        pts = append(pts, core[(xOut.k + j) % n]);
    pts = append(pts, xIn.p);
    for (var k = 0; k < size(pts) - 1; k += 1)
        if (norm(pts[k + 1] - pts[k]) < TINY_EDGE)
            return { "kind" : "cut" };
    const uX = normalize(xIn.p - C);
    const uE = normalize(xOut.p - C);
    if (-cross2(uX, uE) < sin(MIN_SWEEP * radian))
        return { "kind" : "cut" };
    if (!pointInConvex(core, C + normalize(uX + uE) * rho))
        return { "kind" : "cut" };
    const tIn = normalize(xIn.p - pts[size(pts) - 2]);
    const tOut = normalize(pts[1] - xOut.p);
    if (cross2(vector(tIn[1], -tIn[0]), uX * -1) < MIN_TURN || cross2(uE * -1, vector(tOut[1], -tOut[0])) < MIN_TURN)
        return { "kind" : "cut" };
    return { "kind" : "bite", "C" : C, "rho" : rho, "pts" : pts,
            "sweep" : acos(clamp(dot(uX, uE), -1, 1)) / radian };
}

// A straight cut keeping a core clear of the disc (C, rho): of a few
// half-planes that miss the disc, the one keeping the most core. The fallback
// when a bite will not do, and for every disc but the deepest.
function discCut(core is array, C is Vector, rho is number) returns array
{
    var cands = [];
    const g = centroid2(core) - C;
    if (norm(g) > 1e-9)
        cands = append(cands, normalize(g));
    if (!pointInConvex(core, C))
    {
        const q = nearestOnLoop(core, C) - C;
        if (norm(q) > 1e-9)
            cands = append(cands, normalize(q));
    }
    for (var k = 0; k < 16; k += 1)
        cands = append(cands, vector(cos(22.5 * k * degree), sin(22.5 * k * degree)));
    var best = [];
    var bestArea = 0;
    for (var u in cands)
    {
        const kept = clipHalf(core, C + u * rho, u * -1);
        const area = size(kept) >= 3 ? abs(signedArea(kept)) : 0;
        if (area > bestArea)
        {
            best = kept;
            bestArea = area;
        }
    }
    return size(best) >= 3 ? tidy(ccw(best)) : [];
}

// Tidies a core, keeps it out of every disc { c, rho } in discs -- one bite
// from the disc reaching deepest into it, a straight cut for any other -- and
// applies the smallest-hole test. Returns a list of holes { core, bite }:
// none, one, or two when the core had to be split by a rib through a circle,
// splitD (rib / 2 + r) either side of it.
function finishHole(coreIn is array, discs is array, r is number, keepR is number, splitD is number, depth is number) returns array
{
    var core = tidy(ccw(coreIn));
    if (size(core) < 3)
        return [];
    var bite = undefined;
    var near = [];
    const cc = centroid2(core);
    var cr = 0;
    for (var q in core)
        cr = max(cr, norm(q - cc));
    for (var k = 0; k < size(discs); k += 1)
    {
        if (norm(discs[k].c - cc) - cr >= discs[k].rho)      // quick reject: the core lies within cr of cc
            continue;
        const dk = polyPointDist(core, discs[k].c);
        if (dk < discs[k].rho)
            near = append(near, { "depth" : dk - discs[k].rho, "k" : k });
    }
    near = sort(near, function(a, b) { return a.depth != b.depth ? a.depth - b.depth : a.k - b.k; });
    for (var j = 1; j < size(near); j += 1)
    {
        core = discCut(core, discs[near[j].k].c, discs[near[j].k].rho);
        if (size(core) < 3)
            return [];
    }
    if (size(near) > 0)
    {
        const deepest = discs[near[0].k];
        const b = circleBite(core, deepest.c, deepest.rho);
        if (b.kind == "gone")
            return [];
        if (b.kind == "split" && depth == 0)
            return splitHole(core, deepest.c, discs, r, keepR, splitD);
        if (b.kind == "cut" || b.kind == "split")
        {
            core = discCut(core, deepest.c, deepest.rho);
            if (size(core) < 3)
                return [];
        }
        else if (b.kind == "bite")
            bite = b;
    }
    if (keepR > r)
    {
        const inner = insetConvex(core, keepR - r);
        if (size(inner) < 3)
            return [];
        // Bitten: a circle of keepR fits iff some corner of the core shrunk
        // by keepR - r stays keepR - r clear of the disc.
        if (bite != undefined)
        {
            var far = 0;
            for (var q in inner)
                far = max(far, norm(q - bite.C));
            if (far < bite.rho + keepR - r)
                return [];
        }
    }
    return [{ "core" : core, "bite" : bite }];
}

// A core holding a circle's centre, or cut through by its disc: split it by a
// rib through the centre, so that each side gets a true round bite, and take
// whichever of six directions keeps the most hole.
function splitHole(core is array, C is Vector, discs is array, r is number, keepR is number, splitD is number) returns array
{
    var best = [];
    var bestArea = -1;
    for (var k = 0; k < 6; k += 1)
    {
        const u = vector(cos(30 * k * degree), sin(30 * k * degree));
        var holes = [];
        for (var piece in [keepLeft(core, C, u, splitD), keepRight(core, C, u, splitD)])
            if (size(piece) >= 3)
                holes = concatenateArrays([holes, finishHole(piece, discs, r, keepR, splitD, 1)]);
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


// ---------------------------------------------------------------- wheels
//
// With spokes on, each round hole gets a wheel: its ring, then a ring of
// sector-shaped holes split by straight spokes, then a hoop one rib wide, and
// the ordinary cells beyond, bitten round to meet it. A load on the bolt or
// bearing goes straight out along the spokes into the hoop, and from the hoop
// into the web all round.
//
//   Rc   the circle          ra = Rc + ring      inner edge of the sectors
//   rb = ra + spoke length   outer edge          rb + rib: cells start here
//
// A sector is exact -- two straight sides half a spoke off the spokes, arcs of
// radius ra and rb, corners rounded by r -- wherever nothing else touches it.
// One that the border, an inner loop or another wheel reaches into is built as
// a polygon with its outer arc replaced by the chord (so only ever smaller)
// and goes through the same clipping and bite as an ordinary cell.

function leftNormal(u is Vector) returns Vector
{
    return vector(-u[1], u[0]);
}

function keepLeft(p is array, C is Vector, u is Vector, d is number) returns array
{
    const nv = leftNormal(u);
    return clipHalf(p, C + nv * d, nv * -1);
}

function keepRight(p is array, C is Vector, u is Vector, d is number) returns array
{
    const nv = leftNormal(u);
    return clipHalf(p, C - nv * d, nv);
}

// Spokes round one circle: as asked, or about one per cell of circumference,
// halfway along the spokes.
function spokeCount(ra is number, depth is number, cell is number, count is number) returns number
{
    if (count > 0)
        return max(3, count);
    return max(3, round(2 * PI * (ra + depth / 2) / cell));
}

function spokeDirs(n is number, angle is number) returns array
{
    var out = [];
    for (var k = 0; k < n; k += 1)
    {
        const t = angle + 360 * k / n;
        out = append(out, vector(cos(t * degree), sin(t * degree)));
    }
    return out;
}

// The eroded sector between spoke u0 (on its left) and spoke u1 (on its
// right), from ri to ro off C, or undefined when it is not a proper
// four-sided one. Corners: A0, B0 on spoke u0's side, B1, A1 on spoke u1's.
function sectorShape(C is Vector, u0 is Vector, u1 is Vector, d is number, ri is number, ro is number)
{
    if (ri <= d || ro <= ri)
        return undefined;
    const n0 = leftNormal(u0);
    const n1 = leftNormal(u1);
    const si = sqrt(ri * ri - d * d);
    const so = sqrt(ro * ro - d * d);
    if (so - si < TINY_EDGE)
        return undefined;
    const A0 = C + (n0 * d + u0 * si);
    const B0 = C + (n0 * d + u0 * so);
    const B1 = C + (n1 * -d + u1 * so);
    const A1 = C + (n1 * -d + u1 * si);
    const a0 = normalize(A0 - C);
    const a1 = normalize(A1 - C);
    const b0 = normalize(B0 - C);
    const b1 = normalize(B1 - C);
    // The inner arc runs clockwise from A1 to A0: it must turn a little at least.
    if (cross2(a0, a1) < sin(MIN_SWEEP * radian) || norm(A0 - A1) < TINY_EDGE)
        return undefined;
    return { "C" : C, "u0" : u0, "u1" : u1, "d" : d, "ri" : ri, "ro" : ro,
            "A0" : A0, "B0" : B0, "B1" : B1, "A1" : A1,
            "phiI" : acos(clamp(dot(a0, a1), -1, 1)) / radian,
            "phiO" : acos(clamp(dot(b0, b1), -1, 1)) / radian };
}

// Does a circle k larger than the eroded sector's edges fit in it? Its best
// centre is on the bisector, ri + k .. ro - k out, far enough from the spokes.
function sectorKeeps(s is map, k is number) returns boolean
{
    if (k <= 0)
        return true;
    const half = acos(clamp(dot(s.u0, s.u1), -1, 1)) / 2;
    return max(s.ri + k, (s.d + k) / sin(half)) <= s.ro - k;
}

// The wedge between two spokes cut off past ro: by the tangent to the outer
// arc (a polygon holding the true sector, to test it against) and by the
// chord (one inside it, to build a clipped sector from).
function sectorPolys(C is Vector, u0 is Vector, u1 is Vector, d is number, ro is number) returns map
{
    const h = ro + 1;
    const big = [C + vector(-h, -h), C + vector(h, -h), C + vector(h, h), C + vector(-h, h)];
    const wedge = keepRight(keepLeft(big, C, u0, d), C, u1, d);
    if (size(wedge) < 3 || ro <= d)
        return { "tangent" : [], "chord" : [] };
    const b = normalize(u0 + u1);
    const so = sqrt(ro * ro - d * d);
    const pl = C + (leftNormal(u0) * d + u0 * so);
    const pr = C + (leftNormal(u1) * -d + u1 * so);
    return { "tangent" : clipHalf(wedge, C + b * ro, b), "chord" : clipLeftOf(wedge, pl, pr, 0) };
}

// The sector holes round circle i.
function wheelHoles(i is number, wheels is array, zones is array, region is map, rib is number, r is number, border is number, keepR is number) returns array
{
    const w = wheels[i];
    const C = w.c;
    const dirs = w.dirs;
    const d = w.d;
    const ri = w.ra + r;
    const ro = w.rb - r;
    const n = size(dirs);
    var holes = [];
    for (var k = 0; k < n; k += 1)
    {
        const u0 = dirs[k];
        const u1 = dirs[(k + 1) % n];
        const polys = sectorPolys(C, u0, u1, d, ro);
        const tangent = polys.tangent;
        if (size(tangent) < 3)
            continue;
        var others = [];
        for (var j = 0; j < size(zones); j += 1)
            if (j != i && polyPointDist(tangent, zones[j].c) < zones[j].rho)
                others = append(others, zones[j]);
        const c = centroid2(tangent);
        var reach = 0;
        for (var q in tangent)
            reach = max(reach, norm(q - c));
        reach = reach + border + r + SAG + 1e-6;
        const clipped = regionClip(tangent, c, region, reach, border, r, true);
        const s = sectorShape(C, u0, u1, d, ri, ro);
        if (s != undefined && size(others) == 0 && size(clipped) >= 3 &&
            abs(abs(signedArea(clipped)) - abs(signedArea(tangent))) <= TINY_AREA)
        {
            if (sectorKeeps(s, keepR - r))
                holes = append(holes, { "sector" : s });
            continue;
        }
        const chord = polys.chord;
        if (size(chord) < 3)
            continue;
        const core = regionClip(chord, centroid2(chord), region, reach, border, r, true);
        if (size(core) < 3)
            continue;
        holes = concatenateArrays([holes, finishHole(core, concatenateArrays([[{ "c" : C, "rho" : ri }], others]), r, keepR, rib / 2 + r, 0)]);
    }
    return holes;
}

// The holes one cell makes: none, one, or two split round a circle.
function cellHoles(cell is array, region is map, rib is number, r is number, border is number, keepR is number, skipCircles is boolean, discs is array) returns array
{
    const c = centroid2(cell);
    var core = insetConvex(cell, rib / 2 + r);
    if (size(core) < 3)
        return [];
    var cellR = 0;
    for (var q in cell)
        cellR = max(cellR, norm(q - c));
    core = regionClip(core, c, region, cellR + border + r + SAG + 1e-6, border, r, skipCircles);
    if (size(core) < 3)
        return [];
    return finishHole(core, discs, r, keepR, rib / 2 + r, 0);
}

// Every hole on one face: the wheels' sectors, then the cells.
function planHoles(region is map, settings is map) returns array
{
    const r = settings.r;
    const rib = settings.rib;
    const border = settings.border;
    const keepR = settings.keepR;
    const ring = settings.ring;
    var holes = [];
    var discs = [];
    if (ring != undefined)
    {
        for (var circ in region.circles)
            discs = append(discs, { "c" : circ.c, "rho" : circ.r + ring + r });
        if (settings.spokes)
        {
            const w = max(settings.spokeWidth, rib);
            var wheels = [];
            for (var circ in region.circles)
            {
                const ra = circ.r + ring;
                const n = spokeCount(ra, settings.spokeLength, settings.cell, settings.spokeCount);
                wheels = append(wheels, { "c" : circ.c, "rc" : circ.r, "ra" : ra, "rb" : ra + settings.spokeLength,
                            "d" : w / 2 + r, "dirs" : spokeDirs(n, settings.spokeAngle) });
            }
            var zones = [];
            var order = [];
            for (var i = 0; i < size(wheels); i += 1)
            {
                zones = append(zones, { "c" : wheels[i].c, "rho" : wheels[i].rb + rib + r });
                order = append(order, { "rc" : wheels[i].rc, "i" : i });
            }
            // Wheels only round holes of at least spokeMinD, and only where
            // they have room. Two that overlap by more than a spoke length
            // would chop each other up, so: between holes of like size
            // (neither 1.5 times the other), neither gets one -- a row of
            // holes just gets rings -- and between a big hole and a small
            // one, the big one keeps its wheel and the small one sits in it
            // with its ring.
            order = sort(order, function(a, b) { return a.rc != b.rc ? b.rc - a.rc : a.i - b.i; });
            var on = [];
            for (var i = 0; i < size(wheels); i += 1)
                on = append(on, false);
            for (var o in order)
            {
                const i = o.i;
                var ok = 2 * wheels[i].rc >= settings.spokeMinD;
                for (var j = 0; j < size(wheels); j += 1)
                {
                    if (j == i || 2 * wheels[j].rc < settings.spokeMinD || wheels[j].rc * 1.5 <= wheels[i].rc)
                        continue;
                    if (norm(wheels[i].c - wheels[j].c) >= zones[i].rho + zones[j].rho - settings.spokeLength)
                        continue;
                    if (on[j] || wheels[i].rc * 1.5 > wheels[j].rc)
                        ok = false;
                }
                on[i] = ok;
            }
            var keepOut = [];
            for (var j = 0; j < size(wheels); j += 1)
                keepOut = append(keepOut, on[j] ? zones[j] : discs[j]);
            for (var i = 0; i < size(wheels); i += 1)
            {
                const hs = on[i] ? wheelHoles(i, wheels, keepOut, region, rib, r, border, keepR) : [];
                holes = concatenateArrays([holes, hs]);
                // A wheel with no sector left is no wheel: cells only keep
                // their ring clear of that circle.
                if (size(hs) > 0)
                    discs[i] = zones[i];
            }
        }
    }
    var cells = [];
    if (settings.fit)
    {
        const ins = border - rib / 2;
        const lo = region.lo + vector(ins, ins);
        const hi = region.hi - vector(ins, ins);
        if (hi[0] > lo[0] && hi[1] > lo[1])
            cells = fitCells(settings.shape, lo, hi, settings.cell, settings.irregular, settings.seed);
    }
    else
        cells = cropCells(settings.shape, region.lo, region.hi, settings.cell, settings.irregular, settings.seed);
    for (var cell in cells)
        holes = concatenateArrays([holes, cellHoles(cell, region, rib, r, border, keepR, ring != undefined, discs)]);
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

// A bitten core grown by r: lines and corner arcs along pts as above, then an
// arc of radius r about X onto the circle, the concave arc of radius
// rho - r = Rc + ring about the circle's centre, and an arc about E back onto
// the first edge.
function biteOutline(b is map, r is number) returns array
{
    const pts = b.pts;
    const C = b.C;
    const rho = b.rho;
    const m = size(pts) - 1;
    const X = pts[m];
    const E = pts[0];
    const uX = normalize(X - C);
    const uE = normalize(E - C);
    const mid = normalize(uX + uE);
    var ents = [];
    if (r <= 0)
    {
        for (var k = 0; k < m; k += 1)
            ents = append(ents, lineEnt(pts[k], pts[k + 1]));
        return append(ents, arcEnt(X, C + mid * rho, E));
    }
    var normals = [];
    for (var k = 0; k < m; k += 1)
    {
        const t = normalize(pts[k + 1] - pts[k]);
        normals = append(normals, vector(t[1], -t[0]));
    }
    for (var k = 0; k < m; k += 1)
    {
        const nk = normals[k];
        ents = append(ents, lineEnt(pts[k] + nk * r, pts[k + 1] + nk * r));
        if (k + 1 < m)
        {
            const nn = normals[k + 1];
            const q = pts[k + 1];
            ents = append(ents, arcEnt(q + nk * r, q + normalize(nk + nn) * r, q + nn * r));
        }
    }
    const aX = X - uX * r;
    const aE = E - uE * r;
    const nl = normals[m - 1];
    const n0 = normals[0];
    ents = append(ents, arcEnt(X + nl * r, X + normalize(nl - uX) * r, aX));
    ents = append(ents, arcEnt(aX, C + mid * (rho - r), aE));
    return append(ents, arcEnt(aE, E + normalize(n0 - uE) * r, E + n0 * r));
}

// An exact sector: side lines half a spoke off the spokes, the outer arc of
// radius ro + r = rb and the inner one of radius ri - r = ra about the
// circle's centre, and a corner arc of radius r at each of its four corners.
function sectorOutline(s is map, r is number) returns array
{
    const C = s.C;
    const A0 = s.A0;
    const B0 = s.B0;
    const B1 = s.B1;
    const A1 = s.A1;
    const n0 = leftNormal(s.u0);
    const n1 = leftNormal(s.u1);
    const b = normalize(s.u0 + s.u1);
    if (r <= 0)
        return [lineEnt(A0, B0), arcEnt(B0, C + b * s.ro, B1), lineEnt(B1, A1), arcEnt(A1, C + b * s.ri, A0)];
    const a0 = normalize(A0 - C);
    const a1 = normalize(A1 - C);
    const b0 = normalize(B0 - C);
    const b1 = normalize(B1 - C);
    const pA0 = A0 - n0 * r;
    const pB0 = B0 - n0 * r;
    const qB0 = B0 + b0 * r;
    const qB1 = B1 + b1 * r;
    const pB1 = B1 + n1 * r;
    const pA1 = A1 + n1 * r;
    const qA1 = A1 - a1 * r;
    const qA0 = A0 - a0 * r;
    return [lineEnt(pA0, pB0),
            arcEnt(pB0, B0 + normalize(b0 - n0) * r, qB0),
            arcEnt(qB0, C + b * (s.ro + r), qB1),
            arcEnt(qB1, B1 + normalize(b1 + n1) * r, pB1),
            lineEnt(pB1, pA1),
            arcEnt(pA1, A1 + normalize(n1 - a1) * r, qA1),
            arcEnt(qA1, C + b * (s.ri - r), qA0),
            arcEnt(qA0, A0 + normalize(a0 + n0) * -r, pA0)];
}

function holeOutline(hole is map, r is number) returns array
{
    if (hole.sector != undefined)
        return sectorOutline(hole.sector, r);
    if (hole.bite != undefined)
        return biteOutline(hole.bite, r);
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
// Steiner's formula, area + perimeter * r + pi r^2, for the core grown by r.
// It holds for the bitten and sector shapes as for a convex one: each outline
// turns through exactly one full turn, and grown by r stays simple.

function coreArea(core is array, r is number) returns number
{
    var per = 0;
    for (var k = 0; k < size(core); k += 1)
        per += norm(core[(k + 1) % size(core)] - core[k]);
    return abs(signedArea(core)) + per * r + PI * r * r;
}

// The polygon E ... X less the circular segment beyond its chord X-E.
function biteArea(b is map, r is number) returns number
{
    const pts = b.pts;
    var per = 0;
    for (var k = 0; k < size(pts) - 1; k += 1)
        per += norm(pts[k + 1] - pts[k]);
    per += b.rho * b.sweep;
    const area = abs(signedArea(pts)) - b.rho * b.rho / 2 * (b.sweep - sin(b.sweep * radian));
    return area + per * r + PI * r * r;
}

// The four corners' polygon, plus the outer circular segment, less the inner.
function sectorArea(s is map, r is number) returns number
{
    const side = norm(s.B0 - s.A0) + norm(s.A1 - s.B1);
    const area = abs(signedArea([s.A0, s.B0, s.B1, s.A1])) + s.ro * s.ro / 2 * (s.phiO - sin(s.phiO * radian))
        - s.ri * s.ri / 2 * (s.phiI - sin(s.phiI * radian));
    return area + (side + s.ro * s.phiO + s.ri * s.phiI) * r + PI * r * r;
}

function holeArea(hole is map, r is number) returns number
{
    if (hole.sector != undefined)
        return sectorArea(hole.sector, r);
    if (hole.bite != undefined)
        return biteArea(hole.bite, r);
    return coreArea(hole.core, r);
}
