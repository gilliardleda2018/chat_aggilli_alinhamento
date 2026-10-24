# Changelog - Video Builder Pro

## [v7.5] - 2026-10-23 (FINAL)

### Adicionado
- **19 abas funcionais** (8 originais + 11 novas)
- **Video Downloader** (yt-dlp): YouTube, TikTok, Instagram, etc
- **Face Restore** (GFPGAN): Restauração de rostos em videos
- **WhisperX**: Legendas karaokê com word-level timestamps
- **Upscale AI** (Real-ESRGAN): SD → HD → 4K
- **Audio Stems** (Demucs): Separação vocals/instrumental
- **Legendas Turbo** (faster-whisper): 4x mais rápido

### Integrações AI
- Claude AI (roteiros, títulos, descrições)
- Whisper AI (legendas automáticas)
- faster-whisper (legendas 4x mais rápidas)
- WhisperX (karaokê word-level)
- Demucs (separação de áudio)
- Real-ESRGAN (upscale de video)
- GFPGAN (restauração facial)

### Técnico
- Sistema modular com patch architecture
- GPU encoding (NVENC/AMF/QuickSync)
- 70+ transições GL com easing
- 15+ LUTs profissionais
- Auto-edição (detectar cenas, remover silêncios)
- Conversor vertical 9:16 (TikTok/Reels)
- QC automático (loudness, true peak, checksums)

### Corrigido
- Métodos bool sendo chamados como funções (patch v7.5)
- Download de vídeos: formato simples funciona sem Node.js

---

## [v7.4] - 2026-10-23

### Adicionado
- **16 abas funcionais**
- Upscale AI (Real-ESRGAN)
- Audio Stems (Demucs)
- Legendas Turbo (faster-whisper)

---

## [v7.3] - 2026-10-23

### Adicionado
- **13 abas funcionais**
- 70+ transições GL com easing
- 15+ LUTs embutidas
- Auto-edição (detectar cenas, remover silêncios)
- Legendas AI (Whisper)
- Conversor vertical 9:16
- GPU encoding

---

## [v7.2] - 2026-10-23

### Adicionado
- Salvar/Abrir projeto (.vbp JSON)
- Escolher pasta de renderização
- Transições entre clips
- Color grading por clip

---

## [v7.1] - 2026-10-22

### Adicionado
- Claude AI integrada
- Roteiros, títulos, descrições
- Capítulos e hashtags

---

## [v7.0] - 2026-10-22

### Inicial
- 8 abas: Projeto, Mídia, Timeline, Cor, Áudio, IA, Render, QC
- Renderização básica com FFmpeg
- Menu completo

---

## [v6.0] - Legado

- Versão anterior sem integração AI
