@echo off
chcp 65001 >nul
title Exportar Log - Video Builder Pro v7.0

set "LOG_DIR=%~dp0logs"
set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ======================================================
echo   EXPORTAR LOGS
echo ======================================================
echo.

REM Copiar log principal
if exist "video_builder_v7.log" (
    copy "video_builder_v7.log" "%LOG_DIR%\video_builder_v7_%TIMESTAMP%.log" >nul
    echo [OK] video_builder_v7.log
)

REM Copiar logs antigos
for %%F in (*.log) do (
    if not "%%F"=="video_builder_v7.log" (
        copy "%%F" "%LOG_DIR%\%%~nF_%TIMESTAMP%.log" >nul
        echo [OK] %%F
    )
)

echo.
echo Logs exportados para: %LOG_DIR%
echo.

REM Abrir pasta de logs
explorer "%LOG_DIR%"

pause