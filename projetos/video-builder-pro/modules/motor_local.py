#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Builder Pro v7.9 - motor de IA LOCAL via Ollama (https://ollama.com, licenca MIT).

Por que existe: a API do Claude e paga por uso; sem credito, a aba IA e o
Diretor IA paravam. O Ollama roda modelos abertos (Qwen, Llama, Gemma...) no
proprio computador: gratis, sem limite e sem internet depois de baixar o modelo.

Nenhum codigo do Ollama e copiado: o app so conversa com o servidor local dele
pela API HTTP documentada (POST /api/chat, GET /api/tags).

Interface igual a ClaudeEngine.mensagem(): recebe texto OU a lista de blocos no
formato da Anthropic (texto + imagens base64) e devolve texto. Assim o Diretor IA,
o Revisor (visao) e os botoes da aba IA funcionam sem mudar nada neles.

Sem dependencias novas: usa urllib da biblioteca padrao e IGNORA proxies do
sistema (o servidor e local; um http_proxy configurado quebraria a conexao).
"""

import json
import socket
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple, Union

URL_PADRAO = "http://localhost:11434"
MODELO_PADRAO = "qwen2.5:7b"

# Sugestoes por memoria RAM (modelos que respondem bem em portugues).
# (ram minima em GB, modelo, descricao). Os limites ficam ~1 GB abaixo do nominal
# porque o Linux reporta menos que o pente (8 GB -> MemTotal ~7,6 GB).
SUGESTOES = (
    (15, "qwen2.5:14b", "melhor qualidade; precisa de ~10 GB livres"),
    (7, "qwen2.5:7b", "equilibrio qualidade/velocidade (recomendado)"),
    (5, "llama3.2:3b", "leve; para computadores com pouca memoria"),
    (0, "qwen2.5:1.5b", "muito leve; qualidade basica"),
)
MODELOS_VISAO = ("llava", "qwen2.5vl", "llama3.2-vision", "gemma3", "minicpm-v", "moondream")

INSTRUCOES_INSTALACAO = (
    "1. Instale o Ollama (uma vez), como root (o hifen em 'su -' e necessario no Debian):\n"
    "   su - -c \"curl -fsSL https://ollama.com/install.sh | sh\"\n"
    "2. Baixe um modelo (como seu usuario normal):\n"
    f"   ollama pull {MODELO_PADRAO}\n"
    "3. Volte aqui e clique em 'Testar motor'.\n"
    "Se disser que o Ollama nao esta rodando: abra um terminal e rode  ollama serve"
)


def sugerir_modelo(ram_gb: float) -> Tuple[str, str]:
    for minimo, modelo, desc in SUGESTOES:
        if ram_gb >= minimo:
            return modelo, desc
    return SUGESTOES[-1][1], SUGESTOES[-1][2]


def ram_total_gb() -> float:
    """RAM total (Linux: /proc/meminfo). 0 se nao souber."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for linha in f:
                if linha.startswith("MemTotal:"):
                    return int(linha.split()[1]) / 1024 / 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def tem_visao(modelo: str) -> bool:
    nome = modelo.lower()
    return any(nome.startswith(v) for v in MODELOS_VISAO)


def converter_conteudo(conteudo: Union[str, List[Dict]]) -> Tuple[str, List[str]]:
    """Blocos da Anthropic -> (texto, [imagens base64]) do Ollama."""
    if isinstance(conteudo, str):
        return conteudo, []
    textos, imagens = [], []
    for bloco in conteudo:
        if bloco.get("type") == "text":
            textos.append(bloco.get("text", ""))
        elif bloco.get("type") == "image":
            dado = (bloco.get("source") or {}).get("data")
            if dado:
                imagens.append(dado)
    return "\n\n".join(t for t in textos if t), imagens


