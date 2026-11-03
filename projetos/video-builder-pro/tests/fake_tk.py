"""Stub minimo de tkinter para testar a UI sem display.

Registra o que a aplicacao faz (textos inseridos, messageboxes, dialogos)
para que os testes possam verificar o comportamento real dos callbacks.
"""

import sys
import types
from collections import defaultdict, deque

# ---------------------------------------------------------------- estado global
dialogos = defaultdict(deque)   # nome da funcao -> fila de respostas
mensagens = []                  # (tipo, titulo, texto)


def responder(funcao, *valores):
    """Enfileira respostas para filedialog/simpledialog (ex.: askopenfilename)."""
    dialogos[funcao].extend(valores)


def resetar():
    dialogos.clear()
    mensagens.clear()


# ---------------------------------------------------------------- variaveis
class _Var:
    _padrao = ""

    def __init__(self, master=None, value=None, name=None):
        self._v = self._padrao if value is None else value
        self._traces = []

    def get(self):
        return self._v

    def set(self, v):
        self._v = v
        for cb in self._traces:
            cb()

    def trace_add(self, modo, cb):
        self._traces.append(lambda: cb(None, None, modo))


class StringVar(_Var):
    _padrao = ""


class DoubleVar(_Var):
    _padrao = 0.0

    def get(self):
        return float(self._v)


class IntVar(_Var):
    _padrao = 0

    def get(self):
        return int(self._v)


class BooleanVar(_Var):
    _padrao = False

    def get(self):
        return bool(self._v)


# ---------------------------------------------------------------- widgets
class Widget:
    def __init__(self, master=None, *a, **kw):
        self.master = master
        self.kw = dict(kw)
        self._texto = ""
        self._itens = []
        self._abas = []
        self._sel = ()
        self._tree = {}
        self._ordem = []
        self._after = []
        var = kw.get("textvariable")
        self._var = var

    # geometria / config: no-op
    def pack(self, *a, **kw): return None
    def grid(self, *a, **kw): return None
    def place(self, *a, **kw): return None
    def pack_propagate(self, *a): return None
    def grid_columnconfigure(self, *a, **kw): return None
    def columnconfigure(self, *a, **kw): return None
    def bind(self, *a, **kw): return None
    def focus_set(self): return None
    def destroy(self): return None
    def grab_set(self): return None
    def geometry(self, *a): return None
    def title(self, *a): return None
    def transient(self, *a): return None
    def protocol(self, *a, **kw): return None
    def update_idletasks(self): return None
    def update(self): return None
    def winfo_width(self): return 1000
    def winfo_height(self): return 300
    def clipboard_clear(self): return None
    def clipboard_append(self, t): self._clip = t
    def quit(self): return None
    def mainloop(self): return None
    def wait_window(self, w=None): return None
    def see(self, *a): return None
    def yview(self, *a): return None
    def set(self, *a): return None

    def config(self, **kw):
        self.kw.update(kw)
    configure = config

    def cget(self, k):
        return self.kw.get(k)

    def __getitem__(self, k):
        return self.kw.get(k)

    def __setitem__(self, k, v):
        self.kw[k] = v

    # after: executado sob demanda pelo teste (root.processar_after())
    def after(self, ms, fn=None, *args):
        if fn is not None:
            self._after.append((fn, args))
        return f"after#{len(self._after)}"

    def after_cancel(self, ident):
        return None

    def processar_after(self, limite=50):
        for _ in range(limite):
            if not self._after:
                return
            pend, self._after = self._after, []
            for fn, args in pend:
                fn(*args)

    # Text / Entry
    def insert(self, idx, texto, *tags):
        if isinstance(self, Listbox):
            self._itens.append(texto)
        elif self._var is not None:
            self._var.set(str(self._var.get()) + str(texto))
        else:
            self._texto += str(texto)

    def delete(self, a, b=None):
        if isinstance(self, Listbox):
            if b is None and a not in ("end", END):
                del self._itens[int(a)]
            else:
                self._itens.clear()
        elif self._var is not None:
            self._var.set("")
        else:
            self._texto = ""

    def get(self, a=None, b=None):
        if isinstance(self, Listbox):
            return self._itens[int(a)] if a is not None else list(self._itens)
        if self._var is not None:
            return self._var.get()
        return self._texto

    # Listbox
    def curselection(self):
        return self._sel

    def selection_set(self, i):
        self._sel = (int(i),)

    def size(self):
        return len(self._itens)

    # Notebook
    def add(self, child, **kw):
        self._abas.append(kw.get("text", ""))

    def select(self, idx=None):
        self._selecionada = idx

    def tabs(self):
        return list(self._abas)

    def tab(self, idx, **kw):
        return None

    # Canvas
    def create_rectangle(self, *a, **kw): return 1
    def create_text(self, *a, **kw): return 1
    def create_line(self, *a, **kw): return 1

    # Treeview
    def heading(self, *a, **kw): return None
    def column(self, *a, **kw): return None

    def get_children(self, item=""):
        return list(self._ordem)

    def item(self, iid, **kw):
        if kw:
            self._tree[iid].update(kw)
        return self._tree[iid]

    def selection(self):
        return self._sel

    # Menu
    def add_cascade(self, **kw): return None
    def add_command(self, **kw): return None
    def add_separator(self): return None


