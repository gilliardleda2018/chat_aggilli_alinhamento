@echo off
chcp 65001 >nul
title Video Builder Pro v7.2 - Professional Suite

set "SCRIPT_DIR=%~dp0"
set "SCRIPT=%SCRIPT_DIR%video_builder_pro_v7.1_suite.py"
set "LOGFILE=%SCRIPT_DIR%video_builder_v72.log"

echo ======================================================
echo   VIDEO BUILDER PRO v7.2 - PROFESSIONAL SUITE
echo ======================================================
echo.
echo   Novidades v7.2:
echo   - Salvar/Abrir projeto (.vbp JSON)
echo   - Escolher pasta de render (cria se nao existir)
echo   - Transicoes entre clips
echo   - Color grading por clip
echo   - Claude AI integrada
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Baixe em: https://www.python.org/downloads/
    echo IMPORTANTE: Marque "Add Python to PATH" na instalacao!
    pause
    exit /b 1
)
echo [OK] Python
python --version

REM Verificar script principal
if not exist "%SCRIPT%" (
    echo [ERRO] Script nao encontrado: %SCRIPT%
    echo.
    echo Certifique-se que o arquivo video_builder_pro_v7.2_suite.py
    echo esta na mesma pasta que este .bat
    pause
    exit /b 1
)
echo [OK] Script v7.2

REM Verificar dependencias
echo.
echo Verificando dependencias...

python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [ERRO] Tkinter nao encontrado!
    echo Reinstale o Python marcando a opcao "tcl/tk"
    pause
    exit /b 1
)
echo [OK] Tkinter

python -c "import requests" 2>nul
if errorlevel 1 (
    echo [AVISO] Instalando requests...
    pip install requests --quiet
    if errorlevel 1 (echo [ERRO] requests) else (echo [OK] requests)
) else (
    echo [OK] Requests
)

python -c "import PIL" 2>nul
if errorlevel 1 (
    echo [AVISO] Instalando Pillow...
    pip install Pillow --quiet
    if errorlevel 1 (echo [AVISO] Pillow falhou - opcional) else (echo [OK] Pillow)
) else (
    echo [OK] Pillow
)

REM Verificar FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [AVISO] FFmpeg nao encontrado!
    echo Algumas funcoes podem falhar.
    echo Instale com: winget install ffmpeg
) else (
    echo [OK] FFmpeg
)

echo.
echo ======================================================
echo   Iniciando Professional Suite v7.2...
echo   Log: %LOGFILE%
echo ======================================================
echo.

REM Executar com log detalhado
python "%SCRIPT%" 2>> "%LOGFILE%"

if errorlevel 1 (
    echo.
    echo [ERRO] O app fechou com erro.
    echo Verifique o log: %LOGFILE%
    pause
) else (
    echo.
    echo App encerrado normalmente.
    timeout /t 3 >nul
)