import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .model import ROOT, ModelUnavailable, model_files_present
from .review import PROFILE_PATH, load_profile, review_draft

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MAX_BODY_BYTES = 200_000


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        # Application drafts and request lines are left out of server logs.
        pass

    def _send(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _local_request(self):
        port = self.server.server_port
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        if host not in {f"127.0.0.1:{port}", f"localhost:{port}"} or (
            origin is not None and origin != f"http://{host}"
        ):
            self._json(HTTPStatus.FORBIDDEN, {"error": "Use the local Draftcheck address."})
            return False
        return True

    def do_GET(self):
        if not self._local_request():
            return
        path = urlsplit(self.path).path
        if path in STATIC:
            name, content_type = STATIC[path]
            self._send(HTTPStatus.OK, (ROOT / "web" / name).read_bytes(), content_type)
        elif path == "/api/profile":
            profile = load_profile()
            if profile is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "This copy of Draftcheck has no local voice guide."})
            else:
                self._json(HTTPStatus.OK, profile)
        elif path == "/api/status":
            self._json(
                HTTPStatus.OK,
                {"model_ready": model_files_present(), "has_voice_guide": PROFILE_PATH.is_file()},
            )
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Page not found."})

    def do_POST(self):
        if not self._local_request():
            return
        if self.path != "/api/review":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Page not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Send the draft as JSON."})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_BODY_BYTES:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Provide a draft within the size limit."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Send the draft as a JSON object.")
            result = review_draft(payload.get("text"), payload.get("kind", "general"))
        except (json.JSONDecodeError, UnicodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Send valid UTF-8 JSON."})
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except ModelUnavailable as error:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})
        except Exception:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "The local detector couldn't run. Run setup again, then restart Draftcheck."},
            )
        else:
            self._json(HTTPStatus.OK, result)


def serve(port, open_browser):
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Draftcheck is running at {url}", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
