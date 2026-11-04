#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIDEO BUILDER PRO v7.7 - PROFESSIONAL SUITE
Integracao: video-automation + color-grading-pro + video-editor-senior + Claude AI

Correcoes v7.7 neste arquivo (detalhes em CHANGELOG.md, secao "base"):
  RENDER  - clipes com resolucao/fps/codec diferentes geravam saida
            dessincronizada (video 7,24 s x audio 3,04 s no teste); agora cada
            clipe e normalizado no filter_complex (scale/pad/fps/aresample) e
            unido pelo filtro concat (ou xfade). Respeita inicio/fim, velocidade,
            speed ramp, look/LUT, ajustes de cor, EQ, trilha com ducking e
            loudness alvo (2 passadas). Nao gera mais proxies inuteis.
  QC      - true peak, LRA, black/freeze frames, quadros faltando e bitrate
            reais; video sem audio era APROVADO (fallback -23 fixo) e agora
            reprova; alvo de loudness segue o padrao do projeto; relatorio PDF.
  CHAVE   - API key no cofre do sistema (keyring) quando disponivel; senao em
            arquivo com permissao 600 (antes base64 em arquivo 644). A chave
            nao e mais carregada no campo da tela.
  THREADS - nenhuma thread de trabalho toca em widget (UIDispatcher).
  UI      - Abrir/Salvar projeto, Timeline (in/out, ordem, ripple, velocidade,
            speed ramp, multicam por audio, preview), aba Cor e aba Audio
            ligadas ao render, fila de render processavel.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
except ImportError:
    print("ERRO: Tkinter nao encontrado! (Linux: sudo apt install python3-tk)")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

# Modulos compartilhados (pasta modules/ ao lado deste arquivo)
_MODULOS = Path(__file__).resolve().parent / "modules"
if str(_MODULOS) not in sys.path:
    sys.path.insert(0, str(_MODULOS))

from ffmpeg_utils import (FFmpegErro, abrir_no_player, cadeia_atempo, diretorio_config,  # noqa: E402
                          executar, executar_com_progresso, info_midia, md5_arquivo,
                          medir_loudness, normalizar_loudness, obter_logger, padrao_loudness,
                          PADROES_LOUDNESS, proteger, tipos_video, tipos_midia, EXTS_AUDIO)
from luts_manager import LUTManager  # noqa: E402
from transitions_gl import GLTransition, GLTransitionsEngine  # noqa: E402
from ui_thread import UIDispatcher  # noqa: E402

VERSAO = "7.9"
from ffmpeg_utils import EXTS_VIDEO  # noqa: E402  (fonte unica das extensoes)
import motor_local  # noqa: E402  (v7.9: motor de IA local, Ollama)

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
    # v7.7
    rampa: List[Tuple[float, float]] = field(default_factory=list)   # [(t_relativo, velocidade)]
    ajustes_cor: Dict[str, float] = field(default_factory=dict)      # eq por clipe (match/auto)
    duracao_fonte: float = 0.0                                       # duracao do arquivo

    def duracao_saida(self) -> float:
        """Duracao no resultado final (considera in/out, velocidade e rampa)."""
        dur = max(0.0, self.fim - self.inicio)
        if self.rampa:
            return SeniorEditorEngine.duracao_com_rampa(dur, self.rampa)
        return dur / (self.speed or 1.0)


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
    # v7.7 - escolhas das abas Cor/Audio/Timeline que antes eram ignoradas
    look: str = ""                      # id/nome de look ou LUT .cube ("" = nenhum)
    look_intensidade: float = 1.0
    ajustes_cor: Dict[str, float] = field(default_factory=dict)  # brightness/contrast/saturation
    padrao_audio: str = "EBU R128"
    normalizar_audio: bool = False
    eq: Dict[str, float] = field(default_factory=dict)            # low/mid/high em dB
    transicao: str = ""                 # id do GLTransitionsEngine ("" = corte seco)
    duracao_transicao: float = 0.5
    # v7.8: como encaixar clipes de proporcao diferente na resolucao do projeto
    #   ajustar   = video inteiro + barras pretas (comportamento ate a v7.7, padrao)
    #   preencher = recorta o centro para ocupar a tela toda (Reels a partir de 16:9)
    #   desfocar  = video inteiro sobre ele mesmo ampliado e desfocado
    enquadramento: str = "ajustar"


@dataclass
class QCReport:
    loudness_integrated: Optional[float] = None
    loudness_range: Optional[float] = None
    true_peak: Optional[float] = None
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
    # v7.7
    avisos: List[str] = field(default_factory=list)
    padrao: str = "EBU R128"
    alvo_lufs: float = -23.0
    tem_audio: bool = False
    duracao: float = 0.0
    arquivo: str = ""

    def texto(self) -> str:
        def f(v, un):
            return f"{v:.1f} {un}" if isinstance(v, (int, float)) else "-"
        status = "APROVADO" if self.aprovado else "REPROVADO"
        linhas = ["=" * 58, "         RELATORIO DE QC - Video Builder Pro " + VERSAO, "=" * 58, "",
                  f"  Arquivo:            {Path(self.arquivo).name}",
                  f"  Duracao:            {self.duracao:.2f} s",
                  f"  Resolucao:          {self.resolution}",
                  f"  Codec:              {self.codec}",
                  f"  Bitrate medio/max:  {self.bitrate_avg / 1e6:.2f} / {self.bitrate_max / 1e6:.2f} Mbps",
                  f"  Padrao de audio:    {self.padrao} (alvo {self.alvo_lufs:.0f} LUFS)",
                  f"  Loudness integrado: {f(self.loudness_integrated, 'LUFS')}",
                  f"  Loudness range:     {f(self.loudness_range, 'LU')}",
                  f"  True peak:          {f(self.true_peak, 'dBTP')}",
                  f"  Quadros faltando:   {self.dropped_frames} (estimado)",
                  f"  Trechos pretos:     {self.black_frames}",
                  f"  Trechos congelados: {self.freeze_frames}", "",
                  f"  MD5: {self.checksum_md5}", "", "=" * 58, f"  STATUS: {status}", "=" * 58]
        if self.problemas:
            linhas += ["", "PROBLEMAS:"] + [f"  - {p}" for p in self.problemas]
        if self.avisos:
            linhas += ["", "AVISOS:"] + [f"  - {a}" for a in self.avisos]
        return "\n".join(linhas) + "\n"


# ============================================================
# SERIALIZACAO DE PROJETO (Abrir/Salvar - antes "em desenvolvimento")
# ============================================================

FORMATO_PROJETO = 1


def timeline_para_dict(tl: ProjectTimeline) -> Dict:
    def clip(c: ClipTimeline) -> Dict:
        return {"arquivo": str(c.arquivo), "inicio": c.inicio, "fim": c.fim, "duracao": c.duracao,
                "nome": c.nome, "speed": c.speed, "rampa": [list(p) for p in c.rampa],
                "ajustes_cor": c.ajustes_cor, "color_grade": c.color_grade.value,
                "camera_angle": c.camera_angle, "duracao_fonte": c.duracao_fonte}
    d = {"formato": FORMATO_PROJETO, "versao_app": VERSAO, "salvo_em": datetime.now().isoformat(timespec="seconds"),
         "clips": [clip(c) for c in tl.clips]}
    for k in ("resolucao", "fps", "projeto_nome", "autor", "copyright", "descricao", "look",
              "look_intensidade", "ajustes_cor", "padrao_audio", "normalizar_audio", "eq",
              "transicao", "duracao_transicao", "enquadramento"):
        d[k] = getattr(tl, k)
    d["resolucao"] = list(tl.resolucao)
    d["music"] = None if tl.music is None else {
        "arquivo": str(tl.music.arquivo), "volume": tl.music.volume, "ducking": tl.music.ducking,
        "ducking_level": tl.music.ducking_level, "loop": tl.music.loop}
    return d


def timeline_de_dict(d: Dict) -> ProjectTimeline:
    if d.get("formato", 1) > FORMATO_PROJETO:
        raise ValueError("Projeto salvo por uma versao mais nova do Video Builder Pro.")
    clips = []
    for c in d.get("clips", []):
        clips.append(ClipTimeline(
            arquivo=Path(c["arquivo"]), inicio=float(c["inicio"]), fim=float(c["fim"]),
            duracao=float(c.get("duracao", c["fim"] - c["inicio"])), nome=c.get("nome", ""),
            speed=float(c.get("speed", 1.0)), rampa=[tuple(p) for p in c.get("rampa", [])],
            ajustes_cor=c.get("ajustes_cor", {}), color_grade=ColorGrade(c.get("color_grade", "none")),
            camera_angle=int(c.get("camera_angle", 0)), duracao_fonte=float(c.get("duracao_fonte", 0))))
    tl = ProjectTimeline(clips=clips)
    for k in ("fps", "projeto_nome", "autor", "copyright", "descricao", "look", "look_intensidade",
              "ajustes_cor", "padrao_audio", "normalizar_audio", "eq", "transicao", "duracao_transicao",
              "enquadramento"):
        if k in d:
            setattr(tl, k, d[k])
    tl.resolucao = tuple(d.get("resolucao", (1920, 1080)))
    if d.get("music"):
        m = d["music"]
        tl.music = MusicTrack(Path(m["arquivo"]), m.get("volume", 0.3), m.get("ducking", True),
                              m.get("ducking_level", 0.15), m.get("loop", False))
    return tl


# ============================================================
# CONFIG MANAGER
# ============================================================

