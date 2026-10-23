@echo off
chcp 65001 >nul
title Atualizar Dependencias - Video Builder Pro v7.0

echo ======================================================
echo   ATUALIZAR DEPENDENCIAS
echo ======================================================
echo.

echo Atualizando pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip atualizado

echo.
echo Atualizando pacotes...

pip install --upgrade Pillow --quiet
echo [OK] Pillow

pip install --upgrade requests --quiet
echo [OK] requests

pip install --upgrade numpy --quiet
echo [OK] numpy

echo.
echo ======================================================
echo   ATUALIZACAO CONCLUIDA!
echo ======================================================
echo.
pause