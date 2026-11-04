"""v7.9 - motor de IA local (Ollama) + erros da API em portugues.

O Ollama e simulado por um servidor HTTP de verdade (thread local) que imita
POST /api/chat e GET /api/tags - o caminho testado e o mesmo do app real.

L01-L05: cliente (modulos/motor_local.py)
L06-L08: ClaudeEngine despachando para o motor ativo; Claude continua padrao
L09-L11: aba IA (seletor) e Diretor IA
L12:     erro "credit balance" da API traduzido
L13-L15: v7.9.1 streaming (texto surgindo) e "timed out" != "nao esta rodando"
"""

import base64
import importlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import fake_tk


class _Ollama(BaseHTTPRequestHandler):
    modelos = ["qwen2.5:7b", "llava:7b"]
    pedidos: list = []
    atraso = 0.0

    def log_message(self, *a):
        pass

    def _json(self, codigo, dados):
        corpo = json.dumps(dados).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json(200, {"models": [{"name": m} for m in self.modelos]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        dados = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Ollama.pedidos.append(dados)
        if dados["model"] not in self.modelos:
            self._json(404, {"error": f"model '{dados['model']}' not found"})
            return
        user = dados["messages"][-1]
        resposta = f"[{dados['model']}] {user['content'][:40]} imgs={len(user.get('images', []))}"
        if _Ollama.atraso:
            time.sleep(_Ollama.atraso)              # simula modelo grande na CPU
        if not dados.get("stream"):
            self._json(200, {"message": {"role": "assistant", "content": resposta}})
            return
        # Streaming igual ao Ollama real: NDJSON, um pedaco por linha, depois done=true
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for i in range(0, len(resposta), 7):
            self.wfile.write((json.dumps({"message": {"role": "assistant", "content": resposta[i:i + 7]},
                                          "done": False}) + "\n").encode())
            self.wfile.flush()
        self.wfile.write((json.dumps({"message": {"content": ""}, "done": True}) + "\n").encode())


@pytest.fixture
def ollama():
    _Ollama.pedidos = []
    _Ollama.atraso = 0.0
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Ollama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(autouse=True)
def home_isolado(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    fake_tk.resetar()


def _base():
    import video_builder_pro_v7_suite as base
    return importlib.reload(base)


IMG = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                    "data": base64.b64encode(b"\xff\xd8quadro").decode()}}


# --------------------------------------------------------------------- L01-L05
def test_L01_converte_blocos_da_anthropic():
    import motor_local as ml
    assert ml.converter_conteudo("oi") == ("oi", [])
    texto, imgs = ml.converter_conteudo([{"type": "text", "text": "a"}, IMG, {"type": "text", "text": "b"}])
    assert texto == "a\n\nb" and imgs == [IMG["source"]["data"]]


def test_L02_chat_texto_system_e_limite(ollama, monkeypatch):
    import motor_local as ml
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")    # proxy do sistema nao pode atrapalhar
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    r = ml.OllamaCliente(ollama).chat("Roteiro sobre cafe", "qwen2.5:7b", system="Seja breve", max_tokens=123)
    assert r.startswith("[qwen2.5:7b] Roteiro sobre cafe")
    p = _Ollama.pedidos[-1]
    assert p["stream"] is True and p["options"]["num_predict"] == 123
    assert p["messages"][0] == {"role": "system", "content": "Seja breve"}


def test_L03_imagens_so_para_modelo_com_visao(ollama, log):
    import motor_local as ml
    c = ml.OllamaCliente(ollama, log)
    assert c.chat([{"type": "text", "text": "revise"}, IMG], "llava:7b").endswith("imgs=1")
    assert c.chat([{"type": "text", "text": "revise"}, IMG], "qwen2.5:7b").endswith("imgs=0")
    assert any("nao tem visao" in m for m in log.mensagens)


def test_L04_testar_e_listar(ollama):
    import motor_local as ml
    c = ml.OllamaCliente(ollama)
    assert c.modelos() == ["llava:7b", "qwen2.5:7b"]
    ok, msg = c.testar("qwen2.5:7b")
    assert ok and "so texto" in msg
    assert c.testar("llava:7b")[0] and "com visao" in c.testar("llava:7b")[1]
    ok, msg = c.testar("gemma3:4b")
    assert not ok and "ollama pull gemma3:4b" in msg


def test_L05_servidor_desligado_explica_como_instalar():
    import motor_local as ml
    c = ml.OllamaCliente("http://127.0.0.1:9")                # porta sem servidor
    ok, msg = c.testar("qwen2.5:7b")
    assert not ok and "nao esta rodando" in msg and "ollama.com/install.sh" in msg
    with pytest.raises(RuntimeError, match="ollama pull"):
        c.chat("oi", "qwen2.5:7b")
    assert ml.sugerir_modelo(32)[0] == "qwen2.5:14b" and ml.sugerir_modelo(8)[0] == "qwen2.5:7b"
    assert ml.sugerir_modelo(7.6)[0] == "qwen2.5:7b"                    # "8 GB" como o Linux reporta
    assert ml.sugerir_modelo(15.5)[0] == "qwen2.5:14b"
    assert ml.sugerir_modelo(4)[0] == "qwen2.5:1.5b"


# --------------------------------------------------------------------- L06-L08
def test_L06_claude_continua_padrao(log):
    base = _base()
    eng = base.ClaudeEngine(base.ConfigManager(), log)
    assert eng.motor() == "claude" and eng.modelo() == "claude-haiku-4-5-20251001"
    assert eng.pronto() is False                              # sem chave, como antes
    eng.config.set("motor_ia", "invalido")
    assert eng.motor() == "claude"
    with pytest.raises(ValueError):
        eng.definir_motor("gpt")


def test_L07_ollama_atende_mensagem_e_atalhos(ollama, log):
    base = _base()
    cfg = base.ConfigManager()
    cfg.set("ollama_url", ollama)
    eng = base.ClaudeEngine(cfg, log)
    eng.definir_motor("ollama")
    assert eng.pronto() and eng.modelo() == "qwen2.5:7b" and eng.nome_motor() == "Ollama (local)"
    assert eng.roteiro("cafe especial").startswith("[qwen2.5:7b] Crie um roteiro")
    assert eng.mensagem([{"type": "text", "text": "x"}, IMG]).endswith("imgs=0")
    eng.definir_modelo("llava:7b")
    assert cfg.get("ollama_model") == "llava:7b" and cfg.get("claude_model", "") == ""   # modelos separados
    assert eng.testar_motor()[0] is True


def test_L08_motor_persiste_entre_aberturas(log):
    base = _base()
    base.ClaudeEngine(base.ConfigManager(), log).definir_motor("ollama")
    assert base.ClaudeEngine(base.ConfigManager(), log).motor() == "ollama"


# --------------------------------------------------------------------- L09-L11
def test_L09_aba_ia_troca_motor_e_gera_local(ollama, log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    app.config.set("ollama_url", ollama)
    assert app.motor_var.get() == "claude"
    app.motor_var.set("ollama")
    app._mudar_motor()
    assert app.claude.motor() == "ollama" and "Ollama" in app.motor_status.cget("text")
    app.ia_prompt.insert("1.0", "cafe especial")
    app.gerar_ia("titulos")                                     # sem chave do Claude: funciona
    app.ui.aguardar()
    assert app.ia_result.get("1.0", "end").startswith("[qwen2.5:7b] Sugira 10 titulos")
    assert not [m for m in fake_tk.mensagens if m[0] in ("showwarning", "showerror")]


def test_L10_aba_ia_lista_e_testa(ollama, log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    app.config.set("ollama_url", ollama)
    app.motor_var.set("ollama")
    app._mudar_motor()
    app.atualizar_modelos_ollama()
    app.ui.aguardar()
    assert "qwen2.5:7b" in app.ollama_combo.cget("values") and "Modelos baixados" in app.motor_status.cget("text")
    app.ollama_modelo_var.set("llava:7b")
    app.testar_motor_ia()
    app.ui.aguardar()
    assert app.config.get("ollama_model") == "llava:7b"
    assert ("showinfo", "Motor de IA") == fake_tk.mensagens[-1][:2]


def test_L11_diretor_usa_motor_local(ollama, log):
    base = _base()
    import v76_patch
    import v78_diretor
    importlib.reload(v76_patch)
    importlib.reload(v78_diretor)
    app = base.VideoBuilderProV7(fake_tk.Tk())
    v76_patch.aplicar_patch(app)
    p = v78_diretor.aplicar_patch_v78(app)
    assert p._llm() is None and "heuristico" in p.status_ia.cget("text")
    app.config.set("ollama_url", ollama)
    app.motor_var.set("ollama")
    app._mudar_motor()                                          # status do Diretor atualiza junto
    assert "Ollama local (qwen2.5:7b)" in p.status_ia.cget("text")
    assert p._llm()("plano?").startswith("[qwen2.5:7b] plano?")


# --------------------------------------------------------------------- L12
def test_L12_erro_de_credito_em_portugues():
    base = _base()
    t = base.traduzir_erro_api(400, '{"error":{"message":"Your credit balance is too low to access the Anthropic API."}}')
    assert "sem creditos" in t and "Billing" in t and "Ollama" in t and "Detalhe tecnico 400" in t
    assert "recusada" in base.traduzir_erro_api(401, "x")
    assert "Aguarde" in base.traduzir_erro_api(429, "x")


# --------------------------------------------------------------------- L13-L15 (v7.9.1)
def test_L13_streaming_monta_texto_e_avisa_parciais(ollama):
    import motor_local as ml
    parciais = []
    r = ml.OllamaCliente(ollama).chat("Roteiro longo sobre cafe", "qwen2.5:7b", ao_parcial=parciais.append)
    assert r == "[qwen2.5:7b] Roteiro longo sobre cafe imgs=0"
    assert len(parciais) > 3 and parciais[-1] == r and all(r.startswith(x) for x in parciais)


def test_L14_lento_nao_e_desligado(ollama):
    """Relato do usuario: 'Ollama nao esta rodando ... (timed out)' com o Ollama no ar."""
    import motor_local as ml
    _Ollama.atraso = 1.5
    with pytest.raises(RuntimeError) as e:
        ml.OllamaCliente(ollama).chat("oi", "qwen2.5:7b", timeout=0.5)
    assert "esta rodando, mas ficou" in str(e.value) and "nao esta rodando" not in str(e.value)
    assert "llama3.2:3b" in str(e.value)
    _Ollama.atraso = 0.2                                            # pausa menor que o timeout: ok
    assert ml.OllamaCliente(ollama).chat("oi", "qwen2.5:7b", timeout=1).endswith("imgs=0")


def test_L15_aba_ia_mostra_texto_surgindo_e_diretor_nao_recebe(ollama, log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    app.config.set("ollama_url", ollama)
    app.motor_var.set("ollama")
    app._mudar_motor()
    vistos = []
    original = app.ia_result.insert
    app.ia_result.insert = lambda pos, txt, *a: (vistos.append(txt), original(pos, txt, *a))
    app.ia_prompt.insert("1.0", "cafe")
    app.gerar_ia("roteiro")
    app.ui.aguardar()
    assert app.ia_result.get("1.0", "end").startswith("[qwen2.5:7b] Crie um roteiro")
    assert not app.claude._progresso                               # callback removido no fim
    assert app.claude.mensagem("x").startswith("[qwen2.5:7b]")      # outra chamada: sem parcial
