#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUBTITLES AI - Video Builder Pro v7.3
Gera legendas automaticas usando Whisper (OpenAI)
Baseado em: github.com/Eyevinn/auto-subtitles
"""

import subprocess
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re


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
        self.whisper_disponivel = self._verificar_whisper()

    def _verificar_whisper(self) -> bool:
        """Verifica se Whisper esta instalado"""
        try:
            result = subprocess.run(
                ["whisper", "--help"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            self.log("AVISO: Whisper nao encontrado. Instale com: pip install openai-whisper")
            return False

    def gerar_legendas(self, video: Path,
                       idioma: str = "pt",
                       modelo: str = "base",
                       saida_formato: str = "srt") -> Path:
        """Gera legendas para o video usando Whisper"""

        if not self.whisper_disponivel:
            raise Exception("Whisper nao instalado. Rode: pip install openai-whisper")

        self.log(f"Gerando legendas (modelo: {modelo}, idioma: {idioma})...")

        # Extrai audio do video
        audio_path = self.temp_dir / "audio.wav"
        self._extrair_audio(video, audio_path)

        # Executa Whisper
        saida_srt = self.temp_dir / f"legendas.{saida_formato}"

        cmd = [
            "whisper",
            str(audio_path),
            "--model", modelo,
            "--language", idioma,
            "--output_format", saida_formato,
            "--output_dir", str(self.temp_dir)
        ]

        self.log("Processando com Whisper (pode demorar)...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro no Whisper: {result.stderr[:300]}")
            raise Exception(f"Falha ao gerar legendas: {result.stderr[:200]}")

        # Whisper gera arquivo com nome do audio
        arquivo_gerado = self.temp_dir / f"audio.{saida_formato}"
        if arquivo_gerado.exists():
            arquivo_gerado.rename(saida_srt)

        self.log(f"Legendas geradas: {saida_srt}")
        return saida_srt

    def gerar_legendas_rapidas(self, video: Path,
                               idioma: str = "pt") -> List[SubtitleSegment]:
        """Gera legendas rapidamente usando VAD + deteccao de silencio"""

        self.log("Gerando legendas rapidas (baseado em VAD)...")

        # Extrai audio
        audio_path = self.temp_dir / "audio.wav"
        self._extrair_audio(video, audio_path)

        # Detecta segmentos de fala usando silencedetect invertido
        segmentos = self._detectar_segmentos_fala(audio_path)

        # Converte para SubtitleSegment
        legendas = []
        for i, (inicio, fim) in enumerate(segmentos):
            legendas.append(SubtitleSegment(
                inicio=inicio,
                fim=fim,
                texto=f"[Segmento {i+1}]",
                confianca=0.8
            ))

        return legendas

    def queimar_legendas_no_video(self, video: Path, legendas_srt: Path,
                                   saida: Path,
                                   estilo: Dict = None) -> Path:
        """Queima legendas no video (hardcode)"""

        self.log("Queimando legendas no video...")

        # Estilo padrao
        if estilo is None:
            estilo = {
                "fonte": "Arial",
                "tamanho": 24,
                "cor": "white",
                "borda": "black",
                "largura_borda": 2,
                "posicao": "bottom"
            }

        # Constroi filtro de legendas
        filtro = (
            f"subtitles='{legendas_srt}':"
            f"force_style='FontName={estilo['fonte']},"
            f"FontSize={estilo['tamanho']},"
            f"PrimaryColour={self._cor_para_ass(estilo['cor'])},"
            f"OutlineColour={self._cor_para_ass(estilo['borda'])},"
            f"Outline={estilo['largura_borda']},"
            f"Alignment=2'"  # 2 = bottom center
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "copy",
            str(saida)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:300]}")
            raise Exception(f"Falha ao queimar legendas: {result.stderr[:200]}")

        return saida

    def adicionar_legendas_soft(self, video: Path, legendas_srt: Path,
                                 saida: Path) -> Path:
        """Adiciona legendas como track separada (soft subtitles)"""

        self.log("Adicionando legendas como track separada...")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(legendas_srt),
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=por",
            str(saida)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:300]}")
            raise Exception(f"Falha ao adicionar legendas: {result.stderr[:200]}")

        return saida

    def converter_srt_para_vtt(self, srt: Path, vtt: Path):
        """Converte SRT para VTT"""

        with open(srt, 'r', encoding='utf-8') as f:
            conteudo = f.read()

        # Substitui virgulas por pontos nos timestamps
        conteudo = re.sub(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', r'\1:\2:\3.\4', conteudo)

        # Adiciona header VTT
        conteudo_vtt = "WEBVTT\n\n" + conteudo

        with open(vtt, 'w', encoding='utf-8') as f:
            f.write(conteudo_vtt)

        self.log(f"Convertido SRT para VTT: {vtt}")

    def _extrair_audio(self, video: Path, saida: Path):
        """Extrai audio do video em WAV"""

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(saida)
        ]

        subprocess.run(cmd, capture_output=True)

    def _detectar_segmentos_fala(self, audio: Path) -> List[Tuple[float, float]]:
        """Detecta segmentos de fala usando silencedetect"""

        # Detecta silencios
        cmd = [
            "ffmpeg",
            "-i", str(audio),
            "-af", "silencedetect=noise=-35dB:d=0.5",
            "-f", "null",
            "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr

        # Parse silencios
        silencios = []
        inicio_silencio = None

        for line in stderr.split('\n'):
            if "silence_start" in line:
                match = re.search(r'silence_start:\s*([\d.]+)', line)
                if match:
                    inicio_silencio = float(match.group(1))

            elif "silence_end" in line:
                match = re.search(r'silence_end:\s*([\d.]+)', line)
                if match and inicio_silencio is not None:
                    fim_silencio = float(match.group(1))
                    silencios.append((inicio_silencio, fim_silencio))
                    inicio_silencio = None

        # Inverte para obter segmentos de fala
        duracao_total = self._obter_duracao_audio(audio)
        segmentos_fala = []
        inicio_anterior = 0.0

        for inicio, fim in silencios:
            if inicio > inicio_anterior:
                segmentos_fala.append((inicio_anterior, inicio))
            inicio_anterior = fim

        # Ultimo segmento
        if inicio_anterior < duracao_total:
            segmentos_fala.append((inicio_anterior, duracao_total))

        return segmentos_fala

    def _obter_duracao_audio(self, audio: Path) -> float:
        """Obtem duracao do audio"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", str(audio)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    def _cor_para_ass(self, cor: str) -> str:
        """Converte cor para formato ASS"""
        cores = {
            "white": "&H00FFFFFF",
            "black": "&H00000000",
            "red": "&H000000FF",
            "green": "&H0000FF00",
            "blue": "&H00FF0000",
            "yellow": "&H0000FFFF",
            "cyan": "&H00FFFF00",
            "magenta": "&H00FF00FF",
        }
        return cores.get(cor.lower(), "&H00FFFFFF")

    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
