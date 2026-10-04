FeatureScript 2960;
import(path : "onshape/std/geometry.fs", version : "2960.0");

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
// every hole is a convex "core" polygon, sketched as its edges pushed out by
// the corner radius and joined by true arcs.
//
// The face outline is handled in maths, not with an offset, because offsetting
// a face boundary inward fails as soon as the border is larger than one of its
// fillets. The outline is sampled into chords (no more than 0.005mm off a
// curve), and each hole is clipped by the chords near it. That is exact for a
// convex outline. Near an inside corner it trims holes a little more than
// strictly necessary -- never less. Inner loops (screw holes, slots) are kept
// clear with one straight cut each, chosen to keep the most of the hole:
// exact beside a round hole or a straight side, conservative elsewhere.
//
// Tested outside Onshape, in the repository this ships with: tools/fsmirror.py
// mirrors this geometry function for function and was measured on 729 cases
// against the true face outline, and tools/fsinterp.py runs this file's own
// maths and matches the mirror point for point. The Onshape calls themselves
// have never been run. See ../docs/featurescript.md.
//
// Paste into a Feature Studio. If Onshape has already written its own
// "FeatureScript" and "import" lines at the top, keep whichever version is
// newer. Every std call here was checked against version 2960; older
// versions are untested.
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

        const settings = {
                "shape" : shape, "cell" : cell, "rib" : rib, "r" : r, "keepR" : keepR,
                "border" : max(definition.border / millimeter, rib),
                "irregular" : definition.irregularity, "seed" : definition.seed,
                "fit" : definition.fit
            };

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
            if (size(plan.cores) == 0)
                continue;

            const sketchId = id + ("sketch" ~ fi);
            const sketch = newSketchOnPlane(context, sketchId, { "sketchPlane" : plan.sketchPlane });
            for (var hi = 0; hi < size(plan.cores); hi += 1)
            {
                drawHole(sketch, "h" ~ hi, plan.cores[hi], r);
                openArea += holeArea(plan.cores[hi], r);
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
            holeTotal += size(plan.cores);
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

    var cells;
    if (settings.fit)
    {
        const ins = settings.border - settings.rib / 2;
        const lo = region.lo + vector(ins, ins);
        const hi = region.hi - vector(ins, ins);
        cells = (hi[0] > lo[0] && hi[1] > lo[1])
            ? fitCells(settings.shape, lo, hi, settings.cell, settings.irregular, settings.seed)
            : [];
    }
    else
        cells = cropCells(settings.shape, region.lo, region.hi, settings.cell, settings.irregular, settings.seed);

    var cores = [];
    for (var c in cells)
    {
        const core = holeCore(c, region, settings.rib, settings.r, settings.border, settings.keepR);
        if (size(core) >= 3)
            cores = append(cores, core);
    }

    const box = evBox3d(context, { "topology" : qOwnerBody(face), "cSys" : cSys, "tight" : false });
    return {
            "cores" : cores,
            "sketchPlane" : sketchPlane,
            "below" : max(-box.minCorner[2] / millimeter, 0),
            "faceArea" : evArea(context, { "entities" : face }) / (millimeter * millimeter)
        };
}

// Points along one edge in face coordinates, and the worst chord error.
function sampleEdge(context is Context, edge is Query, face is Query, curve, len is number, cSys is CoordSystem) returns map
{
    var n = 1;
    var sag = 0;
    if (curve is Circle)
    {
        const rad = curve.radius / millimeter;
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
    return { "pts" : pts, "sag" : sag };
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
            const box = [s + vector(-rc, -rc), s + vector(rc, -rc), s + vector(rc, rc), s + vector(-rc, rc)];
            const c = clipAll(box, s, nbrs);
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

// Chains sampled edges into closed loops, end to next start.
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
            end = polys[nxt].pts[size(polys[nxt].pts) - 1];
        }
        loops = append(loops, { "pts" : chain, "sag" : sag });
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
            inners = append(inners, { "hull" : hull, "centre" : c, "sag" : lp.sag });
            inner = size(inners) - 1;
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
    return { "segs" : segs, "inners" : inners, "lo" : lo, "hi" : hi, "grid" : grid, "gs" : gs };
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

// The convex core of one hole. The hole itself is this grown by r.
function holeCore(cell is array, region is map, rib is number, r is number, border is number, keepR is number) returns array
{
    const c = centroid2(cell);
    var core = insetConvex(cell, rib / 2 + r);
    if (size(core) < 3)
        return [];
    var cellR = 0;
    for (var q in cell)
        cellR = max(cellR, norm(q - c));
    const reach = cellR + border + r + SAG + 1e-6;
    const near = nearSegments(region, c, reach);
    const inside = insideRegion(region, c);
    if (size(near) == 0)
    {
        if (!inside)
            return [];
    }
    else
    {
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
                core = innerClip(core, c, innerLoop.hull, border + r + innerLoop.sag);
            }
            if (size(core) < 3)
                return [];
        }
    }
    core = tidy(ccw(core));
    if (size(core) < 3)
        return [];
    if (keepR > r && size(insetConvex(core, keepR - r)) < 3)
        return [];
    return core;
}

// Sketches one hole: the core's edges pushed out by r, joined by arcs of
// radius r about its corners.
function drawHole(sketch is Sketch, prefix is string, core is array, r is number)
{
    const n = size(core);
    if (r <= 0)
    {
        for (var k = 0; k < n; k += 1)
            skLineSegment(sketch, prefix ~ "l" ~ k, {
                        "start" : core[k] * millimeter,
                        "end" : core[(k + 1) % n] * millimeter
                    });
        return;
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
        skLineSegment(sketch, prefix ~ "l" ~ k, {
                    "start" : (a + nk * r) * millimeter,
                    "end" : (b + nk * r) * millimeter
                });
        skArc(sketch, prefix ~ "a" ~ k, {
                    "start" : (b + nk * r) * millimeter,
                    "mid" : (b + normalize(nk + nn) * r) * millimeter,
                    "end" : (b + nn * r) * millimeter
                });
    }
}

function holeArea(core is array, r is number) returns number
{
    var per = 0;
    for (var k = 0; k < size(core); k += 1)
        per += norm(core[(k + 1) % size(core)] - core[k]);
    return abs(signedArea(core)) + per * r + PI * r * r;
}
