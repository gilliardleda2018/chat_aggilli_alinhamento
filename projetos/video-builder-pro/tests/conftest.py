"""Fixtures compartilhadas dos testes do Video Builder Pro.

Toda midia de teste e sintetica (FFmpeg lavfi), gerada uma vez por sessao.
Nenhum teste depende de arquivos externos, GPU, rede ou chave de API.
"""

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "modules"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Tkinter nao existe em servidores de CI; o stub permite importar a UI.
import fake_tk  # noqa: E402

fake_tk.instalar()


def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def midia(tmp_path_factory):
    d = tmp_path_factory.mktemp("midia")
    m = {}

    # 1280x720 25fps, 3s, com tom de 440 Hz
    m["hd_audio"] = d / "hd_audio.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=25:d=3",
        "-f", "lavfi", "-i", "sine=f=440:d=3",
        "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(m["hd_audio"]))

    # 640x480 30fps, 3s, SEM audio (formato diferente de proposito)
    m["sd_mudo"] = d / "sd mudo's.mp4"  # espaco + apostrofo no nome
    _ff("-f", "lavfi", "-i", "testsrc2=s=640x480:r=30:d=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(m["sd_mudo"]))

    # Fala sintetica: 2s tom, 2s silencio, 2s tom
    m["com_silencio"] = d / "com_silencio.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=6",
        "-f", "lavfi", "-i",
        "sine=f=300:d=6,volume='if(between(t,2,4),0,1)':eval=frame",
        "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-g", "250",
        "-pix_fmt", "yuv420p", "-c:a", "aac", str(m["com_silencio"]))

    # Duas cenas (vermelho -> azul) para deteccao de corte
    m["duas_cenas"] = d / "duas_cenas.mp4"
    _ff("-f", "lavfi", "-i", "color=red:s=320x240:r=25:d=2",
        "-f", "lavfi", "-i", "color=blue:s=320x240:r=25:d=2",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(m["duas_cenas"]))

    # Preto no inicio (1s) para o QC detectar black frames
    m["com_preto"] = d / "com_preto.mp4"
    _ff("-f", "lavfi", "-i", "color=black:s=320x240:r=25:d=1",
        "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=2",
        "-f", "lavfi", "-i", "sine=d=3",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
        "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(m["com_preto"]))

    # SRT simples
    m["srt"] = d / "legenda.srt"
    m["srt"].write_text("1\n00:00:00,000 --> 00:00:02,000\nOla mundo\n\n", encoding="utf-8")

    # LUT .cube identidade 2x2x2
    m["cube"] = d / "ident.cube"
    linhas = ["LUT_3D_SIZE 2"]
    for b in (0, 1):
        for g in (0, 1):
            for r in (0, 1):
                linhas.append(f"{r} {g} {b}")
    m["cube"].write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return m


def probe(caminho):
    """Retorna dict com streams e duracao (para asserts)."""
    import json
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(caminho)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def duracoes(caminho):
    info = probe(caminho)
    res = {}
    for s in info["streams"]:
        res[s["codec_type"]] = float(s.get("duration", info["format"]["duration"]))
    return res


@pytest.fixture
def log():
    mensagens = []

    def _log(msg):
        mensagens.append(str(msg))
    _log.mensagens = mensagens
    return _log
