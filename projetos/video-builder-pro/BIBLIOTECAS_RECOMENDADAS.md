# Bibliotecas e Repositórios Recomendados — Video Builder Pro

Pesquisa realizada em 23/10/2026 via GitHub API. Objetivo: fortalecer o app com funcionalidades validadas pela comunidade.

---

## TIER 1 — OURO (implementar já: alto impacto + fácil integração)

### 1. Auto-Editor — `WyattBlue/auto-editor`
- **O que faz:** Edição automática por análise de áudio — remove silêncios, corta por loudness, jump cuts.
- **Por que trazer:** Python + FFmpeg, lógica pronta de detecção de silêncio por threshold.
- **Integração no VBP:** Nova aba **"Auto-Cut"**. Caso de uso: 40 min de aula gravada → remove pausas/"ããã" → sobra 22 min editados.
- **Link:** https://github.com/WyattBlue/auto-editor

### 2. faster-whisper — `SYSTRAN/faster-whisper`
- **O que faz:** Transcrição Whisper **4x mais rápida** que o original, roda em CPU, timestamps por palavra.
- **Por que trazer:** Combina com a aba IA (Claude gera roteiro → Whisper transcreve → legendas sincronizadas).
- **Integração no VBP:** Nova aba **"Legendas"**: transcreve vídeo, gera SRT, queima no render via FFmpeg. Recurso #1 pedido por YouTubers.
- **Link:** https://github.com/SYSTRAN/faster-whisper

### 3. PySceneDetect — `Breakthrough/PySceneDetect` ⭐ 5.2k
- **O que faz:** Detecta cortes/mudanças de cena (OpenCV).
- **Por que trazer:** Python puro, `pip install scenedetect`. Serve para auto-split de clips, QC (cortes por minuto) e alimentar o `multicam()` placeholder.
- **Integração no VBP:** Botão **"Detectar Cenas"** → split automático na timeline. No QC: relatório de cortes.
- **Link:** https://github.com/Breakthrough/PySceneDetect

---

## TIER 2 — PRATA (médio prazo, precisa adaptação)

### 4. MoviePy — `Zulko/moviepy` ⭐ 15k
- **O que faz:** Biblioteca de edição mais famosa do Python — compositing, texto animado, efeitos.
- **Uso no VBP:** NÃO substituir o render FFmpeg. Usar como **gerador de overlays/títulos animados** que alimentam o filter_complex.
- **Link:** https://github.com/Zulko/moviepy

### 5. OpenTimelineIO (OTIO) — `AcademySoftwareFoundation/OpenTimelineIO` ⭐ 2k
- **O que faz:** Formato padrão da indústria (Pixar/Disney) de intercâmbio de timelines.
- **Uso no VBP:** Evoluir o salvar/abrir .vbp para também **exportar .otio** → timeline abre no DaVinci/Premiere/Final Cut. Interoperabilidade = credibilidade profissional.
- **Link:** https://github.com/AcademySoftwareFoundation/OpenTimelineIO

### 6. clippyme — `fralapo/clippyme`
- **O que faz:** Alternativa open-source ao Opus Clip — vídeo longo → shorts 9:16 com detecção de momentos virais (IA), reframing automático, legendas.
- **Uso no VBP:** Nova aba **"Shorts"**: vídeo de 1h → 5 shorts verticais com legenda e corte no rosto (active-speaker crop).
- **Link:** https://github.com/fralapo/clippyme

---

## TIER 3 — BRONZE (referência/inspiração)

| Repositório | O que aproveitar |
|---|---|
| `antoniocostalopes/video-Kit` | Pipeline completo como Claude Skill: whisper + auto-cut + LUTs + reframe + diarization + TTS + remoção de fundo. Mapa do que o mercado considera "editor IA completo" |
| `Noah-Grimaldi/auto-gaming-montage-maker` | Detecção de eventos visuais (YOLO) → montagem automática. Referência para detecção de highlights |
| `yeeking/podomatic` | Auto-switch de câmeras por quem está falando (podcast 2 câmeras). **Referência direta para o `multicam()`** |
| `francozanardi/movielite` | Alternativa ao MoviePy com Numba (performance), caso MoviePy fique lento |
| `qiuninghuan-cloud/shot-blade` | GUI Tkinter + PySceneDetect para split por cena — prova de conceito da Sprint 1 |

---

## Notas de integração técnica

- **Regra do projeto mantida:** novas libs devem rodar em threads `daemon=True` e logar no `video_builder_v7.log`.
- Dependências novas entram no `ATUALIZAR_DEPENDENCIAS.bat`.
- Testar cada integração como módulo separado antes de fundir no script principal (evitar repetir as quebras de IndentationError/NameError do passado).
- Tudo que for render final continua saindo pelo FFmpeg CLI — libs Python só preparam dados/filtros.
