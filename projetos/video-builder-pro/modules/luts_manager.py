#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LUTS MANAGER - Video Builder Pro v7.3
Gerencia aplicacao de LUTs (.cube) e looks embutidos
"""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import re


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
        """Aplica LUT ao video"""

        # Verifica se e LUT personalizada
        if lut_nome in self.luts_personalizadas:
            return self._aplicar_lut_arquivo(
                video, self.luts_personalizadas[lut_nome],
                saida, intensidade
            )

        # Verifica se e look embutido
        for id_lut, info in self.LOOKS_EMBUTIDOS.items():
            if info["nome"] == lut_nome or id_lut == lut_nome:
                return self._aplicar_look_embutido(video, id_lut, saida, intensidade)

        self.log(f"AVISO: LUT '{lut_nome}' nao encontrada, usando cinematic")
        return self._aplicar_look_embutido(video, "cinematic", saida, intensidade)

    def _aplicar_look_embutido(self, video: Path, look_id: str,
                                saida: Path, intensidade: float) -> Path:
        """Aplica look embutido via filtro FFmpeg"""

        filtro = self.LOOKS_EMBUTIDOS.get(look_id, self.LOOKS_EMBUTIDOS["cinematic"])["filtro"]

        # Ajusta intensidade se necessario
        if intensidade != 1.0:
            filtro = self._ajustar_intensidade_filtro(filtro, intensidade)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            str(saida)
        ]

        self.log(f"Aplicando look '{look_id}' em {video.name}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:300]}")
            raise Exception(f"Falha ao aplicar look: {result.stderr[:200]}")

        return saida

    def _aplicar_lut_arquivo(self, video: Path, lut_arquivo: Path,
                              saida: Path, intensidade: float) -> Path:
        """Aplica LUT de arquivo .cube"""

        # FFmpeg lut3d nao suporta intensidade diretamente
        # Podemos usar blend para misturar

        if intensidade == 1.0:
            filtro = f"lut3d=file='{lut_arquivo}':interp=trilinear"
        else:
            # Mistura LUT com original usando blend
            filtro = (
                f"[0:v]split[a][b];"
                f"[a]lut3d=file='{lut_arquivo}':interp=trilinear[lut];"
                f"[b][lut]blend=all_mode=normal:all_opacity={intensidade}"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            str(saida)
        ]

        self.log(f"Aplicando LUT '{lut_arquivo.name}' (intensidade: {intensidade})...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"Erro: {result.stderr[:300]}")
            raise Exception(f"Falha ao aplicar LUT: {result.stderr[:200]}")

        return saida

    def _ajustar_intensidade_filtro(self, filtro: str, intensidade: float) -> str:
        """Ajusta intensidade de filtros eq/colorbalance"""

        # Para eq, ajusta os valores numericos
        if "eq=" in filtro:
            def ajustar_valor(match):
                param = match.group(1)
                valor = float(match.group(2))
                # Ajusta proporcionalmente a intensidade
                novo_valor = valor * intensidade
                return f"{param}={novo_valor:.3f}"

            filtro = re.sub(r'(contrast|saturation|brightness|gamma)=([\d.-]+)',
                           ajustar_valor, filtro)

        return filtro

    def obter_filtro_ffmpeg(self, lut_nome: str, intensidade: float = 1.0) -> str:
        """Retorna filtro FFmpeg para uso em filter_complex"""

        # Verifica LUT personalizada
        if lut_nome in self.luts_personalizadas:
            lut_arquivo = self.luts_personalizadas[lut_nome]
            if intensidade == 1.0:
                return f"lut3d=file='{lut_arquivo}':interp=trilinear"
            else:
                return (
                    f"split[a][b];"
                    f"[a]lut3d=file='{lut_arquivo}':interp=trilinear[lut];"
                    f"[b][lut]blend=all_mode=normal:all_opacity={intensidade}"
                )

        # Verifica look embutido
        for id_lut, info in self.LOOKS_EMBUTIDOS.items():
            if info["nome"] == lut_nome or id_lut == lut_nome:
                filtro = info["filtro"]
                if intensidade != 1.0:
                    filtro = self._ajustar_intensidade_filtro(filtro, intensidade)
                return filtro

        # Default
        return self.LOOKS_EMBUTIDOS["cinematic"]["filtro"]

    def gerar_preview_lut(self, lut_nome: str, imagem_base: Optional[Path] = None) -> Path:
        """Gera preview da LUT em imagem"""

        if imagem_base is None:
            # Usa imagem de teste padrao (grid de cores)
            imagem_base = self.temp_dir / "test_grid.png"
            self._criar_grid_teste(imagem_base)

        saida = self.temp_dir / f"preview_{lut_nome}.png"

        # Aplica LUT na imagem
        if lut_nome in self.luts_personalizadas:
            lut_arquivo = self.luts_personalizadas[lut_nome]
            cmd = [
                "ffmpeg", "-y",
                "-i", str(imagem_base),
                "-vf", f"lut3d=file='{lut_arquivo}':interp=trilinear",
                "-frames:v", "1",
                str(saida)
            ]
        else:
            filtro = self.obter_filtro_ffmpeg(lut_nome)
            cmd = [
                "ffmpeg", "-y",
                "-i", str(imagem_base),
                "-vf", filtro,
                "-frames:v", "1",
                str(saida)
            ]

        subprocess.run(cmd, capture_output=True)
        return saida

    def _criar_grid_teste(self, saida: Path):
        """Cria grid de cores para teste"""

        # Cria imagem com gradiente de cores para preview
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "testsrc2=size=1280x720:duration=1",
            "-frames:v", "1",
            str(saida)
        ]

        subprocess.run(cmd, capture_output=True)

    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
