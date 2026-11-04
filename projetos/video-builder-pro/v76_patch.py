#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PATCH v7.6 -> v7.7 - Video Builder Pro
Adiciona 12 abas ao app base (total 20). Uso: aplicar_patch(app).

Correcoes v7.7 (detalhes em CHANGELOG.md, secao "v76_patch.py"):
  CRASHES
  - Detectar Cenas: c.get('inicio') sobre float -> AttributeError. Agora usa
    AutoEditor.detectar_cenas() que devolve dicts.
  - Vertical: string "smart" no lugar de CropMode e o blur caia na posicao
    de resolucao_saida -> AttributeError. Agora por palavra-chave.
  - Queimar legendas: metodo inexistente (queimar_legendas). Corrigido no
    modulo (alias) e aqui.
  - WhisperX: "cuda" sempre (GPUInfo e sempre truthy) -> falha em CPU.
    Agora detecta CUDA via torch e usa compute_type int8 na CPU.
  - mixagem_automatica usava self.auto_audio_padrao inexistente e nao
    tinha botao; legendas_automaticas tambem nao tinha botao. Ambos ligados.
  - upscaler/stems_separator/face_restore/auto_*_ai nao existiam: criados
    em modules/ (upscaler.py, stems_separator.py, face_restore.py,
    auto_suite.py).
  COMPATIBILIDADE (Python 3.13)
  - moviepy 2.x removeu moviepy.editor/subclip/speedx e o pydub depende do
    modulo audioop (removido no 3.13). Preview, speed, trim, analise e
    normalizacao agora usam FFmpeg direto: zero dependencias extras.
  - "Normalizar Audio (pydub)" usava dBFS (RMS) rotulado como YouTube e, ao
    salvar .mp4, DESCARTAVA o video. Agora EBU R128 (LUFS) 2 passadas,
    video copiado.
  UI
  - Nenhuma thread toca em widget (app.ui.chamar).
  - Transicoes GL: a aba so listava nomes; agora aplica entre 2 clipes
    (com easing) ou define a transicao do projeto.
  - Speed ramp: dialogo tinha dois sliders iguais (o primeiro sem rotulo).
  - Status das abas reflete o que esta realmente instalado.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "modules"))

import tkinter as tk  # noqa: E402
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk  # noqa: E402

from auto_editor import AutoEditor  # noqa: E402
from auto_suite import AutoAudioAI, AutoCaptionAI, AutoColorAI, AutoEditorAI, AutoFormatAI  # noqa: E402
from ffmpeg_utils import (PADROES_LOUDNESS, abrir_no_player, binario, cadeia_atempo,  # noqa: E402
                          executar, executar_com_progresso, info_midia, medir_loudness,
                          normalizar_loudness, padrao_loudness, tipos_midia, tipos_video)
from gpu_encoder import GPUEncoder, GPUType  # noqa: E402
from luts_manager import LUTManager  # noqa: E402
from subtitles_ai import SubtitlesAI  # noqa: E402
from transitions_gl import EasingType, GLTransition, GLTransitionsEngine  # noqa: E402
from vertical_converter import CropMode, VerticalConverter  # noqa: E402

# v7.8.1: maiusculas e minusculas (o dialogo do Tk no Linux diferencia: .MP4)
VIDEOS = tipos_video()
MIDIA = tipos_midia()
MP4 = [("MP4", "*.mp4")]


def aplicar_patch(app):
    return V73Patch(app)


def _instalado(modulo: str) -> bool:
    return importlib.util.find_spec(modulo) is not None


