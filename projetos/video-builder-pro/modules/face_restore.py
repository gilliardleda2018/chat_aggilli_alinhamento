#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FACE RESTORE - Video Builder Pro v7.7

O v76_patch.py importava 'face_restore.FaceRestorer', mas o arquivo nao
existia no repositorio: a aba "Face Restore" nunca funcionou. Implementado na
v7.7 com GFPGAN (pip install gfpgan). Os quadros sao decodificados e
codificados pelo FFmpeg via pipe (sem gravar PNGs em disco) e o audio
original e mantido.

Modelo: GFPGANv1.4.pth, procurado em ~/.video_builder_pro/models/; se nao
existir, o proprio GFPGAN baixa da release oficial na 1a execucao.

Compatibilidade: o basicsr (dependencia do gfpgan) quebra com torchvision
>= 0.17 ("No module named 'torchvision.transforms.functional_tensor'").
O erro e detectado e a mensagem explica a correcao.
"""

import importlib.util
import subprocess
from pathlib import Path

try:
    from ffmpeg_utils import diretorio_config, info_midia, FFmpegErro
except ImportError:
    from .ffmpeg_utils import diretorio_config, info_midia, FFmpegErro

URL_MODELO = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"


class FaceRestorer:
    def __init__(self, log_callback):
        self.log = log_callback
        try:
            self.gfpgan_disponivel = importlib.util.find_spec("gfpgan") is not None
        except (ValueError, ImportError):  # modulo ja carregado sem __spec__
            self.gfpgan_disponivel = "gfpgan" in __import__("sys").modules
        self._restaurador = None
        if not self.gfpgan_disponivel:
            self.log("[AVISO] GFPGAN nao instalado: pip install gfpgan")

    def _carregar(self, usar_gpu: bool = True):
        if self._restaurador is not None:
            return self._restaurador
        try:
            from gfpgan import GFPGANer
        except ModuleNotFoundError as e:
            if "functional_tensor" in str(e):
                raise RuntimeError(
                    "basicsr incompativel com o torchvision instalado. Corrija com:\n"
                    "  pip install 'torchvision<0.17'  (ou o fork: pip install basicsr-fixed)") from e
            raise RuntimeError("GFPGAN nao instalado: pip install gfpgan") from e
        local = diretorio_config() / "models" / "GFPGANv1.4.pth"
        modelo = str(local) if local.is_file() else URL_MODELO
        if modelo == URL_MODELO:
            self.log("Baixando modelo GFPGANv1.4 (~350 MB) na primeira execucao...")
        device = None
        if not usar_gpu:
            import torch
            device = torch.device("cpu")
        self._restaurador = GFPGANer(model_path=modelo, upscale=1, arch="clean",
                                     channel_multiplier=2, bg_upsampler=None, device=device)
        return self._restaurador

    def restaurar_video(self, video: Path, saida: Path, usar_gpu: bool = True) -> Path:
        import numpy as np
        info = info_midia(Path(video))
        if not info["tem_video"]:
            raise ValueError("Arquivo sem video.")
        w, h, fps = info["width"], info["height"], info["fps"] or 25
        restaurador = self._carregar(usar_gpu)

        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:v:0",
                                "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        enc_cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                   "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-", "-i", str(video), "-map", "0:v:0"]
        enc_cmd += ["-map", "1:a:0", "-c:a", "copy"] if info["tem_audio"] else []
        enc_cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-shortest", str(saida)]
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        tam = w * h * 3
        total = max(1, int(info["duracao"] * fps))
        n, ultimo = 0, -10
        try:
            while True:
                bruto = dec.stdout.read(tam)
                if len(bruto) < tam:
                    break
                quadro = np.frombuffer(bruto, np.uint8).reshape(h, w, 3)
                _, _, restaurado = restaurador.enhance(quadro, has_aligned=False,
                                                       only_center_face=False, paste_back=True)
                if restaurado is None:
                    restaurado = quadro
                enc.stdin.write(np.ascontiguousarray(restaurado, dtype=np.uint8).tobytes())
                n += 1
                pct = n * 100 // total
                if pct >= ultimo + 10:
                    ultimo = pct
                    self.log(f"  rostos: {min(pct, 100)}% ({n} quadros)")
        finally:
            dec.stdout.close()
            dec.wait()
            enc.stdin.close()
            err = enc.stderr.read().decode("utf-8", "replace")
            enc.wait()
        if enc.returncode != 0:
            raise FFmpegErro(enc_cmd, enc.returncode, err)
        self.log(f"[OK] {n} quadros restaurados: {saida}")
        return Path(saida)
