#!/usr/bin/env python3
"""
MCP server (stdio) that forwards tool calls to the FusionMCP add-in running
inside Fusion 360 on this machine.

    pip install mcp requests
    python fusion_mcp_server.py            # normally launched by Claude Code via .mcp.json

Environment: FUSION_MCP_URL (default http://127.0.0.1:8765), FUSION_MCP_TOKEN.
"""
import json, os, sys
import requests
try:                                   # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:                    # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

URL = os.environ.get("FUSION_MCP_URL", "http://127.0.0.1:8765").rstrip("/")
TOKEN = os.environ.get("FUSION_MCP_TOKEN", "")
mcp = _Server("fusion")


def _hdr():
    return {"X-Token": TOKEN} if TOKEN else {}


def _exec(code: str, timeout: float = 120) -> dict:
    try:
        r = requests.post(URL + "/exec", json={"code": code, "timeout": timeout}, headers=_hdr(), timeout=timeout + 5)
        return r.json()
    except requests.ConnectionError:
        return {"ok": False, "error": "Cannot reach the FusionMCP add-in at %s. Is Fusion open and the add-in running?" % URL}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def _fmt(res: dict) -> str:
    return json.dumps(res, indent=1)


@mcp.tool()
def fusion_status() -> str:
    """Ping the Fusion bridge: product version and the active document name."""
    try:
        r = requests.get(URL + "/ping", headers=_hdr(), timeout=5)
        return _fmt(r.json())
    except Exception as e:
        return _fmt({"ok": False, "error": "bridge not reachable at %s: %r" % (URL, e)})


@mcp.tool()
def fusion_exec(code: str, timeout: float = 120) -> str:
    """Run Python inside Fusion 360 on its main thread.

    Namespace: adsk, app, ui, design (adsk.fusion.Design), root (root component),
    tbm (TemporaryBRepManager), math, json. Assign to `result` to return a value;
    print() output is captured. The Fusion API works in centimetres."""
    return _fmt(_exec(code, timeout))


@mcp.tool()
def fusion_list_components() -> str:
    """List components, their occurrences and bodies in the active design."""
    code = r'''
out = []
def walk(occs, depth):
    for o in occs:
        c = o.component
        out.append({"depth": depth, "name": o.name, "component": c.name,
                    "bodies": [b.name for b in c.bRepBodies], "visible": o.isVisible})
        walk(o.childOccurrences, depth + 1)
out.append({"depth": 0, "name": "(root)", "component": root.name, "bodies": [b.name for b in root.bRepBodies]})
walk(root.occurrences, 1)
result = out
'''
    return _fmt(_exec(code))


@mcp.tool()
def fusion_import_step(path: str, component_name: str = "") -> str:
    """Import a STEP file (e.g. a goBILDA part download) into the root of the active design.
    Returns the created occurrence names and their bounding boxes in mm."""
    code = r'''
import os
p = %s
if not os.path.exists(p):
    raise FileNotFoundError(p)
im = app.importManager
opts = im.createSTEPImportOptions(p)
opts.isViewFit = False
occs = im.importToTarget2(opts, root)
out = []
for o in occs:
    name = %s
    if name:
        o.component.name = name
    bb = o.boundingBox
    out.append({"occurrence": o.name, "bbox_mm": [[bb.minPoint.x*10, bb.minPoint.y*10, bb.minPoint.z*10],
                                                  [bb.maxPoint.x*10, bb.maxPoint.y*10, bb.maxPoint.z*10]]})
result = out
''' % (json.dumps(path), json.dumps(component_name))
    return _fmt(_exec(code, 300))


@mcp.tool()
def fusion_move_occurrence(occurrence_name: str, translate_mm: list, rotate_deg: list = None, axis: list = None) -> str:
    """Move an occurrence: translation in mm, optional rotation (degrees) about an axis (x,y,z) through its origin.
    rotate_deg is a single-element list, e.g. [90]."""
    code = r'''
name = %s
occ = None
for o in root.allOccurrences:
    if o.name == name or o.component.name == name:
        occ = o; break
if occ is None:
    raise ValueError("occurrence not found: " + name)
m = adsk.core.Matrix3D.create()
rot = %s
ax = %s
if rot:
    r = adsk.core.Matrix3D.create()
    r.setToRotation(math.radians(rot[0]), adsk.core.Vector3D.create(*ax), adsk.core.Point3D.create(0,0,0))
    m.transformBy(r)
t = %s
m.translation = adsk.core.Vector3D.create(t[0]/10.0, t[1]/10.0, t[2]/10.0)
occ.transform = m
design.snapshots.add() if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else None
result = "moved " + occ.name
''' % (json.dumps(occurrence_name), json.dumps(rotate_deg or []), json.dumps(axis or [0, 0, 1]), json.dumps(translate_mm))
    return _fmt(_exec(code))


@mcp.tool()
def fusion_screenshot(path: str, width: int = 1600, height: int = 1000, fit: bool = True) -> str:
    """Save a PNG of the active viewport to `path` (absolute path on the Fusion machine)."""
    code = r'''
vp = app.activeViewport
if %s:
    vp.fit()
ok = vp.saveAsImageFile(%s, %d, %d)
result = {"saved": bool(ok), "path": %s}
''' % ("True" if fit else "False", json.dumps(path), width, height, json.dumps(path))
    return _fmt(_exec(code))


@mcp.tool()
def fusion_run_script_file(path: str, timeout: float = 600) -> str:
    """Execute a Python file (on the Fusion machine) inside Fusion, in the bridge namespace.
    Use this to run projects/ftc-biobuzz-bot/fusion/build_in_fusion.py, for example."""
    code = r'''
import runpy, os, sys
p = %s
d = os.path.dirname(p)
if d not in sys.path:
    sys.path.insert(0, d)
ns = runpy.run_path(p, init_globals={"adsk": adsk, "app": app, "ui": ui, "design": design, "root": root, "tbm": tbm})
if "run" in ns and callable(ns["run"]):
    result = ns["run"](None)
else:
    result = "ran " + p
''' % json.dumps(path)
    return _fmt(_exec(code, timeout))


if __name__ == "__main__":
    mcp.run()
