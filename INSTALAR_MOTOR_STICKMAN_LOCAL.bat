@echo off
setlocal
cd /d "%~dp0"
title ia-video - Instalacion del motor local
echo.
echo     IA-VIDEO | MOTOR LOCAL ORIGINAL
echo     Instala solo bibliotecas necesarias para Skia + Piper + MP4.
echo     NO instala ComfyUI, no usa cuentas ni consume creditos.
echo.
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv ".venv"
  if errorlevel 1 (
    echo.
    echo ERROR: instala Python 3.12 y ejecuta este instalador otra vez.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto ERROR
".venv\Scripts\python.exe" -m pip install -r "requirements-studio-local.txt"
if errorlevel 1 goto ERROR
".venv\Scripts\python.exe" -c "import skia, numpy, pydantic, piper; print('Motor local listo')"
if errorlevel 1 goto ERROR
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo AVISO: FFmpeg no esta en el PATH. Debes instalarlo para exportar MP4.
)
echo.
echo INSTALACION COMPLETADA. Abre ABRIR_STUDIO_PRO.bat
pause
exit /b 0
:ERROR
echo.
echo ERROR: no se completo la instalacion. Revisa el mensaje anterior.
pause
exit /b 1
