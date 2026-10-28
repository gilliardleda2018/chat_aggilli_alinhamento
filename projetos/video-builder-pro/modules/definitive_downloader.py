from pathlib import Path
import subprocess
import shutil
import os

try:
    import yt_dlp
    YT_DLP_OK = True
except ImportError:
    YT_DLP_OK = False

try:
    import instaloader
    INSTA_OK = True
except ImportError:
    INSTA_OK = False


def _detectar_browser():
    """
    Detecta navegador e perfil correto, mesmo rodando como root.
    Procura nos perfis do usuario real (SUDO_USER ou home /home/*).
    """
    # Usuario real (pode ser diferente de root)
    usuario_real = os.environ.get("SUDO_USER") or os.environ.get("USER", "")
    homes_candidatos = []

    if usuario_real and usuario_real != "root":
        homes_candidatos.append(Path(f"/home/{usuario_real}"))

    # Fallback: varre /home/
    for home in Path("/home").iterdir():
        if home.is_dir() and home not in homes_candidatos:
            homes_candidatos.append(home)

    # Mapeamento: browser -> caminhos possiveis do perfil
    perfis = {
        "firefox": [
            ".mozilla/firefox",
            ".var/app/org.mozilla.firefox/.mozilla/firefox",
            "snap/firefox/common/.mozilla/firefox",
            ".config/mozilla/firefox",
        ],
        "chromium": [
            ".config/chromium",
            ".var/app/org.chromium.Chromium/config/chromium",
            "snap/chromium/current/.config/chromium",
        ],
        "chrome": [
            ".config/google-chrome",
            ".var/app/com.google.Chrome/config/google-chrome",
        ],
    }

    for home in homes_candidatos:
        for browser, subpaths in perfis.items():
            for sub in subpaths:
                full = home / sub
                if full.exists():
                    return browser, str(full)

    return None, None


class DefinitiveDownloader:
    def __init__(self, log_callback):
        self.log = log_callback
        self.browser = None
        self.browser_path = None

        if YT_DLP_OK:
            self.log("[OK] yt-dlp disponivel")
            browser, path = _detectar_browser()
            if browser:
                self.browser = browser
                self.browser_path = path
                self.log(f"[OK] Cookies: {browser} em {path}")
            else:
                self.log("[AVISO] Nenhum perfil de navegador encontrado.")
                self.log("[AVISO] Videos do YouTube podem falhar por bot-check.")
                self.log("[DICA] Exporte cookies manualmente:")
                self.log("  yt-dlp --cookies cookies.txt <URL>")
                self.log("  e use o arquivo cookies.txt no campo de cookies")

        if INSTA_OK:
            self.log("[OK] instaloader disponivel")

    def _opcoes_base(self):
        """Opcoes base com cookies se disponivel."""
        opts = {"quiet": True}
        if self.browser:
            opts["cookiesfrombrowser"] = (self.browser, self.browser_path)
        # Fallback: arquivo cookies.txt na pasta do app
        cookies_file = Path(__file__).parent.parent / "cookies.txt"
        if cookies_file.exists():
            opts["cookiefile"] = str(cookies_file)
            self.log(f"[OK] Usando cookies.txt: {cookies_file}")
        return opts

    def obter_info(self, url: str) -> dict:
        if not YT_DLP_OK:
            raise Exception("yt-dlp nao instalado: pip install yt-dlp")
        opts = self._opcoes_base()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "titulo": info.get("title", "Desconhecido"),
                "autor": info.get("uploader", "-"),
                "duracao": info.get("duration", 0),
                "plataforma": info.get("extractor", "-"),
                "metodo": f"yt-dlp ({self.browser or 'sem cookies'})",
            }

    def baixar_video(self, url: str, pasta: Path, qualidade: str = "best") -> Path:
        if not YT_DLP_OK:
            raise Exception("yt-dlp nao instalado: pip install yt-dlp")
        formatos = {
            "best":  "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "audio": "bestaudio/best",
        }
        saida = [None]

        def hook(d):
            if d["status"] == "finished":
                saida[0] = Path(d["filename"])

        opts = self._opcoes_base()
        opts.update({
            "outtmpl": str(pasta / "%(title)s.%(ext)s"),
            "format": formatos.get(qualidade, formatos["best"]),
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
            "quiet": False,
        })

        self.log(f"Baixando: {url}")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return saida[0] or pasta

    def baixar_playlist(self, url: str, pasta: Path, max_videos: int = 10) -> list:
        if not YT_DLP_OK:
            raise Exception("yt-dlp nao instalado: pip install yt-dlp")
        arquivos = []

        def hook(d):
            if d["status"] == "finished":
                arquivos.append(Path(d["filename"]))

        opts = self._opcoes_base()
        opts.update({
            "outtmpl": str(pasta / "%(playlist_index)s_%(title)s.%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "playlistend": max_videos,
            "ignoreerrors": True,
            "progress_hooks": [hook],
            "quiet": False,
        })

        self.log(f"Baixando playlist (max {max_videos}): {url}")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return arquivos
