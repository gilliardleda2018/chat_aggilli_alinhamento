# ROADMAP — Video Builder Pro

Definido em 23/10/2026. Base: análise em `BIBLIOTECAS_RECOMENDADAS.md`.

```
SPRINT 1  →  PySceneDetect   →  aba "Detectar Cenas" + QC melhorado
SPRINT 2  →  faster-whisper  →  aba "Legendas" (SRT + burn no render)
SPRINT 3  →  Auto-Editor     →  aba "Auto-Cut" (remoção de silêncio)
SPRINT 4  →  OTIO            →  exportar timeline .otio (DaVinci/Premiere)
SPRINT 5  →  insp. clippyme  →  aba "Shorts" (9:16 + auto-crop no rosto)
```

## Por que essa ordem

1. **SceneDetect primeiro** — `pip install`, ~30 linhas de integração, resolve 2 pendências (split automático + QC real).
2. **Whisper** — maior valor percebido pelo usuário final (legendas automáticas).
3. **Auto-Cut** — diferencial competitivo (edição automática por áudio).
4. **OTIO** — profissionaliza o projeto (interoperabilidade com NLEs).
5. **Shorts** — aproveita a trend de conteúdo vertical; depende das sprints 1 e 2.

## Checklist por sprint

- [ ] Protótipo em script separado funcionando
- [ ] Teste com vídeo real do usuário
- [ ] Integração na UI (aba nova ou botão)
- [ ] Log funcionando (`video_builder_v7.log`)
- [ ] Dependência no `ATUALIZAR_DEPENDENCIAS.bat`
- [ ] Atualizar CHANGELOG.md e README.md
- [ ] Commit + push neste repositório
- [ ] Novo ponto de parada em `contextos/`

## Status

| Sprint | Status | Observação |
|--------|--------|------------|
| 1 — SceneDetect | ⏳ Aguardando OK do usuário | Sugerida como primeira |
| 2 — Whisper | 🔒 Bloqueada | Começa após Sprint 1 |
| 3 — Auto-Cut | 🔒 Bloqueada | |
| 4 — OTIO | 🔒 Bloqueada | |
| 5 — Shorts | 🔒 Bloqueada | Depende de 1 e 2 |

## Antes das sprints (débito técnico)

- [ ] Testar v7.1 (transições + LUTs no render final)
- [ ] Confirmar se v7.3 existe localmente (há `README_v7.3.md` e `VideoBuilderPro_v73.bat` no repo)
