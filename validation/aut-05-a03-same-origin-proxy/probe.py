"""Owned localhost probe: real Origin policy, never a login success fixture."""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy, LoginOriginError

policy = LoginOriginPolicy((sys.argv[1],))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.handle_probe()

    def do_POST(self):
        self.handle_probe()

    def handle_probe(self):
        entries = [(name.lower().encode("ascii"), value.encode("ascii")) for name, value in self.headers.raw_items()]
        try:
            if self.command == "POST":
                policy.require_trusted(entries)
            else:
                policy.require_trusted_host(entries)
            status = 418  # Explicitly NOT a successful login/session response.
        except LoginOriginError:
            status = 403
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        data = {"policy_allowed": status == 418, "host": self.headers.get("Host"),
            "origin": self.headers.get("Origin"), "path": self.path,
            "method": self.command, "body_matches_synthetic": body == b'{"probe":true}',
            "cookie_matches_synthetic": self.headers.get("Cookie") == "probe_cookie=synthetic",
            "csrf_matches_synthetic": self.headers.get("X-CSRF-Token") == "synthetic-csrf-probe",
            "key_matches_synthetic": self.headers.get("Idempotency-Key") == "synthetic-probe-key"}
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
print(server.server_port, flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
