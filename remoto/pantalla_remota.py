"""Control remoto de la pantalla de tu PC con Windows desde el teléfono.

Botones: apagar pantalla, encender pantalla y ver la pantalla casi en vivo.
Solo funciona dentro de tu red wifi y pide una clave en la dirección.

Uso:
    pip install mss
    python pantalla_remota.py
Luego abre en el teléfono la dirección que se imprime (misma red wifi).
"""
import ctypes
import json
import os
import secrets
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

try:
    import mss
    import mss.tools
except ImportError:
    sys.exit("Falta la librería mss. Instala con:  pip install mss")

if os.name != "nt":
    sys.exit("Este script es solo para Windows.")

PORT = int(os.environ.get("PORT", "8765"))
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clave.txt")

user32 = ctypes.windll.user32
HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170


def load_key():
    # La clave se guarda para que el enlace del teléfono siga valiendo entre ejecuciones
    try:
        with open(KEY_FILE, encoding="utf-8") as f:
            k = f.read().strip()
            if k:
                return k
    except OSError:
        pass
    k = secrets.token_urlsafe(12)
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(k)
    return k


KEY = load_key()


def monitor_off():
    # 2 = apagar monitor (la PC sigue encendida)
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)


def monitor_on():
    # Un movimiento mínimo del mouse despierta el monitor
    user32.mouse_event(0x0001, 1, 0, 0, 0)
    user32.mouse_event(0x0001, -1, 0, 0, 0)
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)


def screenshot_png():
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])  # todos los monitores juntos
        return mss.tools.to_png(shot.rgb, shot.size)


PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pantalla remota</title>
<style>
  body{margin:0;font-family:system-ui,sans-serif;background:#0c1311;color:#e4eeeb}
  .bar{display:flex;gap:8px;padding:12px;position:sticky;top:0;background:#151f1c}
  button{flex:1;padding:14px 8px;font:inherit;font-weight:700;border:0;border-radius:12px;
    background:#2dd4bf;color:#062520}
  button.off{background:#f87171;color:#2a0a0a}
  button.alt{background:#26342f;color:#e4eeeb}
  #msg{padding:0 12px 8px;font-size:13px;color:#8b9d98;min-height:1.4em}
  img{width:100%;display:block}
</style></head><body>
<div class="bar">
  <button class="off" id="off">Apagar pantalla</button>
  <button id="on">Encender</button>
  <button class="alt" id="view">Ver</button>
</div>
<div id="msg"></div>
<img id="shot" alt="" hidden>
<script>
var K=new URLSearchParams(location.search).get("k")||"", timer=null, busy=false;
function msg(t){document.getElementById("msg").textContent=t}
function post(a){return fetch("/"+a+"?k="+encodeURIComponent(K),{method:"POST"})
  .then(function(r){msg(r.ok?"Listo":"Error "+r.status)}).catch(function(){msg("Sin conexión")})}
document.getElementById("off").onclick=function(){stop();post("off")};
document.getElementById("on").onclick=function(){post("on")};
var img=document.getElementById("shot");
function tick(){
  if(busy)return; busy=true;
  img.onload=img.onerror=function(){busy=false};
  img.src="/shot.png?k="+encodeURIComponent(K)+"&t="+Date.now();
}
function stop(){clearInterval(timer);timer=null;img.hidden=true;
  document.getElementById("view").textContent="Ver"}
document.getElementById("view").onclick=function(){
  if(timer){stop();return}
  img.hidden=false;document.getElementById("view").textContent="Parar";
  tick();timer=setInterval(tick,1000);
};
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _auth(self):
        q = parse_qs(urlparse(self.path).query)
        return secrets.compare_digest(q.get("k", [""])[0], KEY)

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._auth():
            return self._send(403, "Clave incorrecta".encode())
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if path == "/shot.png":
            try:
                return self._send(200, screenshot_png(), "image/png")
            except Exception as e:
                return self._send(500, str(e).encode())
        self._send(404)

    def do_POST(self):
        if not self._auth():
            return self._send(403, "Clave incorrecta".encode())
        path = urlparse(self.path).path
        if path == "/off":
            monitor_off()
        elif path == "/on":
            monitor_on()
        else:
            return self._send(404)
        self._send(200, json.dumps({"ok": True}).encode(), "application/json")

    def log_message(self, *a):
        pass


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    print("Abre esto en tu teléfono (misma red wifi):")
    print(f"  http://{lan_ip()}:{PORT}/?k={KEY}")
    print("Ctrl+C para cerrar.")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
