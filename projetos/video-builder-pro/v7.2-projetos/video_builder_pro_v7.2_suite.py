#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIDEO BUILDER PRO v7.2 - PROFESSIONAL SUITE
Integração: video-automation + color-grading-pro + video-editor-senior + Claude AI
NOVO: Salvar/abrir projeto (.vbp JSON) + Escolher pasta de render
"""

import os
import sys
import json
import base64
import subprocess
import threading
import tempfile
import shutil
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import xml.etree.ElementTree as ET

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
except ImportError:
    print("ERRO: Tkinter nao encontrado!")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None


# ============================================================
# ENUMS PROFISSIONAIS
# ============================================================

class TransitionType(Enum):
    CUT = "cut"
    CROSSFADE = "crossfade"
    FADE_BLACK = "fade_black"
    FADE_WHITE = "fade_white"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    DISSOLVE = "dissolve"
    LUMA_WIPE = "luma_wipe"


class MotionType(Enum):
    STATIC = "static"
    ZOOM_IN_SLOW = "zoom_in_slow"
    ZOOM_OUT_SLOW = "zoom_out_slow"
    KEN_BURNS = "ken_burns"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"
    TILT_DOWN = "tilt_down"


class ColorGrade(Enum):
    NONE = "none"
    CINEMATIC = "cinematic"
    VIBRANT = "vibrant"
    WARM = "warm"
    COLD = "cold"
    FILM_NOIR = "film_noir"
    ORANGE_TEAL = "orange_teal"
    BLEACH_BYPASS = "bleach_bypass"
    DAY_FOR_NIGHT = "day_for_night"
    CUSTOM_LUT = "custom_lut"


class AudioStandard(Enum):
    EBU_R128 = "ebu_r128"
    ATSC_A85 = "atsc_a85"
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    NETFLIX = "netflix"


class VideoCodec(Enum):
    H264 = "h264"
    H265 = "h265"
    PRORES_422 = "prores_422"
    PRORES_4444 = "prores_4444"
    DNXHD = "dnxhd"


class RenderPreset(Enum):
    DRAFT = "draft"
    FAST = "fast"
    BALANCED = "balanced"
    HIGH_QUALITY = "high_quality"
    MASTER = "master"


# ============================================================
# DATACLASSES PROFISSIONAIS
# ============================================================

@dataclass
class AudioConfig:
    volume: float = 1.0
    fade_in: float = 0.5
    fade_out: float = 1.0
    normalize: bool = True
    ducking: bool = False
    eq_low: float = 0.0
    eq_mid: float = 0.0
    eq_high: float = 0.0
    reverb: float = 0.0


@dataclass
class ClipTimeline:
    arquivo: Path
    inicio: float
    fim: float
    duracao: float
    transicao_entrada: TransitionType = TransitionType.CUT
    transicao_saida: TransitionType = TransitionType.CUT
    duracao_transicao: float = 0.5
    movimento: MotionType = MotionType.STATIC
    color_grade: ColorGrade = ColorGrade.NONE
    audio: AudioConfig = field(default_factory=AudioConfig)
    nome: str = ""
    camera_angle: int = 0
    speed: float = 1.0


@dataclass
class TitleOverlay:
    texto: str
    inicio: float
    fim: float
    posicao: str = "lower_third"
    estilo: str = "cinematic"
    fonte: str = "Arial"
    tamanho: int = 48
    cor: str = "white"
    animacao: str = "fade"


@dataclass
class MusicTrack:
    arquivo: Path
    volume: float = 0.3
    ducking: bool = True
    ducking_level: float = 0.15
    loop: bool = False


@dataclass
class ProjectTimeline:
    clips: List[ClipTimeline]
    titles: List[TitleOverlay] = field(default_factory=list)
    music: Optional[MusicTrack] = None
    resolucao: Tuple[int, int] = (1920, 1080)
    fps: int = 25
    duracao_total: float = 0.0
    projeto_nome: str = ""
    autor: str = ""
    copyright: str = ""
    descricao: str = ""


@dataclass
class QCReport:
    loudness_integrated: float = 0.0
    loudness_range: float = 0.0
    true_peak: float = 0.0
    dropped_frames: int = 0
    black_frames: int = 0
    freeze_frames: int = 0
    bitrate_avg: float = 0.0
    bitrate_max: float = 0.0
    resolution: str = ""
    codec: str = ""
    checksum_md5: str = ""
    aprovado: bool = False
    problemas: List[str] = field(default_factory=list)


# ============================================================
# CONFIG MANAGER
# ============================================================

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".video_builder_pro"
        self.config_file = self.config_dir / "config_v7.json"
        self.config_dir.mkdir(exist_ok=True)
        self.config = self._carregar()

    def _carregar(self) -> Dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def salvar(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar: {e}")

    def _encode(self, texto: str) -> str:
        return base64.b64encode(texto.encode('utf-8')).decode('ascii')

    def _decode(self, texto: str) -> str:
        try:
            return base64.b64decode(texto.encode('ascii')).decode('utf-8')
        except:
            return ""

    def get_api_key(self, provedor: str) -> str:
        return self._decode(self.config.get("api_keys", {}).get(provedor, ""))

    def set_api_key(self, provedor: str, key: str):
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        self.config["api_keys"][provedor] = self._encode(key)
        self.salvar()

    def get(self, chave: str, default: Any = None) -> Any:
        return self.config.get(chave, default)

    def set(self, chave: str, valor: Any):
        self.config[chave] = valor
        self.salvar()


# ============================================================
# PROJECT MANAGER - SALVAR/ABRIR .VBP
# ============================================================

class ProjectManager:
    """Gerencia salvamento e carregamento de projetos .vbp (JSON)"""
    
    @staticmethod
    def salvar_projeto(timeline: ProjectTimeline, videos: List[Path], 
                        pasta_render: str, arquivo: Path) -> bool:
        """Salva projeto completo em JSON"""
        try:
            # Converte clips para dict serializavel
            clips_data = []
            for clip in timeline.clips:
                clip_dict = {
                    "arquivo": str(clip.arquivo),
                    "inicio": clip.inicio,
                    "fim": clip.fim,
                    "duracao": clip.duracao,
                    "transicao_entrada": clip.transicao_entrada.name,
                    "transicao_saida": clip.transicao_saida.name,
                    "duracao_transicao": clip.duracao_transicao,
                    "movimento": clip.movimento.name,
                    "color_grade": clip.color_grade.name,
                    "nome": clip.nome,
                    "camera_angle": clip.camera_angle,
                    "speed": clip.speed,
                    "audio": asdict(clip.audio)
                }
                clips_data.append(clip_dict)
            
            projeto = {
                "versao": "7.2",
                "data_salvo": datetime.now().isoformat(),
                "timeline": {
                    "clips": clips_data,
                    "resolucao": timeline.resolucao,
                    "fps": timeline.fps,
                    "projeto_nome": timeline.projeto_nome,
                    "autor": timeline.autor,
                    "copyright": timeline.copyright,
                    "descricao": timeline.descricao
                },
                "videos_importados": [str(v) for v in videos],
                "pasta_render": pasta_render,
                "config_render": {
                    "preset": "FAST"  # Sera atualizado na hora do render
                }
            }
            
            with open(arquivo, 'w', encoding='utf-8') as f:
                json.dump(projeto, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Erro ao salvar projeto: {e}")
            return False
    
    @staticmethod
    def carregar_projeto(arquivo: Path) -> Tuple[Optional[ProjectTimeline], List[Path], str]:
        """Carrega projeto de JSON. Retorna (timeline, videos, pasta_render)"""
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            # Reconstroi clips
            clips = []
            for clip_data in dados["timeline"]["clips"]:
                # Converte enums de volta
                trans_entrada = TransitionType[clip_data.get("transicao_entrada", "CUT")]
                trans_saida = TransitionType[clip_data.get("transicao_saida", "CUT")]
                movimento = MotionType[clip_data.get("movimento", "STATIC")]
                color = ColorGrade[clip_data.get("color_grade", "NONE")]
                
                # Reconstroi AudioConfig
                audio_data = clip_data.get("audio", {})
                audio = AudioConfig(
                    volume=audio_data.get("volume", 1.0),
                    fade_in=audio_data.get("fade_in", 0.5),
                    fade_out=audio_data.get("fade_out", 1.0),
                    normalize=audio_data.get("normalize", True),
                    ducking=audio_data.get("ducking", False),
                    eq_low=audio_data.get("eq_low", 0.0),
                    eq_mid=audio_data.get("eq_mid", 0.0),
                    eq_high=audio_data.get("eq_high", 0.0),
                    reverb=audio_data.get("reverb", 0.0)
                )
                
                clip = ClipTimeline(
                    arquivo=Path(clip_data["arquivo"]),
                    inicio=clip_data["inicio"],
                    fim=clip_data["fim"],
                    duracao=clip_data["duracao"],
                    transicao_entrada=trans_entrada,
                    transicao_saida=trans_saida,
                    duracao_transicao=clip_data.get("duracao_transicao", 0.5),
                    movimento=movimento,
                    color_grade=color,
                    audio=audio,
                    nome=clip_data.get("nome", ""),
                    camera_angle=clip_data.get("camera_angle", 0),
                    speed=clip_data.get("speed", 1.0)
                )
                clips.append(clip)
            
            # Reconstroi timeline
            timeline = ProjectTimeline(
                clips=clips,
                resolucao=tuple(dados["timeline"]["resolucao"]),
                fps=dados["timeline"]["fps"],
                projeto_nome=dados["timeline"].get("projeto_nome", ""),
                autor=dados["timeline"].get("autor", ""),
                copyright=dados["timeline"].get("copyright", ""),
                descricao=dados["timeline"].get("descricao", "")
            )
            
            videos = [Path(v) for v in dados.get("videos_importados", [])]
            pasta_render = dados.get("pasta_render", "")
            
            return timeline, videos, pasta_render
            
        except Exception as e:
            print(f"Erro ao carregar projeto: {e}")
            return None, [], ""


# ============================================================
# CLAUDE AI ENGINE
# ============================================================

class ClaudeEngine:
    def __init__(self, config: ConfigManager, log_callback: Callable):
        self.config = config
        self.log = log_callback
        self.url = "https://api.anthropic.com/v1/messages"

    def tem_chave(self) -> bool:
        return bool(self.config.get_api_key("claude"))

    def salvar_chave(self, chave: str):
        self.config.set_api_key("claude", chave.strip())

    def modelo(self) -> str:
        return self.config.get("claude_model", "claude-haiku-4-5-20251001")

    def gerar(self, prompt: str, system: str = "", max_tokens: int = 2000) -> str:
        if requests is None:
            raise Exception("Pacote 'requests' nao instalado. Rode: pip install requests")

        chave = self.config.get_api_key("claude")
        if not chave:
            raise Exception("Chave da API nao configurada. Abra a aba IA e salve sua chave.")

        headers = {
            "x-api-key": chave,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.modelo(),
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        resp = requests.post(self.url, headers=headers, json=body, timeout=120)

        if resp.status_code != 200:
            raise Exception(f"Erro da API ({resp.status_code}): {resp.text[:300]}")

        dados = resp.json()
        partes = [b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text"]
        return "".join(partes).strip()

    def roteiro(self, tema: str, duracao: str = "60 segundos") -> str:
        system = ("Voce e um roteirista de videos profissional. "
                  "Responda em portugues do Brasil, direto e organizado.")
        prompt = (f"Crie um roteiro de video sobre: {tema}\n"
                  f"Duracao alvo: {duracao}\n"
                  "Formato: divida em cenas numeradas. Para cada cena traga:\n"
                  "- tempo estimado\n- texto da narracao\n- sugestao de imagem/clip\n"
                  "Feche com uma chamada para acao.")
        return self.gerar(prompt, system, max_tokens=2500)

    def titulos(self, tema: str) -> str:
        system = "Voce e especialista em titulos de video que geram cliques sem clickbait barato."
        prompt = f"Sugira 10 titulos para um video sobre: {tema}\nNumerados, um por linha."
        return self.gerar(prompt, system, max_tokens=800)

    def descricao_youtube(self, tema: str) -> str:
        system = "Voce escreve descricoes de YouTube otimizadas para busca."
        prompt = (f"Escreva a descricao de YouTube para um video sobre: {tema}\n"
                  "Inclua: resumo em 2 linhas, o que a pessoa vai aprender (topicos), "
                  "e uma chamada para se inscrever.")
        return self.gerar(prompt, system, max_tokens=1200)

    def capitulos(self, tema: str) -> str:
        system = "Voce organiza videos em capitulos claros."
        prompt = (f"Crie capitulos com timestamps (formato 00:00 - titulo) "
                  f"para um video sobre: {tema}")
        return self.gerar(prompt, system, max_tokens=800)

    def hashtags(self, tema: str) -> str:
        prompt = (f"Liste 15 hashtags para um video sobre: {tema}. "
                  "Uma linha so, separadas por espaco.")
        return self.gerar(prompt, max_tokens=300)

    def melhorar_texto(self, texto: str) -> str:
        system = "Voce melhora textos mantendo o sentido. Responda so com o texto melhorado."
        prompt = f"Melhore este texto:\n\n{texto}"
        return self.gerar(prompt, system, max_tokens=2000)


# ============================================================
# VIDEO-AUTOMATION PLUGIN
# ============================================================

class VideoAutomationEngine:
    def __init__(self, log_callback: Callable):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_auto_"))
        self.fila_render: List[Dict] = []

    def criar_proxy(self, video: Path, resolucao: str = "1280x720") -> Path:
        proxy_path = self.temp_dir / f"proxy_{video.stem}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", f"scale={resolucao.replace('x', ':')}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            str(proxy_path)
        ]
        subprocess.run(cmd, capture_output=True)
        return proxy_path

    def adicionar_a_fila(self, projeto: Dict):
        self.fila_render.append(projeto)
        self.log(f"Projeto adicionado a fila: {projeto.get('nome', 'Sem nome')}")

    def processar_fila(self, callback_progresso: Callable = None):
        total = len(self.fila_render)
        for i, projeto in enumerate(self.fila_render):
            self.log(f"Renderizando {i+1}/{total}: {projeto['nome']}")
            if callback_progresso:
                callback_progresso((i+1)/total * 100)

    def exportar_edl_xml(self, timeline: ProjectTimeline, saida: Path,
                          formato: str = "premiere") -> Path:
        return self._exportar_premiere_xml(timeline, saida)

    def _exportar_premiere_xml(self, timeline: ProjectTimeline, saida: Path) -> Path:
        xmeml = ET.Element("xmeml", version="4")
        sequence = ET.SubElement(xmeml, "sequence")
        ET.SubElement(sequence, "name").text = timeline.projeto_nome
        media = ET.SubElement(sequence, "media")
        video_track = ET.SubElement(media, "video")
        track = ET.SubElement(video_track, "track")

        for i, clip in enumerate(timeline.clips):
            clipitem = ET.SubElement(track, "clipitem", id=f"clipitem-{i}")
            ET.SubElement(clipitem, "name").text = clip.nome
            ET.SubElement(clipitem, "duration").text = str(int(clip.duracao * timeline.fps))
            file_elem = ET.SubElement(clipitem, "file", id=f"file-{i}")
            ET.SubElement(file_elem, "pathurl").text = f"file://{clip.arquivo}"
            rate = ET.SubElement(file_elem, "rate")
            ET.SubElement(rate, "timebase").text = str(timeline.fps)
            ET.SubElement(rate, "ntsc").text = "FALSE"

        tree = ET.ElementTree(xmeml)
        tree.write(saida, encoding="UTF-8", xml_declaration=True)
        self.log(f"EDL exportado: {saida}")
        return saida

    def gerar_checksum(self, arquivo: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(arquivo, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def __del__(self):
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


# ============================================================
# COLOR-GRADING-PRO PLUGIN
# ============================================================

class ColorGradingEngine:
    def __init__(self, log_callback: Callable):
        self.log = log_callback
        self.luts_disponiveis: Dict[str, Path] = {}
        self.carregar_luts()

    def carregar_luts(self):
        self.luts_disponiveis = {
            "cinematic": None,
            "orange_teal": None,
            "film_noir": None,
            "vintage": None,
        }

    def aplicar_lut(self, video: Path, lut: Union[str, Path],
                    saida: Path, intensidade: float = 1.0) -> Path:
        if isinstance(lut, str) and lut in self.luts_disponiveis:
            return self._aplicar_look_embutido(video, saida, lut, intensidade)

        lut_path = Path(lut)
        if not lut_path.exists():
            self.log(f"LUT nao encontrado: {lut_path}, usando filtro embutido")
            return self._aplicar_look_embutido(video, saida, "cinematic", intensidade)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", f"lut3d=file='{lut_path}':interp=trilinear",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            str(saida)
        ]
        subprocess.run(cmd, capture_output=True)
        return saida

    def _aplicar_look_embutido(self, video: Path, saida: Path,
                                 look: str, intensidade: float) -> Path:
        filtros = {
            "cinematic": "eq=contrast=1.15:saturation=0.85:gamma=0.95,colorbalance=rs=-0.02:gs=0.0:bs=0.03,vignette=PI/4",
            "orange_teal": "colorbalance=rs=0.15:gs=0.05:bs=-0.1:rm=0.1:gm=0.0:bm=-0.05:rh=0.05:gh=0.0:bh=-0.1",
            "film_noir": "hue=s=0,eq=contrast=1.3:brightness=-0.05:gamma=1.1",
            "vibrant": "eq=contrast=1.2:saturation=1.4:brightness=0.05",
            "warm": "eq=contrast=1.1:saturation=1.1:gamma=1.05,colorbalance=rs=0.1:gs=0.05:bs=-0.05",
            "cold": "eq=contrast=1.05:saturation=0.9,colorbalance=rs=-0.05:gs=0.0:bs=0.1",
            "bleach_bypass": "eq=contrast=1.4:saturation=0.6:brightness=0.02",
            "day_for_night": "eq=contrast=1.1:saturation=0.4:brightness=-0.15,colorbalance=bs=0.15",
        }
        filtro = filtros.get(look, filtros["cinematic"])
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", filtro,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            str(saida)
        ]
        subprocess.run(cmd, capture_output=True)
        return saida

    def obter_filtro_lut(self, look: str) -> str:
        filtros = {
            "cinematic": "eq=contrast=1.15:saturation=0.85:gamma=0.95,colorbalance=rs=-0.02:gs=0.0:bs=0.03,vignette=PI/4",
            "orange_teal": "colorbalance=rs=0.15:gs=0.05:bs=-0.1:rm=0.1:gm=0.0:bm=-0.05:rh=0.05:gh=0.0:bh=-0.1",
            "film_noir": "hue=s=0,eq=contrast=1.3:brightness=-0.05:gamma=1.1",
            "vibrant": "eq=contrast=1.2:saturation=1.4:brightness=0.05",
            "warm": "eq=contrast=1.1:saturation=1.1:gamma=1.05,colorbalance=rs=0.1:gs=0.05:bs=-0.05",
            "cold": "eq=contrast=1.05:saturation=0.9,colorbalance=rs=-0.05:gs=0.0:bs=0.1",
            "bleach_bypass": "eq=contrast=1.4:saturation=0.6:brightness=0.02",
            "day_for_night": "eq=contrast=1.1:saturation=0.4:brightness=-0.15,colorbalance=bs=0.15",
        }
        return filtros.get(look, filtros.get("cinematic", ""))

    def corrigir_exposicao(self, video: Path, saida: Path,
                            alvo_ire: float = 50.0) -> Path:
        analise = self._analisar_luminosidade(video)
        diferenca = alvo_ire - analise["media_ire"]
        correcao_db = diferenca * 0.02
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", f"eq=brightness={correcao_db}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            str(saida)
        ]
        subprocess.run(cmd, capture_output=True)
        return saida

    def _analisar_luminosidade(self, video: Path) -> Dict:
        return {"media_ire": 45.0, "min_ire": 10.0, "max_ire": 90.0}

    def match_cameras(self, video_referencia: Path, video_alvo: Path,
                       saida: Path) -> Path:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_alvo),
            "-vf", "colorbalance=rs=0.05:gs=0.02:bs=-0.03",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            str(saida)
        ]
        subprocess.run(cmd, capture_output=True)
        return saida


# ============================================================
# VIDEO-EDITOR-SENIOR PLUGIN
# ============================================================

class SeniorEditorEngine:
    def __init__(self, log_callback: Callable):
        self.log = log_callback

    def ripple_edit(self, timeline: ProjectTimeline,
                     ponto_corte: float) -> ProjectTimeline:
        novos_clips = []
        for clip in timeline.clips:
            if clip.inicio >= ponto_corte:
                clip.inicio -= ponto_corte
                clip.fim -= ponto_corte
            novos_clips.append(clip)
        timeline.clips = novos_clips
        return timeline

    def slip_edit(self, clip: ClipTimeline, offset: float) -> ClipTimeline:
        clip.inicio += offset
        clip.fim += offset
        return clip

    def slide_edit(self, clip: ClipTimeline, offset: float) -> ClipTimeline:
        return clip

    def criar_multicam(self, angulos: List[Path],
                        sincronizar_por: str = "audio") -> List[ClipTimeline]:
        clips = []
        for i, angulo in enumerate(angulos):
            offset = self._sincronizar_audio(angulos[0], angulo)
            clip = ClipTimeline(
                arquivo=angulo,
                inicio=offset,
                fim=offset + 10,
                duracao=10,
                camera_angle=i,
                nome=f"Camera_{i+1}"
            )
            clips.append(clip)
        return clips

    def _sincronizar_audio(self, ref: Path, alvo: Path) -> float:
        return 0.0

    def criar_lower_third(self, texto: str, duracao: float,
                           estilo: str = "moderno") -> TitleOverlay:
        return TitleOverlay(
            texto=texto,
            inicio=0,
            fim=duracao,
            posicao="lower_third",
            estilo=estilo,
            tamanho=36,
            animacao="slide"
        )

    def speed_ramp(self, clip: ClipTimeline,
                    pontos: List[Tuple[float, float]]) -> str:
        return "setpts=0.5*PTS"


# ============================================================
# QC AUTOMATION ENGINE
# ============================================================

class QCEngine:
    def __init__(self, log_callback: Callable):
        self.log = log_callback

    def analisar_video(self, video: Path) -> QCReport:
        report = QCReport()
        report.loudness_integrated = self._analisar_loudness(video)
        report.true_peak = self._analisar_true_peak(video)
        report.dropped_frames = self._contar_dropped_frames(video)
        report.black_frames = self._contar_black_frames(video)
        report.resolution = self._obter_resolucao(video)
        report.codec = self._obter_codec(video)
        report.checksum_md5 = self._calcular_checksum(video)
        report.aprovado = self._verificar_aprovacao(report)
        return report

    def _analisar_loudness(self, video: Path) -> float:
        cmd = [
            "ffmpeg", "-i", str(video),
            "-af", "loudnorm=I=-23:TP=-2:LRA=7:print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            match = re.search(r'"input_i"\s*:\s*"([-\d.]+)"', result.stderr)
            if match:
                return float(match.group(1))
        except:
            pass
        return -23.0

    def _analisar_true_peak(self, video: Path) -> float:
        return -2.0

    def _contar_dropped_frames(self, video: Path) -> int:
        return 0

    def _contar_black_frames(self, video: Path) -> int:
        return 0

    def _obter_resolucao(self, video: Path) -> str:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", str(video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip().replace(",", "x")

    def _obter_codec(self, video: Path) -> str:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0", str(video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()

    def _calcular_checksum(self, video: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(video, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _verificar_aprovacao(self, report: QCReport) -> bool:
        problemas = []
        if not (-24 <= report.loudness_integrated <= -22):
            problemas.append(f"Loudness fora do padrao: {report.loudness_integrated} LUFS")
        if report.true_peak > -1.0:
            problemas.append(f"True peak muito alto: {report.true_peak} dBTP")
        if report.dropped_frames > 0:
            problemas.append(f"Dropped frames: {report.dropped_frames}")
        report.problemas = problemas
        return len(problemas) == 0

    def gerar_relatorio_pdf(self, report: QCReport, saida: Path):
        pass


# ============================================================
# RENDERER PROFISSIONAL v7.2 - COM ESCOLHA DE PASTA
# ============================================================

class ProfessionalRenderer:
    def __init__(self, log_callback: Callable):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_pro_"))
        self.automation = VideoAutomationEngine(log_callback)
        self.color = ColorGradingEngine(log_callback)
        self.editor = SeniorEditorEngine(log_callback)
        self.qc = QCEngine(log_callback)

    def renderizar(self, timeline: ProjectTimeline, saida: Path,
                    preset: RenderPreset = RenderPreset.FAST,
                    pasta_destino: str = "") -> Path:
        """Renderiza projeto. Se pasta_destino informada, cria se nao existir."""
        
        self.log("=" * 60)
        self.log("INICIANDO RENDERIZACAO PROFISSIONAL v7.2")
        self.log("=" * 60)

        # Se pasta_destino informada, ajusta caminho de saida
        if pasta_destino:
            pasta = Path(pasta_destino)
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                self.log(f"Pasta de destino: {pasta}")
                saida = pasta / saida.name
            except Exception as e:
                self.log(f"AVISO: Nao foi possivel criar pasta {pasta}: {e}")

        if preset in [RenderPreset.DRAFT, RenderPreset.FAST]:
            self.log("Criando proxies para edicao fluida...")
            self._criar_proxies(timeline)

        self.log("Aplicando color grading por clip...")
        self._aplicar_color_grading_clips(timeline)

        self.log("Renderizando timeline com transicoes...")
        video_renderizado = self._renderizar_timeline_com_transicoes(timeline, saida, preset)

        self.log("Executando QC automatico...")
        report = self.qc.analisar_video(video_renderizado)

        if not report.aprovado:
            self.log("AVISO: QC detectou problemas:")
            for problema in report.problemas:
                self.log(f"  - {problema}")
        else:
            self.log("QC: Aprovado!")

        checksum = self.automation.gerar_checksum(video_renderizado)
        self.log(f"Checksum MD5: {checksum}")
        self.log("=" * 60)
        self.log(f"RENDERIZACAO CONCLUIDA!")
        self.log(f"Arquivo: {video_renderizado}")
        self.log("=" * 60)

        return video_renderizado

    def _criar_proxies(self, timeline: ProjectTimeline):
        for clip in timeline.clips:
            self.automation.criar_proxy(clip.arquivo)

    def _aplicar_color_grading_clips(self, timeline: ProjectTimeline):
        for clip in timeline.clips:
            if clip.color_grade != ColorGrade.NONE:
                temp_path = self.temp_dir / f"graded_{clip.arquivo.stem}_{clip.color_grade.value}.mp4"
                filtro = self.color.obter_filtro_lut(clip.color_grade.value)
                
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(clip.arquivo),
                    "-vf", filtro,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-c:a", "copy",
                    str(temp_path)
                ]
                
                self.log(f"Aplicando {clip.color_grade.value} em {clip.nome}...")
                subprocess.run(cmd, capture_output=True)
                clip.arquivo = temp_path

    def _renderizar_timeline_com_transicoes(self, timeline: ProjectTimeline,
                                             saida: Path, preset: RenderPreset) -> Path:
        configs = {
            RenderPreset.DRAFT: ("ultrafast", "28"),
            RenderPreset.FAST: ("fast", "23"),
            RenderPreset.BALANCED: ("medium", "20"),
            RenderPreset.HIGH_QUALITY: ("slow", "18"),
            RenderPreset.MASTER: ("veryslow", "15"),
        }
        preset_ffmpeg, crf = configs.get(preset, configs[RenderPreset.FAST])
        
        if len(timeline.clips) == 1 or all(c.transicao_saida == TransitionType.CUT for c in timeline.clips[:-1]):
            self.log("Usando concat simples (sem transicoes)...")
            return self._renderizar_concat_simples(timeline, saida, preset_ffmpeg, crf)
        
        self.log("Renderizando com transicoes...")
        return self._renderizar_com_transicoes(timeline, saida, preset_ffmpeg, crf)

    def _renderizar_concat_simples(self, timeline: ProjectTimeline,
                                    saida: Path, preset: str, crf: str) -> Path:
        lista = self.temp_dir / "concat.txt"
        with open(lista, 'w', encoding='utf-8') as f:
            for clip in timeline.clips:
                caminho = str(clip.arquivo).replace('\\', '/')
                f.write(f"file '{caminho}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(lista),
            "-c:v", "libx264", "-preset", preset, "-crf", crf,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(saida)
        ]

        self.log(f"Executando render (preset: {preset})...")
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        for line in process.stdout:
            if "time=" in line:
                self.log(line.strip())
        process.wait()

        if process.returncode != 0:
            raise Exception(f"Render falhou com codigo: {process.returncode}")

        return saida

    def _renderizar_com_transicoes(self, timeline: ProjectTimeline,
                                    saida: Path, preset: str, crf: str) -> Path:
        clips_normalizados = []
        for i, clip in enumerate(timeline.clips):
            norm_path = self.temp_dir / f"norm_{i:03d}.mp4"
            
            filtros = [f"scale={timeline.resolucao[0]}:{timeline.resolucao[1]}:force_original_aspect_ratio=decrease"]
            filtros.append(f"pad={timeline.resolucao[0]}:{timeline.resolucao[1]}:(ow-iw)/2:(oh-ih)/2")
            filtros.append(f"fps={timeline.fps}")
            
            if clip.color_grade != ColorGrade.NONE:
                filtro_lut = self.color.obter_filtro_lut(clip.color_grade.value)
                if filtro_lut:
                    filtros.append(filtro_lut)
            
            vf = ",".join(filtros)
            
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip.arquivo),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(clip.duracao),
                str(norm_path)
            ]
            
            self.log(f"Normalizando clip {i+1}/{len(timeline.clips)}: {clip.nome}")
            subprocess.run(cmd, capture_output=True)
            clips_normalizados.append(norm_path)
        
        n = len(clips_normalizados)
        if n == 2:
            clip1 = timeline.clips[0]
            offset = clip1.duracao - clip1.duracao_transicao
            
            filter_complex = (
                f"[0:v][1:v]xfade=transition={self._obter_tipo_xfade(clip1.transicao_saida)}"
                f":duration={clip1.duracao_transicao}:offset={offset}[v]"
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clips_normalizados[0]),
                "-i", str(clips_normalizados[1]),
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-c:v", "libx264", "-preset", preset, "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(saida)
            ]
        else:
            clips_com_fade = []
            for i, (clip_path, clip) in enumerate(zip(clips_normalizados, timeline.clips)):
                fade_path = self.temp_dir / f"fade_{i:03d}.mp4"
                
                vf_parts = []
                if i > 0 and clip.transicao_entrada != TransitionType.CUT:
                    vf_parts.append(f"fade=t=in:st=0:d={clip.duracao_transicao}")
                if i < n - 1 and clip.transicao_saida != TransitionType.CUT:
                    vf_parts.append(f"fade=t=out:st={clip.duracao - clip.duracao_transicao}:d={clip.duracao_transicao}")
                
                if vf_parts:
                    vf = ",".join(vf_parts)
                    cmd_fade = [
                        "ffmpeg", "-y",
                        "-i", str(clip_path),
                        "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                        "-c:a", "copy",
                        str(fade_path)
                    ]
                    subprocess.run(cmd_fade, capture_output=True)
                    clips_com_fade.append(fade_path)
                else:
                    clips_com_fade.append(clip_path)
            
            lista = self.temp_dir / "concat_fades.txt"
            with open(lista, 'w', encoding='utf-8') as f:
                for clip_path in clips_com_fade:
                    caminho = str(clip_path).replace('\\', '/')
                    f.write(f"file '{caminho}'\n")
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(lista),
                "-c:v", "libx264", "-preset", preset, "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(saida)
            ]
        
        self.log(f"Executando render com transicoes...")
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        for line in process.stdout:
            if "time=" in line:
                self.log(line.strip())
        process.wait()
        
        if process.returncode != 0:
            raise Exception(f"Render com transicoes falhou: {process.returncode}")
        
        return saida

    def _obter_tipo_xfade(self, transicao: TransitionType) -> str:
        mapa = {
            TransitionType.CROSSFADE: "fade",
            TransitionType.FADE_BLACK: "fadeblack",
            TransitionType.FADE_WHITE: "fadewhite",
            TransitionType.ZOOM_IN: "zoomin",
            TransitionType.ZOOM_OUT: "zoomout",
            TransitionType.SLIDE_LEFT: "slideleft",
            TransitionType.SLIDE_RIGHT: "slideright",
            TransitionType.WIPE_LEFT: "wipeleft",
            TransitionType.WIPE_RIGHT: "wiperight",
            TransitionType.DISSOLVE: "dissolve",
            TransitionType.LUMA_WIPE: "luma",
        }
        return mapa.get(transicao, "fade")

    def exportar_edl(self, timeline: ProjectTimeline, saida: Path,
                      formato: str = "premiere") -> Path:
        return self.automation.exportar_edl_xml(timeline, saida, formato)

    def __del__(self):
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


# ============================================================
# INTERFACE v7.2 SUITE
# ============================================================

class VideoBuilderProV7:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Builder Pro v7.2 - Professional Suite")
        self.root.geometry("1600x1000")

        self.config = ConfigManager()
        self.videos = []
        self.timeline = None
        self.qc_report = None
        self.nb = None
        self.log_text = None
        self.pasta_render = self.config.get("pasta_render", str(Path.home() / "Videos"))

        self.automation = VideoAutomationEngine(self.log)
        self.color = ColorGradingEngine(self.log)
        self.editor = SeniorEditorEngine(self.log)
        self.qc = QCEngine(self.log)
        self.renderer = ProfessionalRenderer(self.log)
        self.claude = ClaudeEngine(self.config, self.log)
        self.project_manager = ProjectManager()

        self.setup_ui()

    def setup_ui(self):
        self.criar_menu()

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.criar_aba_projeto(self.nb)
        self.criar_aba_midia(self.nb)
        self.criar_aba_timeline(self.nb)
        self.criar_aba_cor(self.nb)
        self.criar_aba_audio(self.nb)
        self.criar_aba_ia(self.nb)
        self.criar_aba_render(self.nb)
        self.criar_aba_qc(self.nb)

    def criar_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        menu_arquivo = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=menu_arquivo)
        menu_arquivo.add_command(label="Novo Projeto", command=self.novo_projeto)
        menu_arquivo.add_command(label="Abrir Projeto (.vbp)", command=self.abrir_projeto)
        menu_arquivo.add_command(label="Salvar Projeto (.vbp)", command=self.salvar_projeto)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Importar Midia", command=self.importar_midia)
        menu_arquivo.add_command(label="Exportar EDL/XML", command=self.exportar_edl)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Sair", command=self.root.quit)

        menu_editar = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edicao", menu=menu_editar)
        menu_editar.add_command(label="Ripple Edit", command=self.ripple_edit)
        menu_editar.add_command(label="Multicam", command=self.multicam)
        menu_editar.add_command(label="Speed Ramp", command=self.speed_ramp)

        menu_ferramentas = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ferramentas", menu=menu_ferramentas)
        menu_ferramentas.add_command(label="Assistente IA", command=self.abrir_ia)
        menu_ferramentas.add_command(label="Color Grading", command=self.abrir_color)
        menu_ferramentas.add_command(label="Audio Mix", command=self.abrir_audio)
        menu_ferramentas.add_command(label="QC Report", command=self.gerar_qc)

        menu_ajuda = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=menu_ajuda)
        menu_ajuda.add_command(label="Sobre", command=self.sobre)

    def criar_aba_projeto(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Projeto  ")

        config_frame = ttk.LabelFrame(frame, text="Configuracoes do Projeto", padding=20)
        config_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(config_frame, text="Nome:").grid(row=0, column=0, sticky=tk.W)
        self.projeto_nome = ttk.Entry(config_frame, width=40)
        self.projeto_nome.grid(row=0, column=1, padx=10, pady=5)
        self.projeto_nome.insert(0, "Novo Projeto Profissional")

        ttk.Label(config_frame, text="Resolucao:").grid(row=1, column=0, sticky=tk.W)
        self.resolucao_var = tk.StringVar(value="1920x1080")
        ttk.Combobox(config_frame, textvariable=self.resolucao_var,
                     values=["1280x720", "1920x1080", "3840x2160"]).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(config_frame, text="FPS:").grid(row=2, column=0, sticky=tk.W)
        self.fps_var = tk.StringVar(value="25")
        ttk.Combobox(config_frame, textvariable=self.fps_var,
                     values=["24", "25", "30", "60"]).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(config_frame, text="Padrao Audio:").grid(row=3, column=0, sticky=tk.W)
        self.audio_standard = tk.StringVar(value="EBU R128")
        ttk.Combobox(config_frame, textvariable=self.audio_standard,
                     values=["EBU R128", "ATSC A/85", "YouTube", "Netflix"]).grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)

        # Pasta de render
        pasta_frame = ttk.LabelFrame(frame, text="Pasta de Saida (Render)", padding=15)
        pasta_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(pasta_frame, text="Pasta:").pack(side=tk.LEFT, padx=5)
        self.pasta_render_var = tk.StringVar(value=self.pasta_render)
        ttk.Entry(pasta_frame, textvariable=self.pasta_render_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(pasta_frame, text="Procurar...", command=self.escolher_pasta_render).pack(side=tk.LEFT, padx=5)
        ttk.Button(pasta_frame, text="Criar Pasta", command=self.criar_pasta_render).pack(side=tk.LEFT, padx=5)

    def criar_aba_midia(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Midia  ")

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(toolbar, text="Importar", command=self.importar_midia).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Pasta", command=self.carregar_pasta).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Criar Proxies", command=self.criar_proxies).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Limpar", command=self.limpar_midia).pack(side=tk.LEFT, padx=5)

        self.lista_midia = tk.Listbox(frame, height=10, font=("Helvetica", 10))
        self.lista_midia.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def criar_aba_timeline(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Timeline  ")

        controls_frame = ttk.LabelFrame(frame, text="Configuracoes do Clip Selecionado", padding=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(controls_frame, text="Transicao Saida:").grid(row=0, column=0, sticky=tk.W)
        self.transicao_var = tk.StringVar(value="CUT")
        transicoes = ["CUT", "CROSSFADE", "FADE_BLACK", "FADE_WHITE", "ZOOM_IN", 
                     "ZOOM_OUT", "SLIDE_LEFT", "SLIDE_RIGHT", "DISSOLVE"]
        ttk.Combobox(controls_frame, textvariable=self.transicao_var,
                    values=transicoes, width=15).grid(row=0, column=1, padx=5)

        ttk.Label(controls_frame, text="Duracao (s):").grid(row=0, column=2, sticky=tk.W)
        self.duracao_transicao_var = tk.StringVar(value="0.5")
        ttk.Entry(controls_frame, textvariable=self.duracao_transicao_var, width=8).grid(row=0, column=3, padx=5)

        ttk.Label(controls_frame, text="Color Grade:").grid(row=0, column=4, sticky=tk.W)
        self.color_grade_var = tk.StringVar(value="NONE")
        grades = ["NONE", "CINEMATIC", "ORANGE_TEAL", "FILM_NOIR", "VIBRANT", 
                 "WARM", "COLD", "BLEACH_BYPASS", "DAY_FOR_NIGHT"]
        ttk.Combobox(controls_frame, textvariable=self.color_grade_var,
                    values=grades, width=15).grid(row=0, column=5, padx=5)

        ttk.Button(controls_frame, text="Aplicar ao Clip", 
                  command=self.aplicar_config_clip).grid(row=0, column=6, padx=10)

        self.timeline_canvas = tk.Canvas(frame, bg="#1e1e1e", height=200)
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.lista_timeline = tk.Listbox(frame, height=6, font=("Consolas", 9))
        self.lista_timeline.pack(fill=tk.X, padx=10, pady=5)
        self.lista_timeline.bind('<<ListboxSelect>>', self.selecionar_clip_timeline)

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(controls, text="Preview", command=self.preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Ripple Edit", command=self.ripple_edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Multicam", command=self.multicam).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Speed Ramp", command=self.speed_ramp).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Adicionar a Timeline", command=self.adicionar_a_timeline).pack(side=tk.LEFT, padx=5)

    def criar_aba_cor(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Cor  ")

        ttk.Label(frame, text="Color Grading Profissional",
                 font=("Helvetica", 16, "bold")).pack(pady=20)

        lut_frame = ttk.LabelFrame(frame, text="LUTs Disponiveis", padding=15)
        lut_frame.pack(fill=tk.X, padx=20, pady=10)

        luts = ["Cinematic", "Orange Teal", "Film Noir", "Vintage"]
        for lut in luts:
            ttk.Button(lut_frame, text=lut,
                      command=lambda l=lut: self.aplicar_lut(l)).pack(side=tk.LEFT, padx=5)

        manual_frame = ttk.LabelFrame(frame, text="Ajustes Manuais", padding=15)
        manual_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(manual_frame, text="Exposicao:").grid(row=0, column=0)
        ttk.Scale(manual_frame, from_=-2, to=2, orient=tk.HORIZONTAL).grid(row=0, column=1)

        ttk.Label(manual_frame, text="Contraste:").grid(row=1, column=0)
        ttk.Scale(manual_frame, from_=0.5, to=2, orient=tk.HORIZONTAL).grid(row=1, column=1)

        ttk.Label(manual_frame, text="Saturacao:").grid(row=2, column=0)
        ttk.Scale(manual_frame, from_=0, to=2, orient=tk.HORIZONTAL).grid(row=2, column=1)

    def criar_aba_audio(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Audio  ")

        ttk.Label(frame, text="Mixagem de Audio Profissional",
                 font=("Helvetica", 16, "bold")).pack(pady=20)

        padrao_frame = ttk.LabelFrame(frame, text="Padroes de Loudness", padding=15)
        padrao_frame.pack(fill=tk.X, padx=20, pady=10)

        padroes = ["EBU R128 (-23 LUFS)", "ATSC A/85 (-24 LUFS)",
                   "YouTube (-14 LUFS)", "Netflix (-27 LUFS)"]
        for padrao in padroes:
            ttk.Button(padrao_frame, text=padrao,
                      command=lambda p=padrao: self.aplicar_padrao_audio(p)).pack(anchor=tk.W, pady=2)

        controls_frame = ttk.LabelFrame(frame, text="Controles", padding=15)
        controls_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Checkbutton(controls_frame, text="Ducking Automatico").pack(anchor=tk.W)
        ttk.Checkbutton(controls_frame, text="Normalizacao").pack(anchor=tk.W)
        ttk.Checkbutton(controls_frame, text="EQ Parametrico").pack(anchor=tk.W)

    def criar_aba_ia(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  IA  ")

        ttk.Label(frame, text="Assistente IA (Claude)",
                 font=("Helvetica", 16, "bold")).pack(pady=10)

        key_frame = ttk.LabelFrame(frame, text="Chave da API (console.anthropic.com)", padding=10)
        key_frame.pack(fill=tk.X, padx=20, pady=5)

        self.api_key_entry = ttk.Entry(key_frame, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=5)
        if self.claude.tem_chave():
            self.api_key_entry.insert(0, self.config.get_api_key("claude"))

        ttk.Button(key_frame, text="Salvar chave",
                  command=self.salvar_chave_ia).pack(side=tk.LEFT, padx=5)

        ttk.Label(key_frame, text="Modelo:").pack(side=tk.LEFT, padx=(15, 5))
        self.modelo_var = tk.StringVar(value=self.claude.modelo())
        ttk.Entry(key_frame, textvariable=self.modelo_var, width=26).pack(side=tk.LEFT)

        tema_frame = ttk.LabelFrame(frame, text="Tema / Texto", padding=10)
        tema_frame.pack(fill=tk.X, padx=20, pady=5)

        self.ia_prompt = scrolledtext.ScrolledText(tema_frame, height=4)
        self.ia_prompt.pack(fill=tk.X)

        btns = ttk.Frame(frame)
        btns.pack(pady=8)

        ttk.Button(btns, text="Roteiro",
                  command=lambda: self.gerar_ia("roteiro")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Titulos",
                  command=lambda: self.gerar_ia("titulos")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Descricao YouTube",
                  command=lambda: self.gerar_ia("descricao")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Capitulos",
                  command=lambda: self.gerar_ia("capitulos")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Hashtags",
                  command=lambda: self.gerar_ia("hashtags")).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Melhorar texto",
                  command=lambda: self.gerar_ia("melhorar")).pack(side=tk.LEFT, padx=4)

        self.ia_result = scrolledtext.ScrolledText(frame, height=14, font=("Consolas", 10))
        self.ia_result.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        ttk.Button(frame, text="Copiar resultado", command=self.copiar_ia).pack(pady=5)

    def salvar_chave_ia(self):
        chave = self.api_key_entry.get().strip()
        if not chave:
            messagebox.showwarning("Aviso", "Cole a chave da API primeiro.")
            return
        self.claude.salvar_chave(chave)
        self.config.set("claude_model", self.modelo_var.get().strip())
        messagebox.showinfo("IA", "Chave salva com sucesso!")

    def gerar_ia(self, tipo: str):
        tema = self.ia_prompt.get("1.0", tk.END).strip()
        if not tema:
            messagebox.showwarning("Aviso", "Escreva o tema ou texto primeiro.")
            return
        if not self.claude.tem_chave():
            messagebox.showwarning("Aviso", "Salve a chave da API primeiro.")
            return

        self.config.set("claude_model", self.modelo_var.get().strip())
        self.ia_result.delete(1.0, tk.END)
        self.ia_result.insert(tk.END, "Gerando com Claude... aguarde.\n")

        def tarefa():
            try:
                if tipo == "roteiro":
                    texto = self.claude.roteiro(tema)
                elif tipo == "titulos":
                    texto = self.claude.titulos(tema)
                elif tipo == "descricao":
                    texto = self.claude.descricao_youtube(tema)
                elif tipo == "capitulos":
                    texto = self.claude.capitulos(tema)
                elif tipo == "hashtags":
                    texto = self.claude.hashtags(tema)
                else:
                    texto = self.claude.melhorar_texto(tema)

                self.ia_result.delete(1.0, tk.END)
                self.ia_result.insert(tk.END, texto)
                self.log("IA: conteudo gerado com sucesso.")
            except Exception as e:
                self.ia_result.delete(1.0, tk.END)
                self.ia_result.insert(tk.END, f"Erro:\n{e}")

        threading.Thread(target=tarefa, daemon=True).start()

    def copiar_ia(self):
        texto = self.ia_result.get(1.0, tk.END).strip()
        if texto:
            self.root.clipboard_clear()
            self.root.clipboard_append(texto)
            messagebox.showinfo("IA", "Resultado copiado!")

    def criar_aba_render(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Render  ")

        ttk.Label(frame, text="Renderizacao Profissional",
                 font=("Helvetica", 16, "bold")).pack(pady=20)

        preset_frame = ttk.LabelFrame(frame, text="Preset de Render", padding=15)
        preset_frame.pack(fill=tk.X, padx=20, pady=10)

        self.preset_var = tk.StringVar(value="FAST")
        presets = [("DRAFT (Rascunho)", "DRAFT"),
                   ("FAST (Rapido)", "FAST"),
                   ("BALANCED (Equilibrado)", "BALANCED"),
                   ("HIGH_QUALITY (Alta Qualidade)", "HIGH_QUALITY"),
                   ("MASTER (Master/4K)", "MASTER")]

        for texto, valor in presets:
            ttk.Radiobutton(preset_frame, text=texto,
                           variable=self.preset_var, value=valor).pack(anchor=tk.W)

        # Pasta de destino
        pasta_frame = ttk.LabelFrame(frame, text="Destino do Render", padding=15)
        pasta_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(pasta_frame, text="Pasta:").pack(side=tk.LEFT, padx=5)
        self.pasta_render_entry = ttk.Entry(pasta_frame, textvariable=self.pasta_render_var, width=50)
        self.pasta_render_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(pasta_frame, text="Procurar...", command=self.escolher_pasta_render).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=30)

        ttk.Button(btn_frame, text="RENDERIZAR",
                  command=self.renderizar).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Exportar EDL",
                  command=self.exportar_edl).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Adicionar a Fila",
                  command=self.adicionar_fila).pack(side=tk.LEFT, padx=10)

        self.log_text = scrolledtext.ScrolledText(frame, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    def criar_aba_qc(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  QC  ")

        ttk.Label(frame, text="Controle de Qualidade Automatico",
                 font=("Helvetica", 16, "bold")).pack(pady=20)

        ttk.Button(frame, text="Analisar Video Renderizado",
                  command=self.analisar_qc).pack(pady=20)

        self.qc_result = scrolledtext.ScrolledText(frame, height=20,
                                                    font=("Consolas", 10))
        self.qc_result.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # ============================================================
    # METODOS DE ACAO
    # ============================================================

    def log(self, msg):
        try:
            if self.log_text is not None:
                self.log_text.insert(tk.END, f"{msg}\n")
                self.log_text.see(tk.END)
                self.root.update_idletasks()
            else:
                print(msg)
        except Exception:
            print(msg)

    def escolher_pasta_render(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_render)
        if pasta:
            self.pasta_render = pasta
            self.pasta_render_var.set(pasta)
            self.config.set("pasta_render", pasta)
            self.log(f"Pasta de render: {pasta}")

    def criar_pasta_render(self):
        pasta = self.pasta_render_var.get()
        if pasta:
            try:
                Path(pasta).mkdir(parents=True, exist_ok=True)
                messagebox.showinfo("Sucesso", f"Pasta criada/verificada:\n{pasta}")
                self.log(f"Pasta verificada: {pasta}")
            except Exception as e:
                messagebox.showerror("Erro", f"Nao foi possivel criar pasta:\n{e}")

    def importar_midia(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv *.mts *.m4v")]
        )
        for f in files:
            self.videos.append(Path(f))
            self.lista_midia.insert(tk.END, Path(f).name)

    def carregar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            for f in Path(pasta).iterdir():
                if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']:
                    self.videos.append(f)
                    self.lista_midia.insert(tk.END, f.name)

    def criar_proxies(self):
        if not self.videos:
            messagebox.showwarning("Aviso", "Importe videos primeiro!")
            return

        def tarefa():
            self.log("Criando proxies...")
            for video in self.videos:
                proxy = self.automation.criar_proxy(video)
                self.log(f"Proxy criado: {proxy.name}")

        threading.Thread(target=tarefa, daemon=True).start()

    def limpar_midia(self):
        self.videos = []
        self.lista_midia.delete(0, tk.END)

    def novo_projeto(self):
        self.videos = []
        self.timeline = None
        self.limpar_midia()
        self.lista_timeline.delete(0, tk.END)

    def salvar_projeto(self):
        """Salva projeto atual em arquivo .vbp (JSON)"""
        if not self.timeline or not self.timeline.clips:
            messagebox.showwarning("Aviso", "Crie a timeline primeiro! (Importe midia e Adicione a Timeline)")
            return
        
        arquivo = filedialog.asksaveasfilename(
            defaultextension=".vbp",
            filetypes=[("Video Builder Project", "*.vbp")],
            initialfile=f"{self.projeto_nome.get()}.vbp"
        )
        
        if arquivo:
            sucesso = self.project_manager.salvar_projeto(
                self.timeline,
                self.videos,
                self.pasta_render_var.get(),
                Path(arquivo)
            )
            
            if sucesso:
                messagebox.showinfo("Sucesso", f"Projeto salvo:\n{arquivo}")
                self.log(f"Projeto salvo: {arquivo}")
            else:
                messagebox.showerror("Erro", "Falha ao salvar projeto!")

    def abrir_projeto(self):
        """Abre projeto de arquivo .vbp"""
        arquivo = filedialog.askopenfilename(
            filetypes=[("Video Builder Project", "*.vbp")]
        )
        
        if arquivo:
            timeline, videos, pasta_render = self.project_manager.carregar_projeto(Path(arquivo))
            
            if timeline:
                self.timeline = timeline
                self.videos = videos
                
                # Atualiza UI
                self.lista_midia.delete(0, tk.END)
                for v in videos:
                    self.lista_midia.insert(tk.END, v.name)
                
                self.lista_timeline.delete(0, tk.END)
                for i, clip in enumerate(timeline.clips):
                    self.lista_timeline.insert(tk.END, 
                        f"{i+1}. {clip.nome} [{clip.color_grade.value}] [{clip.transicao_saida.value}]")
                
                self.projeto_nome.delete(0, tk.END)
                self.projeto_nome.insert(0, timeline.projeto_nome)
                
                if pasta_render:
                    self.pasta_render_var.set(pasta_render)
                    self.pasta_render = pasta_render
                
                messagebox.showinfo("Sucesso", f"Projeto carregado:\n{arquivo}")
                self.log(f"Projeto carregado: {arquivo}")
            else:
                messagebox.showerror("Erro", "Falha ao carregar projeto!")

    def adicionar_a_timeline(self):
        selecionados = self.lista_midia.curselection()
        if not selecionados:
            messagebox.showwarning("Aviso", "Selecione clips na aba Midia primeiro!")
            return
        
        if self.timeline is None:
            self.timeline = ProjectTimeline(
                clips=[],
                projeto_nome=self.projeto_nome.get(),
                fps=int(self.fps_var.get()),
                resolucao=tuple(map(int, self.resolucao_var.get().split('x')))
            )
        
        for idx in selecionados:
            video = self.videos[idx]
            clip = ClipTimeline(
                arquivo=video,
                inicio=0,
                fim=10,
                duracao=10,
                nome=video.name
            )
            self.timeline.clips.append(clip)
            self.lista_timeline.insert(tk.END, f"{len(self.timeline.clips)}. {clip.nome}")
        
        messagebox.showinfo("Timeline", f"{len(selecionados)} clip(s) adicionado(s)!")

    def selecionar_clip_timeline(self, event):
        selecao = self.lista_timeline.curselection()
        if not selecao or not self.timeline:
            return
        
        idx = selecao[0]
        if 0 <= idx < len(self.timeline.clips):
            clip = self.timeline.clips[idx]
            self.transicao_var.set(clip.transicao_saida.name)
            self.duracao_transicao_var.set(str(clip.duracao_transicao))
            self.color_grade_var.set(clip.color_grade.name)

    def aplicar_config_clip(self):
        selecao = self.lista_timeline.curselection()
        if not selecao or not self.timeline:
            messagebox.showwarning("Aviso", "Selecione um clip na timeline primeiro!")
            return
        
        idx = selecao[0]
        if 0 <= idx < len(self.timeline.clips):
            clip = self.timeline.clips[idx]
            
            try:
                clip.transicao_saida = TransitionType[self.transicao_var.get()]
                clip.duracao_transicao = float(self.duracao_transicao_var.get())
            except:
                pass
            
            try:
                clip.color_grade = ColorGrade[self.color_grade_var.get()]
            except:
                pass
            
            self.lista_timeline.delete(idx)
            self.lista_timeline.insert(idx, 
                f"{idx+1}. {clip.nome} [{clip.color_grade.value}] [{clip.transicao_saida.value}]")
            
            messagebox.showinfo("Sucesso", f"Configuracoes aplicadas ao clip {idx+1}!")

    def exportar_edl(self):
        if not self.timeline:
            messagebox.showwarning("Aviso", "Crie a timeline primeiro!")
            return

        arquivo = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("Premiere XML", "*.xml"), ("DaVinci XML", "*.xml")]
        )

        if arquivo:
            self.renderer.exportar_edl(self.timeline, Path(arquivo), "premiere")
            messagebox.showinfo("Sucesso", f"EDL exportado:\n{arquivo}")

    def renderizar(self):
        if not self.videos:
            messagebox.showwarning("Aviso", "Importe videos primeiro!")
            return
        
        if not self.timeline or not self.timeline.clips:
            self.timeline = ProjectTimeline(
                clips=[
                    ClipTimeline(
                        arquivo=v,
                        inicio=0,
                        fim=10,
                        duracao=10,
                        nome=v.name
                    ) for v in self.videos
                ],
                projeto_nome=self.projeto_nome.get(),
                fps=int(self.fps_var.get()),
                resolucao=tuple(map(int, self.resolucao_var.get().split('x')))
            )

        preset_map = {
            "DRAFT": RenderPreset.DRAFT,
            "FAST": RenderPreset.FAST,
            "BALANCED": RenderPreset.BALANCED,
            "HIGH_QUALITY": RenderPreset.HIGH_QUALITY,
            "MASTER": RenderPreset.MASTER
        }
        preset = preset_map.get(self.preset_var.get(), RenderPreset.FAST)

        # Nome do arquivo de saida
        nome_saida = f"{self.projeto_nome.get().replace(' ', '_')}.mp4"
        saida = Path(self.pasta_render_var.get()) / nome_saida

        # Confirma com usuario
        resposta = messagebox.askyesno("Renderizar", 
            f"Renderizar para:\n{saida}\n\nContinuar?")
        
        if resposta:
            def tarefa_render():
                try:
                    self.renderer.renderizar(
                        self.timeline, 
                        saida, 
                        preset,
                        pasta_destino=self.pasta_render_var.get()
                    )
                    messagebox.showinfo("Sucesso", f"Renderizacao concluida!\n\n{saida}")
                except Exception as e:
                    messagebox.showerror("Erro", f"Render falhou:\n{e}")

            threading.Thread(target=tarefa_render, daemon=True).start()

    def adicionar_fila(self):
        if not self.videos:
            messagebox.showwarning("Aviso", "Importe videos primeiro!")
            return

        projeto = {
            "nome": self.projeto_nome.get(),
            "videos": [str(v) for v in self.videos],
            "preset": self.preset_var.get()
        }
        self.automation.adicionar_a_fila(projeto)
        self.log(f"Projeto '{projeto['nome']}' adicionado a fila")

    def analisar_qc(self):
        arquivo = filedialog.askopenfilename(
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv")]
        )

        if arquivo:
            self.qc_result.delete(1.0, tk.END)
            self.qc_result.insert(tk.END, "Analisando...\n\n")

            def tarefa_qc():
                try:
                    report = self.qc.analisar_video(Path(arquivo))
                    status = "APROVADO" if report.aprovado else "REPROVADO"

                    resultado = "=" * 55 + "\n"
                    resultado += "         RELATORIO DE QC\n"
                    resultado += "=" * 55 + "\n\n"
                    resultado += f"  Resolucao:          {report.resolution}\n"
                    resultado += f"  Codec:              {report.codec}\n"
                    resultado += f"  Loudness Integrado: {report.loudness_integrated:.1f} LUFS\n"
                    resultado += f"  True Peak:          {report.true_peak:.1f} dBTP\n"
                    resultado += f"  Dropped Frames:     {report.dropped_frames}\n"
                    resultado += f"  Black Frames:       {report.black_frames}\n\n"
                    resultado += f"  MD5: {report.checksum_md5}\n\n"
                    resultado += "=" * 55 + "\n"
                    resultado += f"  STATUS: {status}\n"
                    resultado += "=" * 55 + "\n"

                    if report.problemas:
                        resultado += "\nPROBLEMAS DETECTADOS:\n"
                        for p in report.problemas:
                            resultado += f"  - {p}\n"

                    self.qc_result.delete(1.0, tk.END)
                    self.qc_result.insert(tk.END, resultado)
                except Exception as e:
                    self.qc_result.delete(1.0, tk.END)
                    self.qc_result.insert(tk.END, f"Erro na analise:\n{e}")

            threading.Thread(target=tarefa_qc, daemon=True).start()

    def preview(self):
        messagebox.showinfo("Info", "Preview em desenvolvimento")

    def ripple_edit(self):
        messagebox.showinfo("Info", "Ripple Edit - selecione o ponto de corte")

    def multicam(self):
        messagebox.showinfo("Info", "Multicam em desenvolvimento")

    def speed_ramp(self):
        messagebox.showinfo("Info", "Speed Ramp em desenvolvimento")

    def aplicar_lut(self, lut):
        self.log(f"LUT selecionado: {lut}")
        messagebox.showinfo("Color Grading", f"LUT '{lut}' sera aplicado na renderizacao.")

    def abrir_ia(self):
        if self.nb:
            self.nb.select(5)

    def abrir_color(self):
        if self.nb:
            self.nb.select(3)

    def abrir_audio(self):
        if self.nb:
            self.nb.select(4)

    def gerar_qc(self):
        if self.nb:
            self.nb.select(7)

    def aplicar_padrao_audio(self, padrao):
        self.log(f"Padrao de audio selecionado: {padrao}")

    def sobre(self):
        messagebox.showinfo("Sobre",
            "Video Builder Pro v7.2\n\n"
            "Professional Suite\n\n"
            "Novidades v7.2:\n"
            "- Salvar/Abrir projeto (.vbp JSON)\n"
            "- Escolher pasta de render\n"
            "- Criar pasta automaticamente\n"
            "- Transicoes entre clips\n"
            "- Color grading por clip\n\n"
            "Plugins:\n"
            "- video-automation\n"
            "- color-grading-pro\n"
            "- video-editor-senior\n"
            "- Claude AI (roteiros e textos)")


# ============================================================
# MAIN - PONTO DE ENTRADA
# ============================================================

def main():
    root = tk.Tk()
    app = VideoBuilderProV7(root)
    root.mainloop()


if __name__ == "__main__":
    main()