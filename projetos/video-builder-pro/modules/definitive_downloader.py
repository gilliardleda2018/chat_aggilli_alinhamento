#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEFINITIVE DOWNLOADER - Video Builder Pro v7.7
Download via yt-dlp (YouTube, Instagram, TikTok, Vimeo, X...).

Correcoes v7.7 (ver CHANGELOG.md, secao "definitive_downloader.py"):
  - Windows: Path("/home").iterdir() levantava FileNotFoundError no
    __init__, o downloader virava None e a aba mostrava "pip install yt-dlp"
    (mensagem falsa). Agora ha perfis de navegador por sistema (Windows,
    macOS, Linux/Flatpak/Snap).
  - Seguranca: rodando como root, varria /home/* e usava os cookies do
    PRIMEIRO usuario encontrado (sessao de outra pessoa). Agora usa apenas
    o home do usuario real (SUDO_USER via pwd, ou o proprio usuario).
  - cookies.txt com permissao 644 (legivel por qualquer usuario local) e
    corrigido para 600 automaticamente, com aviso no log. Local preferido:
    ~/.video_builder_pro/cookies.txt (fora da pasta do app/repositorio).
  - cookies.txt e cookies do navegador eram usados juntos: se o banco do
    navegador estivesse bloqueado/criptografado (Chrome no Windows), o
    download falhava mesmo com um cookies.txt valido. Agora cookies.txt tem
    prioridade, e ha nova tentativa sem cookies do navegador quando a
    leitura deles falha.
  - baixar_video retornava o arquivo intermediario (.f137.mp4) do hook
    'finished', que some apos o merge; agora retorna o arquivo final.
  - Progresso e avisos do yt-dlp passam pelo log da app (antes iam para o
    stdout, invisiveis na UI).
"""

import os
import re
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

try:
    from ffmpeg_utils import diretorio_config, permissao_aberta, proteger
except ImportError:
    from .ffmpeg_utils import diretorio_config, permissao_aberta, proteger

try:
    import yt_dlp
    YT_DLP_OK = True
except ImportError:
    yt_dlp = None
    YT_DLP_OK = False

try:
    import instaloader  # noqa: F401
    INSTA_OK = True
except ImportError:
    INSTA_OK = False


# Ordem importa: Firefox primeiro, porque o Chrome/Edge no Windows usam
# criptografia "app-bound" que o yt-dlp nem sempre consegue ler.
PERFIS = {
    "posix": {
        "firefox": [".mozilla/firefox", ".var/app/org.mozilla.firefox/.mozilla/firefox",
                    "snap/firefox/common/.mozilla/firefox", ".config/mozilla/firefox"],
        "chromium": [".config/chromium", ".var/app/org.chromium.Chromium/config/chromium",
                     "snap/chromium/current/.config/chromium"],
        "chrome": [".config/google-chrome", ".var/app/com.google.Chrome/config/google-chrome"],
        "brave": [".config/BraveSoftware/Brave-Browser"],
        "edge": [".config/microsoft-edge"],
    },
    "nt": {
        "firefox": ["AppData/Roaming/Mozilla/Firefox"],
        "chrome": ["AppData/Local/Google/Chrome/User Data"],
        "edge": ["AppData/Local/Microsoft/Edge/User Data"],
        "brave": ["AppData/Local/BraveSoftware/Brave-Browser/User Data"],
        "chromium": ["AppData/Local/Chromium/User Data"],
    },
    "darwin": {
        "firefox": ["Library/Application Support/Firefox"],
        "safari": ["Library/Containers/com.apple.Safari"],
        "chrome": ["Library/Application Support/Google/Chrome"],
        "edge": ["Library/Application Support/Microsoft Edge"],
        "brave": ["Library/Application Support/BraveSoftware/Brave-Browser"],
    },
}


def _home_usuario_real() -> Path:
    """Home do usuario que iniciou a app (nao o do root quando via sudo)."""
    sudo_user = os.environ.get("SUDO_USER")
    if os.name != "nt" and sudo_user and sudo_user != "root":
        try:
            import pwd
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except (ImportError, KeyError):
            pass
    return Path.home()


def _sistema() -> str:
    if os.name == "nt":
        return "nt"
    return "darwin" if sys.platform == "darwin" else "posix"


def _detectar_browser(home: Optional[Path] = None,
                      sistema: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """(navegador, caminho_do_perfil) no home do usuario real, ou (None, None)."""
    home = Path(home) if home else _home_usuario_real()
    for browser, subpaths in PERFIS[sistema or _sistema()].items():
        for sub in subpaths:
            full = home / sub
            if full.is_dir():
                return browser, str(full)
    return None, None


def localizar_cookies_txt() -> Optional[Path]:
    """cookies.txt em ~/.video_builder_pro (preferido) ou na pasta do app (legado)."""
    for c in (diretorio_config() / "cookies.txt", Path(__file__).resolve().parent.parent / "cookies.txt"):
        if c.is_file():
            return c
    return None


class _LoggerYDL:
    """Redireciona mensagens do yt-dlp para o log da aplicacao."""

    def __init__(self, log: Callable):
        self.log = log

    def debug(self, msg):
        if msg.startswith("[download] Destination") or msg.startswith("[Merger]"):
            self.log(msg)

    def info(self, msg):
        self.log(msg)

    def warning(self, msg):
        self.log(f"[AVISO] {msg}")

    def error(self, msg):
        self.log(f"[ERRO] {msg}")


class DefinitiveDownloader:
    def __init__(self, log_callback):
        self.log = log_callback
        self.browser, self.browser_path = None, None
        self.cookies_txt: Optional[Path] = None

        if not YT_DLP_OK:
            self.log("[AVISO] yt-dlp nao instalado: pip install -U yt-dlp")
            return
        self.log(f"[OK] yt-dlp {getattr(yt_dlp.version, '__version__', '?')} disponivel")

        self.cookies_txt = localizar_cookies_txt()
        if self.cookies_txt:
            self._proteger_cookies(self.cookies_txt)
            self.log(f"[OK] Cookies: {self.cookies_txt}")
        self.browser, self.browser_path = _detectar_browser()
        if self.browser:
            self.log(f"[OK] Perfil do navegador: {self.browser} em {self.browser_path}")
        elif not self.cookies_txt:
            self.log("[AVISO] Nenhum cookie disponivel: o YouTube pode pedir verificacao anti-bot.")
            self.log(f"[DICA] Exporte cookies (formato Netscape) para {diretorio_config() / 'cookies.txt'}")
        if INSTA_OK:
            self.log("[OK] instaloader disponivel")

    def _proteger_cookies(self, caminho: Path):
        if permissao_aberta(caminho):
            if proteger(caminho, 0o600):
                self.log(f"[SEGURANCA] {caminho.name} estava legivel por outros usuarios: permissao ajustada para 600")
            else:
                self.log(f"[SEGURANCA] {caminho} esta legivel por outros usuarios. Rode: chmod 600 '{caminho}'")

    def _opcoes_base(self, usar_navegador: bool = True) -> dict:
        """Opcoes comuns. cookies.txt tem prioridade sobre o navegador."""
        opts = {"quiet": True, "no_warnings": False, "logger": _LoggerYDL(self.log),
                "noprogress": True}
        if self.cookies_txt and self.cookies_txt.is_file():
            opts["cookiefile"] = str(self.cookies_txt)
        elif usar_navegador and self.browser:
            opts["cookiesfrombrowser"] = (self.browser, self.browser_path)
        return opts

    def _hook_progresso(self):
        estado = {"ultimo": -10}

        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total:
                    pct = int(d.get("downloaded_bytes", 0) * 100 / total)
                    if pct >= estado["ultimo"] + 10:
                        estado["ultimo"] = pct
                        self.log(f"  baixando: {pct}%")
            elif d.get("status") == "finished":
                estado["ultimo"] = -10
        return hook

    def _executar(self, url: str, opts: dict, download: bool):
        """Executa com nova tentativa sem cookies do navegador se eles falharem."""
        if not YT_DLP_OK:
            raise RuntimeError("yt-dlp nao instalado: pip install -U yt-dlp")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download), ydl
        except Exception as e:  # yt_dlp.utils.DownloadError e erros de cookies
            msg = str(e)
            if "cookiesfrombrowser" in opts and re.search(r"cookie|decrypt|keyring|locked", msg, re.I):
                self.log(f"[AVISO] Falha ao ler cookies do {self.browser}: tentando sem eles...")
                opts = {k: v for k, v in opts.items() if k != "cookiesfrombrowser"}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=download), ydl
            if re.search(r"JavaScript|JS runtime|n challenge|nsig", msg, re.I):
                raise RuntimeError(f"{msg}\nDica: atualize o yt-dlp (pip install -U yt-dlp) e instale "
                                   "um runtime JavaScript (ex.: deno) exigido pelo YouTube.") from e
            if re.search(r"Sign in to confirm|bot", msg, re.I):
                raise RuntimeError(f"{msg}\nDica: o YouTube pediu verificacao. Exporte cookies para "
                                   f"{diretorio_config() / 'cookies.txt'}") from e
            raise

    @staticmethod
    def _arquivos_finais(info: dict, ydl) -> List[Path]:
        """Arquivos finais (apos merge) a partir do info_dict."""
        arquivos = []
        for entrada in (info.get("entries") or [info]):
            if not entrada:
                continue
            for req in entrada.get("requested_downloads") or []:
                if req.get("filepath"):
                    arquivos.append(Path(req["filepath"]))
                    break
            else:
                if entrada.get("filepath"):
                    arquivos.append(Path(entrada["filepath"]))
                else:
                    arquivos.append(Path(ydl.prepare_filename(entrada)).with_suffix(".mp4"))
        return arquivos

    def obter_info(self, url: str) -> dict:
        info, _ = self._executar(url, self._opcoes_base(), download=False)
        origem = "cookies.txt" if self.cookies_txt else (self.browser or "sem cookies")
        return {"titulo": info.get("title", "Desconhecido"), "autor": info.get("uploader", "-"),
                "duracao": info.get("duration", 0), "plataforma": info.get("extractor", "-"),
                "metodo": f"yt-dlp ({origem})"}

    def baixar_video(self, url: str, pasta: Path, qualidade: str = "best") -> Path:
        formatos = {
            "best": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "audio": "bestaudio/best",
        }
        opts = self._opcoes_base()
        opts.update({"outtmpl": str(Path(pasta) / "%(title).150B [%(id)s].%(ext)s"),
                     "format": formatos.get(qualidade, formatos["best"]),
                     "progress_hooks": [self._hook_progresso()], "noplaylist": True,
                     "windowsfilenames": True})
        if qualidade == "audio":
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
        else:
            opts["merge_output_format"] = "mp4"
        self.log(f"Baixando: {url}")
        info, ydl = self._executar(url, opts, download=True)
        arquivos = self._arquivos_finais(info, ydl)
        return arquivos[0] if arquivos else Path(pasta)

    def baixar_playlist(self, url: str, pasta: Path, max_videos: int = 10) -> list:
        opts = self._opcoes_base()
        opts.update({"outtmpl": str(Path(pasta) / "%(playlist_index)03d_%(title).150B.%(ext)s"),
                     "format": "bestvideo+bestaudio/best", "merge_output_format": "mp4",
                     "playlistend": max_videos, "ignoreerrors": True,
                     "progress_hooks": [self._hook_progresso()], "windowsfilenames": True})
        self.log(f"Baixando playlist (max {max_videos}): {url}")
        info, ydl = self._executar(url, opts, download=True)
        return [a for a in self._arquivos_finais(info or {}, ydl) if a.exists()]