class ConfigManager:
    """Configuracao em ~/.video_builder_pro/config_v7.json.

    v7.7: chaves de API ficam no cofre do sistema (pacote 'keyring':
    Credential Manager no Windows, Secret Service/KWallet no Linux, Keychain
    no macOS). Sem keyring, ficam no JSON (base64 = apenas ofuscacao) com
    permissao 600. O diretorio fica com 700 e a gravacao e atomica.
    """

    SERVICO_KEYRING = "video-builder-pro"

    def __init__(self):
        self.config_dir = diretorio_config()
        self.config_file = self.config_dir / "config_v7.json"
        self.config = self._carregar()
        proteger(self.config_file, 0o600)

    def _carregar(self) -> Dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError) as e:
                obter_logger().error("config corrompida (%s): usando padrao", e)
                return {}
        return {}

    def salvar(self):
        tmp = self.config_file.with_suffix(".tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            os.replace(tmp, self.config_file)
            proteger(self.config_file, 0o600)
        except OSError as e:
            obter_logger().error("erro ao salvar config: %s", e)

    @staticmethod
    def _keyring():
        try:
            import keyring
            backend = keyring.get_keyring()
            # backends "fail"/"null" nao guardam nada
            if "fail" in type(backend).__module__ or "null" in type(backend).__module__:
                return None
            return keyring
        except Exception:  # noqa: BLE001 - keyring ausente ou sem backend
            return None

    def _encode(self, texto: str) -> str:
        import base64
        return base64.b64encode(texto.encode("utf-8")).decode("ascii")

    def _decode(self, texto: str) -> str:
        import base64
        try:
            return base64.b64decode(texto.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeError):
            return ""

    def onde_esta_chave(self, provedor: str) -> str:
        kr = self._keyring()
        try:   # v7.8.1: cofre bloqueado/sem D-Bus nao pode derrubar a tela (excecao no meio do salvar)
            if kr and kr.get_password(self.SERVICO_KEYRING, provedor):
                return "cofre do sistema"
        except Exception:  # noqa: BLE001
            pass
        if self.config.get("api_keys", {}).get(provedor):
            return f"arquivo {self.config_file} (permissao 600)"
        return ""

    def get_api_key(self, provedor: str) -> str:
        kr = self._keyring()
        if kr:
            try:
                v = kr.get_password(self.SERVICO_KEYRING, provedor)
                if v:
                    return v
            except Exception:  # noqa: BLE001
                pass
        return self._decode(self.config.get("api_keys", {}).get(provedor, ""))

    def set_api_key(self, provedor: str, key: str):
        kr = self._keyring()
        if kr:
            try:
                kr.set_password(self.SERVICO_KEYRING, provedor, key)
                self.config.get("api_keys", {}).pop(provedor, None)  # migra: remove do arquivo
                self.salvar()
                return
            except Exception as e:  # noqa: BLE001
                obter_logger().warning("keyring falhou (%s): gravando no arquivo 600", e)
        self.config.setdefault("api_keys", {})[provedor] = self._encode(key)
        self.salvar()

    def get(self, chave: str, default: Any = None) -> Any:
        return self.config.get(chave, default)

    def set(self, chave: str, valor: Any):
        self.config[chave] = valor
        self.salvar()


# ============================================================
# CLAUDE AI ENGINE - A INTELIGENCIA DO APP
# ============================================================

def traduzir_erro_api(status: int, texto: str) -> str:
    """v7.9: erros comuns da API do Claude em portugues, com o que fazer.
    O texto original continua no final (para suporte)."""
    baixo = (texto or "").lower()
    if "credit balance" in baixo:
        dica = ("Sua conta da API da Anthropic esta sem creditos.\n"
                "Compre creditos em console.anthropic.com > Settings > Billing\n"
                "ou use o motor GRATUITO local: aba IA > Motor > Ollama (local).")
    elif status in (401, 403):
        dica = "Chave da API recusada (invalida ou revogada). Gere outra em console.anthropic.com > API Keys."
    elif status == 429:
        dica = "Limite de uso da API atingido. Aguarde alguns minutos ou use o motor Ollama (local)."
    elif status in (500, 502, 503, 529):
        dica = "A API do Claude esta instavel/sobrecarregada. Tente de novo em instantes."
    elif status == 404 and "model" in baixo:
        dica = "Modelo nao encontrado. Confira o nome no campo Modelo (ex.: claude-haiku-4-5-20251001)."
    else:
        dica = "Erro da API do Claude."
    return f"{dica}\n\n(Detalhe tecnico {status}: {(texto or '')[:300]})"


class ClaudeEngine:
    """Gera roteiros, titulos e textos via IA.

    v7.9: o nome ficou (todo o app usa self.claude), mas agora ha DOIS motores:
      - "claude": API da Anthropic (pago por uso, melhor qualidade) - PADRAO;
      - "ollama": modelo aberto rodando no proprio computador (gratis, offline).
    Config: motor_ia, claude_model, ollama_model, ollama_url."""

    MOTORES = ("claude", "ollama")
    MODELO_CLAUDE_PADRAO = "claude-haiku-4-5-20251001"

    def __init__(self, config: ConfigManager, log_callback: Callable):
        self.config = config
        self.log = log_callback
        self.url = "https://api.anthropic.com/v1/messages"

    # ---- motor ativo (v7.9)
    def motor(self) -> str:
        m = self.config.get("motor_ia", "claude")
        return m if m in self.MOTORES else "claude"

    def definir_motor(self, motor: str):
        if motor not in self.MOTORES:
            raise ValueError(f"Motor desconhecido: {motor}")
        self.config.set("motor_ia", motor)
        self.log(f"IA: motor ativo = {self.nome_motor()}")

    def nome_motor(self) -> str:
        return "Claude (API)" if self.motor() == "claude" else "Ollama (local)"

    def local(self) -> "motor_local.OllamaCliente":
        return motor_local.OllamaCliente(self.config.get("ollama_url", motor_local.URL_PADRAO), self.log)

    def pronto(self) -> bool:
        """Ha motor configurado? (Claude: chave salva; Ollama: escolhido - o servidor e
        conferido na chamada, para nao travar a tela com rede aqui.)"""
        return self.motor() == "ollama" or self.tem_chave()

    def tem_chave(self) -> bool:
        return bool(self.config.get_api_key("claude"))

    def salvar_chave(self, chave: str):
        self.config.set_api_key("claude", chave.strip())

    def modelo(self) -> str:
        if self.motor() == "ollama":
            return self.config.get("ollama_model", motor_local.MODELO_PADRAO)
        return self.config.get("claude_model", self.MODELO_CLAUDE_PADRAO)

    def definir_modelo(self, modelo: str):
        modelo = (modelo or "").strip()
        if modelo:
            self.config.set("ollama_model" if self.motor() == "ollama" else "claude_model", modelo)

    def testar_motor(self) -> Tuple[bool, str]:
        if self.motor() == "ollama":
            return self.local().testar(self.modelo())
        return self.testar_chave()

    def gerar(self, prompt: str, system: str = "", max_tokens: int = 2000) -> str:
        return self.mensagem(prompt, system=system, max_tokens=max_tokens)

    def testar_chave(self, chave: str = "") -> Tuple[bool, str]:
        """v7.8.1: confere a chave com a API (GET /v1/models: nao gera tokens, sem custo)."""
        if requests is None:
            return False, "Pacote 'requests' nao instalado."
        chave = chave or self.config.get_api_key("claude")
        if not chave:
            return False, "Nenhuma chave salva."
        try:
            r = requests.get("https://api.anthropic.com/v1/models",
                             headers={"x-api-key": chave, "anthropic-version": "2023-06-01"}, timeout=20)
        except Exception as e:  # noqa: BLE001
            return False, f"Sem conexao com a API: {e}"
        if r.status_code == 200:
            return True, "Chave valida."
        if r.status_code in (401, 403):
            return False, "Chave recusada pela Anthropic (invalida, revogada ou sem permissao)."
        return False, f"Resposta inesperada da API ({r.status_code}): {r.text[:200]}"

    def mensagem(self, conteudo: Union[str, List[Dict]], system: str = "", max_tokens: int = 2000,
                 timeout: float = 180) -> str:
        """v7.8: como gerar(), mas aceita lista de blocos (texto e imagens base64)
        para a visao do Diretor/Revisor IA. Bloco de imagem:
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ...}}"""
        if self.motor() == "ollama":
            return self.local().chat(conteudo, self.modelo(), system=system, max_tokens=max_tokens)
        if requests is None:
            raise RuntimeError("Pacote 'requests' nao instalado. Rode: pip install requests")
        chave = self.config.get_api_key("claude")
        if not chave:
            raise RuntimeError("Chave da API nao configurada. Abra a aba IA e salve sua chave.")
        headers = {"x-api-key": chave, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        body = {"model": self.modelo(), "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": conteudo}]}
        if system:
            body["system"] = system
        try:
            resp = requests.post(self.url, headers=headers, json=body, timeout=timeout)
        except Exception as e:  # noqa: BLE001 - rede/timeout/DNS
            raise RuntimeError(f"Falha de conexao com a API: {e}") from e
        if resp.status_code != 200:
            raise RuntimeError(traduzir_erro_api(resp.status_code, resp.text))
        dados = resp.json()
        partes = [b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text"]
        return "".join(partes).strip()

    # --- Atalhos prontos para video ---

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
        self.proxies: Dict[str, Path] = {}   # original -> proxy (usado pelo preview)

    def criar_proxy(self, video: Path, resolucao: str = "1280x720") -> Path:
        """Proxy leve para preview fluido (o render final usa sempre o original)."""
        video = Path(video)
        proxy_path = self.temp_dir / f"proxy_{abs(hash(str(video)))}_{video.stem}.mp4"
        w, h = resolucao.split("x")
        cmd = ["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0", "-map", "0:a:0?",
               "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2",
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", str(proxy_path)]
        executar(cmd, self.log)
        self.proxies[str(video)] = proxy_path
        return proxy_path

    def adicionar_a_fila(self, projeto: Dict):
        """projeto = {'nome', 'saida', 'preset', 'timeline': timeline_para_dict(...)}"""
        self.fila_render.append(projeto)
        self.log(f"Projeto adicionado a fila ({len(self.fila_render)}): {projeto.get('nome', 'Sem nome')}")

    def processar_fila(self, renderizar: Callable[[ProjectTimeline, Path, "RenderPreset"], Path],
                       callback_progresso: Callable = None) -> List[Tuple[str, bool, str]]:
        """Renderiza cada projeto da fila. Antes so registrava no log, sem render."""
        resultados = []
        total = len(self.fila_render)
        while self.fila_render:
            projeto = self.fila_render.pop(0)
            i = total - len(self.fila_render)
            nome = projeto.get("nome", "Sem nome")
            self.log(f"[FILA] Renderizando {i}/{total}: {nome}")
            try:
                tl = timeline_de_dict(projeto["timeline"])
                preset = RenderPreset[projeto.get("preset", "FAST")]
                renderizar(tl, Path(projeto["saida"]), preset)
                resultados.append((nome, True, str(projeto["saida"])))
            except Exception as e:  # noqa: BLE001 - um projeto ruim nao para a fila
                self.log(f"[FILA] Falhou '{nome}': {e}")
                resultados.append((nome, False, str(e)))
            if callback_progresso:
                callback_progresso(i / total * 100)
        return resultados

    def exportar_edl_xml(self, timeline: ProjectTimeline, saida: Path,
                         formato: str = "premiere") -> Path:
        return self._exportar_premiere_xml(timeline, saida)

    def _exportar_premiere_xml(self, timeline: ProjectTimeline, saida: Path) -> Path:
        """FCP7 XML (xmeml v4), importavel no Premiere e no DaVinci Resolve.

        v7.7: inclui in/out/start/end (antes so a duracao fixa de 10 s), taxa
        da sequencia, e 'pathurl' como URI valida (file:///C:/..., espacos
        codificados) - antes "file://C:\\..." nao era encontrado.
        """
        fps = int(timeline.fps)

        def rate(pai):
            r = ET.SubElement(pai, "rate")
            ET.SubElement(r, "timebase").text = str(fps)
            ET.SubElement(r, "ntsc").text = "FALSE"

        xmeml = ET.Element("xmeml", version="4")
        seq = ET.SubElement(xmeml, "sequence")
        ET.SubElement(seq, "name").text = timeline.projeto_nome or "Sequencia"
        rate(seq)
        media = ET.SubElement(seq, "media")
        fmt = ET.SubElement(ET.SubElement(media, "video"), "format")
        sc = ET.SubElement(fmt, "samplecharacteristics")
        ET.SubElement(sc, "width").text = str(timeline.resolucao[0])
        ET.SubElement(sc, "height").text = str(timeline.resolucao[1])
        track = ET.SubElement(media.find("video"), "track")
        pos = 0
        for i, clip in enumerate(timeline.clips):
            ini_f, fim_f = int(round(clip.inicio * fps)), int(round(clip.fim * fps))
            dur_f = max(1, fim_f - ini_f)
            item = ET.SubElement(track, "clipitem", id=f"clipitem-{i + 1}")
            ET.SubElement(item, "name").text = clip.nome or Path(clip.arquivo).name
            ET.SubElement(item, "duration").text = str(int(round((clip.duracao_fonte or clip.fim) * fps)))
            rate(item)
            ET.SubElement(item, "start").text = str(pos)
            ET.SubElement(item, "end").text = str(pos + dur_f)
            ET.SubElement(item, "in").text = str(ini_f)
            ET.SubElement(item, "out").text = str(fim_f)
            f = ET.SubElement(item, "file", id=f"file-{i + 1}")
            ET.SubElement(f, "name").text = Path(clip.arquivo).name
            ET.SubElement(f, "pathurl").text = Path(clip.arquivo).resolve().as_uri()
            rate(f)
            pos += dur_f
        ET.SubElement(seq, "duration").text = str(pos)
        ET.indent(xmeml) if hasattr(ET, "indent") else None
        ET.ElementTree(xmeml).write(saida, encoding="UTF-8", xml_declaration=True)
        self.log(f"EDL exportado: {saida}")
        return Path(saida)

    def gerar_checksum(self, arquivo: Path) -> str:
        return md5_arquivo(Path(arquivo))

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()


# ============================================================
# COLOR-GRADING-PRO PLUGIN
# ============================================================

class ColorGradingEngine:
    """v7.7: delega ao LUTManager (antes havia uma copia dos mesmos filtros)
    e implementa de verdade a analise de luminosidade e o match de cameras
    (antes valores fixos)."""

    def __init__(self, log_callback: Callable):
        self.log = log_callback
        self.luts = LUTManager(log_callback)
        self.luts_disponiveis: Dict[str, Optional[Path]] = {}
        self.carregar_luts()

    def carregar_luts(self):
        self.luts_disponiveis = {l.nome: l.arquivo for l in self.luts.listar_luts()}

    def aplicar_lut(self, video: Path, lut: Union[str, Path], saida: Path, intensidade: float = 1.0) -> Path:
        lut_path = Path(str(lut))
        if lut_path.suffix.lower() == ".cube" and lut_path.exists():
            self.luts.adicionar_lut_personalizada(lut_path.stem, lut_path)
            lut = lut_path.stem
        return self.luts.aplicar_lut(Path(video), str(lut), Path(saida), intensidade)

    def _analisar_sinal(self, video: Path, amostras_por_seg: float = 1.0) -> Dict[str, float]:
        r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an",
                      "-vf", f"fps={amostras_por_seg},signalstats,metadata=print:file=-",
                      "-f", "null", "-"])
        vals: Dict[str, List[float]] = {}
        for linha in r.stdout.splitlines():
            m = re.match(r"lavfi\.signalstats\.(YAVG|YMIN|YMAX|UAVG|VAVG|SATAVG)=([\d.]+)", linha.strip())
            if m:
                vals.setdefault(m.group(1), []).append(float(m.group(2)))
        if "YAVG" not in vals:
            raise RuntimeError(f"Nao foi possivel analisar {Path(video).name}")
        return {k: sum(v) / len(v) for k, v in vals.items()}

    def _analisar_luminosidade(self, video: Path) -> Dict:
        """IRE aproximado a partir do luma 8 bits (16 = 0 IRE, 235 = 100 IRE)."""
        s = self._analisar_sinal(video)

        def ire(y):
            return max(0.0, min(100.0, (y - 16.0) / 219.0 * 100.0))
        return {"media_ire": ire(s["YAVG"]), "min_ire": ire(s.get("YMIN", 16)),
                "max_ire": ire(s.get("YMAX", 235))}

    def calcular_exposicao(self, video: Path, alvo_ire: float = 50.0) -> Dict[str, float]:
        analise = self._analisar_luminosidade(video)
        brilho = max(-0.3, min(0.3, (alvo_ire - analise["media_ire"]) / 100.0 * 0.8))
        self.log(f"Exposicao: media {analise['media_ire']:.0f} IRE -> alvo {alvo_ire:.0f} IRE "
                 f"(brightness {brilho:+.3f})")
        return {"brightness": round(brilho, 4)}

    def corrigir_exposicao(self, video: Path, saida: Path, alvo_ire: float = 50.0) -> Path:
        c = self.calcular_exposicao(video, alvo_ire)
        info = info_midia(Path(video))
        cmd = ["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0", "-vf", f"eq=brightness={c['brightness']}",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        cmd += ["-map", "0:a:0", "-c:a", "copy"] if info["tem_audio"] else []
        executar(cmd + [str(saida)], self.log)
        return Path(saida)

    def calcular_match(self, video_referencia: Path, video_alvo: Path) -> Dict[str, float]:
        """Aproxima o alvo da referencia: brilho (Y medio), saturacao e
        balanco de cor de meios-tons (U/V medios). E uma correcao global
        aproximada, nao um match por histograma."""
        ref, alvo = self._analisar_sinal(video_referencia), self._analisar_sinal(video_alvo)
        aj = {"brightness": round(max(-0.3, min(0.3, (ref["YAVG"] - alvo["YAVG"]) / 255.0)), 4)}
        if alvo.get("SATAVG", 0) > 1 and ref.get("SATAVG"):
            aj["saturation"] = round(max(0.5, min(2.0, ref["SATAVG"] / alvo["SATAVG"])), 4)
        # U (Cb) maior = mais azul; V (Cr) maior = mais vermelho
        du = (ref.get("UAVG", 128) - alvo.get("UAVG", 128)) / 128.0
        dv = (ref.get("VAVG", 128) - alvo.get("VAVG", 128)) / 128.0
        aj["rm"] = round(max(-0.5, min(0.5, dv)), 4)
        aj["bm"] = round(max(-0.5, min(0.5, du)), 4)
        aj["gm"] = round(max(-0.5, min(0.5, -(du + dv) / 2)), 4)
        return aj

    def match_cameras(self, video_referencia: Path, video_alvo: Path, saida: Path) -> Path:
        aj = self.calcular_match(video_referencia, video_alvo)
        self.log(f"Match de cameras: {aj}")
        info = info_midia(Path(video_alvo))
        cmd = ["ffmpeg", "-y", "-i", str(video_alvo), "-map", "0:v:0", "-vf", filtro_ajustes(aj),
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        cmd += ["-map", "0:a:0", "-c:a", "copy"] if info["tem_audio"] else []
        executar(cmd + [str(saida)], self.log)
        return Path(saida)


def filtro_ajustes(aj: Dict[str, float]) -> str:
    """eq (brightness/contrast/saturation/gamma) + colorbalance (rm/gm/bm)."""
    partes = []
    eq = {k: aj[k] for k in ("brightness", "contrast", "saturation", "gamma") if k in aj}
    neutro = {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0, "gamma": 1.0}
    eq = {k: v for k, v in eq.items() if abs(v - neutro[k]) > 1e-4}
    if eq:
        partes.append("eq=" + ":".join(f"{k}={v}" for k, v in eq.items()))
    cb = {k: aj[k] for k in ("rs", "gs", "bs", "rm", "gm", "bm", "rh", "gh", "bh") if abs(aj.get(k, 0)) > 1e-4}
    if cb:
        partes.append("colorbalance=" + ":".join(f"{k}={v}" for k, v in cb.items()))
    return ",".join(partes) or "null"


# ============================================================
# VIDEO-EDITOR-SENIOR PLUGIN
# ============================================================

class SeniorEditorEngine:
    """Operacoes de edicao sobre a timeline sequencial (sem buracos).

    v7.7: ripple/slide/slip/multicam/speed ramp eram stubs ou estavam errados
    (ripple subtraia o ponto de corte do inicio de cada clipe, mexendo no
    material de origem em vez da posicao na timeline).
    """

    def __init__(self, log_callback: Callable):
        self.log = log_callback

    # ---------------------------------------------------- posicoes
    @staticmethod
    def posicoes(timeline: ProjectTimeline) -> List[Tuple[float, float]]:
        """(inicio, fim) de cada clipe NA TIMELINE (tempo de saida)."""
        res, t = [], 0.0
        for c in timeline.clips:
            d = c.duracao_saida()
            res.append((t, t + d))
            t += d
        return res

    def ripple_edit(self, timeline: ProjectTimeline, ponto_corte: float,
                    duracao: Optional[float] = None) -> ProjectTimeline:
        """Ripple delete. Sem 'duracao': remove o clipe que contem o ponto.
        Com 'duracao': remove o trecho [ponto, ponto+duracao] da timeline,
        dividindo clipes se preciso; o restante 'anda' para fechar o buraco."""
        if duracao is None:
            for i, (a, b) in enumerate(self.posicoes(timeline)):
                if a <= ponto_corte < b:
                    removido = timeline.clips.pop(i)
                    self.log(f"Ripple: removido '{removido.nome}' ({b - a:.2f}s)")
                    break
            return self._recalcular(timeline)
        fim_corte = ponto_corte + duracao
        novos: List[ClipTimeline] = []
        for c, (a, b) in zip(timeline.clips, self.posicoes(timeline)):
            if b <= ponto_corte or a >= fim_corte or c.rampa:
                novos.append(c)
                continue
            esc = c.speed or 1.0
            if a < ponto_corte:     # parte antes do corte
                antes = ClipTimeline(**{**c.__dict__, "fim": c.inicio + (ponto_corte - a) * esc})
                novos.append(antes)
            if b > fim_corte:       # parte depois do corte
                depois = ClipTimeline(**{**c.__dict__, "inicio": c.inicio + (fim_corte - a) * esc})
                novos.append(depois)
        timeline.clips = [self._sync_dur(c) for c in novos]
        self.log(f"Ripple: removidos {duracao:.2f}s a partir de {ponto_corte:.2f}s")
        return self._recalcular(timeline)

    def ripple_delete(self, timeline: ProjectTimeline, indice: int) -> ProjectTimeline:
        timeline.clips.pop(indice)
        return self._recalcular(timeline)

    def slip_edit(self, clip: ClipTimeline, offset: float) -> ClipTimeline:
        """Desloca in/out dentro do material de origem, mantendo a duracao."""
        dur = clip.fim - clip.inicio
        limite = clip.duracao_fonte or (clip.fim + abs(offset))
        novo_ini = max(0.0, min(clip.inicio + offset, limite - dur))
        clip.inicio, clip.fim = novo_ini, novo_ini + dur
        return clip

    def slide_edit(self, timeline: ProjectTimeline, indice: int, offset: float) -> ProjectTimeline:
        """Move o clipe na timeline mantendo seu conteudo: o vizinho anterior
        ganha/perde 'offset' no fim e o seguinte perde/ganha no inicio."""
        if not 0 < indice < len(timeline.clips) - 1:
            raise ValueError("Slide precisa de clipes vizinhos dos dois lados.")
        ant, prox = timeline.clips[indice - 1], timeline.clips[indice + 1]
        offset = max(-(ant.fim - ant.inicio - 0.1), min(offset, prox.fim - prox.inicio - 0.1))
        if ant.duracao_fonte:
            offset = min(offset, ant.duracao_fonte - ant.fim)
        offset = max(offset, -prox.inicio)
        ant.fim += offset
        prox.inicio += offset
        self._sync_dur(ant)
        self._sync_dur(prox)
        return self._recalcular(timeline)

    # ---------------------------------------------------- multicam
    def criar_multicam(self, angulos: List[Path], sincronizar_por: str = "audio") -> List[ClipTimeline]:
        """Clipes alinhados pelo audio: inicio de cada angulo ajustado para o
        mesmo instante real; duracao = trecho comum a todos."""
        infos = [info_midia(Path(a)) for a in angulos]
        atrasos = [0.0] + [self._sincronizar_audio(Path(angulos[0]), Path(a)) for a in angulos[1:]]
        base = min(atrasos)
        inicios = [d - base for d in atrasos]
        comum = min(inf["duracao"] - ini for inf, ini in zip(infos, inicios))
        if comum <= 0:
            raise ValueError("Os angulos nao tem trecho em comum.")
        clips = []
        for i, (a, ini, inf) in enumerate(zip(angulos, inicios, infos)):
            self.log(f"Multicam: Camera_{i + 1} offset {ini:+.2f}s")
            clips.append(ClipTimeline(arquivo=Path(a), inicio=round(ini, 3), fim=round(ini + comum, 3),
                                      duracao=round(comum, 3), camera_angle=i, nome=f"Camera_{i + 1}",
                                      duracao_fonte=inf["duracao"]))
        return clips

    @staticmethod
    def _envelope(midia: Path, segundos: float = 90.0, taxa: int = 100) -> List[float]:
        """Envelope de energia do audio (taxa amostras/s), via ffmpeg."""
        import subprocess
        sr = 8000
        r = subprocess.run(["ffmpeg", "-v", "error", "-t", str(segundos), "-i", str(midia), "-vn",
                            "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
        if r.returncode != 0 or not r.stdout:
            raise RuntimeError(f"Sem audio para sincronizar em {Path(midia).name}")
        import array
        amostras = array.array("h", r.stdout)
        passo = sr // taxa
        env = []
        for i in range(0, len(amostras) - passo + 1, passo):
            bloco = amostras[i:i + passo]
            env.append(sum(abs(x) for x in bloco) / passo)
        # remove media e normaliza (correlacao robusta a ganho diferente)
        m = sum(env) / len(env)
        env = [e - m for e in env]
        n = (sum(e * e for e in env) ** 0.5) or 1.0
        return [e / n for e in env]

    def _sincronizar_audio(self, ref: Path, alvo: Path, max_lag: float = 10.0) -> float:
        """Segundos em que o MESMO som aparece mais tarde no alvo que na
        referencia (positivo = o alvo comecou a gravar antes). Correlacao
        cruzada do envelope de energia a 100 Hz (resolucao de 10 ms)."""
        taxa = 100
        a, b = self._envelope(ref, taxa=taxa), self._envelope(alvo, taxa=taxa)
        lag_max = int(max_lag * taxa)
        try:
            import numpy as np
            corr = np.correlate(np.asarray(b), np.asarray(a), mode="full")
            centro = len(a) - 1
            janela = corr[max(0, centro - lag_max): centro + lag_max + 1]
            melhor = int(np.argmax(janela)) + max(0, centro - lag_max) - centro
        except ImportError:
            melhor, melhor_v = 0, float("-inf")
            for lag in range(-lag_max, lag_max + 1):
                v = sum(b[i + lag] * a[i] for i in range(len(a)) if 0 <= i + lag < len(b))
                if v > melhor_v:
                    melhor, melhor_v = lag, v
        return melhor / taxa

    # ---------------------------------------------------- titulos / velocidade
    def criar_lower_third(self, texto: str, duracao: float, estilo: str = "moderno") -> TitleOverlay:
        return TitleOverlay(texto=texto, inicio=0, fim=duracao, posicao="lower_third",
                            estilo=estilo, tamanho=36, animacao="slide")

    @staticmethod
    def _normalizar_rampa(pontos: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        pts = sorted((float(t), float(v)) for t, v in pontos)
        if not pts or pts[0][0] > 0:
            pts.insert(0, (0.0, pts[0][1] if pts else 1.0))
        for _, v in pts:
            if v <= 0:
                raise ValueError("Velocidade da rampa deve ser > 0")
        return pts

    @classmethod
    def duracao_com_rampa(cls, dur: float, pontos: List[Tuple[float, float]]) -> float:
        pts = [p for p in cls._normalizar_rampa(pontos) if p[0] < dur]
        total = 0.0
        for (t, v), prox in zip(pts, pts[1:] + [(dur, None)]):
            total += (prox[0] - t) / v
        return total

    def speed_ramp(self, clip: ClipTimeline, pontos: List[Tuple[float, float]]) -> str:
        """Filtro setpts com velocidade constante por trecho.

        pontos: [(t_relativo_ao_inicio_do_clipe, velocidade)], ex.
        [(0, 1), (2, 0.5), (4, 2)] = normal ate 2 s, camera lenta ate 4 s,
        depois 2x. Antes devolvia sempre 'setpts=0.5*PTS'.
        """
        pts = self._normalizar_rampa(pontos)
        acumulado, trechos = 0.0, []
        for (t, v), prox in zip(pts, pts[1:] + [(None, None)]):
            trechos.append((t, v, acumulado))
            if prox[0] is not None:
                acumulado += (prox[0] - t) / v
        expr = f"{trechos[-1][2]}+(T-{trechos[-1][0]})/{trechos[-1][1]}"
        for k in range(len(trechos) - 2, -1, -1):
            t, v, c = trechos[k]
            expr = f"if(lt(T,{trechos[k + 1][0]}),{c}+(T-{t})/{v},{expr})"
        return f"setpts='({expr})/TB'"

    # ---------------------------------------------------- util
    @staticmethod
    def _sync_dur(c: ClipTimeline) -> ClipTimeline:
        c.duracao = round(max(0.0, c.fim - c.inicio), 4)
        return c

    def _recalcular(self, timeline: ProjectTimeline) -> ProjectTimeline:
        timeline.duracao_total = sum(c.duracao_saida() for c in timeline.clips)
        return timeline


# ============================================================
# QC AUTOMATION ENGINE
# ============================================================

class QCEngine:
    """v7.7: todas as metricas sao medidas (antes true peak, dropped e black
    frames eram constantes) e o alvo segue o padrao de audio escolhido."""

    TOLERANCIA_LU = 1.0

    def __init__(self, log_callback: Callable, padrao: str = "EBU R128"):
        self.log = log_callback
        self.padrao = padrao

    def analisar_video(self, video: Path, padrao: Optional[str] = None) -> QCReport:
        video = Path(video)
        padrao = padrao or self.padrao
        alvo, tp_max = padrao_loudness(padrao)
        info = info_midia(video)
        report = QCReport(padrao=padrao, alvo_lufs=alvo, tem_audio=info["tem_audio"],
                          duracao=info["duracao"], arquivo=str(video))
        report.resolution = self._obter_resolucao(video)
        report.codec = self._obter_codec(video)
        self.log("QC: medindo loudness (EBU R128)...")
        ld = medir_loudness(video)
        report.loudness_integrated, report.loudness_range, report.true_peak = ld["integrado"], ld["lra"], ld["true_peak"]
        if info["tem_video"]:
            self.log("QC: procurando trechos pretos/congelados...")
            report.black_frames, report.freeze_frames = self._contar_black_freeze(video)
            report.dropped_frames = self._contar_dropped_frames(video, info)
            report.bitrate_avg, report.bitrate_max = self._bitrates(video, info)
        report.checksum_md5 = self._calcular_checksum(video)
        report.aprovado = self._verificar_aprovacao(report, tp_max)
        return report

    # Mantido por compatibilidade (v7.3): retorna o valor medido ou None
    def _analisar_loudness(self, video: Path) -> Optional[float]:
        return medir_loudness(Path(video))["integrado"]

    def _analisar_true_peak(self, video: Path) -> Optional[float]:
        return medir_loudness(Path(video))["true_peak"]

    def _contar_black_freeze(self, video: Path) -> Tuple[int, int]:
        r = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an", "-vf",
                      "blackdetect=d=0.1:pix_th=0.10,freezedetect=n=-60dB:d=0.5", "-f", "null", "-"])
        pretos = len(re.findall(r"black_start:", r.stderr))
        congelados = len(re.findall(r"freeze_start:", r.stderr))
        return pretos, congelados

    def _contar_black_frames(self, video: Path) -> int:
        return self._contar_black_freeze(Path(video))[0]

    def _contar_dropped_frames(self, video: Path, info: Optional[Dict] = None) -> int:
        """Estimativa: quadros esperados (duracao x fps) - quadros presentes."""
        info = info or info_midia(Path(video))
        r = executar(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                      "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(video)])
        try:
            presentes = int(r.stdout.strip().split(",")[0])
        except ValueError:
            return 0
        # duracao do STREAM de video (a do container inclui a cauda do audio)
        esperados = int(round(info["duracao_video"] * (info["fps"] or 0)))
        faltando = esperados - presentes
        # tolera 1 quadro de arredondamento e VFR leve (2%)
        return faltando if faltando > max(1, esperados * 0.02) else 0

    def _bitrates(self, video: Path, info: Dict) -> Tuple[float, float]:
        r = executar(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                      "packet=pts_time,size", "-of", "csv=p=0", str(video)])
        por_seg: Dict[int, int] = {}
        for linha in r.stdout.splitlines():
            try:
                t, tam = linha.split(",")[:2]
                por_seg[int(float(t))] = por_seg.get(int(float(t)), 0) + int(tam)
            except ValueError:
                continue
        maximo = max(por_seg.values()) * 8.0 if por_seg else 0.0
        return float(info.get("bit_rate", 0) or 0), maximo

    def _obter_resolucao(self, video: Path) -> str:
        i = info_midia(Path(video))
        return f"{i['width']}x{i['height']}" if i["tem_video"] else ""

    def _obter_codec(self, video: Path) -> str:
        return info_midia(Path(video))["codec"]

    def _calcular_checksum(self, video: Path) -> str:
        return md5_arquivo(Path(video))

    def _verificar_aprovacao(self, report: QCReport, tp_max: Optional[float] = None) -> bool:
        if tp_max is None:
            tp_max = padrao_loudness(report.padrao)[1]
        problemas, avisos = [], []
        if not report.tem_audio:
            problemas.append("Sem trilha de audio")
        elif report.loudness_integrated is None:
            problemas.append("Audio mudo (loudness nao mensuravel)")
        else:
            if abs(report.loudness_integrated - report.alvo_lufs) > self.TOLERANCIA_LU:
                problemas.append(f"Loudness fora do padrao {report.padrao}: "
                                 f"{report.loudness_integrated:.1f} LUFS (alvo {report.alvo_lufs:.0f} "
                                 f"+/- {self.TOLERANCIA_LU:.0f})")
            if report.true_peak is not None and report.true_peak > tp_max:
                problemas.append(f"True peak muito alto: {report.true_peak:.1f} dBTP (max {tp_max:.0f})")
        if report.dropped_frames > 0:
            problemas.append(f"Quadros faltando (estimado): {report.dropped_frames}")
        if report.black_frames:
            avisos.append(f"{report.black_frames} trecho(s) preto(s) >= 0,1 s")
        if report.freeze_frames:
            avisos.append(f"{report.freeze_frames} trecho(s) congelado(s) >= 0,5 s")
        report.problemas, report.avisos = problemas, avisos
        return not problemas

    def gerar_relatorio_pdf(self, report: QCReport, saida: Path) -> Path:
        """PDF de 1+ paginas (sem dependencias). Antes: 'pass'."""
        saida = Path(saida)
        if saida.suffix.lower() != ".pdf":
            saida.write_text(report.texto(), encoding="utf-8")
            return saida
        escrever_pdf_texto(report.texto().splitlines(), saida)
        self.log(f"Relatorio de QC: {saida}")
        return saida


def escrever_pdf_texto(linhas: List[str], saida: Path, por_pagina: int = 60):
    """Gera um PDF simples (Courier 10) com as linhas de texto."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    paginas = [linhas[i:i + por_pagina] for i in range(0, max(1, len(linhas)), por_pagina)] or [[]]
    objs: List[bytes] = []
    n_pag = len(paginas)
    # 1 catalogo, 2 paginas, 3 fonte, depois (pagina, conteudo) por pagina
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pag))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pag} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    for i, pag in enumerate(paginas):
        corpo = "BT /F1 10 Tf 50 800 Td 12 TL " + " ".join(f"({esc(l)}) '" for l in pag) + " ET"
        dados = corpo.encode("cp1252", "replace")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length " + str(len(dados)).encode() + b" >>\nstream\n" + dados + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(saida).write_bytes(bytes(out))


# ============================================================
# RENDERER PROFISSIONAL
# ============================================================

class ProfessionalRenderer:
    PRESETS = {
        RenderPreset.DRAFT: ("ultrafast", "28"),
        RenderPreset.FAST: ("fast", "23"),
        RenderPreset.BALANCED: ("medium", "20"),
        RenderPreset.HIGH_QUALITY: ("slow", "18"),
        RenderPreset.MASTER: ("veryslow", "15"),
    }
    GRADE_PARA_LOOK = {ColorGrade.CINEMATIC: "cinematic", ColorGrade.VIBRANT: "vibrant",
                       ColorGrade.WARM: "warm", ColorGrade.COLD: "cold",
                       ColorGrade.FILM_NOIR: "film_noir", ColorGrade.ORANGE_TEAL: "orange_teal",
                       ColorGrade.BLEACH_BYPASS: "bleach_bypass", ColorGrade.DAY_FOR_NIGHT: "day_for_night"}

    def __init__(self, log_callback: Callable):
        self.log = log_callback
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_pro_"))
        self.automation = VideoAutomationEngine(log_callback)
        self.color = ColorGradingEngine(log_callback)
        self.editor = SeniorEditorEngine(log_callback)
        self.qc = QCEngine(log_callback)
        self.transicoes = GLTransitionsEngine(log_callback)
        self.ultimo_qc: Optional[QCReport] = None

    def renderizar(self, timeline: ProjectTimeline, saida: Path,
                   preset: RenderPreset = RenderPreset.FAST) -> Path:
        saida = Path(saida)
        if not timeline.clips:
            raise ValueError("Timeline vazia: importe midia primeiro.")
        self.log("=" * 60)
        self.log(f"INICIANDO RENDERIZACAO v{VERSAO} ({preset.value}, "
                 f"{timeline.resolucao[0]}x{timeline.resolucao[1]} @ {timeline.fps} fps)")
        self.log("=" * 60)

        intermediario = saida.with_name(f".{saida.stem}.render_tmp{saida.suffix or '.mp4'}")
        try:
            self._renderizar_timeline(timeline, intermediario, preset)
            if timeline.normalizar_audio:
                alvo, tp = padrao_loudness(timeline.padrao_audio)
                self.log(f"Normalizando loudness para {timeline.padrao_audio} ({alvo} LUFS / {tp} dBTP)...")
                normalizar_loudness(intermediario, saida, alvo, tp, self.log)
            else:
                os.replace(intermediario, saida)
        finally:
            if intermediario.exists():
                intermediario.unlink()

        self.log("Executando QC automatico...")
        report = self.qc.analisar_video(saida, timeline.padrao_audio)
        self.ultimo_qc = report
        if report.aprovado:
            self.log("QC: Aprovado!")
        else:
            self.log("AVISO: QC detectou problemas:")
            for p in report.problemas:
                self.log(f"  - {p}")
        for a in report.avisos:
            self.log(f"  (aviso) {a}")
        self.log(f"Checksum MD5: {report.checksum_md5}")
        self.log("=" * 60)
        self.log("RENDERIZACAO CONCLUIDA!")
        self.log("=" * 60)
        return saida

    # ------------------------------------------------------------ grafo
    def _filtros_clipe(self, i: int, clip: ClipTimeline, info: Dict, tl: ProjectTimeline) -> List[str]:
        w, h = tl.resolucao
        w, h = int(w) - int(w) % 2, int(h) - int(h) % 2
        dur_in = max(0.04, clip.fim - clip.inicio)
        dur_out = clip.duracao_saida()
        v = [f"setpts=PTS-STARTPTS"]
        if clip.rampa:
            v.append(self.editor.speed_ramp(clip, clip.rampa))
        elif abs(clip.speed - 1.0) > 1e-6:
            v.append(f"setpts=PTS/{clip.speed}")
        enq = getattr(tl, "enquadramento", "ajustar")
        cauda = f"setsar=1,fps={tl.fps},format=yuv420p"
        if enq == "preencher":
            v.append(f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},{cauda}")
        elif enq != "desfocar":
            v.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
                     f"{cauda}")
        if tl.ajustes_cor:
            v.append(filtro_ajustes(tl.ajustes_cor))
        if clip.ajustes_cor:
            v.append(filtro_ajustes(clip.ajustes_cor))
        corpo = ",".join(x for x in v if x != "null")
        if enq == "desfocar":
            filtros = [f"[{i}:v]{corpo},split[bgs{i}][fgs{i}]",
                       f"[bgs{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:5[bgb{i}]",
                       f"[fgs{i}]scale={w}:{h}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2[fgz{i}]",
                       f"[bgb{i}][fgz{i}]overlay=(W-w)/2:(H-h)/2,{cauda}[vb{i}]"]
        else:
            filtros = [f"[{i}:v]{corpo}[vb{i}]"]
        look = self.GRADE_PARA_LOOK.get(clip.color_grade) or tl.look
        if look:
            filtros.append(f"[vb{i}]{self.color.luts.obter_filtro_ffmpeg(look, tl.look_intensidade, rotulo=str(i))},"
                           f"format=yuv420p,trim=duration={dur_out:.3f},settb=AVTB[vc{i}]")
        else:
            filtros.append(f"[vb{i}]trim=duration={dur_out:.3f},settb=AVTB[vc{i}]")
        fmt_a = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
        if info["tem_audio"] and not clip.rampa:
            a = ["asetpts=PTS-STARTPTS", fmt_a]
            if abs(clip.speed - 1.0) > 1e-6:
                a.append(cadeia_atempo(clip.speed))
            a.append(f"apad,atrim=duration={dur_out:.3f},asettb=AVTB")
            filtros.append(f"[{i}:a]{','.join(a)}[ac{i}]")
        else:
            if clip.rampa and info["tem_audio"]:
                self.log(f"  {clip.nome}: speed ramp sem audio (atempo nao varia no tempo)")
            filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={dur_out:.3f},{fmt_a},asettb=AVTB[ac{i}]")
        return filtros

    def _renderizar_timeline(self, timeline: ProjectTimeline, saida: Path, preset: RenderPreset) -> Path:
        preset_ffmpeg, crf = self.PRESETS.get(preset, self.PRESETS[RenderPreset.FAST])
        entradas, filtros, infos = [], [], []
        for i, clip in enumerate(timeline.clips):
            info = info_midia(Path(clip.arquivo))
            if not info["tem_video"]:
                raise ValueError(f"'{Path(clip.arquivo).name}' nao tem video.")
            clip.duracao_fonte = info["duracao"]
            clip.fim = min(clip.fim, info["duracao"]) if clip.fim > 0 else info["duracao"]
            clip.inicio = max(0.0, min(clip.inicio, clip.fim - 0.04))
            entradas += ["-ss", f"{clip.inicio:.3f}", "-t", f"{clip.fim - clip.inicio:.3f}",
                         "-i", str(clip.arquivo)]
            filtros += self._filtros_clipe(i, clip, info, timeline)
            infos.append(info)
        n = len(timeline.clips)
        duracoes = [c.duracao_saida() for c in timeline.clips]
        rv, ra = [f"[vc{i}]" for i in range(n)], [f"[ac{i}]" for i in range(n)]

        trans = timeline.transicao if timeline.transicao in self.transicoes.TRANSICOES_GL else ""
        dt = float(timeline.duracao_transicao or 0.5)
        if trans and n > 1 and min(duracoes) > dt + 0.05:
            cadeia, fv, fa = self.transicoes.encadear(rv, ra, duracoes, [GLTransition(trans, dt)] * (n - 1))
            filtros += cadeia
            total = sum(duracoes) - dt * (n - 1)
            self.log(f"Transicao '{trans}' ({dt:.2f}s) entre {n} clipes")
        else:
            if trans and n > 1:
                self.log(f"AVISO: clipes curtos para transicao de {dt:.2f}s: usando corte seco")
            filtros.append("".join(v + a for v, a in zip(rv, ra)) + f"concat=n={n}:v=1:a=1[vcat][acat]")
            fv, fa, total = "[vcat]", "[acat]", sum(duracoes)

        # EQ de 3 bandas (aba Audio)
        eq = timeline.eq or {}
        if any(abs(eq.get(k, 0)) > 0.01 for k in ("low", "mid", "high")):
            filtros.append(f"{fa}bass=g={eq.get('low', 0)}:f=120,equalizer=f=1000:t=q:w=1:g={eq.get('mid', 0)},"
                           f"treble=g={eq.get('high', 0)}:f=6000[aeq]")
            fa = "[aeq]"

        # Trilha sonora com ducking (sidechain pela voz)
        if timeline.music and Path(timeline.music.arquivo).exists():
            m = timeline.music
            if m.loop:
                entradas += ["-stream_loop", "-1"]
            entradas += ["-i", str(m.arquivo)]
            k = n
            filtros.append(f"[{k}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                           f"volume={m.volume},apad,atrim=duration={total:.3f}[mus]")
            if m.ducking:
                filtros.append(f"{fa}asplit=2[voz][sc]")
                filtros.append(f"[mus][sc]sidechaincompress=threshold={max(0.001, m.ducking_level):.3f}:"
                               f"ratio=8:attack=20:release=400[duck]")
                filtros.append("[voz][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix]")
            else:
                filtros.append(f"{fa}[mus]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix]")
            fa = "[amix]"
            self.log(f"Trilha: {Path(m.arquivo).name} (volume {m.volume}, ducking {m.ducking})")

        script = self.temp_dir / "grafo_render.txt"
        script.write_text(";\n".join(filtros), encoding="utf-8")
        cmd = ["ffmpeg", "-y", *entradas, "-filter_complex_script", str(script),
               "-map", fv, "-map", fa, "-c:v", "libx264", "-preset", preset_ffmpeg, "-crf", crf,
               "-pix_fmt", "yuv420p", "-r", str(timeline.fps), "-c:a", "aac", "-b:a", "192k",
               "-ar", "48000", "-movflags", "+faststart", str(saida)]
        timeline.duracao_total = total
        self.log(f"Executando render ({n} clipe(s), {total:.1f}s, preset {preset.value})...")
        executar_com_progresso(cmd, self.log, total)
        return saida

    def exportar_edl(self, timeline: ProjectTimeline, saida: Path, formato: str = "premiere") -> Path:
        return self.automation.exportar_edl_xml(timeline, saida, formato)

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()


# ============================================================
# INTERFACE v7.7 SUITE
# ============================================================

class VideoBuilderProV7:
    TRANSICAO_NENHUMA = "(corte seco)"

    def __init__(self, root):
        self.root = root
        self.root.title(f"Video Builder Pro v{VERSAO} - Professional Suite")
        self.root.geometry("1600x1000")

        self.ui = UIDispatcher(root)
        self.logger = obter_logger()
        self.config = ConfigManager()
        self.clips: List[ClipTimeline] = []
        self.timeline: Optional[ProjectTimeline] = None
        self.qc_report: Optional[QCReport] = None
        self.arquivo_projeto: Optional[Path] = None
        self.trilha: Optional[MusicTrack] = None
        self.nb = None
        self.log_text = None
        self._log_pendente: List[str] = []

        self.automation = VideoAutomationEngine(self.log)
        self.color = ColorGradingEngine(self.log)
        self.editor = SeniorEditorEngine(self.log)
        self.qc = QCEngine(self.log)
        self.renderer = ProfessionalRenderer(self.log)
        self.claude = ClaudeEngine(self.config, self.log)

        self.setup_ui()

    # Compatibilidade: a v7.6 expunha self.videos (lista de Path)
    @property
    def videos(self) -> List[Path]:
        return [Path(c.arquivo) for c in self.clips]

    @videos.setter
    def videos(self, valor: List[Path]):
        self.clips = []
        for v in valor:
            self._adicionar_clip(Path(v), atualizar=False)
        self._atualizar_listas()

    # ------------------------------------------------------------ UI base
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
        menu_arquivo.add_command(label="Abrir Projeto...", command=self.abrir_projeto)
        menu_arquivo.add_command(label="Salvar Projeto", command=self.salvar_projeto)
        menu_arquivo.add_command(label="Salvar Projeto Como...", command=lambda: self.salvar_projeto(como=True))
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Importar Midia", command=self.importar_midia)
        menu_arquivo.add_command(label="Exportar EDL/XML", command=self.exportar_edl)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Sair", command=self.root.quit)

        menu_editar = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edicao", menu=menu_editar)
        menu_editar.add_command(label="Ripple Delete (clipe selecionado)", command=self.ripple_edit)
        menu_editar.add_command(label="Multicam (sincronizar por audio)", command=self.multicam)
        menu_editar.add_command(label="Speed Ramp", command=self.speed_ramp)

        menu_ferramentas = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ferramentas", menu=menu_ferramentas)
        menu_ferramentas.add_command(label="Assistente IA", command=self.abrir_ia)
        menu_ferramentas.add_command(label="Color Grading", command=self.abrir_color)
        menu_ferramentas.add_command(label="Audio Mix", command=self.abrir_audio)
        menu_ferramentas.add_command(label="QC Report", command=self.gerar_qc)
        menu_ferramentas.add_command(label="Abrir pasta de logs", command=self.abrir_logs)

        menu_ajuda = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=menu_ajuda)
        menu_ajuda.add_command(label="Sobre", command=self.sobre)

    # ------------------------------------------------------------ abas
    def criar_aba_projeto(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Projeto  ")
        cf = ttk.LabelFrame(frame, text="Configuracoes do Projeto", padding=20)
        cf.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(cf, text="Nome:").grid(row=0, column=0, sticky=tk.W)
        self.projeto_nome = ttk.Entry(cf, width=40)
        self.projeto_nome.grid(row=0, column=1, padx=10, pady=5)
        self.projeto_nome.insert(0, "Novo Projeto Profissional")

        ttk.Label(cf, text="Resolucao:").grid(row=1, column=0, sticky=tk.W)
        self.resolucao_var = tk.StringVar(value="1920x1080")
        ttk.Combobox(cf, textvariable=self.resolucao_var,
                     values=["1280x720", "1920x1080", "3840x2160", "1080x1920", "1080x1080"]
                     ).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(cf, text="FPS:").grid(row=2, column=0, sticky=tk.W)
        self.fps_var = tk.StringVar(value="25")
        ttk.Combobox(cf, textvariable=self.fps_var, values=["24", "25", "30", "50", "60"]
                     ).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(cf, text="Padrao Audio:").grid(row=3, column=0, sticky=tk.W)
        self.audio_standard = tk.StringVar(value="EBU R128")
        ttk.Combobox(cf, textvariable=self.audio_standard, values=list(PADROES_LOUDNESS),
                     state="readonly").grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(cf, text="(usado no render e no QC)").grid(row=3, column=2, sticky=tk.W)

        # v7.8: enquadramento de clipes com proporcao diferente da do projeto
        ttk.Label(cf, text="Enquadramento:").grid(row=4, column=0, sticky=tk.W)
        self.enquadramento_var = tk.StringVar(value="ajustar")
        ttk.Combobox(cf, textvariable=self.enquadramento_var, values=["ajustar", "preencher", "desfocar"],
                     state="readonly").grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(cf, text="ajustar = barras pretas | preencher = recorta o centro | "
                           "desfocar = fundo desfocado").grid(row=4, column=2, sticky=tk.W)

    def criar_aba_midia(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Midia  ")
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(toolbar, text="Importar", command=self.importar_midia).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Pasta", command=self.carregar_pasta).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Criar Proxies (preview)", command=self.criar_proxies).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Limpar", command=self.limpar_midia).pack(side=tk.LEFT, padx=5)
        self.lista_midia = tk.Listbox(frame, height=10, font=("Helvetica", 10))
        self.lista_midia.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def criar_aba_timeline(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Timeline  ")
        self.timeline_canvas = tk.Canvas(frame, bg="#1e1e1e", height=120)
        self.timeline_canvas.pack(fill=tk.X, padx=10, pady=(10, 4))

        colunas = ("n", "nome", "inicio", "fim", "duracao", "vel")
        self.tree_clips = ttk.Treeview(frame, columns=colunas, show="headings", height=8, selectmode="browse")
        for col, txt, larg in zip(colunas, ("#", "Clipe", "In (s)", "Out (s)", "Duracao final", "Velocidade"),
                                  (40, 380, 90, 90, 110, 120)):
            self.tree_clips.heading(col, text=txt)
            self.tree_clips.column(col, width=larg)
        self.tree_clips.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=10, pady=6)
        for txt, cmd in (("Preview", self.preview), ("In/Out...", self.definir_in_out),
                         ("Velocidade...", self.definir_velocidade), ("Speed Ramp...", self.speed_ramp),
                         ("Subir", lambda: self.mover_clip(-1)), ("Descer", lambda: self.mover_clip(1)),
                         ("Ripple Delete", self.ripple_edit), ("Multicam", self.multicam)):
            ttk.Button(controls, text=txt, command=cmd).pack(side=tk.LEFT, padx=3)

        tf = ttk.LabelFrame(frame, text="Transicao entre clipes", padding=8)
        tf.pack(fill=tk.X, padx=10, pady=6)
        nomes = [self.TRANSICAO_NENHUMA] + [t["nome"] for t in self.renderer.transicoes.listar_transicoes()]
        self._transicao_por_nome = {t["nome"]: t["id"] for t in self.renderer.transicoes.listar_transicoes()}
        self.transicao_var = tk.StringVar(value=self.TRANSICAO_NENHUMA)
        ttk.Combobox(tf, textvariable=self.transicao_var, values=nomes, width=34, state="readonly").pack(side=tk.LEFT)
        ttk.Label(tf, text="  Duracao (s):").pack(side=tk.LEFT)
        self.transicao_dur_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(tf, from_=0.1, to=3.0, increment=0.1, textvariable=self.transicao_dur_var, width=6).pack(side=tk.LEFT)

    def criar_aba_cor(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Cor  ")
        ttk.Label(frame, text="Color Grading Profissional", font=("Helvetica", 16, "bold")).pack(pady=12)

        lut_frame = ttk.LabelFrame(frame, text="Look / LUT do projeto (aplicado no render)", padding=12)
        lut_frame.pack(fill=tk.X, padx=20, pady=6)
        self.look_var = tk.StringVar(value="")
        self.look_label = ttk.Label(lut_frame, text="Look atual: nenhum")
        self.look_label.grid(row=0, column=0, columnspan=5, sticky=tk.W, pady=(0, 6))
        nomes = ["Nenhum"] + [l.nome for l in self.color.luts.listar_luts()]
        for k, nome in enumerate(nomes):
            ttk.Button(lut_frame, text=nome, width=18,
                       command=lambda n=nome: self.aplicar_lut(n)).grid(row=1 + k // 5, column=k % 5, padx=3, pady=3)
        ttk.Button(lut_frame, text="Carregar .cube...", command=self.carregar_cube).grid(
            row=2 + len(nomes) // 5, column=0, pady=6, sticky=tk.W)
        ttk.Label(lut_frame, text="Intensidade:").grid(row=2 + len(nomes) // 5, column=1, sticky=tk.E)
        self.look_intensidade = tk.DoubleVar(value=1.0)
        ttk.Scale(lut_frame, from_=0.0, to=1.0, variable=self.look_intensidade,
                  orient=tk.HORIZONTAL, length=200).grid(row=2 + len(nomes) // 5, column=2, columnspan=2)

        manual = ttk.LabelFrame(frame, text="Ajustes manuais (todos os clipes)", padding=12)
        manual.pack(fill=tk.X, padx=20, pady=6)
        self.cor_exposicao = tk.DoubleVar(value=0.0)
        self.cor_contraste = tk.DoubleVar(value=1.0)
        self.cor_saturacao = tk.DoubleVar(value=1.0)
        for r, (txt, var, a, b) in enumerate((("Exposicao (brilho):", self.cor_exposicao, -0.3, 0.3),
                                              ("Contraste:", self.cor_contraste, 0.5, 2.0),
                                              ("Saturacao:", self.cor_saturacao, 0.0, 2.0))):
            ttk.Label(manual, text=txt).grid(row=r, column=0, sticky=tk.W)
            ttk.Scale(manual, from_=a, to=b, variable=var, orient=tk.HORIZONTAL, length=300).grid(row=r, column=1)
        ttk.Button(manual, text="Zerar ajustes", command=self.zerar_ajustes_cor).grid(row=0, column=2, padx=10)

        auto = ttk.LabelFrame(frame, text="Automaticos (por clipe)", padding=12)
        auto.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(auto, text="Corrigir exposicao (50 IRE)", command=self.auto_exposicao).pack(side=tk.LEFT, padx=4)
        ttk.Button(auto, text="Match de cameras (ref = 1o clipe)", command=self.match_cameras).pack(side=tk.LEFT, padx=4)
        ttk.Button(auto, text="Preview do look (1 quadro)", command=self.preview_look).pack(side=tk.LEFT, padx=4)

    def criar_aba_audio(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Audio  ")
        ttk.Label(frame, text="Mixagem de Audio Profissional", font=("Helvetica", 16, "bold")).pack(pady=12)

        pf = ttk.LabelFrame(frame, text="Padrao de Loudness (render + QC)", padding=12)
        pf.pack(fill=tk.X, padx=20, pady=6)
        for nome, (lufs, tp) in PADROES_LOUDNESS.items():
            ttk.Button(pf, text=f"{nome} ({lufs:.0f} LUFS)",
                       command=lambda n=nome: self.aplicar_padrao_audio(n)).pack(anchor=tk.W, pady=2)

        cf = ttk.LabelFrame(frame, text="Controles", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        self.audio_normalizar = tk.BooleanVar(value=True)
        self.audio_ducking = tk.BooleanVar(value=True)
        self.audio_eq = tk.BooleanVar(value=False)
        ttk.Checkbutton(cf, text="Normalizacao (loudnorm 2 passadas)", variable=self.audio_normalizar).grid(row=0, column=0, sticky=tk.W)
        ttk.Checkbutton(cf, text="Ducking automatico da trilha", variable=self.audio_ducking).grid(row=1, column=0, sticky=tk.W)
        ttk.Checkbutton(cf, text="EQ de 3 bandas", variable=self.audio_eq).grid(row=2, column=0, sticky=tk.W)
        self.eq_low, self.eq_mid, self.eq_high = tk.DoubleVar(value=0), tk.DoubleVar(value=0), tk.DoubleVar(value=0)
        for c, (txt, var) in enumerate((("Graves", self.eq_low), ("Medios", self.eq_mid), ("Agudos", self.eq_high))):
            ttk.Label(cf, text=f"{txt} (dB)").grid(row=3, column=c, padx=6)
            ttk.Scale(cf, from_=-12, to=12, variable=var, orient=tk.HORIZONTAL, length=140).grid(row=4, column=c, padx=6)

        tf = ttk.LabelFrame(frame, text="Trilha sonora", padding=12)
        tf.pack(fill=tk.X, padx=20, pady=6)
        self.trilha_label = ttk.Label(tf, text="Nenhuma trilha")
        self.trilha_label.pack(anchor=tk.W)
        ttk.Button(tf, text="Escolher trilha...", command=self.escolher_trilha).pack(side=tk.LEFT, padx=4)
        ttk.Button(tf, text="Remover trilha", command=self.remover_trilha).pack(side=tk.LEFT, padx=4)
        ttk.Label(tf, text="  Volume:").pack(side=tk.LEFT)
        self.trilha_volume = tk.DoubleVar(value=0.3)
        ttk.Scale(tf, from_=0.0, to=1.0, variable=self.trilha_volume, orient=tk.HORIZONTAL, length=150).pack(side=tk.LEFT)
        self.trilha_loop = tk.BooleanVar(value=True)
        ttk.Checkbutton(tf, text="Repetir", variable=self.trilha_loop).pack(side=tk.LEFT, padx=6)

    # ============================================================
    # ABA IA - ASSISTENTE CLAUDE
    # ============================================================

    def criar_aba_ia(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  IA  ")
        ttk.Label(frame, text="Assistente IA", font=("Helvetica", 16, "bold")).pack(pady=10)

        # v7.9: escolha do motor. Claude continua o padrao (nada muda para quem ja usa);
        # Ollama roda no proprio computador, gratis e sem internet.
        motor_frame = ttk.LabelFrame(frame, text="Motor de IA", padding=10)
        motor_frame.pack(fill=tk.X, padx=20, pady=5)
        self.motor_var = tk.StringVar(value=self.claude.motor())
        ttk.Radiobutton(motor_frame, text="Claude (API, pago por uso)", variable=self.motor_var,
                        value="claude", command=self._mudar_motor).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(motor_frame, text="Ollama (local, gratuito)", variable=self.motor_var,
                        value="ollama", command=self._mudar_motor).pack(side=tk.LEFT, padx=5)
        ttk.Label(motor_frame, text="Modelo local:").pack(side=tk.LEFT, padx=(15, 5))
        self.ollama_modelo_var = tk.StringVar(value=self.config.get("ollama_model", motor_local.MODELO_PADRAO))
        self.ollama_combo = ttk.Combobox(motor_frame, textvariable=self.ollama_modelo_var, width=22,
                                         values=[m for _, m, _ in motor_local.SUGESTOES])
        self.ollama_combo.pack(side=tk.LEFT)
        self.ollama_combo.bind("<<ComboboxSelected>>", self._salvar_modelo_ollama)
        self.ollama_combo.bind("<FocusOut>", self._salvar_modelo_ollama, add="+")
        self.ollama_combo.bind("<Return>", self._salvar_modelo_ollama)
        ttk.Button(motor_frame, text="Atualizar lista", command=self.atualizar_modelos_ollama).pack(side=tk.LEFT, padx=5)
        ttk.Button(motor_frame, text="Testar motor", command=self.testar_motor_ia).pack(side=tk.LEFT, padx=5)
        self.motor_status = ttk.Label(frame, text="", justify=tk.LEFT)
        self.motor_status.pack(anchor=tk.W, padx=24)
        self.ao_mudar_motor: List[Callable] = []   # outras abas (Diretor IA) se atualizam
        self._atualizar_status_motor()

        key_frame = ttk.LabelFrame(frame, text="Chave da API (console.anthropic.com)", padding=10)
        key_frame.pack(fill=tk.X, padx=20, pady=5)
        # v7.7: a chave salva NAO e carregada no campo (ficaria na memoria do widget).
        # v7.8.1: em vez do campo vazio (parecia que "a chave sumiu"), o campo mostra
        # uma MASCARA (nao e a chave) e o rotulo verde diz que esta salva e o final dela.
        self.api_key_entry = ttk.Entry(key_frame, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=5)
        self.api_key_entry.bind("<FocusIn>", self._chave_focus_in)
        self.api_key_entry.bind("<Return>", lambda e: self.salvar_chave_ia())
        # v7.8.1: colar a chave e trocar de aba SEM clicar em Salvar perdia a chave
        # (o relato "quando mudo a aba ela some"). Agora sair do campo ou trocar de
        # aba salva automaticamente uma chave sk-ant- recem-colada.
        self.api_key_entry.bind("<FocusOut>", self._chave_auto_salvar, add="+")
        nb.bind("<<NotebookTabChanged>>", self._chave_auto_salvar, add="+")
        ttk.Button(key_frame, text="Salvar chave", command=self.salvar_chave_ia).pack(side=tk.LEFT, padx=5)
        ttk.Button(key_frame, text="Testar chave", command=self.testar_chave_ia).pack(side=tk.LEFT, padx=5)
        ttk.Label(key_frame, text="Modelo:").pack(side=tk.LEFT, padx=(15, 5))
        # Campo do modelo do CLAUDE (o modelo local fica no quadro "Motor de IA").
        self.modelo_var = tk.StringVar(value=self.config.get("claude_model", self.claude.MODELO_CLAUDE_PADRAO))
        ttk.Entry(key_frame, textvariable=self.modelo_var, width=26).pack(side=tk.LEFT)
        self.chave_status = ttk.Label(frame, text="")
        self.chave_status.pack(anchor=tk.W, padx=24)
        self._atualizar_status_chave()

        tema_frame = ttk.LabelFrame(frame, text="Tema / Texto", padding=10)
        tema_frame.pack(fill=tk.X, padx=20, pady=5)
        self.ia_prompt = scrolledtext.ScrolledText(tema_frame, height=4)
        self.ia_prompt.pack(fill=tk.X)

        btns = ttk.Frame(frame)
        btns.pack(pady=8)
        for txt, tipo in (("Roteiro", "roteiro"), ("Titulos", "titulos"), ("Descricao YouTube", "descricao"),
                          ("Capitulos", "capitulos"), ("Hashtags", "hashtags"), ("Melhorar texto", "melhorar")):
            ttk.Button(btns, text=txt, command=lambda t=tipo: self.gerar_ia(t)).pack(side=tk.LEFT, padx=4)

        self.ia_result = scrolledtext.ScrolledText(frame, height=14, font=("Consolas", 10))
        self.ia_result.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        ttk.Button(frame, text="Copiar resultado", command=self.copiar_ia).pack(pady=5)

    MASCARA_CHAVE = "*" * 24   # exibido no campo quando ha chave salva (nao e a chave)

    def _texto_status_chave(self) -> str:
        onde = self.config.onde_esta_chave("claude")
        if not onde:
            return "Nenhuma chave salva. Cole a chave (sk-ant-...) e clique em Salvar (ou Enter)."
        final = self.config.get_api_key("claude")[-4:]
        return f"\u2714 Chave salva (termina em ...{final}) - {onde}. Para trocar, clique no campo e cole a nova."

    def _atualizar_status_chave(self):
        salva = bool(self.config.onde_esta_chave("claude"))
        self.chave_status.config(text=self._texto_status_chave(), foreground="green" if salva else "orange")
        self.api_key_entry.delete(0, tk.END)
        if salva:
            self.api_key_entry.insert(0, self.MASCARA_CHAVE)

    def _chave_focus_in(self, _evento=None):
        if self.api_key_entry.get() == self.MASCARA_CHAVE:
            self.api_key_entry.delete(0, tk.END)

    def _chave_auto_salvar(self, _evento=None):
        """Salva sem perguntar uma chave sk-ant- colada e nao salva; restaura a mascara."""
        digitada = self.api_key_entry.get().strip()
        if digitada.startswith("sk-ant-") and digitada != self.config.get_api_key("claude"):
            self.claude.salvar_chave(digitada)
            self._atualizar_status_chave()
            return
        if not digitada and self.claude.tem_chave():
            self._atualizar_status_chave()

    # ---- v7.9: motor de IA (Claude | Ollama)
    def _texto_status_motor(self) -> str:
        if self.claude.motor() == "claude":
            return "Motor: Claude (API). Precisa de chave com creditos (abaixo)."
        ram = motor_local.ram_total_gb()
        sugerido, desc = motor_local.sugerir_modelo(ram)
        ram_txt = f"{ram:.0f} GB de RAM: sugerido {sugerido} ({desc}). " if ram else ""
        return (f"Motor: Ollama (local) - modelo {self.claude.modelo()}. {ram_txt}"
                "Clique em 'Testar motor'.\n" + motor_local.INSTRUCOES_INSTALACAO)

    def _atualizar_status_motor(self):
        self.motor_status.config(text=self._texto_status_motor(),
                                 foreground="green" if self.claude.motor() == "claude" else "blue")

    def _mudar_motor(self):
        self.claude.definir_motor(self.motor_var.get())
        self._salvar_modelo_ollama()
        self._atualizar_status_motor()
        for cb in list(getattr(self, "ao_mudar_motor", [])):
            try:
                cb()
            except Exception as e:  # noqa: BLE001 - uma aba com erro nao trava a troca
                self.log(f"Aviso ao atualizar aba apos trocar motor: {e}")

    def _salvar_modelo_ollama(self, _evento=None):
        modelo = self.ollama_modelo_var.get().strip()
        if modelo and modelo != self.config.get("ollama_model", motor_local.MODELO_PADRAO):
            self.config.set("ollama_model", modelo)
            self._atualizar_status_motor()

    def atualizar_modelos_ollama(self):
        def tarefa():
            try:
                modelos = self.claude.local().modelos()
            except RuntimeError as e:
                self.ui.chamar(lambda: self.motor_status.config(text=str(e), foreground="red"))
                return

            def fim():
                sugestoes = [m for _, m, _ in motor_local.SUGESTOES if m not in modelos]
                self.ollama_combo.config(values=modelos + sugestoes)
                txt = (f"Modelos baixados: {', '.join(modelos)}" if modelos
                       else f"Nenhum modelo baixado. Rode: ollama pull {self.ollama_modelo_var.get()}")
                self.motor_status.config(text=txt, foreground="green" if modelos else "orange")
            self.ui.chamar(fim)
        self.ui.em_segundo_plano(tarefa, nome="ollama_modelos")

    def testar_motor_ia(self):
        self._salvar_modelo_ollama()
        self.motor_status.config(text=f"Testando {self.claude.nome_motor()}...", foreground="gray")

        def tarefa():
            ok, msg = self.claude.testar_motor()

            def fim():
                self.motor_status.config(text=("\u2714 " if ok else "\u2716 ") + msg,
                                         foreground="green" if ok else "red")
                (messagebox.showinfo if ok else messagebox.showerror)("Motor de IA", msg)
            self.ui.chamar(fim)
        self.ui.em_segundo_plano(tarefa, nome="testar_motor")

    def testar_chave_ia(self):
        digitada = self.api_key_entry.get().strip()
        chave = "" if digitada in ("", self.MASCARA_CHAVE) else digitada
        self.chave_status.config(text="Testando a chave com a API...", foreground="gray")

        def tarefa():
            ok, msg = self.claude.testar_chave(chave)

            def fim():
                self.chave_status.config(text=("\u2714 " if ok else "\u2716 ") + msg,
                                         foreground="green" if ok else "red")
                (messagebox.showinfo if ok else messagebox.showerror)("Chave da API", msg)
            self.ui.chamar(fim)
        self.ui.em_segundo_plano(tarefa, nome="testar_chave")

    def salvar_chave_ia(self):
        chave = self.api_key_entry.get().strip()
        modelo = self.modelo_var.get().strip()
        if modelo:
            self.config.set("claude_model", modelo)
        if not chave or chave == self.MASCARA_CHAVE:
            if self.claude.tem_chave():
                self._atualizar_status_chave()
                messagebox.showinfo("IA", "Modelo salvo. Chave atual mantida.")
            else:
                messagebox.showwarning("Aviso", "Cole a chave da API primeiro.")
            return
        if not chave.startswith("sk-ant-"):
            if not messagebox.askyesno("Chave da API", "A chave nao comeca com 'sk-ant-'. Salvar mesmo assim?"):
                return
        self.claude.salvar_chave(chave)
        self._atualizar_status_chave()
        if self.config.get_api_key("claude") != chave:   # confere que foi gravada de verdade
            messagebox.showerror("IA", "Nao foi possivel gravar a chave. Veja Ferramentas > Abrir pasta de logs.")
            return
        messagebox.showinfo("IA", f"Chave salva (termina em ...{chave[-4:]}) - "
                                  f"{self.config.onde_esta_chave('claude')}.\nUse 'Testar chave' para conferir.")

    def gerar_ia(self, tipo: str):
        tema = self.ia_prompt.get("1.0", tk.END).strip()
        if not tema:
            messagebox.showwarning("Aviso", "Escreva o tema ou texto primeiro.")
            return
        if not self.claude.pronto():
            messagebox.showwarning("Aviso", "Salve a chave da API do Claude ou escolha o motor "
                                            "Ollama (local, gratuito) no quadro 'Motor de IA'.")
            return
        if self.modelo_var.get().strip():
            self.config.set("claude_model", self.modelo_var.get().strip())
        self._salvar_modelo_ollama()
        self.ia_result.delete(1.0, tk.END)
        espera = " Modelo local: a 1a resposta pode levar 1-2 min." if self.claude.motor() == "ollama" else ""
        self.ia_result.insert(tk.END, f"Gerando com {self.claude.nome_motor()} ({self.claude.modelo()})... "
                                      f"aguarde.{espera}\n")
        funcoes = {"roteiro": self.claude.roteiro, "titulos": self.claude.titulos,
                   "descricao": self.claude.descricao_youtube, "capitulos": self.claude.capitulos,
                   "hashtags": self.claude.hashtags, "melhorar": self.claude.melhorar_texto}

        def mostrar(texto):
            self.ia_result.delete(1.0, tk.END)
            self.ia_result.insert(tk.END, texto)

        def tarefa():
            texto = funcoes.get(tipo, self.claude.melhorar_texto)(tema)
            self.ui.chamar(mostrar, texto)
            self.log("IA: conteudo gerado com sucesso.")

        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: mostrar(f"Erro:\n{e}"), nome="ia")

    def copiar_ia(self):
        texto = self.ia_result.get(1.0, tk.END).strip()
        if texto:
            self.root.clipboard_clear()
            self.root.clipboard_append(texto)
            messagebox.showinfo("IA", "Resultado copiado!")

    def criar_aba_render(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Render  ")
        ttk.Label(frame, text="Renderizacao Profissional", font=("Helvetica", 16, "bold")).pack(pady=12)
        pf = ttk.LabelFrame(frame, text="Preset de Render", padding=12)
        pf.pack(fill=tk.X, padx=20, pady=6)
        self.preset_var = tk.StringVar(value="FAST")
        for texto, valor in (("DRAFT (Rascunho)", "DRAFT"), ("FAST (Rapido)", "FAST"),
                             ("BALANCED (Equilibrado)", "BALANCED"), ("HIGH_QUALITY (Alta Qualidade)", "HIGH_QUALITY"),
                             ("MASTER (CRF 15, veryslow)", "MASTER")):
            ttk.Radiobutton(pf, text=texto, variable=self.preset_var, value=valor).pack(anchor=tk.W)
        bf = ttk.Frame(frame)
        bf.pack(pady=16)
        ttk.Button(bf, text="RENDERIZAR", command=self.renderizar).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="Exportar EDL", command=self.exportar_edl).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="Adicionar a Fila", command=self.adicionar_fila).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="Processar Fila", command=self.processar_fila).pack(side=tk.LEFT, padx=8)
        self.fila_label = ttk.Label(frame, text="Fila vazia")
        self.fila_label.pack()
        self.log_text = scrolledtext.ScrolledText(frame, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)
        for msg in self._log_pendente:   # mensagens anteriores a criacao da aba
            self.log_text.insert(tk.END, msg + "\n")
        self._log_pendente.clear()

    def criar_aba_qc(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  QC  ")
        ttk.Label(frame, text="Controle de Qualidade Automatico", font=("Helvetica", 16, "bold")).pack(pady=12)
        bf = ttk.Frame(frame)
        bf.pack(pady=10)
        ttk.Button(bf, text="Analisar Video...", command=self.analisar_qc).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Exportar Relatorio (PDF/TXT)...", command=self.exportar_relatorio_qc).pack(side=tk.LEFT, padx=6)
        ttk.Label(frame, text="O alvo de loudness segue o 'Padrao Audio' da aba Projeto.").pack()
        self.qc_result = scrolledtext.ScrolledText(frame, height=20, font=("Consolas", 10))
        self.qc_result.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

    # ============================================================
    # LOG E UTILITARIOS DE UI
    # ============================================================

    def log(self, msg):
        """Thread-safe: de qualquer thread, a escrita no widget acontece na UI."""
        msg = str(msg)
        self.logger.info(msg)
        self.ui.chamar(self._log_na_ui, msg)

    def _log_na_ui(self, msg: str):
        if self.log_text is None:
            self._log_pendente.append(msg)
            return
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)

    def _info(self, titulo, texto):
        self.ui.chamar(messagebox.showinfo, titulo, texto)

    def _erro(self, titulo, texto):
        self.ui.chamar(messagebox.showerror, titulo, texto)

    def _clip_selecionado(self) -> Optional[int]:
        sel = self.tree_clips.selection()
        if not sel:
            if len(self.clips) == 1:
                return 0
            messagebox.showwarning("Timeline", "Selecione um clipe na lista da Timeline.")
            return None
        return int(sel[0])

    # ============================================================
    # MIDIA / TIMELINE
    # ============================================================

    def _adicionar_clip(self, arquivo: Path, atualizar: bool = True) -> bool:
        """Adiciona um video a timeline. Em caso de falha, o motivo fica em
        self.ultimo_erro_importacao (v7.8.1: antes ia so para o log da aba Render
        e a importacao parecia "nao fazer nada")."""
        self.ultimo_erro_importacao = ""
        try:
            info = info_midia(arquivo)
        except FFmpegErro as e:
            self.ultimo_erro_importacao = f"ffprobe nao conseguiu ler o arquivo: {e}"
            self.log(f"[ERRO] {arquivo.name}: {e}")
            return False
        if not info["tem_video"]:
            self.ultimo_erro_importacao = "o arquivo nao tem trilha de video"
            self.log(f"[AVISO] {arquivo.name} ignorado: sem video.")
            return False
        self.clips.append(ClipTimeline(arquivo=arquivo, inicio=0.0, fim=info["duracao"],
                                       duracao=info["duracao"], nome=arquivo.name,
                                       duracao_fonte=info["duracao"]))
        if atualizar:
            self._atualizar_listas()
        return True

    def _atualizar_listas(self):
        self.lista_midia.delete(0, tk.END)
        for c in self.clips:
            self.lista_midia.insert(tk.END, f"{c.nome}  ({c.duracao_fonte:.1f}s)")
        for iid in self.tree_clips.get_children():
            self.tree_clips.delete(iid)
        for i, c in enumerate(self.clips):
            vel = "rampa" if c.rampa else f"{c.speed:.2f}x"
            self.tree_clips.insert("", "end", iid=str(i), values=(
                i + 1, c.nome, f"{c.inicio:.2f}", f"{c.fim:.2f}", f"{c.duracao_saida():.2f}s", vel))
        self._desenhar_timeline()

    def _desenhar_timeline(self):
        cv = self.timeline_canvas
        cv.delete("all")
        total = sum(c.duracao_saida() for c in self.clips) or 1.0
        largura = max(200, cv.winfo_width() - 20)
        x = 10
        cores = ("#3a7bd5", "#00a86b", "#d2691e", "#8e44ad", "#c0392b", "#16a085")
        for i, c in enumerate(self.clips):
            w = max(4, c.duracao_saida() / total * largura)
            cv.create_rectangle(x, 30, x + w, 90, fill=cores[i % len(cores)], outline="#ffffff")
            if w > 50:
                cv.create_text(x + 5, 60, text=f"{i + 1}. {c.nome[:20]}", anchor=tk.W, fill="white")
            x += w
        cv.create_text(10, 12, text=f"Duracao total: {total:.2f}s", anchor=tk.W, fill="#cccccc")

    def importar_midia(self, arquivos: Optional[List[str]] = None):
        files = arquivos if arquivos is not None else filedialog.askopenfilenames(filetypes=tipos_video())
        self._importar(list(files))

    def _importar(self, arquivos: List):
        falhas = []
        for f in arquivos:
            if not self._adicionar_clip(Path(f), atualizar=False):
                falhas.append(f"{Path(f).name}: {self.ultimo_erro_importacao}")
        self._atualizar_listas()
        if arquivos:
            self.log(f"Importacao: {len(arquivos) - len(falhas)} de {len(arquivos)} arquivo(s) adicionados.")
        if falhas:
            messagebox.showerror("Importar midia",
                                 f"{len(falhas)} arquivo(s) nao foram importados:\n\n" + "\n".join(falhas[:10]) +
                                 "\n\nDetalhes: Ferramentas > Abrir pasta de logs.")

    def carregar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            arquivos = [f for f in sorted(Path(pasta).iterdir()) if f.suffix.lower() in EXTS_VIDEO]
            if not arquivos:
                messagebox.showwarning("Importar pasta", f"Nenhum video ({', '.join(EXTS_VIDEO)}) em:\n{pasta}")
                return
            self._importar(arquivos)

    def criar_proxies(self):
        if not self.clips:
            messagebox.showwarning("Aviso", "Importe videos primeiro!")
            return
        arquivos = self.videos

        def tarefa():
            self.log("Criando proxies (usados no Preview; o render usa os originais)...")
            for video in arquivos:
                proxy = self.automation.criar_proxy(video)
                self.log(f"Proxy criado: {proxy.name}")
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Proxies", str(e)), nome="proxies")

    def limpar_midia(self):
        self.clips = []
        self._atualizar_listas()

    def preview(self):
        i = self._clip_selecionado()
        if i is None:
            return
        c = self.clips[i]
        alvo = self.automation.proxies.get(str(c.arquivo), c.arquivo)
        try:
            player = abrir_no_player(alvo, c.inicio)
            self.log(f"Preview: {c.nome} a partir de {c.inicio:.2f}s ({player})")
        except OSError as e:
            messagebox.showerror("Preview", f"Nao foi possivel abrir o player: {e}")

    def definir_in_out(self):
        i = self._clip_selecionado()
        if i is None:
            return
        c = self.clips[i]
        ini = simpledialog.askfloat("In", f"Inicio (s) - 0 a {c.duracao_fonte:.2f}:", initialvalue=c.inicio,
                                    minvalue=0.0, maxvalue=c.duracao_fonte, parent=self.root)
        if ini is None:
            return
        fim = simpledialog.askfloat("Out", f"Fim (s) - {ini:.2f} a {c.duracao_fonte:.2f}:", initialvalue=c.fim,
                                    minvalue=ini + 0.04, maxvalue=c.duracao_fonte, parent=self.root)
        if fim is None:
            return
        c.inicio, c.fim = float(ini), float(fim)
        self.editor._sync_dur(c)
        self._atualizar_listas()

    def definir_velocidade(self):
        i = self._clip_selecionado()
        if i is None:
            return
        v = simpledialog.askfloat("Velocidade", "Velocidade (0.25 = 4x lento, 2.0 = 2x rapido):",
                                  initialvalue=self.clips[i].speed, minvalue=0.1, maxvalue=8.0, parent=self.root)
        if v:
            self.clips[i].speed, self.clips[i].rampa = float(v), []
            self._atualizar_listas()

    def speed_ramp(self):
        """Velocidade por trechos. Ex.: '0:1, 2:0.5, 4:2' (tempo relativo ao In)."""
        i = self._clip_selecionado()
        if i is None:
            return
        atual = ", ".join(f"{t:g}:{v:g}" for t, v in self.clips[i].rampa) or "0:1, 2:0.5, 4:1"
        txt = simpledialog.askstring("Speed Ramp", "Pontos tempo:velocidade (s relativos ao In)\n"
                                     "Ex.: 0:1, 2:0.5, 4:2   (vazio = remover rampa)",
                                     initialvalue=atual, parent=self.root)
        if txt is None:
            return
        try:
            pontos = [] if not txt.strip() else [
                (float(t), float(v)) for t, v in (p.split(":") for p in txt.replace(";", ",").split(","))]
            if pontos:
                SeniorEditorEngine._normalizar_rampa(pontos)
        except ValueError as e:
            messagebox.showerror("Speed Ramp", f"Formato invalido: {e}")
            return
        self.clips[i].rampa, self.clips[i].speed = pontos, 1.0
        self._atualizar_listas()
        self.log(f"Speed ramp em '{self.clips[i].nome}': {pontos or 'removida'}")

    def mover_clip(self, delta: int):
        i = self._clip_selecionado()
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(self.clips):
            self.clips[i], self.clips[j] = self.clips[j], self.clips[i]
            self._atualizar_listas()
            self.tree_clips.selection_set(str(j))

    def ripple_edit(self):
        i = self._clip_selecionado()
        if i is None:
            return
        tl = self._montar_timeline()
        nome = self.clips[i].nome
        self.editor.ripple_delete(tl, i)
        self.clips = tl.clips
        self._atualizar_listas()
        self.log(f"Ripple delete: '{nome}' removido; clipes seguintes avancaram.")

    def multicam(self):
        if len(self.clips) < 2:
            messagebox.showwarning("Multicam", "Importe 2 ou mais angulos (o 1o e a referencia).")
            return
        arquivos = self.videos

        def tarefa():
            novos = self.editor.criar_multicam(arquivos)

            def aplicar():
                for c, n in zip(self.clips, novos):
                    c.inicio, c.fim = n.inicio, n.fim
                    self.editor._sync_dur(c)
                self._atualizar_listas()
                messagebox.showinfo("Multicam", "Angulos sincronizados pelo audio (In/Out ajustados).")
            self.ui.chamar(aplicar)
        self.log("Multicam: sincronizando angulos pelo audio...")
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Multicam", str(e)), nome="multicam")

    # ============================================================
    # COR / AUDIO
    # ============================================================

    def aplicar_lut(self, lut):
        """Define o look do projeto (antes so registrava no log)."""
        self.look_var.set("" if lut == "Nenhum" else lut)
        self.look_label.config(text=f"Look atual: {lut if lut != 'Nenhum' else 'nenhum'}")
        self.log(f"Look do projeto: {lut}")

    def carregar_cube(self):
        arq = filedialog.askopenfilename(filetypes=[("LUT 3D", "*.cube")])
        if arq:
            p = Path(arq)
            self.color.luts.adicionar_lut_personalizada(p.stem, p)
            self.aplicar_lut(p.stem)

    def zerar_ajustes_cor(self):
        self.cor_exposicao.set(0.0)
        self.cor_contraste.set(1.0)
        self.cor_saturacao.set(1.0)
        for c in self.clips:
            c.ajustes_cor = {}
        self.log("Ajustes de cor zerados.")

    def auto_exposicao(self):
        if not self.clips:
            messagebox.showwarning("Cor", "Importe videos primeiro!")
            return
        clips = list(self.clips)

        def tarefa():
            for c in clips:
                c.ajustes_cor = {**c.ajustes_cor, **self.color.calcular_exposicao(c.arquivo)}
            self._info("Cor", "Exposicao calculada por clipe (aplicada no render).")
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Cor", str(e)), nome="exposicao")

    def match_cameras(self):
        if len(self.clips) < 2:
            messagebox.showwarning("Cor", "Precisa de 2 ou mais clipes (o 1o e a referencia).")
            return
        ref, alvos = self.clips[0], self.clips[1:]

        def tarefa():
            for c in alvos:
                c.ajustes_cor = {**c.ajustes_cor, **self.color.calcular_match(ref.arquivo, c.arquivo)}
                self.log(f"Match {c.nome}: {c.ajustes_cor}")
            self._info("Cor", "Match de cameras calculado (aplicado no render).")
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Cor", str(e)), nome="match")

    def preview_look(self):
        if not self.clips:
            messagebox.showwarning("Cor", "Importe videos primeiro!")
            return
        c = self.clips[0]
        tl = self._montar_timeline()
        destino = self.renderer.temp_dir / "preview_look.png"
        filtro = filtro_ajustes(tl.ajustes_cor)
        look = self.color.luts.obter_filtro_ffmpeg(tl.look, tl.look_intensidade) if tl.look else "null"

        def tarefa():
            executar(["ffmpeg", "-y", "-ss", f"{c.inicio + (c.fim - c.inicio) / 2:.2f}", "-i", str(c.arquivo),
                      "-filter_complex", f"[0:v]{filtro}[a];[a]{look}[b]", "-map", "[b]", "-frames:v", "1",
                      str(destino)], self.log)
            self.ui.chamar(abrir_no_player, destino)
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Cor", str(e)), nome="preview_look")

    def aplicar_padrao_audio(self, padrao):
        """Define o padrao de loudness (antes so registrava no log)."""
        self.audio_standard.set(padrao)
        alvo, tp = padrao_loudness(padrao)
        self.log(f"Padrao de audio: {padrao} ({alvo} LUFS, true peak {tp} dBTP)")

    def escolher_trilha(self):
        arq = filedialog.askopenfilename(filetypes=tipos_midia())
        if arq:
            self.trilha = MusicTrack(Path(arq))
            self.trilha_label.config(text=f"Trilha: {Path(arq).name}")

    def remover_trilha(self):
        self.trilha = None
        self.trilha_label.config(text="Nenhuma trilha")

    # ============================================================
    # PROJETO
    # ============================================================

    def _montar_timeline(self) -> ProjectTimeline:
        try:
            w, h = (int(x) for x in self.resolucao_var.get().lower().split("x"))
        except ValueError:
            raise ValueError("Resolucao invalida (use LARGURAxALTURA, ex.: 1920x1080)")
        try:
            fps = int(float(self.fps_var.get()))
        except ValueError:
            raise ValueError("FPS invalido")
        aj = {"brightness": round(self.cor_exposicao.get(), 4), "contrast": round(self.cor_contraste.get(), 4),
              "saturation": round(self.cor_saturacao.get(), 4)}
        musica = None
        if self.trilha:
            musica = MusicTrack(self.trilha.arquivo, volume=round(self.trilha_volume.get(), 3),
                                ducking=self.audio_ducking.get(), loop=self.trilha_loop.get())
        eq = {"low": self.eq_low.get(), "mid": self.eq_mid.get(), "high": self.eq_high.get()} \
            if self.audio_eq.get() else {}
        return ProjectTimeline(
            clips=self.clips, projeto_nome=self.projeto_nome.get(), fps=fps, resolucao=(w, h),
            look=self.look_var.get(), look_intensidade=round(self.look_intensidade.get(), 3),
            ajustes_cor=aj, padrao_audio=self.audio_standard.get(),
            normalizar_audio=self.audio_normalizar.get(), eq=eq, music=musica,
            transicao=self._transicao_por_nome.get(self.transicao_var.get(), ""),
            duracao_transicao=float(self.transicao_dur_var.get() or 0.5),
            enquadramento=self.enquadramento_var.get() or "ajustar")

    def _aplicar_timeline_na_ui(self, tl: ProjectTimeline):
        self.projeto_nome.delete(0, tk.END)
        self.projeto_nome.insert(0, tl.projeto_nome)
        self.resolucao_var.set(f"{tl.resolucao[0]}x{tl.resolucao[1]}")
        self.fps_var.set(str(tl.fps))
        self.audio_standard.set(tl.padrao_audio)
        self.look_var.set(tl.look)
        self.look_label.config(text=f"Look atual: {tl.look or 'nenhum'}")
        self.look_intensidade.set(tl.look_intensidade)
        self.cor_exposicao.set(tl.ajustes_cor.get("brightness", 0.0))
        self.cor_contraste.set(tl.ajustes_cor.get("contrast", 1.0))
        self.cor_saturacao.set(tl.ajustes_cor.get("saturation", 1.0))
        self.audio_normalizar.set(tl.normalizar_audio)
        self.audio_eq.set(bool(tl.eq))
        self.eq_low.set(tl.eq.get("low", 0))
        self.eq_mid.set(tl.eq.get("mid", 0))
        self.eq_high.set(tl.eq.get("high", 0))
        if tl.music:
            self.trilha = tl.music
            self.trilha_volume.set(tl.music.volume)
            self.trilha_loop.set(tl.music.loop)
            self.audio_ducking.set(tl.music.ducking)
            self.trilha_label.config(text=f"Trilha: {Path(tl.music.arquivo).name}")
        else:
            self.remover_trilha()
        nomes = {v: k for k, v in self._transicao_por_nome.items()}
        self.transicao_var.set(nomes.get(tl.transicao, self.TRANSICAO_NENHUMA))
        self.transicao_dur_var.set(tl.duracao_transicao)
        self.enquadramento_var.set(getattr(tl, "enquadramento", "ajustar"))
        self.clips = tl.clips
        self._atualizar_listas()

    def novo_projeto(self):
        self.timeline = None
        self.arquivo_projeto = None
        self.limpar_midia()
        self.root.title(f"Video Builder Pro v{VERSAO} - Professional Suite")

    def abrir_projeto(self, caminho: Optional[Path] = None):
        caminho = caminho or filedialog.askopenfilename(filetypes=[("Projeto Video Builder", "*.vbp.json *.json")])
        if not caminho:
            return
        try:
            tl = timeline_de_dict(json.loads(Path(caminho).read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError) as e:
            messagebox.showerror("Abrir Projeto", f"Arquivo invalido:\n{e}")
            return
        faltando = [c.nome or str(c.arquivo) for c in tl.clips if not Path(c.arquivo).exists()]
        self._aplicar_timeline_na_ui(tl)
        self.arquivo_projeto = Path(caminho)
        self.root.title(f"Video Builder Pro v{VERSAO} - {Path(caminho).name}")
        self.log(f"Projeto aberto: {caminho}")
        if faltando:
            messagebox.showwarning("Abrir Projeto", "Midias nao encontradas:\n" + "\n".join(faltando))

    def salvar_projeto(self, como: bool = False, caminho: Optional[Path] = None):
        caminho = caminho or (None if como else self.arquivo_projeto) or filedialog.asksaveasfilename(
            defaultextension=".vbp.json", filetypes=[("Projeto Video Builder", "*.vbp.json")])
        if not caminho:
            return
        try:
            dados = timeline_para_dict(self._montar_timeline())
            Path(caminho).write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError) as e:
            messagebox.showerror("Salvar Projeto", str(e))
            return
        self.arquivo_projeto = Path(caminho)
        self.root.title(f"Video Builder Pro v{VERSAO} - {Path(caminho).name}")
        self.log(f"Projeto salvo: {caminho}")

    # ============================================================
    # RENDER / FILA / EDL
    # ============================================================

    def exportar_edl(self):
        if not self.clips:
            messagebox.showwarning("Aviso", "Importe midia primeiro!")
            return
        arquivo = filedialog.asksaveasfilename(defaultextension=".xml",
                                               filetypes=[("FCP7 XML (Premiere / DaVinci)", "*.xml")])
        if arquivo:
            try:
                self.renderer.exportar_edl(self._montar_timeline(), Path(arquivo), "premiere")
                messagebox.showinfo("Sucesso", f"EDL exportado:\n{arquivo}")
            except (OSError, ValueError) as e:
                messagebox.showerror("EDL", str(e))

    def _preset(self) -> RenderPreset:
        return RenderPreset[self.preset_var.get()] if self.preset_var.get() in RenderPreset.__members__ \
            else RenderPreset.FAST

    def renderizar(self, saida: Optional[str] = None):
        if not self.clips:
            messagebox.showwarning("Aviso", "Importe videos primeiro!")
            return
        try:
            self.timeline = self._montar_timeline()
        except ValueError as e:
            messagebox.showerror("Render", str(e))
            return
        preset = self._preset()
        saida = saida or filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
        if not saida:
            return
        tl = self.timeline

        def tarefa():
            self.renderer.renderizar(tl, Path(saida), preset)
            self.qc_report = self.renderer.ultimo_qc

            def fim():
                if self.qc_report:
                    self._mostrar_qc(self.qc_report)
                messagebox.showinfo("Sucesso", f"Renderizacao concluida!\n{saida}")
            self.ui.chamar(fim)
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Erro", f"Render falhou:\n{e}"),
                                 nome="render")

    def adicionar_fila(self, saida: Optional[str] = None):
        if not self.clips:
            messagebox.showwarning("Aviso", "Importe videos primeiro!")
            return
        saida = saida or filedialog.asksaveasfilename(title="Arquivo de saida deste projeto",
                                                      defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
        if not saida:
            return
        try:
            tl = self._montar_timeline()
        except ValueError as e:
            messagebox.showerror("Fila", str(e))
            return
        # copia profunda (via dict): edicoes posteriores nao alteram o item da fila
        projeto = {"nome": tl.projeto_nome, "saida": saida, "preset": self.preset_var.get(),
                   "timeline": timeline_para_dict(tl)}
        self.automation.adicionar_a_fila(projeto)
        self.fila_label.config(text=f"Fila: {len(self.automation.fila_render)} projeto(s)")

    def processar_fila(self):
        if not self.automation.fila_render:
            messagebox.showinfo("Fila", "A fila esta vazia.")
            return

        def tarefa():
            res = self.automation.processar_fila(self.renderer.renderizar)
            ok = sum(1 for _, s, _ in res if s)

            def fim():
                self.fila_label.config(text="Fila vazia")
                texto = "\n".join(f"{'OK ' if s else 'ERRO'} {n}: {d}" for n, s, d in res)
                messagebox.showinfo("Fila", f"{ok}/{len(res)} renderizado(s).\n\n{texto}")
            self.ui.chamar(fim)
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Fila", str(e)), nome="fila")

    # ============================================================
    # QC
    # ============================================================

    def _mostrar_qc(self, report: QCReport):
        self.qc_result.delete(1.0, tk.END)
        self.qc_result.insert(tk.END, report.texto())

    def analisar_qc(self, arquivo: Optional[str] = None):
        arquivo = arquivo or filedialog.askopenfilename(filetypes=tipos_video())
        if not arquivo:
            return
        self.qc_result.delete(1.0, tk.END)
        self.qc_result.insert(tk.END, "Analisando...\n\n")
        padrao = self.audio_standard.get()

        def tarefa():
            report = self.qc.analisar_video(Path(arquivo), padrao)
            self.qc_report = report
            self.ui.chamar(self._mostrar_qc, report)

        def falhou(e):
            self.qc_result.delete(1.0, tk.END)
            self.qc_result.insert(tk.END, f"Erro na analise:\n{e}")
        self.ui.em_segundo_plano(tarefa, ao_erro=falhou, nome="qc")

    def exportar_relatorio_qc(self):
        if not self.qc_report:
            messagebox.showwarning("QC", "Analise um video primeiro.")
            return
        destino = filedialog.asksaveasfilename(defaultextension=".pdf",
                                               filetypes=[("PDF", "*.pdf"), ("Texto", "*.txt")])
        if destino:
            self.qc.gerar_relatorio_pdf(self.qc_report, Path(destino))
            messagebox.showinfo("QC", f"Relatorio salvo:\n{destino}")

    # ============================================================
    # NAVEGACAO / AJUDA
    # ============================================================

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

    def abrir_logs(self):
        pasta = diretorio_config() / "logs"
        pasta.mkdir(exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(pasta))  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(pasta)])
        except OSError:
            messagebox.showinfo("Logs", str(pasta))

    def sobre(self):
        messagebox.showinfo("Sobre",
                            f"Video Builder Pro v{VERSAO}\n\nProfessional Suite\n\n"
                            "Plugins:\n- video-automation\n- color-grading-pro\n- video-editor-senior\n"
                            "- Claude AI (roteiros e textos)\n\n"
                            f"Logs: {diretorio_config() / 'logs'}")


# ============================================================
# MAIN - PONTO DE ENTRADA
# ============================================================

def main():
    root = tk.Tk()
    VideoBuilderProV7(root)
    root.mainloop()


if __name__ == "__main__":
    main()
