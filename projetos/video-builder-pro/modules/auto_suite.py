#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO SUITE - Video Builder Pro v7.7

Implementa os 5 modulos que o v76_patch.py importava mas que NAO existiam
no repositorio (auto_editor_ai, auto_color_ai, auto_audio_ai,
auto_caption_ai, auto_format_ai). Na v7.6 os botoes da aba "Auto-Edit
Suite" sempre falhavam com ImportError. Tudo aqui usa so FFmpeg (+ Whisper
para legendas), sem dependencias novas.

Sobre o "AI" nos nomes: sao automacoes baseadas em analise de sinal
(silencedetect, signalstats, EBU R128), nao modelos de IA - exceto as
legendas, que usam Whisper.
"""

import re
import statistics
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional

try:
    from ffmpeg_utils import (executar, executar_com_progresso, info_midia, detectar_silencios,
                              inverter_intervalos, normalizar_loudness, padrao_loudness)
    from transitions_gl import GLTransitionsEngine, GLTransition
    from subtitles_ai import SubtitlesAI
except ImportError:
    from .ffmpeg_utils import (executar, executar_com_progresso, info_midia, detectar_silencios,
                               inverter_intervalos, normalizar_loudness, padrao_loudness)
    from .transitions_gl import GLTransitionsEngine, GLTransition
    from .subtitles_ai import SubtitlesAI


# ======================================================================
class AutoEditorAI:
    """Corta silencios e (opcionalmente) aplica transicoes entre os trechos."""

    PADRAO = {"threshold_silencio": -35.0, "duracao_minima_silencio": 0.5,
              "remover_pausas": True, "adicionar_transicoes": True,
              "transicao_tipo": "fade", "transicao_duracao": 0.5, "manter_minimo": 1.0,
              "margem": 0.15}

    def __init__(self, log):
        self.log = log
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_autoai_"))

    def editar_automatico(self, video: Path, saida: Path, cfg: Optional[Dict] = None) -> Path:
        cfg = {**self.PADRAO, **(cfg or {})}
        video, saida = Path(video), Path(saida)
        info = info_midia(video)
        if not info["tem_audio"] or not cfg["remover_pausas"]:
            self.log("Sem audio (ou remocao desligada): nada a cortar, copiando.")
            shutil.copyfile(video, saida)
            return saida
        sil = detectar_silencios(video, cfg["threshold_silencio"], cfg["duracao_minima_silencio"])
        # margem: preserva um respiro antes/depois de cada fala
        m = cfg["margem"]
        sil = [(i + m, f - m) for i, f in sil if (f - m) - (i + m) > 0.1]
        trechos = [t for t in inverter_intervalos(sil, info["duracao"])
                   if t[1] - t[0] >= cfg["manter_minimo"]]
        if not trechos:
            raise ValueError("Nenhum trecho com fala acima do minimo configurado.")
        self.log(f"Mantendo {len(trechos)} trechos de {info['duracao']:.1f}s")

        dur_t = float(cfg["transicao_duracao"])
        usar_trans = (cfg["adicionar_transicoes"] and len(trechos) > 1 and
                      all(f - i > 2 * dur_t + 0.1 for i, f in trechos))
        filtros, rv, ra = [], [], []
        w, h = info["width"] - info["width"] % 2, info["height"] - info["height"] % 2
        fps = round(info["fps"] or 25, 3)
        for k, (i, f) in enumerate(trechos):
            filtros.append(f"[0:v]trim=start={i:.3f}:end={f:.3f},setpts=PTS-STARTPTS,"
                           f"scale={w}:{h},setsar=1,fps={fps},format=yuv420p,settb=AVTB[v{k}]")
            # micro fades de 10 ms evitam estalos nos cortes
            filtros.append(f"[0:a]atrim=start={i:.3f}:end={f:.3f},asetpts=PTS-STARTPTS,"
                           f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                           f"afade=t=in:d=0.01,afade=t=out:st={max(0, f - i - 0.01):.3f}:d=0.01,"
                           f"asettb=AVTB[a{k}]")
            rv.append(f"[v{k}]")
            ra.append(f"[a{k}]")
        if usar_trans:
            tipo = cfg["transicao_tipo"] if cfg["transicao_tipo"] in GLTransitionsEngine.TRANSICOES_GL else "fade"
            cadeia, fv, fa = GLTransitionsEngine(self.log).encadear(
                rv, ra, [f - i for i, f in trechos], [GLTransition(tipo, dur_t)] * (len(trechos) - 1))
            filtros += cadeia
        else:
            if cfg["adicionar_transicoes"] and len(trechos) > 1:
                self.log("Trechos curtos demais para transicoes: usando cortes secos.")
            filtros.append("".join(v + a for v, a in zip(rv, ra)) + f"concat=n={len(trechos)}:v=1:a=1[vf][af]")
            fv, fa = "[vf]", "[af]"
        script = self.temp_dir / "grafo.txt"
        script.write_text(";\n".join(filtros), encoding="utf-8")
        total = sum(f - i for i, f in trechos)
        executar_com_progresso(["ffmpeg", "-y", "-i", str(video), "-filter_complex_script", str(script),
                                "-map", fv, "-map", fa, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                "-movflags", "+faststart", str(saida)], self.log, total)
        self.log(f"[OK] Edicao automatica: {info['duracao']:.1f}s -> ~{total:.1f}s")
        return saida


# ======================================================================
class AutoColorAI:
    """Correcao automatica de exposicao, contraste e saturacao (signalstats)."""

    def __init__(self, log):
        self.log = log

    def analisar(self, video: Path, amostras_por_seg: float = 1.0) -> Dict[str, float]:
        r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an",
                      "-vf", f"fps={amostras_por_seg},signalstats,metadata=print:file=-",
                      "-f", "null", "-"])
        valores: Dict[str, List[float]] = {"YMIN": [], "YMAX": [], "YAVG": [], "SATAVG": []}
        for linha in r.stdout.splitlines():
            m = re.match(r"lavfi\.signalstats\.(YMIN|YMAX|YAVG|SATAVG)=([\d.]+)", linha.strip())
            if m:
                valores[m.group(1)].append(float(m.group(2)))
        if not valores["YAVG"]:
            raise RuntimeError("Nao foi possivel analisar o video (sem quadros?).")
        return {k: statistics.median(v) for k, v in valores.items() if v}

    def calcular_correcao(self, a: Dict[str, float]) -> Dict[str, float]:
        """Leva a faixa util para ~16..235, media para ~110 e saturacao para ~45."""
        faixa = max(20.0, a["YMAX"] - a["YMIN"])
        contraste = min(1.5, max(0.85, 200.0 / faixa))
        brilho = min(0.15, max(-0.15, (110.0 - a["YAVG"]) / 255.0 * 0.6))
        sat = min(1.4, max(0.85, 45.0 / max(5.0, a.get("SATAVG", 45.0)))) if a.get("SATAVG") else 1.0
        return {"contrast": round(contraste, 3), "brightness": round(brilho, 3), "saturation": round(sat, 3)}

    def aplicar_color_auto(self, video: Path, saida: Path, modo: str = "auto") -> Path:
        self.log("Analisando cor/exposicao...")
        a = self.analisar(Path(video))
        c = self.calcular_correcao(a)
        self.log(f"  Y medio {a['YAVG']:.0f}, faixa {a['YMIN']:.0f}-{a['YMAX']:.0f} -> "
                 f"contraste {c['contrast']}, brilho {c['brightness']:+}, saturacao {c['saturation']}")
        info = info_midia(Path(video))
        cmd = ["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0",
               "-vf", f"eq=contrast={c['contrast']}:brightness={c['brightness']}:saturation={c['saturation']}",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        cmd += ["-map", "0:a:0", "-c:a", "copy"] if info["tem_audio"] else []
        executar_com_progresso(cmd + [str(saida)], self.log, info["duracao"])
        return Path(saida)


# ======================================================================
class AutoAudioAI:
    """Limpeza leve + normalizacao EBU R128 em 2 passadas para o padrao escolhido."""

    def __init__(self, log):
        self.log = log

    def mixar_automatico(self, video: Path, saida: Path, padrao: str = "YouTube") -> Path:
        alvo, tp = padrao_loudness(padrao)
        self.log(f"Mixagem automatica: passa-altas 70 Hz + compressor leve + loudnorm {alvo} LUFS / {tp} dBTP")
        filtros_pre = "highpass=f=70,acompressor=threshold=-18dB:ratio=2.5:attack=20:release=250:makeup=1"
        return normalizar_loudness(Path(video), Path(saida), alvo, tp, self.log, filtros_pre)


# ======================================================================
class AutoCaptionAI:
    """Whisper -> SRT -> legenda queimada com estilo pronto."""

    ESTILOS = {
        "simples": {"tamanho": 22, "cor": "white", "borda": "black", "largura_borda": 2},
        "destaque": {"tamanho": 30, "cor": "white", "borda": "black", "largura_borda": 4},
        "amarelo": {"tamanho": 26, "cor": "yellow", "borda": "black", "largura_borda": 3},
    }

    def __init__(self, log):
        self.log = log
        self.subs = SubtitlesAI(log)

    def gerar_legendas_auto(self, video: Path, saida: Path, idioma: str = "pt",
                            modelo: str = "base", estilo: str = "simples") -> Path:
        srt = Path(saida).with_suffix(".srt")
        self.subs.gerar_legendas(Path(video), idioma, modelo, "srt", saida=srt)
        self.subs.queimar_legendas_no_video(Path(video), srt, Path(saida),
                                            self.ESTILOS.get(estilo, self.ESTILOS["simples"]))
        self.log(f"[OK] SRT mantido em {srt}")
        return Path(saida)


# ======================================================================
class AutoFormatAI:
    """Gera versoes para cada plataforma (video inteiro sobre fundo desfocado)."""

    PLATAFORMAS = {
        "youtube_16x9": (1920, 1080),
        "reels_tiktok_shorts_9x16": (1080, 1920),
        "instagram_feed_4x5": (1080, 1350),
        "quadrado_1x1": (1080, 1080),
    }

    def __init__(self, log):
        self.log = log

    def converter(self, video: Path, saida: Path, w: int, h: int) -> Path:
        info = info_midia(Path(video))
        filtro = (f"[0:v]split[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
                  f"crop={w}:{h},boxblur=20:5[b];[fg]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                  f"scale=trunc(iw/2)*2:trunc(ih/2)*2[f];[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1[vout]")
        cmd = ["ffmpeg", "-y", "-i", str(video), "-filter_complex", filtro, "-map", "[vout]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart"]
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"] if info["tem_audio"] else ["-an"]
        executar_com_progresso(cmd + [str(saida)], self.log, info["duracao"])
        return Path(saida)

    def converter_todas_plataformas(self, video: Path, pasta: Path) -> List[Path]:
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        saidas = []
        for nome, (w, h) in self.PLATAFORMAS.items():
            destino = pasta / f"{Path(video).stem}_{nome}.mp4"
            self.log(f"Gerando {nome} ({w}x{h})...")
            saidas.append(self.converter(Path(video), destino, w, h))
        return saidas
