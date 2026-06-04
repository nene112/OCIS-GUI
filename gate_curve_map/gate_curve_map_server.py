from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the data workspace for the OpenLayers gate curve viewer")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8610, help="Bind port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = Path(__file__).resolve().parents[1]
    handler = partial(SimpleHTTPRequestHandler, directory=str(data_root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {data_root}")
    print(f"Open http://{args.host}:{args.port}/gate_curve_map/gate_curve_map.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped by user.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
