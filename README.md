# Chat Aggilli - Alinhamento

Repositório de contexto e habilidades para trabalho contínuo com IA.

## Projetos Ativos

| Projeto | Versão Atual | Status |
|---------|-------------|--------|
| Video Builder Pro | **v7.5** | ✅ Completo e funcional |

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

## Retomada Rápida

1. Leia `contextos/2026-10-23_final-do-dia.md`
2. Execute `python rodar_v75.py` na pasta local
3. App abre com 19 abas funcionais

## Instalação Rápida

```bash
# Básico (app funciona)
pip install requests Pillow

# Completo (todas as features)
pip install openai-whisper insightface opencv-python demucs whisperx gfpgan realesrgan yt-dlp faster-whisper
```

## Última Atualização

**23/10/2026 (final do dia)** - v7.5 COMPLETO: 19 abas, 7 AIs integradas, download de vídeos funcionando.

## Como Usar

1. **Retomar trabalho**: Leia o contexto mais recente em `contextos/`
2. **Ver código**: Navegue em `projetos/video-builder-pro/`
3. **Restaurar versão**: Copie de `backups/` para sua máquina
4. **Executar app**: `python rodar_v75.py`
