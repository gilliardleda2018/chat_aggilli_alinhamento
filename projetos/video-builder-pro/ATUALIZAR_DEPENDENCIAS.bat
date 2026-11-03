@echo off
chcp 65001 >nul
title Atualizar Dependencias - Video Builder Pro v7.7

echo ======================================================
echo   ATUALIZAR DEPENDENCIAS (v7.7)
echo ======================================================
echo.
cd /d "%~dp0"

echo Atualizando pip...
python -m pip install --upgrade pip --quiet

echo.
echo Instalando/atualizando dependencias principais (requirements.txt)...
python -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias. Veja a mensagem acima.
    pause
    exit /b 1
)
echo [OK] requests, yt-dlp, keyring, numpy

echo.
echo Modulos de IA (Whisper, Demucs, GFPGAN...) sao opcionais e pesados:
echo   python -m pip install -r requirements-ia.txt
echo.
where ffmpeg >nul 2>nul && (echo [OK] ffmpeg no PATH) || (echo [ERRO] ffmpeg nao encontrado: winget install Gyan.FFmpeg)
echo.
echo ======================================================
echo   ATUALIZACAO CONCLUIDA!
echo ======================================================
echo.
pause
