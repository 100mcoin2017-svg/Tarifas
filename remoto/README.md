# PC Remota (Windows)

Convierte tu teléfono en un control remoto de tu PC con Windows, por wifi:

- **Ver** la pantalla de la PC en vivo.
- **Controlar**: mover el ratón, clic izquierdo, clic derecho, doble clic, arrastrar, rueda.
- **Escribir** con el teclado del teléfono (incluye ⏎, ⌫, Tab, Esc, flechas, Win, Copiar/Pegar/Todo).
- **Apagar y encender el monitor** de la PC. El "widget" es un acceso directo que lo apaga de un toque.

## La forma fácil (un clic)

Con Python ya instalado, solo haz **doble clic en `INICIAR PC REMOTA.bat`**.
Instala lo necesario la primera vez y arranca el programa. No hace falta escribir comandos.

## La forma manual

En la PC con Windows, con Python 3 instalado:

```
pip install mss pillow
python pantalla_remota.py
```

El programa imprime dos direcciones:

- La **app** (ver y controlar): `http://192.168.x.x:8765/?k=CLAVE`
- El **widget apagar monitor**: la misma dirección con `&do=off` al final.

Si Windows pregunta por el firewall, permite el acceso en **redes privadas**.

## Cómo usarlo en el teléfono

1. Abre la dirección de la **app** en el navegador (misma wifi).
2. Para que se vea como una app a pantalla completa: menú del navegador → **Añadir a pantalla de inicio**.
3. Controles:
   - **Tocar** = mover y clic izquierdo donde tocaste.
   - **Mantener pulsado** = clic derecho. También está el botón **Clic der** (arma el siguiente toque).
   - **Doble** = arma un doble clic para el siguiente toque.
   - **Arrastrar** el dedo = arrastrar con el botón izquierdo.
   - **▲ / ▼** = rueda del ratón.
   - **⌨** = abre el teclado para escribir.

## El "widget" para apagar el monitor

Crea en la pantalla de inicio un acceso directo a la dirección que termina en `&do=off`.
Al abrirlo, apaga el monitor de la PC de inmediato (la PC sigue encendida).
En Chrome: abre esa dirección → menú → **Añadir a pantalla de inicio**. Ponle de nombre "Apagar PC".

## Ajustes (opcionales)

Variables de entorno antes de ejecutar:

- `ANCHO` (por defecto 1100): ancho del vídeo; más = más nítido pero más lento.
- `CALIDAD` (45): calidad JPEG 1–95.
- `FPS` (12): cuadros por segundo del vídeo.
- `PORT` (8765): puerto.

## Seguridad

- La clave se guarda en `clave.txt` (no se sube a git) y hace falta en la dirección.
- Da **control total** de la PC a quien tenga el enlace: no lo compartas.
- Úsalo solo en tu red local. **No abras el puerto a internet.** Para usarlo fuera de
  casa, usa una VPN como Tailscale.
- No funciona la pantalla de bloqueo de Windows ni Ctrl+Alt+Supr (el sistema lo impide
  por seguridad).
