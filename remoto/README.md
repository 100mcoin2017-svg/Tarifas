# Pantalla remota (Windows)

Controla el monitor de tu PC desde el teléfono: **apagar pantalla**, **encender** y
**ver la pantalla** casi en vivo (una captura por segundo).

## Uso

1. Instala Python 3 en la PC y luego, en una terminal:
   ```
   pip install mss
   python pantalla_remota.py
   ```
2. Se imprime una dirección como `http://192.168.1.20:8765/?k=CLAVE`. Ábrela en el
   navegador del teléfono (conectado a la **misma wifi**) y guárdala en favoritos.
3. Si Windows pregunta por el firewall, permite el acceso en **redes privadas**.

## Seguridad

- La clave se guarda en `clave.txt` (no se sube a git) y es necesaria en la dirección.
- Solo es accesible en tu red local; **no abras el puerto a internet**. Para usarlo fuera
  de casa, usa una VPN (por ejemplo Tailscale) en lugar de exponer el puerto.
- Quien tenga el enlace puede ver tu pantalla: no lo compartas.
