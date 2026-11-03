#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORTE DE FALA - Video Builder Pro v7.8

Corte bruto automatico de video falado ("口播粗剪" no FireRed-OpenStoryline,
Apache-2.0 - conceito estudado, codigo proprio). Trabalha SOMENTE sobre os
tempos das palavras (modules/transcricao.py), entao nunca corta no meio de
uma palavra - diferente do corte por silencio da v7.7, que so ve volume.

O que remove (cada corte tem motivo registrado no relatorio):
  vicio       hesitacoes: "e", "eh", "ha", "hum", "ahn", "uh"... (lista abaixo)
  vicio_ctx   opcional: "tipo", "ne", "sabe" isolados (desligado por padrao:
              tambem sao palavras de verdade)
  repeticao   palavra ou par de palavras repetido em seguida ("eu eu", "eu acho eu acho")
              -> mantem a ULTIMA ocorrencia
  falsa       palavra cortada pelo Whisper com hifen no fim ("pro-")
  pausa       silencio entre palavras acima de pausa_max: encurta para pausa_alvo
  retake      (opcional, via Claude) frase abandonada que o orador repete melhor depois
  borda       silencio antes da 1a e depois da ultima palavra

Seguranca (para nao "picotar"):
  - cada corte respeita margem nas bordas das palavras vizinhas;
  - cortes < corte_minimo nao sao feitos; trechos mantidos < manter_minimo
    sao absorvidos;
  - se a remocao passar de remocao_maxima (fracao da duracao), so pausas e
    bordas sao aplicadas e um aviso e registrado.
