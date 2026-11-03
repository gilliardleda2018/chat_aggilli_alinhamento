#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU ENCODER - Video Builder Pro v7.7
Deteccao e uso de GPU para encoding acelerado

Correcoes v7.7 (ver CHANGELOG.md, secao "gpu_encoder.py"):
  - Deteccao por 'ffmpeg -encoders' dava falso positivo: um FFmpeg
    compilado com nvenc lista h264_nvenc mesmo sem placa NVIDIA (reproduzido
    numa maquina sem GPU). Agora cada encoder so e marcado disponivel se um
    encode real de teste (1 frame) funcionar.
  - O parse pegava a coluna de flags ("V....D") em vez do nome do encoder.
  - Nome de GPU AMD/Intel so via 'wmic' (Windows, descontinuado); agora
    tenta lspci no Linux e PowerShell/CIM no Windows.
  - gerar_comando_ffmpeg: '-b:v {crf}M' usava o CRF como bitrate (qualidade
    INVERTIDA: "Rapido" 28 Mbps > "Qualidade" 18 Mbps). Agora usa o controle
    de qualidade constante de cada encoder (-cq / -global_quality / -qp).
  - '-hwaccel_output_format cuda' deixava os quadros na GPU e quebrava os
    filtros de CPU (scale/fps) e o -pix_fmt; removido. '-hwaccel d3d11va'
    so e usado no Windows.
  - Presets AMF usavam '-preset' (opcao inexistente no AMF): agora -quality.
"""

import os
import re
import subprocess
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

        # Encoders compilados no FFmpeg, confirmados por um encode de teste real
        compilados = self._listar_encoders_ffmpeg()
        encoders_disponiveis = [e for e in ("h264_nvenc", "h264_amf", "h264_qsv")
                                if e in compilados and self._testar_encoder(e)]

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
        """Nomes dos encoders de video compilados no FFmpeg (coluna 2)."""
        try:
            result = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                                    capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return []
        encoders = []
        for line in result.stdout.splitlines():
            m = re.match(r"\s*V[\w.]{5}\s+(\S+)", line)
            if m and m.group(1) != "=":
                encoders.append(m.group(1).lower())
        return encoders

    def _testar_encoder(self, encoder: str) -> bool:
        """Encode real de 1 frame: so passa se o hardware/driver existir."""
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
               "-i", "color=black:s=256x256:d=0.1", "-frames:v", "1",
               "-c:v", encoder, "-f", "null", "-"]
        try:
            ok = subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        if not ok:
            self.log(f"Encoder {encoder} compilado no FFmpeg, mas sem hardware/driver: ignorado")
        return ok

    def _nome_gpu_sistema(self, marcas: Tuple[str, ...]) -> Optional[str]:
        """Nome da placa via PowerShell (Windows) ou lspci (Linux)."""
        if os.name == "nt":
            cmds = [["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                    ["wmic", "path", "win32_VideoController", "get", "name"]]
        else:
            cmds = [["lspci"]]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                continue
            for line in r.stdout.splitlines():
                if any(m.lower() in line.lower() for m in marcas) and \
                        (os.name == "nt" or "VGA" in line or "Display" in line or "3D" in line):
                    return line.split(": ", 1)[-1].strip()
        return None

    def _obter_nome_gpu_nvidia(self) -> Optional[str]:
        """Obtem nome da GPU NVIDIA"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    def _obter_nome_gpu_amd(self) -> Optional[str]:
        return self._nome_gpu_sistema(("AMD", "Radeon"))

    def _obter_nome_gpu_intel(self) -> Optional[str]:
        return self._nome_gpu_sistema(("Intel",))

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

        # Decode acelerado: quadros voltam para a memoria do sistema, entao
        # os filtros de CPU (scale/fps) continuam funcionando.
        if gpu.tipo == GPUType.NVIDIA:
            cmd.extend(["-hwaccel", "cuda"])
        elif gpu.tipo == GPUType.INTEL:
            cmd.extend(["-hwaccel", "qsv"])
        elif gpu.tipo == GPUType.AMD and os.name == "nt":
            cmd.extend(["-hwaccel", "d3d11va"])

        # Input
        cmd.extend(["-i", str(entrada)])

        # Video codec + controle de qualidade constante (menor = melhor)
        cmd.extend(["-c:v", preset.codec])
        if "nvenc" in preset.codec:
            cmd.extend(["-preset", preset.preset, "-rc", "vbr", "-cq", preset.crf, "-b:v", "0"])
        elif "qsv" in preset.codec:
            cmd.extend(["-preset", preset.preset, "-global_quality", preset.crf])
        elif "amf" in preset.codec:
            cmd.extend(["-quality", preset.preset, "-rc", "cqp",
                        "-qp_i", preset.crf, "-qp_p", preset.crf])
        else:
            cmd.extend(["-preset", preset.preset, "-crf", preset.crf])

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
