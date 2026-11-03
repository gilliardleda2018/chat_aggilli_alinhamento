"""Testes da Sprint A (v7.8): transcricao palavra a palavra, corte de fala,
Diretor + Revisor IA, enquadramento e aba Diretor IA.

Whisper e Claude sao SIMULADOS (o ambiente de teste nao tem modelos nem
chave). O video de teste tem "palavras" = rajadas de tom nos tempos exatos
da transcricao simulada, entao os cortes podem ser verificados no audio.
IDs [Sxx] ligam cada teste ao CHANGELOG v7.8.
"""

import base64
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import fake_tk
from conftest import duracoes, probe

# --------------------------------------------------------------------- material
PALAVRAS = [  # (frase, texto, inicio, fim)
    (0, "Eu", 1.0, 1.3), (0, "eu", 1.4, 1.7), (0, "acho", 1.8, 2.2), (0, "éé", 2.4, 3.0),
    (0, "que", 3.1, 3.4), (0, "funciona.", 3.5, 4.0),
    (1, "Hum", 5.5, 6.0), (1, "isso", 6.2, 6.6), (1, "é", 6.7, 6.8), (1, "importante.", 6.9, 7.6),
    (2, "Obrigado.", 8.6, 9.3),
]
DURACAO = 10.0


def segs_brutos(palavras=PALAVRAS):
    segs = {}
    for f, t, a, b in palavras:
        s = segs.setdefault(f, {"start": a, "end": b, "text": "", "words": []})
        s["words"].append({"word": " " + t, "start": a, "end": b, "probability": 0.95})
        s["end"] = b
        s["text"] += " " + t
    return [segs[k] for k in sorted(segs)]


@pytest.fixture(scope="session")
def fala(tmp_path_factory):
    d = tmp_path_factory.mktemp("fala")
    v = d / "fala.mp4"
    expr = "+".join(f"between(t,{a},{b})" for _, _, a, b in PALAVRAS)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=25:d={DURACAO}",
                    "-f", "lavfi", "-i", f"sine=f=330:d={DURACAO},volume='gt({expr},0)':eval=frame",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(v)], check=True)
    return v


