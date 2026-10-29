@echo off
chcp 65001 >nul
title PC Remota
cd /d "%~dp0"
echo ============================================
echo    PC REMOTA
echo ============================================
echo.
echo Instalando lo necesario (solo tarda la primera vez)...
python -m pip install --quiet --disable-pip-version-check mss pillow
if errorlevel 1 (
  echo.
  echo [X] No se pudo usar Python.
  echo     Instala Python desde https://www.python.org/downloads/
  echo     y marca la casilla "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)
echo.
echo Listo. Abre en el telefono la direccion que aparece abajo.
echo (El telefono debe estar en la misma wifi que esta PC.)
echo Para cerrar el programa, cierra esta ventana.
echo.
python pantalla_remota.py
echo.
pause