class OllamaCliente:
    def __init__(self, url: str = URL_PADRAO, log: Optional[Callable] = None):
        self.url = (url or URL_PADRAO).rstrip("/")
        self.log = log or (lambda *a, **k: None)
        # Sem proxy: o servidor e local.
        self._abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

    # --------------------------------------------------------------- HTTP
    def _erro_conexao(self, e: BaseException, timeout: float) -> RuntimeError:
        """v7.9.1: "timed out" NAO e "nao esta rodando". Desligado = conexao recusada
        na hora; tempo esgotado = o Ollama esta no ar mas lento (modelo grande na CPU)."""
        motivo = getattr(e, "reason", e)
        if isinstance(motivo, (TimeoutError, socket.timeout)) or "timed out" in str(motivo):
            return RuntimeError(
                f"O Ollama esta rodando, mas ficou {timeout:.0f} s sem responder.\n"
                "Normal na 1a vez (o modelo esta sendo carregado na memoria) ou com modelo "
                "grande em computador sem placa de video.\n"
                "Tente de novo; se repetir, use um modelo menor no quadro 'Motor de IA' "
                "(ex.: llama3.2:3b - rode antes: ollama pull llama3.2:3b).")
        return RuntimeError(
            f"Ollama nao esta rodando em {self.url} ({motivo}).\n\n" + INSTRUCOES_INSTALACAO)

    def _abrir_req(self, caminho: str, corpo: Optional[Dict], timeout: float):
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(self.url + caminho, data=dados,
                                     headers={"Content-Type": "application/json"},
                                     method="GET" if corpo is None else "POST")
        try:
            return self._abrir(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")
            try:
                texto = json.loads(texto).get("error", texto)
            except ValueError:
                pass
            raise RuntimeError(f"Ollama respondeu erro {e.code}: {texto[:300]}") from e
        except (urllib.error.URLError, OSError) as e:
            raise self._erro_conexao(e, timeout) from e

    def _req(self, caminho: str, corpo: Optional[Dict] = None, timeout: float = 10) -> Dict:
        r = self._abrir_req(caminho, corpo, timeout)
        try:
            with r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except OSError as e:
            raise self._erro_conexao(e, timeout) from e

    # --------------------------------------------------------------- API
    def modelos(self) -> List[str]:
        return sorted(m.get("name", "") for m in self._req("/api/tags").get("models", []) if m.get("name"))

    def testar(self, modelo: str) -> Tuple[bool, str]:
        """Servidor no ar E modelo baixado (sem gerar texto: instantaneo)."""
        try:
            instalados = self.modelos()
        except RuntimeError as e:
            return False, str(e)
        if not instalados:
            return False, f"Ollama esta rodando, mas nenhum modelo foi baixado.\nRode: ollama pull {modelo or MODELO_PADRAO}"
        alvo = modelo if ":" in modelo else modelo + ":latest"
        if modelo not in instalados and alvo not in instalados:
            return False, (f"O modelo '{modelo}' nao esta baixado.\nRode: ollama pull {modelo}\n\n"
                           f"Modelos instalados: {', '.join(instalados)}")
        visao = "com visao (revisa quadros do video)" if tem_visao(modelo) else "so texto (a revisao visual fica tecnica)"
        return True, f"Ollama pronto: {modelo} - {visao}."

    def chat(self, conteudo: Union[str, List[Dict]], modelo: str, system: str = "",
             max_tokens: int = 2000, timeout: float = 300,
             ao_parcial: Optional[Callable[[str], None]] = None) -> str:
        """v7.9.1: resposta em STREAMING. O timeout vale por trecho recebido (pausa
        maxima sem nenhuma palavra, inclui carregar o modelo), nao para a resposta
        inteira: um roteiro longo na CPU pode levar varios minutos e nao estoura mais.
        ao_parcial(texto_ate_agora) mostra o texto surgindo na tela."""
        texto, imagens = converter_conteudo(conteudo)
        if imagens and not tem_visao(modelo):
            self.log(f"Ollama: '{modelo}' nao tem visao; {len(imagens)} imagem(ns) ignorada(s).")
            imagens = []
        msg: Dict = {"role": "user", "content": texto}
        if imagens:
            msg["images"] = imagens
        mensagens = ([{"role": "system", "content": system}] if system else []) + [msg]
        corpo = {"model": modelo, "messages": mensagens, "stream": True,
                 "options": {"num_predict": int(max_tokens)}}
        partes: List[str] = []
        r = self._abrir_req("/api/chat", corpo, timeout)
        try:
            with r:
                for linha in r:                       # NDJSON: um objeto por linha
                    linha = linha.strip()
                    if not linha:
                        continue
                    d = json.loads(linha.decode("utf-8"))
                    if d.get("error"):
                        raise RuntimeError(f"Ollama: {d['error']}")
                    pedaco = (d.get("message") or {}).get("content") or ""
                    if pedaco:
                        partes.append(pedaco)
                        if ao_parcial:
                            ao_parcial("".join(partes))
                    if d.get("done"):
                        break
        except OSError as e:
            if not partes:
                raise self._erro_conexao(e, timeout) from e
            self.log(f"Ollama: conexao interrompida ({e}); usando o texto recebido ate aqui.")
        saida = "".join(partes).strip()
        if not saida:
            raise RuntimeError(f"Ollama devolveu resposta vazia (modelo {modelo}).")
        return saida
