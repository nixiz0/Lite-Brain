import sys, socket, uvicorn
from pathlib import Path
from threading import Thread
from livereload import Server
from CONFIG import DEV_PORT


# Root of the project (this file's directory)
ROOT = Path(__file__).parent.parent


# -------------------- Helper Functions --------------------
def safe_print(msg: str) -> None:
    """
    Print a message safely, avoiding Unicode issues on some Windows consoles.

    Falls back to ASCII with replacement characters if the console encoding
    cannot handle the given string.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))

def port_free(host: str, port: int) -> bool:
    """Return True if the given TCP port is available on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow quick reuse of ports in TIME_WAIT
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


# -------------------- Final Function --------------------
def start_livereload(host: str = "127.0.0.1", http_port: int = 5500, live_port: int = 35729) -> None:
    """
    Start the livereload server (static files + websocket).
    - Doesn't start if a LiveReload websocket is already bound on live_port.
    - Tries to find a free HTTP port starting from http_port.
    """
    # Do not start a second LiveReload WS server if one is already running
    if not port_free(host, live_port):
        safe_print(f"[LR] LiveReload {live_port} already running; skipping new instance.")
        return

    # Try to find a free HTTP port starting from http_port (optional convenience)
    if not port_free(host, http_port):
        for alt in range(http_port + 1, http_port + 50):
            if port_free(host, alt):
                http_port = alt
                break
        else:
            # Last-resort fallback if no port found in the search range
            http_port = 5510

    server = Server()

    # HTML templates
    server.watch(str(ROOT / "templates" / "**" / "*.html"), delay=0.2)

    # Compiled CSS (adapt filename if your build changes it)
    server.watch(str(ROOT / "static" / "css" / "app.css"), delay=0.1)

    # Frontend JS bundle(s)
    server.watch(str(ROOT / "static" / "js" / "*.js"), delay=0.1)

    safe_print(f"[LR] Livereload HTTP on {host}:{http_port}, WS on {live_port}")
    server.serve(
        host=host,
        port=http_port,
        liveport=live_port,
        root=str(ROOT),
        open_url_delay=None,
        debug=True,
    )

if __name__ == "__main__":
    # Force UTF-8 output if supported, safe_print is the fallback
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 1) Start livereload in a background thread (no-op if WS port already in use)
    Thread(target=start_livereload, daemon=True).start()

    # 2) Start Uvicorn with Python code auto-reload on changes
    uvicorn.run(
        "app.app:app",
        host="127.0.0.1",
        port=DEV_PORT,
        reload=True,
        reload_dirs=[
            str(ROOT / "app"),
            str(ROOT / "templates"),
        ],
    )
