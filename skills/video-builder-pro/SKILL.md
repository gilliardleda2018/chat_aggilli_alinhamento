---
name: video-builder-pro
description: Use ao trabalhar no app Video Builder Pro v7.x (editor de vídeo em Python/Tkinter com FFmpeg e Claude AI). Cobre localização dos arquivos, estado atual do código, histórico de correções, configuração da API do Claude, pendências e roadmap de integração de bibliotecas.
user-invocable: true
---
# Video Builder Pro — Contexto do Projeto

App desktop do usuário: editor de vídeo profissional em Python + Tkinter, com FFmpeg e IA (Claude). Use esta habilidade em qualquer tarefa que mencione o app, o `video_builder_pro_v7_suite.py` ou os `.bat` da pasta.

## Onde estão as coisas

| Item | Caminho |
|------|---------|
| Pasta do projeto | `VIDEOS TESTE-20261021T225738Z-1-001/VIDEOS TESTE/VideoBuilder_5/` (no PC: `C:\Users\umled\Downloads\FireShot\...`) |
| Script principal | `video_builder_pro_v7_suite.py` (~36-50 KB, versão funcionando) |
| Versão em teste | `video_builder_pro_v7.1_suite.py` (73 KB — transições + LUTs por clip) |
| Launcher | `VideoBuilderPro.bat` (verifica Python/deps e roda o script) |
| Log de erros | `video_builder_v7.log` (o .bat redireciona só o stderr: `2>> log`) |
| Config + chave API | `%USERPROFILE%\.video_builder_pro\config_v7.json` (chaves em base64) |
| Repositório de contexto | `github.com/gilliardleda2018/chat_aggilli_alinhamento` |

## Estado atual (23/10/2026)

- **v7.0 ESTÁVEL**: App abre e roda. 8 abas: Projeto, Mídia, Timeline, Cor, Áudio, **IA**, Render, QC.
- Aba **IA** integrada à API do Claude (classe `ClaudeEngine`): roteiro, títulos, descrição YouTube, capítulos, hashtags, melhorar texto.
- **Modelo em uso: `claude-haiku-4-5-20251001`** (nome da API exige a data no final, sem ela dá 404).
- **v7.1 EM TESTE**: transições (CROSSFADE, FADE_BLACK/WHITE, ZOOM_IN/OUT, SLIDE_L/R, DISSOLVE) + LUTs por clip (CINEMATIC, ORANGE_TEAL, FILM_NOIR, VIBRANT, WARM, COLD, BLEACH_BYPASS, DAY_FOR_NIGHT). Render via filter_complex xfade.
- **v7.2**: salvar/abrir projeto .vbp (JSON) + pasta de render customizável.
- **v7.3**: arquivos `README_v7.3.md` e `VideoBuilderPro_v73.bat` no repo — confirmar com o usuário o que ela adiciona.

## Regras aprendidas neste projeto (não repetir erros)

1. **Sempre entregar o arquivo INTEIRO em um único bloco de código.** Colar por partes causou 2 quebras (IndentationError; NameError `tk`).
2. Antes de alterar o `.py`, conferir tamanho antes/depois (arquivo muito menor = arquivo comido).
3. Salvar sempre em **UTF-8**; sem emojis em botões/abas do Tkinter no Windows.
4. O método `log()` é chamado antes da UI existir — manter a proteção (`self.log_text is not None`).
5. Threads de render/QC/IA sempre com `daemon=True`.
6. Erro do app vai para `video_builder_v7.log` — ler o log primeiro, sempre.
7. Nome de modelo Claude na API precisa do identificador datado (ex.: `claude-haiku-4-5-20251001`, `claude-sonnet-4-5-20250929`).
8. Render final sempre sai pelo **FFmpeg CLI** — libs Python só preparam dados/filtros.

## Roadmap de novas funcionalidades (definido 23/10/2026)

Detalhes completos em `projetos/video-builder-pro/BIBLIOTECAS_RECOMENDADAS.md` e `ROADMAP.md` no repositório.

1. **Sprint 1 — PySceneDetect**: botão "Detectar Cenas" (split automático na timeline) + relatório de cortes no QC. `pip install scenedetect[opencv]`.
2. **Sprint 2 — faster-whisper**: aba "Legendas" — transcreve, gera SRT, queima no render.
3. **Sprint 3 — Auto-Editor**: aba "Auto-Cut" — remoção automática de silêncio por threshold de áudio.
4. **Sprint 4 — OpenTimelineIO**: exportar timeline .otio (abre em DaVinci/Premiere).
5. **Sprint 5 — Shorts (insp. clippyme)**: vídeo longo → shorts 9:16 com auto-crop no rosto.

## Pendências / próximos passos conhecidos

- **Aguardando decisão do usuário:** confirmar início da Sprint 1 (PySceneDetect).
- **Testar v7.1**: verificar se transições e LUTs entram corretamente no render final.
- `preview()`, `multicam()`, `speed_ramp()` são placeholders (referência para multicam: repo `yeeking/podomatic`).
- Análise de QC tem placeholders (true peak, dropped/black frames) — Sprint 1 resolve parte.
- Restaurar funções da v6/v5 se o usuário pedir.

## Como restaurar o app se o arquivo quebrar

1. Buscar a versão mais recente no repo: `projetos/video-builder-pro/` (v7.0 estável ou v7.1 teste).
2. Entregar o conteúdo ao usuário em UM bloco, com as instruções: Ctrl+A → Delete → colar → salvar UTF-8.
3. Conferir: 1ª linha `#!/usr/bin/env python3`, última `    main()`.
