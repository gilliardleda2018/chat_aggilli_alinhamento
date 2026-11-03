#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GL TRANSITIONS ENGINE - Video Builder Pro v7.7
Transicoes (46) + easing via xfade do FFmpeg.
Baseado em: github.com/scriptituk/xfade-easing

Correcoes v7.7 (ver CHANGELOG.md, secao "transitions_gl.py"):
  - As 42 transicoes 'gl_*' geravam uma expressao solta no filter_complex
    ("[0:v][1:v]st(1,...)") -> FFmpeg: "No such filter: 'st(1'". Agora
    cada uma e (a) uma mascara real via xfade=transition=custom:expr=...
    ou (b) mapeada para a transicao nativa do xfade mais proxima
    (marcada como aproximacao na lista). O xfade custom so escolhe pixel
    de A ou B por coordenada (nao distorce imagem), entao transicoes de
    distorcao (cube, page curl, swirl 3D...) sao aproximacoes nativas.
  - Easing: no xfade a variavel P vai de 1 -> 0 (verificado em teste);
    as curvas foram escritas para 0 -> 1. Agora usam ld(9) = 1 - P.
  - 36 das 42 'gl_*' caiam num wipe generico identico (nome enganoso).
  - renderizar_transicao nao normalizava os clipes: resolucao/fps
    diferentes abortavam o xfade. Agora normaliza no proprio grafo.
  - Audio era descartado (sem -map de audio); agora acrossfade, com
    silencio sintetico para clipes sem audio.
  - renderizar_multiplas_transicoes calculava o offset so pela duracao do
    clipe i (errado a partir do 3o clipe); agora usa a duracao acumulada.
  - duracao da transicao >= duracao do clipe gerava offset negativo:
    validado com mensagem clara.
