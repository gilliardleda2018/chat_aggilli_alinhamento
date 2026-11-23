# PONTO DE PARADA — 21/11/2026 (app Flutter do Video Builder)

## Retomar daqui

Cole isto no início do novo chat:

> Estou no app Flutter do Video Builder (`projetos/video-builder-flutter`, branch `feat/app-flutter` do repo
> chat_aggilli_alinhamento). Leia o README, `docs/MAPA-DAS-ABAS.md` e os ADR-F01 a F05 antes de mudar algo.

## Decisões do dia (com o dono)

- Processamento **no servidor** `mcp_videobuilder` (escolha do dono). App = interface (ADR-F01).
- Escopo: **todas as 20 abas** já na primeira versão (escolha do dono); as que dependem de IA pesada ficam com tela
  pronta e aviso "aguardando servidor".
- Pedido de manter download de música do YouTube: **não incluído** (termos do YouTube, direitos autorais, Play Store);
  substituído por "Enviar do celular" + fontes de música liberadas (ADR-F04).
- Login sem mudar o servidor: OAuth com loopback 127.0.0.1 (ADR-F02); Nextcloud por Login Flow v2 (ADR-F03).
- APK pelo GitHub Actions, pre-release `apk-latest` (ADR-F05).

## Próximos passos sugeridos

1. Instalar o APK do `apk-latest` e testar: login no servidor, login no Nextcloud, render curto de 2 clipes.
2. Criar a chave de assinatura definitiva e os 4 segredos (README → Assinatura).
3. Servidor (cada item com ADR próprio no mcp_videobuilder): `vb_files_list`, `vb_transcribe_start` (Whisper),
   `vb_qc_start`, LUT `.cube`. Depois avaliar GPU para Stems/Upscale/Face Restore.
4. Ícone com o logotipo da Aggilli (flutter_launcher_icons) e publicação na Play Store.
