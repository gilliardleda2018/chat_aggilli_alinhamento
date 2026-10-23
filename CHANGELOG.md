# Changelog - Video Builder Pro

## [v7.2] - 2026-10-23

### Adicionado
- Salvar/Abrir projeto em formato .vbp (JSON)
- Escolher pasta de renderização com criação automática
- Campo de pasta de render na aba Projeto e aba Render
- Botão "Criar Pasta" para verificar/criar diretório

### Corrigido
- Render agora usa pasta escolhida pelo usuário

---

## [v7.1] - 2026-10-22

### Adicionado
- Transições entre clips: CROSSFADE, FADE_BLACK, FADE_WHITE, ZOOM_IN, ZOOM_OUT, SLIDE_LEFT, SLIDE_RIGHT, DISSOLVE
- Color grading por clip: CINEMATIC, ORANGE_TEAL, FILM_NOIR, VIBRANT, WARM, COLD, BLEACH_BYPASS, DAY_FOR_NIGHT
- Interface de timeline com seleção de clip e aplicação de configurações
- Normalização de clips para mesma resolução/fps antes do render

### Técnico
- Render usa filter_complex do FFmpeg para xfade
- Clips processados individualmente antes da concatenação

---

## [v7.0] - 2026-10-22

### Adicionado
- Integração Claude AI (aba IA)
- Geração de: roteiro, títulos, descrição YouTube, capítulos, hashtags, melhorar texto
- Modelo padrão: claude-haiku-4-5-20251001
- Chave API salva localmente (base64)

### Interface
- 8 abas: Projeto, Mídia, Timeline, Cor, Áudio, IA, Render, QC
- Menu completo: Arquivo, Edição, Ferramentas, Ajuda

### Estabilidade
- Proteção no método log() para não quebrar antes da UI
- Threads com daemon=True
- Sem emojis em botões (compatibilidade Windows)

---

## [v6.0] - Legado

- Versão anterior sem integração AI
- Render básico por concatenação
