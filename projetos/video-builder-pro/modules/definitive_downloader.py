from pathlib import Path

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
    """Procura perfis de navegador na pasta do usuário atual."""
    try:
        home = Path.home()
    except (OSError, RuntimeError):
        return None, None

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

    for browser, subpaths in perfis.items():
        for sub in subpaths:
            full = home / sub
            try:
                if full.is_dir():
                    return browser, str(full)
            except OSError:
                continue

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

        if INSTA_OK:
            self.log("[OK] instaloader disponivel")

    @property
    def disponivel(self):
        return YT_DLP_OK

    def _opcoes_base(self):
        """Opcoes base com cookies se disponivel."""
        opts = {"quiet": True}
        cookies_file = Path(__file__).parent.parent / "cookies.txt"
        if cookies_file.exists():
            opts["cookiefile"] = str(cookies_file)
            self.log(f"[OK] Usando cookies.txt: {cookies_file}")
        elif self.browser:
            opts["cookiesfrombrowser"] = (self.browser, self.browser_path)
        return opts

    def obter_info(self, url: str) -> dict:
        if not YT_DLP_OK:
            raise Exception("yt-dlp indisponível. Siga a instalação no README.")
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
            raise Exception("yt-dlp indisponível. Siga a instalação no README.")
        formatos = {
            "best":  "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "audio": "bestaudio/best",
        }
        saida = None

        def registrar_arquivo(caminho):
            nonlocal saida
            saida = Path(caminho)

        opts = self._opcoes_base()
        opts.update({
            "outtmpl": str(pasta / "%(title)s.%(ext)s"),
            "format": formatos.get(qualidade, formatos["best"]),
            "merge_output_format": "mp4",
            "post_hooks": [registrar_arquivo],
            "quiet": False,
        })

        self.log(f"Baixando: {url}")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        if saida is None or not saida.is_file():
            raise RuntimeError("O yt-dlp não retornou um arquivo de vídeo.")
        return saida

    def baixar_playlist(self, url: str, pasta: Path, max_videos: int = 10) -> list:
        if not YT_DLP_OK:
            raise Exception("yt-dlp indisponível. Siga a instalação no README.")
        arquivos = []

        def registrar_arquivo(caminho):
            arquivo = Path(caminho)
            if arquivo.is_file():
                arquivos.append(arquivo)

        opts = self._opcoes_base()
        opts.update({
            "outtmpl": str(pasta / "%(playlist_index)s_%(title)s.%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "playlistend": max_videos,
            "ignoreerrors": True,
            "post_hooks": [registrar_arquivo],
            "quiet": False,
        })

        self.log(f"Baixando playlist (max {max_videos}): {url}")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        if not arquivos:
            raise RuntimeError("Nenhum vídeo da playlist foi baixado. Consulte o erro do yt-dlp no terminal.")
        return arquivos
