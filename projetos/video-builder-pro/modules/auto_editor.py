#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO EDITOR - Video Builder Pro v7.3
Remove silencios automaticamente e detecta cortes de cena
Baseado em: github.com/Muzamil4266/Python-auto-video-editor
"""

import subprocess
import tempfile
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class EditDecision:
    """Decisao de edicao automatica"""
    tipo: str  # "remover_silencio", "corte_cena", "manter"
    inicio: float
    fim: float
    duracao: float
    descricao: str = ""


class AutoEditor:
    """Editor automatico com deteccao de silencio e cortes"""

    def __init__(self, log_callback):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_auto_"))

    def detectar_silencios(self, video: Path,
                          threshold_db: float = -35.0,
                          duracao_minima: float = 0.5) -> List[Tuple[float, float]]:
        """Detecta silencios no video usando FFmpeg silencedetect"""

        self.log(f"Detectando silencios (threshold: {threshold_db}dB, min: {duracao_minima}s)...")

        # FFmpeg silencedetect
        cmd = [
            "ffmpeg",
            "-i", str(video),
            "-af", f"silencedetect=noise={threshold_db}dB:d={duracao_minima}",
            "-f", "null",
            "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr

        # Parse output
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

        self.log(f"Encontrados {len(silencios)} silencios")
        return silencios

    def detectar_cortes_cena(self, video: Path,
                             threshold: float = 0.3) -> List[float]:
        """Detecta cortes de cena usando FFmpeg scene detection"""

        self.log(f"Detectando cortes de cena (threshold: {threshold})...")

        # FFmpeg scene detection
        cmd = [
            "ffmpeg",
            "-i", str(video),
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null",
            "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr

        # Parse showinfo output
        cortes = []
        for line in stderr.split('\n'):
            if "pts_time" in line:
                match = re.search(r'pts_time:([\d.]+)', line)
                if match:
                    tempo = float(match.group(1))
                    cortes.append(tempo)

        self.log(f"Encontrados {len(cortes)} cortes de cena")
        return cortes

    def gerar_decisoes_edicao(self, video: Path,
                              remover_silencios: bool = True,
                              threshold_silencio: float = -35.0,
                              duracao_minima_silencio: float = 0.5,
                              detectar_cortes: bool = True,
                              threshold_cena: float = 0.3) -> List[EditDecision]:
        """Gera lista de decisoes de edicao"""

        decisoes = []

        # Obtem duracao total
        duracao_total = self._obter_duracao(video)

        # Detecta silencios
        silencios = []
        if remover_silencios:
            silencios = self.detectar_silencios(
                video, threshold_silencio, duracao_minima_silencio
            )

        # Detecta cortes de cena
        cortes = []
        if detectar_cortes:
            cortes = self.detectar_cortes_cena(video, threshold_cena)

        # Cria decisoes para silencios
        for inicio, fim in silencios:
            decisoes.append(EditDecision(
                tipo="remover_silencio",
                inicio=inicio,
                fim=fim,
                duracao=fim - inicio,
                descricao=f"Remover silencio ({fim - inicio:.1f}s)"
            ))

        # Cria decisoes para cortes de cena
        for tempo in cortes:
            decisoes.append(EditDecision(
                tipo="corte_cena",
                inicio=tempo,
                fim=tempo + 0.1,
                duracao=0.1,
                descricao=f"Corte de cena detectado"
            ))

        # Ordena por tempo
        decisoes.sort(key=lambda d: d.inicio)

        return decisoes

    def aplicar_edicao_automatica(self, video: Path, saida: Path,
                                  decisoes: List[EditDecision],
                                  manter_audio_original: bool = False) -> Path:
        """Aplica decisoes de edicao no video"""

        # Separa silencios para remover
        silencios = [d for d in decisoes if d.tipo == "remover_silencio"]

        if not silencios:
            self.log("Nenhum silencio para remover")
            # Copia video original
            import shutil
            shutil.copy(video, saida)
            return saida

        self.log(f"Removendo {len(silencios)} silencios...")

        # Gera filtro para remover silencios
        # Usa abremoveloud e compand para suavizar
        filtro_audio = self._gerar_filtro_remover_silencios(silencios)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-af", filtro_audio,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(saida)
        ]

        self.log("Aplicando remocao de silencios...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:300]}")
            raise Exception(f"Falha na edicao automatica: {result.stderr[:200]}")

        return saida

    def cortar_em_segmentos(self, video: Path,
                           decisoes: List[EditDecision]) -> List[Path]:
        """Corta video em segmentos baseado nas decisoes"""

        # Obtem duracao total
        duracao_total = self._obter_duracao(video)

        # Cria segmentos (partes entre cortes)
        segmentos = []
        cortes = [0.0] + [d.inicio for d in decisoes if d.tipo == "corte_cena"] + [duracao_total]
        cortes = sorted(set(cortes))

        for i in range(len(cortes) - 1):
            inicio = cortes[i]
            fim = cortes[i + 1]

            if fim - inicio > 0.5:  # Minimo 0.5s
                segmento_path = self.temp_dir / f"segmento_{i:03d}.mp4"

                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video),
                    "-ss", str(inicio),
                    "-t", str(fim - inicio),
                    "-c:v", "copy",
                    "-c:a", "copy",
                    str(segmento_path)
                ]

                subprocess.run(cmd, capture_output=True)
                segmentos.append(segmento_path)

        return segmentos

    def _gerar_filtro_remover_silencios(self, silencios: List[Tuple[float, float]]) -> str:
        """Gera filtro FFmpeg para remover silencios"""

        # Usa compand para atenuar silencios
        # Formato: compand=attacks=0:decays=0:points=-90/-90|0/-90

        # Simplificado: usa abremoveloud para remover partes abaixo do threshold
        filtro = "abremoveloud=tolerance=-30dB:overlap=0.5"

        return filtro

    def remover_silencios_simples(self, video: Path, saida: Path,
                                   threshold_db: float = -35.0,
                                   duracao_minima: float = 0.5) -> Path:
        """Metodo simplificado para remover silencios"""

        self.log("Removendo silencios (metodo simples)...")

        # Detecta silencios primeiro
        silencios = self.detectar_silencios(video, threshold_db, duracao_minima)

        if not silencios:
            self.log("Nenhum silencio encontrado")
            import shutil
            shutil.copy(video, saida)
            return saida

        # Cria segmentos sem silencio
        duracao_total = self._obter_duracao(video)
        segmentos_sem_silencio = []
        inicio_anterior = 0.0

        for inicio, fim in silencios:
            if inicio > inicio_anterior:
                # Segmento com som
                segmento_path = self.temp_dir / f"keep_{len(segmentos_sem_silencio):03d}.mp4"

                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video),
                    "-ss", str(inicio_anterior),
                    "-t", str(inicio - inicio_anterior),
                    "-c:v", "copy",
                    "-c:a", "copy",
                    str(segmento_path)
                ]

                subprocess.run(cmd, capture_output=True)
                segmentos_sem_silencio.append(segmento_path)

            inicio_anterior = fim

        # Ultimo segmento
        if inicio_anterior < duracao_total:
            segmento_path = self.temp_dir / f"keep_{len(segmentos_sem_silencio):03d}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video),
                "-ss", str(inicio_anterior),
                "-t", str(duracao_total - inicio_anterior),
                "-c:v", "copy",
                "-c:a", "copy",
                str(segmento_path)
            ]

            subprocess.run(cmd, capture_output=True)
            segmentos_sem_silencio.append(segmento_path)

        # Concatena segmentos
        if len(segmentos_sem_silencio) > 1:
            lista_concat = self.temp_dir / "concat.txt"
            with open(lista_concat, 'w', encoding='utf-8') as f:
                for seg in segmentos_sem_silencio:
                    f.write(f"file '{seg}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(lista_concat),
                "-c", "copy",
                str(saida)
            ]

            subprocess.run(cmd, capture_output=True)
        else:
            import shutil
            shutil.copy(segmentos_sem_silencio[0], saida)

        self.log(f"Silencios removidos: {saida}")
        return saida

    def _obter_duracao(self, video: Path) -> float:
        """Obtem duracao do video"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", str(video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
