"""Tiny local API that exposes the review search as TOOLS for the n8n AI agent.

    python src/api.py          # http://localhost:8765

GET /search?q=<question>&app=Notion|Evernote&k=12   most relevant reviews (semantic search, local embeddings)
GET /stats?app=Notion|Evernote                       praise / complaint / request counts per topic (all reviews)

Only the Python standard library is used for the server; it listens on this computer only (127.0.0.1).
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag  # noqa: E402

PORT = 8765
INDEX = rag.Index()
rag.embed(["warm up"], "query")  # load the embedding model once at start-up


def search(q, app=None, k=12):
    hits = INDEX.search(rag.embed([q], "query")[0], app or None, int(k))
    return [{"n": i + 1, "app": r.app, "stars": int(r.rating), "date": f"{r.date:%b %Y}", "text": r.text,
             "helpful_likes": int(r.thumbs_up)} for i, r in enumerate(hits.itertuples())]


def stats(app=None):
    s = INDEX.stats if not app else INDEX.stats[INDEX.stats.app == app]
    return [{"app": r.app, "topic": r.topic, "praise": int(r.positive), "complaints": int(r.negative),
             "requests": int(r.request), "reviews_in_app": int(r.reviews_in_app)} for r in s.itertuples()
            if r.topic != "other"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        p = {k: v[0] for k, v in parse_qs(u.query).items()}
        app = p.get("app") if p.get("app") in ("Notion", "Evernote") else None
        try:
            if u.path == "/search" and p.get("q"):
                body, code = search(p["q"], app, min(int(p.get("k", 12)), 30)), 200
            elif u.path == "/stats":
                body, code = stats(app), 200
            else:
                body, code = {"error": "use /search?q=...&app=... or /stats?app=..."}, 404
        except Exception as e:
            body, code = {"error": str(e)}, 500
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"review API on http://127.0.0.1:{PORT}  (/search, /stats)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
