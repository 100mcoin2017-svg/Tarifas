"""Escritorio remoto casero para Windows: ver y controlar tu PC desde el teléfono.

Desde el navegador del teléfono (misma red wifi) puedes:
  - Ver la pantalla de la PC en vivo.
  - Controlarla: mover el ratón, hacer clic, arrastrar, rueda y escribir.
  - Apagar y encender el monitor (el "widget": un acceso directo a .../?do=off lo apaga de un toque).

Uso:
    pip install mss pillow
    python pantalla_remota.py
Luego abre en el teléfono la dirección que se imprime.

Solo para Windows. Funciona dentro de tu red local; para usarlo fuera de casa
usa una VPN (p. ej. Tailscale), nunca abras el puerto a internet.
"""
import ctypes
import json
import os
import secrets
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from urllib.parse import parse_qs, urlparse

if os.name != "nt":
    sys.exit("Este script es solo para Windows.")

try:
    import mss
except ImportError:
    sys.exit("Falta 'mss'. Instala con:  pip install mss pillow")

try:
    from PIL import Image
except ImportError:
    sys.exit("Falta 'pillow'. Instala con:  pip install mss pillow")

PORT = int(os.environ.get("PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(HERE, "clave.txt")

# Calidad/tamaño del vídeo: más ancho = más nítido pero más lento por wifi
MAX_WIDTH = int(os.environ.get("ANCHO", "1100"))
JPEG_QUALITY = int(os.environ.get("CALIDAD", "45"))
FPS = int(os.environ.get("FPS", "12"))

# --- DPI: ver la resolución real y que el mapeo del ratón coincida ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32

# --- Apagar/encender monitor ---
HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170


def monitor_off():
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)


def monitor_on():
    # Un movimiento mínimo del ratón despierta el monitor
    _mouse(MOUSEEVENTF_MOVE, 1, 0)
    _mouse(MOUSEEVENTF_MOVE, -1, 0)
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)


# --- Simular ratón y teclado con SendInput ---
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR)]


class _IU(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _IU)]


def _send(inp):
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _mouse(flags, dx=0, dy=0, data=0):
    mi = MOUSEINPUT(dx, dy, data, flags, 0, None)
    _send(INPUT(INPUT_MOUSE, _IU(mi=mi)))


def move_to(fx, fy):
    # fx, fy: fracción 0..1 sobre el escritorio virtual completo
    nx = max(0, min(65535, int(fx * 65535)))
    ny = max(0, min(65535, int(fy * 65535)))
    _mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny)


def click(button="left", double=False):
    down, up = (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
    if button == "right":
        down, up = (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
    veces = 2 if double else 1
    for _ in range(veces):
        _mouse(down)
        _mouse(up)


def button_down(button="left"):
    _mouse(MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN)


def button_up(button="left"):
    _mouse(MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP)


def scroll(notches):
    _mouse(MOUSEEVENTF_WHEEL, data=int(notches) * 120)


def _key(vk, up, unicode_char=None):
    if unicode_char is not None:
        flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
        ki = KEYBDINPUT(0, ord(unicode_char), flags, 0, None)
    else:
        ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, None)
    _send(INPUT(INPUT_KEYBOARD, _IU(ki=ki)))


VK = {
    "enter": 0x0D, "back": 0x08, "tab": 0x09, "esc": 0x1B, "space": 0x20,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "win": 0x5B,
    "home": 0x24, "end": 0x23, "delete": 0x2E, "ctrl": 0x11,
}


def tap_key(name):
    vk = VK.get(name)
    if vk is None:
        return
    _key(vk, False)
    _key(vk, True)


def type_text(s):
    for ch in s:
        _key(0, False, unicode_char=ch)
        _key(0, True, unicode_char=ch)


def combo_ctrl(letter):
    _key(VK["ctrl"], False)
    vk = ord(letter.upper())
    _key(vk, False)
    _key(vk, True)
    _key(VK["ctrl"], True)


# --- Captura de pantalla a JPEG ---
def grab_jpeg(sct):
    mon = sct.monitors[0]  # todo el escritorio virtual (todos los monitores)
    shot = sct.grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if img.width > MAX_WIDTH:
        h = int(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, h), Image.BILINEAR)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


# --- Icono generado (para añadir a pantalla de inicio) ---
def make_icon(size):
    from PIL import ImageDraw
    img = Image.new("RGB", (size, size), "#0c1311")
    d = ImageDraw.Draw(img)
    sw = max(2, int(size * 0.085))
    cx = size / 2
    r = size * 0.26
    box = [cx - r, size * 0.38 - r, cx + r, size * 0.38 + r]
    d.arc(box, start=70, end=110 + 360, fill="#2dd4bf", width=sw)
    d.line([cx, size * 0.26, cx, size * 0.5], fill="#2dd4bf", width=sw)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- Clave de acceso ---
def load_key():
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

MANIFEST = json.dumps({
    "name": "PC Remota", "short_name": "PC Remota",
    "start_url": "./", "scope": "./", "display": "fullscreen",
    "orientation": "landscape", "background_color": "#000000", "theme_color": "#0c1311",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
})

