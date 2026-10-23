# Video Builder Pro v7.3

Editor de vídeo profissional em Python + Tkinter com FFmpeg e Claude AI.

## Novidades v7.3

### Módulos Adicionados

| Módulo | Descrição | Fonte |
|--------|-----------|-------|
| **GL Transitions** | 70+ transições com easing | github.com/scriptituk/xfade-easing |
| **LUT Manager** | Aplicação de LUTs (.cube) e looks embutidos | - |
| **Auto Editor** | Remoção automática de silêncios | github.com/Muzamil4266/Python-auto-video-editor |
| **Subtitles AI** | Legendas automáticas com Whisper | github.com/Eyevinn/auto-subtitles |
| **Vertical Converter** | Conversão para 9:16 (TikTok/Reels) | github.com/algometrix/vertical_video_convertor |
| **GPU Encoder** | Encoding acelerado por GPU | - |

### Funcionalidades

- ✅ 70+ transições GL com easing (cubic, elastic, bounce, etc.)
- ✅ 15+ LUTs embutidas (cinematic, vintage, HDR, etc.)
- ✅ Suporte a LUTs personalizadas (.cube)
- ✅ Remoção automática de silêncios
- ✅ Detecção de cortes de cena
- ✅ Legendas automáticas (Whisper AI)
- ✅ Queimar legendas no vídeo (hardcode)
- ✅ Adicionar legendas soft (track separada)
- ✅ Conversão para vertical (9:16)
- ✅ Face tracking para crop inteligente
- ✅ Blur no fundo (estilo TikTok)
- ✅ Encoding GPU (NVENC, AMF, QuickSync)
- ✅ Presets otimizados para cada GPU

## Instalação

### Requisitos Básicos

```bash
pip install requests Pillow
```

### Requisitos Opcionais (para funcionalidades avançadas)

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

## Uso

### Executar App

```bash
python video_builder_pro_v7_suite.py
```

### Novas Funcionalidades

#### Transições GL

```python
from modules import GLTransitionsEngine, GLTransition, EasingType

engine = GLTransitionsEngine(log)
transicao = GLTransition(
    nome="gl_cube",
    duracao=1.0,
    easing=EasingType.ELASTIC
)
engine.renderizar_transicao(clip1, clip2, transicao, saida)
```

#### Aplicar LUT

```python
from modules import LUTManager

lut_mgr = LUTManager(log)
lut_mgr.aplicar_lut(video, "cinematic", saida, intensidade=1.0)
```

#### Remover Silêncios

```python
from modules import AutoEditor

auto = AutoEditor(log)
auto.remover_silencios_simples(video, saida, threshold_db=-35.0)
```

#### Gerar Legendas

```python
from modules import SubtitlesAI

subs = SubtitlesAI(log)
subs.gerar_legendas(video, "pt", "base", "srt")
```

#### Converter Vertical

```python
from modules import VerticalConverter, CropMode

vertical = VerticalConverter(log)
vertical.converter(video, saida, CropMode.SMART, adicionar_blur_fundo=True)
```

#### Encoding GPU

```python
from modules import GPUEncoder

gpu = GPUEncoder(log)
melhor = gpu.obter_melhor_gpu()
cmd = gpu.gerar_comando_ffmpeg(melhor, preset, entrada, saida)
```

## Estrutura de Pastas

```
video-builder-pro/
├── modules/
│   ├── __init__.py
│   ├── transitions_gl.py      # Transições GL
│   ├── luts_manager.py        # Gerenciador de LUTs
│   ├── auto_editor.py         # Auto-edição
│   ├── subtitles_ai.py        # Legendas AI
│   ├── vertical_converter.py  # Conversor vertical
│   ├── gpu_encoder.py         # Encoding GPU
│   └── v73_integration.py     # Integração
├── luts/                       # LUTs personalizadas (.cube)
├── video_builder_pro_v7_suite.py
└── README.md
```

## Performance

### Encoding GPU vs CPU

| GPU | Velocidade | Qualidade |
|-----|-----------|-----------|
| NVIDIA NVENC | 5-10x CPU | Boa |
| AMD AMF | 3-7x CPU | Boa |
| Intel QuickSync | 2-5x CPU | Boa |
| CPU x264 | Base | Melhor |

### Transições GL

- Transições simples: ~0.5s por segundo de vídeo
- Transições complexas: ~2s por segundo de vídeo
- Easing adiciona ~0.2s de overhead

## Roadmap

### v7.4 (Próximo)

- [ ] Preview em tempo real
- [ ] Multicam editing
- [ ] Speed ramp
- [ ] Exportação para redes sociais (APIs)
- [ ] Templates de projeto

### v8.0 (Futuro)

- [ ] Interface web (opcional)
- [ ] Colaboração em nuvem
- [ ] IA de edição automática completa

## Suporte

- Issues: github.com/gilliardleda2018/chat_aggilli_alinhamento/issues
- Documentação: Wiki do projeto

## Licença

Projeto pessoal - Aggilli Intelligence
