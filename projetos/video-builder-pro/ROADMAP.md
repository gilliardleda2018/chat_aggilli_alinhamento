# ROADMAP — Video Builder Pro

## Edição profissional autônoma (definido em 03/11/2026)

Base: pesquisa de repositórios em 03/11/2026 (licenças conferidas). Só código MIT/Apache/BSD/domínio público
é incorporado; projetos AGPL/GPL (OpenMontage, RobustVideoMatting) servem apenas de referência.

| Sprint | Entrega | Referências | Status |
|---|---|---|---|
| **A** | Diretor + Revisor (Claude), transcrição palavra a palavra, corte de vícios/repetições/pausas/retakes, estilos, enquadramento vertical | agentic-video-editor (MIT), FireRed-OpenStoryline (Apache-2.0), WhisperX (BSD-2), stable-ts (MIT) | ✅ v7.8 |
| **B** | Limpeza de voz (DeepFilterNet), legendas animadas palavra a palavra (estilo destaque) | DeepFilterNet (Apache/MIT), captacity (MIT) | ⏳ Próxima |
| **C** | Cortes na batida da música, PySceneDetect, corte de câmera por falante (podcast) | beat_this (MIT), PySceneDetect (BSD-3), pyannote-audio (MIT) | 🔒 |
| **D** | Estilos aprendidos de um vídeo de referência, exportação OpenTimelineIO (DaVinci/Premiere) | OpenTimelineIO (Apache-2.0) | 🔒 |

Regras de cada sprint: testes de regressão antes de alterar, novo patch/aba isolado quando possível,
CHANGELOG com decisão + motivo + teste, PR separado.

---


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
