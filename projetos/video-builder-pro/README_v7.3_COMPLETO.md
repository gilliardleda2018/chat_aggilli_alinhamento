# Video Builder Pro v7.3 — Professional Suite

Editor de vídeo profissional em Python + Tkinter com FFmpeg e Claude AI.

## 🎉 Novidades v7.3

### Módulos Adicionados

| Módulo | Descrição | Status |
|--------|-----------|--------|
| **GL Transitions** | 70+ transições com easing | ✅ |
| **LUT Manager** | 15+ LUTs embutidas + suporte .cube | ✅ |
| **Auto Editor** | Remoção automática de silêncios | ✅ |
| **Subtitles AI** | Legendas automáticas (Whisper) | ✅ |
| **Vertical Converter** | Conversão para 9:16 (TikTok/Reels) | ✅ |
| **GPU Encoder** | Encoding acelerado (NVENC/AMF/QuickSync) | ✅ |

---

## 📁 Estrutura do Projeto

```
video-builder-pro/
├── modules/
│   ├── __init__.py              # Imports e fallback
│   ├── transitions_gl.py        # 70+ transições GL
│   ├── luts_manager.py          # Gerenciador de LUTs
│   ├── auto_editor.py           # Auto-edição
│   ├── subtitles_ai.py          # Legendas AI
│   ├── vertical_converter.py    # Conversor vertical
│   ├── gpu_encoder.py           # Encoding GPU
│   └── v73_integration.py       # Integração
├── luts/                         # LUTs personalizadas (.cube)
├── v73_patch.py                  # Patch para app v7.2
├── testar_modulos.py             # Script de teste
├── INICIAR_V7.3.bat              # Inicializador v7.3
├── video_builder_pro_v7.1_suite.py  # App principal v7.2
└── README_v7.3.md                # Este arquivo
```

---

## 🚀 Início Rápido

### Opção 1: Usar Patch (Recomendado)

Execute o app v7.2 com o patch v7.3:

```bash
INICIAR_V7.3.bat
```

Ou manualmente:

```python
from video_builder_pro_v7.1_suite import VideoBuilderProV7
from v73_patch import aplicar_patch
import tkinter as tk

root = tk.Tk()
app = VideoBuilderProV7(root)
patch = aplicar_patch(app)
root.mainloop()
```

### Opção 2: Testar Módulos Individualmente

```bash
python testar_modulos.py
```

---

## 📖 Documentação

### Exemplos de Uso

Veja `EXEMPLO_USO_V7.3.md` para exemplos detalhados de cada módulo.

### Módulos

#### GL Transitions
- 70+ transições GL (gl_cube, gl_doorway, gl_Swirl, etc.)
- 11 tipos de easing (cubic, elastic, bounce, etc.)
- Expressões customizadas para FFmpeg xfade

#### LUT Manager
- 15 LUTs embutidas (cinematic, vintage, HDR, etc.)
- Suporte a LUTs personalizadas (.cube)
- Ajuste de intensidade (0.0 a 1.0)

#### Auto Editor
- Detecção de silêncios (FFmpeg silencedetect)
- Detecção de cortes de cena
- Remoção automática de silêncios

#### Subtitles AI
- Legendas automáticas com Whisper AI
- Suporte a 99 idiomas
- Exportação SRT/VTT
- Queimar legendas no vídeo (hardcode)
- Legendas soft (track separada)

#### Vertical Converter
- Conversão para 9:16 (TikTok/Reels/Shorts)
- Face tracking inteligente (OpenCV + InsightFace)
- Blur no fundo (estilo TikTok)
- Modos: center, top, bottom, smart, manual

#### GPU Encoder
- Detecção automática de GPU (NVIDIA/AMD/Intel)
- Presets otimizados por GPU
- Encoding 5-10x mais rápido que CPU
- Suporte a H.264 e HEVC

---

## ⚙️ Instalação

### Requisitos Básicos

```bash
pip install requests Pillow
```

### Requisitos Opcionais

```bash
# Para legendas automáticas
pip install openai-whisper

# Para face tracking no vertical converter
pip install opencv-python insightface
```

### FFmpeg

Certifique-se de ter o FFmpeg instalado e no PATH:

```bash
ffmpeg -version
```

---

## 🎯 Funcionalidades

### Transições GL (70+)

- **Básicas**: fade, dissolve, fadeblack, fadewhite
- **GL Avançadas**: gl_cube, gl_doorway, gl_Swirl, gl_WaterDrop, gl_ripple
- **Efeitos**: gl_BookFlip, gl_chessboard, gl_kaleidoscope, gl_Mosaic
- **Easing**: linear, quadratic, cubic, quartic, quintic, sinusoidal, exponential, circular, elastic, back, bounce

