#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher do Video Builder Pro v7.8: base (8 abas) + patch v7.6/7.7 (12 abas)
+ patch v7.8 Diretor IA (1 aba) = 21 abas. E tambem o ponto de entrada do
executavel instalado (PyInstaller).

  python rodar_v78.py              abre o app
  python rodar_v78.py --verificar [arquivo.json]
                                   checa a instalacao SEM abrir janela (FFmpeg,
                                   modulos, estilos, transcritores). O executavel
                                   do Windows nao tem console: passe um arquivo
                                   para receber o resultado. Usado pelo CI.

O rodar_v77.py continua funcionando (20 abas, sem o Diretor IA).
"""

import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PASTA = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(PASTA))
sys.path.insert(0, str(PASTA / "modules"))


def verificar(destino: str = "") -> int:
    """Diagnostico em texto/JSON. Codigo de saida 0 = instalacao OK."""
    from ffmpeg_utils import pasta_app, preparar_ffmpeg_embutido
    rel = {"python": sys.version.split()[0], "empacotado": bool(getattr(sys, "frozen", False)),
           "pasta_app": str(pasta_app()), "ffmpeg_embutido": str(preparar_ffmpeg_embutido() or "")}
    ok = True
    for prog in ("ffmpeg", "ffprobe", "ffplay"):
        caminho = shutil.which(prog)
        rel[prog] = caminho or "NAO ENCONTRADO"
        if caminho and prog != "ffplay":
            r = subprocess.run([caminho, "-version"], capture_output=True, text=True)
            rel[prog + "_versao"] = (r.stdout.splitlines() or ["?"])[0][:80]
        elif prog != "ffplay":
            ok = False
    try:
        import tkinter  # noqa: F401
        import video_builder_pro_v7_suite as base
        import v76_patch  # noqa: F401
        import v78_diretor  # noqa: F401
        from diretor_ia import carregar_estilos
        from luts_manager import LUTManager
        from transcricao import backends_instalados
        rel["versao_app"] = base.VERSAO
        rel["estilos"] = sorted(carregar_estilos())
        rel["luts"] = len(LUTManager(lambda m: None).listar_luts())
        rel["transcritores"] = backends_instalados()
        ok = ok and len(rel["estilos"]) >= 4 and rel["luts"] >= 15
    except Exception:  # noqa: BLE001
        rel["erro_import"] = traceback.format_exc()[-1500:]
        ok = False
    rel["ok"] = ok
    texto = json.dumps(rel, ensure_ascii=False, indent=2)
    if destino:
        Path(destino).write_text(texto, encoding="utf-8")
    if sys.stdout is not None:          # None no executavel "windowed" do Windows
        print(texto)
    return 0 if ok else 1


def main():
    if "--verificar" in sys.argv:
        k = sys.argv.index("--verificar")
        return verificar(sys.argv[k + 1] if len(sys.argv) > k + 1 else "")
    from ffmpeg_utils import preparar_ffmpeg_embutido
    preparar_ffmpeg_embutido()          # FFmpeg que veio no instalador tem prioridade

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    try:
        from ffmpeg_utils import pasta_app
        icone = pasta_app() / "assets" / "icone_256.png"
        if icone.exists():
            root.iconphoto(True, tk.PhotoImage(file=str(icone)))
    except Exception:  # noqa: BLE001 - icone e cosmetico
        pass
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        root.withdraw()
        messagebox.showerror("Video Builder Pro",
                             "FFmpeg/ffprobe nao encontrados no PATH.\n\n"
                             "Windows: winget install Gyan.FFmpeg\nLinux: sudo apt install ffmpeg")
        return 1
    try:
        from video_builder_pro_v7_suite import VideoBuilderProV7
        from v76_patch import aplicar_patch
        from v78_diretor import aplicar_patch_v78
        app = VideoBuilderProV7(root)
        aplicar_patch(app)
        aplicar_patch_v78(app)
    except Exception:  # noqa: BLE001
        detalhe = traceback.format_exc()
        try:
            from ffmpeg_utils import obter_logger
            obter_logger().critical("falha ao iniciar:\n%s", detalhe)
        except Exception:  # noqa: BLE001
            pass
        root.withdraw()
        messagebox.showerror("Video Builder Pro - erro ao iniciar", detalhe[-1500:])
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
