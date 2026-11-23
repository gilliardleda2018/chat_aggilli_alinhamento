# Mapa das 20 abas: desktop v7.6 → app Flutter

Legenda: ✅ funciona no app · 🟡 funciona com limite (explicado) · ⏳ tela pronta, aguardando ferramenta no servidor ·
🔁 substituída (ver ADR).

| # | Aba no desktop | Arquivo no app | Situação | Como funciona no app |
|---|---|---|---|---|
| 1 | Projeto | `tabs/projeto_tab.dart` | ✅ | Nome, formato (16:9, 9:16, 1:1, 4:5), resolução, fps, encaixe, pasta de saída. Salvar/abrir/duplicar/apagar projetos no aparelho (JSON do `EditPlan`, equivale ao `.vbp`). |
| 2 | Mídia | `tabs/midia_tab.dart` | ✅ | Navega no Nextcloud (WebDAV). Toque em vídeo/foto → adiciona à timeline; áudio → vira trilha; .srt/.vtt/.ass → legenda. Botão "Informações" chama `vb_media_probe`; "Prévia" chama `vb_media_preview` (folha de contato). |
| 3 | Timeline | `tabs/timeline_tab.dart` | ✅ | Lista reordenável de clipes: início/fim, velocidade, volume, duração e Ken Burns (fotos), transição. Mostra a duração final calculada igual ao servidor. |
| 4 | Cor | `tabs/cor_tab.dart` | ✅ | Brilho, contraste, saturação, temperatura (`ColorGrade`). |
| 5 | Áudio | `tabs/audio_tab.dart` | ✅ | Trilha (volume, início, ducking, loop), loudness (LUFS), fade de abertura/encerramento. |
| 6 | IA | `tabs/ia_tab.dart` | ✅ | Claude com a chave do próprio usuário (cofre do aparelho), igual ao desktop: roteiro, títulos, descrição YouTube, capítulos, hashtags, melhorar texto; botão "Usar como texto na tela". |
| 7 | Render | `tabs/render_tab.dart` | ✅ | Revisão do roteiro, `vb_render_start`, progresso por `vb_job_status` (a cada 5 s com a tela aberta), cancelar, lista de trabalhos, link do vídeo pronto. Mostra plano e minutos (`vb_account`). |
| 8 | QC | `tabs/qc_tab.dart` | 🟡 | `vb_analyze_start` em uma mídia: LUFS, silêncios, trocas de cena, trechos com som. Checagem local do roteiro (clipes curtos, textos fora da linha do tempo, transições maiores que o clipe). QC do arquivo final aguarda ferramenta no servidor. |
| 9 | Transições GL | `tabs/transicoes_tab.dart` | ✅ | Catálogo das 40 transições do servidor (xfade), aplicar em um clipe ou em todos, duração. As "70+ com easing" do desktop eram GLSL locais; no servidor valem as 40 do FFmpeg. |
| 10 | LUTs Avançadas | `tabs/luts_tab.dart` | 🟡 | Os looks do desktop (Cinematic, Orange & Teal, Film Noir, Vibrant, Warm, Cold, Bleach Bypass…) convertidos para `ColorGrade`. Aproximação: o servidor ainda não aplica arquivo `.cube`. |
| 11 | Auto-Edição | `tabs/auto_edicao_tab.dart` | ✅ | Analisa um vídeo no servidor e monta os clipes sozinho: por trechos com som (remove silêncios) ou por cenas, com duração mínima. |
| 12 | Legendas AI (Whisper) | `tabs/legendas_tab.dart` | 🟡 | Hoje: escolher legenda pronta (.srt/.vtt/.ass) do Nextcloud e tamanho. Geração automática ⏳ (o servidor ainda não tem Whisper). |
| 13 | Vertical 9:16 | `tabs/vertical_tab.dart` | ✅ | Converte o projeto para 9:16 com encaixe `blur`/`crop`/`pad` e mostra a zona segura das redes. |
| 14 | Upscale AI | `tabs/upscale_tab.dart` | 🟡 | Resolução de saída até 2160 (4K) por escala do FFmpeg. Real-ESRGAN ⏳. |
| 15 | Audio Stems | `tabs/stems_tab.dart` | ⏳ | Tela com o fluxo (escolher mídia → separar voz/instrumental). Aguarda Demucs no servidor. |
| 16 | Legendas Turbo | `tabs/legendas_turbo_tab.dart` | ⏳ | Aguarda faster-whisper no servidor. Enquanto isso, aponta para a aba Legendas. |
| 17 | Download | `tabs/enviar_tab.dart` | 🔁 | Vira **Enviar / Importar**: envia arquivos do celular ao Nextcloud + atalhos de músicas liberadas (ADR-F04). |
| 18 | Face Restore | `tabs/face_restore_tab.dart` | ⏳ | Aguarda GFPGAN no servidor. |
| 19 | WhisperX (karaokê) | `tabs/whisperx_tab.dart` | ⏳ | Aguarda WhisperX no servidor. |
| 20 | Auto-Edit Suite | `tabs/auto_suite_tab.dart` | ✅ | Painel de status (servidor, Nextcloud, plano, capacidades via `vb_capabilities`) + ações em lote: aplicar formato de rede (Reels/Shorts/YouTube/Feed), cortar 0,4 s de tremido nas pontas, transição padrão em tudo, texto de gancho nos primeiros 2,5 s. |

## O que o servidor precisa ganhar para fechar as ⏳ (sugestão de roteiro)

1. `vb_transcribe_start` (faster-whisper) → libera Legendas AI, Legendas Turbo e WhisperX (karaokê por palavra).
2. `vb_qc_start` sobre o MP4 final (loudness, true peak, quadros pretos) → QC completo.
3. `vb_files_list` → dispensa o segundo login no Nextcloud (ADR-F03).
4. `lut` no `ColorGrade` (arquivo `.cube` do Nextcloud com `lut3d`) → LUTs reais.
5. Stems (Demucs), Upscale (Real-ESRGAN) e Face Restore (GFPGAN) exigem GPU: avaliar instância com GPU sob demanda.

Cada item é uma mudança no `mcp_videobuilder` com seu próprio ADR; o app já tem a tela e só passa a chamar a
ferramenta.
