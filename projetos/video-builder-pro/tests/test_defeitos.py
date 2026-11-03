"""Testes dos DEFEITOS da auditoria v7.6 (03/11/2026).

Cada teste reproduz um defeito documentado em CHANGELOG.md. Na v7.6
(commit 85c9ea4) eles falham; na v7.7 devem passar. O ID [Dxx] liga o
teste a linha correspondente do CHANGELOG.
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
from conftest import duracoes, probe


@pytest.fixture(autouse=True)
def home_isolado(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("SUDO_USER", raising=False)
    fake_tk.resetar()
    return home


def _base():
    import video_builder_pro_v7_suite as base
    return importlib.reload(base)


def _app_com_patch():
    base = _base()
    import v76_patch
    importlib.reload(v76_patch)
    app = base.VideoBuilderProV7(fake_tk.Tk())
    patch = v76_patch.aplicar_patch(app)
    return base, app, patch


def _rodar(app):
    app.ui.aguardar()


def _erros():
    return [m for m in fake_tk.mensagens if m[0] == "showerror"]


# ====================================================================== MODULOS
def test_D01_detectar_cenas_retorna_dicts(midia, log):
    from auto_editor import AutoEditor
    cenas = AutoEditor(log).detectar_cenas(midia["duas_cenas"])
    assert len(cenas) == 2
    assert abs(cenas[0]["fim"] - 2.0) < 0.1 and abs(cenas[1]["inicio"] - 2.0) < 0.1


def test_D02_vertical_aceita_string_e_blur_por_nome(midia, tmp_path, log):
    from vertical_converter import VerticalConverter
    s = tmp_path / "v.mp4"
    VerticalConverter(log).converter(midia["hd_audio"], s, "center", adicionar_blur_fundo=True)
    v = [x for x in probe(s)["streams"] if x["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1080, 1920)


def test_D03_vertical_blur_visivel(midia, tmp_path, log):
    """Com blur, o topo do quadro deve ser o fundo desfocado (nao o video recortado)."""
    from vertical_converter import VerticalConverter
    vc = VerticalConverter(log)
    filtro = vc._gerar_filtro_com_blur(None, (1080, 1920), 1280, 720)
    assert "force_original_aspect_ratio=decrease" in filtro  # video inteiro, nao recortado


def test_D04_vertical_video_sem_audio(midia, tmp_path, log):
    from vertical_converter import VerticalConverter
    s = tmp_path / "v.mp4"
    VerticalConverter(log).converter(midia["sd_mudo"], s, "center", adicionar_blur_fundo=False)
    assert "audio" not in duracoes(s)


def test_D05_queimar_legendas_existe_e_aceita_caminho_hostil(midia, tmp_path, log):
    from subtitles_ai import SubtitlesAI
    pasta = tmp_path / "C:dir, it's [x]"
    pasta.mkdir()
    srt = pasta / "leg's.srt"
    srt.write_text(midia["srt"].read_text(encoding="utf-8"), encoding="utf-8")
    s = tmp_path / "q.mp4"
    SubtitlesAI(log).queimar_legendas(midia["hd_audio"], srt, s)
    assert s.exists() and abs(duracoes(s)["video"] - 3.0) < 0.2


def test_D06_legendas_salvas_no_destino_escolhido(midia, tmp_path, log, monkeypatch):
    """SRT ia para a pasta temporaria (apagada) com nome fixo."""
    import subtitles_ai
    sub = subtitles_ai.SubtitlesAI(log)

    def whisper_falso(cmd, log=None, timeout=None):
        if "--output_dir" in cmd:
            out = Path(cmd[cmd.index("--output_dir") + 1])
            (out / "audio.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    monkeypatch.setattr(subtitles_ai, "executar", whisper_falso)
    sub._cmd_whisper, sub.whisper_disponivel = ["whisper"], True
    destino = tmp_path / "final" / "minha.srt"
    r = sub.gerar_legendas(midia["hd_audio"], "pt", "base", "srt", saida=destino)
    assert r == destino and destino.exists()
    assert not str(r).startswith(str(sub.temp_dir))


def test_D07_lut_intensidade_interpola_do_neutro(log):
    from luts_manager import LUTManager
    f = LUTManager(log).obter_filtro_ffmpeg("cinematic", 0.5)
    assert "contrast=1.0750" in f        # 1 + (1.15 - 1) * 0.5 (antes 0.575)
    assert "saturation=0.9250" in f
    assert LUTManager(log).obter_filtro_ffmpeg("cinematic", 0.0) == "null"


def test_D08_lut_cube_intensidade_parcial_e_caminho_hostil(midia, tmp_path, log):
    from luts_manager import LUTManager
    pasta = tmp_path / "luts: it's"
    pasta.mkdir()
    cube = pasta / "l'ut.cube"
    cube.write_text(midia["cube"].read_text(), encoding="utf-8")
    lm = LUTManager(log)
    lm.adicionar_lut_personalizada("x", cube)
    s = tmp_path / "o.mp4"
    lm.aplicar_lut(midia["sd_mudo"], "x", s, 0.5)
    assert s.exists()


@pytest.mark.parametrize("tid", ["gl_heart", "gl_Diamond", "gl_cube", "gl_Swirl", "gl_StarWipe"])
def test_D09_transicoes_gl_validas_entre_formatos_diferentes(midia, tmp_path, log, tid):
    from transitions_gl import GLTransitionsEngine, GLTransition, EasingType
    s = tmp_path / f"{tid}.mp4"
    GLTransitionsEngine(log).renderizar_transicao(midia["hd_audio"], midia["sd_mudo"],
                                                  GLTransition(tid, 1.0, EasingType.CUBIC), s)
    d = duracoes(s)
    assert abs(d["video"] - 5.0) < 0.3 and abs(d["audio"] - 5.0) < 0.3  # audio preservado


def test_D10_todas_as_46_transicoes_geram_filtro_valido(tmp_path, log):
    from transitions_gl import GLTransitionsEngine, GLTransition
    g = GLTransitionsEngine(log)
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    for cor, arq in (("red", a), ("blue", b)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color={cor}:s=64x64:r=10:d=1",
                        str(arq)], check=True)
    for tid in g.TRANSICOES_GL:
        g.renderizar_transicao(a, b, GLTransition(tid, 0.5), tmp_path / "t.mp4")


def test_D11_easing_progresso_de_A_para_B(tmp_path, log):
    """No xfade P vai de 1 a 0: a transicao deve COMECAR em A e TERMINAR em B."""
    from transitions_gl import GLTransitionsEngine, GLTransition, EasingType
    a, b, s = tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "s.mp4"
    for cor, arq in (("red", a), ("blue", b)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color={cor}:s=32x32:r=10:d=2",
                        str(arq)], check=True)
    GLTransitionsEngine(log).renderizar_transicao(a, b, GLTransition("gl_Diamond", 1.0, EasingType.LINEAR), s)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(s), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    n = 32 * 32 * 3
    quadros = [raw[i:i + n] for i in range(0, len(raw), n)]
    vermelho = [sum(q[0::3]) / (32 * 32) for q in quadros]
    assert vermelho[10] > 200          # inicio da transicao: ainda A (vermelho)
    assert vermelho[19] < 60           # fim da transicao: B (azul)


def test_D12_multiplas_transicoes_offset_acumulado(midia, tmp_path, log):
    from transitions_gl import GLTransitionsEngine, GLTransition
    s = tmp_path / "m.mp4"
    GLTransitionsEngine(log).renderizar_multiplas_transicoes(
        [midia["hd_audio"]] * 3, [GLTransition("fade", 1.0)] * 2, s)
    assert abs(duracoes(s)["video"] - 7.0) < 0.3   # 3x3 - 2x1


def test_D13_gpu_sem_hardware_nao_e_detectada(log):
    from gpu_encoder import GPUEncoder, GPUType
    g = GPUEncoder(log)
    falso = [e for e in g.gpus_detectadas if e.tipo != GPUType.CPU and not g._testar_encoder(e.encoder)]
    assert falso == []


def test_D14_gpu_comando_usa_qualidade_constante(log):
    from gpu_encoder import GPUEncoder, GPUInfo, GPUType, EncoderPreset
    g = GPUEncoder(log)
    cmd = g.gerar_comando_ffmpeg(GPUInfo(GPUType.NVIDIA, "x", "h264_nvenc", True),
                                 EncoderPreset("q", "h264_nvenc", "p7", "18", ""), Path("a"), Path("b"),
                                 resolucao=(1280, 720))
    assert "-cq" in cmd and "18" in cmd and "-hwaccel_output_format" not in cmd
    assert "18M" not in cmd


def test_D15_downloader_windows_sem_home_unix(tmp_path, log):
    import definitive_downloader as dd
    home = tmp_path / "winhome"
    (home / "AppData/Roaming/Mozilla/Firefox").mkdir(parents=True)
    assert dd._detectar_browser(home, "nt") == ("firefox", str(home / "AppData/Roaming/Mozilla/Firefox"))


def test_D16_downloader_nao_usa_perfil_de_outro_usuario(tmp_path, monkeypatch, log, home_isolado):
    import definitive_downloader as dd
    outro = tmp_path / "outro_usuario" / ".mozilla" / "firefox"
    outro.mkdir(parents=True)
    assert dd._detectar_browser(home_isolado, "posix") == (None, None)


@pytest.mark.skipif(os.name == "nt", reason="permissoes POSIX")
def test_D17_cookies_644_vira_600(log, home_isolado, monkeypatch):
    import definitive_downloader as dd
    importlib.reload(dd)
    cfg = home_isolado / ".video_builder_pro"
    cfg.mkdir()
    ck = cfg / "cookies.txt"
    ck.write_text("# Netscape HTTP Cookie File\n")
    os.chmod(ck, 0o644)
    monkeypatch.setattr(dd, "YT_DLP_OK", True)
    monkeypatch.setattr(dd, "yt_dlp", types.SimpleNamespace(version=types.SimpleNamespace(__version__="x")))
    d = dd.DefinitiveDownloader(log)
    assert stat.S_IMODE(ck.stat().st_mode) == 0o600
    assert d._opcoes_base()["cookiefile"] == str(ck)
    assert "cookiesfrombrowser" not in d._opcoes_base()


def test_D18_modulos_ausentes_agora_existem(log):
    for mod in ("upscaler", "stems_separator", "face_restore", "auto_suite"):
        importlib.import_module(mod)


def test_D19_upscale_classico_sem_realesrgan(midia, tmp_path, log):
    import upscaler
    u = upscaler.VideoUpscaler(log)
    u.realesrgan_disponivel = False
    s = tmp_path / "up.mp4"
    u.upscale(midia["sd_mudo"], s, "2x")
    v = [x for x in probe(s)["streams"] if x["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1280, 960)


def test_D20_upscale_ia_orquestracao(midia, tmp_path, log, monkeypatch):
    """Simula o binario realesrgan (copia os PNGs ampliados) e valida o pipeline."""
    import upscaler
    falso = tmp_path / "realesrgan-falso.py"
    falso.write_text(
        "import sys,subprocess,pathlib\n"
        "a=sys.argv; i=pathlib.Path(a[a.index('-i')+1]); o=pathlib.Path(a[a.index('-o')+1])\n"
        "for p in sorted(i.glob('*.png')):\n"
        "    subprocess.run(['ffmpeg','-v','error','-y','-i',str(p),'-vf','scale=iw*4:ih*4',str(o/p.name)],check=True)\n")
    u = upscaler.VideoUpscaler(log)
    u.binario, u.realesrgan_disponivel = sys.executable, True
    real_exec = upscaler.executar
    monkeypatch.setattr(upscaler, "executar",
                        lambda cmd, log=None: real_exec([cmd[0], str(falso), *cmd[1:]] if cmd[0] == sys.executable else cmd, log))
    s = tmp_path / "ia.mp4"
    u.upscale(midia["sd_mudo"], s, "2x")
    v = [x for x in probe(s)["streams"] if x["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1280, 960)


def test_D21_stems_orquestracao_demucs(midia, tmp_path, log, monkeypatch):
    import stems_separator
    sep = stems_separator.StemSeparator(log)
    sep._cmd, sep.demucs_disponivel = ["demucs"], True
    real_exec = stems_separator.executar

    def exec_falso(cmd, log=None, timeout=None):
        if cmd[0] == "demucs":
            wav = Path(cmd[-1])
            out = Path(cmd[cmd.index("-o") + 1]) / cmd[cmd.index("-n") + 1] / wav.stem
            out.mkdir(parents=True)
            for n in (("vocals", "no_vocals") if "--two-stems" in cmd else ("vocals", "drums", "bass", "other")):
                (out / f"{n}.wav").write_bytes(wav.read_bytes())
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_exec(cmd, log)
    monkeypatch.setattr(stems_separator, "executar", exec_falso)
    v, i = tmp_path / "v.wav", tmp_path / "i.wav"
    sep.separar_vocals_instrumental(midia["hd_audio"], v, i)
    assert v.exists() and i.exists()
    assert len(sep.separar_stems(midia["hd_audio"], tmp_path / "4")) == 4


def test_D22_face_restore_pipeline_com_gfpgan_simulado(midia, tmp_path, log, monkeypatch):
    pytest.importorskip("numpy")

    class GFPGANerFalso:
        def __init__(self, **kw):
            pass

        def enhance(self, img, **kw):
            return None, None, img[:, :, ::-1]
    monkeypatch.setitem(sys.modules, "gfpgan", types.SimpleNamespace(GFPGANer=GFPGANerFalso))
    import face_restore
    importlib.reload(face_restore)
    fr = face_restore.FaceRestorer(log)
    monkeypatch.setattr(face_restore, "URL_MODELO", "falso")
    s = tmp_path / "f.mp4"
    fr.restaurar_video(midia["hd_audio"], s, usar_gpu=True)
    d = duracoes(s)
    assert abs(d["video"] - 3.0) < 0.2 and "audio" in d


def test_D23_auto_suite_funciona(midia, tmp_path, log):
    from auto_suite import AutoEditorAI, AutoColorAI, AutoAudioAI, AutoFormatAI
    s1 = tmp_path / "ed.mp4"
    AutoEditorAI(log).editar_automatico(midia["com_silencio"], s1,
                                        {"transicao_duracao": 0.3, "manter_minimo": 0.5, "margem": 0.1})
    assert duracoes(s1)["video"] < 5.6
    s2 = tmp_path / "cor.mp4"
    AutoColorAI(log).aplicar_color_auto(midia["hd_audio"], s2)
    assert s2.exists()
    s3 = tmp_path / "mix.mp4"
    AutoAudioAI(log).mixar_automatico(midia["hd_audio"], s3, "YouTube")
    from ffmpeg_utils import medir_loudness
    assert abs(medir_loudness(s3)["integrado"] - (-14)) < 1.5
    saidas = AutoFormatAI(log).converter_todas_plataformas(midia["sd_mudo"], tmp_path / "plat")
    assert len(saidas) == 4


# ====================================================================== BASE
def test_D24_render_clipes_heterogeneos_sincronizado(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3),
        base.ClipTimeline(arquivo=midia["sd_mudo"], inicio=0, fim=3, duracao=3),
    ], fps=25, resolucao=(1280, 720))
    s = tmp_path / "r.mp4"
    base.ProfessionalRenderer(log).renderizar(tl, s, base.RenderPreset.DRAFT)
    d = duracoes(s)
    assert abs(d["video"] - 6.0) < 0.15 and abs(d["audio"] - 6.0) < 0.15   # antes 7,24 x 3,04
    v = [x for x in probe(s)["streams"] if x["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1280, 720)


def test_D25_render_respeita_in_out_e_velocidade(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=1.0, fim=2.5, duracao=1.5),
        base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3, speed=2.0),
    ], fps=25, resolucao=(640, 360))
    s = tmp_path / "r.mp4"
    base.ProfessionalRenderer(log).renderizar(tl, s, base.RenderPreset.DRAFT)
    assert abs(duracoes(s)["video"] - 3.0) < 0.15   # 1.5 + 3/2


def test_D26_render_nao_cria_proxies(midia, tmp_path, log):
    base = _base()
    r = base.ProfessionalRenderer(log)
    tl = base.ProjectTimeline(clips=[base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=1, duracao=1)],
                              resolucao=(320, 180))
    r.renderizar(tl, tmp_path / "x.mp4", base.RenderPreset.DRAFT)
    assert list(r.automation.temp_dir.glob("proxy_*")) == []


def test_D27_render_aplica_loudness_do_padrao(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3)],
                              resolucao=(320, 180), padrao_audio="YouTube", normalizar_audio=True)
    r = base.ProfessionalRenderer(log)
    r.renderizar(tl, tmp_path / "x.mp4", base.RenderPreset.DRAFT)
    assert abs(r.ultimo_qc.loudness_integrated - (-14)) < 1.0 and r.ultimo_qc.aprovado, r.ultimo_qc.problemas
    d = duracoes(tmp_path / "x.mp4")
    assert abs(d["audio"] - d["video"]) < 0.05        # loudnorm nao pode deixar cauda


def test_D28_render_look_transicao_trilha_eq(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(
        clips=[base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3),
               base.ClipTimeline(arquivo=midia["sd_mudo"], inicio=0, fim=3, duracao=3)],
        resolucao=(640, 360), look="Cinematic", look_intensidade=0.5, transicao="gl_heart",
        duracao_transicao=0.5, eq={"low": 3, "mid": 0, "high": -2},
        music=base.MusicTrack(midia["com_silencio"], volume=0.4, ducking=True, loop=True))
    s = tmp_path / "x.mp4"
    base.ProfessionalRenderer(log).renderizar(tl, s, base.RenderPreset.DRAFT)
    d = duracoes(s)
    assert abs(d["video"] - 5.5) < 0.2 and abs(d["audio"] - 5.5) < 0.2


def test_D29_speed_ramp_real(midia, tmp_path, log):
    base = _base()
    tl = base.ProjectTimeline(clips=[base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=3, duracao=3,
                                                       rampa=[(0, 1), (1, 0.5), (2, 2)])],
                              resolucao=(320, 180))
    esperado = 1 + 1 / 0.5 + 1 / 2   # 3.5 s
    assert abs(tl.clips[0].duracao_saida() - esperado) < 1e-6
    s = tmp_path / "x.mp4"
    base.ProfessionalRenderer(log).renderizar(tl, s, base.RenderPreset.DRAFT)
    assert abs(duracoes(s)["video"] - esperado) < 0.15


def test_D30_qc_sem_audio_reprova(midia, log):
    base = _base()
    r = base.QCEngine(log).analisar_video(midia["sd_mudo"])
    assert not r.aprovado and any("audio" in p.lower() for p in r.problemas)


def test_D31_qc_metricas_reais(midia, log):
    base = _base()
    r = base.QCEngine(log).analisar_video(midia["com_preto"])
    assert r.true_peak is not None and r.true_peak < -10      # antes -2.0 fixo
    assert r.loudness_range is not None
    assert r.black_frames >= 1                                 # antes 0 fixo
    assert r.bitrate_avg > 0 and r.bitrate_max >= r.bitrate_avg * 0.5


def test_D32_qc_alvo_segue_padrao(midia, tmp_path, log):
    base = _base()
    from ffmpeg_utils import normalizar_loudness
    yt = tmp_path / "yt.mp4"
    normalizar_loudness(midia["hd_audio"], yt, -14, -1)
    assert base.QCEngine(log).analisar_video(yt, "YouTube").aprovado
    assert not base.QCEngine(log).analisar_video(yt, "EBU R128").aprovado


def test_D33_qc_relatorio_pdf(midia, tmp_path, log):
    base = _base()
    q = base.QCEngine(log)
    pdf = q.gerar_relatorio_pdf(q.analisar_video(midia["hd_audio"]), tmp_path / "qc.pdf")
    dados = pdf.read_bytes()
    assert dados.startswith(b"%PDF-1.4") and dados.rstrip().endswith(b"%%EOF") and b"RELATORIO DE QC" in dados


def test_D34_luminosidade_e_match_reais(midia, log):
    base = _base()
    c = base.ColorGradingEngine(log)
    escuro = c._analisar_luminosidade(midia["duas_cenas"])["media_ire"]
    claro = c._analisar_luminosidade(midia["hd_audio"])["media_ire"]
    assert escuro != claro                                       # antes 45.0 fixo
    aj = c.calcular_match(midia["hd_audio"], midia["duas_cenas"])
    assert aj["brightness"] != 0


def test_D35_multicam_sincroniza_por_audio(midia, tmp_path, log):
    base = _base()
    atrasado = tmp_path / "cam2.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=gray:s=160x90:r=25:d=6",
                    "-i", str(midia["com_silencio"]), "-filter_complex",
                    "[1:a]adelay=700|700,apad[a]", "-map", "0:v", "-map", "[a]", "-t", "6", "-shortest",
                    str(atrasado)], check=True)
    ed = base.SeniorEditorEngine(log)
    lag = ed._sincronizar_audio(midia["com_silencio"], atrasado)
    assert abs(lag - 0.7) < 0.05
    clips = ed.criar_multicam([midia["com_silencio"], atrasado])
    assert abs(clips[1].inicio - 0.7) < 0.05 and clips[0].inicio == 0


def test_D36_ripple_e_slide_corretos(log):
    base = _base()
    C = base.ClipTimeline
    tl = base.ProjectTimeline(clips=[C(Path("a"), 0, 4, 4, nome="a"), C(Path("b"), 0, 4, 4, nome="b"),
                                     C(Path("c"), 0, 4, 4, nome="c")])
    ed = base.SeniorEditorEngine(log)
    ed.ripple_edit(tl, 5.0)                         # remove 'b' (4..8)
    assert [c.nome for c in tl.clips] == ["a", "c"] and tl.duracao_total == 8
    tl2 = base.ProjectTimeline(clips=[C(Path("a"), 0, 4, 4, nome="a"), C(Path("b"), 0, 4, 4, nome="b")])
    ed.ripple_edit(tl2, 3.0, 2.0)                   # remove 3..5
    assert [(c.inicio, c.fim) for c in tl2.clips] == [(0, 3), (1.0, 4)]
    tl3 = base.ProjectTimeline(clips=[C(Path("a"), 0, 4, 4, duracao_fonte=10), C(Path("b"), 0, 4, 4),
                                      C(Path("c"), 2, 6, 4)])
    ed.slide_edit(tl3, 1, 1.0)
    assert tl3.clips[0].fim == 5 and tl3.clips[2].inicio == 3


def test_D37_edl_com_in_out_e_uri(midia, tmp_path, log):
    import xml.etree.ElementTree as ET
    base = _base()
    tl = base.ProjectTimeline(clips=[base.ClipTimeline(arquivo=midia["sd_mudo"], inicio=1, fim=2, duracao=1)], fps=25)
    xml = tmp_path / "e.xml"
    base.VideoAutomationEngine(log).exportar_edl_xml(tl, xml)
    item = ET.parse(xml).getroot().find(".//clipitem")
    assert item.find("in").text == "25" and item.find("out").text == "50"
    url = item.find("file/pathurl").text
    assert url.startswith("file:///") and "%20" in url and "'" not in url.replace("%27", "")


def test_D38_fila_processa_de_verdade(midia, tmp_path, log):
    base = _base()
    r = base.ProfessionalRenderer(log)
    tl = base.ProjectTimeline(clips=[base.ClipTimeline(arquivo=midia["hd_audio"], inicio=0, fim=1, duracao=1)],
                              resolucao=(320, 180))
    for n in (1, 2):
        r.automation.adicionar_a_fila({"nome": f"p{n}", "saida": str(tmp_path / f"p{n}.mp4"), "preset": "DRAFT",
                                       "timeline": base.timeline_para_dict(tl)})
    res = r.automation.processar_fila(r.renderizar)
    assert [s for _, s, _ in res] == [True, True] and (tmp_path / "p2.mp4").exists()


@pytest.mark.skipif(os.name == "nt", reason="permissoes POSIX")
def test_D39_config_600_e_keyring(log, home_isolado, monkeypatch):
    base = _base()
    cfg = base.ConfigManager()
    cfg.set_api_key("claude", "sk-teste")
    assert stat.S_IMODE(cfg.config_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(cfg.config_dir.stat().st_mode) == 0o700
    cofre = {}

    class Backend:
        pass
    kr = types.SimpleNamespace(get_keyring=lambda: Backend(),
                               set_password=lambda s, u, p: cofre.__setitem__((s, u), p),
                               get_password=lambda s, u: cofre.get((s, u)))
    monkeypatch.setitem(sys.modules, "keyring", kr)
    cfg.set_api_key("claude", "sk-no-cofre")
    assert cofre[("video-builder-pro", "claude")] == "sk-no-cofre"
    assert "claude" not in json.loads(cfg.config_file.read_text()).get("api_keys", {})
    assert base.ConfigManager().get_api_key("claude") == "sk-no-cofre"


def test_D40_logging_em_arquivo(home_isolado, log):
    import ffmpeg_utils
    lg = ffmpeg_utils.obter_logger()          # o logger e global: reinicia para o HOME deste teste
    for h in list(lg.handlers):
        lg.removeHandler(h)
    ffmpeg_utils._LOGGER_PRONTO = False
    from ffmpeg_utils import FFmpegErro, executar, obter_logger
    with pytest.raises(FFmpegErro):
        executar(["ffmpeg", "-v", "error", "-i", "/nao/existe.mp4", "-f", "null", "-"])
    for h in obter_logger().handlers:
        h.flush()
    logs = list((Path.home() / ".video_builder_pro" / "logs").glob("*.log"))
    assert logs and "falhou" in logs[0].read_text(encoding="utf-8")


# ====================================================================== UI (stub Tk)
def test_D41_log_thread_safe(log):
    import threading
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    antes = app.log_text.get()
    t = threading.Thread(target=lambda: app.log("de outra thread"))
    t.start()
    t.join()
    assert app.log_text.get() == antes          # widget intocado pela thread
    app.ui.aguardar()
    assert "de outra thread" in app.log_text.get()


def test_D42_projeto_salvar_e_abrir(midia, tmp_path, log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    fake_tk.responder("askopenfilenames", (str(midia["hd_audio"]), str(midia["sd_mudo"])))
    app.importar_midia()
    app.clips[0].inicio, app.clips[0].fim = 0.5, 2.0
    app.aplicar_lut("Warm")
    app.aplicar_padrao_audio("YouTube")
    arq = tmp_path / "p.vbp.json"
    app.salvar_projeto(caminho=arq)
    app2 = base.VideoBuilderProV7(fake_tk.Tk())
    app2.abrir_projeto(arq)
    assert [c.nome for c in app2.clips] == [c.nome for c in app.clips]
    assert app2.clips[0].inicio == 0.5 and app2.look_var.get() == "Warm"
    assert app2.audio_standard.get() == "YouTube"


def test_D43_render_pela_ui_aplica_escolhas(midia, tmp_path, log):
    base = _base()
    app = base.VideoBuilderProV7(fake_tk.Tk())
    fake_tk.responder("askopenfilenames", (str(midia["hd_audio"]),))
    app.importar_midia()
    app.resolucao_var.set("320x180")
    app.preset_var.set("DRAFT")
    app.aplicar_padrao_audio("YouTube")
    s = tmp_path / "ui.mp4"
    app.renderizar(str(s))
    _rodar(app)
    assert not _erros(), _erros()
    assert app.qc_report and abs(app.qc_report.loudness_integrated + 14) < 1.0


def test_D44_chave_nao_volta_para_o_campo(log):
    base = _base()
    base.ConfigManager().set_api_key("claude", "sk-secreta")
    app = base.VideoBuilderProV7(fake_tk.Tk())
    assert app.api_key_entry.get() == ""


def test_D45_patch_detectar_cenas_sem_crash(midia, log):
    base, app, patch = _app_com_patch()
    fake_tk.responder("askopenfilename", str(midia["duas_cenas"]))
    patch.detectar_cenas()
    _rodar(app)
    assert not _erros(), _erros()
    assert "Cena 2" in patch.auto_log.get()


def test_D46_patch_vertical_e_queimar_sem_crash(midia, tmp_path, log):
    base, app, patch = _app_com_patch()
    fake_tk.responder("askopenfilename", str(midia["hd_audio"]), str(midia["hd_audio"]), str(midia["srt"]))
    fake_tk.responder("asksaveasfilename", str(tmp_path / "v.mp4"), str(tmp_path / "q.mp4"))
    patch.vertical_modo.set("smart")
    patch.converter_vertical()
    patch.queimar_legendas()
    _rodar(app)
    assert not _erros(), _erros()
    assert (tmp_path / "v.mp4").exists() and (tmp_path / "q.mp4").exists()


def test_D47_patch_whisperx_usa_cpu_sem_cuda(log, monkeypatch):
    base, app, patch = _app_com_patch()
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False)))
    assert patch._cuda() is False


def test_D48_patch_suite_sem_moviepy_pydub(midia, tmp_path, log):
    """Speed, trim, analise e normalizacao funcionam so com FFmpeg."""
    base, app, patch = _app_com_patch()
    fake_tk.responder("askopenfilename", str(midia["hd_audio"]), str(midia["hd_audio"]),
                      str(midia["hd_audio"]), str(midia["hd_audio"]))
    fake_tk.responder("askfloat", 2.0, 0.5, 2.0)
    fake_tk.responder("asksaveasfilename", str(tmp_path / "speed.mp4"), str(tmp_path / "trim.mp4"),
                      str(tmp_path / "norm.mp4"))
    patch.speed_ramp_moviepy()
    _rodar(app)
    patch.trim_moviepy()
    _rodar(app)
    patch.analisar_audio_pydub()
    _rodar(app)
    patch.auto_audio_padrao.set("YouTube")
    patch.normalizar_audio_pydub()
    _rodar(app)
    assert not _erros(), _erros()
    assert abs(duracoes(tmp_path / "speed.mp4")["video"] - 1.5) < 0.15
    assert abs(duracoes(tmp_path / "trim.mp4")["video"] - 1.5) < 0.15
    d = duracoes(tmp_path / "norm.mp4")
    assert "video" in d and "audio" in d                       # antes o video era descartado
    assert "LUFS" in patch.auto_suite_log.get()


def test_D49_patch_mixagem_e_transicao_gl_ligadas(midia, tmp_path, log):
    base, app, patch = _app_com_patch()
    fake_tk.responder("askopenfilename", str(midia["hd_audio"]), str(midia["hd_audio"]), str(midia["sd_mudo"]))
    fake_tk.responder("asksaveasfilename", str(tmp_path / "mix.mp4"), str(tmp_path / "gl.mp4"))
    patch.mixagem_automatica()
    _rodar(app)
    patch.gl_lista.selection_set(patch._gl_ids.index("gl_heart"))
    patch.aplicar_transicao_gl()
    _rodar(app)
    assert not _erros(), _erros()
    assert (tmp_path / "mix.mp4").exists() and (tmp_path / "gl.mp4").exists()
    patch.usar_transicao_no_projeto()
    assert app._montar_timeline().transicao == "gl_heart"
