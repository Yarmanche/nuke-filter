#!/usr/bin/env python3
"""
Serves generator.html and processes video/GIF drops via ffmpeg.
Run:  python3 nuke_server.py [port]        (default port from FILTER_PORT, else 8788)
"""
import json, os, sys, tempfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from nuke_vid import run as nuke_run
import config

EXT_OK = {".mp4", ".gif", ".webm", ".mov", ".mkv", ".avi", ".jpg", ".jpeg", ".png", ".webp"}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def do_POST(self):
        if not self.path.startswith("/api/nuke"):
            self.send_error(404); return
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        name = os.path.basename(q.get("name", ["upload"])[0])
        ext = os.path.splitext(name)[1].lower()
        if ext not in EXT_OK:
            self._json(400, {"error": f"unsupported type: {ext}"}); return
        pos = q.get("pos", ["center"])[0]
        try: width = float(q.get("width", [str(config.LOGO_WIDTH)])[0])
        except ValueError: width = config.LOGO_WIDTH
        fx = fy = None
        try:
            if pos == "custom":
                fx = float(q.get("fx", ["0.5"])[0]); fy = float(q.get("fy", ["0.5"])[0])
        except ValueError: pass

        length = int(self.headers.get("Content-Length", 0))
        tmpdir = tempfile.mkdtemp(prefix="nuke_")
        inp = os.path.join(tmpdir, "in" + ext)
        with open(inp, "wb") as f:
            f.write(self.rfile.read(length))

        out_ext = ".gif" if ext == ".gif" else ".mp4"
        out = os.path.join(tmpdir, "out" + out_ext)
        r = nuke_run(inp, out, pos=pos, width=width, fx=fx, fy=fy)
        if r.returncode != 0 or not os.path.exists(out):
            self._json(500, {"error": (r.stderr or "ffmpeg failed")[-500:]}); return
        # serve output at /out/<id> — store mapping
        self.server.outputs = getattr(self.server, "outputs", {})
        oid = os.path.basename(tmpdir)
        self.server.outputs[oid] = out
        self._json(200, {"url": f"/out/{oid}{out_ext}",
                         "mb": round(os.path.getsize(out)/1e6, 1)})

    def do_GET(self):
        if self.path.startswith("/out/"):
            oid = self.path.split("/out/")[1]
            fname = self.server.outputs.get(os.path.splitext(oid)[0]) if hasattr(self.server, "outputs") else None
            if not fname:
                self.send_error(404); return
            ctype = "image/gif" if oid.endswith(".gif") else "video/mp4"
            with open(fname, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", f'attachment; filename="nuked-{os.path.basename(oid)}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else config.PORT
    print(f"server on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
