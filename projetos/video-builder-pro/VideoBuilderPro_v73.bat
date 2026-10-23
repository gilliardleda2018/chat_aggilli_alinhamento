@echo off
REM ============================================================
REM Video Builder Pro v7.3 - Professional Suite
REM Inicializador com Patch v7.3
REM ============================================================

title Video Builder Pro v7.3

echo.
echo ========================================
echo  Video Builder Pro v7.3
echo  Professional Suite
echo ========================================
echo.

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Instale Python 3.10+ de:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Verifica FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [AVISO] FFmpeg nao encontrado!
    echo.
    echo Instale FFmpeg de:
    echo https://ffmpeg.org/download.html
    echo.
    echo Adicione ao PATH e reinicie o app.
    echo.
    pause
)

REM Verifica modulos v7.3
if not exist "modules\__init__.py" (
    echo [ERRO] Modulos v7.3 nao encontrados!
    echo.
    echo Baixe o projeto completo do GitHub:
    echo https://github.com/gilliardleda2018/chat_aggilli_alinhamento
    echo.
    pause
    exit /b 1
)

REM Verifica app principal
if not exist "video_builder_pro_v7.1_suite.py" (
    echo [ERRO] App principal nao encontrado!
    echo.
    echo Baixe o projeto completo do GitHub.
    echo.
    pause
    exit /b 1
)

echo [OK] Python instalado
echo [OK] FFmpeg instalado
echo [OK] Modulos v7.3 encontrados
echo [OK] App principal encontrado
echo.
echo ========================================
echo  Iniciando Video Builder Pro v7.3...
echo ========================================
echo.
echo Novidades v7.3:
echo - 70+ Transicoes GL
echo - 15+ LUTs Avancadas
echo - Auto-Edicao
echo - Legendas AI
echo - Conversor Vertical
echo - GPU Encoding
echo.

REM Inicia app com patch v7.3
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Importa app original
    from video_builder_pro_v7.1_suite import VideoBuilderProV7
    import tkinter as tk

    # Aplica patch v7.3
    from v73_patch import aplicar_patch

    # Cria app
    root = tk.Tk()
    app = VideoBuilderProV7(root)

    # Aplica patch
    patch = aplicar_patch(app)

    print('Patch v7.3 aplicado com sucesso!')
    print('Novas abas disponiveis:')
    print('- Transicoes GL')
    print('- LUTs Avancadas')
    print('- Auto-Edicao')
    print('- Legendas AI')
    print('- Vertical')

    # Inicia loop
    root.mainloop()

except Exception as e:
    print(f'ERRO: {e}')
    import traceback
    traceback.print_exc()
    input('Pressione ENTER para sair...')
"

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar app!
    echo.
    pause
)
