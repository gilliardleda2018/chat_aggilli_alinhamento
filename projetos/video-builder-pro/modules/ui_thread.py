#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI THREAD - Video Builder Pro v7.7

Tkinter NAO e thread-safe: na v7.6 cerca de 30 threads de trabalho
chamavam widget.insert/delete, messagebox e update_idletasks diretamente,
causando travamentos e crashes intermitentes ("main thread is not in main
loop", "Tcl_AsyncDelete"). Este modulo centraliza a regra:

  * threads de trabalho NUNCA tocam em widgets: usam ui.chamar(fn, ...);
  * a thread principal drena a fila a cada 50 ms com root.after.
"""

import queue
import threading
import traceback
from typing import Callable, Optional

try:
    from ffmpeg_utils import obter_logger
except ImportError:
    from .ffmpeg_utils import obter_logger


class UIDispatcher:
    def __init__(self, root, intervalo_ms: int = 50):
        self.root = root
        self.intervalo = intervalo_ms
        self.fila: "queue.Queue" = queue.Queue()
        self._thread_ui = threading.current_thread()
        self.threads: list = []
        self.root.after(self.intervalo, self._drenar)

    def na_thread_ui(self) -> bool:
        return threading.current_thread() is self._thread_ui

    def chamar(self, fn: Callable, *args, **kwargs):
        """Executa fn na thread da UI (imediato se ja estiver nela)."""
        if self.na_thread_ui():
            return fn(*args, **kwargs)
        self.fila.put((fn, args, kwargs))
        return None

    def _drenar(self):
        try:
            while True:
                fn, args, kwargs = self.fila.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception:  # um erro de UI nao pode parar a fila
                    obter_logger().error("erro em callback de UI:\n%s", traceback.format_exc())
        except queue.Empty:
            pass
        self.root.after(self.intervalo, self._drenar)

    def em_segundo_plano(self, tarefa: Callable, ao_erro: Optional[Callable[[Exception], None]] = None,
                         nome: str = "tarefa") -> threading.Thread:
        """Roda tarefa numa thread daemon; excecoes sao logadas e repassadas a ao_erro (na UI)."""
        def _alvo():
            try:
                tarefa()
            except Exception as e:  # noqa: BLE001 - reportado ao usuario
                obter_logger().error("falha em %s:\n%s", nome, traceback.format_exc())
                if ao_erro:
                    self.chamar(ao_erro, e)
        t = threading.Thread(target=_alvo, daemon=True, name=nome)
        self.threads = [x for x in self.threads if x.is_alive()] + [t]
        t.start()
        return t

    def aguardar(self, timeout: float = 600):
        """Usado em testes: espera as threads e drena a fila."""
        for t in list(self.threads):
            t.join(timeout)
        self._drenar_sem_reagendar()

    def _drenar_sem_reagendar(self):
        while not self.fila.empty():
            fn, args, kwargs = self.fila.get_nowait()
            fn(*args, **kwargs)
