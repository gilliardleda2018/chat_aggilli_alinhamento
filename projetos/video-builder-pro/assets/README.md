# Logotipo da Aggilli (usado nos instaladores)

Coloque aqui o arquivo **oficial**:

- `logo_aggilli.png` — PNG com fundo transparente, 512×512 px ou maior (ideal: 1024×1024), **ou**
- `logo_aggilli.svg` — vetor (convertido com `rsvg-convert`).

A partir dele, `instalador/gerar_icones.py` cria em `assets/gerados/` (pasta ignorada pelo git):

| Arquivo | Uso |
|---|---|
| `icone.ico` (16–256 px) | ícone do `.exe`, do instalador e dos atalhos no Windows |
| `icone_256.png` / `icone_512.png` | menu do Linux e ícone da janela do app |
| `assistente_grande*.bmp` | imagem lateral do assistente de instalação (Windows) |
| `assistente_pequeno*.bmp` | canto do cabeçalho do assistente (Windows) |

Sem o logo, só é possível gerar build de **teste** (`--sem-logo`), com um monograma
neutro "VB" que não representa a marca. Builds oficiais (tag `v*`) falham sem o logo.