"""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

try:
    from transcricao import Palavra, Transcricao
except ImportError:
    from .transcricao import Palavra, Transcricao

# Hesitacoes que nunca sao palavras em portugues:
VICIOS = {"eh", "hah", "ham", "hum", "hm", "hmm", "uhm", "uh", "ahn", "ah", "er", "erm"}
# Ambiguas: "e"/"a" (conectivo/artigo) e "ha" (= "ha", verbo haver). So contam
# como vicio quando ALONGADAS ("eee", "aaa", "haa") ou isoladas por pausas.
# "um" (numeral) e "uhum" (concordancia) NUNCA sao removidos.
AMBIGUOS = {"e", "a", "ha", "han"}
VICIOS_CONTEXTUAIS = {"tipo", "ne", "sabe", "entao", "assim", "basicamente"}


def normalizar(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w-]", "", s)
    return re.sub(r"(.)\1{2,}", r"\1\1", s)  # "eeeee" -> "ee", "hummm" -> "humm"


def _sem_repeticao(s: str) -> str:
    return re.sub(r"(.)\1+", r"\1", s)


@dataclass
class ConfigCorte:
    remover_vicios: bool = True
    remover_vicios_contextuais: bool = False
    remover_repeticoes: bool = True
    remover_falsas_partidas: bool = True
    cortar_pausas: bool = True
    pausa_max: float = 0.6       # silencio maior que isso entre palavras e encurtado...
    pausa_alvo: float = 0.25     # ...para este valor
    margem: float = 0.04         # folga mantida junto as palavras vizinhas
    corte_minimo: float = 0.08
    manter_minimo: float = 0.25
    borda: float = 0.15          # respiro antes da 1a / depois da ultima palavra
    remocao_maxima: float = 0.35  # fracao maxima da FALA removida antes do modo seguro


@dataclass
class Corte:
    inicio: float
    fim: float
    motivo: str
    texto: str = ""

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


@dataclass
class ResultadoCorte:
    duracao_original: float
    manter: List[Tuple[float, float]]
    cortes: List[Corte]
    avisos: List[str] = field(default_factory=list)

    @property
    def duracao_final(self) -> float:
        return sum(f - i for i, f in self.manter)

    def resumo(self) -> Dict[str, float]:
        r: Dict[str, float] = {}
        for c in self.cortes:
            r[c.motivo] = r.get(c.motivo, 0.0) + c.duracao
        return {k: round(v, 2) for k, v in r.items()}

    def to_dict(self) -> Dict:
        return {"duracao_original": round(self.duracao_original, 3),
                "duracao_final": round(self.duracao_final, 3),
                "manter": [[round(i, 3), round(f, 3)] for i, f in self.manter],
                "cortes": [asdict(c) for c in self.cortes], "resumo_por_motivo": self.resumo(),
                "avisos": self.avisos}


class CorteFala:
    def __init__(self, log: Callable, config: Optional[ConfigCorte] = None):
        self.log = log
        self.cfg = config or ConfigCorte()

    # ------------------------------------------------------------ deteccao
    def _eh_vicio(self, palavras: List[Palavra], i: int) -> Optional[str]:
        n = normalizar(palavras[i].texto).strip("-")
        if not n:
            return None
        base = _sem_repeticao(n)
        if self.cfg.remover_vicios:
            if base in AMBIGUOS:
                isolado = ((i == 0 or palavras[i].inicio - palavras[i - 1].fim > 0.3) and
                           (i == len(palavras) - 1 or palavras[i + 1].inicio - palavras[i].fim > 0.3))
                if len(n) > len(base) or isolado:
                    return "vicio"
            elif base in VICIOS or n in VICIOS:
                return "vicio"
        if self.cfg.remover_vicios_contextuais and base in VICIOS_CONTEXTUAIS:
            return "vicio_ctx"
        return None

    def marcar(self, t: Transcricao, retakes: Optional[List[int]] = None) -> Dict[int, str]:
        """indice global da palavra -> motivo da remocao."""
        pal = t.palavras
        marcadas: Dict[int, str] = {}
        for i in range(len(pal)):
            m = self._eh_vicio(pal, i)
            if m:
                marcadas[i] = m
            elif self.cfg.remover_falsas_partidas and pal[i].texto.strip().endswith("-") and len(pal[i].texto) > 2:
                marcadas[i] = "falsa"
        if self.cfg.remover_repeticoes:
            validas = [i for i in range(len(pal)) if i not in marcadas]
            norm = [normalizar(pal[i].texto) for i in validas]
            k = 0
            while k < len(validas):
                # par repetido: "eu acho eu acho" -> remove o primeiro par
                if k + 3 < len(validas) and norm[k] and norm[k:k + 2] == norm[k + 2:k + 4]:
                    marcadas[validas[k]] = marcadas[validas[k + 1]] = "repeticao"
                    k += 2
                    continue
                if k + 1 < len(validas) and norm[k] and norm[k] == norm[k + 1] and len(norm[k]) > 0:
                    marcadas[validas[k]] = "repeticao"
                k += 1
        if retakes:
            ids = set(retakes)
            gi = 0
            for s in t.segmentos:
                for _ in s.palavras:
                    if s.id in ids:
                        marcadas[gi] = "retake"
                    gi += 1
        return marcadas

    # ------------------------------------------------------------ intervalos
    def calcular(self, t: Transcricao, retakes: Optional[List[int]] = None,
                 duracao: Optional[float] = None, _seguro: bool = False) -> ResultadoCorte:
        c = self.cfg
        total = duracao or t.duracao
        pal = t.palavras
        if not pal:
            return ResultadoCorte(total, [(0.0, total)], [], ["Sem fala detectada: nada cortado."])
        marcadas = {} if _seguro else self.marcar(t, retakes)
        # limite de seguranca: mede so a FALA removida (silencio nao conta)
        fala_total = sum(p.fim - p.inicio for p in pal) or 1.0
        # retakes ficam fora da conta: ja foram limitados em detectar_retakes (<= 40%)
        fala_removida = sum(pal[k].fim - pal[k].inicio for k, m in marcadas.items() if m != "retake")
        if not _seguro and fala_removida / fala_total > c.remocao_maxima:
            res = self.calcular(t, None, duracao, _seguro=True)
            res.avisos.insert(0, f"Os cortes de palavras removeriam {fala_removida / fala_total:.0%} da fala "
                                 f"(limite {c.remocao_maxima:.0%}): aplicados so pausas e bordas (modo seguro). "
                                 "Revise a transcricao ou o idioma.")
            for a in res.avisos[:1]:
                self.log(f"[AVISO] {a}")
            return res
        cortes: List[Corte] = []

        def adicionar(ini, fim, motivo, texto=""):
            if fim - ini >= c.corte_minimo:
                cortes.append(Corte(round(ini, 3), round(fim, 3), motivo, texto))

        # palavras removidas: do fim da palavra mantida anterior ao inicio da seguinte
        i = 0
        while i < len(pal):
            if i not in marcadas:
                i += 1
                continue
            j = i
            while j + 1 < len(pal) and (j + 1) in marcadas:
                j += 1
            # O corte SEMPRE cobre inteiras as palavras removidas [pal[i].inicio, pal[j].fim];
            # do silencio em volta, fica uma pausa natural (margem minima junto as vizinhas).
            if i > 0 and j + 1 < len(pal):
                folga_esq = pal[i].inicio - pal[i - 1].fim
                folga_dir = pal[j + 1].inicio - pal[j].fim
                pausa = max(c.pausa_alvo, 2 * c.margem)
                fica_esq = min(folga_esq, max(c.margem, pausa / 2))
                fica_dir = min(folga_dir, max(c.margem, pausa - fica_esq))
                ini, fim = pal[i - 1].fim + fica_esq, pal[j + 1].inicio - fica_dir
            elif i == 0:
                ini = 0.0
                fim = total if j + 1 >= len(pal) else min(
                    pal[j + 1].inicio - c.margem, max(pal[j].fim, pal[j + 1].inicio - c.borda))
            else:
                fim = total
                ini = max(pal[i - 1].fim + c.margem, min(pal[i].inicio, pal[i - 1].fim + c.borda))
            motivos = sorted({marcadas[k] for k in range(i, j + 1)})
            adicionar(ini, fim, "+".join(motivos), " ".join(pal[k].texto for k in range(i, j + 1)))
            i = j + 1

        # pausas longas entre palavras mantidas
        if c.cortar_pausas:
            mantidas = [k for k in range(len(pal)) if k not in marcadas]
            for a, b in zip(mantidas, mantidas[1:]):
                if b != a + 1:
                    continue  # ja tratado no corte de palavras
                gap = pal[b].inicio - pal[a].fim
                if gap > c.pausa_max:
                    meio = (pal[a].fim + pal[b].inicio) / 2
                    adicionar(meio - (gap - c.pausa_alvo) / 2, meio + (gap - c.pausa_alvo) / 2, "pausa")
        # bordas
        adicionar(0.0, max(0.0, pal[0].inicio - c.borda), "borda")
        adicionar(min(total, pal[-1].fim + c.borda), total, "borda")

        cortes = self._mesclar(cortes)
        avisos: List[str] = []
        manter = self._complemento(cortes, total)
        # absorve trechos mantidos curtos demais (viram 'piscadas')
        curtos = [(a, b) for a, b in manter if b - a < c.manter_minimo]
        if curtos and len(manter) > 1:
            for a, b in curtos:
                cortes.append(Corte(round(a, 3), round(b, 3), "fragmento"))
            cortes = self._mesclar(cortes)
            manter = self._complemento(cortes, total)
        res = ResultadoCorte(total, manter, cortes, avisos)
        self.log(f"Corte de fala: {total:.1f}s -> {res.duracao_final:.1f}s ({res.resumo()})")
        for a in avisos:
            self.log(f"[AVISO] {a}")
        return res

    @staticmethod
    def _mesclar(cortes: List[Corte], tolerancia: float = 0.05) -> List[Corte]:
        res: List[Corte] = []
        for x in sorted(cortes, key=lambda k: k.inicio):
            if res and x.inicio <= res[-1].fim + tolerancia:
                u = res[-1]
                u.fim = max(u.fim, x.fim)
                if x.motivo not in u.motivo.split("+"):
                    u.motivo = "+".join(sorted(set(u.motivo.split("+")) | set(x.motivo.split("+"))))
                u.texto = " ".join(t for t in (u.texto, x.texto) if t)
            else:
                res.append(Corte(x.inicio, x.fim, x.motivo, x.texto))
        return res

    @staticmethod
    def _complemento(cortes: List[Corte], total: float) -> List[Tuple[float, float]]:
        res, cursor = [], 0.0
        for x in sorted(cortes, key=lambda k: k.inicio):
            if x.inicio > cursor + 1e-3:
                res.append((round(cursor, 3), round(x.inicio, 3)))
            cursor = max(cursor, x.fim)
        if total > cursor + 1e-3:
            res.append((round(cursor, 3), round(total, 3)))
        return res

    # ------------------------------------------------------------ retakes (LLM)
    def detectar_retakes(self, t: Transcricao, llm: Callable[..., str], maximo: float = 0.4) -> List[int]:
        """Pergunta ao Claude quais frases sao tentativas abandonadas.
        Resposta invalida ou que remova demais e ignorada (retorna [])."""
        if len(t.segmentos) < 2:
            return []
        linhas = "\n".join(f"[{s.id}] ({s.inicio:.1f}-{s.fim:.1f}s) {s.texto}" for s in t.segmentos)
        system = ("Voce e um editor de video profissional fazendo o corte bruto de uma gravacao falada. "
                  "Responda APENAS com JSON valido.")
        prompt = ("Abaixo estao as frases transcritas, com id. Identifique RETAKES: frases que o orador "
                  "comecou, abandonou ou errou e logo em seguida REPETIU de forma melhor. Marque somente a "
                  "versao ruim (a anterior). Nao marque frases unicas, nem repeticoes intencionais de enfase.\n"
                  'Formato: {"retakes": [ids], "motivos": {"id": "motivo curto"}}\n\n' + linhas)
        try:
            resposta = llm(prompt, system=system, max_tokens=800)
            dados = extrair_json(resposta)
            ids = []
            for x in dados.get("retakes", []):   # ignora ids nao numericos sem perder os validos
                try:
                    ids.append(int(x))
                except (TypeError, ValueError):
                    continue
        except Exception as e:  # noqa: BLE001 - LLM e opcional
            self.log(f"[AVISO] Deteccao de retakes ignorada: {e}")
            return []
        validos = {s.id: s for s in t.segmentos}
        ids = sorted({i for i in ids if i in validos})
        dur = sum(validos[i].fim - validos[i].inicio for i in ids)
        if t.duracao and dur / t.duracao > maximo:
            self.log(f"[AVISO] Retakes sugeridos removeriam {dur / t.duracao:.0%} (> {maximo:.0%}): ignorados")
            return []
        if ids:
            self.log(f"Retakes detectados: frases {ids}")
        return ids


def extrair_json(texto: str) -> Dict:
    """Extrai o primeiro objeto JSON de uma resposta (tolera ```json e texto em volta)."""
    texto = re.sub(r"```(?:json)?", "", texto or "")
    ini = texto.find("{")
    if ini < 0:
        raise ValueError("resposta sem JSON")
    nivel, dentro, esc = 0, False, False
    for k in range(ini, len(texto)):
        ch = texto[k]
        if dentro:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                dentro = False
        elif ch == '"':
            dentro = True
        elif ch == "{":
            nivel += 1
        elif ch == "}":
            nivel -= 1
            if nivel == 0:
                return json.loads(texto[ini:k + 1])
    raise ValueError("JSON incompleto na resposta")