class V73Patch:
    """Nome mantido por compatibilidade com launchers da v7.3-v7.6."""

    def __init__(self, app):
        self.app = app
        self.log = app.log
        self.ui = app.ui

        self.gl_trans = GLTransitionsEngine(self.log)
        self.luts = LUTManager(self.log)
        self.auto_editor = AutoEditor(self.log)
        self.subtitles = SubtitlesAI(self.log)
        self.vertical = VerticalConverter(self.log)
        self.gpu = GPUEncoder(self.log)

        self.log(f"[{'OK' if binario('ffmpeg') else 'ERRO'}] ffmpeg  "
                 f"[{'OK' if binario('ffplay') else 'AVISO'}] ffplay (preview)")

        self.upscaler = self._carregar("upscaler", "VideoUpscaler")
        self.stems = self._carregar("stems_separator", "StemSeparator")
        self.downloader = self._carregar("definitive_downloader", "DefinitiveDownloader")
        self.face_restore = self._carregar("face_restore", "FaceRestorer")

        self.adicionar_abas()
        self.log("=" * 60)
        self.log(f"PATCH v7.7 APLICADO: {len(self.app.nb.tabs())} abas")
        self.log("=" * 60)

    def _carregar(self, modulo, classe):
        try:
            mod = __import__(modulo)
            return getattr(mod, classe)(self.log)
        except Exception as e:  # noqa: BLE001 - modulo opcional
            self.log(f"[AVISO] {classe} indisponivel: {e}")
            return None

    def _ok(self, obj, nome):
        if obj is None:
            return False
        attr = getattr(obj, nome, False)
        try:
            return attr() if callable(attr) else bool(attr)
        except Exception:  # noqa: BLE001
            return False

    # ============================================================ helpers
    def _escrever(self, widget, msg: str):
        """Escreve num ScrolledText de qualquer thread."""
        def _ui():
            widget.insert(tk.END, f"{msg}\n")
            widget.see(tk.END)
        self.ui.chamar(_ui)

    def _tarefa(self, widget, titulo: str, fn, sucesso=None, limpar: bool = False):
        """Roda fn(log) em segundo plano. log escreve no widget + log geral."""
        if limpar:
            widget.delete(1.0, tk.END)

        def log(msg):
            self.log(msg)
            self._escrever(widget, msg)

        def alvo():
            resultado = fn(log)
            texto = sucesso(resultado) if callable(sucesso) else (sucesso or "Concluido!")
            log(f"[OK] {texto}")
            self.ui.chamar(messagebox.showinfo, titulo, texto)

        def erro(e):
            self._escrever(widget, f"[ERRO] {e}")
            messagebox.showerror(titulo, str(e))
        log(f"{titulo}: iniciando...")
        return self.ui.em_segundo_plano(alvo, ao_erro=erro, nome=titulo)

    @staticmethod
    def _abrir(titulo="Video", tipos=VIDEOS):
        return filedialog.askopenfilename(title=titulo, filetypes=tipos)

    @staticmethod
    def _salvar(titulo="Salvar", ext=".mp4", tipos=MP4):
        return filedialog.asksaveasfilename(title=titulo, defaultextension=ext, filetypes=tipos)

    def _status(self, pai, ok: bool, texto_ok: str, texto_falta: str):
        ttk.Label(pai, text=f"[OK] {texto_ok}" if ok else f"[!] {texto_falta}",
                  foreground="green" if ok else "orange").pack(anchor=tk.W)

    def _log_widget(self, frame, altura=10, inicial="Aguardando acao...\n"):
        w = scrolledtext.ScrolledText(frame, height=altura, font=("Consolas", 9))
        w.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        w.insert(tk.END, inicial)
        return w

    def _cuda(self) -> bool:
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001 - torch ausente/quebrado
            return self.gpu.obter_melhor_gpu().tipo == GPUType.NVIDIA

    # ============================================================ abas
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
            self._escrever(self.auto_log, msg)

    def criar_aba_transicoes_gl(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Transicoes GL  ")
        lista_t = self.gl_trans.listar_transicoes()
        ttk.Label(frame, text=f"Transicoes ({len(lista_t)})", font=("Helvetica", 16, "bold")).pack(pady=12)
        ttk.Label(frame, text="Mascaras suportam easing. As marcadas '(aprox.)' usam a transicao nativa "
                              "do FFmpeg mais proxima (o xfade nao distorce imagem).").pack()
        lf = ttk.LabelFrame(frame, text="Transicoes Disponiveis", padding=10)
        lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.gl_lista = tk.Listbox(lf, yscrollcommand=sb.set, font=("Consolas", 10), height=12)
        self._gl_ids = []
        for t in lista_t:
            self.gl_lista.insert(tk.END, f"{t['nome']}  [{t['tipo']}]")
            self._gl_ids.append(t["id"])
        self.gl_lista.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.gl_lista.yview)
        cf = ttk.Frame(frame)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Easing:").pack(side=tk.LEFT)
        self.gl_easing = tk.StringVar(value="cubic")
        ttk.Combobox(cf, textvariable=self.gl_easing, values=[e.value for e in EasingType],
                     width=12, state="readonly").pack(side=tk.LEFT, padx=4)
        ttk.Label(cf, text="Duracao (s):").pack(side=tk.LEFT, padx=(12, 0))
        self.gl_duracao = tk.DoubleVar(value=1.0)
        ttk.Spinbox(cf, from_=0.1, to=5.0, increment=0.1, textvariable=self.gl_duracao, width=6).pack(side=tk.LEFT)
        ttk.Button(cf, text="Aplicar entre 2 clipes...", command=self.aplicar_transicao_gl).pack(side=tk.LEFT, padx=8)
        ttk.Button(cf, text="Usar no projeto (Timeline)", command=self.usar_transicao_no_projeto).pack(side=tk.LEFT)
        self.gl_log = self._log_widget(frame, 6)

    def criar_aba_luts(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  LUTs Avancadas  ")
        luts = self.luts.listar_luts()
        ttk.Label(frame, text=f"LUTs Profissionais ({len(luts)})", font=("Helvetica", 16, "bold")).pack(pady=12)
        lf = ttk.LabelFrame(frame, text="Aplicar em um arquivo de video", padding=12)
        lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        for k, lut in enumerate(luts):
            ttk.Button(lf, text=lut.nome, width=20, command=lambda l=lut: self.aplicar_lut_video(l)
                       ).grid(row=k // 3, column=k % 3, padx=5, pady=5)
        cf = ttk.LabelFrame(frame, text="Controles", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Intensidade (0 = original, 1 = look completo):").pack(side=tk.LEFT, padx=5)
        self.lut_intensidade = tk.DoubleVar(value=1.0)
        ttk.Scale(cf, from_=0.0, to=1.0, variable=self.lut_intensidade, orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT)
        ttk.Button(cf, text="Carregar .cube...", command=self.carregar_cube).pack(side=tk.LEFT, padx=10)
        self.lut_log = self._log_widget(frame, 6)

    def criar_aba_auto_edicao(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Auto-Edicao  ")
        ttk.Label(frame, text="Auto-Edicao Inteligente", font=("Helvetica", 16, "bold")).pack(pady=12)
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Detectar Cenas", command=self.detectar_cenas).pack(fill=tk.X, pady=4)
        ttk.Button(af, text="Remover Silencios", command=self.remover_silencios).pack(fill=tk.X, pady=4)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Threshold de silencio (dB):").pack(anchor=tk.W)
        self.silencio_threshold = tk.DoubleVar(value=-35.0)
        ttk.Scale(cf, from_=-60, to=-20, variable=self.silencio_threshold, orient=tk.HORIZONTAL, length=300).pack(fill=tk.X)
        ttk.Label(cf, text="Sensibilidade de cena (0.1 sensivel - 0.6 so cortes fortes):").pack(anchor=tk.W)
        self.cena_threshold = tk.DoubleVar(value=0.3)
        ttk.Scale(cf, from_=0.1, to=0.6, variable=self.cena_threshold, orient=tk.HORIZONTAL, length=300).pack(fill=tk.X)
        self.auto_log = self._log_widget(frame, 10)

    def criar_aba_legendas(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Legendas AI  ")
        ttk.Label(frame, text="Legendas Automaticas (Whisper AI)", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, self._ok(self.subtitles, "whisper_disponivel"), "Whisper instalado",
                     "pip install openai-whisper")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Gerar Legendas (SRT)...", command=self.gerar_legendas).pack(fill=tk.X, pady=4)
        ttk.Button(af, text="Queimar Legendas no Video...", command=self.queimar_legendas).pack(fill=tk.X, pady=4)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Idioma:").pack(anchor=tk.W)
        self.legendas_idioma = tk.StringVar(value="pt")
        ttk.Combobox(cf, textvariable=self.legendas_idioma, values=["pt", "en", "es", "fr", "de", "it"], width=10).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Modelo:").pack(anchor=tk.W)
        self.legendas_modelo = tk.StringVar(value="base")
        ttk.Combobox(cf, textvariable=self.legendas_modelo, values=["tiny", "base", "small", "medium", "large", "turbo"], width=10).pack(anchor=tk.W, pady=3)
        self.legendas_log = self._log_widget(frame, 10, "")

    def criar_aba_vertical(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Vertical  ")
        ttk.Label(frame, text="Conversor Vertical 9:16", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, self._ok(self.vertical, "insightface_disponivel") and self._ok(self.vertical, "opencv_disponivel"),
                     "InsightFace + OpenCV (modo smart)", "modo smart = centro (pip install insightface opencv-python onnxruntime)")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Converter para Vertical (9:16)...", command=self.converter_vertical).pack(fill=tk.X, pady=4)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Modo de recorte (quando o blur esta desligado):").pack(anchor=tk.W)
        self.vertical_modo = tk.StringVar(value="smart")
        ttk.Combobox(cf, textvariable=self.vertical_modo, values=["center", "top", "bottom", "smart"],
                     width=15, state="readonly").pack(anchor=tk.W, pady=3)
        self.vertical_blur = tk.BooleanVar(value=True)
        ttk.Checkbutton(cf, text="Video inteiro sobre fundo desfocado (estilo Reels/TikTok)",
                        variable=self.vertical_blur).pack(anchor=tk.W)
        self.vertical_log = self._log_widget(frame, 10, "")

    def criar_aba_upscale(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Upscale AI  ")
        ttk.Label(frame, text="Upscale de Video (Real-ESRGAN)", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        ia = self._ok(self.upscaler, "realesrgan_disponivel")
        self._status(sf, ia, "Real-ESRGAN ncnn-vulkan (IA)",
                     "realesrgan-ncnn-vulkan nao encontrado: sera usado o modo classico (FFmpeg lanczos). "
                     "Coloque o binario no PATH ou em bin/")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Upscale 2x...", command=lambda: self.fazer_upscale("2x")).pack(fill=tk.X, pady=4)
        ttk.Button(af, text="Upscale 4x...", command=lambda: self.fazer_upscale("4x")).pack(fill=tk.X, pady=4)
        ttk.Button(af, text="Upscale Anime 4x...", command=lambda: self.fazer_upscale("anime")).pack(fill=tk.X, pady=4)
        self.upscale_gpu = tk.BooleanVar(value=True)
        ttk.Checkbutton(af, text="Usar GPU (Vulkan) - desmarcado = modo classico", variable=self.upscale_gpu).pack(anchor=tk.W, pady=4)
        self.upscale_log = self._log_widget(frame, 10)

    def criar_aba_stems(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Audio Stems  ")
        ttk.Label(frame, text="Separacao de Audio (Demucs AI)", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, self._ok(self.stems, "demucs_disponivel"), "Demucs instalado", "pip install demucs")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Separar Vocais + Instrumental...", command=self.separar_vocais).pack(fill=tk.X, pady=4)
        ttk.Button(af, text="Separar 4 Stems...", command=self.separar_todos_stems).pack(fill=tk.X, pady=4)
        self.stems_log = self._log_widget(frame, 10)

    def criar_aba_legendas_turbo(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Legendas Turbo  ")
        ttk.Label(frame, text="Legendas Turbo (faster-whisper)", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, _instalado("faster_whisper"), "faster-whisper instalado", "pip install faster-whisper")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Gerar Legendas TURBO (SRT)...", command=self.gerar_legendas_turbo).pack(fill=tk.X, pady=4)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Idioma:").pack(anchor=tk.W)
        self.turbo_idioma = tk.StringVar(value="pt")
        ttk.Combobox(cf, textvariable=self.turbo_idioma, values=["pt", "en", "es", "fr", "de", "it"], width=10).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Modelo:").pack(anchor=tk.W)
        self.turbo_modelo = tk.StringVar(value="base")
        ttk.Combobox(cf, textvariable=self.turbo_modelo, values=["tiny", "base", "small", "medium", "large-v2", "large-v3", "turbo"], width=15).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Device:").pack(anchor=tk.W)
        self.turbo_device = tk.StringVar(value="auto")
        ttk.Combobox(cf, textvariable=self.turbo_device, values=["auto", "cuda", "cpu"], width=10).pack(anchor=tk.W, pady=3)
        self.turbo_log = self._log_widget(frame, 10)

    def criar_aba_download(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Download  ")
        ttk.Label(frame, text="Download de Videos (yt-dlp)", font=("Helvetica", 14, "bold")).pack(pady=8)
        painel = ttk.Frame(frame)
        painel.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        esq = ttk.Frame(painel, width=420)
        esq.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        esq.pack_propagate(False)
        sf = ttk.LabelFrame(esq, text="Status", padding=8)
        sf.pack(fill=tk.X, pady=(0, 6))
        import definitive_downloader as dd
        self._status(sf, dd.YT_DLP_OK, "yt-dlp pronto (YouTube, Instagram, TikTok, Vimeo...)", "pip install -U yt-dlp")
        if self.downloader is not None and dd.YT_DLP_OK:
            origem = (str(self.downloader.cookies_txt) if self.downloader.cookies_txt
                      else (self.downloader.browser or "nenhum"))
            ttk.Label(sf, text=f"Cookies: {origem}").pack(anchor=tk.W)
        uf = ttk.LabelFrame(esq, text="URL do Video", padding=8)
        uf.pack(fill=tk.X, pady=(0, 6))
        self.download_url = ttk.Entry(uf, font=("Consolas", 9))
        self.download_url.pack(fill=tk.X, pady=4)
        ttk.Button(uf, text="Obter Info", command=self.obter_info_video).pack(fill=tk.X)
        qf = ttk.LabelFrame(esq, text="Qualidade", padding=8)
        qf.pack(fill=tk.X, pady=(0, 6))
        self.download_qualidade = tk.StringVar(value="best")
        for txt, val in [("Melhor qualidade", "best"), ("1080p", "1080p"), ("720p", "720p"), ("480p", "480p"), ("Apenas audio", "audio")]:
            ttk.Radiobutton(qf, text=txt, variable=self.download_qualidade, value=val).pack(anchor=tk.W)
        af = ttk.LabelFrame(esq, text="Acoes", padding=8)
        af.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(af, text="Baixar Video", command=self.baixar_video).pack(fill=tk.X, pady=3)
        ttk.Button(af, text="Baixar Playlist (max 10)", command=self.baixar_playlist).pack(fill=tk.X, pady=3)
        dir_ = ttk.Frame(painel)
        dir_.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(dir_, text="Log:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        self.download_log = scrolledtext.ScrolledText(dir_, font=("Consolas", 9))
        self.download_log.pack(fill=tk.BOTH, expand=True)
        self.download_log.insert(tk.END, "Cole uma URL e clique em Baixar\n")

    def criar_aba_face_restore(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Face Restore  ")
        ttk.Label(frame, text="Restauracao de Rostos (GFPGAN)", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, self._ok(self.face_restore, "gfpgan_disponivel"), "GFPGAN instalado", "pip install gfpgan")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Restaurar Rostos no Video...", command=self.restaurar_rostos).pack(fill=tk.X, pady=4)
        self.face_gpu = tk.BooleanVar(value=True)
        ttk.Checkbutton(af, text="Usar GPU (CUDA) se disponivel", variable=self.face_gpu).pack(anchor=tk.W)
        self.face_log = self._log_widget(frame, 12)

    def criar_aba_whisperx(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  WhisperX  ")
        ttk.Label(frame, text="WhisperX - Timestamps por Palavra", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Status", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, _instalado("whisperx"), "WhisperX instalado", "pip install whisperx")
        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        ttk.Button(af, text="Gerar Legendas Karaoke (ASS)...", command=self.gerar_karaoke).pack(fill=tk.X, pady=4)
        cf = ttk.LabelFrame(frame, text="Configuracoes", padding=12)
        cf.pack(fill=tk.X, padx=20, pady=6)
        ttk.Label(cf, text="Idioma:").pack(anchor=tk.W)
        self.whisperx_idioma = tk.StringVar(value="pt")
        ttk.Combobox(cf, textvariable=self.whisperx_idioma, values=["pt", "en", "es", "fr", "de", "it"], width=10).pack(anchor=tk.W, pady=3)
        ttk.Label(cf, text="Modelo:").pack(anchor=tk.W)
        self.whisperx_modelo = tk.StringVar(value="base")
        ttk.Combobox(cf, textvariable=self.whisperx_modelo, values=["tiny", "base", "small", "medium", "large-v2", "large-v3"], width=15).pack(anchor=tk.W, pady=3)
        self.whisperx_log = self._log_widget(frame, 12)

    def criar_aba_auto_edit_suite(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Auto-Edit Suite  ")
        ttk.Label(frame, text="Suite de Edicao Automatizada", font=("Helvetica", 16, "bold")).pack(pady=12)
        sf = ttk.LabelFrame(frame, text="Ferramentas", padding=12)
        sf.pack(fill=tk.X, padx=20, pady=6)
        self._status(sf, bool(binario("ffmpeg")), "FFmpeg (edicao, audio, cor, formatos)", "FFmpeg nao encontrado no PATH")
        self._status(sf, bool(binario("ffplay")), "ffplay (preview)", "ffplay ausente: preview abre no player do sistema")
        self._status(sf, self._ok(self.subtitles, "whisper_disponivel"), "Whisper (legendas automaticas)",
                     "pip install openai-whisper (legendas automaticas)")

        af = ttk.LabelFrame(frame, text="Acoes", padding=12)
        af.pack(fill=tk.X, padx=20, pady=6)
        grade = [("Preview Rapido", self.preview_moviepy), ("Speed / Slow Motion...", self.speed_ramp_moviepy),
                 ("Cortar Clipe (Trim)...", self.trim_moviepy), ("Analise de Audio (EBU R128)", self.analisar_audio_pydub),
                 ("Normalizar Audio (LUFS)...", self.normalizar_audio_pydub),
                 ("Edicao Automatica Completa", self.editar_automatico_completo),
                 ("Color Grading Automatico", self.color_grading_automatico),
                 ("Mixagem Automatica", self.mixagem_automatica),
                 ("Legendas Automaticas", self.legendas_automaticas),
                 ("Converter Todas as Plataformas", self.converter_todas_plataformas)]
        for k, (txt, cmd) in enumerate(grade):
            ttk.Button(af, text=txt, command=cmd, width=34).grid(row=k // 2, column=k % 2, padx=4, pady=3, sticky=tk.W)
        of = ttk.Frame(frame)
        of.pack(fill=tk.X, padx=20)
        ttk.Label(of, text="Padrao da mixagem:").pack(side=tk.LEFT)
        self.auto_audio_padrao = tk.StringVar(value="YouTube")
        ttk.Combobox(of, textvariable=self.auto_audio_padrao, values=list(PADROES_LOUDNESS), width=12,
                     state="readonly").pack(side=tk.LEFT, padx=4)
        ttk.Label(of, text="  Estilo da legenda:").pack(side=tk.LEFT)
        self.auto_caption_estilo = tk.StringVar(value="simples")
        ttk.Combobox(of, textvariable=self.auto_caption_estilo, values=list(AutoCaptionAI.ESTILOS), width=10,
                     state="readonly").pack(side=tk.LEFT, padx=4)
        self.auto_suite_log = self._log_widget(frame, 10)

    # ============================================================ acoes: transicoes / LUT
    def _gl_selecionada(self):
        sel = self.gl_lista.curselection()
        if not sel:
            messagebox.showwarning("Transicoes", "Selecione uma transicao na lista.")
            return None
        return self._gl_ids[sel[0]]

    def aplicar_transicao_gl(self):
        tid = self._gl_selecionada()
        if not tid:
            return
        a = self._abrir("Primeiro clipe")
        if not a:
            return
        b = self._abrir("Segundo clipe")
        if not b:
            return
        s = self._salvar()
        if not s:
            return
        t = GLTransition(tid, float(self.gl_duracao.get()), EasingType(self.gl_easing.get()))
        self._tarefa(self.gl_log, "Transicao",
                     lambda log: GLTransitionsEngine(log).renderizar_transicao(Path(a), Path(b), t, Path(s)),
                     f"Transicao salva em {s}")

    def usar_transicao_no_projeto(self):
        tid = self._gl_selecionada()
        if not tid:
            return
        nome = self.gl_trans.TRANSICOES_GL[tid]["nome"]
        if hasattr(self.app, "transicao_var"):
            self.app.transicao_var.set(nome)
            self.app.transicao_dur_var.set(float(self.gl_duracao.get()))
        self._escrever(self.gl_log, f"Transicao do projeto: {nome} ({self.gl_duracao.get():.1f}s)")

    def carregar_cube(self):
        arq = filedialog.askopenfilename(filetypes=[("LUT 3D", "*.cube")])
        if arq:
            p = Path(arq)
            self.luts.adicionar_lut_personalizada(p.stem, p)
            self._escrever(self.lut_log, f"LUT '{p.stem}' carregada. Use 'Aplicar' abaixo ou na aba Cor.")
            self.aplicar_lut_video(next(l for l in self.luts.listar_luts() if l.nome == p.stem))

    def aplicar_lut_video(self, lut):
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        intensidade = self.lut_intensidade.get()
        self._tarefa(self.lut_log, "LUT", lambda log: self.luts.aplicar_lut(Path(v), lut.nome, Path(s), intensidade),
                     f"'{lut.nome}' aplicado em {Path(s).name}")

    # ============================================================ acoes: auto-edicao
    def detectar_cenas(self):
        v = self._abrir()
        if not v:
            return
        limiar = self.cena_threshold.get()

        def fn(log):
            cenas = AutoEditor(log).detectar_cenas(Path(v), limiar)
            for i, c in enumerate(cenas, 1):
                log(f"Cena {i}: {c['inicio']:.2f}s - {c['fim']:.2f}s ({c['duracao']:.2f}s)")
            return cenas
        self._tarefa(self.auto_log, "Detectar Cenas", fn, lambda c: f"{len(c)} cena(s) detectada(s)", limpar=True)

    def remover_silencios(self):
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        thr = self.silencio_threshold.get()
        self._tarefa(self.auto_log, "Remover Silencios",
                     lambda log: AutoEditor(log).remover_silencios_simples(Path(v), Path(s), thr),
                     f"Silencios removidos: {Path(s).name}", limpar=True)

    # ============================================================ acoes: legendas / vertical
    def gerar_legendas(self):
        if not self._ok(self.subtitles, "whisper_disponivel"):
            messagebox.showwarning("Aviso", "pip install openai-whisper")
            return
        v = self._abrir()
        if not v:
            return
        s = self._salvar("Salvar legenda", ".srt", [("SRT", "*.srt")])
        if not s:
            return
        idioma, modelo = self.legendas_idioma.get(), self.legendas_modelo.get()
        self._tarefa(self.legendas_log, "Legendas",
                     lambda log: SubtitlesAI(log).gerar_legendas(Path(v), idioma, modelo, "srt", saida=Path(s)),
                     lambda p: f"Legendas geradas: {p}")

    def queimar_legendas(self):
        v = self._abrir()
        if not v:
            return
        srt = filedialog.askopenfilename(title="Legenda", filetypes=[("Legendas", "*.srt *.ass *.vtt")])
        if not srt:
            return
        s = self._salvar()
        if not s:
            return
        self._tarefa(self.legendas_log, "Queimar Legendas",
                     lambda log: SubtitlesAI(log).queimar_legendas_no_video(Path(v), Path(srt), Path(s)),
                     f"Legendas queimadas: {Path(s).name}")

    def converter_vertical(self):
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        modo, blur = CropMode(self.vertical_modo.get()), self.vertical_blur.get()
        self._tarefa(self.vertical_log, "Vertical",
                     lambda log: VerticalConverter(log).converter(Path(v), Path(s), modo, adicionar_blur_fundo=blur),
                     f"Convertido: {Path(s).name}")

    # ============================================================ acoes: upscale / stems / rostos
    def fazer_upscale(self, escala):
        if self.upscaler is None:
            messagebox.showerror("Erro", "Upscaler nao disponivel (veja o log).")
            return
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        gpu = self.upscale_gpu.get()

        def fn(log):
            self.upscaler.log = log
            return self.upscaler.upscale(Path(v), Path(s), escala, gpu)
        self._tarefa(self.upscale_log, "Upscale", fn, f"Upscale {escala} concluido: {Path(s).name}")

    def separar_vocais(self):
        if not self._ok(self.stems, "demucs_disponivel"):
            messagebox.showerror("Erro", "pip install demucs")
            return
        a = self._abrir("Audio/Video", MIDIA)
        if not a:
            return
        p = filedialog.askdirectory(title="Pasta de saida")
        if not p:
            return
        ap, pp = Path(a), Path(p)
        self._tarefa(self.stems_log, "Stems",
                     lambda log: self.stems.separar_vocals_instrumental(ap, pp / f"{ap.stem}_VOCALS.wav",
                                                                        pp / f"{ap.stem}_INSTRUMENTAL.wav"),
                     "Separacao concluida!")

    def separar_todos_stems(self):
        if not self._ok(self.stems, "demucs_disponivel"):
            messagebox.showerror("Erro", "pip install demucs")
            return
        a = self._abrir("Audio/Video", MIDIA)
        if not a:
            return
        p = filedialog.askdirectory(title="Pasta de saida")
        if not p:
            return
        self._tarefa(self.stems_log, "Stems", lambda log: self.stems.separar_stems(Path(a), Path(p), "htdemucs"),
                     lambda r: f"{len(r)} stems gerados!")

    def restaurar_rostos(self):
        if not self._ok(self.face_restore, "gfpgan_disponivel"):
            messagebox.showerror("Erro", "pip install gfpgan")
            return
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        gpu = self.face_gpu.get()

        def fn(log):
            self.face_restore.log = log
            return self.face_restore.restaurar_video(Path(v), Path(s), gpu)
        self._tarefa(self.face_log, "Face Restore", fn, "Rostos restaurados!")

    # ============================================================ acoes: whisper turbo / x
    def gerar_legendas_turbo(self):
        if not _instalado("faster_whisper"):
            messagebox.showerror("Erro", "pip install faster-whisper")
            return
        v = self._abrir()
        if not v:
            return
        s = self._salvar("Salvar SRT", ".srt", [("SRT", "*.srt")])
        if not s:
            return
        modelo, idioma = self.turbo_modelo.get(), self.turbo_idioma.get()
        device = self.turbo_device.get()
        if device == "auto":
            device = "cuda" if self._cuda() else "cpu"

        def fn(log):
            from faster_whisper import WhisperModel
            compute = "float16" if device == "cuda" else "int8"
            log(f"faster-whisper {modelo} em {device} ({compute})...")
            model = WhisperModel(modelo, device=device, compute_type=compute)
            segments, _ = model.transcribe(str(v), language=idioma, beam_size=5, vad_filter=True)
            n = 0
            with open(s, "w", encoding="utf-8") as f:
                for n, seg in enumerate(segments, 1):
                    f.write(f"{n}\n{self._format_timestamp(seg.start)} --> {self._format_timestamp(seg.end)}\n"
                            f"{seg.text.strip()}\n\n")
                    log(f"[{self._format_timestamp(seg.start)}] {seg.text.strip()}")
            return n
        self._tarefa(self.turbo_log, "Legendas Turbo", fn, lambda n: f"{n} legendas geradas em {Path(s).name}", limpar=True)

    def gerar_karaoke(self):
        if not _instalado("whisperx"):
            messagebox.showerror("Erro", "pip install whisperx")
            return
        v = self._abrir()
        if not v:
            return
        s = self._salvar("Salvar ASS", ".ass", [("ASS", "*.ass")])
        if not s:
            return
        idioma, modelo = self.whisperx_idioma.get(), self.whisperx_modelo.get()
        device = "cuda" if self._cuda() else "cpu"

        def fn(log):
            import whisperx
            compute = "float16" if device == "cuda" else "int8"
            log(f"WhisperX {modelo} em {device} ({compute})...")
            model = whisperx.load_model(modelo, device, compute_type=compute, language=idioma)
            audio = whisperx.load_audio(str(v))
            result = model.transcribe(audio, language=idioma)
            ma, meta = whisperx.load_align_model(language_code=idioma, device=device)
            result = whisperx.align(result["segments"], ma, meta, audio, device)
            n = 0
            with open(s, "w", encoding="utf-8-sig") as f:
                f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
                        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,"
                        "Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
                        "MarginL,MarginR,MarginV,Encoding\n"
                        "Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,60,1\n\n"
                        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
                for seg in result["segments"]:
                    for w in seg.get("words", []):
                        if "start" not in w or "end" not in w:   # numeros/simbolos sem alinhamento
                            continue
                        palavra = w["word"].strip().replace("{", "(").replace("}", ")").replace("\n", " ")
                        f.write(f"Dialogue: 0,{self._format_ass_time(w['start'])},{self._format_ass_time(w['end'])},"
                                f"Default,,0,0,0,,{palavra}\n")
                        n += 1
            return n
        self._tarefa(self.whisperx_log, "WhisperX", fn, lambda n: f"Karaoke gerado ({n} palavras)")

    # ============================================================ acoes: download
    def obter_info_video(self):
        url = self.download_url.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Cole uma URL primeiro!")
            return
        if self.downloader is None:
            messagebox.showerror("Erro", "Downloader indisponivel (veja o log).")
            return

        def fn(log):
            self.downloader.log = log
            info = self.downloader.obter_info(url)
            for k in ["titulo", "autor", "duracao", "plataforma", "metodo"]:
                log(f"{k}: {info.get(k, '-')}")
            return info
        self._tarefa(self.download_log, "Info", fn, lambda i: i.get("titulo", "ok"), limpar=True)

    def baixar_video(self):
        url = self.download_url.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Cole uma URL primeiro!")
            return
        if self.downloader is None:
            messagebox.showerror("Erro", "Downloader indisponivel (veja o log).")
            return
        p = filedialog.askdirectory(title="Pasta de destino")
        if not p:
            return
        qualidade = self.download_qualidade.get()

        def fn(log):
            self.downloader.log = log
            return self.downloader.baixar_video(url, Path(p), qualidade)
        self._tarefa(self.download_log, "Download", fn, lambda a: f"Baixado: {a}", limpar=True)

    def baixar_playlist(self):
        url = self.download_url.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Cole uma URL!")
            return
        if self.downloader is None:
            messagebox.showerror("Erro", "Downloader indisponivel (veja o log).")
            return
        p = filedialog.askdirectory(title="Pasta de destino")
        if not p:
            return

        def fn(log):
            self.downloader.log = log
            return self.downloader.baixar_playlist(url, Path(p), 10)
        self._tarefa(self.download_log, "Playlist", fn, lambda a: f"{len(a)} videos baixados!", limpar=True)

    # ============================================================ acoes: suite (FFmpeg)
    def preview_moviepy(self):
        """Preview (nome mantido): ffplay ou player do sistema. Sem moviepy."""
        v = self._abrir("Video para preview")
        if not v:
            return
        try:
            info = info_midia(Path(v))
            self._escrever(self.auto_suite_log, f"{Path(v).name}: {info['duracao']:.1f}s | "
                                                f"{info['width']}x{info['height']} | {info['fps']:.2f} fps")
            self._escrever(self.auto_suite_log, f"Abrindo com {abrir_no_player(Path(v))}...")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Preview", str(e))

    def speed_ramp_moviepy(self):
        """Velocidade constante via FFmpeg (setpts + atempo). Sem moviepy."""
        v = self._abrir()
        if not v:
            return
        vel = simpledialog.askfloat("Velocidade", "Velocidade (0.25 = 4x lento, 2.0 = 2x rapido):",
                                    initialvalue=0.5, minvalue=0.1, maxvalue=8.0, parent=self.app.root)
        if not vel:
            return
        s = self._salvar()
        if not s:
            return

        def fn(log):
            info = info_midia(Path(v))
            cmd = ["ffmpeg", "-y", "-i", str(v), "-map", "0:v:0", "-vf", f"setpts=PTS/{vel}",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
            if info["tem_audio"]:
                cmd += ["-map", "0:a:0", "-af", cadeia_atempo(vel), "-c:a", "aac", "-b:a", "192k"]
            executar_com_progresso(cmd + [str(s)], log, info["duracao"] / vel)
            return s
        self._tarefa(self.auto_suite_log, "Speed", fn, f"Velocidade {vel:.2f}x aplicada: {Path(s).name}", limpar=True)

    def trim_moviepy(self):
        """Corte preciso ao frame via FFmpeg. Sem moviepy."""
        v = self._abrir()
        if not v:
            return
        try:
            duracao = info_midia(Path(v))["duracao"]
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Erro", f"Nao foi possivel ler o video: {e}")
            return
        ini = simpledialog.askfloat("Cortar", f"Inicio (s) - duracao total {duracao:.1f}s:", initialvalue=0.0,
                                    minvalue=0.0, maxvalue=duracao, parent=self.app.root)
        if ini is None:
            return
        fim = simpledialog.askfloat("Cortar", "Fim (s):", initialvalue=round(duracao, 2),
                                    minvalue=ini + 0.04, maxvalue=duracao, parent=self.app.root)
        if fim is None:
            return
        s = self._salvar()
        if not s:
            return

        def fn(log):
            info = info_midia(Path(v))
            cmd = ["ffmpeg", "-y", "-ss", f"{ini:.3f}", "-i", str(v), "-t", f"{fim - ini:.3f}", "-map", "0:v:0",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
            cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"] if info["tem_audio"] else []
            executar_com_progresso(cmd + [str(s)], log, fim - ini)
            return s
        self._tarefa(self.auto_suite_log, "Trim", fn, f"Clipe cortado: {fim - ini:.1f}s", limpar=True)

    def analisar_audio_pydub(self):
        """Analise EBU R128 real (LUFS/LRA/true peak). Sem pydub."""
        v = self._abrir("Audio/Video", MIDIA)
        if not v:
            return

        def fn(log):
            info = info_midia(Path(v))
            if not info["tem_audio"]:
                raise ValueError("Arquivo sem trilha de audio.")
            m = medir_loudness(Path(v))
            log("=" * 50)
            log(f"ANALISE DE AUDIO - {Path(v).name}")
            log(f"Duracao:      {info['duracao']:.1f}s | Sample rate: {info['sample_rate']} Hz")
            if m["integrado"] is None:
                log("Audio digitalmente mudo.")
                return m
            log(f"Loudness:     {m['integrado']:.1f} LUFS (integrado)")
            log(f"Faixa (LRA):  {m['lra']:.1f} LU")
            log(f"True peak:    {m['true_peak']:.1f} dBTP")
            log("AVALIACAO POR PADRAO:")
            for nome, (alvo, tp) in PADROES_LOUDNESS.items():
                ok = abs(m["integrado"] - alvo) <= 1.0 and (m["true_peak"] or -99) <= tp
                log(f"  {'[OK]' if ok else '[!] '} {nome:10s} alvo {alvo:.0f} LUFS / {tp:.0f} dBTP")
            log("=" * 50)
            return m
        self._tarefa(self.auto_suite_log, "Analise de Audio", fn,
                     lambda m: "Analise concluida" if m["integrado"] is None else f"{m['integrado']:.1f} LUFS",
                     limpar=True)

    def normalizar_audio_pydub(self):
        """Normalizacao EBU R128 em 2 passadas; video copiado sem reencode."""
        v = self._abrir("Audio/Video", MIDIA)
        if not v:
            return
        tem_video = Path(v).suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm")
        tipos = MP4 + [("MOV", "*.mov")] if tem_video else [("MP3", "*.mp3"), ("WAV", "*.wav"), ("FLAC", "*.flac"), ("M4A", "*.m4a")]
        s = self._salvar("Salvar", ".mp4" if tem_video else ".mp3", tipos)
        if not s:
            return
        padrao = self.auto_audio_padrao.get()
        alvo, tp = padrao_loudness(padrao)
        self._tarefa(self.auto_suite_log, "Normalizar Audio",
                     lambda log: normalizar_loudness(Path(v), Path(s), alvo, tp, log),
                     f"Normalizado para {padrao} ({alvo:.0f} LUFS): {Path(s).name}", limpar=True)

    def editar_automatico_completo(self):
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        cfg = {"threshold_silencio": self.silencio_threshold.get(), "remover_pausas": True,
               "adicionar_transicoes": True, "transicao_tipo": "fade", "transicao_duracao": 0.3,
               "manter_minimo": 0.5}
        self._tarefa(self.auto_suite_log, "Edicao Automatica",
                     lambda log: AutoEditorAI(log).editar_automatico(Path(v), Path(s), cfg),
                     "Edicao concluida!", limpar=True)

    def color_grading_automatico(self):
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        self._tarefa(self.auto_suite_log, "Color Grading",
                     lambda log: AutoColorAI(log).aplicar_color_auto(Path(v), Path(s), "auto"),
                     "Color grading concluido!", limpar=True)

    def mixagem_automatica(self):
        v = self._abrir("Audio/Video", MIDIA)
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        padrao = self.auto_audio_padrao.get()
        self._tarefa(self.auto_suite_log, "Mixagem",
                     lambda log: AutoAudioAI(log).mixar_automatico(Path(v), Path(s), padrao),
                     f"Mixagem concluida ({padrao})!", limpar=True)

    def legendas_automaticas(self):
        if not self._ok(self.subtitles, "whisper_disponivel"):
            messagebox.showwarning("Aviso", "pip install openai-whisper")
            return
        v = self._abrir()
        if not v:
            return
        s = self._salvar()
        if not s:
            return
        estilo = self.auto_caption_estilo.get()
        self._tarefa(self.auto_suite_log, "Legendas Automaticas",
                     lambda log: AutoCaptionAI(log).gerar_legendas_auto(Path(v), Path(s), "pt", "base", estilo),
                     "Legendas concluidas!", limpar=True)

    def converter_todas_plataformas(self):
        v = self._abrir()
        if not v:
            return
        p = filedialog.askdirectory(title="Pasta de saida")
        if not p:
            return
        self._tarefa(self.auto_suite_log, "Plataformas",
                     lambda log: AutoFormatAI(log).converter_todas_plataformas(Path(v), Path(p)),
                     lambda a: f"{len(a)} versoes geradas!", limpar=True)

    # ============================================================ formatos de tempo
    def _format_timestamp(self, seconds):
        ms_total = int(round(seconds * 1000))
        h, ms_total = divmod(ms_total, 3_600_000)
        m, ms_total = divmod(ms_total, 60_000)
        s, ms = divmod(ms_total, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _format_ass_time(self, seconds):
        cs_total = int(round(seconds * 100))
        h, cs_total = divmod(cs_total, 360_000)
        m, cs_total = divmod(cs_total, 6000)
        s, cs = divmod(cs_total, 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


V76Patch = V73Patch  # nome novo, mesma classe
