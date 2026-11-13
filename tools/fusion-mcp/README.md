# Fusion MCP bridge

Lets a Claude Code session drive Autodesk Fusion 360 on your machine: run Python
inside Fusion, build bodies, import STEP files (goBILDA parts), move occurrences,
take viewport screenshots.

Two halves:

| Piece | Where it runs | What it does |
| --- | --- | --- |
| `addin/FusionMCP/` | **inside Fusion** (add-in) | opens `http://127.0.0.1:8765`, executes posted Python on Fusion's main thread |
| `server/fusion_mcp_server.py` | on your machine, launched by Claude Code | MCP server (stdio) exposing tools that call the add-in |

The repo's `.mcp.json` already points Claude Code at the server, so a local
session in this repo picks up the `fusion` tools automatically.

## Install (once)

1. **Add-in.** In Fusion: *Utilities > Add-Ins* (Shift+S), *Add-Ins* tab, green
   **+**, choose the folder `tools/fusion-mcp/addin/FusionMCP`, then select it
   and click **Run** (tick *Run on Startup*). Fusion's text command window
   (View > Show Text Commands) logs `FusionMCP bridge listening on http://127.0.0.1:8765`.
2. **Server deps.** `pip install mcp requests` (works with mcp 1.x and 2.x).
3. **Claude Code.** Open a terminal in this repo on the Fusion machine and start
   `claude`. Approve the `fusion` MCP server when prompted. Check with
   `/mcp`, or ask Claude to call `fusion_status`.

Without the MCP server you can also talk to the add-in directly:

```bash
curl -s localhost:8765/ping
```

```bash
curl -s -X POST localhost:8765/exec -H 'Content-Type: application/json' \
  -d '{"code":"result = [b.name for b in root.bRepBodies]"}'
```

## Tools

- `fusion_status` - version + active document.
- `fusion_exec(code)` - run Python in Fusion. Namespace: `adsk, app, ui, design, root, tbm, math, json`. Set `result` to return a value; `print` is captured. **Fusion's API uses centimetres.**
- `fusion_list_components` - occurrence tree with bodies.
- `fusion_import_step(path, component_name)` - import a STEP file into the root (goBILDA offers STEP downloads on each product page; download them to a folder on the Fusion machine first).
- `fusion_move_occurrence(name, translate_mm, rotate_deg, axis)` - place an imported part.
- `fusion_screenshot(path, w, h)` - PNG of the viewport, so Claude can look at the model.
- `fusion_run_script_file(path)` - run a script file in Fusion, e.g. `projects/ftc-biobuzz-bot/fusion/build_in_fusion.py`.

## Security

The add-in executes any Python it is sent. It binds to localhost only, but any
process on the machine can reach it. To restrict callers, put a token in
`addin/FusionMCP/config.json` and set `FUSION_MCP_TOKEN` to the same value in
`.mcp.json`'s `env` block. Stop the add-in when you are not using it.

## Limits

- A modal dialog in Fusion blocks the main thread; calls then time out (default 120 s).
- The add-in was written against the Fusion API documentation and tested here
  only against a stub of the `adsk` module (HTTP loop, job queue, error
  capture, MCP round-trip). The first run inside real Fusion is the real test;
  errors come back as full tracebacks in the tool result.
