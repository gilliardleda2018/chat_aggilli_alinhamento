#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO EDITOR - Video Builder Pro v7.7
Remove silencios automaticamente e detecta cortes de cena.
Baseado em: github.com/Muzamil4266/Python-auto-video-editor

Correcoes v7.7 (ver CHANGELOG.md, secao "auto_editor.py"):
  - Cortes com "-ss depois de -i" + "-c copy" caiam no keyframe anterior
    (trechos imprecisos/congelados). Agora o corte e feito num unico filtro
    (trim/atrim + concat) com reencode: preciso ao frame.
  - returncode de cada ffmpeg agora e verificado (antes falhava em silencio
    e concatenava segmentos vazios).
  - Video sem audio nao quebra mais (antes o silencedetect falhava).
  - Novo detectar_cenas(): devolve cenas [{inicio, fim}] - a UI v7.6
    chamava c.get('inicio') sobre floats e quebrava.
  - aplicar_edicao_automatica usava o filtro inexistente 'abremoveloud'.
  - Diretorio temporario removido com cleanup() explicito (alem do __del__).
"""

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from ffmpeg_utils import (executar, info_midia, duracao as _duracao,
                              detectar_silencios as _detectar_silencios,
                              inverter_intervalos, executar_com_progresso)
except ImportError:  # importado como pacote (modules.auto_editor)
    from .ffmpeg_utils import (executar, info_midia, duracao as _duracao,
                               detectar_silencios as _detectar_silencios,
                               inverter_intervalos, executar_com_progresso)


@dataclass
class EditDecision:
    """Decisao de edicao automatica"""
    tipo: str  # "remover_silencio", "corte_cena", "manter"
    inicio: float
    fim: float
    duracao: float
    descricao: str = ""


class AutoEditor:
    """Editor automatico com deteccao de silencio e cortes"""

    def __init__(self, log_callback):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_autoedit_"))

    # ------------------------------------------------------------ deteccao
    def detectar_silencios(self, video: Path,
                           threshold_db: float = -35.0,
                           duracao_minima: float = 0.5) -> List[Tuple[float, float]]:
        """Detecta silencios no video usando FFmpeg silencedetect"""
        self.log(f"Detectando silencios (threshold: {threshold_db}dB, min: {duracao_minima}s)...")
        silencios = _detectar_silencios(Path(video), threshold_db, duracao_minima)
        self.log(f"Encontrados {len(silencios)} silencios")
        return silencios

    def detectar_cortes_cena(self, video: Path, threshold: float = 0.3) -> List[float]:
        """Tempos (s) em que ha corte de cena. Mantido como List[float] (API v7.3)."""
        self.log(f"Detectando cortes de cena (threshold: {threshold})...")
        r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an",
                      "-vf", f"select='gt(scene,{threshold})',showinfo",
                      "-f", "null", "-"])
        cortes = []
        for linha in r.stderr.splitlines():
            if "Parsed_showinfo" in linha:
                m = re.search(r"pts_time:\s*([\d.]+)", linha)
                if m:
                    cortes.append(float(m.group(1)))
        self.log(f"Encontrados {len(cortes)} cortes de cena")
        return cortes

    def detectar_cenas(self, video: Path, threshold: float = 0.3) -> List[Dict[str, float]]:
        """Cenas completas [{'inicio','fim','duracao'}] a partir dos cortes."""
        total = _duracao(Path(video))
        pontos = [0.0] + [c for c in self.detectar_cortes_cena(video, threshold) if 0 < c < total] + [total]
        cenas = []
        for ini, fim in zip(pontos, pontos[1:]):
            if fim - ini > 0.04:  # ignora cortes duplicados no mesmo frame
                cenas.append({"inicio": ini, "fim": fim, "duracao": fim - ini})
        return cenas

    def gerar_decisoes_edicao(self, video: Path,
                              remover_silencios: bool = True,
                              threshold_silencio: float = -35.0,
                              duracao_minima_silencio: float = 0.5,
                              detectar_cortes: bool = True,
                              threshold_cena: float = 0.3) -> List[EditDecision]:
        """Gera lista de decisoes de edicao"""
        decisoes = []
        if remover_silencios:
            for ini, fim in self.detectar_silencios(video, threshold_silencio, duracao_minima_silencio):
                decisoes.append(EditDecision("remover_silencio", ini, fim, fim - ini,
                                             f"Remover silencio ({fim - ini:.1f}s)"))
        if detectar_cortes:
            for t in self.detectar_cortes_cena(video, threshold_cena):
                decisoes.append(EditDecision("corte_cena", t, t + 0.1, 0.1, "Corte de cena detectado"))
        decisoes.sort(key=lambda d: d.inicio)
        return decisoes

    # ------------------------------------------------------------ aplicacao
    def aplicar_edicao_automatica(self, video: Path, saida: Path,
                                  decisoes: List[EditDecision],
                                  manter_audio_original: bool = False) -> Path:
        """Remove os trechos marcados como 'remover_silencio'."""
        silencios = [(d.inicio, d.fim) for d in decisoes if d.tipo == "remover_silencio"]
        return self._manter_trechos(Path(video), Path(saida),
                                    inverter_intervalos(silencios, _duracao(Path(video))))

    def cortar_em_segmentos(self, video: Path, decisoes: List[EditDecision]) -> List[Path]:
        """Corta o video em arquivos separados nos cortes de cena (precisao de frame)."""
        total = _duracao(Path(video))
        pontos = sorted({0.0, total, *[d.inicio for d in decisoes if d.tipo == "corte_cena"]})
        tem_audio = info_midia(Path(video))["tem_audio"]
        segmentos = []
        for i, (ini, fim) in enumerate(zip(pontos, pontos[1:])):
            if fim - ini <= 0.5:
                continue
            seg = self.temp_dir / f"segmento_{i:03d}.mp4"
            cmd = ["ffmpeg", "-y", "-ss", f"{ini:.3f}", "-i", str(video), "-t", f"{fim - ini:.3f}",
                   "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]
            cmd += ["-c:a", "aac", "-b:a", "192k"] if tem_audio else ["-an"]
            executar(cmd + [str(seg)], self.log)
            segmentos.append(seg)
        return segmentos

    def remover_silencios_simples(self, video: Path, saida: Path,
                                  threshold_db: float = -35.0,
                                  duracao_minima: float = 0.5) -> Path:
        """Remove silencios mantendo apenas os trechos com som (preciso ao frame)."""
        video, saida = Path(video), Path(saida)
        self.log("Removendo silencios...")
        silencios = self.detectar_silencios(video, threshold_db, duracao_minima)
        if not silencios:
            self.log("Nenhum silencio encontrado - copiando o original")
            shutil.copyfile(video, saida)
            return saida
        trechos = inverter_intervalos(silencios, _duracao(video))
        return self._manter_trechos(video, saida, trechos)

    def _manter_trechos(self, video: Path, saida: Path,
                        trechos: List[Tuple[float, float]]) -> Path:
        if not trechos:
            raise ValueError("Nada para manter: o arquivo inteiro e silencio.")
        info = info_midia(video)
        partes, rotulos = [], []
        for i, (ini, fim) in enumerate(trechos):
            partes.append(f"[0:v]trim=start={ini:.3f}:end={fim:.3f},setpts=PTS-STARTPTS[v{i}]")
            rot = f"[v{i}]"
            if info["tem_audio"]:
                partes.append(f"[0:a]atrim=start={ini:.3f}:end={fim:.3f},asetpts=PTS-STARTPTS[a{i}]")
                rot += f"[a{i}]"
            rotulos.append(rot)
        a = 1 if info["tem_audio"] else 0
        partes.append(f"{''.join(rotulos)}concat=n={len(trechos)}:v=1:a={a}[vout]" + ("[aout]" if a else ""))
        script = self.temp_dir / "trechos.txt"
        script.write_text(";\n".join(partes), encoding="utf-8")  # evita limite de linha de comando
        cmd = ["ffmpeg", "-y", "-i", str(video), "-filter_complex_script", str(script),
               "-map", "[vout]"]
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"] if a else []
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(saida)]
        total = sum(f - i for i, f in trechos)
        self.log(f"Mantendo {len(trechos)} trechos ({total:.1f}s de {info['duracao']:.1f}s)")
        executar_com_progresso(cmd, self.log, total)
        self.log(f"Silencios removidos: {saida}")
        return saida

    def _obter_duracao(self, video: Path) -> float:
        """Mantido por compatibilidade (v7.3)."""
        return _duracao(Path(video))

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()
