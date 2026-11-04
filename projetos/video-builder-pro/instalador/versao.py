#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le a versao do app (VERSAO em video_builder_pro_v7_suite.py), imprime-a e gera
instalador/versao_windows.txt: metadados do .exe no Windows (Propriedades >
Detalhes: empresa "Aggilli Intelligence", produto, versao).

Uso: python instalador/versao.py   ->  imprime "7.8.1"
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMPRESA = "Aggilli Intelligence"
PRODUTO = "Video Builder Pro"


def versao() -> str:
    texto = (RAIZ / "video_builder_pro_v7_suite.py").read_text(encoding="utf-8")
    m = re.search(r'^VERSAO\s*=\s*"([\d.]+)"', texto, re.M)
    if not m:
        raise SystemExit("VERSAO nao encontrada em video_builder_pro_v7_suite.py")
    return m.group(1)


def gerar_versao_windows(v: str) -> Path:
    partes = [int(x) for x in v.split(".")] + [0, 0, 0]
    tupla = tuple(partes[:4])
    conteudo = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tupla}, prodvers={tupla}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604b0', [
      StringStruct('CompanyName', '{EMPRESA}'),
      StringStruct('FileDescription', '{PRODUTO} - editor de video com IA'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'VideoBuilderPro'),
      StringStruct('LegalCopyright', 'Copyright (c) {EMPRESA}'),
      StringStruct('OriginalFilename', 'VideoBuilderPro.exe'),
      StringStruct('ProductName', '{PRODUTO}'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
"""
    destino = RAIZ / "instalador" / "versao_windows.txt"
    destino.write_text(conteudo, encoding="utf-8")
    return destino


if __name__ == "__main__":
    v = versao()
    gerar_versao_windows(v)
    print(v)
