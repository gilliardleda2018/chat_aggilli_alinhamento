@echo off
chcp 65001 >nul
title Video Builder Pro v7.1 - Professional Suite

set "SCRIPT_DIR=%~dp0"
set "SCRIPT=%SCRIPT_DIR%video_builder_pro_v7.1_suite.py"
set "LOGFILE=%SCRIPT_DIR%video_builder_v71.log"

echo ======================================================
echo   VIDEO BUILDER PRO v7.1 - PROFESSIONAL SUITE
echo ======================================================
echo.
echo   Novidades v7.1:
echo   - Transicoes entre clips (CROSSFADE, FADE, ZOOM, etc)
echo   - Color grading por clip (CINEMATIC, ORANGE_TEAL, etc)
echo   - Render com filtros aplicados
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    pause
    exit /b 1
)
echo [OK] Python

if not exist "%SCRIPT%" (
    echo [ERRO] Script nao encontrado: %SCRIPT%
    pause
    exit /b 1
)
echo [OK] Script v7.1 (65 KB)

python -c "import tkinter" 2>nul
if errorlevel 1 (echo [ERRO] Tkinter & pause & exit /b 1)
echo [OK] Tkinter

echo.
echo Iniciando v7.1...
echo Log: %LOGFILE%
echo.

python "%SCRIPT%" 2>> "%LOGFILE%"

if errorlevel 1 (
    echo.
    echo [ERRO] App fechou com erro!
    echo Verifique: %LOGFILE%
    pause
) else (
    echo.
    echo App encerrado normalmente.
    timeout /t 3 >nul
)