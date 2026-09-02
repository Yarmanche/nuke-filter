#!/usr/bin/env python3
"""Server + tray icon. Starts nuke_server.py, tray menu: open/stop.
Run: python3 nuke_tray.py   (or via the desktop launcher)"""
import base64, os, subprocess, sys, threading

import config

PORT = config.PORT
URL = f"http://localhost:{PORT}/generator.html"

# ---------- tiny red-box icon (16px, drawn in code so no asset needed) ----------
ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAjElEQVR4nO3WsQ3CAAxE0c8pc4RBYHwYJFkEOgoKIEgQJfdfadmSbbkwSJIkSZIkSWpyeA5cxvHGzp3n+TF3KBfKhXKhXCg3fJp4mia25no8vs0J5YZfbHVtS641lAvlQrlQLpQL5UK5UG5YWrDFl/iVUG7Y0wv8jVAulAvlQrms3YAkSZIkSZIk/ukOmW4NOkPsGf8AAAAASUVORK5CYII="

server = None

procs = {"server": None, "bot": None}

def _alive(k):
    p = procs[k]
    return p is not None and p.poll() is None

def start_server():
    if _alive("server"): return True
    procs["server"] = subprocess.Popen(
        [sys.executable, "-u", os.path.join(config.BASE, "nuke_server.py"), str(PORT)],
        cwd=config.BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True

def start_bot():
    if _alive("bot"): return True
    # the bot itself loads .env from config.BASE (via config.py); env is inherited
    procs["bot"] = subprocess.Popen(
        [sys.executable, "-u", os.path.join(config.BASE, "nuke_bot.py")],
        cwd=config.BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True

def stop_one(k):
    p = procs[k]
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill()
    procs[k] = None

def stop_server():
    stop_one("server")

def stop_bot():
    stop_one("bot")

def server_running(): return _alive("server")
def bot_running(): return _alive("bot")

def open_browser():
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, URL])

def main():
    try:
        import pystray
        from PIL import Image
    except ImportError:
        # no tray lib — just run server in foreground
        print("pystray not installed — running server in foreground. Ctrl-C to stop.")
        os.execv(sys.executable, [sys.executable, "-u", os.path.join(config.BASE, "nuke_server.py"), str(PORT)])

    icon_image = Image.open(__import__("io").BytesIO(base64.b64decode(ICON_B64)))

    def on_open(icon, item):
        if not server_running(): start_server()
        open_browser()

    def on_toggle_server(icon, item):
        stop_server() if server_running() else start_server()

    def on_toggle_bot(icon, item):
        stop_bot() if bot_running() else start_bot()

    def on_quit(icon, item):
        stop_server(); stop_bot()
        icon.stop()
        os._exit(0)

    from pystray import Menu, MenuItem as MI
    icon = pystray.Icon("boxed_gen", icon_image, config.APP_NAME, menu=Menu(
        MI("open generator", on_open, default=True),
        MI(lambda text, item: ("stop gen server" if server_running() else "start gen server"), on_toggle_server),
        MI(lambda text, item: ("stop TG bot" if bot_running() else "start TG bot"), on_toggle_bot),
        MI("quit (kill everything)", on_quit),
    ))
    start_server()
    start_bot()
    threading.Timer(1.0, open_browser).start()  # auto-open on launch
    print("tray running — server on", URL)
    icon.run()

if __name__ == "__main__":
    main()
