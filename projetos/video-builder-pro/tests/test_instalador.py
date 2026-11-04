"""Testes do empacotamento/instalador. IDs [I01-I08] no CHANGELOG."""

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def home_isolado(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def test_I01_pasta_app_fonte_e_empacotado(monkeypatch, tmp_path):
    import ffmpeg_utils
    assert ffmpeg_utils.pasta_app() == RAIZ
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert ffmpeg_utils.pasta_app() == tmp_path


def test_I02_ffmpeg_embutido_vai_para_o_path(monkeypatch, tmp_path):
    import ffmpeg_utils
    monkeypatch.setattr(ffmpeg_utils, "pasta_app", lambda: tmp_path)
    assert ffmpeg_utils.preparar_ffmpeg_embutido() is None              # sem bin/: nao mexe no PATH
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")).write_text("x")
    monkeypatch.setenv("PATH", "/usr/bin")
    assert ffmpeg_utils.preparar_ffmpeg_embutido() == tmp_path / "bin"
    assert os.environ["PATH"].split(os.pathsep)[0] == str(tmp_path / "bin")


def test_I03_estilos_do_usuario_somam_e_sobrescrevem(home_isolado):
    import diretor_ia
    pasta = home_isolado / ".video_builder_pro" / "estilos"
    pasta.mkdir(parents=True)
    (pasta / "meu_estilo.json").write_text(json.dumps({"nome": "Meu"}), encoding="utf-8")
    (pasta / "reels_dinamico.json").write_text(json.dumps({"nome": "Reels editado", "duracao_alvo": 20}),
                                               encoding="utf-8")
    e = diretor_ia.carregar_estilos()
    assert e["meu_estilo"]["nome"] == "Meu"
    assert e["reels_dinamico"]["duracao_alvo"] == 20 and "youtube_educativo" in e


def test_I04_luts_da_pasta_do_usuario(home_isolado, log, midia):
    from luts_manager import LUTManager
    pasta = home_isolado / ".video_builder_pro" / "luts"
    pasta.mkdir(parents=True)
    shutil.copy(midia["cube"], pasta / "minha_lut.cube")
    assert "minha_lut" in LUTManager(log).luts_personalizadas


def test_I05_launcher_verificar(tmp_path):
    import fake_tk  # noqa: F401 - tkinter falso ja instalado pelo conftest
    import rodar_v78
    importlib.reload(rodar_v78)
    destino = tmp_path / "v.json"
    assert rodar_v78.verificar(str(destino)) == 0
    r = json.loads(destino.read_text(encoding="utf-8"))
    assert r["ok"] and r["versao_app"] and len(r["estilos"]) >= 4 and r["luts"] >= 15


def test_I06_gerar_icones(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    from PIL import Image
    sys.path.insert(0, str(RAIZ / "instalador"))
    import gerar_icones
    importlib.reload(gerar_icones)
    monkeypatch.setattr(gerar_icones, "ASSETS", tmp_path)
    monkeypatch.setattr(gerar_icones, "SAIDA", tmp_path / "gerados")
    with pytest.raises(SystemExit, match="Logotipo nao encontrado"):
        gerar_icones.gerar(sem_logo=False)                                # build oficial exige o logo
    saida = gerar_icones.gerar(sem_logo=True)
    assert (saida / "SEM_LOGO").exists()                                  # marcado como teste
    logo = Image.new("RGBA", (800, 300), (200, 30, 30, 255))             # logo retangular de exemplo
    logo.save(tmp_path / "logo_aggilli.png")
    saida = gerar_icones.gerar(sem_logo=True)
    assert not (saida / "SEM_LOGO").exists()                              # logo real presente
    ico = Image.open(saida / "icone.ico")
    assert (256, 256) in ico.info["sizes"] and (16, 16) in ico.info["sizes"]
    assert Image.open(saida / "assistente_grande.bmp").size == (164, 314)
    assert Image.open(saida / "assistente_pequeno_2x.bmp").size == (110, 116)
    png = Image.open(saida / "icone_256.png")
    assert png.size == (256, 256) and png.getpixel((0, 0))[3] == 0      # proporcao mantida, fundo transparente


def test_I07_versao_e_metadados_windows():
    sys.path.insert(0, str(RAIZ / "instalador"))
    import versao
    v = versao.versao()
    import video_builder_pro_v7_suite as base
    assert v == base.VERSAO
    txt = versao.gerar_versao_windows(v)
    try:
        conteudo = txt.read_text(encoding="utf-8")
        assert "Aggilli Intelligence" in conteudo and f"'{v}'" in conteudo
    finally:
        txt.unlink()


@pytest.mark.skipif(not shutil.which("dpkg-deb") or os.name == "nt", reason="dpkg-deb indisponivel")
def test_I08_build_deb(tmp_path):
    """Monta o .deb com um executavel falso (o PyInstaller real roda no CI)."""
    copia = tmp_path / "vbp"
    shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns("tests", "__pycache__", "dist", "build"))
    subprocess.run([sys.executable, str(copia / "instalador" / "gerar_icones.py"), "--sem-logo"], check=True)
    exe = copia / "dist" / "VideoBuilderPro" / "VideoBuilderPro"
    exe.parent.mkdir(parents=True)
    exe.write_text("#!/bin/sh\necho ok\n")
    exe.chmod(0o755)
    subprocess.run(["bash", str(copia / "instalador" / "build_deb.sh")], check=True, capture_output=True)
    deb = next((copia / "dist" / "instalador").glob("video-builder-pro_*_*.deb"))
    info = subprocess.run(["dpkg-deb", "-f", str(deb), "Package", "Version", "Depends"],
                          capture_output=True, text=True, check=True).stdout
    assert "video-builder-pro" in info and "ffmpeg" in info
    lista = subprocess.run(["dpkg-deb", "-c", str(deb)], capture_output=True, text=True, check=True).stdout
    for f in ("usr/bin/video-builder-pro", "usr/share/applications/video-builder-pro.desktop",
              "usr/share/icons/hicolor/256x256/apps/video-builder-pro.png",
              "opt/aggilli/video-builder-pro/VideoBuilderPro"):
        assert f in lista


def test_I09_icone_usa_simbolo_e_lateral_empilha(tmp_path, monkeypatch):
    """Logo horizontal: icone sai do SIMBOLO (legivel em 16 px); a lateral empilha simbolo + nome."""
    pytest.importorskip("PIL")
    from PIL import Image
    sys.path.insert(0, str(RAIZ / "instalador"))
    import gerar_icones
    importlib.reload(gerar_icones)
    monkeypatch.setattr(gerar_icones, "ASSETS", tmp_path)
    monkeypatch.setattr(gerar_icones, "SAIDA", tmp_path / "gerados")
    Image.new("RGBA", (900, 260), (255, 0, 0, 255)).save(tmp_path / "logo_aggilli.png")       # vermelho
    Image.new("RGBA", (300, 260), (0, 0, 255, 255)).save(tmp_path / "simbolo_aggilli.png")    # azul
    Image.new("RGBA", (600, 180), (0, 255, 0, 255)).save(tmp_path / "texto_aggilli.png")      # verde
    saida = gerar_icones.gerar()
    centro = Image.open(saida / "icone_256.png").getpixel((128, 128))
    assert centro[:3] == (0, 0, 255)                                   # icone = simbolo, nao o logo inteiro
    lat = Image.open(saida / "assistente_grande.bmp").convert("RGB")
    cores = {lat.getpixel((82, y)) for y in range(0, 314, 2)}
    assert (0, 0, 255) in cores and (0, 255, 0) in cores and (255, 0, 0) not in cores


def test_I10_logo_oficial_sem_linha_obras():
    """A pedido (03/11/2026): logo sem 'OBRAS INTELLIGENCE' (linha inferior removida)."""
    pytest.importorskip("PIL")
    from PIL import Image
    import numpy as np
    for nome in ("logo_aggilli.png", "simbolo_aggilli.png", "texto_aggilli.png"):
        assert (RAIZ / "assets" / nome).is_file(), nome
    a = np.array(Image.open(RAIZ / "assets" / "logo_aggilli.png"))
    assert (a[a[:, :, 3] == 0][:, :3] == 0).all()                     # nada escondido sob a transparencia
    linhas = np.where((a[:, 760:, 3] > 30).sum(1) > 0)[0]              # regiao do texto (direita)
    blocos = np.split(linhas, np.where(np.diff(linhas) > 3)[0] + 1)
    assert len(blocos) == 2                                            # so "AGGILLI" e "INTELLIGENCE"
