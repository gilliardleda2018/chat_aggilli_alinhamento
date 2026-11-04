#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PATCH v7.8 - aba "Diretor IA" (21a aba). Uso: aplicar_patch_v78(app),
DEPOIS de aplicar_patch(app) da v7.6/v7.7.

Por que um patch separado: as 20 abas da v7.7 continuam identicas (sem
regressao), e o Diretor pode ser desligado so nao aplicando este patch.

Fluxo da aba:
  1. Adicionar video(s) brutos, escolher estilo (estilos/*.json) e briefing.
  2. "Analisar": transcricao palavra a palavra + corte de fala (vicios,
     repeticoes, pausas, retakes via Claude). Mostra o que sera removido.
  3. "Editar automaticamente": Diretor planeja -> render (motor v7.7) ->
     Revisor da nota -> refaz ate a nota minima ou o limite de tentativas.
     Gera <saida>.diretor.md / .json documentando cada decisao.
  4. "Enviar para a Timeline": leva o plano para a aba Timeline para ajuste
     manual fino (in/out, ordem, velocidade...) e render normal.

Sem chave da API: o Diretor usa heuristica (densidade de fala) e o Revisor
so a nota tecnica. Sem transcritor instalado: unidades por cena.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent / "modules"))

import tkinter as tk  # noqa: E402
from tkinter import filedialog, messagebox, scrolledtext, ttk  # noqa: E402

from diretor_ia import DiretorIA, carregar_estilos, validar_estilo  # noqa: E402
from transcricao import Transcritor, backends_instalados  # noqa: E402


def aplicar_patch_v78(app, transcritor: Optional[Transcritor] = None):
    return PatchDiretor(app, transcritor)


class PatchDiretor:
    def __init__(self, app, transcritor: Optional[Transcritor] = None):
        self.app = app
        self.log = app.log
        self.ui = app.ui
        self.transcritor = transcritor or Transcritor(self.log)
        self.estilos = carregar_estilos()
        self.arquivos: List[Path] = []
        self.diretor: Optional[DiretorIA] = None
        self.ultimo = None
        self.criar_aba(app.nb)
        self.log(f"PATCH v7.8 (Diretor IA) aplicado: {len(app.nb.tabs())} abas")

    # ------------------------------------------------------------ IA
    def _llm(self):
        """Claude (texto + visao) se houver chave; senao None (modo heuristico)."""
        if not self.app.claude.tem_chave():
            return None
        return self.app.claude.mensagem

    def _renderizar(self, clipes: List[Dict], estilo: Dict, saida: Path):
        """Callback do Diretor: plano -> ProjectTimeline -> motor de render v7.7."""
        import video_builder_pro_v7_suite as base
        tl = base.ProjectTimeline(
            clips=[base.ClipTimeline(arquivo=Path(c["arquivo"]), inicio=c["inicio"], fim=c["fim"],
                                     duracao=round(c["fim"] - c["inicio"], 3),
                                     nome=f"{Path(c['arquivo']).name} [{c['unidade']}]") for c in clipes],
            projeto_nome=saida.stem, resolucao=tuple(estilo["resolucao"]), fps=int(estilo["fps"]),
            look=estilo.get("look", ""), look_intensidade=float(estilo.get("look_intensidade", 1.0)),
            padrao_audio=estilo.get("padrao_audio", "YouTube"), normalizar_audio=True,
            transicao=estilo.get("transicao", ""), duracao_transicao=float(estilo.get("duracao_transicao") or 0.5),
            enquadramento=estilo.get("enquadramento", "ajustar"))
        preset = base.RenderPreset[self.preset.get()]
        arq = self.app.renderer.renderizar(tl, Path(saida), preset)
        return arq, self.app.renderer.ultimo_qc

    def _novo_diretor(self) -> DiretorIA:
        return DiretorIA(self.log, self._renderizar, self._llm(), self.transcritor)

    # ------------------------------------------------------------ UI
    def criar_aba(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Diretor IA  ")
        ttk.Label(frame, text="Diretor IA - edicao autonoma", font=("Helvetica", 16, "bold")).pack(pady=8)

        sf = ttk.LabelFrame(frame, text="Status", padding=8)
        sf.pack(fill=tk.X, padx=20, pady=4)
        bks = self.transcritor.disponiveis()
        ttk.Label(sf, text=f"[OK] Transcricao palavra a palavra: {', '.join(bks)}" if bks else
                  "[!] Sem transcritor: pip install whisperx (ou faster-whisper). Sem ele, so corte por cenas.",
                  foreground="green" if bks else "orange").pack(anchor=tk.W)
        self.status_ia = ttk.Label(sf, text="")
        self.status_ia.pack(anchor=tk.W)
        self._atualizar_status_ia()

        mf = ttk.LabelFrame(frame, text="1. Material bruto", padding=8)
        mf.pack(fill=tk.X, padx=20, pady=4)
        self.lista = tk.Listbox(mf, height=4, font=("Consolas", 9))
        self.lista.pack(fill=tk.X)
        bf = ttk.Frame(mf)
        bf.pack(fill=tk.X, pady=4)
        ttk.Button(bf, text="Adicionar videos...", command=self.adicionar).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="Usar os clipes da aba Midia", command=self.usar_midia).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="Limpar", command=self.limpar).pack(side=tk.LEFT, padx=3)

        cf = ttk.LabelFrame(frame, text="2. Direcao", padding=8)
        cf.pack(fill=tk.X, padx=20, pady=4)
        ttk.Label(cf, text="Estilo:").grid(row=0, column=0, sticky=tk.W)
        self._nomes_estilo = {v["nome"]: k for k, v in self.estilos.items()}
        self.estilo = tk.StringVar(value=next(iter(self._nomes_estilo), ""))
        ttk.Combobox(cf, textvariable=self.estilo, values=list(self._nomes_estilo), width=30,
                     state="readonly").grid(row=0, column=1, sticky=tk.W)
        ttk.Label(cf, text="Duracao alvo (s, vazio = do estilo):").grid(row=0, column=2, sticky=tk.E, padx=(12, 2))
        self.alvo = tk.StringVar(value="")
        ttk.Entry(cf, textvariable=self.alvo, width=8).grid(row=0, column=3, sticky=tk.W)
        ttk.Label(cf, text="Briefing:").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.brief = tk.Text(cf, height=3, width=80)
        self.brief.grid(row=1, column=1, columnspan=5, sticky=tk.W, pady=4)
        self.idioma = tk.StringVar(value="pt")
        self.modelo = tk.StringVar(value="small")
        self.retakes = tk.BooleanVar(value=True)
        self.visao = tk.BooleanVar(value=True)
        self.tentativas = tk.IntVar(value=2)
        self.preset = tk.StringVar(value="BALANCED")
        linha = ttk.Frame(cf)
        linha.grid(row=2, column=0, columnspan=6, sticky=tk.W)
        ttk.Label(linha, text="Idioma:").pack(side=tk.LEFT)
        ttk.Combobox(linha, textvariable=self.idioma, values=["pt", "en", "es"], width=4).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(linha, text="Modelo:").pack(side=tk.LEFT)
        ttk.Combobox(linha, textvariable=self.modelo, values=["base", "small", "medium", "large-v3", "turbo"],
                     width=9).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(linha, text="Retakes (IA)", variable=self.retakes).pack(side=tk.LEFT)
        ttk.Checkbutton(linha, text="Revisao visual (IA)", variable=self.visao).pack(side=tk.LEFT, padx=6)
        ttk.Label(linha, text="Tentativas:").pack(side=tk.LEFT)
        ttk.Spinbox(linha, from_=1, to=4, textvariable=self.tentativas, width=3).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(linha, text="Qualidade:").pack(side=tk.LEFT)
        ttk.Combobox(linha, textvariable=self.preset, values=["DRAFT", "FAST", "BALANCED", "HIGH_QUALITY"],
                     width=12, state="readonly").pack(side=tk.LEFT)

        af = ttk.LabelFrame(frame, text="3. Acoes", padding=8)
        af.pack(fill=tk.X, padx=20, pady=4)
        ttk.Button(af, text="Analisar (transcrever + corte de fala)", command=self.analisar).pack(side=tk.LEFT, padx=3)
        ttk.Button(af, text="EDITAR AUTOMATICAMENTE...", command=self.editar).pack(side=tk.LEFT, padx=3)
        ttk.Button(af, text="Enviar para a Timeline", command=self.enviar_timeline).pack(side=tk.LEFT, padx=3)
        ttk.Button(af, text="Abrir relatorio", command=self.abrir_relatorio).pack(side=tk.LEFT, padx=3)

        self.saida_log = scrolledtext.ScrolledText(frame, height=14, font=("Consolas", 9))
        self.saida_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        self.saida_log.insert(tk.END, "Adicione o material bruto, escolha o estilo e clique em EDITAR AUTOMATICAMENTE.\n")

    def _atualizar_status_ia(self):
        if self.app.claude.tem_chave():
            self.status_ia.config(text=f"[OK] Claude ({self.app.claude.modelo()}): direcao, retakes e revisao visual",
                                  foreground="green")
        else:
            self.status_ia.config(text="[!] Sem chave da API (aba IA): plano heuristico e revisao so tecnica",
                                  foreground="orange")

    def _escrever(self, msg: str):
        def _ui():
            self.saida_log.insert(tk.END, f"{msg}\n")
            self.saida_log.see(tk.END)
        self.ui.chamar(_ui)

    def _log(self, msg):
        self.log(msg)
        self._escrever(str(msg))

    def _estilo_atual(self) -> Dict:
        chave = self._nomes_estilo.get(self.estilo.get())
        estilo = validar_estilo(dict(self.estilos.get(chave, {})))
        if self.alvo.get().strip():
            try:
                estilo["duracao_alvo"] = float(self.alvo.get().replace(",", "."))
            except ValueError:
                raise ValueError("Duracao alvo invalida")
        return estilo

    def _atualizar_lista(self):
        self.lista.delete(0, tk.END)
        for a in self.arquivos:
            self.lista.insert(tk.END, a.name)
        self.diretor = None  # material mudou: reanalisar

    # ------------------------------------------------------------ acoes
    def adicionar(self):
        from ffmpeg_utils import tipos_video
        for f in filedialog.askopenfilenames(filetypes=tipos_video()):
            self.arquivos.append(Path(f))
        self._atualizar_lista()

    def usar_midia(self):
        self.arquivos = list(dict.fromkeys(self.app.videos))
        self._atualizar_lista()

    def limpar(self):
        self.arquivos = []
        self._atualizar_lista()

    def _validar(self) -> bool:
        if not self.arquivos:
            messagebox.showwarning("Diretor IA", "Adicione pelo menos um video.")
            return False
        return True

    def analisar(self):
        if not self._validar():
            return
        try:
            estilo = self._estilo_atual()
        except ValueError as e:
            messagebox.showerror("Diretor IA", str(e))
            return
        self._atualizar_status_ia()
        self.diretor = self._novo_diretor()
        self.diretor.log = self._log
        self.diretor.indexador.log = self._log
        arquivos, idioma, modelo, ret = list(self.arquivos), self.idioma.get(), self.modelo.get(), self.retakes.get()

        def tarefa():
            ind = self.diretor.analisar(arquivos, estilo, idioma, modelo, ret)
            for a in ind.arquivos:
                c = a.get("corte")
                if c:
                    self._escrever(f"{a['nome']}: {c['duracao_original']:.1f}s -> {c['duracao_final']:.1f}s "
                                   f"{c['resumo_por_motivo']}")
                    for x in [x for x in c["cortes"] if x["texto"]][:30]:
                        self._escrever(f"   - {x['inicio']:.2f}s [{x['motivo']}] \"{x['texto']}\"")
                for av in a.get("avisos", []):
                    self._escrever(f"   AVISO: {av}")
            self._escrever(f"{len(ind.unidades)} unidades prontas para o Diretor.")
            self.ui.chamar(messagebox.showinfo, "Diretor IA", "Analise concluida (veja o log da aba).")
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Diretor IA", str(e)),
                                 nome="diretor_analise")

    def editar(self, saida: Optional[str] = None):
        if not self._validar():
            return
        try:
            estilo = self._estilo_atual()
        except ValueError as e:
            messagebox.showerror("Diretor IA", str(e))
            return
        saida = saida or filedialog.asksaveasfilename(title="Salvar video editado", defaultextension=".mp4",
                                                      filetypes=[("MP4", "*.mp4")])
        if not saida:
            return
        self._atualizar_status_ia()
        if self.diretor is None:
            self.diretor = self._novo_diretor()
        else:  # a chave pode ter sido salva depois da analise
            llm = self._llm()
            self.diretor.llm = self.diretor.diretor.llm = self.diretor.revisor.llm = self.diretor.indexador.llm = llm
        for obj in (self.diretor, self.diretor.indexador, self.diretor.diretor, self.diretor.revisor):
            obj.log = self._log
        args = dict(brief=self.brief.get("1.0", tk.END).strip(), max_tentativas=int(self.tentativas.get()),
                    usar_visao=self.visao.get(), idioma=self.idioma.get(), modelo=self.modelo.get(),
                    detectar_retakes=self.retakes.get(), estilo_id=self._nomes_estilo.get(self.estilo.get(), ""))
        arquivos = list(self.arquivos)

        def tarefa():
            r = self.diretor.executar(arquivos, estilo, Path(saida), **args)
            self.ultimo = r
            v = r.versoes[r.melhor - 1]
            self.ui.chamar(messagebox.showinfo, "Diretor IA",
                           f"Video pronto: {r.final.name}\nVersao {r.melhor} de {len(r.versoes)}, nota "
                           f"{v.revisao.nota:.1f}\n\nRelatorio: {r.relatorio_md.name}")
        self._escrever("Iniciando edicao automatica...")
        self.ui.em_segundo_plano(tarefa, ao_erro=lambda e: messagebox.showerror("Diretor IA", str(e)),
                                 nome="diretor_edicao")

    def enviar_timeline(self):
        """Leva a melhor versao para a Timeline (ajuste fino manual + render normal)."""
        if not self.ultimo or not self.diretor or not self.diretor.indice:
            messagebox.showwarning("Diretor IA", "Rode 'Editar automaticamente' primeiro.")
            return
        import video_builder_pro_v7_suite as base
        v = self.ultimo.versoes[self.ultimo.melhor - 1]
        estilo = self._estilo_atual()
        clips = []
        for c in v.plano.clipes(self.diretor.indice):
            dur_fonte = next((a["duracao"] for a in self.diretor.indice.arquivos if a["arquivo"] == c["arquivo"]), 0)
            clips.append(base.ClipTimeline(arquivo=Path(c["arquivo"]), inicio=c["inicio"], fim=c["fim"],
                                           duracao=round(c["fim"] - c["inicio"], 3),
                                           nome=f"{Path(c['arquivo']).name} [{c['unidade']}]", duracao_fonte=dur_fonte))
        app = self.app
        app.clips = clips
        app.resolucao_var.set(f"{estilo['resolucao'][0]}x{estilo['resolucao'][1]}")
        app.fps_var.set(str(estilo["fps"]))
        app.audio_standard.set(estilo["padrao_audio"])
        app.audio_normalizar.set(True)
        app.aplicar_lut(estilo.get("look") or "Nenhum")      # id do look (o render aceita id ou nome)
        app.look_intensidade.set(float(estilo.get("look_intensidade", 1.0)))
        app.enquadramento_var.set(estilo["enquadramento"])
        nomes = {v: k for k, v in app._transicao_por_nome.items()}
        app.transicao_var.set(nomes.get(estilo.get("transicao", ""), app.TRANSICAO_NENHUMA))
        if estilo.get("duracao_transicao"):
            app.transicao_dur_var.set(float(estilo["duracao_transicao"]))
        app._atualizar_listas()
        self._escrever(f"{len(clips)} clipes enviados para a Timeline (estilo {estilo['nome']}).")
        messagebox.showinfo("Diretor IA", f"{len(clips)} clipes na aba Timeline. Ajuste e renderize.")

    def abrir_relatorio(self):
        if not self.ultimo:
            messagebox.showwarning("Diretor IA", "Nenhum relatorio gerado ainda.")
            return
        try:
            import os
            import subprocess
            p = self.ultimo.relatorio_md
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])
        except OSError:
            messagebox.showinfo("Relatorio", str(self.ultimo.relatorio_md))