@pytest.fixture(autouse=True)
def home_isolado(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    fake_tk.resetar()
    return home


@pytest.fixture
def transcritor(tmp_path, log):
    from transcricao import Transcritor
    chamadas = []

    def backend(wav, idioma, modelo, device):
        chamadas.append(wav)
        return segs_brutos()
    t = Transcritor(log, backends={"fake": backend}, pasta_cache=tmp_path / "cache")
    t.chamadas = chamadas
    return t


class ClaudeFalso:
    """Simula ClaudeEngine.mensagem: devolve respostas enfileiradas e guarda o que recebeu."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.recebido = []

    def __call__(self, conteudo, system="", max_tokens=0):
        self.recebido.append(conteudo)
        r = self.respostas.pop(0) if self.respostas else "{}"
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


def _base():
    import video_builder_pro_v7_suite as base
    return importlib.reload(base)


def renderizador(log):
    base = _base()
    r = base.ProfessionalRenderer(log)

    def renderizar(clipes, estilo, saida):
        tl = base.ProjectTimeline(
            clips=[base.ClipTimeline(arquivo=Path(c["arquivo"]), inicio=c["inicio"], fim=c["fim"],
                                     duracao=c["fim"] - c["inicio"]) for c in clipes],
            resolucao=(320, 180) if estilo["resolucao"][0] > estilo["resolucao"][1] else (180, 320),
            fps=25, padrao_audio=estilo["padrao_audio"], normalizar_audio=False,
            enquadramento=estilo["enquadramento"])
        arq = r.renderizar(tl, saida, base.RenderPreset.DRAFT)
        return arq, r.ultimo_qc
    return renderizar


# ===================================================================== transcricao
def test_S01_transcricao_formato_e_cache(fala, transcritor):
    t1 = transcritor.transcrever(fala)
    assert [p.texto for p in t1.palavras][:3] == ["Eu", "eu", "acho"]
    assert len(t1.segmentos) == 3 and t1.backend == "fake"
    t2 = transcritor.transcrever(fala)                      # do cache
    assert len(transcritor.chamadas) == 1 and t2.texto == t1.texto


def test_S02_transcricao_interpola_palavras_sem_tempo(log):
    from transcricao import _montar
    t = _montar([{"start": 0, "end": 2, "text": "tem 10 reais", "words": [
        {"word": "tem", "start": 0.0, "end": 0.4}, {"word": "10"}, {"word": "reais", "start": 1.2, "end": 1.8}]}],
        "pt", "x", 2.0)
    p = t.palavras
    assert p[1].inicio == 0.4 and p[1].fim == 1.2


def test_S03_transcricao_erros_claros(midia, tmp_path, log):
    from transcricao import Transcritor
    with pytest.raises(ValueError, match="nao tem audio"):
        Transcritor(log, backends={"x": lambda *a: []}, pasta_cache=tmp_path).transcrever(midia["sd_mudo"])
    with pytest.raises(RuntimeError, match="pip install whisperx"):
        Transcritor(log, backends={}, pasta_cache=tmp_path).transcrever(midia["hd_audio"])


# ===================================================================== corte de fala
def _transc():
    from transcricao import _montar
    return _montar(segs_brutos(), "pt", "fake", DURACAO)


def test_S04_corte_remove_vicios_repeticoes_e_pausas(log):
    from corte_fala import CorteFala
    r = CorteFala(log).calcular(_transc())
    removidas = " ".join(c.texto for c in r.cortes)
    assert "éé" in removidas and "Hum" in removidas and "Eu" in removidas
    motivos = r.resumo()
    assert any("pausa" in k for k in motivos) and any("borda" in k for k in motivos)
    assert r.duracao_final < 7.0 and not r.avisos


def test_S05_corte_nunca_corta_dentro_de_palavra(log):
    from corte_fala import CorteFala
    t = _transc()
    r = CorteFala(log).calcular(t)
    removidas = {"Eu", "éé", "Hum"}
    for p in t.palavras:
        dentro = any(i - 1e-6 <= p.inicio and p.fim <= f + 1e-6 for i, f in r.manter)
        fora = all(p.fim <= i + 1e-6 or p.inicio >= f - 1e-6 for i, f in r.manter)
        assert (fora if p.texto in removidas else dentro), p


def test_S06_palavras_ambiguas_preservadas(log):
    from corte_fala import CorteFala
    from transcricao import _montar
    t = _montar([{"start": 0, "end": 3, "text": "", "words": [
        {"word": w, "start": a, "end": b} for w, a, b in
        [("Há", 0.0, 0.3), ("um", 0.35, 0.5), ("problema", 0.55, 1.0), ("e", 1.05, 1.1), ("a", 1.15, 1.2),
         ("solução", 1.25, 1.8), ("uhum", 1.85, 2.2)]]}], "pt", "x", 3.0)
    assert not CorteFala(log).marcar(t)       # nenhuma palavra real removida


def test_S07_modo_seguro_com_transcricao_suspeita(log):
    from corte_fala import CorteFala
    from transcricao import _montar
    lixo = [{"start": 0, "end": 5, "text": "", "words": [
        {"word": "hum", "start": i * 0.5, "end": i * 0.5 + 0.3} for i in range(8)] +
        [{"word": "ok", "start": 4.2, "end": 4.5}]}]
    r = CorteFala(log).calcular(_montar(lixo, "pt", "x", 5.0))
    assert r.avisos and "modo seguro" in r.avisos[0]
    assert all(set(c.motivo.split("+")) <= {"pausa", "borda", "fragmento"} for c in r.cortes)


def test_S08_corte_aplicado_no_audio_bate_com_o_calculo(fala, tmp_path, log):
    from auto_editor import AutoEditor
    from corte_fala import CorteFala
    r = CorteFala(log).calcular(_transc(), duracao=DURACAO)
    s = tmp_path / "cortado.mp4"
    AutoEditor(log)._manter_trechos(fala, s, r.manter)
    assert abs(duracoes(s)["audio"] - r.duracao_final) < 0.12


def test_S09_extrair_json_robusto():
    from corte_fala import extrair_json
    assert extrair_json('Claro!\n```json\n{"a": "x}y", "b": {"c": [1]}}\n```\nfim') == {"a": "x}y", "b": {"c": [1]}}
    with pytest.raises(ValueError):
        extrair_json("sem json aqui")


def test_S10_retakes_via_llm_validados(log):
    from corte_fala import CorteFala
    t = _transc()
    c = CorteFala(log)
    assert c.detectar_retakes(t, ClaudeFalso({"retakes": [0, 99, "x"]})) == [0]
    assert c.detectar_retakes(t, ClaudeFalso({"retakes": [0, 1, 2]})) == []     # removeria demais
    assert c.detectar_retakes(t, ClaudeFalso("nao entendi")) == []
    r = c.calcular(t, retakes=[0])
    assert all(i >= 4.0 for i, _ in r.manter)                                   # frase 0 inteira saiu


# ===================================================================== diretor
def _indice(fala, transcritor, log, estilo=None, llm=None):
    from diretor_ia import Indexador, validar_estilo
    return Indexador(log, transcritor, llm).indexar([fala], validar_estilo(estilo or {}), detectar_retakes=False)


def test_S11_indice_unidades_por_frase(fala, transcritor, log):
    ind = _indice(fala, transcritor, log)
    assert [u.id for u in ind.unidades] == ["a1f0", "a1f1", "a1f2"]
    assert "Hum" not in ind.unidades[1].texto or ind.unidades[1].duracao < 2.2   # vicio fora dos trechos
    assert Path(ind.arquivos[0]["folha"]).exists()


def test_S12_estilos_carregam_e_validam():
    from diretor_ia import carregar_estilos
    e = carregar_estilos()
    assert {"youtube_educativo", "reels_dinamico", "depoimento", "podcast_cortes"} <= set(e)
    assert e["reels_dinamico"]["enquadramento"] == "preencher" and e["reels_dinamico"]["resolucao"] == [1080, 1920]


def test_S13_heuristica_respeita_estilo(fala, transcritor, log):
    from diretor_ia import Diretor, validar_estilo
    ind = _indice(fala, transcritor, log)
    d = Diretor(log)
    tudo = d.planejar(ind, validar_estilo({"selecao": "tudo"}))
    assert tudo.unidades == ["a1f0", "a1f1", "a1f2"] and tudo.origem == "heuristica"
    curto = d.planejar(ind, validar_estilo({"selecao": "melhores", "duracao_alvo": 2.5, "gancho_max": 3}))
    assert curto.duracao(ind) <= 2.5 * 1.05 + 1e-6 and curto.unidades
    cont = d.planejar(ind, validar_estilo({"selecao": "continuo", "duracao_alvo": 3.5}))
    ordem = [u.id for u in ind.unidades]
    pos = [ordem.index(u) for u in cont.unidades]
    assert pos == list(range(pos[0], pos[0] + len(pos)))                        # contiguo


def test_S14_diretor_claude_validado(fala, transcritor, log):
    from diretor_ia import Diretor, validar_estilo
    ind = _indice(fala, transcritor, log)
    llm = ClaudeFalso({"titulo": "T", "gancho": "forte", "unidades": ["a1f2", "inventado", "a1f0", "a1f2", "a1f1"],
                       "justificativas": {"a1f2": "fecha bem", "inventado": "x"}})
    p = Diretor(log, llm).planejar(ind, validar_estilo({"duracao_alvo": 4.0}))
    assert p.origem == "claude" and p.unidades[0] == "a1f2"
    assert "inventado" not in p.unidades and len(set(p.unidades)) == len(p.unidades)
    assert p.duracao(ind) <= 4.0 * 1.15 + 1e-6                                    # ajuste de duracao
    blocos = llm.recebido[0]
    img = [b for b in blocos if b.get("type") == "image"][0]
    assert img["source"]["media_type"] == "image/jpeg"
    jpg = Path(fala).with_name("folha_teste.jpg")
    jpg.write_bytes(base64.b64decode(img["source"]["data"]))
    v = probe(jpg)["streams"][0]
    assert max(v["width"], v["height"]) <= 1568                                 # sem reamostragem na API


def test_S15_falha_do_claude_cai_na_heuristica(fala, transcritor, log):
    from diretor_ia import Diretor, validar_estilo
    ind = _indice(fala, transcritor, log)
    p = Diretor(log, ClaudeFalso(RuntimeError("timeout"))).planejar(ind, validar_estilo({}))
    assert p.origem == "heuristica" and "falha do Claude" in p.observacoes and p.unidades


def test_S16_revisor_nota_tecnica_e_visual(fala, transcritor, log, tmp_path):
    from diretor_ia import PlanoEdicao, Revisor, validar_estilo
    ind = _indice(fala, transcritor, log)
    plano = PlanoEdicao("x", ["a1f0", "a1f1", "a1f2"])
    longe = Revisor(log).revisar(fala, plano, ind, validar_estilo({"duracao_alvo": 60}), usar_visao=False)
    assert longe.nota_tecnica <= 7.0 and any("alvo" in p for p in longe.problemas)
    llm = ClaudeFalso({"nota": 9, "criterios": {"ritmo": 9}, "problemas": [], "sugestoes": ["ok"]})
    r = Revisor(log, llm).revisar(fala, plano, ind, validar_estilo({}), usar_visao=True)
    assert r.nota_ia == 9 and abs(r.nota - (0.4 * r.nota_tecnica + 0.6 * 9)) < 0.01


def test_S17_execucao_completa_com_nova_tentativa(fala, transcritor, log, tmp_path):
    from diretor_ia import DiretorIA
    llm = ClaudeFalso(
        {"unidades": ["a1f0", "a1f1", "a1f2"], "titulo": "v1"},                     # plano 1
        {"nota": 2, "problemas": ["gancho fraco"], "sugestoes": ["comecar pelo fim"]},  # revisao 1
        {"unidades": ["a1f2", "a1f0", "a1f1"], "titulo": "v2", "gancho": "agradecimento"},  # plano 2
        {"nota": 9, "problemas": [], "sugestoes": []})                              # revisao 2
    d = DiretorIA(log, renderizador(log), llm, transcritor)
    saida = tmp_path / "final.mp4"
    r = d.executar([fala], {"nota_minima": 7}, saida, brief="teste", max_tentativas=3,
                   detectar_retakes=False)
    assert len(r.versoes) == 2 and r.melhor == 2 and r.versoes[1].revisao.aprovado
    assert saida.exists() and (tmp_path / "final_v1.mp4").exists()
    assert "gancho fraco" in json.dumps(llm.recebido[2], ensure_ascii=False)       # feedback chegou ao diretor
    md = r.relatorio_md.read_text(encoding="utf-8")
    assert "éé" in md and "Hum" in md and "Versao 2" in md and "gancho fraco" in md
    dados = json.loads(r.relatorio_json.read_text(encoding="utf-8"))
    assert dados["versao_escolhida"] == 2 and len(dados["versoes"]) == 2
    d_aud = duracoes(saida)
    assert abs(d_aud["audio"] - r.versoes[1].plano.duracao(d.indice)) < 0.2


def test_S18_sem_fala_usa_cenas(midia, transcritor, log, tmp_path):
    from diretor_ia import DiretorIA
    d = DiretorIA(log, renderizador(log), None, transcritor)
    r = d.executar([midia["duas_cenas"]], {"plano_max": 1.5}, tmp_path / "c.mp4", max_tentativas=1)
    assert all(u.tipo == "cena" for u in d.indice.unidades) and len(d.indice.unidades) >= 3
    assert abs(duracoes(r.final)["video"] - 4.0) < 0.2


# ===================================================================== base
def test_S19_claude_mensagem_multimodal_e_gerar_inalterado(monkeypatch, log):
    base = _base()
    cfg = base.ConfigManager()
    cfg.set_api_key("claude", "sk-x")
    corpos = []

    class Resp:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(base, "requests", type("R", (), {"post": staticmethod(
        lambda url, headers=None, json=None, timeout=None: (corpos.append(json), Resp())[1])}))
    eng = base.ClaudeEngine(cfg, log)
    eng.gerar("oi")
    blocos = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "AA=="}},
              {"type": "text", "text": "descreva"}]
    assert eng.mensagem(blocos, system="s") == "ok"
    assert corpos[0]["messages"][0]["content"] == "oi"              # gerar(): mesmo corpo da v7.7
    assert corpos[1]["messages"][0]["content"] == blocos and corpos[1]["system"] == "s"


@pytest.mark.parametrize("modo", ["ajustar", "preencher", "desfocar"])
def test_S20_enquadramento(midia, tmp_path, log, modo):
    base = _base()
    tl = base.ProjectTimeline(clips=[base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=1, duracao=1)],
                              resolucao=(180, 320), fps=25, enquadramento=modo)
    s = tmp_path / f"{modo}.mp4"
    base.ProfessionalRenderer(log).renderizar(tl, s, base.RenderPreset.DRAFT)
    v = [x for x in probe(s)["streams"] if x["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (180, 320)
    topo = subprocess.run(["ffmpeg", "-v", "error", "-i", str(s), "-frames:v", "1", "-vf", "crop=180:20:0:0",
                           "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    media_topo = sum(topo) / len(topo)
    if modo == "ajustar":
        assert media_topo < 25          # barra preta (comportamento v7.7 preservado)
    else:
        assert media_topo > 25          # imagem ocupa o topo


def test_S21_projeto_salva_enquadramento(tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[], enquadramento="desfocar")
    assert base.timeline_de_dict(base.timeline_para_dict(tl)).enquadramento == "desfocar"
    assert base.timeline_de_dict({"clips": []}).enquadramento == "ajustar"     # projetos v7.7 continuam abrindo


# ===================================================================== UI
def _app(transcritor=None):
    base = _base()
    import v76_patch
    import v78_diretor
    importlib.reload(v76_patch)
    importlib.reload(v78_diretor)
    app = base.VideoBuilderProV7(fake_tk.Tk())
    v76_patch.aplicar_patch(app)
    p = v78_diretor.aplicar_patch_v78(app, transcritor)
    return app, p


def test_S22_ui_21_abas_e_edicao_automatica_sem_chave(fala, transcritor, tmp_path, log):
    app, p = _app(transcritor)
    assert len(app.nb.tabs()) == 21
    p.arquivos = [fala]
    p.estilo.set("YouTube educativo")
    p.preset.set("DRAFT")
    p.editar(str(tmp_path / "ui.mp4"))
    app.ui.aguardar()
    erros = [m for m in fake_tk.mensagens if m[0] == "showerror"]
    assert not erros, erros
    assert (tmp_path / "ui.mp4").exists() and (tmp_path / "ui.diretor.md").exists()
    assert "heuristica" in (tmp_path / "ui.diretor.md").read_text(encoding="utf-8")
    p.enviar_timeline()
    trechos = p.ultimo.versoes[0].plano.clipes(p.diretor.indice)
    assert len(app.clips) == len(trechos) == 4           # frase 0 tem 2 trechos ("éé" removido no meio)
    assert app.clips[0].inicio > 0.9
    assert app.enquadramento_var.get() == "ajustar" and app.audio_standard.get() == "YouTube"
    tl = app._montar_timeline()
    assert tl.resolucao == (1920, 1080)


def test_S23_ui_analisar_mostra_cortes(fala, transcritor, log):
    app, p = _app(transcritor)
    p.arquivos = [fala]
    p.analisar()
    app.ui.aguardar()
    texto = p.saida_log.get()
    assert '"éé"' in texto and '"Hum"' in texto and "unidades prontas" in texto
