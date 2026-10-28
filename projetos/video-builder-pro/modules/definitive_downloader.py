from pathlib import Path
import subprocess
import shutil

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
    """Detecta qual navegador esta disponivel para extrair cookies."""
    for browser in ("firefox", "chromium", "chromium-browser", "chrome", "brave"):
        if shutil.which(browser):
            # Retorna nome compativel com yt-dlp
            if "chromium" in browser:
                return "chromium"
            if browser == "chromium-browser":
                return "chromium"
            return browser
    return None


class DefinitiveDownloader:
    def __init__(self, log_callback):
        self.log = log_callback
        self.browser = _detectar_browser()
        if YT_DLP_OK:
            self.log(f"[OK] yt-dlp disponivel")
            if self.browser:
                self.log(f"[OK] Cookies do {self.browser} serao usados automaticamente")
            else:
                self.log("[AVISO] Nenhum navegador detectado para cookies (pode falhar no YouTube)")
        if INSTA_OK:
            self.log("[OK] instaloader disponivel")

    def _opcoes_base(self):
        """Opcoes base do yt-dlp com suporte a cookies."""
        opts = {"quiet": True}
        if self.browser:
            opts["cookiesfrombrowser"] = (self.browser,)
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
