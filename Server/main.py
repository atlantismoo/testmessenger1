import json, uuid, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

HOST, PORT = "141.24.111.52", 20202
STORE, LOCK = {}, threading.Lock()

def convo_id(a, b): return "__".join(sorted([a, b]))

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, obj, status=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if urlparse(self.path).path != "/messages":
            return self._json({"error": "not found"}, 404)
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json({"error": "invalid json"}, 400)

        s, t, ts, msg = data.get("from"), data.get("to"), data.get("timestamp"), data.get("message")
        if not (s and t and ts and msg):
            return self._json({"error": "missing fields"}, 400)

        try: datetime.fromisoformat(ts)
        except Exception: pass

        m = {"id": str(uuid.uuid4()), "from": s, "to": t, "timestamp": ts, "message": msg, "status": "sent"}
        cid = convo_id(s, t)
        with LOCK:
            STORE.setdefault(cid, []).append(m)
            STORE[cid].sort(key=lambda x: x.get("timestamp", ""))
        return self._json(m, 201)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path != "/messages":
            return self._json({"error": "not found"}, 404)
        qs = parse_qs(p.query)
        since = qs.get("since", [None])[0]
        from_user = qs.get("from_user", [None])[0]
        to_user = qs.get("to", [None])[0] or qs.get("to", [None])[0]

        def newer(m):
            if since:
                try:
                    return m.get("timestamp", "") > since
                except Exception:
                    return True
            return True  # when since is None, accept all

        res = []
        with LOCK:
            if from_user and to_user:
                # return full convo if since is None, else only newer messages
                msgs = STORE.get(convo_id(from_user, to_user), [])
                res = [m for m in msgs if newer(m)]
            else:
                # aggregate across all convos
                for msgs in STORE.values():
                    for m in msgs:
                        if newer(m):
                            res.append(m)
                res.sort(key=lambda x: x.get("timestamp", ""))
        return self._json(res, 200)

    def log_message(self, *a): pass

if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Server running at http://{HOST}:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        print("Stopped")