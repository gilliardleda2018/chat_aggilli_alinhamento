# ADR-F01: App Flutter como cliente do servidor do Video Builder

- Situação: Aceito
- Data: 2026-11-21
- Decidido por: Gilliard (escolha "Servidor" na pergunta sobre onde processar)

## Contexto

O Video Builder Pro desktop (v7.6) é Python + Tkinter + FFmpeg, com 20 abas. Várias abas usam IA pesada
(Whisper, WhisperX, Real-ESRGAN, GFPGAN, Demucs) que precisa de GPU/CPU de computador. Tkinter não roda no Android.
O objetivo é usar o Video Builder direto do celular.

Já existe o servidor `mcp_videobuilder` (video.aggillintelligence.com.br, EC2 us-east-1) que renderiza roteiros
(`EditPlan`) com FFmpeg, lê mídias do Nextcloud e grava o resultado no Nextcloud.

## Alternativas

1. **App Flutter = interface; processamento no servidor.** Escolhida.
2. Híbrido: FFmpeg no aparelho para cortes simples. Rejeitada: o FFmpegKit para Flutter foi descontinuado,
   dobraria a lógica de render (celular e servidor) e gasta bateria.
3. Só no celular: rejeitada, deixaria a maior parte das abas sem função.

## Decisão

- O app monta o mesmo `EditPlan` documentado em `mcp_videobuilder/docs/ROTEIRO.md` e envia por
  `vb_render_start`. Acompanha com `vb_job_status`, lista com `vb_jobs_list`, cancela com `vb_job_cancel`.
- A conversa com o servidor é o protocolo MCP (JSON-RPC 2.0 por HTTP em `/mcp`), o mesmo que o claude.ai usa.
  O servidor roda em modo `stateless_http=True, json_response=True`, então cada chamada é um POST com resposta JSON.
- **Nenhuma mudança no servidor** nesta etapa (sem regressão no que já está em produção).

## Consequências

- Recursos que o servidor ainda não tem (Whisper, Upscale real, Stems, Face Restore) aparecem como telas
  estruturadas com o aviso "aguardando servidor" e o roteiro do que falta (ver `MAPA-DAS-ABAS.md`).
- Quando o servidor ganhar uma ferramenta nova, o app só precisa chamar a ferramenta: a tela já existe.
- O app precisa de internet para renderizar.
