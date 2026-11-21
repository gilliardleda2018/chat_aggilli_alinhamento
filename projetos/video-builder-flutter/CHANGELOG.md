# Changelog · Video Builder app Flutter

## [8.0.0] - 2026-11-21

Primeira versão do app Android, reestruturando o Video Builder Pro desktop v7.6 em Flutter.

### Adicionado
- 20 abas na mesma ordem do desktop (mapa completo em `docs/MAPA-DAS-ABAS.md`):
  - funcionais: Projeto, Mídia, Timeline (com textos na tela), Cor, Áudio, IA, Render, Transições, Auto-Edição,
    Vertical, Enviar/Importar, Auto-Edit Suite;
  - funcionais com limite: QC, LUTs (looks aproximados), Legendas (arquivo pronto), Upscale (escala até 4K);
  - telas prontas aguardando o servidor: Audio Stems, Legendas Turbo, Face Restore, WhisperX.
- Renderização no servidor `mcp_videobuilder` pelo protocolo MCP (ADR-F01).
- Login OAuth com retorno em loopback, sem mudança no servidor (ADR-F02); token fixo como alternativa.
- Nextcloud direto por WebDAV com Login Flow v2: navegar, adicionar e enviar arquivos do celular (ADR-F03).
- Diagnóstico embutido em Configurações (servidor, conta/plano, Nextcloud).
- Projetos salvos no aparelho (salvar, abrir, duplicar, apagar).
- APK gerado no GitHub Actions e publicado no pre-release `apk-latest` (ADR-F05).
- Testes: roteiro → JSON, linha do tempo igual à do servidor, auto-edição, construção das 20 abas.

### Alterado em relação ao desktop
- Aba Download virou **Enviar / Importar**: sem download de YouTube/TikTok/Instagram (ADR-F04).
- Transições: as 40 do servidor (xfade) no lugar das 70+ GLSL locais.
- LUTs: looks convertidos para brilho/contraste/saturação/temperatura até o servidor aceitar `.cube`.

### Não muda
- O app desktop (v7.6) continua como está, em `projetos/video-builder-pro/`.
- O servidor `mcp_videobuilder` não foi alterado.
