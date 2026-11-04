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
    def _req(self, caminho: str, corpo: Optional[Dict] = None, timeout: float = 10) -> Dict:
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(self.url + caminho, data=dados,
                                     headers={"Content-Type": "application/json"},
                                     method="GET" if corpo is None else "POST")
        try:
            with self._abrir(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")
            try:
                texto = json.loads(texto).get("error", texto)
            except ValueError:
                pass
            raise RuntimeError(f"Ollama respondeu erro {e.code}: {texto[:300]}") from e
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError(
                f"Ollama nao esta rodando em {self.url} ({getattr(e, 'reason', e)}).\n\n" + INSTRUCOES_INSTALACAO) from e

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
             max_tokens: int = 2000, timeout: float = 600) -> str:
        texto, imagens = converter_conteudo(conteudo)
        if imagens and not tem_visao(modelo):
            self.log(f"Ollama: '{modelo}' nao tem visao; {len(imagens)} imagem(ns) ignorada(s).")
            imagens = []
        msg: Dict = {"role": "user", "content": texto}
        if imagens:
            msg["images"] = imagens
        mensagens = ([{"role": "system", "content": system}] if system else []) + [msg]
        corpo = {"model": modelo, "messages": mensagens, "stream": False,
                 "options": {"num_predict": int(max_tokens)}}
        # Modelo local e mais lento que a API: timeout maior (1a chamada tambem carrega o modelo).
        resp = self._req("/api/chat", corpo, timeout=timeout)
        saida = ((resp.get("message") or {}).get("content") or "").strip()
        if not saida:
            raise RuntimeError(f"Ollama devolveu resposta vazia (modelo {modelo}).")
        return saida
