#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU ENCODER - Video Builder Pro v7.3
Deteccao e uso de GPU para encoding acelerado
"""

import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class GPUType(Enum):
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    APPLE = "apple"
    CPU = "cpu"


@dataclass
class GPUInfo:
    """Informacao de GPU detectada"""
    tipo: GPUType
    nome: str
    encoder: str
    disponivel: bool


@dataclass
class EncoderPreset:
    """Preset de encoding"""
    nome: str
    codec: str
    preset: str
    crf: str
    descricao: str


class GPUEncoder:
    """Gerenciador de encoding GPU"""

    # Presets de encoding
    PRESETS = {
        GPUType.NVIDIA: [
            EncoderPreset("NVENC H264 Rapido", "h264_nvenc", "p1", "28", "Encoding rapido com GPU NVIDIA"),
            EncoderPreset("NVENC H264 Balanceado", "h264_nvenc", "p4", "23", "Equilibrio qualidade/velocidade"),
            EncoderPreset("NVENC H264 Qualidade", "h264_nvenc", "p7", "18", "Alta qualidade com GPU"),
            EncoderPreset("NVENC HEVC Rapido", "hevc_nvenc", "p1", "30", "HEVC rapido (menor arquivo)"),
            EncoderPreset("NVENC HEVC Qualidade", "hevc_nvenc", "p7", "22", "HEVC alta qualidade"),
        ],
        GPUType.AMD: [
            EncoderPreset("AMF H264 Rapido", "h264_amf", "speed", "28", "Encoding rapido com GPU AMD"),
            EncoderPreset("AMF H264 Qualidade", "h264_amf", "quality", "20", "Alta qualidade com AMD"),
            EncoderPreset("AMF HEVC", "hevc_amf", "balanced", "25", "HEVC com AMD"),
        ],
        GPUType.INTEL: [
            EncoderPreset("QSV H264 Rapido", "h264_qsv", "veryfast", "28", "QuickSync rapido"),
            EncoderPreset("QSV H264 Qualidade", "h264_qsv", "slow", "20", "QuickSync qualidade"),
            EncoderPreset("QSV HEVC", "hevc_qsv", "medium", "25", "HEVC QuickSync"),
        ],
        GPUType.CPU: [
            EncoderPreset("x264 Ultrarapido", "libx264", "ultrafast", "28", "CPU ultrarapido (rascunho)"),
            EncoderPreset("x264 Rapido", "libx264", "fast", "23", "CPU rapido"),
            EncoderPreset("x264 Balanceado", "libx264", "medium", "20", "CPU balanceado"),
            EncoderPreset("x264 Qualidade", "libx264", "slow", "18", "CPU alta qualidade"),
            EncoderPreset("x264 Master", "libx264", "veryslow", "15", "CPU master (maxima qualidade)"),
            EncoderPreset("x265 Rapido", "libx265", "fast", "26", "HEVC rapido"),
            EncoderPreset("x265 Qualidade", "libx265", "slow", "20", "HEVC qualidade"),
        ]
    }

    def __init__(self, log_callback):
        self.log = log_callback
        self.gpus_detectadas: List[GPUInfo] = []
        self._detectar_gpus()

    def _detectar_gpus(self):
        """Detecta GPUs disponiveis"""

        self.log("Detectando GPUs...")

        # Verifica encoders disponiveis no FFmpeg
        encoders_disponiveis = self._listar_encoders_ffmpeg()

        # NVIDIA
        if any("nvenc" in e for e in encoders_disponiveis):
            nome = self._obter_nome_gpu_nvidia()
            self.gpus_detectadas.append(GPUInfo(
                tipo=GPUType.NVIDIA,
                nome=nome or "NVIDIA GPU",
                encoder="h264_nvenc",
                disponivel=True
            ))
            self.log(f"GPU NVIDIA detectada: {nome}")

        # AMD
        if any("amf" in e for e in encoders_disponiveis):
            nome = self._obter_nome_gpu_amd()
            self.gpus_detectadas.append(GPUInfo(
                tipo=GPUType.AMD,
                nome=nome or "AMD GPU",
                encoder="h264_amf",
                disponivel=True
            ))
            self.log(f"GPU AMD detectada: {nome}")

        # Intel QuickSync
        if any("qsv" in e for e in encoders_disponiveis):
            nome = self._obter_nome_gpu_intel()
            self.gpus_detectadas.append(GPUInfo(
                tipo=GPUType.INTEL,
                nome=nome or "Intel QuickSync",
                encoder="h264_qsv",
                disponivel=True
            ))
            self.log(f"GPU Intel detectada: {nome}")

        # Sempre adiciona CPU como fallback
        self.gpus_detectadas.append(GPUInfo(
            tipo=GPUType.CPU,
            nome="CPU (software)",
            encoder="libx264",
            disponivel=True
        ))

        self.log(f"Total: {len(self.gpus_detectadas)} dispositivos de encoding")

    def _listar_encoders_ffmpeg(self) -> List[str]:
        """Lista encoders disponiveis no FFmpeg"""
        cmd = ["ffmpeg", "-encoders"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        encoders = []
        for line in result.stdout.split('\n'):
            if "h264" in line.lower() or "hevc" in line.lower() or "h265" in line.lower():
                match = re.search(r'\s+(\w+)\s+', line)
                if match:
                    encoders.append(match.group(1).lower())

        return encoders

    def _obter_nome_gpu_nvidia(self) -> Optional[str]:
        """Obtem nome da GPU NVIDIA"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None

    def _obter_nome_gpu_amd(self) -> Optional[str]:
        """Obtem nome da GPU AMD"""
        try:
            # Windows: wmic
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if "AMD" in line or "Radeon" in line:
                        return line.strip()
        except:
            pass
        return None

    def _obter_nome_gpu_intel(self) -> Optional[str]:
        """Obtem nome da GPU Intel"""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if "Intel" in line:
                        return line.strip()
        except:
            pass
        return None

    def obter_melhor_gpu(self) -> GPUInfo:
        """Retorna melhor GPU disponivel"""
        # Prioridade: NVIDIA > AMD > Intel > CPU
        prioridade = [GPUType.NVIDIA, GPUType.AMD, GPUType.INTEL, GPUType.CPU]

        for tipo in prioridade:
            for gpu in self.gpus_detectadas:
                if gpu.tipo == tipo and gpu.disponivel:
                    return gpu

        # Fallback
        return self.gpus_detectadas[-1] if self.gpus_detectadas else GPUInfo(
            tipo=GPUType.CPU, nome="CPU", encoder="libx264", disponivel=True
        )

    def obter_presets(self, gpu_tipo: Optional[GPUType] = None) -> List[EncoderPreset]:
        """Obtem presets para GPU especifica"""
        if gpu_tipo is None:
            gpu_tipo = self.obter_melhor_gpu().tipo

        return self.PRESETS.get(gpu_tipo, self.PRESETS[GPUType.CPU])

    def gerar_comando_ffmpeg(self, gpu: GPUInfo, preset: EncoderPreset,
                            entrada: Path, saida: Path,
                            resolucao: Optional[Tuple[int, int]] = None,
                            fps: Optional[int] = None,
                            bitrate_audio: str = "192k") -> List[str]:
        """Gera comando FFmpeg otimizado para GPU"""

        cmd = ["ffmpeg", "-y"]

        # Hardware acceleration para decode (se disponivel)
        if gpu.tipo == GPUType.NVIDIA:
            cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
        elif gpu.tipo == GPUType.INTEL:
            cmd.extend(["-hwaccel", "qsv"])
        elif gpu.tipo == GPUType.AMD:
            cmd.extend(["-hwaccel", "d3d11va"])

        # Input
        cmd.extend(["-i", str(entrada)])

        # Video codec
        cmd.extend(["-c:v", preset.codec])
        cmd.extend(["-preset", preset.preset])

        # CRF ou bitrate
        if "nvenc" in preset.codec or "qsv" in preset.codec or "amf" in preset.codec:
            # GPU usa bitrate ou qp em vez de crf
            cmd.extend(["-b:v", f"{preset.crf}M"])
        else:
            cmd.extend(["-crf", preset.crf])

        # Filtros
        filtros = []
        if resolucao:
            filtros.append(f"scale={resolucao[0]}:{resolucao[1]}")
        if fps:
            filtros.append(f"fps={fps}")

        if filtros:
            cmd.extend(["-vf", ",".join(filtros)])

        # Audio
        cmd.extend(["-c:a", "aac", "-b:a", bitrate_audio])

        # Output
        cmd.extend(["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
        cmd.append(str(saida))

        return cmd

    def estimar_velocidade(self, gpu_tipo: GPUType) -> str:
        """Estima velocidade relativa de encoding"""
        velocidades = {
            GPUType.NVIDIA: "5-10x mais rapido que CPU",
            GPUType.AMD: "3-7x mais rapido que CPU",
            GPUType.INTEL: "2-5x mais rapido que CPU",
            GPUType.CPU: "Velocidade base"
        }
        return velocidades.get(gpu_tipo, "Desconhecido")
