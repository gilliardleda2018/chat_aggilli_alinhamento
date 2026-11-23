"""Inicializa o aplicativo base com as abas do Video Builder Pro v7.6."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os
import sys
import tkinter as tk


def criar_app(root):
    runtime = Path(__file__).resolve().parents[2] / ".video_builder_pro" / "runtime"
    deno = runtime / ("deno.exe" if os.name == "nt" else "deno")
    if deno.is_file():
        os.environ["PATH"] = os.pathsep.join((str(runtime), os.environ.get("PATH", "")))
    dependencias = runtime / "python"
    if dependencias.is_dir():
        sys.path.insert(0, str(dependencias))

    from v76_patch import aplicar_patch

    arquivo_base = Path(__file__).with_name("video_builder_pro_v7.1_suite.py")
    spec = spec_from_file_location("video_builder_base", arquivo_base)
    base = module_from_spec(spec)
    sys.modules[spec.name] = base
    spec.loader.exec_module(base)

    app = base.VideoBuilderProV7(root)
    app.patch_v76 = aplicar_patch(app)
    root.title("Video Builder Pro v7.6")
    return app


def main():
    root = tk.Tk()
    app = criar_app(root)
    app.root.mainloop()


if __name__ == "__main__":
    main()