### LUTs (15+)

- **Cinema**: Cinematic, Orange Teal, Film Noir, Dramatic
- **Vintage**: Vintage, Bleach Bypass, Day for Night
- **Moderno**: Vibrant, Warm, Cold, Pastel, Matte, Crisp, Soft Light
- **Efeitos**: HDR, Soft Light

### Auto-Edição

- Remoção de silêncios (threshold configurável)
- Detecção de cortes de cena
- Segmentação automática

### Legendas AI

- Geração automática (Whisper)
- 99 idiomas suportados
- 5 modelos (tiny, base, small, medium, large)
- Queimar no vídeo ou adicionar como track

### Conversão Vertical

- Crop central, topo, baixo, inteligente (face tracking)
- Blur no fundo (estilo TikTok)
- Resolução 9:16 (1080x1920)

### GPU Encoding

- **NVIDIA**: NVENC (5-10x mais rápido)
- **AMD**: AMF (3-7x mais rápido)
- **Intel**: QuickSync (2-5x mais rápido)
- **CPU**: x264/x265 (base)

---

## 🔧 Uso Avançado

### Integração com App Existente

```python
from v73_patch import aplicar_patch

# Aplica patch no app v7.2
patch = aplicar_patch(app)

# Novas abas adicionadas:
# - Transicoes GL
# - LUTs Avancadas
# - Auto-Edicao
# - Legendas AI
# - Vertical
```

### Uso Standalone

```python
from modules import V73Integration

v73 = V73Integration(log)

# Usa funcionalidades
v73.renderizar_com_transicao_gl(...)
v73.aplicar_lut_rapido(...)
v73.remover_silencios_auto(...)
```

---

## 📊 Performance

### Encoding GPU vs CPU

| GPU | Velocidade | Qualidade | Uso |
|-----|-----------|-----------|-----|
| NVIDIA NVENC | 5-10x CPU | Boa | Recomendado |
| AMD AMF | 3-7x CPU | Boa | Bom |
| Intel QuickSync | 2-5x CPU | Boa | Bom |
| CPU x264 | Base | Melhor | Alta qualidade |

### Transições GL

- Transições simples: ~0.5s por segundo de vídeo
- Transições complexas: ~2s por segundo de vídeo
- Easing adiciona ~0.2s de overhead

### Auto-Edição

- Análise: ~1x tempo real
- Remoção de silêncios: ~2x tempo real
- Detecção de cortes: ~0.5x tempo real

---

## 🐛 Troubleshooting

### Módulos não encontrados

```bash
# Verifique se a pasta modules existe
ls modules/

# Se não existir, baixe do GitHub
```

### Whisper não instalado

```bash
pip install openai-whisper
```

### GPU não detectada

- Verifique drivers atualizados
- NVIDIA: instale CUDA Toolkit
- AMD: instale drivers Adrenalin
- Intel: instale drivers mais recentes

### Erro de encoding

- Verifique FFmpeg no PATH
- Teste com CPU primeiro (preset FAST)
- Verifique logs de erro

---

## 📝 Changelog

### v7.3 (23/10/2026)

- ✅ Adicionados 6 novos módulos
- ✅ 70+ transições GL com easing
- ✅ 15+ LUTs embutidas
- ✅ Auto-edição (remoção de silêncios)
- ✅ Legendas AI (Whisper)
- ✅ Conversão vertical (9:16)
- ✅ GPU encoding (NVENC/AMF/QuickSync)
- ✅ Patch para app v7.2
- ✅ Script de teste dos módulos
- ✅ Documentação completa

### v7.2 (23/10/2026)

- ✅ Salvar/Abrir projeto (.vbp JSON)
- ✅ Escolher pasta de render
- ✅ Transições entre clips
- ✅ Color grading por clip

### v7.1 (22/10/2026)

- ✅ Claude AI integrada
- ✅ Roteiros, títulos, descrições
- ✅ Capítulos e hashtags

---

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

---

## 📄 Licença

Projeto pessoal - Aggilli Intelligence

---

## 🔗 Links

- GitHub: github.com/gilliardleda2018/chat_aggilli_alinhamento
- Issues: github.com/gilliardleda2018/chat_aggilli_alinhamento/issues
- Documentação: Wiki do projeto

---

## 🎬 Exemplos de Uso

Veja `EXEMPLO_USO_V7.3.md` para exemplos detalhados de cada módulo.

---

**Video Builder Pro v7.3** — Professional Suite 🎥
