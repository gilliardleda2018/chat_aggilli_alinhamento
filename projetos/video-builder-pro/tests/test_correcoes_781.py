"""v7.8.1 - correcoes do primeiro teste do .deb no Debian (03/11/2026).

C01-C03: importacao de midia no app empacotado (ffprobe herdava as libs do pacote).
C04:     erros de importacao visiveis.
C05-C08: chave da API ("some ao trocar de aba"), teste da chave, cofre com erro.
C09:     --verificar reprova quando o ffprobe nao funciona.
"""

import importlib
import json
import os
import stat
import subprocess
import sys
import types
from pathlib import Path

import pytest

import fake_tk


@pytest.fixture(autouse=True)
def home_isolado(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    fake_tk.resetar()
    return home


def _base():
    import video_builder_pro_v7_suite as base
    return importlib.reload(base)


# --------------------------------------------------------------------- C01-C03
def test_C01_ambiente_sem_pacote(monkeypatch):
    import ffmpeg_utils as fu
    env = {"LD_LIBRARY_PATH": "/opt/app/_internal", "LD_LIBRARY_PATH_ORIG": "/usr/local/lib", "X": "1"}
    assert fu.ambiente_sem_pacote(env) == env                       # codigo-fonte: nao mexe
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    if os.name == "nt":
        assert fu.ambiente_sem_pacote(env) == env
        return
    assert fu.ambiente_sem_pacote(env) == {"LD_LIBRARY_PATH": "/usr/local/lib", "X": "1"}
    assert "LD_LIBRARY_PATH" not in fu.ambiente_sem_pacote({"LD_LIBRARY_PATH": "/opt/app/_internal"})


@pytest.mark.skipif(os.name == "nt", reason="LD_LIBRARY_PATH e do Linux")
def test_C02_subprocessos_nao_herdam_libs_do_pacote(monkeypatch):
    import ffmpeg_utils as fu
    monkeypatch.setattr(subprocess.Popen, "__init__", subprocess.Popen.__init__)   # restaura no fim
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/aggilli/video-builder-pro/_internal")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    try:
        assert fu.isolar_subprocessos() is True and fu.isolar_subprocessos() is False   # idempotente
        filho = subprocess.run([sys.executable, "-c", "import os; print(os.environ.get('LD_LIBRARY_PATH'))"],
                               capture_output=True, text=True).stdout.strip()
        assert filho == "None"                                          # filho sem as libs do pacote
        assert os.environ["LD_LIBRARY_PATH"].endswith("_internal")     # o proprio app continua com elas
    finally:
        if hasattr(subprocess.Popen, "_vbp_isolado"):
            del subprocess.Popen._vbp_isolado


def test_C03_dialogos_aceitam_maiusculas():
    from ffmpeg_utils import tipos_midia, tipos_video
    pad = tipos_video()[0][1].split()
    assert "*.mp4" in pad and "*.MP4" in pad and "*.MOV" in pad
    assert ("Todos os arquivos", "*") in tipos_video()
    assert "*.WAV" in tipos_midia()[0][1]


# --------------------------------------------------------------------- C04
def test_C04_importacao_mostra_o_que_falhou(midia, tmp_path):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    ruim = tmp_path / "corrompido.mp4"
    ruim.write_bytes(b"isto nao e um video")
    so_audio = tmp_path / "so_audio.m4a"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1", str(so_audio)], check=True)
    app.importar_midia([str(midia["hd_audio"]), str(ruim), str(so_audio)])
    assert len(app.clips) == 1
    erros = [m for m in fake_tk.mensagens if m[0] == "showerror"]
    assert len(erros) == 1 and "corrompido.mp4" in erros[0][2] and "so_audio.m4a" in erros[0][2]
    assert "sem trilha de video" in erros[0][2] or "nao tem trilha de video" in erros[0][2]


def test_C04b_importar_pasta_com_extensao_maiuscula(midia, tmp_path):
    import shutil
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    shutil.copy(midia["hd_audio"], tmp_path / "CAMERA.MP4")
    fake_tk.responder("askdirectory", str(tmp_path))
    app.carregar_pasta()
    assert [c.nome for c in app.clips] == ["CAMERA.MP4"]


# --------------------------------------------------------------------- C05-C08
def test_C05_chave_salva_aparece_mascarada(log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    assert app.api_key_entry.get() == "" and app.chave_status.cget("foreground") == "orange"
    chave = "sk-ant-api03-" + "x" * 40 + "WXYZ"
    app.api_key_entry.insert(0, chave)
    app.salvar_chave_ia()
    assert app.api_key_entry.get() == app.MASCARA_CHAVE                     # campo nao fica vazio...
    assert chave not in app.api_key_entry.get()                             # ...e nao mostra a chave
    assert "WXYZ" in app.chave_status.cget("text") and app.chave_status.cget("foreground") == "green"
    assert app.config.get_api_key("claude") == chave
    app.salvar_chave_ia()                                                   # salvar com a mascara mantem a chave
    assert app.config.get_api_key("claude") == chave
    app._chave_focus_in()                                                   # clicar no campo limpa a mascara
    assert app.api_key_entry.get() == ""
    app2 = base.VideoBuilderProV7(fake_tk.Tk())                             # reabrir o app
    assert app2.api_key_entry.get() == app2.MASCARA_CHAVE and "WXYZ" in app2.chave_status.cget("text")


def test_C06_testar_chave(monkeypatch, log):
    base = _base()
    cfg = base.ConfigManager()
    eng = base.ClaudeEngine(cfg, log)
    assert eng.testar_chave() == (False, "Nenhuma chave salva.")
    respostas = {"sk-ok": 200, "sk-ruim": 401}

    def get(url, headers=None, timeout=None):
        assert url.endswith("/v1/models") and headers["anthropic-version"]
        if headers["x-api-key"] == "sk-off":
            raise OSError("rede fora")
        return types.SimpleNamespace(status_code=respostas[headers["x-api-key"]], text="")
    monkeypatch.setattr(base, "requests", types.SimpleNamespace(get=get))
    assert eng.testar_chave("sk-ok") == (True, "Chave valida.")
    assert eng.testar_chave("sk-ruim")[0] is False and "recusada" in eng.testar_chave("sk-ruim")[1]
    assert "Sem conexao" in eng.testar_chave("sk-off")[1]


def test_C07_cofre_com_erro_nao_derruba_a_tela(monkeypatch, log):
    base = _base()

    class Quebrado:
        pass

    def falha(*a):
        raise RuntimeError("cofre bloqueado")
    monkeypatch.setitem(sys.modules, "keyring", types.SimpleNamespace(
        get_keyring=lambda: Quebrado(), set_password=falha, get_password=falha))
    cfg = base.ConfigManager()
    cfg.set_api_key("claude", "sk-ant-fallback-1234")                      # cai no arquivo 600
    assert "arquivo" in cfg.onde_esta_chave("claude")
    assert cfg.get_api_key("claude") == "sk-ant-fallback-1234"
    app = base.VideoBuilderProV7(fake_tk.Tk())
    assert "1234" in app.chave_status.cget("text")


def test_C08_enter_salva_e_prefixo_estranho_pergunta(log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    app.api_key_entry.insert(0, "chave-sem-prefixo-123")
    app.salvar_chave_ia()
    assert any(m[0] == "askyesno" for m in fake_tk.mensagens)              # pergunta antes de salvar


# --------------------------------------------------------------------- C09
@pytest.mark.skipif(os.name == "nt", reason="script de shell")
def test_C09_verificar_reprova_ffprobe_quebrado(tmp_path, monkeypatch):
    falso = tmp_path / "bin"
    falso.mkdir()
    for prog in ("ffmpeg", "ffprobe"):
        f = falso / prog
        f.write_text("#!/bin/sh\necho 'libstdc++.so.6: version GLIBCXX_3.4.32 not found' >&2\nexit 1\n")
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{falso}{os.pathsep}{os.environ['PATH']}")
    import rodar_v78
    importlib.reload(rodar_v78)
    destino = tmp_path / "v.json"
    assert rodar_v78.verificar(str(destino)) == 1                           # antes: "ok": true
    r = json.loads(destino.read_text(encoding="utf-8"))
    assert r["ok"] is False and "GLIBCXX" in r["ffprobe_erro"] and r["teste_importacao"].startswith("FALHOU")


# --------------------------------------------------------------------- C10
def test_C10_trocar_de_aba_sem_salvar_nao_perde_a_chave(log):
    """Relato do usuario: colava a chave, trocava de aba e ela sumia."""
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    chave = "sk-ant-api03-" + "y" * 40 + "ABCD"
    app.api_key_entry.insert(0, chave)
    app._chave_auto_salvar()                      # = <FocusOut> / <<NotebookTabChanged>>
    assert app.config.get_api_key("claude") == chave
    assert app.api_key_entry.get() == app.MASCARA_CHAVE and "ABCD" in app.chave_status.cget("text")
    assert not [m for m in fake_tk.mensagens if m[0] in ("askyesno", "showerror")]   # silencioso
    app._chave_focus_in()                         # clicou no campo e saiu sem digitar
    app._chave_auto_salvar()
    assert app.api_key_entry.get() == app.MASCARA_CHAVE and app.config.get_api_key("claude") == chave
    app._chave_focus_in()
    app.api_key_entry.insert(0, "texto-qualquer")  # sem sk-ant-: nao salva sozinho
    app._chave_auto_salvar()
    assert app.config.get_api_key("claude") == chave
