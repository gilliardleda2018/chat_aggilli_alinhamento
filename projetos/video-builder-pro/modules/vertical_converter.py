#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERTICAL CONVERTER - Video Builder Pro v7.7
Converte videos horizontais para vertical (9:16) com face tracking
Baseado em: github.com/algometrix/vertical_video_convertor

Correcoes v7.7 (ver CHANGELOG.md, secao "vertical_converter.py"):
  - converter() exigia CropMode e a UI passava a string "smart"
    -> AttributeError 'str' object has no attribute 'value'. Agora aceita
    CropMode ou str, e os parametros opcionais sao keyword-only
    (a UI passava o blur na posicao de resolucao_saida).
  - Modo blur: o primeiro plano era recortado em 9:16 e escalado para a
    tela inteira, cobrindo 100% do fundo (blur invisivel). Agora o video
    inteiro fica centralizado sobre o fundo desfocado (estilo TikTok/Reels).
  - Video sem audio quebrava no '-c:a aac' com mapeamento implicito: tratado.
  - Face tracking: f.bbox[2]*f.bbox[3] nao e area (bbox e x1,y1,x2,y2);
    a maior face agora e escolhida pela area real. ctx_id=-1 (CPU) quando
    nao ha CUDA, em vez de assumir GPU.
  - ffprobe/ffmpeg com returncode verificado.
