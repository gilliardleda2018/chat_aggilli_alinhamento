@echo off
setlocal
title Video Builder Pro v7.6
python "%~dp0rodar_v76.py"
if errorlevel 1 (
    echo [ERRO] Falha ao iniciar o Video Builder Pro.
    pause
    exit /b 1
)
