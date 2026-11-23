# Chat Aggilli - Alinhamento

Repositório de contexto e habilidades para trabalho contínuo com IA.

## Projetos Ativos

| Projeto | Versão Atual | Status |
|---------|-------------|--------|
| Video Builder Pro (desktop) | **v7.6** | [Instalação e aba Download](#instalação-em-um-checkout-limpo) |
| Video Builder app Android (Flutter) | **8.0.0** | 🧪 Primeira versão; renderiza no servidor. Ver [`projetos/video-builder-flutter`](projetos/video-builder-flutter/README.md) |

## Video Builder Pro v7.5

Editor de vídeo profissional com **19 abas** e **7 integrações AI**:

### Core (8 abas)
- Projeto, Mídia, Timeline, Cor, Áudio, IA, Render, QC

### v7.3 - Professional Suite (5 abas)
- Transições GL (70+ com easing)
- LUTs Avançadas (15+ profissionais)
- Auto-Edição (detectar cenas, remover silêncios)
- Legendas AI (Whisper)
- Vertical 9:16 (TikTok/Reels)

### v7.4 - AI Power (3 abas)
- Upscale AI (Real-ESRGAN: SD→HD→4K)
- Audio Stems (Demucs: vocals/instrumental)
- Legendas Turbo (faster-whisper: 4x mais rápido)

### v7.5 - Content Tools (3 abas)
- Download (yt-dlp: YouTube, TikTok, etc)
- Face Restore (GFPGAN)
- WhisperX (karaokê word-level)

## Integrações AI

| AI | Função | Status |
|----|--------|--------|
| Claude | Roteiros, títulos, descrições | ✅ |
| Whisper | Legendas automáticas | ⚠️ pip install |
| faster-whisper | Legendas 4x mais rápidas | ⚠️ pip install |
| WhisperX | Karaokê (word-level) | ⚠️ pip install |
| Demucs | Separação áudio | ⚠️ pip install |
| Real-ESRGAN | Upscale video | ⚠️ binário |
| GFPGAN | Restauração facial | ⚠️ pip install |

## Estrutura

```
chat_aggilli_alinhamento/
├── contextos/           # Pontos de parada datados
├── projetos/
│   └── video-builder-pro/
│       ├── modules/     # Módulos v7.3-v7.5
│       └── *.bat        # Launchers
└── skills/              # Skills do Claude
```

## Instalação em um checkout limpo

1. Instale Python 3.11 ou superior com Tkinter. No Debian ou Ubuntu, o Tkinter é fornecido pelo pacote `python3-tk`. Use `python -m tkinter` para verificar a instalação.
2. Instale o FFmpeg e deixe-o no `PATH` para juntar vídeo e áudio. Para baixar do YouTube, instale o Deno 2.3 ou superior. Deixe-o no `PATH` ou coloque `deno` (`deno.exe` no Windows) em `.video_builder_pro/runtime/` na raiz do checkout.
3. Na raiz do repositório, instale as dependências e abra o aplicativo. No Linux, use `python3` se o comando `python` estiver indisponível.

   ```bash
   python -m pip install --upgrade --target .video_builder_pro/runtime/python -r projetos/video-builder-pro/requirements.txt
   python projetos/video-builder-pro/rodar_v76.py
   ```

4. Na aba **Download**, cole a URL, selecione a qualidade, clique em **Baixar Vídeo** e escolha a pasta de destino. No Windows, você também pode abrir o app pelo `VideoBuilderPro_v73.bat`, que chama o launcher v7.6.

O arquivo de dependências instala a revisão oficial do `yt-dlp` que corrige `addOnDisposeCallback`, incluindo os scripts EJS compatíveis. O launcher carrega as dependências do diretório local do projeto. Se o YouTube exigir login, o downloader pode usar a sessão de um perfil de navegador detectado. [Correção do yt-dlp](https://github.com/yt-dlp/yt-dlp/pull/18124)

## Última Atualização

**23/10/2026 (final do dia)** - v7.5 COMPLETO: 19 abas, 7 AIs integradas, download de vídeos funcionando.

## Como Usar

1. **Retomar trabalho**: Leia o contexto mais recente em `contextos/`
2. **Ver código**: Navegue em `projetos/video-builder-pro/`
3. **Restaurar versão**: Copie de `backups/` para sua máquina
4. **Executar app**: `python projetos/video-builder-pro/rodar_v76.py`