class Tk(Widget):
    pass


class Toplevel(Widget):
    pass


class Menu(Widget):
    pass


class Canvas(Widget):
    pass


class Listbox(Widget):
    pass


class Text(Widget):
    pass


class _Treeview(Widget):
    def insert(self, parent, idx, iid=None, values=(), text=""):
        iid = iid or f"I{len(self._ordem)}"
        self._tree[iid] = {"values": list(values), "text": text}
        self._ordem.append(iid)
        return iid

    def delete(self, *iids):
        for i in iids:
            self._tree.pop(i, None)
            if i in self._ordem:
                self._ordem.remove(i)

    def selection_set(self, iid):
        self._sel = (iid,)


END = "end"
for _nome in ("BOTH X Y LEFT RIGHT TOP BOTTOM W E N S NW NE SW SE CENTER HORIZONTAL "
              "VERTICAL WORD DISABLED NORMAL ACTIVE SINGLE EXTENDED BROWSE RIDGE SUNKEN").split():
    globals()[_nome] = _nome.lower()


class TclError(Exception):
    pass


def instalar():
    """Registra os modulos falsos em sys.modules (antes de importar a app)."""
    tk = types.ModuleType("tkinter")
    for k, v in list(globals().items()):
        if k.isupper() or k in ("Tk", "Toplevel", "Menu", "Canvas", "Listbox", "Text",
                                "StringVar", "DoubleVar", "IntVar", "BooleanVar", "TclError"):
            setattr(tk, k, v)
    tk.Frame = tk.Label = tk.Button = tk.Entry = tk.Scale = Widget

    ttk = types.ModuleType("tkinter.ttk")
    for nome in ("Frame LabelFrame Label Button Entry Combobox Scale Checkbutton Radiobutton "
                 "Notebook Scrollbar Separator Spinbox Progressbar Style").split():
        setattr(ttk, nome, type(nome, (Widget,), {}))
    ttk.Treeview = _Treeview

    st = types.ModuleType("tkinter.scrolledtext")
    st.ScrolledText = type("ScrolledText", (Widget,), {})

    fd = types.ModuleType("tkinter.filedialog")
    for nome in ("askopenfilename", "askopenfilenames", "asksaveasfilename", "askdirectory"):
        def _f(*a, _n=nome, **kw):
            fila = dialogos[_n]
            if fila:
                return fila.popleft()
            return () if _n == "askopenfilenames" else ""
        setattr(fd, nome, _f)

    mb = types.ModuleType("tkinter.messagebox")
    for nome in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel"):
        def _m(titulo="", texto="", *a, _n=nome, **kw):
            mensagens.append((_n, titulo, texto))
            return True
        setattr(mb, nome, _m)

    sd = types.ModuleType("tkinter.simpledialog")
    for nome in ("askfloat", "askstring", "askinteger"):
        def _s(*a, _n=nome, **kw):
            fila = dialogos[_n]
            return fila.popleft() if fila else None
        setattr(sd, nome, _s)

    tk.ttk, tk.scrolledtext, tk.filedialog, tk.messagebox, tk.simpledialog = ttk, st, fd, mb, sd
    sys.modules.update({
        "tkinter": tk, "tkinter.ttk": ttk, "tkinter.scrolledtext": st,
        "tkinter.filedialog": fd, "tkinter.messagebox": mb, "tkinter.simpledialog": sd,
    })
