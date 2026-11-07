@echo off
setlocal
cd /d "%~dp0"
title ia-video - Studio Pro experimental
echo.
echo    IA VIDEO - STUDIO PRO (OPCIONAL)
echo    La aplicacion Stickman IA original NO se modifica.
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m studio_pro gui
    goto FIN
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -m studio_pro gui
    goto FIN
)
python -m studio_pro gui
:FIN
if errorlevel 1 (
    echo.
    echo ERROR: La interfaz no pudo arrancar.
    echo Comprueba Python y vuelve a intentar.
    pause
)
