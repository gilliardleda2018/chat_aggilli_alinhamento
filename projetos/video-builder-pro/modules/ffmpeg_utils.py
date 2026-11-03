#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFMPEG UTILS - Video Builder Pro v7.7

Funcoes comuns usadas por todos os modulos. Criado na v7.7 para eliminar
duplicacoes da v7.6 (3 copias de _obter_duracao, 2 parsers de silencedetect,
2 calculos de MD5) e corrigir dois defeitos sistemicos:

  * subprocess.run sem checagem de returncode (falhas silenciosas);
  * caminhos com ':' , '\\' ou apostrofo quebrando filtros (lut3d, subtitles).

Tambem centraliza o logging em arquivo (~/.video_builder_pro/logs/).
"""

import hashlib
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# Em Windows, evita abrir uma janela de console para cada ffmpeg/ffprobe.
_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


class FFmpegErro(RuntimeError):
    """Falha de um comando ffmpeg/ffprobe, com o final do stderr."""

    def __init__(self, cmd: Sequence[str], returncode: int, stderr: str):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stderr = stderr or ""
        resumo = self.stderr.strip().splitlines()[-3:]
        super().__init__(f"{Path(cmd[0]).name} falhou (codigo {returncode}): " + " | ".join(resumo))


# ------------------------------------------------------------------ pastas do app
def pasta_app() -> Path:
    """Raiz do app, em codigo-fonte ou empacotado (PyInstaller).

    Fonte:        .../video-builder-pro/          (modules/ fica aqui dentro)
    Empacotado:   sys._MEIPASS (pasta _internal do PyInstaller onedir)
    v7.8: antes cada modulo usava Path(__file__).parent.parent, que aponta
    para fora do pacote quando o app esta instalado (estilos/luts/bin sumiam).
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def preparar_ffmpeg_embutido() -> Optional[Path]:
    """Se o instalador trouxe FFmpeg em <app>/bin, coloca-o na frente do PATH.
    Retorna a pasta usada (ou None se nao houver binarios embutidos)."""
    pasta = pasta_app() / "bin"
    nome = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if (pasta / nome).is_file():
        caminhos = os.environ.get("PATH", "").split(os.pathsep)
        if str(pasta) not in caminhos:
            os.environ["PATH"] = os.pathsep.join([str(pasta), *caminhos])
        return pasta
    return None


# ------------------------------------------------------------------ logging
_LOGGER_PRONTO = False


def diretorio_config() -> Path:
    """~/.video_builder_pro, criado com permissao 700 (so o dono acessa)."""
    d = Path.home() / ".video_builder_pro"
    d.mkdir(parents=True, exist_ok=True)
    proteger(d, 0o700)
    return d


