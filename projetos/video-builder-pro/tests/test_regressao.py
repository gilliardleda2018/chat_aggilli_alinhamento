"""Testes de REGRESSAO: comportamento que ja funcionava na v7.6.

Estes testes passam na versao original (commit 85c9ea4) e devem continuar
passando depois de cada correcao. Se algum falhar, a correcao regrediu.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from conftest import duracoes, probe


@pytest.fixture(autouse=True)
def home_isolado(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()


# ------------------------------------------------------------------ modulos
def test_lut_embutido_preserva_duracao_e_audio(midia, tmp_path, log):
    from luts_manager import LUTManager
    saida = tmp_path / "lut.mp4"
    LUTManager(log).aplicar_lut(midia["hd_audio"], "Cinematic", saida, 1.0)
    d = duracoes(saida)
    assert abs(d["video"] - 3.0) < 0.2
    assert "audio" in d


def test_lut_cube_intensidade_total(midia, tmp_path, log):
    from luts_manager import LUTManager
    lm = LUTManager(log)
    lm.adicionar_lut_personalizada("ident", midia["cube"])
    saida = tmp_path / "cube.mp4"
    lm.aplicar_lut(midia["hd_audio"], "ident", saida, 1.0)
    assert saida.exists() and saida.stat().st_size > 0


def test_listas_de_luts_e_transicoes(log):
    from luts_manager import LUTManager
    from transitions_gl import GLTransitionsEngine
    assert len(LUTManager(log).listar_luts()) >= 15
    assert len(GLTransitionsEngine(log).listar_transicoes()) >= 46


def test_detectar_silencios(midia, log):
    from auto_editor import AutoEditor
    sil = AutoEditor(log).detectar_silencios(midia["com_silencio"], -35.0, 0.5)
    assert len(sil) == 1
    ini, fim = sil[0]
    assert 1.8 <= ini <= 2.3 and 3.8 <= fim <= 4.3


def test_remover_silencios_encurta_video(midia, tmp_path, log):
    from auto_editor import AutoEditor
    saida = tmp_path / "sem_silencio.mp4"
    AutoEditor(log).remover_silencios_simples(midia["com_silencio"], saida, -35.0)
    assert duracoes(saida)["audio"] < 5.0


def test_transicao_nativa_fade(midia, tmp_path, log):
    from transitions_gl import GLTransitionsEngine, GLTransition
    saida = tmp_path / "fade.mp4"
    GLTransitionsEngine(log).renderizar_transicao(
        midia["hd_audio"], midia["hd_audio"], GLTransition("fade", 1.0), saida)
    assert abs(duracoes(saida)["video"] - 5.0) < 0.3


def test_vertical_centro_sem_blur(midia, tmp_path, log):
    from vertical_converter import VerticalConverter, CropMode
    saida = tmp_path / "vert.mp4"
    VerticalConverter(log).converter(midia["hd_audio"], saida, CropMode.CENTER,
                                     adicionar_blur_fundo=False)
    v = [s for s in probe(saida)["streams"] if s["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1080, 1920)


def test_srt_para_vtt(midia, tmp_path, log):
    from subtitles_ai import SubtitlesAI
    vtt = tmp_path / "x.vtt"
    SubtitlesAI(log).converter_srt_para_vtt(midia["srt"], vtt)
    texto = vtt.read_text(encoding="utf-8")
    assert texto.startswith("WEBVTT") and "00:00:02.000" in texto


# ------------------------------------------------------------------ base
def _base():
    import importlib
    import video_builder_pro_v7_suite as base
    return importlib.reload(base)


def test_config_roundtrip_chave(log):
    base = _base()
    cfg = base.ConfigManager()
    cfg.set_api_key("claude", "sk-ant-teste")
    assert base.ConfigManager().get_api_key("claude") == "sk-ant-teste"


def test_claude_engine_monta_requisicao(monkeypatch, log):
    base = _base()
    cfg = base.ConfigManager()
    cfg.set_api_key("claude", "sk-ant-teste")
    capturado = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": "ok"}]}

    class Req:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            capturado.update(url=url, headers=headers, body=json)
            return Resp()

    monkeypatch.setattr(base, "requests", Req)
    assert base.ClaudeEngine(cfg, log).titulos("tema") == "ok"
    assert capturado["headers"]["x-api-key"] == "sk-ant-teste"
    assert capturado["body"]["messages"][0]["role"] == "user"


def test_qc_resolucao_codec_md5(midia, log):
    import hashlib
    base = _base()
    r = base.QCEngine(log).analisar_video(midia["hd_audio"])
    assert r.resolution == "1280x720"
    assert r.codec == "h264"
    assert r.checksum_md5 == hashlib.md5(midia["hd_audio"].read_bytes()).hexdigest()


def test_render_clipes_homogeneos(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3, nome="a"),
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3, nome="b"),
    ], projeto_nome="t", fps=25)
    saida = tmp_path / "render.mp4"
    base.ProfessionalRenderer(log).renderizar(tl, saida, base.RenderPreset.DRAFT)
    d = duracoes(saida)
    assert abs(d["video"] - 6.0) < 0.3 and abs(d["audio"] - 6.0) < 0.3


def test_exportar_edl(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3, nome="a"),
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3, nome="b"),
    ], projeto_nome="proj", fps=25)
    xml = tmp_path / "edl.xml"
    base.ProfessionalRenderer(log).exportar_edl(tl, xml)
    raiz = ET.parse(xml).getroot()
    assert raiz.tag == "xmeml"
    assert len(raiz.findall(".//clipitem")) == 2


# ------------------------------------------------------------------ UI (stub)
def test_ui_monta_20_abas(log):
    import fake_tk
    base = _base()
    root = fake_tk.Tk()
    app = base.VideoBuilderProV7(root)
    assert len(app.nb.tabs()) == 8
    import importlib
    import v76_patch
    importlib.reload(v76_patch)
    v76_patch.aplicar_patch(app)
    assert len(app.nb.tabs()) == 20


def test_formatos_de_tempo_legenda(log):
    import v76_patch
    p = v76_patch.V73Patch.__new__(v76_patch.V73Patch)
    assert p._format_timestamp(3661.5) == "01:01:01,500"
    assert p._format_ass_time(61.25) == "0:01:01.25"
