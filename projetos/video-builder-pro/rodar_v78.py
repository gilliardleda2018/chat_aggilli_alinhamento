#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher do Video Builder Pro v7.8: base (8 abas) + patch v7.6/7.7 (12 abas)
+ patch v7.8 Diretor IA (1 aba) = 21 abas.

O rodar_v77.py continua funcionando (20 abas, sem o Diretor IA).
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
