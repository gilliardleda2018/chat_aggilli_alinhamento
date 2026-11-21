# ADR-F04: Aba Download vira "Enviar do celular" (sem baixar do YouTube)

- Situação: Aceito
- Data: 2026-11-21

## Contexto

A aba Download do desktop usa yt-dlp/instaloader para baixar de YouTube, TikTok e Instagram. Em 21/11/2026 foi
pedido manter ao menos o download de músicas do YouTube no app.

## Decisão

O app **não** baixa de YouTube nem de outras plataformas de terceiros:

- os Termos do YouTube proíbem baixar conteúdo fora dos recursos oferecidos por ele, e a maioria das músicas tem
  direitos autorais (vídeos publicados com elas podem ser silenciados ou removidos);
- um app que faz isso é recusado pela Google Play, o que inviabiliza a distribuição comercial da Aggilli;
- mantém a mesma regra do servidor (ADR-006 do `mcp_videobuilder`).

No lugar, a aba (renomeada **Enviar / Importar**) oferece:

1. **Enviar do celular**: escolher qualquer arquivo de áudio, vídeo, foto ou legenda do aparelho e enviar para uma
   pasta do Nextcloud (padrão `Musicas/` para áudio, `Video Builder/Envios/` para o resto).
2. **Fontes de música liberadas**: atalhos para a Biblioteca de Áudio do YouTube (YouTube Studio) e para a Pixabay
   Music, que permitem baixar para uso em vídeos. A pessoa baixa pelo navegador e importa pelo item 1.

## Consequências

- O app desktop continua com a aba original, sob responsabilidade de quem usa (decisão anterior, inalterada).
