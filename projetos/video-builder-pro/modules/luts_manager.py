#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LUTS MANAGER - Video Builder Pro v7.7
Gerencia aplicacao de LUTs (.cube) e looks embutidos

Correcoes v7.7 (ver CHANGELOG.md, secao "luts_manager.py"):
  - Intensidade multiplicava os parametros do 'eq' pelo valor do slider:
    contrast 1.15 x 0.5 = 0.575 (abaixo do neutro 1.0, o look INVERTIA).
    Agora interpola a partir do valor neutro: neutro + (v - neutro) * i
    (contrast/saturation/gamma neutro 1, brightness neutro 0), e o
    colorbalance/vignette/unsharp/curves tambem respeitam a intensidade.
  - Intensidade 0 devolve o video sem alteracao de cor.
  - Caminho de .cube com ':' (Windows) ou apostrofo quebrava o lut3d:
    usa escapar_caminho_filtro().
  - Mistura parcial de .cube usava '-vf' com 'blend' sem formato comum;
    agora e um filter_complex com format=gbrp nos dois ramos.
  - Video sem audio: '-c:a copy' nao falha mais (mapeamento opcional).
  - returncode verificado em preview/grade de teste.
"""

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    from ffmpeg_utils import executar, escapar_caminho_filtro, info_midia, executar_com_progresso
except ImportError:
    from .ffmpeg_utils import executar, escapar_caminho_filtro, info_midia, executar_com_progresso

# Valores neutros dos parametros ajustaveis (intensidade 0 => neutro)
_NEUTRO = {"contrast": 1.0, "saturation": 1.0, "gamma": 1.0, "brightness": 0.0}


@dataclass
class LUTInfo:
    """Informacao de LUT"""
    nome: str
    arquivo: Optional[Path]
    tipo: str  # "embutido" ou "arquivo"
    descricao: str = ""
    categoria: str = ""


class LUTManager:
    """Gerenciador de LUTs e color grading"""

    # Looks embutidos (filtros FFmpeg)
    LOOKS_EMBUTIDOS = {
        "cinematic": {
            "nome": "Cinematic",
            "descricao": "Contraste alto, saturacao reduzida, vignette sutil",
            "categoria": "cinema",
            "filtro": "eq=contrast=1.15:saturation=0.85:gamma=0.95,colorbalance=rs=-0.02:gs=0.0:bs=0.03,vignette=PI/4"
        },
        "orange_teal": {
            "nome": "Orange & Teal",
            "descricao": "Laranja nas altas luzes, azul esverdeado nas sombras",
            "categoria": "cinema",
            "filtro": "colorbalance=rs=0.15:gs=0.05:bs=-0.1:rm=0.1:gm=0.0:bm=-0.05:rh=0.05:gh=0.0:bh=-0.1"
        },
        "film_noir": {
            "nome": "Film Noir",
            "descricao": "Preto e branco com alto contraste",
            "categoria": "vintage",
            "filtro": "hue=s=0,eq=contrast=1.3:brightness=-0.05:gamma=1.1"
        },
        "vibrant": {
            "nome": "Vibrant",
            "descricao": "Cores vivas e saturadas",
            "categoria": "moderno",
            "filtro": "eq=contrast=1.2:saturation=1.4:brightness=0.05"
        },
        "warm": {
            "nome": "Warm",
            "descricao": "Tons quentes, aconchegantes",
            "categoria": "moderno",
            "filtro": "eq=contrast=1.1:saturation=1.1:gamma=1.05,colorbalance=rs=0.1:gs=0.05:bs=-0.05"
        },
        "cold": {
            "nome": "Cold",
            "descricao": "Tons frios, azulados",
            "categoria": "moderno",
            "filtro": "eq=contrast=1.05:saturation=0.9,colorbalance=rs=-0.05:gs=0.0:bs=0.1"
        },
        "bleach_bypass": {
            "nome": "Bleach Bypass",
            "descricao": "Alto contraste, baixa saturacao (estilo filme de guerra)",
            "categoria": "vintage",
            "filtro": "eq=contrast=1.4:saturation=0.6:brightness=0.02"
        },
        "day_for_night": {
            "nome": "Day for Night",
            "descricao": "Simula cena noturna",
            "categoria": "efeitos",
            "filtro": "eq=contrast=1.1:saturation=0.4:brightness=-0.15,colorbalance=bs=0.15"
        },
        "vintage": {
            "nome": "Vintage",
            "descricao": "Look de filme antigo",
            "categoria": "vintage",
            "filtro": "eq=contrast=1.1:saturation=0.7:gamma=1.1,colorbalance=rs=0.05:bs=0.1,curves=vintage"
        },
        "hdr": {
            "nome": "HDR Effect",
            "descricao": "Simula alcance dinamico expandido",
            "categoria": "efeitos",
            "filtro": "eq=contrast=1.3:saturation=1.2:gamma=0.9,unsharp=5:5:1.0"
        },
        "pastel": {
            "nome": "Pastel",
            "descricao": "Tons suaves e leitosos",
            "categoria": "moderno",
            "filtro": "eq=contrast=0.9:saturation=0.8:brightness=0.1:gamma=1.1"
        },
        "matte": {
            "nome": "Matte",
            "descricao": "Look fosco, sem brilho",
            "categoria": "moderno",
            "filtro": "eq=contrast=0.95:saturation=0.9:gamma=1.05,curves=m=0/0:0.1/0.15:0.5/0.5:0.9/0.85:1/1"
        },
        "crisp": {
            "nome": "Crisp",
            "descricao": "Nitidez aumentada, cores limpas",
            "categoria": "moderno",
            "filtro": "unsharp=5:5:0.8,eq=contrast=1.1:saturation=1.1"
        },
        "dramatic": {
            "nome": "Dramatic",
            "descricao": "Alto contraste, sombras profundas",
            "categoria": "cinema",
            "filtro": "eq=contrast=1.4:saturation=0.9:brightness=-0.05,curves=m=0/0:0.3/0.1:0.7/0.9:1/1"
        },
        "soft_light": {
            "nome": "Soft Light",
            "descricao": "Luz suave, look de filme romantico",
            "categoria": "moderno",
            "filtro": "eq=contrast=1.05:saturation=0.95:gamma=1.1,colorbalance=rs=0.05:gs=0.02"
        },
    }

    def __init__(self, log_callback):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_luts_"))
        self.luts_personalizadas: Dict[str, Path] = {}
        self._carregar_luts_pasta()

    def _carregar_luts_pasta(self):
        """Carrega LUTs .cube da pasta luts/ se existir"""
        pasta_luts = Path(__file__).parent.parent / "luts"
        if pasta_luts.exists():
            for arquivo in pasta_luts.glob("*.cube"):
                nome = arquivo.stem
                self.luts_personalizadas[nome] = arquivo
                self.log(f"LUT carregada: {nome}")

    def adicionar_lut_personalizada(self, nome: str, arquivo: Path):
        """Adiciona LUT .cube personalizada"""
        if arquivo.exists() and arquivo.suffix.lower() == ".cube":
            self.luts_personalizadas[nome] = arquivo
            self.log(f"LUT '{nome}' adicionada com sucesso!")
        else:
            raise ValueError(f"Arquivo LUT invalido: {arquivo}")

    def listar_luts(self) -> List[LUTInfo]:
        """Lista todas as LUTs disponiveis"""
        luts = []

        # Embutidas
        for id_lut, info in self.LOOKS_EMBUTIDOS.items():
            luts.append(LUTInfo(
                nome=info["nome"],
                arquivo=None,
                tipo="embutido",
                descricao=info["descricao"],
                categoria=info["categoria"]
            ))

        # Personalizadas (.cube)
        for nome, arquivo in self.luts_personalizadas.items():
            luts.append(LUTInfo(
                nome=nome,
                arquivo=arquivo,
                tipo="arquivo",
                descricao=f"LUT personalizada: {arquivo.name}",
                categoria="personalizada"
            ))

        return luts

    def aplicar_lut(self, video: Path, lut_nome: str,
                    saida: Path, intensidade: float = 1.0) -> Path:
        """Aplica LUT (.cube) ou look embutido ao video."""
        intensidade = max(0.0, min(1.0, float(intensidade)))
        filtro = self.obter_filtro_ffmpeg(lut_nome, intensidade)
        if lut_nome not in self.luts_personalizadas and self._id_embutido(lut_nome) is None:
            self.log(f"AVISO: LUT '{lut_nome}' nao encontrada, usando cinematic")
        info = info_midia(Path(video))
        cmd = ["ffmpeg", "-y", "-i", str(video), "-filter_complex", f"[0:v]{filtro}[vout]",
               "-map", "[vout]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        cmd += ["-map", "0:a:0?", "-c:a", "copy"] if info["tem_audio"] else ["-an"]
        self.log(f"Aplicando '{lut_nome}' em {Path(video).name} (intensidade {intensidade:.2f})...")
        executar_com_progresso(cmd + [str(saida)], self.log, info["duracao"])
        return Path(saida)

    def _id_embutido(self, lut_nome: str) -> Optional[str]:
        for id_lut, info in self.LOOKS_EMBUTIDOS.items():
            if lut_nome in (id_lut, info["nome"]):
                return id_lut
        return None

    # Mantidos por compatibilidade com a API v7.3 -------------------------
    def _aplicar_look_embutido(self, video, look_id, saida, intensidade):
        return self.aplicar_lut(video, look_id, saida, intensidade)

    def _aplicar_lut_arquivo(self, video, lut_arquivo, saida, intensidade):
        nome = Path(lut_arquivo).stem
        self.luts_personalizadas.setdefault(nome, Path(lut_arquivo))
        return self.aplicar_lut(video, nome, saida, intensidade)

    def _ajustar_intensidade_filtro(self, filtro: str, intensidade: float) -> str:
        """Interpola cada parametro entre o neutro e o valor do look."""
        i = max(0.0, min(1.0, float(intensidade)))

        def _eq(m):
            nome, valor = m.group(1), float(m.group(2))
            neutro = _NEUTRO[nome]
            return f"{nome}={neutro + (valor - neutro) * i:.4f}"
        filtro = re.sub(r"\b(contrast|saturation|brightness|gamma)=(-?[\d.]+)", _eq, filtro)

        # colorbalance: neutro 0
        filtro = re.sub(r"\b([rgb][smh])=(-?[\d.]+)",
                        lambda m: f"{m.group(1)}={float(m.group(2)) * i:.4f}", filtro)
        # unsharp=lx:ly:amount -> amount neutro 0
        filtro = re.sub(r"unsharp=(\d+):(\d+):(-?[\d.]+)",
                        lambda m: f"unsharp={m.group(1)}:{m.group(2)}:{float(m.group(3)) * i:.4f}", filtro)
        # vignette=angulo -> angulo menor = mais forte; 0 desliga. Escala o angulo.
        filtro = re.sub(r"vignette=PI/(\d+)",
                        lambda m: f"vignette=angle={3.14159265 / float(m.group(1)) * i:.4f}", filtro)
        return filtro

    def obter_filtro_ffmpeg(self, lut_nome: str, intensidade: float = 1.0, rotulo: str = "") -> str:
        """Cadeia de filtros (sem rotulos de entrada/saida) para filter_complex.

        Para .cube com intensidade < 1 usa split + blend, por isso o retorno
        deve ser usado como '[in]<filtro>[out]' dentro de um filter_complex.
        'rotulo' torna unicos os rotulos internos quando o filtro aparece
        varias vezes no mesmo grafo (um por clipe no render).
        """
        r = rotulo
        i = max(0.0, min(1.0, float(intensidade)))
        if i == 0.0:
            return "null"
        if lut_nome in self.luts_personalizadas:
            lut = f"lut3d=file={escapar_caminho_filtro(self.luts_personalizadas[lut_nome])}:interp=trilinear"
            if i >= 1.0:
                return lut
            return (f"format=gbrp,split[_lo{r}][_lb{r}];[_lb{r}]{lut}[_ll{r}];"
                    f"[_lo{r}][_ll{r}]blend=all_mode=normal:all_opacity={i:.4f},format=yuv420p")
        id_lut = self._id_embutido(lut_nome) or "cinematic"
        filtro = self.LOOKS_EMBUTIDOS[id_lut]["filtro"]
        if i >= 1.0:
            return filtro
        filtro = self._ajustar_intensidade_filtro(filtro, i)
        if "curves=" in filtro:  # curvas nao tem parametro numerico simples: mistura
            return (f"format=gbrp,split[_co{r}][_cb{r}];[_cb{r}]{filtro}[_cl{r}];"
                    f"[_co{r}][_cl{r}]blend=all_mode=normal:all_opacity={i:.4f},format=yuv420p")
        return filtro

    def gerar_preview_lut(self, lut_nome: str, imagem_base: Optional[Path] = None) -> Path:
        """Gera preview da LUT em imagem"""
        if imagem_base is None:
            imagem_base = self.temp_dir / "test_grid.png"
            self._criar_grid_teste(imagem_base)
        saida = self.temp_dir / f"preview_{re.sub(r'[^\w-]', '_', lut_nome)}.png"
        executar(["ffmpeg", "-y", "-i", str(imagem_base), "-filter_complex",
                  f"[0:v]{self.obter_filtro_ffmpeg(lut_nome)}[o]", "-map", "[o]",
                  "-frames:v", "1", str(saida)], self.log)
        return saida

    def _criar_grid_teste(self, saida: Path):
        """Cria grid de cores para teste"""
        executar(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:duration=1",
                  "-frames:v", "1", str(saida)], self.log)

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()
