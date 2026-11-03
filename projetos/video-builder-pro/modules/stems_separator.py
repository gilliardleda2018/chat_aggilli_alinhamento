#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STEMS SEPARATOR - Video Builder Pro v7.7

O v76_patch.py importava 'stems_separator.StemSeparator', mas o arquivo nao
existia no repositorio: a aba "Audio Stems" nunca funcionou. Implementado na
v7.7 usando o Demucs (Meta) pela linha de comando - 'demucs' no PATH ou
'python -m demucs'. Instalar: pip install demucs

Saidas do Demucs: <saida>/<modelo>/<nome>/{vocals,no_vocals}.wav (2 stems)
ou {drums,bass,other,vocals}.wav (4 stems).
"""

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    from ffmpeg_utils import executar, info_midia
except ImportError:
    from .ffmpeg_utils import executar, info_midia


def localizar_demucs() -> Optional[List[str]]:
    if shutil.which("demucs"):
        return ["demucs"]
    if importlib.util.find_spec("demucs") is not None:
        return [sys.executable, "-m", "demucs"]
    return None


class StemSeparator:
    def __init__(self, log_callback):
        self.log = log_callback
        self._cmd = localizar_demucs()
        self.demucs_disponivel = self._cmd is not None
        if not self.demucs_disponivel:
            self.log("[AVISO] Demucs nao instalado: pip install demucs")

    def _preparar(self, entrada: Path, trabalho: Path) -> Path:
        """Extrai o audio para WAV estereo 44.1 kHz (o Demucs nao le video)."""
        if not info_midia(entrada)["tem_audio"]:
            raise ValueError(f"'{entrada.name}' nao tem audio.")
        wav = trabalho / (entrada.stem.replace(" ", "_") + ".wav")
        executar(["ffmpeg", "-y", "-i", str(entrada), "-vn", "-ac", "2", "-ar", "44100",
                  "-c:a", "pcm_s16le", str(wav)], self.log)
        return wav

    def _rodar(self, wav: Path, trabalho: Path, modelo: str, dois_stems: bool) -> Path:
        if not self.demucs_disponivel:
            raise RuntimeError("Demucs nao instalado: pip install demucs")
        cmd = [*self._cmd, "-n", modelo, "-o", str(trabalho / "sep")]
        if dois_stems:
            cmd += ["--two-stems", "vocals"]
        self.log(f"Demucs ({modelo}) separando - pode demorar varios minutos...")
        executar(cmd + [str(wav)], self.log)
        pasta = trabalho / "sep" / modelo / wav.stem
        if not pasta.is_dir():
            raise RuntimeError(f"Demucs terminou mas nao gerou {pasta}")
        return pasta

    def separar_vocals_instrumental(self, entrada: Path, vocals: Path, instrumental: Path,
                                    modelo: str = "htdemucs") -> List[Path]:
        trabalho = Path(tempfile.mkdtemp(prefix="vbp_stems_"))
        try:
            pasta = self._rodar(self._preparar(Path(entrada), trabalho), trabalho, modelo, True)
            Path(vocals).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pasta / "vocals.wav"), vocals)
            shutil.move(str(pasta / "no_vocals.wav"), instrumental)
            self.log(f"[OK] {Path(vocals).name} + {Path(instrumental).name}")
            return [Path(vocals), Path(instrumental)]
        finally:
            shutil.rmtree(trabalho, ignore_errors=True)

    def separar_stems(self, entrada: Path, pasta_saida: Path, modelo: str = "htdemucs") -> List[Path]:
        trabalho = Path(tempfile.mkdtemp(prefix="vbp_stems_"))
        try:
            pasta = self._rodar(self._preparar(Path(entrada), trabalho), trabalho, modelo, False)
            destino = Path(pasta_saida)
            destino.mkdir(parents=True, exist_ok=True)
            saidas = []
            for wav in sorted(pasta.glob("*.wav")):
                alvo = destino / f"{Path(entrada).stem}_{wav.stem.upper()}.wav"
                shutil.move(str(wav), alvo)
                saidas.append(alvo)
            self.log(f"[OK] {len(saidas)} stems em {destino}")
            return saidas
        finally:
            shutil.rmtree(trabalho, ignore_errors=True)