def obter_logger() -> logging.Logger:
    """Logger 'vbp' com arquivo rotativo (5 x 1 MB) em ~/.video_builder_pro/logs."""
    global _LOGGER_PRONTO
    logger = logging.getLogger("vbp")
    if _LOGGER_PRONTO:
        return logger
    logger.setLevel(logging.DEBUG)
    try:
        pasta = diretorio_config() / "logs"
        pasta.mkdir(exist_ok=True)
        h = logging.handlers.RotatingFileHandler(
            pasta / "video_builder.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
        logger.addHandler(h)
    except OSError as e:  # disco cheio / sem permissao: segue so com stderr
        print(f"[AVISO] log em arquivo indisponivel: {e}", file=sys.stderr)
    _LOGGER_PRONTO = True
    return logger


def proteger(caminho: Path, modo: int = 0o600) -> bool:
    """Aplica chmod restritivo em POSIX. Retorna True se ficou protegido."""
    if os.name == "nt":
        return True  # ACLs do perfil do usuario ja isolam o arquivo
    try:
        os.chmod(caminho, modo)
        return True
    except OSError:
        return False


def permissao_aberta(caminho: Path) -> bool:
    """True se grupo/outros podem ler o arquivo (ex.: 644)."""
    if os.name == "nt" or not caminho.exists():
        return False
    return bool(caminho.stat().st_mode & 0o077)


# ------------------------------------------------------------------ execucao
def binario(nome: str) -> Optional[str]:
    return shutil.which(nome)


def executar(cmd: Sequence[str], log: Optional[Callable] = None,
             timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """Executa e levanta FFmpegErro se o returncode != 0."""
    cmd = [str(c) for c in cmd]
    obter_logger().debug("exec: %s", " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, **_FLAGS)
    except FileNotFoundError as e:
        raise FFmpegErro(cmd, -1, f"programa nao encontrado: {cmd[0]} ({e})") from e
    if r.returncode != 0:
        err = FFmpegErro(cmd, r.returncode, r.stderr)
        obter_logger().error("%s\n%s", err, r.stderr[-2000:])
        if log:
            log(f"[ERRO] {err}")
        raise err
    return r


def executar_com_progresso(cmd: Sequence[str], log: Callable, duracao_total: float = 0.0) -> None:
    """Roda ffmpeg lendo o progresso (-progress pipe:1) e logando a porcentagem."""
    cmd = [str(c) for c in cmd]
    if "-progress" not in cmd:
        cmd = [cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]]
    obter_logger().debug("exec: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", **_FLAGS)
    ultimo = -10
    stderr_linhas: List[str] = []

    import threading

    def _ler_err():
        for linha in proc.stderr:
            stderr_linhas.append(linha)
            del stderr_linhas[:-200]
    t = threading.Thread(target=_ler_err, daemon=True)
    t.start()
    for linha in proc.stdout:
        if linha.startswith("out_time_us=") and duracao_total > 0:
            try:
                seg = int(linha.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            pct = int(min(100, seg / duracao_total * 100))
            if pct >= ultimo + 10:
                ultimo = pct
                log(f"  progresso: {pct}%")
    proc.wait()
    t.join(timeout=5)
    if proc.returncode != 0:
        err = FFmpegErro(cmd, proc.returncode, "".join(stderr_linhas))
        obter_logger().error("%s\n%s", err, "".join(stderr_linhas)[-2000:])
        raise err


# ------------------------------------------------------------------ ffprobe
def info_midia(video: Path) -> Dict:
    """width, height, fps, duracao, tem_audio, tem_video, sample_rate, bit_rate."""
    r = executar(["ffprobe", "-v", "error", "-print_format", "json",
                  "-show_streams", "-show_format", str(video)])
    dados = json.loads(r.stdout or "{}")
    info = {"tem_video": False, "tem_audio": False, "width": 0, "height": 0, "fps": 0.0,
            "duracao": 0.0, "codec": "", "sample_rate": 0, "bit_rate": 0,
            "duracao_video": 0.0, "duracao_audio": 0.0}
    fmt = dados.get("format", {})
    try:
        info["duracao"] = float(fmt.get("duration", 0) or 0)
        info["bit_rate"] = int(fmt.get("bit_rate", 0) or 0)
    except ValueError:
        pass
    for s in dados.get("streams", []):
        if s.get("codec_type") == "video" and not info["tem_video"] \
                and s.get("disposition", {}).get("attached_pic", 0) == 0:
            info["tem_video"] = True
            info["width"] = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
            info["codec"] = s.get("codec_name", "")
            info["fps"] = _fracao(s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1")
            info["duracao_video"] = float(s.get("duration", 0) or 0)
        elif s.get("codec_type") == "audio" and not info["tem_audio"]:
            info["tem_audio"] = True
            info["sample_rate"] = int(s.get("sample_rate", 0) or 0)
            info["duracao_audio"] = float(s.get("duration", 0) or 0)
    if not info["duracao"]:
        info["duracao"] = max(info["duracao_video"], info["duracao_audio"])
    info["duracao_video"] = info["duracao_video"] or (info["duracao"] if info["tem_video"] else 0.0)
    info["duracao_audio"] = info["duracao_audio"] or (info["duracao"] if info["tem_audio"] else 0.0)
    return info


def _fracao(txt: str) -> float:
    try:
        n, d = txt.split("/") if "/" in txt else (txt, "1")
        return float(n) / float(d) if float(d) else 0.0
    except ValueError:
        return 0.0


def duracao(video: Path) -> float:
    d = info_midia(video)["duracao"]
    if d <= 0:
        raise FFmpegErro(["ffprobe", str(video)], 1, "duracao indisponivel (arquivo invalido?)")
    return d


# ------------------------------------------------------------------ analises
_RE_SIL_INI = re.compile(r"silence_start:\s*(-?[\d.]+)")
_RE_SIL_FIM = re.compile(r"silence_end:\s*([\d.]+)")


def detectar_silencios(midia: Path, threshold_db: float = -35.0,
                       duracao_minima: float = 0.5) -> List[Tuple[float, float]]:
    """Lista (inicio, fim) de silencios. Arquivo sem audio -> lista vazia."""
    if not info_midia(midia)["tem_audio"]:
        return []
    r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(midia), "-vn",
                  "-af", f"silencedetect=noise={threshold_db}dB:d={duracao_minima}",
                  "-f", "null", "-"])
    silencios, ini = [], None
    for linha in r.stderr.splitlines():
        m = _RE_SIL_INI.search(linha)
        if m:
            ini = max(0.0, float(m.group(1)))
            continue
        m = _RE_SIL_FIM.search(linha)
        if m and ini is not None:
            silencios.append((ini, float(m.group(1))))
            ini = None
    if ini is not None:  # silencio ate o fim do arquivo
        silencios.append((ini, duracao(midia)))
    return silencios


def inverter_intervalos(intervalos: List[Tuple[float, float]], total: float,
                        minimo: float = 0.05) -> List[Tuple[float, float]]:
    """Complemento de intervalos em [0, total] (ex.: silencios -> trechos com som)."""
    res, cursor = [], 0.0
    for ini, fim in sorted(intervalos):
        if ini - cursor > minimo:
            res.append((cursor, ini))
        cursor = max(cursor, fim)
    if total - cursor > minimo:
        res.append((cursor, total))
    return res


def medir_loudness(midia: Path) -> Dict[str, Optional[float]]:
    """Medicao EBU R128 real: integrado (LUFS), LRA (LU) e true peak (dBTP).

    Retorna None nos campos quando o arquivo nao tem audio (antes a v7.6
    devolvia -23.0 fixo e o QC aprovava video mudo).
    """
    vazio = {"integrado": None, "lra": None, "true_peak": None}
    if not info_midia(midia)["tem_audio"]:
        return vazio
    r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(midia), "-vn",
                  "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return vazio
    d = json.loads(m.group(0))

    def _f(k):
        try:
            v = float(d[k])
            return None if v in (float("inf"), float("-inf")) else v
        except (KeyError, ValueError):
            return None
    return {"integrado": _f("input_i"), "lra": _f("input_lra"), "true_peak": _f("input_tp")}


# Alvos de loudness (LUFS integrado, true peak maximo em dBTP)
PADROES_LOUDNESS = {
    "EBU R128": (-23.0, -1.0),
    "ATSC A/85": (-24.0, -2.0),
    "YouTube": (-14.0, -1.0),
    "Spotify": (-14.0, -1.0),
    "Podcast": (-16.0, -1.0),
    "Netflix": (-27.0, -2.0),
}


def padrao_loudness(nome: str) -> Tuple[float, float]:
    """Aceita 'YouTube', 'YouTube (-14 LUFS)', 'ebu r128'..."""
    chave = (nome or "").split("(")[0].strip().lower()
    for k, v in PADROES_LOUDNESS.items():
        if k.lower() == chave:
            return v
    return PADROES_LOUDNESS["EBU R128"]


def filtro_loudnorm(midia: Path, alvo_lufs: float, tp: float = -1.0, lra: float = 11.0) -> str:
    """1a passada do loudnorm: mede e devolve o filtro da 2a passada (linear)."""
    r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(midia), "-vn",
                  "-af", f"loudnorm=I={alvo_lufs}:TP={tp}:LRA={lra}:print_format=json",
                  "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return f"loudnorm=I={alvo_lufs}:TP={tp}:LRA={lra}"
    d = json.loads(m.group(0))
    if any(d.get(k) in ("-inf", "inf") for k in ("input_i", "input_tp", "input_thresh")):
        return "anull"  # audio digitalmente mudo: nada a normalizar
    return (f"loudnorm=I={alvo_lufs}:TP={tp}:LRA={lra}:measured_I={d['input_i']}:"
            f"measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:"
            f"measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true")


def normalizar_loudness(entrada: Path, saida: Path, alvo_lufs: float, tp: float = -1.0,
                        log: Optional[Callable] = None, filtros_pre: str = "") -> Path:
    """Normaliza em 2 passadas para o alvo (LUFS). Video copiado sem reencode."""
    info = info_midia(Path(entrada))
    if not info["tem_audio"]:
        raise ValueError(f"'{Path(entrada).name}' nao tem audio para normalizar.")
    ln = filtro_loudnorm(Path(entrada), alvo_lufs, tp)
    # o loudnorm acrescenta ~0,1 s de cauda: corta na duracao original do audio
    # (sem isso o audio ficava maior que o video e o QC acusava quadros faltando)
    corte = f"atrim=duration={info['duracao_audio']:.3f}" if info["duracao_audio"] else ""
    af = ",".join(f for f in (filtros_pre, ln, corte, "aresample=48000") if f)
    codec = {".mp3": ["libmp3lame", "-b:a", "192k"], ".wav": ["pcm_s16le"], ".flac": ["flac"]}.get(
        Path(saida).suffix.lower(), ["aac", "-b:a", "192k"])
    cmd = ["ffmpeg", "-y", "-i", str(entrada), "-map", "0:a:0", "-af", af, "-c:a", *codec]
    if info["tem_video"] and Path(saida).suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v"):
        cmd += ["-map", "0:v:0", "-c:v", "copy"]
    executar(cmd + [str(saida)], log)
    return Path(saida)


def md5_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(caminho, "rb") as f:
        for chunk in iter(lambda: f.read(bloco), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ filtros
def escapar_caminho_filtro(caminho: Path) -> str:
    """Escapa um caminho para uso DENTRO de um filtro (lut3d=file=..., subtitles=...).

    O filtergraph tem dois niveis de escape (ver docs do FFmpeg, "Notes on
    filtergraph escaping"):
      1. valor da opcao do filtro: escapa  \\  '  :
      2. descricao do filtergraph: escapa  \\  '  [  ]  ,  ;
    O resultado vai SEM aspas. Funciona com 'C:\\Users\\...' e "Joao's.srt".
    """
    s = str(Path(caminho).resolve()).replace("\\", "/")
    for ch in ("\\", "'", ":"):          # nivel 1
        s = s.replace(ch, "\\" + ch)
    for ch in ("\\", "'", "[", "]", ",", ";"):  # nivel 2
        s = s.replace(ch, "\\" + ch)
    return s


def escapar_concat(caminho: Path) -> str:
    """Linha 'file ...' segura para o concat demuxer (apostrofos)."""
    return "file '" + str(Path(caminho).resolve()).replace("'", "'\\''") + "'"


def cadeia_atempo(velocidade: float) -> str:
    """atempo so aceita 0.5..2.0 em FFmpeg antigos: decompoe em cadeia."""
    if velocidade <= 0:
        raise ValueError("velocidade deve ser > 0")
    partes, v = [], velocidade
    while v > 2.0:
        partes.append("atempo=2.0")
        v /= 2.0
    while v < 0.5:
        partes.append("atempo=0.5")
        v /= 0.5
    partes.append(f"atempo={v:.6f}")
    return ",".join(partes)


def abrir_no_player(caminho: Path, inicio: float = 0.0) -> str:
    """Abre o video: ffplay se existir; senao o player padrao do sistema."""
    if binario("ffplay"):
        cmd = ["ffplay", "-autoexit", "-loglevel", "error", "-window_title", Path(caminho).name]
        if inicio > 0:
            cmd += ["-ss", f"{inicio:.3f}"]
        subprocess.Popen(cmd + [str(caminho)], **_FLAGS)
        return "ffplay"
    if os.name == "nt":
        os.startfile(str(caminho))  # type: ignore[attr-defined]
        return "padrao"
    abridor = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([abridor, str(caminho)])
    return abridor