PAGE = r"""<!doctype html><html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>PC Remota</title>
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0c1311">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<link rel="apple-touch-icon" href="icon-192.png">
<style>
  :root{--bg:#0c1311;--bar:#151f1c;--border:#26342f;--fg:#e4eeeb;--muted:#8b9d98;
    --accent:#2dd4bf;--on-accent:#062520;--off:#f87171;
    --font:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{background:#000;color:var(--fg);font-family:var(--font);
    display:flex;flex-direction:column;overflow:hidden;touch-action:none;-webkit-user-select:none;user-select:none}
  .bar{display:flex;gap:6px;align-items:center;padding:6px;background:var(--bar);flex:none;flex-wrap:wrap}
  button{font:inherit;font-weight:700;color:var(--fg);background:var(--border);border:0;
    border-radius:10px;padding:9px 11px;cursor:pointer;font-size:13px;white-space:nowrap}
  button.on{background:var(--accent);color:var(--on-accent)}
  button.danger{background:var(--off);color:#2a0a0a}
  button.armed{outline:2px solid var(--accent)}
  .sp{flex:1}
  #stage{flex:1;position:relative;background:#000;overflow:hidden;display:grid;place-items:center}
  #screen{max-width:100%;max-height:100%;display:block;image-rendering:auto}
  #msg{position:absolute;top:8px;left:50%;transform:translateX(-50%);
    background:#000a;padding:6px 12px;border-radius:10px;font-size:12px;color:var(--muted);pointer-events:none}
  .kb{display:none;gap:6px;padding:6px;background:var(--bar);flex:none;flex-wrap:wrap;align-items:center;border-top:1px solid var(--border)}
  .kb.show{display:flex}
  #txt{flex:1;min-width:120px;font:inherit;padding:9px;border-radius:10px;border:1px solid var(--border);
    background:var(--bg);color:var(--fg)}
  .k{padding:9px 10px;background:var(--border);border-radius:9px;font-size:13px}
</style></head><body>

<div class="bar">
  <button id="offb" class="danger">⏻ Apagar monitor</button>
  <button id="onb">Encender</button>
  <span class="sp"></span>
  <button id="rc">Clic der</button>
  <button id="dc">Doble</button>
  <button id="su">▲</button>
  <button id="sd">▼</button>
  <button id="kbt">⌨</button>
</div>

<div id="stage">
  <img id="screen" alt="Pantalla de la PC">
  <div id="msg">Conectando…</div>
</div>

<div class="kb" id="kb">
  <input id="txt" placeholder="Escribe aquí…" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
  <button class="k" data-k="back">⌫</button>
  <button class="k" data-k="enter">⏎</button>
  <button class="k" data-k="tab">Tab</button>
  <button class="k" data-k="esc">Esc</button>
  <button class="k" data-k="left">←</button>
  <button class="k" data-k="up">↑</button>
  <button class="k" data-k="down">↓</button>
  <button class="k" data-k="right">→</button>
  <button class="k" data-k="win">Win</button>
  <button class="k" data-c="a">Todo</button>
  <button class="k" data-c="c">Copiar</button>
  <button class="k" data-c="v">Pegar</button>
</div>

<script>
(function(){
  var K=new URLSearchParams(location.search).get("k")||"";
  var DO=new URLSearchParams(location.search).get("do")||"";
  var $=function(id){return document.getElementById(id)};
  var img=$("screen");

  function send(obj){
    return fetch("/input?k="+encodeURIComponent(K),
      {method:"POST",body:JSON.stringify(obj),keepalive:true}).catch(function(){});
  }
  function act(a){return fetch("/"+a+"?k="+encodeURIComponent(K),{method:"POST"}).catch(function(){})}

  // Vídeo en vivo (MJPEG); si falla, cae a fotos cada 400 ms
  function startStream(){
    img.onerror=function(){img.onerror=null;poll()};
    img.onload=function(){$("msg").style.display="none"};
    img.src="/stream?k="+encodeURIComponent(K);
  }
  function poll(){
    $("msg").style.display="none";
    setInterval(function(){img.src="/shot.jpg?k="+encodeURIComponent(K)+"&t="+Date.now()},400);
  }
  startStream();

  // Mapear un toque sobre la imagen a fracción 0..1 del escritorio (object-fit: contain)
  function frac(e){
    var r=img.getBoundingClientRect();
    var iw=img.naturalWidth||r.width, ih=img.naturalHeight||r.height;
    var scale=Math.min(r.width/iw, r.height/ih);
    var dw=iw*scale, dh=ih*scale;
    var ox=r.left+(r.width-dw)/2, oy=r.top+(r.height-dh)/2;
    var fx=(e.clientX-ox)/dw, fy=(e.clientY-oy)/dh;
    return {x:Math.max(0,Math.min(1,fx)), y:Math.max(0,Math.min(1,fy))};
  }

  var armRight=false, armDouble=false, down=null, dragging=false, lp=null, lastMove=0;
  function setArm(){$("rc").classList.toggle("armed",armRight);$("dc").classList.toggle("armed",armDouble)}
  $("rc").onclick=function(){armRight=!armRight;armDouble=false;setArm()};
  $("dc").onclick=function(){armDouble=!armDouble;armRight=false;setArm()};

  img.addEventListener("pointerdown",function(e){
    e.preventDefault(); img.setPointerCapture(e.pointerId);
    down=frac(e); dragging=false;
    lp=setTimeout(function(){lp=null; send({t:"click",x:down.x,y:down.y,b:"right"}); down=null;},550);
  });
  img.addEventListener("pointermove",function(e){
    if(!down) return;
    var f=frac(e);
    var moved=Math.abs(f.x-down.x)>0.012||Math.abs(f.y-down.y)>0.012;
    if(moved && !dragging){
      if(lp){clearTimeout(lp);lp=null;}
      dragging=true; send({t:"down",x:down.x,y:down.y});
    }
    if(dragging){
      var now=Date.now(); if(now-lastMove<40) return; lastMove=now;
      send({t:"move",x:f.x,y:f.y});
    }
  });
  function endPointer(e){
    if(lp){clearTimeout(lp);lp=null;}
    if(dragging){ send({t:"up",x:frac(e).x,y:frac(e).y}); }
    else if(down){
      send({t:"click",x:down.x,y:down.y,b:armRight?"right":"left",d:armDouble});
      armRight=false; armDouble=false; setArm();
    }
    down=null; dragging=false;
  }
  img.addEventListener("pointerup",endPointer);
  img.addEventListener("pointercancel",function(){if(lp){clearTimeout(lp);lp=null;}down=null;dragging=false;});

  $("offb").onclick=function(){act("off")};
  $("onb").onclick=function(){act("on")};
  $("su").onclick=function(){send({t:"scroll",dy:3})};
  $("sd").onclick=function(){send({t:"scroll",dy:-3})};

  // Teclado
  $("kbt").onclick=function(){
    var kb=$("kb"); kb.classList.toggle("show");
    $("kbt").classList.toggle("on",kb.classList.contains("show"));
    if(kb.classList.contains("show")) $("txt").focus();
  };
  var prev="";
  $("txt").addEventListener("input",function(){
    var v=$("txt").value;
    if(v.length>prev.length){ send({t:"text",s:v.slice(prev.length)}); }
    else if(v.length<prev.length){ for(var i=0;i<prev.length-v.length;i++) send({t:"key",k:"back"}); }
    prev=v;
  });
  Array.prototype.forEach.call(document.querySelectorAll(".k"),function(b){
    b.onclick=function(){
      if(b.dataset.c){ send({t:"combo",c:b.dataset.c}); return; }
      var k=b.dataset.k;
      send({t:"key",k:k});
      if(k==="enter"||k==="esc"){ $("txt").value=""; prev=""; }
      else if(k==="back"){ prev=$("txt").value; }
    };
  });

  if(DO==="off"){ act("off"); $("msg").style.display="block"; $("msg").textContent="Monitor apagado"; }
})();
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
        if path == "/manifest.webmanifest":
            return self._send(200, MANIFEST.encode(), "application/manifest+json")
        if path in ("/icon-192.png", "/icon-512.png"):
            size = 192 if "192" in path else 512
            return self._send(200, make_icon(size), "image/png")
        if path == "/shot.jpg":
            try:
                with mss.mss() as sct:
                    return self._send(200, grab_jpeg(sct), "image/jpeg")
            except Exception as e:
                return self._send(500, str(e).encode())
        if path == "/stream":
            return self._stream()
        self._send(404)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        delay = 1.0 / max(1, FPS)
        try:
            with mss.mss() as sct:
                while True:
                    frame = grab_jpeg(sct)
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                     b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    time.sleep(delay)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self):
        if not self._auth():
            return self._send(403, "Clave incorrecta".encode())
        path = urlparse(self.path).path
        if path == "/off":
            monitor_off(); return self._send(200, b"ok")
        if path == "/on":
            monitor_on(); return self._send(200, b"ok")
        if path == "/input":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(n) or b"{}")
                self._do_input(data)
                return self._send(200, b"ok")
            except Exception as e:
                return self._send(500, str(e).encode())
        self._send(404)

    def _do_input(self, d):
        t = d.get("t")
        if t == "move":
            move_to(d["x"], d["y"])
        elif t == "down":
            move_to(d["x"], d["y"]); button_down("left")
        elif t == "up":
            move_to(d["x"], d["y"]); button_up("left")
        elif t == "click":
            move_to(d["x"], d["y"]); click(d.get("b", "left"), bool(d.get("d")))
        elif t == "scroll":
            scroll(d.get("dy", 0))
        elif t == "key":
            tap_key(d.get("k", ""))
        elif t == "text":
            type_text(d.get("s", ""))
        elif t == "combo":
            combo_ctrl(d.get("c", ""))

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
    url = f"http://{lan_ip()}:{PORT}/?k={KEY}"
    print("Escritorio remoto listo. Abre esto en tu teléfono (misma red wifi):")
    print("  " + url)
    print("Widget 'apagar monitor' (crea un acceso directo a esta dirección):")
    print(f"  {url}&do=off")
    print("Ctrl+C para cerrar.")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
