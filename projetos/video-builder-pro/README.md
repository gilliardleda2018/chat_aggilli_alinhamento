# Video Builder Pro

Editor de vídeo profissional em Python + Tkinter com FFmpeg e Claude AI.

## Versões

| Versão | Data | Destaque | Status |
|--------|------|----------|--------|
| v7.8 | 03/11/2026 | Diretor IA: edição autônoma (corte de fala, diretor, revisor) + 93 testes | ✅ Atual |
| v7.7 | 03/11/2026 | Correção de todos os defeitos da auditoria v7.6 + 68 testes | ✅ Estável |
| v7.6 | 28/10/2026 | 20 abas (base + v76_patch) | ⚠️ Substituída pela v7.7 |
| v7.2 | 23/10/2026 | Salvar/abrir projeto | 📦 Anterior |
| v7.1 | 22/10/2026 | Transições + LUTs | 🧪 Teste |
| v7.0 | 22/10/2026 | Claude AI integrada | ✅ Estável |
| v6.0 | - | Legado | 📦 Arquivo |

## Instalar (usuários)

Baixe em **Releases** do GitHub:

- **Windows:** `VideoBuilderPro-Setup-<versão>.exe`. Não precisa de administrador nem de Python ou FFmpeg (já vêm junto).
- **Linux (Debian/Ubuntu):** `sudo apt install ./video-builder-pro_<versão>_amd64.deb`. Depois, procure "Video Builder Pro" no menu ou rode `video-builder-pro`.

Configurações, chave da API e logos ficam em `~/.video_builder_pro/` e sobrevivem a reinstalações. Estilos e LUTs próprios podem ser colocados em `~/.video_builder_pro/estilos/` e `~/.video_builder_pro/luts/`.

Para gerar os instaladores: logo em `assets/logo_aggilli.png` e uma tag `v*`. Os detalhes estão em `CHANGELOG.md` e no workflow `.github/workflows/video-builder-pro.yml`.

## v7.8 - Diretor IA

```bash
pip install -r requirements.txt
pip install whisperx            # recomendado (ou faster-whisper): transcrição palavra a palavra
python rodar_v78.py             # 21 abas (a última é "Diretor IA")
```

1. Aba **Diretor IA** → adicione os vídeos brutos (ou "Usar os clipes da aba Mídia").
2. Escolha o **estilo** (`estilos/*.json`) e escreva um **briefing** (opcional).
3. **Analisar** mostra o que será cortado (vícios, repetições, pausas, retakes).
4. **Editar automaticamente** → o Diretor planeja, renderiza, o Revisor dá nota e refaz se precisar.
5. Confira `<saida>.diretor.md`: cada corte e cada decisão documentados.
6. **Enviar para a Timeline** para ajustes finos manuais.

Com a chave da API (aba IA), o Claude dirige, detecta retakes e assiste ao resultado. Sem a chave, funciona em modo heurístico.

## v7.7

```bash
pip install -r requirements.txt          # principal
pip install -r requirements-ia.txt       # opcional: Whisper, Demucs, GFPGAN...
python rodar_v77.py                      # base (8 abas) + patch (12 abas)
python -m pytest tests                   # 68 testes (precisa de ffmpeg)
```

- Logs: `~/.video_builder_pro/logs/video_builder.log`
- Cookies do YouTube: `~/.video_builder_pro/cookies.txt` (o app força permissão 600)
- Chave da API: cofre do sistema (`keyring`) ou arquivo com permissão 600
- O `rodar_v76.py` antigo continua compatível.
- Detalhes de cada correção: `CHANGELOG.md` (raiz), seção v7.7.

## Requisitos

- Python 3.10 a 3.13
- FFmpeg + ffprobe no PATH (ffplay opcional, para preview)
- Tkinter (Linux: `sudo apt install python3-tk`)
- Dependências Python: `requirements.txt` (moviepy e pydub não são mais necessários)

## Instalação

1. Clone este repositório
2. Instale dependências: `pip install requests Pillow`
3. Execute o `.bat` da versão desejada

## Uso

### v7.2 (recomendado)

```bash
cd v7.2-projetos
VideoBuilderPro_v72.bat
