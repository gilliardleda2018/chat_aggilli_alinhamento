# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec do Video Builder Pro (Windows e Linux).
#   cd projetos/video-builder-pro
#   python instalador/gerar_icones.py          (ou --sem-logo para teste)
#   pyinstaller --noconfirm instalador/video_builder_pro.spec
# Resultado: dist/VideoBuilderPro/ (modo "onedir": abre muito mais rapido que o
# "onefile" de 151 MB da v7.6, que se descompactava a cada execucao).
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

RAIZ = Path(SPECPATH).parent
GER = RAIZ / "assets" / "gerados"
EH_WIN = sys.platform.startswith("win")

datas = [(str(p), "estilos") for p in (RAIZ / "estilos").glob("*.json")]
datas += [(str(GER / "icone_256.png"), "assets")]
if (RAIZ / "luts").is_dir():
    datas += [(str(p), "luts") for p in (RAIZ / "luts").glob("*.cube")]
binaries = []
# FFmpeg embutido (o CI baixa para instalador/ffmpeg/ antes do build)
for nome in ("ffmpeg", "ffprobe", "ffplay"):
    exe = RAIZ / "instalador" / "ffmpeg" / (nome + (".exe" if EH_WIN else ""))
    if exe.is_file():
        binaries.append((str(exe), "bin"))
for lic in (RAIZ / "instalador" / "ffmpeg").glob("LICENSE*"):
    datas.append((str(lic), "bin"))

# Modulos carregados dinamicamente pelo patch (__import__) ou por caminho
hiddenimports = ["ffmpeg_utils", "ui_thread", "transitions_gl", "luts_manager", "auto_editor",
                 "subtitles_ai", "vertical_converter", "gpu_encoder", "definitive_downloader",
                 "upscaler", "stems_separator", "face_restore", "auto_suite", "transcricao",
                 "corte_fala", "diretor_ia", "video_builder_pro_v7_suite", "v76_patch", "v78_diretor"]
hiddenimports += collect_submodules("keyring.backends")

# Pacotes opcionais: entram no instalador SE estiverem instalados no build.
# faster-whisper (sem PyTorch, ~250 MB) deixa o Diretor IA funcionando sem
# instalar nada; yt-dlp precisa dos extratores (importados dinamicamente).
for pkg in ("yt_dlp", "faster_whisper", "ctranslate2", "tokenizers", "av", "onnxruntime", "huggingface_hub"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        print(f"[spec] {pkg} nao instalado: fora do pacote")

a = Analysis([str(RAIZ / "rodar_v78.py")], pathex=[str(RAIZ), str(RAIZ / "modules")],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["torch", "torchvision", "torchaudio", "tensorflow", "matplotlib", "moviepy", "pydub"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="VideoBuilderPro",
          console=False, icon=str(GER / "icone.ico") if EH_WIN else None,
          version=str(RAIZ / "instalador" / "versao_windows.txt") if EH_WIN and
          (RAIZ / "instalador" / "versao_windows.txt").exists() else None)
coll = COLLECT(exe, a.binaries, a.datas, name="VideoBuilderPro")
