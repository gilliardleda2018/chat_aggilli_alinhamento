#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUBTITLES AI - Video Builder Pro v7.7
Gera legendas automaticas usando Whisper (OpenAI).
Baseado em: github.com/Eyevinn/auto-subtitles

Correcoes v7.7 (ver CHANGELOG.md, secao "subtitles_ai.py"):
  - O SRT era gravado na pasta temporaria (apagada no __del__) com nome fixo
    'legendas.srt': o usuario perdia o arquivo e chamadas seguidas se
    sobrescreviam. Agora aceita 'saida' e, por padrao, grava ao lado do video
    (<video>.srt).
  - O patch chamava queimar_legendas(), que nao existia: criado como alias
    de queimar_legendas_no_video().
  - Caminho do SRT no filtro 'subtitles' com ':' (C:\\...) ou apostrofo quebrava
    o FFmpeg: agora usa escapar_caminho_filtro().
  - Deteccao do Whisper: aceita o CLI 'whisper' OU o modulo python 'whisper'
    (python -m whisper), o que cobre instalacao em venv sem PATH.
  - Falhas do ffmpeg de extracao de audio agora sao reportadas.
"""

import importlib.util
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from ffmpeg_utils import (executar, escapar_caminho_filtro, info_midia,
                              detectar_silencios, inverter_intervalos, duracao)
except ImportError:
    from .ffmpeg_utils import (executar, escapar_caminho_filtro, info_midia,
                               detectar_silencios, inverter_intervalos, duracao)


@dataclass
class SubtitleSegment:
    """Segmento de legenda"""
    inicio: float
    fim: float
    texto: str
    confianca: float = 1.0


class SubtitlesAI:
    """Gerador de legendas com Whisper AI"""

    def __init__(self, log_callback):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_subs_"))
        self._cmd_whisper = self._localizar_whisper()
        self.whisper_disponivel = self._cmd_whisper is not None
        if not self.whisper_disponivel:
            self.log("AVISO: Whisper nao encontrado. Instale com: pip install openai-whisper")

    def _localizar_whisper(self) -> Optional[List[str]]:
        if shutil.which("whisper"):
            return ["whisper"]
        if importlib.util.find_spec("whisper") is not None:
            return [sys.executable, "-m", "whisper"]
        return None

    def _verificar_whisper(self) -> bool:
        """Mantido por compatibilidade (v7.3)."""
        return self._localizar_whisper() is not None

    def gerar_legendas(self, video: Path, idioma: str = "pt", modelo: str = "base",
                       saida_formato: str = "srt", saida: Optional[Path] = None) -> Path:
        """Gera legendas com Whisper. Retorna o caminho FINAL (fora do temp)."""
        if not self.whisper_disponivel:
            raise RuntimeError("Whisper nao instalado. Rode: pip install openai-whisper")
        video = Path(video)
        if not info_midia(video)["tem_audio"]:
            raise RuntimeError(f"'{video.name}' nao tem trilha de audio para transcrever.")
        destino = Path(saida) if saida else video.with_suffix(f".{saida_formato}")

        self.log(f"Gerando legendas (modelo: {modelo}, idioma: {idioma})...")
        trabalho = Path(tempfile.mkdtemp(prefix="job_", dir=self.temp_dir))
        audio_path = trabalho / "audio.wav"
        self._extrair_audio(video, audio_path)

        self.log("Processando com Whisper (pode demorar)...")
        executar([*self._cmd_whisper, str(audio_path), "--model", modelo, "--language", idioma,
                  "--output_format", saida_formato, "--output_dir", str(trabalho)], self.log)

        gerado = trabalho / f"audio.{saida_formato}"
        if not gerado.exists():
            raise RuntimeError(f"Whisper terminou mas nao gerou {gerado.name}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(gerado), destino)
        shutil.rmtree(trabalho, ignore_errors=True)
        self.log(f"Legendas geradas: {destino}")
        return destino

    def gerar_legendas_rapidas(self, video: Path, idioma: str = "pt") -> List[SubtitleSegment]:
        """Marca segmentos de fala (sem transcricao) a partir do silencedetect."""
        self.log("Gerando marcacoes de fala (baseado em silencio)...")
        video = Path(video)
        fala = inverter_intervalos(detectar_silencios(video, -35.0, 0.5), duracao(video))
        return [SubtitleSegment(i, f, f"[Segmento {n + 1}]", 0.8) for n, (i, f) in enumerate(fala)]

    def queimar_legendas_no_video(self, video: Path, legendas_srt: Path, saida: Path,
                                  estilo: Optional[Dict] = None) -> Path:
        """Queima legendas no video (hardcode)"""
        self.log("Queimando legendas no video...")
        estilo = {"fonte": "Arial", "tamanho": 24, "cor": "white", "borda": "black",
                  "largura_borda": 2, "posicao": "bottom", **(estilo or {})}
        alinhamento = {"bottom": 2, "top": 8, "middle": 5}.get(estilo["posicao"], 2)
        force = (f"FontName={estilo['fonte']},FontSize={estilo['tamanho']},"
                 f"PrimaryColour={self._cor_para_ass(estilo['cor'])},"
                 f"OutlineColour={self._cor_para_ass(estilo['borda'])},"
                 f"Outline={estilo['largura_borda']},Alignment={alinhamento}")
        # force_style vai entre aspas no nivel do filtergraph; virgulas protegidas.
        filtro = f"subtitles={escapar_caminho_filtro(legendas_srt)}:force_style='{force}'"
        tem_audio = info_midia(Path(video))["tem_audio"]
        cmd = ["ffmpeg", "-y", "-i", str(video), "-vf", filtro,
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "copy"] if tem_audio else ["-an"]
        executar(cmd + [str(saida)], self.log)
        self.log(f"Legendas queimadas: {saida}")
        return Path(saida)

    # A UI v7.6 chamava este nome (AttributeError). Alias definitivo:
    queimar_legendas = queimar_legendas_no_video

    def adicionar_legendas_soft(self, video: Path, legendas_srt: Path, saida: Path,
                                idioma: str = "por") -> Path:
        """Adiciona legendas como track separada (soft subtitles)"""
        self.log("Adicionando legendas como track separada...")
        executar(["ffmpeg", "-y", "-i", str(video), "-i", str(legendas_srt),
                  "-map", "0", "-map", "1", "-c", "copy", "-c:s", "mov_text",
                  "-metadata:s:s:0", f"language={idioma}", str(saida)], self.log)
        return Path(saida)

    def converter_srt_para_vtt(self, srt: Path, vtt: Path):
        """Converte SRT para VTT"""
        conteudo = Path(srt).read_text(encoding="utf-8-sig")
        conteudo = re.sub(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", r"\1:\2:\3.\4", conteudo)
        Path(vtt).write_text("WEBVTT\n\n" + conteudo, encoding="utf-8")
        self.log(f"Convertido SRT para VTT: {vtt}")

    def _extrair_audio(self, video: Path, saida: Path):
        """Extrai audio do video em WAV mono 16 kHz (formato do Whisper)."""
        executar(["ffmpeg", "-y", "-i", str(video), "-vn", "-acodec", "pcm_s16le",
                  "-ar", "16000", "-ac", "1", str(saida)], self.log)

    def _detectar_segmentos_fala(self, audio: Path) -> List[Tuple[float, float]]:
        """Mantido por compatibilidade (v7.3)."""
        return inverter_intervalos(detectar_silencios(Path(audio), -35.0, 0.5), duracao(Path(audio)))

    def _obter_duracao_audio(self, audio: Path) -> float:
        return duracao(Path(audio))

    def _cor_para_ass(self, cor: str) -> str:
        """Converte cor para formato ASS (&HAABBGGRR)."""
        cores = {"white": "&H00FFFFFF", "black": "&H00000000", "red": "&H000000FF",
                 "green": "&H0000FF00", "blue": "&H00FF0000", "yellow": "&H0000FFFF",
                 "cyan": "&H00FFFF00", "magenta": "&H00FF00FF"}
        return cores.get(cor.lower(), "&H00FFFFFF")

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()