"""

import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Union

try:
    from ffmpeg_utils import executar, info_midia, executar_com_progresso
except ImportError:
    from .ffmpeg_utils import executar, info_midia, executar_com_progresso


class CropMode(Enum):
    CENTER = "center"
    TOP = "top"
    BOTTOM = "bottom"
    SMART = "smart"  # Face tracking
    MANUAL = "manual"


@dataclass
class CropRegion:
    """Regiao de crop"""
    x: int
    y: int
    largura: int
    altura: int


class VerticalConverter:
    """Conversor de video horizontal para vertical"""

    def __init__(self, log_callback):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_vertical_"))
        self.opencv_disponivel = self._verificar_opencv()
        self.insightface_disponivel = self._verificar_insightface()

    def _verificar_opencv(self) -> bool:
        """Verifica se OpenCV esta instalado"""
        try:
            import cv2
            return True
        except ImportError:
            self.log("AVISO: OpenCV nao encontrado. Instale com: pip install opencv-python")
            return False

    def _verificar_insightface(self) -> bool:
        """Verifica se InsightFace esta instalado"""
        try:
            import insightface
            return True
        except ImportError:
            self.log("AVISO: InsightFace nao encontrado. Instale com: pip install insightface")
            return False

    def converter(self, video: Path, saida: Path,
                  modo: Union[CropMode, str] = CropMode.CENTER, *,
                  resolucao_saida: Tuple[int, int] = (1080, 1920),
                  adicionar_blur_fundo: bool = True,
                  regiao_manual: Optional[CropRegion] = None) -> Path:
        """Converte video para vertical.

        blur=True  -> video inteiro centralizado sobre fundo desfocado.
        blur=False -> recorte 9:16 conforme o modo (center/top/bottom/smart/manual).
        """
        if isinstance(modo, str):
            modo = CropMode(modo.strip().lower())
        if modo == CropMode.MANUAL and regiao_manual is None:
            raise ValueError("Modo manual exige regiao_manual (x, y, largura, altura).")

        self.log(f"Convertendo para vertical ({modo.value}, blur={adicionar_blur_fundo})...")

        # Obtem resolucao original
        largura_orig, altura_orig = self._obter_resolucao(video)
        self.log(f"Resolucao original: {largura_orig}x{altura_orig}")

        # Define regiao de crop baseado no modo
        if modo == CropMode.MANUAL and regiao_manual:
            crop = regiao_manual
        elif modo == CropMode.SMART and self.insightface_disponivel:
            crop = self._detectar_crop_facial(video, largura_orig, altura_orig, resolucao_saida)
        elif modo == CropMode.TOP:
            crop = self._calcular_crop_topo(largura_orig, altura_orig, resolucao_saida)
        elif modo == CropMode.BOTTOM:
            crop = self._calcular_crop_baixo(largura_orig, altura_orig, resolucao_saida)
        else:  # CENTER
            crop = self._calcular_crop_centro(largura_orig, altura_orig, resolucao_saida)

        self.log(f"Regiao de crop: {crop.largura}x{crop.altura} em ({crop.x},{crop.y})")

        # Constroi filtro FFmpeg
        if adicionar_blur_fundo:
            filtro = self._gerar_filtro_com_blur(crop, resolucao_saida, largura_orig, altura_orig)
        else:
            filtro = self._gerar_filtro_simples(crop, resolucao_saida)

        info = info_midia(Path(video))
        cmd = ["ffmpeg", "-y", "-i", str(video), "-filter_complex", filtro + "[vout]",
               "-map", "[vout]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"] if info["tem_audio"] else ["-an"]

        self.log("Renderizando video vertical...")
        executar_com_progresso(cmd + [str(saida)], self.log, info["duracao"])
        self.log(f"Conversao concluida: {saida}")
        return saida

    def _obter_resolucao(self, video: Path) -> Tuple[int, int]:
        """Obtem resolucao do video"""
        info = info_midia(Path(video))
        if not info["tem_video"]:
            raise ValueError(f"'{Path(video).name}' nao tem trilha de video.")
        return info["width"], info["height"]

    def _calcular_crop_centro(self, largura_orig: int, altura_orig: int,
                               resolucao_saida: Tuple[int, int]) -> CropRegion:
        """Calcula crop central para vertical"""

        # Aspect ratio vertical (9:16)
        aspect_alvo = resolucao_saida[0] / resolucao_saida[1]

        # Calcula largura do crop baseado na altura original
        altura_crop = altura_orig
        largura_crop = int(altura_crop * aspect_alvo)

        # Se largura_crop > largura_orig, ajusta
        if largura_crop > largura_orig:
            largura_crop = largura_orig
            altura_crop = int(largura_crop / aspect_alvo)

        # Centraliza
        x = (largura_orig - largura_crop) // 2
        y = (altura_orig - altura_crop) // 2

        return CropRegion(x, y, largura_crop, altura_crop)

    def _calcular_crop_topo(self, largura_orig: int, altura_orig: int,
                            resolucao_saida: Tuple[int, int]) -> CropRegion:
        """Calcula crop no topo (para mostrar rosto)"""

        aspect_alvo = resolucao_saida[0] / resolucao_saida[1]
        altura_crop = altura_orig
        largura_crop = int(altura_crop * aspect_alvo)

        if largura_crop > largura_orig:
            largura_crop = largura_orig
            altura_crop = int(largura_crop / aspect_alvo)

        x = (largura_orig - largura_crop) // 2
        y = 0  # Topo

        return CropRegion(x, y, largura_crop, altura_crop)

    def _calcular_crop_baixo(self, largura_orig: int, altura_orig: int,
                             resolucao_saida: Tuple[int, int]) -> CropRegion:
        """Calcula crop embaixo (para mostrar acao)"""

        aspect_alvo = resolucao_saida[0] / resolucao_saida[1]
        altura_crop = altura_orig
        largura_crop = int(altura_crop * aspect_alvo)

        if largura_crop > largura_orig:
            largura_crop = largura_orig
            altura_crop = int(largura_crop / aspect_alvo)

        x = (largura_orig - largura_crop) // 2
        y = altura_orig - altura_crop  # Embaixo

        return CropRegion(x, y, largura_crop, altura_crop)

    def _detectar_crop_facial(self, video: Path,
                              largura_orig: int, altura_orig: int,
                              resolucao_saida: Tuple[int, int]) -> CropRegion:
        """Detecta crop baseado em tracking facial"""

        if not self.opencv_disponivel or not self.insightface_disponivel:
            self.log("Face tracking nao disponivel, usando crop central")
            return self._calcular_crop_centro(largura_orig, altura_orig, resolucao_saida)

        try:
            import cv2
            import insightface

            self.log("Analisando faces para crop inteligente...")

            # Carrega modelo de deteccao facial (GPU se houver CUDA, senao CPU)
            from insightface.app import FaceAnalysis
            try:
                import onnxruntime
                ctx = 0 if "CUDAExecutionProvider" in onnxruntime.get_available_providers() else -1
            except ImportError:
                ctx = -1
            app = FaceAnalysis(allowed_modules=["detection"])
            app.prepare(ctx_id=ctx, det_size=(640, 640))

            # Analisa alguns frames
            cap = cv2.VideoCapture(str(video))
            faces_detectadas = []

            # Analisa 10 frames distribuidos
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frames_analisar = [int(total_frames * i / 10) for i in range(10)]

            for frame_idx in frames_analisar:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if ret:
                    faces = app.get(frame)
                    if faces:
                        # Pega a maior face
                        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                        x1, y1, x2, y2 = map(int, face.bbox)
                        faces_detectadas.append({
                            'centro_x': (x1 + x2) // 2,
                            'centro_y': (y1 + y2) // 2,
                            'largura': x2 - x1,
                            'altura': y2 - y1
                        })

            cap.release()

            if faces_detectadas:
                # Calcula centro medio das faces
                centro_x_medio = sum(f['centro_x'] for f in faces_detectadas) // len(faces_detectadas)
                centro_y_medio = sum(f['centro_y'] for f in faces_detectadas) // len(faces_detectadas)

                self.log(f"Faces detectadas em ({centro_x_medio}, {centro_y_medio})")

                # Calcula crop centrado na face
                aspect_alvo = resolucao_saida[0] / resolucao_saida[1]
                altura_crop = altura_orig
                largura_crop = int(altura_crop * aspect_alvo)

                if largura_crop > largura_orig:
                    largura_crop = largura_orig
                    altura_crop = int(largura_crop / aspect_alvo)

                # Centraliza na face, com margem
                x = max(0, centro_x_medio - largura_crop // 2)
                x = min(x, largura_orig - largura_crop)

                y = max(0, centro_y_medio - altura_crop // 2)
                y = min(y, altura_orig - altura_crop)

                return CropRegion(x, y, largura_crop, altura_crop)

        except Exception as e:
            self.log(f"Erro no face tracking: {e}")

        # Fallback para centro
        return self._calcular_crop_centro(largura_orig, altura_orig, resolucao_saida)

    def _gerar_filtro_simples(self, crop: CropRegion,
                               resolucao_saida: Tuple[int, int]) -> str:
        """Gera filtro simples de crop + scale (rotulo de saida e adicionado depois)"""
        return (f"[0:v]crop={crop.largura}:{crop.altura}:{crop.x}:{crop.y},"
                f"scale={resolucao_saida[0]}:{resolucao_saida[1]},setsar=1")

    def _gerar_filtro_com_blur(self, crop: CropRegion,
                                resolucao_saida: Tuple[int, int],
                                largura_orig: int, altura_orig: int) -> str:
        """Fundo: video preenchendo 9:16 e desfocado. Frente: video INTEIRO
        reduzido para caber na largura, centralizado (o fundo fica visivel
        acima e abaixo)."""
        w, h = resolucao_saida
        return (f"[0:v]split[bg][fg];"
                f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"boxblur=20:5[bg_blur];"
                f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"scale=trunc(iw/2)*2:trunc(ih/2)*2[fg_scaled];"
                f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2,setsar=1")

    def criar_preview_crop(self, video: Path, crop: CropRegion,
                           saida: Path, tempo: float = 5.0) -> Path:
        """Cria preview do crop"""

        filtro = (
            f"crop={crop.largura}:{crop.altura}:{crop.x}:{crop.y},"
            f"scale=540:960"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-t", str(tempo),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(saida)
        ]

        executar(cmd, self.log)
        return saida

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()
