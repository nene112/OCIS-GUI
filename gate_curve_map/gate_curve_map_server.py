from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse
TEXT_EXTENSIONS = {
    ".csv",
    ".css",
    ".html",
    ".htm",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".svg",
    ".tsv",
    ".txt",
}


class CachedTextFile(NamedTuple):
    mtime_ns: int
    content_type: str
    payload: bytes


def resolve_fs_api_path(raw_path: str) -> Path:
    text = str(raw_path or "").strip()
    path = Path(text)
    if path.is_absolute():
        return path
    page_dir = Path(__file__).resolve().parent
    candidates = [
        (page_dir / text).resolve(),
        (page_dir.parent / text).resolve(),
        (Path.cwd() / text).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def decode_text_bytes(payload: bytes) -> str:
    # Match local detectEncode(): try UTF-8 first, then GB18030/GBK strictly.
    # Do not score UTF-8 with errors="replace" against GBK — that can pick garbled headers.
    strict_ok: list[tuple[str, str]] = []
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            strict_ok.append((encoding, payload.decode(encoding)))
        except (UnicodeDecodeError, LookupError):
            continue

    if strict_ok:
        def score(item: tuple[str, str]) -> tuple[int, int]:
            encoding, text = item
            cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
            utf8_bonus = 1 if encoding.startswith("utf-8") else 0
            if cjk:
                return (cjk, utf8_bonus)
            return (0, utf8_bonus)

        return max(strict_ok, key=score)[1]

    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return payload.decode(encoding, errors="replace")
        except LookupError:
            continue
    return payload.decode("utf-8", errors="replace")


class Utf8HTTPRequestHandler(SimpleHTTPRequestHandler):
    text_cache: dict[str, CachedTextFile] = {}
    optional_text_defaults = {
        "stake.json": ("application/json; charset=utf-8", b"{}"),
    }

    def _is_text_file(self, path: Path) -> bool:
        return path.suffix.lower() in TEXT_EXTENSIONS

    def _build_cached_text_file(self, path: Path) -> CachedTextFile:
        raw = path.read_bytes()
        text = decode_text_bytes(raw)
        payload = text.encode("utf-8")
        content_type = self.guess_type(str(path))
        if "charset=" not in content_type.lower():
            content_type = f"{content_type}; charset=utf-8"
        return CachedTextFile(
            mtime_ns=path.stat().st_mtime_ns,
            content_type=content_type,
            payload=payload,
        )

    def _get_cached_text_file(self, path: Path) -> CachedTextFile:
        key = str(path.resolve())
        stat = path.stat()
        cached = self.text_cache.get(key)
        if cached and cached.mtime_ns == stat.st_mtime_ns:
            return cached

        cached = self._build_cached_text_file(path)
        self.text_cache[key] = cached
        return cached

    def _serve_utf8_text(self, path: Path, body: bool) -> None:
        cached = self._get_cached_text_file(path)

        self.send_response(200)
        self.send_header("Content-Type", cached.content_type)
        self.send_header("Content-Length", str(len(cached.payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(cached.payload)

    def _maybe_serve_text_file(self, body: bool) -> bool:
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            fallback = self.optional_text_defaults.get(path.name.lower())
            if not fallback:
                return False
            content_type, payload = fallback
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(payload)
            return True

        if not self._is_text_file(path):
            return False
        self._serve_utf8_text(path, body=body)
        return True

    def _send_json(self, payload: object, body: bool, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(data)

    def _handle_fs_read_api(self, query: dict[str, list[str]], body: bool) -> bool:
        raw_path = query.get("path", [""])[0]
        path = resolve_fs_api_path(raw_path)
        if not raw_path:
            self._send_json({"error": "missing path"}, body=body, status=400)
            return True
        if not path.is_file():
            fallback = self.optional_text_defaults.get(path.name.lower())
            if fallback:
                content_type, payload = fallback
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body:
                    self.wfile.write(payload)
                return True
            self._send_json({"error": "file not found", "path": raw_path}, body=body, status=404)
            return True
        if self._is_text_file(path):
            self._serve_utf8_text(path, body=body)
            return True
        content_type, _ = mimetypes.guess_type(str(path))
        if not content_type:
            content_type = "application/octet-stream"
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(payload)
        return True

    def _handle_fs_list_dir_api(self, query: dict[str, list[str]], body: bool) -> bool:
        raw_path = query.get("path", [""])[0]
        if not raw_path:
            self._send_json({"error": "missing path"}, body=body, status=400)
            return True
        path = resolve_fs_api_path(raw_path)
        if not path.exists() or not path.is_dir():
            self._send_json({"error": "directory not found", "path": raw_path}, body=body, status=404)
            return True
        items = sorted([item.name for item in path.iterdir() if item.is_dir()], key=str.lower)
        self._send_json({"items": items}, body=body)
        return True

    def _maybe_handle_api(self, body: bool) -> bool:
        parsed = urlparse(self.path)
        if parsed.path == "/api/fs/read":
            return self._handle_fs_read_api(parse_qs(parsed.query), body=body)
        if parsed.path == "/api/fs/list-dir":
            return self._handle_fs_list_dir_api(parse_qs(parsed.query), body=body)
        return False

    def do_GET(self) -> None:
        if self._maybe_handle_api(body=True):
            return
        if self._maybe_serve_text_file(body=True):
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self._maybe_handle_api(body=False):
            return
        if self._maybe_serve_text_file(body=False):
            return
        super().do_HEAD()


def warm_text_cache(data_root: Path) -> dict[str, CachedTextFile]:
    cache: dict[str, CachedTextFile] = {}
    for path in data_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue

        raw = path.read_bytes()
        text = decode_text_bytes(raw)
        payload = text.encode("utf-8")
        content_type, _ = mimetypes.guess_type(str(path))
        if not content_type:
            content_type = "text/plain"
        if "charset=" not in content_type.lower():
            content_type = f"{content_type}; charset=utf-8"
        cache[str(path.resolve())] = CachedTextFile(
            mtime_ns=path.stat().st_mtime_ns,
            content_type=content_type,
            payload=payload,
        )
    return cache


def warm_text_cache_in_background(data_root: Path) -> None:
    try:
        Utf8HTTPRequestHandler.text_cache.update(warm_text_cache(data_root))
        print(f"Warmed {len(Utf8HTTPRequestHandler.text_cache)} text files as UTF-8")
    except Exception as exc:
        print(f"Background UTF-8 warmup skipped: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the data workspace for the OpenLayers gate curve viewer")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8610, help="Bind port")
    parser.add_argument("--open", action="store_true", help="Open the viewer in the default browser after startup")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = Path(__file__).resolve().parents[1]
    Utf8HTTPRequestHandler.text_cache = {}
    handler = partial(Utf8HTTPRequestHandler, directory=str(data_root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    viewer_url = f"http://{args.host}:{args.port}/gate_curve_map/gate_curve_map.html"
    print(f"Serving {data_root}")
    print(f"Open {viewer_url}")
    if args.open:
        try:
            webbrowser.open(viewer_url, new=2)
            print("Browser launch requested.")
        except Exception as exc:
            print(f"Browser auto-open failed: {exc}")
    threading.Thread(
        target=warm_text_cache_in_background,
        args=(data_root,),
        daemon=True,
        name="utf8-warm-cache",
    ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped by user.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
