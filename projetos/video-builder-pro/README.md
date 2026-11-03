# Video Builder Pro

Editor de vídeo profissional em Python + Tkinter com FFmpeg e Claude AI.

## Versões

| Versão | Data | Destaque | Status |
|--------|------|----------|--------|
| v7.7 | 03/11/2026 | Correção de todos os defeitos da auditoria v7.6 + 68 testes | ✅ Atual |
| v7.6 | 28/10/2026 | 20 abas (base + v76_patch) | ⚠️ Substituída pela v7.7 |
| v7.2 | 23/10/2026 | Salvar/abrir projeto | 📦 Anterior |
| v7.1 | 22/10/2026 | Transições + LUTs | 🧪 Teste |
| v7.0 | 22/10/2026 | Claude AI integrada | ✅ Estável |
| v6.0 | - | Legado | 📦 Arquivo |

## v7.7 (atual)

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
