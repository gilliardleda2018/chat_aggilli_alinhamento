#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERTICAL CONVERTER - Video Builder Pro v7.3
Converte videos horizontais para vertical (9:16) com face tracking
Baseado em: github.com/algometrix/vertical_video_convertor
"""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json


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
                  modo: CropMode = CropMode.CENTER,
                  resolucao_saida: Tuple[int, int] = (1080, 1920),
                  adicionar_blur_fundo: bool = True,
                  regiao_manual: Optional[CropRegion] = None) -> Path:
        """Converte video para vertical"""

        self.log(f"Convertendo para vertical ({modo.value})...")

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

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(saida)
        ]

        self.log("Renderizando video vertical...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:300]}")
            raise Exception(f"Falha na conversao: {result.stderr[:200]}")

        self.log(f"Conversao concluida: {saida}")
        return saida

    def _obter_resolucao(self, video: Path) -> Tuple[int, int]:
        """Obtem resolucao do video"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", str(video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        largura, altura = map(int, result.stdout.strip().split(','))
        return largura, altura

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

            # Carrega modelo de deteccao facial
            app = insightface.app.FaceAnalysis()
            app.prepare(ctx_id=0, det_size=(640, 640))

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
                        face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
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
        """Gera filtro simples de crop + scale"""

        filtro = (
            f"crop={crop.largura}:{crop.altura}:{crop.x}:{crop.y},"
            f"scale={resolucao_saida[0]}:{resolucao_saida[1]}"
        )

        return filtro

    def _gerar_filtro_com_blur(self, crop: CropRegion,
                                resolucao_saida: Tuple[int, int],
                                largura_orig: int, altura_orig: int) -> str:
        """Gera filtro com blur no fundo (estilo TikTok)"""

        # Video embaixo (blur), video em cima (crop)
        filtro = (
            f"[0:v]split[bg][fg];"
            f"[bg]scale={resolucao_saida[0]}:{resolucao_saida[1]},"
            f"boxblur=20:5[bg_blur];"
            f"[fg]crop={crop.largura}:{crop.altura}:{crop.x}:{crop.y},"
            f"scale={resolucao_saida[0]}:{resolucao_saida[1]}[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2"
        )

        return filtro

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
            "-ss", "0",
            "-t", str(tempo),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(saida)
        ]

        subprocess.run(cmd, capture_output=True)
        return saida

    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
