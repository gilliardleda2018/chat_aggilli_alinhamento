import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "modules"))

from transitions_gl import GLTransitionsEngine
from luts_manager import LUTManager
from auto_editor import AutoEditor
from subtitles_ai import SubtitlesAI
from vertical_converter import VerticalConverter
from gpu_encoder import GPUEncoder

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading


def aplicar_patch(app):
    patch = V73Patch(app)
    return patch


class V73Patch:
    def __init__(self, app):
        self.app = app
        self.log = app.log

        self.gl_trans = GLTransitionsEngine(self.log)
        self.luts = LUTManager(self.log)
        self.auto_editor = AutoEditor(self.log)
        self.subtitles = SubtitlesAI(self.log)
        self.vertical = VerticalConverter(self.log)
        self.gpu = GPUEncoder(self.log)

        try:
            from upscaler import VideoUpscaler
            self.upscaler = VideoUpscaler(self.log)
        except Exception as e:
            self.upscaler = None
            self.log(f"[AVISO] Upscaler nao disponivel: {e}")

        try:
            from stems_separator import StemSeparator
            self.stems = StemSeparator(self.log)
        except Exception as e:
            self.stems = None
            self.log(f"[AVISO] StemSeparator nao disponivel: {e}")

        try:
            from definitive_downloader import DefinitiveDownloader
            self.downloader = DefinitiveDownloader(self.log)
        except Exception as e:
            self.downloader = None
            self.log(f"[AVISO] DefinitiveDownloader nao disponivel: {e}")

        try:
            from face_restore import FaceRestorer
            self.face_restore = FaceRestorer(self.log)
        except Exception as e:
            self.face_restore = None
            self.log(f"[AVISO] FaceRestorer nao disponivel: {e}")

        self.adicionar_abas()
        self.log("=" * 60)
        self.log("PATCH v7.6 APLICADO COM SUCESSO! (20 abas)")
        self.log("=" * 60)

    def _ok(self, obj, nome):
        if obj is None:
            return False
        attr = getattr(obj, nome, False)
        try:
            return attr() if callable(attr) else bool(attr)
        except Exception:
            return False

    def adicionar_abas(self):
        nb = self.app.nb
        self.criar_aba_transicoes_gl(nb)
        self.criar_aba_luts(nb)
        self.criar_aba_auto_edicao(nb)
        self.criar_aba_legendas(nb)
        self.criar_aba_vertical(nb)
        self.criar_aba_upscale(nb)
        self.criar_aba_stems(nb)
        self.criar_aba_legendas_turbo(nb)
        self.criar_aba_download(nb)
        self.criar_aba_face_restore(nb)
        self.criar_aba_whisperx(nb)
        self.criar_aba_auto_edit_suite(nb)

    def log_auto(self, msg):
        self.log(msg)
        if hasattr(self, "auto_log"):
            self.auto_log.insert(tk.END, f"{msg}\n")
            self.auto_log.see(tk.END)
            self.app.root.update_idletasks()

    def criar_aba_transicoes_gl(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Transicoes GL  ")
        ttk.Label(frame, text="Transicoes GL Avancadas (46+)", font=("Helvetica", 16, "bold")).pack(pady=20)
        lf = ttk.LabelFrame(frame, text="Transicoes Disponiveis", padding=15)
        lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lista = tk.Listbox(lf, yscrollcommand=sb.set, font=("Consolas", 10))
        for t in self.gl_trans.listar_transicoes():
            lista.insert(tk.END, t.get("nome", t.get("id", "?")))
        lista.pack(fill=tk.BOTH, expand=True)
        sb.config(command=lista.yview)

    def criar_aba_luts(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  LUTs Avancadas  ")
        ttk.Label(frame, text="LUTs Profissionais (15+)", font=("Helvetica", 16, "bold")).pack(pady=20)
        lf = ttk.LabelFrame(frame, text="LUTs Disponiveis", padding=15)
        lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        row = col = 0
        for lut in self.luts.listar_luts():
            ttk.Button(lf, text=lut.nome, width=20, command=lambda l=lut: self.aplicar_lut_video(l)).grid(row=row, column=col, padx=5, pady=5)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        cf = ttk.LabelFrame(frame, text="Controles", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Intensidade:").pack(side=tk.LEFT, padx=5)
        self.lut_intensidade = tk.DoubleVar(value=1.0)
        ttk.Scale(cf, from_=0.0, to=1.0, variable=self.lut_intensidade, orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT)

    def criar_aba_auto_edicao(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Auto-Edicao  ")
        ttk.Label(frame, text="Auto-Edicao Inteligente", font=("Helvetica", 16, "bold")).pack(pady=20)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Detectar Cenas", command=self.detectar_cenas).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="Remover Silencios", command=self.remover_silencios).pack(fill=tk.X, pady=5)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Threshold (dB):").pack(anchor=tk.W)
        self.silencio_threshold = tk.DoubleVar(value=-35.0)
        ttk.Scale(cf, from_=-60, to=-20, variable=self.silencio_threshold, orient=tk.HORIZONTAL, length=300).pack(fill=tk.X)
        self.auto_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.auto_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.auto_log.insert(tk.END, "Aguardando acao...\n")

    def criar_aba_legendas(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Legendas AI  ")
        ttk.Label(frame, text="Legendas Automaticas (Whisper AI)", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        if self._ok(self.subtitles, "whisper_disponivel"):
            ttk.Label(sf, text="[OK] Whisper instalado", foreground="green").pack(anchor=tk.W)
        else:
            ttk.Label(sf, text="[!] pip install openai-whisper", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Gerar Legendas (SRT)", command=self.gerar_legendas).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="Queimar Legendas no Video", command=self.queimar_legendas).pack(fill=tk.X, pady=5)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Idioma:").pack(anchor=tk.W)
        self.legendas_idioma = tk.StringVar(value="pt")
        ttk.Combobox(cf, textvariable=self.legendas_idioma, values=["pt","en","es","fr","de"], width=10).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Modelo:").pack(anchor=tk.W)
        self.legendas_modelo = tk.StringVar(value="base")
        ttk.Combobox(cf, textvariable=self.legendas_modelo, values=["tiny","base","small","medium","large"], width=10).pack(anchor=tk.W, pady=3)
        self.legendas_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.legendas_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def criar_aba_vertical(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Vertical  ")
        ttk.Label(frame, text="Conversor Vertical 9:16", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        if self._ok(self.vertical, "insightface_disponivel"):
            ttk.Label(sf, text="[OK] InsightFace instalado", foreground="green").pack(anchor=tk.W)
        else:
            ttk.Label(sf, text="[!] pip install insightface opencv-python", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Converter para Vertical (9:16)", command=self.converter_vertical).pack(fill=tk.X, pady=5)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Modo:").pack(anchor=tk.W)
        self.vertical_modo = tk.StringVar(value="smart")
        ttk.Combobox(cf, textvariable=self.vertical_modo, values=["center","top","bottom","smart","manual"], width=15).pack(anchor=tk.W, pady=3)
        self.vertical_blur = tk.BooleanVar(value=True)
        ttk.Checkbutton(cf, text="Blur no fundo", variable=self.vertical_blur).pack(anchor=tk.W)
        self.vertical_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.vertical_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def criar_aba_upscale(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Upscale AI  ")
        ttk.Label(frame, text="Upscale de Video (Real-ESRGAN)", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        if self.upscaler is not None:
            ttk.Label(sf, text="[OK] Upscaler carregado", foreground="green").pack(anchor=tk.W)
        else:
            ttk.Label(sf, text="[!] Real-ESRGAN nao encontrado", foreground="red").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Upscale 2x", command=lambda: self.fazer_upscale("2x")).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="Upscale 4x", command=lambda: self.fazer_upscale("4x")).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="Upscale Anime 4x", command=lambda: self.fazer_upscale("anime")).pack(fill=tk.X, pady=5)
        self.upscale_gpu = tk.BooleanVar(value=True)
        ttk.Checkbutton(af, text="Usar GPU", variable=self.upscale_gpu).pack(anchor=tk.W, pady=5)
        self.upscale_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.upscale_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.upscale_log.insert(tk.END, "Aguardando acao...\n")

    def criar_aba_stems(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Audio Stems  ")
        ttk.Label(frame, text="Separacao de Audio (Demucs AI)", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        if self.stems is not None and self._ok(self.stems, "demucs_disponivel"):
            ttk.Label(sf, text="[OK] Demucs instalado", foreground="green").pack(anchor=tk.W)
        else:
            ttk.Label(sf, text="[!] pip install demucs", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Separar Vocais + Instrumental", command=self.separar_vocais).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="Separar 4 Stems", command=self.separar_todos_stems).pack(fill=tk.X, pady=5)
        self.stems_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.stems_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.stems_log.insert(tk.END, "Aguardando acao...\n")

    def criar_aba_legendas_turbo(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Legendas Turbo  ")
        ttk.Label(frame, text="Legendas Turbo (faster-whisper)", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        try:
            import faster_whisper
            ttk.Label(sf, text="[OK] faster-whisper instalado", foreground="green").pack(anchor=tk.W)
        except ImportError:
            ttk.Label(sf, text="[!] pip install faster-whisper", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Gerar Legendas TURBO (SRT)", command=self.gerar_legendas_turbo).pack(fill=tk.X, pady=5)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Idioma:").pack(anchor=tk.W)
        self.turbo_idioma = tk.StringVar(value="pt")
        ttk.Combobox(cf, textvariable=self.turbo_idioma, values=["pt","en","es","fr","de"], width=10).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Modelo:").pack(anchor=tk.W)
        self.turbo_modelo = tk.StringVar(value="base")
        ttk.Combobox(cf, textvariable=self.turbo_modelo, values=["tiny","base","small","medium","large-v2","large-v3"], width=15).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Device:").pack(anchor=tk.W)
        self.turbo_device = tk.StringVar(value="cpu")
        ttk.Combobox(cf, textvariable=self.turbo_device, values=["cuda","cpu"], width=10).pack(anchor=tk.W, pady=3)
        self.turbo_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.turbo_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.turbo_log.insert(tk.END, "Aguardando acao...\n")

    def criar_aba_download(self, nb):
        """ABA 17: Download - layout com painel esquerdo fixo + log expandivel"""
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Download  ")

        # Titulo
        ttk.Label(frame, text="Download de Videos (yt-dlp)", font=("Helvetica", 14, "bold")).pack(pady=8)

        # Painel principal: esquerda (controles) + direita (log)
        painel = ttk.Frame(frame)
        painel.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- ESQUERDA: controles fixos ---
        esq = ttk.Frame(painel, width=420)
        esq.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        esq.pack_propagate(False)

        # Status
        sf = ttk.LabelFrame(esq, text="Status", padding=8)
        sf.pack(fill=tk.X, pady=(0, 6))
        if self.downloader is not None:
            ttk.Label(sf, text="[OK] yt-dlp + instaloader prontos", foreground="green").pack(anchor=tk.W)
            ttk.Label(sf, text="YouTube, Instagram, TikTok, Vimeo...", foreground="green").pack(anchor=tk.W)
        else:
            ttk.Label(sf, text="[!] pip install yt-dlp instaloader", foreground="red").pack(anchor=tk.W)

        # URL
        uf = ttk.LabelFrame(esq, text="URL do Video", padding=8)
        uf.pack(fill=tk.X, pady=(0, 6))
        self.download_url = ttk.Entry(uf, font=("Consolas", 9))
        self.download_url.pack(fill=tk.X, pady=4)
        ttk.Button(uf, text="Obter Info", command=self.obter_info_video).pack(fill=tk.X)

        # Qualidade
        qf = ttk.LabelFrame(esq, text="Qualidade", padding=8)
        qf.pack(fill=tk.X, pady=(0, 6))
        self.download_qualidade = tk.StringVar(value="best")
        for txt, val in [("Melhor qualidade","best"),("1080p","1080p"),("720p","720p"),("480p","480p"),("Apenas audio","audio")]:
            ttk.Radiobutton(qf, text=txt, variable=self.download_qualidade, value=val).pack(anchor=tk.W)

        # Acoes — SEMPRE VISIVEIS
        af = ttk.LabelFrame(esq, text="Acoes", padding=8)
        af.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(af, text="Baixar Video", command=self.baixar_video).pack(fill=tk.X, pady=3)
        ttk.Button(af, text="Baixar Playlist (max 10)", command=self.baixar_playlist).pack(fill=tk.X, pady=3)

        # --- DIREITA: log expandivel ---
        dir_ = ttk.Frame(painel)
        dir_.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(dir_, text="Log:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        self.download_log = scrolledtext.ScrolledText(dir_, font=("Consolas", 9))
        self.download_log.pack(fill=tk.BOTH, expand=True)
        self.download_log.insert(tk.END, "Cole uma URL e clique em Baixar\n")
        self.download_log.insert(tk.END, "Suporta: YouTube, Instagram, TikTok, Vimeo, Twitter e mais\n")

    def criar_aba_face_restore(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Face Restore  ")
        ttk.Label(frame, text="Restauracao de Rostos (GFPGAN)", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        if self.face_restore is not None and self._ok(self.face_restore, "gfpgan_disponivel"):
            ttk.Label(sf, text="[OK] GFPGAN instalado", foreground="green").pack(anchor=tk.W)
        else:
            ttk.Label(sf, text="[!] pip install gfpgan", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Restaurar Rostos no Video", command=self.restaurar_rostos).pack(fill=tk.X, pady=5)
        self.face_log = scrolledtext.ScrolledText(frame, height=12, font=("Consolas", 9))
        self.face_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.face_log.insert(tk.END, "Aguardando acao...\n")

    def criar_aba_whisperx(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  WhisperX  ")
        ttk.Label(frame, text="WhisperX - Timestamps por Palavra", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        try:
            import whisperx
            ttk.Label(sf, text="[OK] WhisperX instalado", foreground="green").pack(anchor=tk.W)
        except ImportError:
            ttk.Label(sf, text="[!] pip install whisperx", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="Gerar Legendas Karaoke (ASS)", command=self.gerar_karaoke).pack(fill=tk.X, pady=5)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Idioma:").pack(anchor=tk.W)
        self.whisperx_idioma = tk.StringVar(value="pt")
        ttk.Combobox(cf, textvariable=self.whisperx_idioma, values=["pt","en","es","fr","de"], width=10).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Modelo:").pack(anchor=tk.W)
        self.whisperx_modelo = tk.StringVar(value="base")
        ttk.Combobox(cf, textvariable=self.whisperx_modelo, values=["tiny","base","small","medium","large-v2"], width=15).pack(anchor=tk.W, pady=3)
        self.whisperx_log = scrolledtext.ScrolledText(frame, height=12, font=("Consolas", 9))
        self.whisperx_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.whisperx_log.insert(tk.END, "Aguardando acao...\n")

    def criar_aba_auto_edit_suite(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Auto-Edit Suite  ")
        ttk.Label(frame, text="Suite de Edicao Automatizada com IA", font=("Helvetica", 16, "bold")).pack(pady=20)
        sf = ttk.LabelFrame(frame, text="Status dos Modulos", padding=15)
        sf.pack(fill=tk.X, padx=20, pady=10)
        for nome, mod in [("Auto-Editor AI","auto_editor_ai"),("Auto-Color AI","auto_color_ai"),("Auto-Audio AI","auto_audio_ai"),("Auto-Caption AI","auto_caption_ai"),("Auto-Format AI","auto_format_ai")]:
            try:
                __import__(mod)
                ttk.Label(sf, text=f"[OK] {nome}", foreground="green").pack(anchor=tk.W)
            except ImportError:
                ttk.Label(sf, text=f"[!] {nome}", foreground="orange").pack(anchor=tk.W)
        af = ttk.LabelFrame(frame, text="Acoes Automatizadas", padding=15)
        af.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(af, text="1. Edicao Automatica Completa", command=self.editar_automatico_completo).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="2. Color Grading Automatico", command=self.color_grading_automatico).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="3. Mixagem Automatica de Audio", command=self.mixagem_automatica).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="4. Legendas Automaticas + Karaoke", command=self.legendas_automaticas).pack(fill=tk.X, pady=5)
        ttk.Button(af, text="5. Converter Todas as Plataformas", command=self.converter_todas_plataformas).pack(fill=tk.X, pady=5)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=15)
        cf.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(cf, text="Padrao Audio:").pack(anchor=tk.W)
        self.auto_audio_padrao = tk.StringVar(value="youtube")
        ttk.Combobox(cf, textvariable=self.auto_audio_padrao, values=["youtube","ebu_r128","netflix","spotify"], width=15).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Estilo Legendas:").pack(anchor=tk.W)
        self.auto_caption_estilo = tk.StringVar(value="karaoke")
        ttk.Combobox(cf, textvariable=self.auto_caption_estilo, values=["simples","karaoke","palavra_por_palavra"], width=15).pack(anchor=tk.W, pady=3)
        self.auto_suite_log = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
        self.auto_suite_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.auto_suite_log.insert(tk.END, "Aguardando acao...\n")

    # =========================================================
    # ACOES
    # =========================================================

    def aplicar_lut_video(self, lut):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                self.luts.aplicar_lut(Path(v), lut.nome, Path(s), self.lut_intensidade.get())
                messagebox.showinfo("Sucesso", f"LUT aplicado!")
            except Exception as e:
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def detectar_cenas(self):
        self.log_auto("DETECTANDO CENAS...")
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        def t():
            try:
                cenas = self.auto_editor.detectar_cortes_cena(Path(v))
                self.log_auto(f"[OK] {len(cenas)} cenas detectadas!")
                for i, c in enumerate(cenas, 1):
                    self.log_auto(f"Cena {i}: {c.get('inicio',0):.1f}s - {c.get('fim',0):.1f}s")
            except Exception as e:
                import traceback
                self.log_auto(f"[ERRO] {e}\n{traceback.format_exc()}")
        threading.Thread(target=t, daemon=True).start()

    def remover_silencios(self):
        self.log_auto("REMOVENDO SILENCIOS...")
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        thr = self.silencio_threshold.get()
        def t():
            try:
                self.auto_editor.remover_silencios_simples(Path(v), Path(s), thr)
                self.log_auto(f"[OK] Salvo: {s}")
                messagebox.showinfo("Sucesso", "Silencios removidos!")
            except Exception as e:
                import traceback
                self.log_auto(f"[ERRO] {e}\n{traceback.format_exc()}")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def gerar_legendas(self):
        if not self._ok(self.subtitles, "whisper_disponivel"):
            messagebox.showwarning("Aviso", "pip install openai-whisper"); return
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        def t():
            try:
                srt = self.subtitles.gerar_legendas(Path(v), self.legendas_idioma.get(), self.legendas_modelo.get(), "srt")
                self.legendas_log.insert(tk.END, f"[OK] {srt}\n")
                messagebox.showinfo("Sucesso", "Legendas geradas!")
            except Exception as e:
                self.legendas_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def queimar_legendas(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        srt = filedialog.askopenfilename(title="SRT", filetypes=[("SRT","*.srt")])
        if not srt: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                self.subtitles.queimar_legendas(Path(v), Path(srt), Path(s))
                messagebox.showinfo("Sucesso", "Legendas queimadas!")
            except Exception as e:
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def converter_vertical(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                self.vertical.converter(Path(v), Path(s), self.vertical_modo.get(), self.vertical_blur.get())
                messagebox.showinfo("Sucesso", "Convertido!")
            except Exception as e:
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def fazer_upscale(self, escala):
        if self.upscaler is None: messagebox.showerror("Erro", "Upscaler nao disponivel."); return
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                self.upscaler.upscale(Path(v), Path(s), escala, self.upscale_gpu.get())
                messagebox.showinfo("Sucesso", "Upscale concluido!")
            except Exception as e:
                self.upscale_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def separar_vocais(self):
        if self.stems is None: messagebox.showerror("Erro", "pip install demucs"); return
        a = filedialog.askopenfilename(title="Audio/Video", filetypes=[("Audio/Video","*.mp3 *.wav *.mp4 *.mov *.avi *.mkv *.m4a *.flac")])
        if not a: return
        p = filedialog.askdirectory(title="Pasta de saida")
        if not p: return
        def t():
            try:
                ap, pp = Path(a), Path(p)
                self.stems.separar_vocals_instrumental(ap, pp/f"{ap.stem}_VOCALS.wav", pp/f"{ap.stem}_INSTRUMENTAL.wav")
                messagebox.showinfo("Sucesso", "Separacao concluida!")
            except Exception as e:
                self.stems_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def separar_todos_stems(self):
        if self.stems is None: messagebox.showerror("Erro", "pip install demucs"); return
        a = filedialog.askopenfilename(title="Audio/Video", filetypes=[("Audio/Video","*.mp3 *.wav *.mp4 *.mov *.avi *.mkv *.m4a *.flac")])
        if not a: return
        p = filedialog.askdirectory(title="Pasta de saida")
        if not p: return
        def t():
            try:
                stems = self.stems.separar_stems(Path(a), Path(p), "htdemucs")
                messagebox.showinfo("Sucesso", f"{len(stems)} stems gerados!")
            except Exception as e:
                self.stems_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def gerar_legendas_turbo(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar SRT", defaultextension=".srt", filetypes=[("SRT","*.srt")])
        if not s: return
        self.turbo_log.delete(1.0, tk.END)
        def t():
            try:
                from faster_whisper import WhisperModel
                device = self.turbo_device.get()
                compute = "float16" if device == "cuda" else "int8"
                model = WhisperModel(self.turbo_modelo.get(), device=device, compute_type=compute)
                segments, info = model.transcribe(str(v), language=self.turbo_idioma.get(), beam_size=5)
                with open(s, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(segments, 1):
                        f.write(f"{i}\n{self._format_timestamp(seg.start)} --> {self._format_timestamp(seg.end)}\n{seg.text.strip()}\n\n")
                        self.turbo_log.insert(tk.END, f"[{self._format_timestamp(seg.start)}] {seg.text.strip()}\n")
                        self.turbo_log.see(tk.END)
                        self.app.root.update_idletasks()
                messagebox.showinfo("Sucesso", "Legendas geradas!")
            except Exception as e:
                self.turbo_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def obter_info_video(self):
        url = self.download_url.get().strip()
        if not url: messagebox.showwarning("Aviso", "Cole uma URL primeiro!"); return
        if self.downloader is None: messagebox.showerror("Erro", "pip install yt-dlp"); return
        def t():
            try:
                info = self.downloader.obter_info(url)
                self.download_log.delete(1.0, tk.END)
                for k in ["titulo","autor","duracao","plataforma","metodo"]:
                    self.download_log.insert(tk.END, f"{k}: {info.get(k,'-')}\n")
            except Exception as e:
                self.download_log.insert(tk.END, f"[ERRO] {e}\n")
        threading.Thread(target=t, daemon=True).start()

    def baixar_video(self):
        url = self.download_url.get().strip()
        if not url: messagebox.showwarning("Aviso", "Cole uma URL primeiro!"); return
        if self.downloader is None: messagebox.showerror("Erro", "Downloader indisponivel."); return
        p = filedialog.askdirectory(title="Pasta de destino")
        if not p: return
        def t():
            try:
                self.download_log.delete(1.0, tk.END)
                self.download_log.insert(tk.END, f"Baixando: {url}\n")
                arq = self.downloader.baixar_video(url, Path(p), self.download_qualidade.get())
                self.download_log.insert(tk.END, f"[OK] {arq}\n")
                messagebox.showinfo("Sucesso", "Baixado!")
            except Exception as e:
                self.download_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def baixar_playlist(self):
        url = self.download_url.get().strip()
        if not url: messagebox.showwarning("Aviso", "Cole uma URL!"); return
        if self.downloader is None: messagebox.showerror("Erro", "Downloader indisponivel."); return
        p = filedialog.askdirectory(title="Pasta de destino")
        if not p: return
        def t():
            try:
                arqs = self.downloader.baixar_playlist(url, Path(p), 10)
                messagebox.showinfo("Sucesso", f"{len(arqs)} videos baixados!")
            except Exception as e:
                self.download_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def restaurar_rostos(self):
        if self.face_restore is None: messagebox.showerror("Erro", "pip install gfpgan"); return
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                self.face_restore.restaurar_video(Path(v), Path(s))
                messagebox.showinfo("Sucesso", "Rostos restaurados!")
            except Exception as e:
                self.face_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def gerar_karaoke(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar ASS", defaultextension=".ass", filetypes=[("ASS","*.ass")])
        if not s: return
        def t():
            try:
                import whisperx
                device = "cuda" if self.gpu.obter_melhor_gpu() else "cpu"
                idioma = self.whisperx_idioma.get()
                model = whisperx.load_model(self.whisperx_modelo.get(), device, language=idioma)
                result = model.transcribe(str(v), language=idioma)
                ma, meta = whisperx.load_align_model(language_code=idioma, device=device)
                result = whisperx.align(result["segments"], ma, meta, str(v), device)
                with open(s, "w", encoding="utf-8") as f:
                    f.write("[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
                    for seg in result["segments"]:
                        for w in seg.get("words", []):
                            f.write(f"Dialogue: 0,{self._format_ass_time(w['start'])},{self._format_ass_time(w['end'])},Default,,0,0,0,,{w['word'].strip()}\n")
                messagebox.showinfo("Sucesso", "Karaoke gerado!")
            except Exception as e:
                self.whisperx_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def editar_automatico_completo(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                from auto_editor_ai import AutoEditorAI
                AutoEditorAI(self.log).editar_automatico(Path(v), Path(s), {"threshold_silencio":-35.0,"remover_pausas":True,"adicionar_transicoes":True,"transicao_tipo":"fade","transicao_duracao":0.5,"manter_minimo":1.0})
                messagebox.showinfo("Sucesso", "Edicao concluida!")
            except Exception as e:
                self.auto_suite_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def color_grading_automatico(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                from auto_color_ai import AutoColorAI
                AutoColorAI(self.log).aplicar_color_auto(Path(v), Path(s), "auto")
                messagebox.showinfo("Sucesso", "Color grading concluido!")
            except Exception as e:
                self.auto_suite_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def mixagem_automatica(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                from auto_audio_ai import AutoAudioAI
                AutoAudioAI(self.log).mixar_automatico(Path(v), Path(s), self.auto_audio_padrao.get())
                messagebox.showinfo("Sucesso", "Mixagem concluida!")
            except Exception as e:
                self.auto_suite_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def legendas_automaticas(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        s = filedialog.asksaveasfilename(title="Salvar", defaultextension=".mp4", filetypes=[("MP4","*.mp4")])
        if not s: return
        def t():
            try:
                from auto_caption_ai import AutoCaptionAI
                AutoCaptionAI(self.log).gerar_legendas_auto(Path(v), Path(s), "pt", "base", self.auto_caption_estilo.get())
                messagebox.showinfo("Sucesso", "Legendas concluidas!")
            except Exception as e:
                self.auto_suite_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def converter_todas_plataformas(self):
        v = filedialog.askopenfilename(title="Video", filetypes=[("Videos","*.mp4 *.mov *.avi *.mkv")])
        if not v: return
        p = filedialog.askdirectory(title="Pasta de saida")
        if not p: return
        def t():
            try:
                from auto_format_ai import AutoFormatAI
                arqs = AutoFormatAI(self.log).converter_todas_plataformas(Path(v), Path(p))
                messagebox.showinfo("Sucesso", f"{len(arqs)} versoes geradas!")
            except Exception as e:
                self.auto_suite_log.insert(tk.END, f"[ERRO] {e}\n")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=t, daemon=True).start()

    def _format_timestamp(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _format_ass_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
