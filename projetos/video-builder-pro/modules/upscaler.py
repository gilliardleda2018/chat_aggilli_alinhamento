#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UPSCALER - Video Builder Pro v7.7

O v76_patch.py importava 'upscaler.VideoUpscaler', mas o arquivo nao existia
no repositorio: a aba "Upscale AI" sempre mostrava "Real-ESRGAN nao
encontrado" e os botoes falhavam. Implementado na v7.7.

Backends (escolhidos automaticamente):
  1. Real-ESRGAN ncnn-vulkan (IA, GPU via Vulkan - NVIDIA/AMD/Intel):
     binario 'realesrgan-ncnn-vulkan' no PATH ou em <app>/bin/.
     Download: github.com/xinntao/Real-ESRGAN/releases (pacote ncnn-vulkan
     com a pasta 'models').
  2. Classico (sem IA): FFmpeg lanczos + unsharp. Usado quando o binario nao
     existe ou quando "Usar GPU" esta desmarcado (o ncnn-vulkan precisa de
     GPU Vulkan).

O audio original e mantido sem reencode.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

try:
    from ffmpeg_utils import executar, executar_com_progresso, info_midia, pasta_app
except ImportError:
    from .ffmpeg_utils import executar, executar_com_progresso, info_midia, pasta_app

# escala pedida -> (modelo, fator do modelo, fator final)
MODOS = {
    "2x": ("realesrgan-x4plus", 4, 2),
    "4x": ("realesrgan-x4plus", 4, 4),
    "anime": ("realesr-animevideov3", 4, 4),
}


def localizar_realesrgan() -> Optional[str]:
    for nome in ("realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"):
        p = shutil.which(nome)
        if p:
            return p
        local = pasta_app() / "bin" / nome
        if local.is_file():
            return str(local)
    return None


class VideoUpscaler:
    def __init__(self, log_callback):
        self.log = log_callback
        self.binario = localizar_realesrgan()
        self.realesrgan_disponivel = self.binario is not None
        if self.realesrgan_disponivel:
            self.log(f"[OK] Real-ESRGAN: {self.binario}")
        else:
            self.log("[AVISO] realesrgan-ncnn-vulkan nao encontrado: upscale usara o modo classico (FFmpeg).")

    def upscale(self, video: Path, saida: Path, escala: str = "2x", usar_gpu: bool = True) -> Path:
        if escala not in MODOS:
            raise ValueError(f"Escala invalida: {escala} (use {', '.join(MODOS)})")
        info = info_midia(Path(video))
        if not info["tem_video"]:
            raise ValueError("Arquivo sem video.")
        _, _, fator = MODOS[escala]
        w, h = info["width"] * fator, info["height"] * fator
        if self.realesrgan_disponivel and usar_gpu:
            return self._upscale_ia(Path(video), Path(saida), escala, info, w, h)
        motivo = "GPU desmarcada" if self.realesrgan_disponivel else "Real-ESRGAN nao instalado"
        self.log(f"Upscale classico (lanczos) - {motivo}.")
        return self._upscale_classico(Path(video), Path(saida), info, w, h)

    def _upscale_classico(self, video: Path, saida: Path, info: dict, w: int, h: int) -> Path:
        cmd = ["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0",
               "-vf", f"scale={w}:{h}:flags=lanczos,unsharp=5:5:0.6",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        cmd += ["-map", "0:a:0", "-c:a", "copy"] if info["tem_audio"] else []
        executar_com_progresso(cmd + [str(saida)], self.log, info["duracao"])
        return saida

    def _upscale_ia(self, video: Path, saida: Path, escala: str, info: dict, w: int, h: int) -> Path:
        modelo, fator_modelo, fator = MODOS[escala]
        trabalho = Path(tempfile.mkdtemp(prefix="vbp_upscale_"))
        try:
            entrada, saida_frames = trabalho / "in", trabalho / "out"
            entrada.mkdir()
            saida_frames.mkdir()
            n_est = int(info["duracao"] * (info["fps"] or 25))
            self.log(f"Extraindo ~{n_est} quadros (precisa de espaco em disco temporario)...")
            executar(["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0", "-vsync", "0",
                      str(entrada / "%08d.png")], self.log)
            self.log(f"Real-ESRGAN ({modelo}) em {n_est} quadros - pode demorar...")
            executar([self.binario, "-i", str(entrada), "-o", str(saida_frames), "-n", modelo,
                      "-s", str(fator_modelo), "-f", "png"], self.log)
            fps = info["fps"] or 25
            cmd = ["ffmpeg", "-y", "-framerate", f"{fps}", "-i", str(saida_frames / "%08d.png"),
                   "-i", str(video), "-map", "0:v:0"]
            vf = [f"scale={w}:{h}:flags=lanczos"] if fator != fator_modelo else []
            cmd += (["-vf", ",".join(vf)] if vf else []) + [
                "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p"]
            cmd += ["-map", "1:a:0", "-c:a", "copy", "-shortest"] if info["tem_audio"] else []
            executar(cmd + [str(saida)], self.log)
            self.log(f"[OK] Upscale {escala}: {w}x{h}")
            return saida
        finally:
            shutil.rmtree(trabalho, ignore_errors=True)
