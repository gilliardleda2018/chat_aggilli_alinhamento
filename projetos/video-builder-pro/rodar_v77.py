#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher do Video Builder Pro v7.7: app base (8 abas) + patch (12 abas).

O rodar_v76.py local continua funcionando: aplicar_patch() e V73Patch
mantiveram os nomes. Este launcher acrescenta:
  - verificacao do FFmpeg antes de abrir a janela;
  - erro de inicializacao mostrado em janela e gravado no log
    (~/.video_builder_pro/logs/video_builder.log), em vez de sumir no console;
  - funciona de qualquer pasta (usa o caminho deste arquivo).
"""

import shutil
import sys
import traceback
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))
sys.path.insert(0, str(PASTA / "modules"))


def main():
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        root.withdraw()
        messagebox.showerror("Video Builder Pro",
                             "FFmpeg/ffprobe nao encontrados no PATH.\n\n"
                             "Windows: winget install Gyan.FFmpeg\n"
                             "Linux: sudo apt install ffmpeg")
        return 1
    try:
        from video_builder_pro_v7_suite import VideoBuilderProV7
        from v76_patch import aplicar_patch
        app = VideoBuilderProV7(root)
        aplicar_patch(app)
    except Exception:  # noqa: BLE001 - mostrar qualquer falha de inicializacao
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
