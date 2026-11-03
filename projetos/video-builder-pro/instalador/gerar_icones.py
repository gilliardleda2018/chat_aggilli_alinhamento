#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera todos os icones e imagens do instalador a partir do logotipo da Aggilli.

Entrada (coloque o arquivo oficial aqui):
    assets/logo_aggilli.png    PNG, de preferencia fundo transparente, >= 512 px
    (ou assets/logo_aggilli.svg, convertido com rsvg-convert se disponivel)

Saida (assets/gerados/, recriada a cada build):
    icone.ico                  Windows: 16, 24, 32, 48, 64, 128, 256 px
    icone_256.png / _512.png   Linux (menu) e janela do app
    assistente_grande.bmp      Inno Setup: imagem lateral (164x314 e @2x 328x628)
    assistente_pequeno.bmp     Inno Setup: canto do cabecalho (55x58 e @2x 110x116)

Build de teste sem o logo oficial:
    python gerar_icones.py --sem-logo
gera um monograma neutro "VB" (sem nenhuma marca) e grava assets/gerados/SEM_LOGO,
para o CI recusar publicar uma release assim.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
SAIDA = ASSETS / "gerados"
COR_FUNDO = (18, 24, 38)         # fundo escuro neutro das imagens do assistente
TAMANHOS_ICO = [16, 24, 32, 48, 64, 128, 256]


def carregar_logo(sem_logo: bool) -> Image.Image:
    png, svg = ASSETS / "logo_aggilli.png", ASSETS / "logo_aggilli.svg"
    if png.is_file():
        return Image.open(png).convert("RGBA")
    if svg.is_file():
        if not shutil.which("rsvg-convert"):
            sys.exit("logo_aggilli.svg encontrado, mas 'rsvg-convert' nao esta instalado. Exporte um PNG.")
        tmp = SAIDA / "_logo_svg.png"
        subprocess.run(["rsvg-convert", "-w", "1024", "-o", str(tmp), str(svg)], check=True)
        return Image.open(tmp).convert("RGBA")
    if not sem_logo:
        sys.exit(f"Logotipo nao encontrado. Coloque o arquivo oficial em {png} (ou .svg).\n"
                 "Para um build de TESTE sem marca: python gerar_icones.py --sem-logo")
    return monograma_neutro()


def monograma_neutro(lado: int = 1024) -> Image.Image:
    """Placeholder SEM marca: circulo cinza com 'VB'. Nao representa a Aggilli."""
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((40, 40, lado - 40, lado - 40), fill=(90, 98, 112, 255))
    try:
        fonte = ImageFont.truetype("DejaVuSans-Bold.ttf", int(lado * 0.38))
    except OSError:
        fonte = ImageFont.load_default(int(lado * 0.38)) if hasattr(ImageFont, "load_default") else None
    d.text((lado / 2, lado / 2), "VB", fill=(255, 255, 255, 255), font=fonte, anchor="mm")
    return img


def quadrado(logo: Image.Image, lado: int, margem: float = 0.06) -> Image.Image:
    """Logo centralizado num quadrado transparente, sem distorcer."""
    util = int(lado * (1 - 2 * margem))
    l = logo.copy()
    l.thumbnail((util, util), Image.LANCZOS)
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.paste(l, ((lado - l.width) // 2, (lado - l.height) // 2), l)
    return tela


def em_fundo(logo: Image.Image, w: int, h: int, ocupacao: float, posicao_y: float = 0.5) -> Image.Image:
    """Logo sobre fundo solido (BMP do Inno Setup nao tem transparencia)."""
    tela = Image.new("RGB", (w, h), COR_FUNDO)
    l = logo.copy()
    l.thumbnail((int(w * ocupacao), int(h * ocupacao)), Image.LANCZOS)
    tela.paste(l, ((w - l.width) // 2, int(h * posicao_y - l.height / 2)), l)
    return tela


def gerar(sem_logo: bool = False) -> Path:
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir(parents=True)
    logo = carregar_logo(sem_logo)
    if logo.width < 256 or logo.height < 64:
        print(f"[AVISO] logo pequeno ({logo.width}x{logo.height}): o icone pode ficar borrado. Use >= 512 px.")

    base = quadrado(logo, 512)
    base.save(SAIDA / "icone_512.png")
    quadrado(logo, 256).save(SAIDA / "icone_256.png")
    base.save(SAIDA / "icone.ico", sizes=[(t, t) for t in TAMANHOS_ICO])
    # Inno Setup 6 escolhe a melhor resolucao para o DPI da tela entre as listadas
    for nome, (w, h), ocup, y in (("assistente_grande", (164, 314), 0.8, 0.42),
                                  ("assistente_pequeno", (55, 58), 0.9, 0.5)):
        em_fundo(logo, w, h, ocup, y).save(SAIDA / f"{nome}.bmp")
        em_fundo(logo, w * 2, h * 2, ocup, y).save(SAIDA / f"{nome}_2x.bmp")
    if sem_logo and not (ASSETS / "logo_aggilli.png").is_file() and not (ASSETS / "logo_aggilli.svg").is_file():
        (SAIDA / "SEM_LOGO").write_text("Build de teste com monograma neutro. Nao publicar.\n", encoding="utf-8")
        print("[AVISO] Gerado com monograma neutro (build de teste, sem logotipo oficial).")
    print(f"[OK] Icones em {SAIDA}")
    return SAIDA


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sem-logo", action="store_true", help="build de teste com monograma neutro")
    gerar(ap.parse_args().sem_logo)