"""

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from ffmpeg_utils import executar_com_progresso, info_midia
except ImportError:
    from .ffmpeg_utils import executar_com_progresso, info_midia


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
    """Definicao de transicao"""
    nome: str
    duracao: float = 1.0
    easing: EasingType = EasingType.CUBIC
    params: Dict = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if isinstance(self.easing, str):
            self.easing = EasingType(self.easing.lower())


# Coordenadas normalizadas e progresso suavizado usados nas mascaras:
#   ld(1)=x (0..1)   ld(2)=y (0..1)   ld(0)=p (0..1, ja com easing)
_X, _Y, _P = "ld(1)", "ld(2)", "ld(0)"
_R = f"hypot({_X}-0.5,{_Y}-0.5)"                     # raio 0..0.7071
_ANG = f"(atan2({_Y}-0.5,{_X}-0.5)/(2*PI)+0.5)"      # angulo 0..1


def _hash(a: str, b: str) -> str:
    """Pseudo-aleatorio deterministico 0..1 por celula."""
    return f"mod(abs(sin(({a})*12.9898+({b})*78.233)*43758.5453),1)"


# id -> nome exibido, e 'nativo' (xfade) OU 'mascara' (valor 0..1: o pixel
# passa para B quando mascara < p).
_DEF = {
    # Basicas (nativas)
    "fade": ("Fade", {"nativo": "fade"}),
    "dissolve": ("Dissolve", {"nativo": "dissolve"}),
    "fadeblack": ("Fade Black", {"nativo": "fadeblack"}),
    "fadewhite": ("Fade White", {"nativo": "fadewhite"}),
    # Mascaras reais (suportam easing)
    "gl_Swirl": ("Swirl", {"mascara": f"0.5*mod({_ANG}+3*{_R},1)+0.5*{_R}/0.7072"}),
    "gl_WaterDrop": ("Water Drop", {"mascara": f"0.9*{_R}/0.7072+0.0999*(0.5+0.5*sin({_R}*60))"}),
    "gl_ripple": ("Ripple", {"mascara": f"0.85*{_R}/0.7072+0.1499*(0.5+0.5*sin({_R}*120))"}),
    "gl_chessboard": ("Chessboard", {"mascara": f"0.5*mod(floor({_X}*8)+floor({_Y}*8),2)+0.4999*mod({_Y}*8,1)"}),
    "gl_heart": ("Heart", {"mascara_bool":
        f"st(3,({_X}-0.5)/(3*{_P}+0.0001));st(4,(0.42-{_Y})/(3*{_P}+0.0001));"
        "lt(pow(ld(3)*ld(3)+ld(4)*ld(4)-0.04,3)-ld(3)*ld(3)*ld(4)*ld(4)*ld(4)*0.2,0)"}),
    "gl_pinwheel": ("Pinwheel", {"mascara": f"mod({_ANG}*4,1)"}),
    "gl_polar_function": ("Polar Function", {"mascara": f"({_R}/0.7072)*(0.8+0.2*cos(5*2*PI*{_ANG}))"}),
    "gl_windowslice": ("Window Slice", {"mascara": f"0.5*{_X}+0.4999*mod({_X}*10,1)"}),
    "gl_angular": ("Angular", {"mascara": f"mod(atan2({_X}-0.5,0.5-{_Y})/(2*PI)+1,1)"}),
    "gl_Bars": ("Bars", {"mascara": _hash(f"floor({_X}*30)", "0")}),
    "gl_CrazyParametricFun": ("Parametric Fun", {"mascara": f"mod(abs(sin({_X}*13+{_Y}*7)*cos({_X}*5-{_Y}*11))*0.999,1)"}),
    "gl_crosshatch": ("Cross Hatch", {"mascara": _hash(f"floor({_X}*40)", f"floor({_Y}*40)")}),
    "gl_Diamond": ("Diamond", {"mascara": f"abs({_X}-0.5)+abs({_Y}-0.5)"}),
    "gl_FanIn": ("Fan In", {"mascara": f"abs(atan2({_X}-0.5,1.0001-{_Y}))/(PI/2)"}),
    "gl_FanOut": ("Fan Out", {"mascara": f"1-abs(atan2({_X}-0.5,1.0001-{_Y}))/(PI/2)"}),
    "gl_FanUp": ("Fan Up", {"mascara": f"abs(atan2({_X}-0.5,{_Y}+0.0001))/(PI/2)"}),
    "gl_Flower": ("Flower", {"mascara": f"({_R}/0.7072)/(0.6+0.4*abs(cos(3*2*PI*{_ANG})))/1.7"}),
    "gl_perlin": ("Perlin", {"mascara": "0.6*" + _hash(f"floor({_X}*8)", f"floor({_Y}*8)") +
                             "+0.3999*" + _hash(f"floor({_X}*32)", f"floor({_Y}*32)")}),
    "gl_randomsquares": ("Random Squares", {"mascara": _hash(f"floor({_X}*10)", f"floor({_Y}*10)")}),
    "gl_squareswire": ("Squares Wire", {"mascara": f"2*max(abs(mod({_X}*10,1)-0.5),abs(mod({_Y}*10,1)-0.5))"}),
    "gl_StarWipe": ("Star Wipe", {"mascara": f"({_R}/0.7072)/(0.7+0.3*cos(5*2*PI*{_ANG}))/2.5"}),
    "gl_static_wipe": ("Static Wipe", {"mascara": f"0.8*{_Y}+0.1999*" + _hash(f"floor({_X}*200)", f"floor({_Y}*200)")}),
    "gl_windowblinds": ("Window Blinds", {"mascara": f"mod({_Y}*10,1)"}),
    # Distorcoes: o xfade custom nao desloca pixels -> nativa mais proxima
    "gl_cube": ("Cube (aprox.)", {"nativo": "slideleft"}),
    "gl_doorway": ("Doorway (aprox.)", {"nativo": "vertopen"}),
    "gl_BookFlip": ("Book Flip (aprox.)", {"nativo": "wipetl"}),
    "gl_crosswarp": ("Cross Warp (aprox.)", {"nativo": "smoothleft"}),
    "gl_directionalwarp": ("Directional Warp (aprox.)", {"nativo": "smoothright"}),
    "gl_kaleidoscope": ("Kaleidoscope (aprox.)", {"nativo": "radial"}),
    "gl_Mosaic": ("Mosaic (aprox.)", {"nativo": "pixelize"}),
    "gl_SimplePageCurl": ("Page Curl (aprox.)", {"nativo": "wipetr"}),
    "gl_swap": ("Swap (aprox.)", {"nativo": "slideright"}),
    "gl_Bounce": ("Bounce (aprox.)", {"nativo": "slidedown"}),
    "gl_Dreamy": ("Dreamy (aprox.)", {"nativo": "hblur"}),
    "gl_hexagonalize": ("Hexagonalize (aprox.)", {"nativo": "pixelize"}),
    "gl_InvertedPageCurl": ("Inverted Page Curl (aprox.)", {"nativo": "wipebl"}),
    "gl_LinearBlur": ("Linear Blur (aprox.)", {"nativo": "hblur"}),
    "gl_Rolls": ("Rolls (aprox.)", {"nativo": "slideup"}),
    "gl_RotateScaleVanish": ("Rotate Scale Vanish (aprox.)", {"nativo": "zoomin"}),
    "gl_rotateTransition": ("Rotate (aprox.)", {"nativo": "radial"}),
    "gl_rotate_scale_fade": ("Rotate Scale Fade (aprox.)", {"nativo": "zoomin"}),
    "gl_Slides": ("Slides (aprox.)", {"nativo": "slideleft"}),
}

class GLTransitionsEngine:
    """Engine de transicoes com easing via FFmpeg xfade"""

    TRANSICOES_GL = {k: {"nome": n, "params": {}, **d} for k, (n, d) in _DEF.items()}

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

    # ------------------------------------------------------------ expressoes
    @classmethod
    def _easing(cls, easing: EasingType) -> str:
        """Curva de easing gravada em ld(0), com progresso 0 -> 1."""
        expr = cls.EASING_EXPR.get(easing, "st(0,P)")
        return "st(9,1-P);" + re.sub(r"\bP\b", "ld(9)", expr)

    def gerar_expressao_xfade(self, transicao: GLTransition, offset: float) -> str:
        """Filtro xfade completo (sem rotulos) para a transicao."""
        d = self.TRANSICOES_GL.get(transicao.nome)
        if d is None:
            raise ValueError(f"Transicao desconhecida: {transicao.nome}")
        base = f"xfade=duration={transicao.duracao:.3f}:offset={max(0.0, offset):.3f}"
        if "nativo" in d:
            return f"{base}:transition={d['nativo']}"
        return f"{base}:transition=custom:expr='{self._expr_custom(transicao, d)}'"

    def _expr_custom(self, transicao: GLTransition, d: Dict) -> str:
        pre = f"{self._easing(transicao.easing)};st(1,X/W);st(2,Y/H);"
        if "mascara_bool" in d:
            cond = f"({d['mascara_bool']})"
        else:
            cond = f"lt({d['mascara']},{_P})"
        # Garante quadro final 100% B (evita pixel residual por arredondamento)
        return pre + f"if(gte({_P},0.999)+{cond},B,A)"

    def _gerar_expressao_gl(self, transicao: GLTransition, easing_expr: str = "") -> str:
        """Mantido por compatibilidade (v7.3): devolve a expressao custom."""
        d = self.TRANSICOES_GL.get(transicao.nome, {})
        return self._expr_custom(transicao, d) if ("mascara" in d or "mascara_bool" in d) else ""

    # ------------------------------------------------------------ grafo
    @staticmethod
    def _normalizar(idx: int, info: Dict, w: int, h: int, fps: float) -> List[str]:
        f = [f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
             f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p,settb=AVTB[v{idx}]"]
        if info["tem_audio"]:
            f.append(f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                     f"asettb=AVTB[a{idx}]")
        else:
            f.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={info['duracao']:.3f},"
                     f"aformat=sample_fmts=fltp,asettb=AVTB[a{idx}]")
        return f

    def encadear(self, rotulos_v: Sequence[str], rotulos_a: Sequence[str],
                 duracoes: Sequence[float], transicoes: Sequence[GLTransition],
                 prefixo: str = "x") -> Tuple[List[str], str, str]:
        """Encadeia xfade/acrossfade entre N streams ja normalizados.

        Retorna (filtros, rotulo_video_final, rotulo_audio_final).
        offset_k = soma(duracoes[0..k]) - soma(transicoes[0..k]).
        """
        if len(transicoes) != len(rotulos_v) - 1:
            raise ValueError("Numero de transicoes deve ser clipes - 1")
        for i, t in enumerate(transicoes):
            limite = min(duracoes[i], duracoes[i + 1])
            if t.duracao >= limite:
                raise ValueError(f"Transicao {i + 1} ({t.duracao:.2f}s) maior que o clipe ({limite:.2f}s)")
        filtros, v, a = [], rotulos_v[0], rotulos_a[0]
        acumulado = duracoes[0]
        for i, t in enumerate(transicoes):
            offset = acumulado - t.duracao
            nv, na = f"[{prefixo}v{i}]", f"[{prefixo}a{i}]"
            filtros.append(f"{v}{rotulos_v[i + 1]}{self.gerar_expressao_xfade(t, offset)}{nv}")
            filtros.append(f"{a}{rotulos_a[i + 1]}acrossfade=d={t.duracao:.3f}:c1=tri:c2=tri{na}")
            v, a = nv, na
            acumulado = acumulado - t.duracao + duracoes[i + 1]
        return filtros, v, a

    def renderizar_transicao(self, clip1: Path, clip2: Path,
                             transicao: GLTransition, saida: Path) -> Path:
        """Renderiza clip1 + transicao + clip2 (formatos podem ser diferentes)."""
        return self.renderizar_multiplas_transicoes([clip1, clip2], [transicao], saida)

    def renderizar_multiplas_transicoes(self, clips: List[Path], transicoes: List[GLTransition],
                                        saida: Path, resolucao: Optional[Tuple[int, int]] = None,
                                        fps: Optional[float] = None) -> Path:
        """Renderiza N clipes com N-1 transicoes. Resolucao/fps: do 1o clipe."""
        if len(clips) != len(transicoes) + 1:
            raise ValueError(f"Numero de clips ({len(clips)}) deve ser transicoes ({len(transicoes)}) + 1")
        infos = [info_midia(Path(c)) for c in clips]
        w, h = resolucao or (infos[0]["width"], infos[0]["height"])
        w, h = w - w % 2, h - h % 2
        fps = fps or round(infos[0]["fps"] or 25, 3)
        filtros = []
        for i, inf in enumerate(infos):
            filtros += self._normalizar(i, inf, w, h, fps)
        cadeia, rv, ra = self.encadear([f"[v{i}]" for i in range(len(clips))],
                                       [f"[a{i}]" for i in range(len(clips))],
                                       [inf["duracao"] for inf in infos], transicoes)
        filtros += cadeia
        script = self.temp_dir / "grafo.txt"
        script.write_text(";\n".join(filtros), encoding="utf-8")
        entradas = []
        for c in clips:
            entradas += ["-i", str(c)]
        cmd = ["ffmpeg", "-y", *entradas, "-filter_complex_script", str(script),
               "-map", rv, "-map", ra, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
               str(saida)]
        total = sum(i["duracao"] for i in infos) - sum(t.duracao for t in transicoes)
        nomes = ", ".join(f"{t.nome}/{t.easing.value}" for t in transicoes)
        self.log(f"Renderizando {len(transicoes)} transicao(oes): {nomes}...")
        executar_com_progresso(cmd, self.log, total)
        return Path(saida)

    def _normalizar_clip(self, clip: Path, saida: Path,
                         resolucao: Tuple[int, int] = (1920, 1080), fps: int = 25):
        """Mantido por compatibilidade (v7.3)."""
        from ffmpeg_utils import executar
        vf = (f"scale={resolucao[0]}:{resolucao[1]}:force_original_aspect_ratio=decrease,"
              f"pad={resolucao[0]}:{resolucao[1]}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}")
        executar(["ffmpeg", "-y", "-i", str(clip), "-vf", vf, "-c:v", "libx264", "-preset", "fast",
                  "-crf", "20", "-c:a", "aac", "-b:a", "192k", str(saida)], self.log)

    def _obter_duracao(self, video: Path) -> float:
        return info_midia(Path(video))["duracao"]

    def listar_transicoes(self) -> List[Dict]:
        """Lista todas as transicoes disponiveis"""
        return [{"id": tid, "nome": info["nome"], "params": info["params"],
                 "tipo": "nativa" if "nativo" in info else "mascara"}
                for tid, info in self.TRANSICOES_GL.items()]

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()
