#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIRETOR IA - Video Builder Pro v7.8

Edicao autonoma em 4 etapas, com o Claude como diretor e revisor:

  1. INDEXAR   transcricao palavra a palavra, corte de fala (vicios,
               repeticoes, pausas, retakes), cenas, folha de contato visual.
               O material vira UNIDADES: frases ja limpas (ou cenas, se nao
               houver fala), cada uma com trechos-fonte exatos.
  2. PLANEJAR  o Diretor escolhe e ordena unidades segundo um ESTILO
               (estilos/*.json) e o briefing. Como so escolhe unidades
               pre-validadas, nenhum corte cai no meio de uma palavra.
               Sem chave da API, uma heuristica faz o plano.
  3. EXECUTAR  o plano vira uma timeline e e renderizado pelo motor da v7.7
               (callback 'renderizar', fornecido pela UI).
  4. REVISAR   nota tecnica (QC, duracao, ritmo, silencio residual) + nota do
               Claude olhando quadros do resultado. Abaixo da nota minima, o
               feedback volta ao Diretor e uma nova versao e gerada.

Arquitetura inspirada em poseljacob/agentic-video-editor (MIT: Diretor ->
Editor -> Revisor com nova tentativa) e FireRed-OpenStoryline (Apache-2.0:
estilos reutilizaveis, corte de fala). Codigo proprio.

Tudo e documentado: cada execucao grava <saida>.diretor.md e .json com os
cortes (e o texto removido), as unidades escolhidas e por que, e as notas.
"""

import base64
import json
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    from ffmpeg_utils import detectar_silencios, diretorio_config, executar, info_midia, pasta_app
    from corte_fala import ConfigCorte, CorteFala, ResultadoCorte, extrair_json
    from transcricao import Transcricao, Transcritor
    from auto_editor import AutoEditor
except ImportError:
    from .ffmpeg_utils import detectar_silencios, diretorio_config, executar, info_midia, pasta_app
    from .corte_fala import ConfigCorte, CorteFala, ResultadoCorte, extrair_json
    from .transcricao import Transcricao, Transcritor
    from .auto_editor import AutoEditor

PASTA_ESTILOS = pasta_app() / "estilos"   # estilos que vem com o app (somente leitura se instalado)
LLM = Callable[..., str]   # llm(conteudo: str | list[bloco], system=..., max_tokens=...) -> str

ESTILO_PADRAO = {
    "nome": "Personalizado", "descricao": "", "selecao": "tudo", "resolucao": [1920, 1080], "fps": 30,
    "enquadramento": "ajustar", "duracao_alvo": None, "plano_min": 0.8, "plano_max": 60.0, "gancho_max": 10.0,
    "transicao": "", "duracao_transicao": 0.0, "look": "", "look_intensidade": 1.0, "padrao_audio": "YouTube",
    "corte": {}, "nota_minima": 7.0, "regras": [],
}


# ====================================================================== estilos
def pastas_estilos() -> List[Path]:
    """Estilos do app + estilos do usuario em ~/.video_builder_pro/estilos.
    O usuario pode criar/editar estilos ali mesmo com o app instalado em
    Program Files (somente leitura); um arquivo com o mesmo nome sobrescreve."""
    return [PASTA_ESTILOS, diretorio_config() / "estilos"]


def carregar_estilos(pasta: Optional[Path] = None) -> Dict[str, Dict]:
    estilos = {}
    for d in ([Path(pasta)] if pasta else pastas_estilos()):
        for arq in sorted(Path(d).glob("*.json")):
            try:
                estilos[arq.stem] = validar_estilo(json.loads(arq.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
    return estilos


def validar_estilo(d: Dict) -> Dict:
    e = {**ESTILO_PADRAO, **(d or {})}
    if e["selecao"] not in ("tudo", "melhores", "continuo"):
        e["selecao"] = "tudo"
    if e["enquadramento"] not in ("ajustar", "preencher", "desfocar"):
        e["enquadramento"] = "ajustar"
    e["resolucao"] = [int(x) for x in e["resolucao"]][:2]
    e["corte"] = {k: v for k, v in (e.get("corte") or {}).items() if k in ConfigCorte.__dataclass_fields__}
    return e


# ====================================================================== modelos
@dataclass
class Unidade:
    id: str
    arquivo: str
    trechos: List[Tuple[float, float]]
    texto: str = ""
    tipo: str = "fala"           # fala | cena
    energia: float = 0.0

    @property
    def duracao(self) -> float:
        return sum(f - i for i, f in self.trechos)


@dataclass
class PlanoEdicao:
    estilo: str
    unidades: List[str]
    titulo: str = ""
    gancho: str = ""
    justificativas: Dict[str, str] = field(default_factory=dict)
    observacoes: str = ""
    origem: str = "heuristica"   # claude | heuristica | manual
    tentativa: int = 1

    def clipes(self, indice: "Indice") -> List[Dict]:
        """Lista final de clipes (arquivo, inicio, fim) na ordem do plano."""
        res = []
        for uid in self.unidades:
            u = indice.unidade(uid)
            for ini, fim in u.trechos:
                res.append({"arquivo": u.arquivo, "inicio": round(ini, 3), "fim": round(fim, 3), "unidade": uid})
        return res

    def duracao(self, indice: "Indice") -> float:
        return sum(indice.unidade(u).duracao for u in self.unidades)


@dataclass
class Revisao:
    nota: float
    nota_tecnica: float
    nota_ia: Optional[float]
    aprovado: bool
    metricas: Dict[str, Any] = field(default_factory=dict)
    problemas: List[str] = field(default_factory=list)
    sugestoes: List[str] = field(default_factory=list)
    criterios_ia: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Indice:
    arquivos: List[Dict]
    unidades: List[Unidade]

    def unidade(self, uid: str) -> Unidade:
        for u in self.unidades:
            if u.id == uid:
                return u
        raise KeyError(uid)


# ====================================================================== util visual
def folha_contato(video: Path, saida: Path, colunas: int = 4, linhas: int = 3, lado: int = 320) -> Path:
    """Grade de quadros igualmente espacados (JPEG <= 1568 px, limite sem
    reamostragem da API de visao). Ordem: esquerda->direita, cima->baixo."""
    info = info_midia(Path(video))
    n = colunas * linhas
    taxa = n / max(info["duracao"], 0.1)
    escala = f"scale='if(gt(iw,ih),{lado},-2)':'if(gt(iw,ih),-2,{lado})'"
    executar(["ffmpeg", "-y", "-i", str(video), "-an", "-vf",
              f"fps={taxa:.5f},{escala},pad={lado}:{lado}:(ow-iw)/2:(oh-ih)/2,tile={colunas}x{linhas}",
              "-frames:v", "1", "-q:v", "5", str(saida)])
    return Path(saida)


def bloco_imagem(caminho: Path) -> Dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(Path(caminho).read_bytes()).decode("ascii")}}


# ====================================================================== 1. indexar
class Indexador:
    def __init__(self, log: Callable, transcritor: Optional[Transcritor] = None, llm: Optional[LLM] = None):
        self.log = log
        self.transcritor = transcritor or Transcritor(log)
        self.llm = llm
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vbp_diretor_"))

    def indexar(self, arquivos: Sequence[Path], estilo: Dict, idioma: str = "pt", modelo: str = "base",
                detectar_retakes: bool = True) -> Indice:
        cfg = ConfigCorte(**estilo.get("corte", {}))
        dados, unidades = [], []
        for n, arq in enumerate(arquivos, 1):
            arq = Path(arq)
            info = info_midia(arq)
            if not info["tem_video"]:
                raise ValueError(f"'{arq.name}' nao tem video.")
            reg: Dict[str, Any] = {"n": n, "arquivo": str(arq), "nome": arq.name, "duracao": info["duracao"],
                                   "transcricao": None, "corte": None, "avisos": []}
            transc = None
            if info["tem_audio"]:
                try:
                    transc = self.transcritor.transcrever(arq, idioma, modelo)
                except RuntimeError as e:      # nenhum backend instalado
                    reg["avisos"].append(str(e))
                    self.log(f"[AVISO] {e}")
            if transc and transc.palavras:
                retakes = []
                corte = CorteFala(self.log, cfg)
                if detectar_retakes and self.llm:
                    retakes = corte.detectar_retakes(transc, self.llm)
                res = corte.calcular(transc, retakes, info["duracao"])
                reg.update(transcricao={"backend": transc.backend, "palavras": len(transc.palavras),
                                        "texto": transc.texto}, corte=res.to_dict(), retakes=retakes)
                reg["avisos"] += res.avisos
                unidades += self._unidades_fala(n, arq, transc, res, estilo)
            else:
                unidades += self._unidades_cena(n, arq, info["duracao"], estilo)
            try:
                reg["folha"] = str(folha_contato(arq, self.temp_dir / f"folha_{n}.jpg"))
            except Exception as e:  # noqa: BLE001 - so usada pela visao
                self.log(f"[AVISO] folha de contato de {arq.name}: {e}")
            dados.append(reg)
        if not unidades:
            raise ValueError("Nenhum trecho aproveitavel encontrado no material.")
        self.log(f"Indexado: {len(arquivos)} arquivo(s), {len(unidades)} unidades")
        return Indice(dados, unidades)

    @staticmethod
    def _unidades_fala(n: int, arq: Path, t: Transcricao, res: ResultadoCorte, estilo: Dict) -> List[Unidade]:
        """Uma unidade por frase: trechos mantidos dentro da janela da frase."""
        segs = t.segmentos
        limites = [0.0] + [(a.fim + b.inicio) / 2 for a, b in zip(segs, segs[1:])] + [res.duracao_original]
        unidades = []
        for k, s in enumerate(segs):
            ja, jb = limites[k], limites[k + 1]
            trechos = [(max(i, ja), min(f, jb)) for i, f in res.manter if min(f, jb) - max(i, ja) > 0.05]
            if not trechos:
                continue  # frase inteira removida (retake)
            dur_fala = sum(p.fim - p.inicio for p in s.palavras) or 0.01
            conf = sum(p.prob for p in s.palavras) / max(1, len(s.palavras))
            energia = round(len(s.palavras) / max(0.5, sum(f - i for i, f in trechos)) * conf, 3)
            unidades.append(Unidade(f"a{n}f{s.id}", str(arq), [(round(i, 3), round(f, 3)) for i, f in trechos],
                                    s.texto.strip(), "fala", energia))
        return unidades

    def _unidades_cena(self, n: int, arq: Path, duracao: float, estilo: Dict) -> List[Unidade]:
        """Sem fala: unidades = cenas, divididas pelo plano maximo do estilo."""
        try:
            cenas = AutoEditor(self.log).detectar_cenas(arq)
        except Exception:  # noqa: BLE001
            cenas = [{"inicio": 0.0, "fim": duracao}]
        pmax = float(estilo.get("plano_max") or 60)
        unidades, k = [], 0
        for c in cenas:
            ini = c["inicio"]
            while c["fim"] - ini > 0.3:
                fim = min(c["fim"], ini + pmax)
                unidades.append(Unidade(f"a{n}c{k}", str(arq), [(round(ini, 3), round(fim, 3))], "", "cena",
                                        round(fim - ini, 3)))
                ini, k = fim, k + 1
        return unidades

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)


# ====================================================================== 2. planejar
class Diretor:
    def __init__(self, log: Callable, llm: Optional[LLM] = None):
        self.log = log
        self.llm = llm

    def planejar(self, indice: Indice, estilo: Dict, brief: str = "", feedback: Optional[Revisao] = None,
                 plano_anterior: Optional[PlanoEdicao] = None, tentativa: int = 1, estilo_id: str = "") -> PlanoEdicao:
        if self.llm:
            try:
                plano = self._planejar_llm(indice, estilo, brief, feedback, plano_anterior, estilo_id)
                plano.tentativa = tentativa
                return self._ajustar_duracao(plano, indice, estilo)
            except Exception as e:  # noqa: BLE001 - cai na heuristica, documentado no plano
                self.log(f"[AVISO] Diretor IA indisponivel ({e}); usando heuristica.")
                plano = self._heuristica(indice, estilo, estilo_id)
                plano.observacoes = f"Plano heuristico (falha do Claude: {e}). " + plano.observacoes
                plano.tentativa = tentativa
                return plano
        plano = self._heuristica(indice, estilo, estilo_id, feedback)
        plano.tentativa = tentativa
        return plano

    # ---------------------------------------------------- heuristica (sem API)
    def _heuristica(self, indice: Indice, estilo: Dict, estilo_id: str = "",
                    feedback: Optional[Revisao] = None) -> PlanoEdicao:
        us = indice.unidades
        alvo = estilo.get("duracao_alvo")
        if feedback and alvo:   # 2a tentativa sem IA: aperta a duracao em 15%
            alvo = alvo * 0.85
        modo = estilo.get("selecao", "tudo")
        escolhidas: List[Unidade]
        if not alvo or modo == "tudo" or sum(u.duracao for u in us) <= alvo:
            escolhidas, motivo = list(us), "todo o material util, em ordem"
        elif modo == "continuo":
            melhor, melhor_v = (0, 1), -1.0
            for i in range(len(us)):
                dur, soma = 0.0, 0.0
                for j in range(i, len(us)):
                    if us[j].arquivo != us[i].arquivo or dur + us[j].duracao > alvo * 1.1:
                        break
                    dur += us[j].duracao
                    soma += us[j].energia * us[j].duracao
                    if soma > melhor_v:
                        melhor, melhor_v = (i, j + 1), soma
            escolhidas, motivo = us[melhor[0]:melhor[1]], "trecho continuo de maior densidade de fala"
        else:
            ranking = sorted(us, key=lambda u: u.energia, reverse=True)
            sel, dur = [], 0.0
            for u in ranking:
                if dur + u.duracao <= alvo * 1.05:
                    sel.append(u)
                    dur += u.duracao
            ordem = {u.id: k for k, u in enumerate(us)}
            escolhidas = sorted(sel or ranking[:1], key=lambda u: ordem[u.id])
            motivo = "unidades de maior densidade de fala ate a duracao alvo, em ordem original"
        ids = [u.id for u in escolhidas]
        gancho = ""
        if float(estilo.get("gancho_max") or 99) <= 5 and len(escolhidas) > 1:
            forte = max(escolhidas, key=lambda u: u.energia)
            ids.remove(forte.id)
            ids.insert(0, forte.id)
            gancho = f"{forte.id}: unidade de maior energia movida para o inicio (gancho)"
        return PlanoEdicao(estilo_id or estilo.get("nome", ""), ids, titulo="", gancho=gancho,
                           justificativas={i: motivo for i in ids}, origem="heuristica",
                           observacoes=f"Selecao '{modo}', alvo {alvo or 'livre'}.")

    # ---------------------------------------------------- Claude
    def _planejar_llm(self, indice: Indice, estilo: Dict, brief: str, feedback: Optional[Revisao],
                      anterior: Optional[PlanoEdicao], estilo_id: str) -> PlanoEdicao:
        linhas = []
        for u in indice.unidades:
            n = u.id.split("f")[0].split("c")[0][1:]
            txt = u.texto if u.tipo == "fala" else "(cena sem fala)"
            linhas.append(f"{u.id} | arq {n} | {u.trechos[0][0]:.1f}s | {u.duracao:.1f}s | {txt}")
        alvo = estilo.get("duracao_alvo")
        regras = "\n".join(f"- {r}" for r in estilo.get("regras", []))
        partes = [
            f"ESTILO: {estilo['nome']} - {estilo['descricao']}",
            f"DURACAO ALVO: {f'{alvo} s (tolerancia 15%)' if alvo else 'livre (use o necessario)'}",
            f"GANCHO: o inicio deve prender em ate {estilo['gancho_max']} s.",
            f"REGRAS DO ESTILO:\n{regras}" if regras else "",
            f"BRIEFING DO USUARIO: {brief}" if brief.strip() else "",
            "ARQUIVOS: " + "; ".join(f"arq {a['n']} = {a['nome']} ({a['duracao']:.1f}s)" for a in indice.arquivos),
            "UNIDADES DISPONIVEIS (id | arquivo | inicio | duracao | texto). Vicios, repeticoes e pausas "
            "JA foram removidos de cada unidade:\n" + "\n".join(linhas),
        ]
        if feedback and anterior:
            partes.append("VERSAO ANTERIOR (reprovada pelo revisor, nota "
                          f"{feedback.nota:.1f}): {', '.join(anterior.unidades)}\n"
                          "PROBLEMAS: " + "; ".join(feedback.problemas) + "\n"
                          "SUGESTOES: " + "; ".join(feedback.sugestoes) + "\nCorrija esses pontos.")
        partes.append('Responda SO com JSON: {"titulo": "...", "gancho": "por que o inicio prende", '
                      '"unidades": ["id", ...] (ordem final, sem repetir), '
                      '"justificativas": {"id": "por que entra"}, "observacoes": "..."}')
        conteudo: List[Dict] = []
        for a in indice.arquivos[:4]:          # ate 4 folhas de contato (custo controlado)
            if a.get("folha") and Path(a["folha"]).exists():
                conteudo.append(bloco_imagem(Path(a["folha"])))
                conteudo.append({"type": "text", "text": f"Acima: 12 quadros igualmente espacados do arq {a['n']} "
                                                         "(esquerda->direita, cima->baixo)."})
        conteudo.append({"type": "text", "text": "\n\n".join(p for p in partes if p)})
        system = ("Voce e um diretor e editor de video profissional. Escolhe e ordena trechos para o melhor "
                  "resultado possivel no estilo pedido: gancho forte, ritmo, clareza e final redondo. "
                  "Nunca invente ids. Responda apenas JSON valido.")
        self.log("Diretor IA (Claude) planejando a edicao...")
        dados = extrair_json(self.llm(conteudo, system=system, max_tokens=3000))
        validos = {u.id for u in indice.unidades}
        ids, vistos = [], set()
        for uid in dados.get("unidades", []):
            uid = str(uid).strip()
            if uid in validos and uid not in vistos:
                ids.append(uid)
                vistos.add(uid)
        invalidos = [str(u) for u in dados.get("unidades", []) if str(u).strip() not in validos]
        if not ids:
            raise ValueError("o plano do Claude nao tinha nenhuma unidade valida")
        obs = str(dados.get("observacoes", ""))
        if invalidos:
            obs += f" [ids invalidos descartados: {', '.join(invalidos[:10])}]"
        return PlanoEdicao(estilo_id or estilo["nome"], ids, str(dados.get("titulo", ""))[:150],
                           str(dados.get("gancho", ""))[:400],
                           {k: str(v)[:300] for k, v in (dados.get("justificativas") or {}).items() if k in vistos},
                           obs.strip(), "claude")

    def _ajustar_duracao(self, plano: PlanoEdicao, indice: Indice, estilo: Dict) -> PlanoEdicao:
        alvo = estilo.get("duracao_alvo")
        if not alvo:
            return plano
        removidas = []
        while len(plano.unidades) > 1 and plano.duracao(indice) > alvo * 1.15:
            removidas.append(plano.unidades.pop())   # preserva o gancho (inicio)
        if removidas:
            plano.observacoes += f" [ajuste automatico: {len(removidas)} unidade(s) finais retiradas para " \
                                 f"caber em {alvo}s +15%]"
            self.log(f"Plano acima da duracao alvo: removidas {removidas}")
        return plano


# ====================================================================== 4. revisar
class Revisor:
    def __init__(self, log: Callable, llm: Optional[LLM] = None):
        self.log = log
        self.llm = llm

    def revisar(self, video: Path, plano: PlanoEdicao, indice: Indice, estilo: Dict,
                qc: Any = None, usar_visao: bool = True, brief: str = "") -> Revisao:
        video = Path(video)
        dur = info_midia(video)["duracao"]
        clipes = plano.clipes(indice)
        planos = [c["fim"] - c["inicio"] for c in clipes]
        m: Dict[str, Any] = {"duracao": round(dur, 2), "clipes": len(clipes),
                             "plano_mais_longo": round(max(planos), 2) if planos else 0,
                             "plano_mais_curto": round(min(planos), 2) if planos else 0}
        nota, problemas, sugestoes = 10.0, [], []
        if qc is not None:
            m["qc_aprovado"] = bool(getattr(qc, "aprovado", True))
            for p in list(getattr(qc, "problemas", []))[:2]:
                problemas.append(f"QC: {p}")
                nota -= 2.0
        alvo = estilo.get("duracao_alvo")
        if alvo:
            desvio = abs(dur - alvo) / alvo
            m["desvio_duracao"] = round(desvio, 3)
            if desvio > 0.4:
                nota -= 3.0
                problemas.append(f"Duracao {dur:.0f}s muito longe do alvo {alvo}s")
                sugestoes.append("Mais curto" if dur > alvo else "Incluir mais trechos relevantes")
            elif desvio > 0.2:
                nota -= 1.5
                problemas.append(f"Duracao {dur:.0f}s fora do alvo {alvo}s (+/-20%)")
        pmax = float(estilo.get("plano_max") or 1e9)
        if planos and max(planos) > pmax * 1.2:
            nota -= 1.0
            problemas.append(f"Plano de {max(planos):.1f}s acima do maximo do estilo ({pmax}s)")
            sugestoes.append("Usar unidades mais curtas para dar ritmo")
        curtos = sum(1 for p in planos if p < float(estilo.get("plano_min") or 0) * 0.5)
        if curtos:
            nota -= min(1.5, 0.5 * curtos)
            problemas.append(f"{curtos} plano(s) curtos demais (efeito 'piscada')")
        if info_midia(video)["tem_audio"]:
            sil = sum(f - i for i, f in detectar_silencios(video, -40.0, 0.8))
            m["silencio_residual"] = round(sil / max(dur, 0.1), 3)
            if sil / max(dur, 0.1) > 0.15:
                nota -= 2.0
                problemas.append(f"{sil:.1f}s de silencio no resultado")
            elif sil / max(dur, 0.1) > 0.05:
                nota -= 1.0
                problemas.append(f"{sil:.1f}s de silencio residual")
        for a in indice.arquivos:
            if any("modo seguro" in x for x in a.get("avisos", [])):
                nota -= 1.0
                problemas.append(f"Corte de fala em modo seguro em {a['nome']} (transcricao suspeita)")
        tecnica = round(max(0.0, min(10.0, nota)), 2)

        nota_ia, criterios = None, {}
        if usar_visao and self.llm:
            try:
                nota_ia, criterios, p_ia, s_ia = self._avaliar_ia(video, plano, indice, estilo, brief)
                problemas += [f"IA: {p}" for p in p_ia]
                sugestoes += s_ia
            except Exception as e:  # noqa: BLE001 - revisao visual e opcional
                self.log(f"[AVISO] Revisao visual indisponivel: {e}")
        final = round(0.4 * tecnica + 0.6 * nota_ia, 2) if nota_ia is not None else tecnica
        aprovado = final >= float(estilo.get("nota_minima") or 7)
        self.log(f"Revisao: nota {final:.1f} (tecnica {tecnica:.1f}"
                 f"{f', IA {nota_ia:.1f}' if nota_ia is not None else ''}) -> "
                 f"{'APROVADO' if aprovado else 'REFAZER'}")
        return Revisao(final, tecnica, nota_ia, aprovado, m, problemas, sugestoes, criterios)

    def _avaliar_ia(self, video: Path, plano: PlanoEdicao, indice: Indice, estilo: Dict, brief: str):
        tmp = Path(tempfile.mkdtemp(prefix="vbp_rev_"))
        try:
            folha = folha_contato(video, tmp / "resultado.jpg", 4, 4, 300)
            texto = " / ".join(indice.unidade(u).texto for u in plano.unidades if indice.unidade(u).texto)
            conteudo = [bloco_imagem(folha), {"type": "text", "text": (
                f"Acima: 16 quadros igualmente espacados do video editado ({estilo['nome']}).\n"
                f"Fala, na ordem montada: {texto[:6000] or '(sem fala)'}\n"
                f"Briefing: {brief or '-'}\nRegras do estilo: {'; '.join(estilo.get('regras', []))}\n"
                'Avalie como editor-chefe exigente. JSON: {"nota": 0-10, "criterios": {"gancho": 0-10, '
                '"ritmo": 0-10, "clareza": 0-10, "visual": 0-10, "final": 0-10}, '
                '"problemas": ["..."], "sugestoes": ["acao concreta para a proxima versao"]}')}]
            dados = extrair_json(self.llm(conteudo, system="Voce revisa videos editados. Responda so JSON.",
                                          max_tokens=1200))
            nota = max(0.0, min(10.0, float(dados["nota"])))
            return (nota, dados.get("criterios", {}), [str(x) for x in dados.get("problemas", [])][:5],
                    [str(x) for x in dados.get("sugestoes", [])][:5])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ====================================================================== orquestrador
@dataclass
class Versao:
    n: int
    arquivo: str
    plano: PlanoEdicao
    revisao: Revisao


@dataclass
class ResultadoDiretor:
    final: Path
    versoes: List[Versao]
    melhor: int
    relatorio_md: Path
    relatorio_json: Path


Renderizador = Callable[[List[Dict], Dict, Path], Tuple[Path, Any]]
"""renderizar(clipes, estilo, saida) -> (arquivo, qc_report). Fornecido pela UI
(converte para ProjectTimeline e usa o ProfessionalRenderer da v7.7)."""


class DiretorIA:
    def __init__(self, log: Callable, renderizar: Renderizador, llm: Optional[LLM] = None,
                 transcritor: Optional[Transcritor] = None):
        self.log = log
        self.renderizar = renderizar
        self.llm = llm
        self.indexador = Indexador(log, transcritor, llm)
        self.diretor = Diretor(log, llm)
        self.revisor = Revisor(log, llm)
        self.indice: Optional[Indice] = None

    def analisar(self, arquivos: Sequence[Path], estilo: Dict, idioma: str = "pt", modelo: str = "base",
                 detectar_retakes: bool = True) -> Indice:
        self.indice = self.indexador.indexar(arquivos, validar_estilo(estilo), idioma, modelo, detectar_retakes)
        return self.indice

    def executar(self, arquivos: Sequence[Path], estilo: Dict, saida: Path, brief: str = "",
                 max_tentativas: int = 2, usar_visao: bool = True, idioma: str = "pt", modelo: str = "base",
                 detectar_retakes: bool = True, estilo_id: str = "") -> ResultadoDiretor:
        estilo = validar_estilo(estilo)
        saida = Path(saida)
        if self.indice is None or [a["arquivo"] for a in self.indice.arquivos] != [str(Path(a)) for a in arquivos]:
            self.analisar(arquivos, estilo, idioma, modelo, detectar_retakes)
        indice = self.indice
        versoes: List[Versao] = []
        plano, revisao = None, None
        for n in range(1, max(1, int(max_tentativas)) + 1):
            self.log(f"===== Diretor IA: versao {n} =====")
            plano = self.diretor.planejar(indice, estilo, brief, revisao, plano, n, estilo_id)
            destino = saida.with_name(f"{saida.stem}_v{n}{saida.suffix or '.mp4'}")
            arquivo, qc = self.renderizar(plano.clipes(indice), estilo, destino)
            revisao = self.revisor.revisar(arquivo, plano, indice, estilo, qc, usar_visao, brief)
            versoes.append(Versao(n, str(arquivo), plano, revisao))
            if revisao.aprovado:
                break
        melhor = max(versoes, key=lambda v: v.revisao.nota)
        shutil.copyfile(melhor.arquivo, saida)
        md, js = self._relatorio(saida, estilo, brief, indice, versoes, melhor.n)
        self.log(f"[OK] Final: {saida.name} (versao {melhor.n}, nota {melhor.revisao.nota:.1f}). Relatorio: {md.name}")
        return ResultadoDiretor(saida, versoes, melhor.n, md, js)

    # ---------------------------------------------------- documentacao
    def _relatorio(self, saida: Path, estilo: Dict, brief: str, indice: Indice, versoes: List[Versao],
                   melhor: int) -> Tuple[Path, Path]:
        agora = datetime.now().isoformat(timespec="seconds")
        dados = {"gerado_em": agora, "saida": str(saida), "estilo": estilo, "brief": brief, "versao_escolhida": melhor,
                 "arquivos": [{k: v for k, v in a.items() if k != "folha"} for a in indice.arquivos],
                 "unidades": [asdict(u) for u in indice.unidades],
                 "versoes": [{"n": v.n, "arquivo": v.arquivo, "plano": asdict(v.plano),
                              "duracao_plano": round(v.plano.duracao(indice), 2), "revisao": asdict(v.revisao)}
                             for v in versoes]}
        js = saida.with_suffix(".diretor.json")
        js.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

        L = [f"# Relatorio do Diretor IA - {saida.name}", "", f"- Gerado em: {agora}",
             f"- Estilo: **{estilo['nome']}** ({estilo['descricao']})", f"- Briefing: {brief or '-'}",
             f"- Versao escolhida: **v{melhor}** de {len(versoes)}", "", "## Material", ""]
        for a in indice.arquivos:
            L.append(f"### {a['nome']} ({a['duracao']:.1f}s)")
            if a.get("transcricao"):
                L.append(f"- Transcricao: {a['transcricao']['backend']}, {a['transcricao']['palavras']} palavras")
            c = a.get("corte")
            if c:
                L.append(f"- Corte de fala: {c['duracao_original']:.1f}s -> {c['duracao_final']:.1f}s; "
                         f"por motivo (s): {c['resumo_por_motivo']}")
                if a.get("retakes"):
                    L.append(f"- Retakes removidos (frases): {a['retakes']}")
                removidos = [x for x in c["cortes"] if x["texto"]]
                if removidos:
                    L.append("- Palavras removidas:")
                    L += [f"  - {x['inicio']:.2f}-{x['fim']:.2f}s [{x['motivo']}] \"{x['texto']}\"" for x in removidos[:200]]
            for av in a.get("avisos", []):
                L.append(f"- AVISO: {av}")
            L.append("")
        for v in versoes:
            r = v.revisao
            L += [f"## Versao {v.n} - nota {r.nota:.1f} ({'aprovada' if r.aprovado else 'reprovada'})", "",
                  f"- Arquivo: `{Path(v.arquivo).name}`  |  plano: {v.plano.origem}  |  duracao do plano: "
                  f"{v.plano.duracao(indice):.1f}s", f"- Notas: tecnica {r.nota_tecnica:.1f}"
                  f"{f', IA {r.nota_ia:.1f}' if r.nota_ia is not None else ''}; metricas {r.metricas}"]
            if v.plano.titulo:
                L.append(f"- Titulo sugerido: {v.plano.titulo}")
            if v.plano.gancho:
                L.append(f"- Gancho: {v.plano.gancho}")
            if v.plano.observacoes:
                L.append(f"- Observacoes: {v.plano.observacoes}")
            L += ["", "| # | Unidade | Duracao | Texto | Por que entrou |", "|---|---|---|---|---|"]
            for k, uid in enumerate(v.plano.unidades, 1):
                u = indice.unidade(uid)
                txt = (u.texto or "(cena)").replace("|", "/")[:120]
                L.append(f"| {k} | {uid} | {u.duracao:.1f}s | {txt} | {v.plano.justificativas.get(uid, '')[:120]} |")
            if r.problemas:
                L += ["", "Problemas apontados:"] + [f"- {p}" for p in r.problemas]
            if r.sugestoes:
                L += ["", "Sugestoes:"] + [f"- {s}" for s in r.sugestoes]
            L.append("")
        md = saida.with_suffix(".diretor.md")
        md.write_text("\n".join(L), encoding="utf-8")
        return md, js
