# Logotipo da Aggilli (usado nos instaladores)

Arquivos oficiais (fundo transparente), versionados no repositório:

| Arquivo | Conteúdo | Uso |
|---|---|---|
| `logo_aggilli.png` | Símbolo + "AGGILLI INTELLIGENCE" (2100×615) | documentação; fallback de tudo |
| `simbolo_aggilli.png` | Só o símbolo (o "A" com a folha) | ícone do app, atalhos, cabeçalho do instalador |
| `texto_aggilli.png` | Só "AGGILLI INTELLIGENCE" | imagem lateral do instalador (abaixo do símbolo) |

**Origem e edição (03/11/2026):** logo enviado pelo usuário; a linha inferior "OBRAS INTELLIGENCE" foi
removida a pedido. Símbolo e nome foram separados automaticamente (componentes conectados do canal alfa),
preservando o brilho original. Os pixels totalmente transparentes têm a cor zerada, então nada fica
escondido sob a transparência.

Por que separar: o logo é horizontal (~3,4:1). Num ícone quadrado de 16–48 px, o nome vira um borrão;
o símbolo continua reconhecível.

`instalador/gerar_icones.py` gera a partir deles, em `assets/gerados/` (pasta ignorada pelo git):
`icone.ico` (16–256 px), `icone_256.png`, `icone_512.png` e as imagens do assistente do Windows (1x/2x DPI).

Para trocar o logo: substitua os PNGs (mantendo os nomes) e gere uma nova tag `v*`.
