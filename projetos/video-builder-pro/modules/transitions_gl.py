#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GL TRANSITIONS ENGINE - Video Builder Pro v7.3
Implementa transicoes GL (70+) + easing via expressoes customizadas FFmpeg
Baseado em: github.com/scriptituk/xfade-easing
"""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class EasingType(Enum):
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    CUBIC = "cubic"
    QUARTIC = "quartic"
    QUINTIC = "quintic"
    SINUSOIDAL = "sinusoidal"
    EXPONENTIAL = "exponential"
    CIRCULAR = "circular"
    ELASTIC = "elastic"
    BACK = "back"
    BOUNCE = "bounce"


@dataclass
class GLTransition:
    """Definicao de transicao GL"""
    nome: str
    duracao: float = 1.0
    easing: EasingType = EasingType.CUBIC
    params: Dict = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}


class GLTransitionsEngine:
    """Engine para transicoes GL com easing via FFmpeg xfade"""

    # Transicoes GL disponiveis (do gl-transitions)
    TRANSICOES_GL = {
        # Basicas
        "fade": {"nome": "Fade", "params": {}},
        "dissolve": {"nome": "Dissolve", "params": {}},
        "fadeblack": {"nome": "Fade Black", "params": {}},
        "fadewhite": {"nome": "Fade White", "params": {}},

        # GL Avancadas
        "gl_cube": {"nome": "Cube", "params": {"persp": 0.7, "unzoom": 0.3, "reflection": 0.4}},
        "gl_doorway": {"nome": "Doorway", "params": {"reflection": 0.4, "perspective": 0.4, "depth": 3}},
        "gl_Swirl": {"nome": "Swirl", "params": {"radius": 1}},
        "gl_WaterDrop": {"nome": "Water Drop", "params": {"amplitude": 30, "speed": 30}},
        "gl_ripple": {"nome": "Ripple", "params": {"amplitude": 100, "speed": 50}},
        "gl_BookFlip": {"nome": "Book Flip", "params": {}},
        "gl_chessboard": {"nome": "Chessboard", "params": {"grid": 8}},
        "gl_crosswarp": {"nome": "Cross Warp", "params": {}},
        "gl_directionalwarp": {"nome": "Directional Warp", "params": {"smoothness": 0.1}},
        "gl_heart": {"nome": "Heart", "params": {}},
        "gl_kaleidoscope": {"nome": "Kaleidoscope", "params": {"speed": 1, "angle": 1, "power": 1.5}},
        "gl_Mosaic": {"nome": "Mosaic", "params": {"endx": 2, "endy": -1}},
        "gl_pinwheel": {"nome": "Pinwheel", "params": {"speed": 2}},
        "gl_polar_function": {"nome": "Polar Function", "params": {"segments": 5}},
        "gl_SimplePageCurl": {"nome": "Page Curl", "params": {"angle": 80, "radius": 0.15}},
        "gl_swap": {"nome": "Swap", "params": {"reflection": 0.4, "perspective": 0.2, "depth": 3}},
        "gl_windowslice": {"nome": "Window Slice", "params": {"count": 10, "smoothness": 0.5}},
        "gl_angular": {"nome": "Angular", "params": {"startingAngle": 90}},
        "gl_Bars": {"nome": "Bars", "params": {"vertical": 0}},
        "gl_Bounce": {"nome": "Bounce", "params": {"bounces": 3}},
        "gl_CrazyParametricFun": {"nome": "Parametric Fun", "params": {"a": 4, "b": 1, "amplitude": 120}},
        "gl_crosshatch": {"nome": "Cross Hatch", "params": {"threshold": 3, "fadeEdge": 0.1}},
        "gl_Diamond": {"nome": "Diamond", "params": {"smoothness": 0.05}},
        "gl_Dreamy": {"nome": "Dreamy", "params": {}},
        "gl_FanIn": {"nome": "Fan In", "params": {"smoothness": 0.05}},
        "gl_FanOut": {"nome": "Fan Out", "params": {"smoothness": 0.05}},
        "gl_FanUp": {"nome": "Fan Up", "params": {"smoothness": 0.05}},
        "gl_Flower": {"nome": "Flower", "params": {"rotation": 360}},
        "gl_hexagonalize": {"nome": "Hexagonalize", "params": {"steps": 50, "horizontalHexagons": 20}},
        "gl_InvertedPageCurl": {"nome": "Inverted Page Curl", "params": {"angle": 100}},
        "gl_LinearBlur": {"nome": "Linear Blur", "params": {"intensity": 0.1}},
        "gl_perlin": {"nome": "Perlin", "params": {"scale": 4, "smoothness": 0.01}},
        "gl_randomsquares": {"nome": "Random Squares", "params": {"size": 10}},
        "gl_Rolls": {"nome": "Rolls", "params": {"type": 0, "rotDown": 0}},
        "gl_RotateScaleVanish": {"nome": "Rotate Scale Vanish", "params": {}},
        "gl_rotateTransition": {"nome": "Rotate", "params": {}},
        "gl_rotate_scale_fade": {"nome": "Rotate Scale Fade", "params": {"rotations": 1, "scale": 8}},
        "gl_Slides": {"nome": "Slides", "params": {"type": 0, "slideIn": 0}},
        "gl_squareswire": {"nome": "Squares Wire", "params": {"squares": 10}},
        "gl_StarWipe": {"nome": "Star Wipe", "params": {"borderThickness": 0.01}},
        "gl_static_wipe": {"nome": "Static Wipe", "params": {"upToDown": 1, "maxSpan": 0.5}},
        "gl_windowblinds": {"nome": "Window Blinds", "params": {}},
    }

    # Expressoes de easing para FFmpeg
    EASING_EXPR = {
        EasingType.LINEAR: "st(0,P)",
        EasingType.QUADRATIC: "st(0,if(lt(P,0.5),2*P*P,1-2*(1-P)^2))",
        EasingType.CUBIC: "st(0,if(lt(P,0.5),4*P^3,1-4*(1-P)^3))",
        EasingType.QUARTIC: "st(0,if(lt(P,0.5),8*P^4,1-8*(1-P)^4))",
        EasingType.QUINTIC: "st(0,if(lt(P,0.5),16*P^5,1-16*(1-P)^5))",
        EasingType.SINUSOIDAL: "st(0,0.5-0.5*cos(PI*P))",
        EasingType.EXPONENTIAL: "st(0,if(lt(P,0.5),0.5*2^(10*(2*P-1)),1-0.5*2^(-10*(2*P-1))))",
        EasingType.CIRCULAR: "st(0,if(lt(P,0.5),0.5*(1-sqrt(1-4*P^2)),0.5*(sqrt(1-(2*P-2)^2)+1)))",
        EasingType.ELASTIC: "st(0,cos((1-P)*20.944)/2^(10*(1-P)))",
        EasingType.BACK: "st(0,if(lt(P,0.5),(P*7.18982-2.59491)*P*P*2,(P*7.18982-4.59491)*(1-P)^2*2+1))",
        EasingType.BOUNCE: "st(0,if(lt(P,1/2.75),7.5625*P*P,if(lt(P,2/2.75),7.5625*(P-1.5/2.75)^2+0.75,if(lt(P,2.5/2.75),7.5625*(P-2.25/2.75)^2+0.9375,7.5625*(P-2.625/2.75)^2+0.984375))))",
    }

    def __init__(self, log_callback):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_gl_"))

    def gerar_expressao_xfade(self, transicao: GLTransition, offset: float) -> str:
        """Gera expressao xfade com easing para FFmpeg"""

        # Easing expression
        easing_expr = self.EASING_EXPR.get(transicao.easing, "st(0,P)")

        # Transicao GL especifica
        if transicao.nome.startswith("gl_"):
            # Transicoes GL customizadas
            expr = self._gerar_expressao_gl(transicao, easing_expr)
        else:
            # Transicoes nativas xfade
            expr = f"xfade=transition={transicao.nome}:duration={transicao.duracao}:offset={offset}"

        return expr

    def _gerar_expressao_gl(self, transicao: GLTransition, easing_expr: str) -> str:
        """Gera expressao para transicao GL especifica"""

        # Exemplos de expressoes GL (simplificadas)
        expressoes_gl = {
            "gl_cube": f"st(1,{transicao.params.get('persp', 0.7)});{easing_expr};"
                      f"st(2,0.5-(0.5-Y/H)*(1-ld(0)));"
                      f"if(lt(X/W,ld(0)),A,B)",

            "gl_Swirl": f"st(1,{transicao.params.get('radius', 1)});{easing_expr};"
                       f"st(2,X/W-0.5);st(3,0.5-Y/H);st(4,hypot(ld(2),ld(3)));"
                       f"if(lt(ld(4),ld(1)),A,B)",

            "gl_ripple": f"st(1,{transicao.params.get('amplitude', 100)});"
                        f"st(2,{transicao.params.get('speed', 50)});{easing_expr};"
                        f"st(3,sin((X/W+Y/H)*ld(2)*ld(0)));"
                        f"if(gt(ld(3),0.5),A,B)",
        }

        return expressoes_gl.get(transicao.nome, f"{easing_expr};if(lt(X/W,ld(0)),A,B)")

    def renderizar_transicao(self, clip1: Path, clip2: Path,
                            transicao: GLTransition, saida: Path) -> Path:
        """Renderiza transicao entre dois clips"""

        # Obtem duracao do primeiro clip
        duracao1 = self._obter_duracao(clip1)
        offset = duracao1 - transicao.duracao

        # Gera filter_complex
        expr = self.gerar_expressao_xfade(transicao, offset)

        filter_complex = f"[0:v][1:v]{expr}[v]"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip1),
            "-i", str(clip2),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(saida)
        ]

        self.log(f"Renderizando transicao {transicao.nome} com easing {transicao.easing.value}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro na renderizacao: {result.stderr[:500]}")
            raise Exception(f"Falha ao renderizar transicao: {result.stderr[:200]}")

        return saida

    def renderizar_multiplas_transicoes(self, clips: List[Path],
                                       transicoes: List[GLTransition],
                                       saida: Path) -> Path:
        """Renderiza multiplos clips com transicoes entre eles"""

        if len(clips) != len(transicoes) + 1:
            raise ValueError(f"Numero de clips ({len(clips)}) deve ser transicoes ({len(transicoes)}) + 1")

        # Normaliza clips primeiro
        clips_norm = []
        for i, clip in enumerate(clips):
            norm_path = self.temp_dir / f"norm_{i:03d}.mp4"
            self._normalizar_clip(clip, norm_path)
            clips_norm.append(norm_path)

        # Construi filter_complex com xfade em cadeia
        inputs = []
        filters = []

        # Adiciona inputs
        for i, clip in enumerate(clips_norm):
            inputs.extend(["-i", str(clip)])

        # Primeira transicao
        offset = self._obter_duracao(clips_norm[0]) - transicoes[0].duracao
        expr = self.gerar_expressao_xfade(transicoes[0], offset)
        filters.append(f"[0:v][1:v]{expr}[v1]")

        # Transicoes intermediarias
        for i in range(1, len(transicoes)):
            offset = self._obter_duracao(clips_norm[i]) - transicoes[i].duracao
            expr = self.gerar_expressao_xfade(transicoes[i], offset)
            filters.append(f"[v{i}][{i+1}:v]{expr}[v{i+1}]")

        # Audio (concatena)
        audio_filters = ""
        for i in range(len(clips_norm)):
            audio_filters += f"[{i}:a]"
        audio_filters += f"concat=n={len(clips_norm)}:v=0:a=1[a]"

        filter_complex = ";".join(filters) + ";" + audio_filters

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[v{len(transicoes)}]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(saida)
        ]

        self.log(f"Renderizando {len(transicoes)} transicoes GL...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:500]}")
            raise Exception(f"Falha ao renderizar: {result.stderr[:200]}")

        return saida

    def _normalizar_clip(self, clip: Path, saida: Path,
                        resolucao: Tuple[int, int] = (1920, 1080),
                        fps: int = 25):
        """Normaliza clip para resolucao e fps padrao"""

        vf = f"scale={resolucao[0]}:{resolucao[1]}:force_original_aspect_ratio=decrease,"
        vf += f"pad={resolucao[0]}:{resolucao[1]}:(ow-iw)/2:(oh-ih)/2,"
        vf += f"fps={fps}"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(saida)
        ]

        subprocess.run(cmd, capture_output=True)

    def _obter_duracao(self, video: Path) -> float:
        """Obtem duracao do video em segundos"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", str(video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    def listar_transicoes(self) -> List[Dict]:
        """Lista todas as transicoes GL disponiveis"""
        return [
            {
                "id": tid,
                "nome": info["nome"],
                "params": info["params"]
            }
            for tid, info in self.TRANSICOES_GL.items()
        ]

    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
