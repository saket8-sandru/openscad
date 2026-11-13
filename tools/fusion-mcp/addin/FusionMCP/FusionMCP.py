# FusionMCP add-in: a tiny localhost HTTP bridge into Fusion 360's Python API.
#
# POST /exec   {"code": "...python...", "timeout": 120}
#     Runs the code on Fusion's main thread. Namespace: adsk, app, ui, design,
#     root (root component), tbm (TemporaryBRepManager), and a `result` slot.
#     Returns {"ok": bool, "stdout": str, "result": <json-able or repr>, "error": str}
# GET  /ping   -> {"ok": true, "product": ..., "document": ...}
#
# Everything the Fusion API can do is reachable through /exec, which is what the
# MCP server in ../server builds its tools on. Binds to 127.0.0.1 only; set a
# token in config.json and send it as the X-Token header to restrict callers
# further (any local process can otherwise send code).
import adsk.core, adsk.fusion
import json, os, io, queue, threading, traceback, contextlib, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_app = None
_ui = None
_handlers = []          # keep event handler objects alive
_jobs = queue.Queue()
_server = None
_thread = None
_cfg = {"host": "127.0.0.1", "port": 8765, "token": ""}
EVENT_ID = "FusionMCP_exec_event"


def _load_cfg():
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(p) as f:
            _cfg.update(json.load(f))
    except Exception:
        pass


class _Job:
    def __init__(self, code):
        self.code = code
        self.done = threading.Event()
        self.reply = None

    def run(self):
        out = io.StringIO()
        ns = {}
        try:
            design = adsk.fusion.Design.cast(_app.activeProduct)
            ns = {
                "adsk": adsk, "app": _app, "ui": _ui, "design": design,
                "root": design.rootComponent if design else None,
                "tbm": adsk.fusion.TemporaryBRepManager.get(),
                "result": None, "json": json, "os": os, "math": __import__("math"),
            }
            with contextlib.redirect_stdout(out):
                exec(compile(self.code, "<fusion-mcp>", "exec"), ns, ns)
            res = ns.get("result")
            try:
                json.dumps(res)
            except Exception:
                res = repr(res)
            self.reply = {"ok": True, "stdout": out.getvalue(), "result": res, "error": ""}
        except Exception:
            self.reply = {"ok": False, "stdout": out.getvalue(), "result": None,
                          "error": traceback.format_exc()}
        finally:
            self.done.set()


class _ExecHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        # Runs on Fusion's main thread. Drain every queued job.
        while True:
            try:
                job = _jobs.get_nowait()
            except queue.Empty:
                return
            try:
                job.run()
            except Exception:
                try:
                    job.reply = {"ok": False, "error": traceback.format_exc(), "stdout": "", "result": None}
                finally:
                    job.done.set()


class _Http(BaseHTTPRequestHandler):
    def log_message(self, *a):   # keep Fusion's console quiet
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        tok = _cfg.get("token") or ""
        if tok and self.headers.get("X-Token", "") != tok:
            self._send(403, {"ok": False, "error": "bad token"})
            return False
        return True

    def do_GET(self):
        if not self._auth():
            return
        if self.path == "/ping":
            try:
                doc = _app.activeDocument.name if _app and _app.activeDocument else None
            except Exception:
                doc = None
            self._send(200, {"ok": True, "product": "Fusion 360", "document": doc, "version": _app.version})
        else:
            self._send(404, {"ok": False, "error": "unknown path"})

    def do_POST(self):
        if not self._auth():
            return
        if self.path != "/exec":
            self._send(404, {"ok": False, "error": "unknown path"})
            return
        n = int(self.headers.get("Content-Length", "0"))
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception as e:
            self._send(400, {"ok": False, "error": "bad json: %s" % e})
            return
        code = req.get("code", "")
        timeout = float(req.get("timeout", 120))
        job = _Job(code)
        _jobs.put(job)
        _app.fireCustomEvent(EVENT_ID, "")
        if not job.done.wait(timeout):
            self._send(504, {"ok": False, "error": "timed out after %ss (Fusion busy or modal dialog open)" % timeout,
                             "stdout": "", "result": None})
            return
        self._send(200, job.reply)


def run(context):
    global _app, _ui, _server, _thread
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        _load_cfg()
        ev = _app.registerCustomEvent(EVENT_ID)
        h = _ExecHandler()
        ev.add(h)
        _handlers.append(h)
        _server = ThreadingHTTPServer((_cfg["host"], int(_cfg["port"])), _Http)
        _thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _thread.start()
        _app.log("FusionMCP bridge listening on http://%s:%s" % (_cfg["host"], _cfg["port"]))
    except Exception:
        if _ui:
            _ui.messageBox("FusionMCP failed to start:\n" + traceback.format_exc())


def stop(context):
    global _server
    try:
        if _server:
            _server.shutdown()
            _server.server_close()
            _server = None
        _app.unregisterCustomEvent(EVENT_ID)
    except Exception:
        pass
