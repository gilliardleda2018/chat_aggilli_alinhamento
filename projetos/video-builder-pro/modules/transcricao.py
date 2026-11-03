#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRANSCRICAO - Video Builder Pro v7.8

Transcricao com tempo de CADA PALAVRA, base do corte de fala (vicios,
repeticoes, pausas) e do Diretor IA. Ate a v7.7 so havia legendas por frase
(Whisper CLI -> SRT), sem precisao para cortar no meio de uma frase.

Backends, em ordem de preferencia (o primeiro instalado e usado):
  1. whisperx        - alinhamento forcado (wav2vec2): melhor precisao de corte
  2. stable_whisper  - (stable-ts) timestamps estabilizados
  3. faster_whisper  - word_timestamps=True, rapido em CPU
  4. whisper         - openai-whisper com word_timestamps=True

Todos sao convertidos para o mesmo formato (Transcricao/Segmento/Palavra) e
o resultado fica em cache (~/.video_builder_pro/cache/transcricoes), porque
transcrever e a etapa mais lenta e o Diretor pode replanejar varias vezes.
"""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from ffmpeg_utils import diretorio_config, executar, info_midia
except ImportError:
    from .ffmpeg_utils import diretorio_config, executar, info_midia

ORDEM_BACKENDS = ("whisperx", "stable_whisper", "faster_whisper", "whisper")
VERSAO_CACHE = 1


@dataclass
class Palavra:
    texto: str
    inicio: float
    fim: float
    prob: float = 1.0


@dataclass
class Segmento:
    id: int
    inicio: float
    fim: float
    texto: str
    palavras: List[Palavra] = field(default_factory=list)


@dataclass
class Transcricao:
    idioma: str
    backend: str
    duracao: float
    segmentos: List[Segmento] = field(default_factory=list)

    @property
    def palavras(self) -> List[Palavra]:
        return [p for s in self.segmentos for p in s.palavras]

    @property
    def texto(self) -> str:
        return " ".join(s.texto for s in self.segmentos).strip()

    def to_dict(self) -> Dict:
        return {"versao": VERSAO_CACHE, **asdict(self)}

    @classmethod
    def from_dict(cls, d: Dict) -> "Transcricao":
        segs = [Segmento(s["id"], s["inicio"], s["fim"], s["texto"],
                         [Palavra(**p) for p in s.get("palavras", [])]) for s in d.get("segmentos", [])]
        return cls(d.get("idioma", ""), d.get("backend", ""), float(d.get("duracao", 0)), segs)


# ---------------------------------------------------------------- normalizacao
def _corrigir_tempos(palavras: List[Palavra], ini_seg: float, fim_seg: float) -> List[Palavra]:
    """Preenche palavras sem tempo (numeros/simbolos no WhisperX) por
    interpolacao e garante ordem crescente sem sobreposicao."""
    n = len(palavras)
    for i, p in enumerate(palavras):
        if p.inicio is None or p.fim is None or p.fim < p.inicio:
            ant = next((palavras[j].fim for j in range(i - 1, -1, -1) if palavras[j].fim is not None), ini_seg)
            prox = next((palavras[j].inicio for j in range(i + 1, n) if palavras[j].inicio is not None), fim_seg)
            p.inicio, p.fim = ant, max(ant, prox)
    for a, b in zip(palavras, palavras[1:]):
        if b.inicio < a.fim:
            meio = (a.fim + b.inicio) / 2
            a.fim, b.inicio = meio, meio
    return palavras


def _montar(segs_brutos: List[Dict], idioma: str, backend: str, duracao: float) -> Transcricao:
    """segs_brutos: [{'start','end','text','words':[{'word','start','end','probability'}]}]"""
    segmentos = []
    for k, s in enumerate(segs_brutos):
        palavras = []
        for w in s.get("words") or []:
            texto = str(w.get("word", w.get("text", ""))).strip()
            if not texto:
                continue
            ini, fim = w.get("start"), w.get("end")
            palavras.append(Palavra(texto, None if ini is None else round(float(ini), 3),
                                    None if fim is None else round(float(fim), 3),
                                    round(float(w.get("probability", w.get("score", 1.0)) or 1.0), 3)))
        ini_s, fim_s = float(s.get("start", 0) or 0), float(s.get("end", 0) or 0)
        _corrigir_tempos(palavras, ini_s, fim_s)
        if palavras:
            ini_s, fim_s = palavras[0].inicio, palavras[-1].fim
        texto = str(s.get("text", "")).strip() or " ".join(p.texto for p in palavras)
        if texto:
            segmentos.append(Segmento(len(segmentos), round(ini_s, 3), round(fim_s, 3), texto, palavras))
    return Transcricao(idioma, backend, duracao, segmentos)


# ---------------------------------------------------------------- backends
def _cuda() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def _bk_whisperx(audio: Path, idioma: str, modelo: str, device: str) -> List[Dict]:
    import whisperx
    compute = "float16" if device == "cuda" else "int8"
    m = whisperx.load_model(modelo, device, compute_type=compute, language=idioma)
    dados = whisperx.load_audio(str(audio))
    r = m.transcribe(dados, batch_size=8, language=idioma)
    ma, meta = whisperx.load_align_model(language_code=idioma, device=device)
    r = whisperx.align(r["segments"], ma, meta, dados, device, return_char_alignments=False)
    return r["segments"]


def _bk_stable_whisper(audio: Path, idioma: str, modelo: str, device: str) -> List[Dict]:
    import stable_whisper
    r = stable_whisper.load_model(modelo, device=device).transcribe(str(audio), language=idioma)
    return [{"start": s.start, "end": s.end, "text": s.text,
             "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                       for w in s.words]} for s in r.segments]


def _bk_faster_whisper(audio: Path, idioma: str, modelo: str, device: str) -> List[Dict]:
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device=device, compute_type="float16" if device == "cuda" else "int8")
    segs, _ = m.transcribe(str(audio), language=idioma, word_timestamps=True, beam_size=5)
    return [{"start": s.start, "end": s.end, "text": s.text,
             "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                       for w in (s.words or [])]} for s in segs]


def _bk_whisper(audio: Path, idioma: str, modelo: str, device: str) -> List[Dict]:
    import whisper
    r = whisper.load_model(modelo, device=device).transcribe(str(audio), language=idioma, word_timestamps=True)
    return r["segments"]


BACKENDS: Dict[str, Callable] = {"whisperx": _bk_whisperx, "stable_whisper": _bk_stable_whisper,
                                 "faster_whisper": _bk_faster_whisper, "whisper": _bk_whisper}


def backends_instalados() -> List[str]:
    res = []
    for nome in ORDEM_BACKENDS:
        try:
            if importlib.util.find_spec(nome) is not None:
                res.append(nome)
        except (ValueError, ImportError):
            pass
    return res


# ---------------------------------------------------------------- API
class Transcritor:
    def __init__(self, log: Callable, backends: Optional[Dict[str, Callable]] = None,
                 pasta_cache: Optional[Path] = None):
        """backends: injeta implementacoes (testes ou backends novos)."""
        self.log = log
        self._backends = backends
        self.pasta_cache = pasta_cache or (diretorio_config() / "cache" / "transcricoes")

    def disponiveis(self) -> List[str]:
        return list(self._backends) if self._backends is not None else backends_instalados()

    def _chave(self, midia: Path, idioma: str, modelo: str, backend: str) -> str:
        st = midia.stat()
        base = f"{midia.resolve()}|{st.st_size}|{int(st.st_mtime)}|{idioma}|{modelo}|{backend}|{VERSAO_CACHE}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    def transcrever(self, midia: Path, idioma: str = "pt", modelo: str = "base", device: str = "auto",
                    backend: Optional[str] = None, usar_cache: bool = True) -> Transcricao:
        midia = Path(midia)
        info = info_midia(midia)
        if not info["tem_audio"]:
            raise ValueError(f"'{midia.name}' nao tem audio para transcrever.")
        disponiveis = self.disponiveis()
        if not disponiveis:
            raise RuntimeError("Nenhum transcritor instalado. Instale um (recomendado): "
                               "pip install whisperx   (ou faster-whisper / stable-ts / openai-whisper)")
        nome = backend or disponiveis[0]
        if nome not in disponiveis:
            raise RuntimeError(f"Backend '{nome}' nao instalado. Disponiveis: {', '.join(disponiveis)}")
        cache = self.pasta_cache / f"{self._chave(midia, idioma, modelo, nome)}.json"
        if usar_cache and cache.exists():
            try:
                t = Transcricao.from_dict(json.loads(cache.read_text(encoding="utf-8")))
                self.log(f"Transcricao em cache ({nome}): {midia.name}")
                return t
            except (ValueError, KeyError, TypeError):
                pass
        if device == "auto":
            device = "cuda" if _cuda() else "cpu"
        fn = (self._backends or BACKENDS)[nome]
        trabalho = Path(tempfile.mkdtemp(prefix="vbp_transc_"))
        try:
            wav = trabalho / "audio.wav"
            executar(["ffmpeg", "-y", "-i", str(midia), "-vn", "-ac", "1", "-ar", "16000",
                      "-c:a", "pcm_s16le", str(wav)], self.log)
            self.log(f"Transcrevendo {midia.name} com {nome} ({modelo}, {device})...")
            t = _montar(fn(wav, idioma, modelo, device), idioma, nome, info["duracao"])
        finally:
            shutil.rmtree(trabalho, ignore_errors=True)
        self.log(f"  {len(t.segmentos)} frases, {len(t.palavras)} palavras")
        try:
            self.pasta_cache.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(t.to_dict(), ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return t
