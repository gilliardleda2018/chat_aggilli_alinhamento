# ADR-F02: Login no servidor por OAuth com retorno em loopback (127.0.0.1)

- Situação: Aceito
- Data: 2026-11-21

## Contexto

O servidor protege `/mcp` com OAuth 2.1 (registro dinâmico de cliente + PKCE), igual ao mcp_nextcloud (ADR-003 do
servidor). O registro só aceita `redirect_uri` da lista `MCP_ALLOWED_REDIRECT_PREFIXES`. O padrão inclui
`http://127.0.0.1:` e `http://localhost:`, mas **não** um esquema próprio de app (ex.: `br.com.aggilli.videobuilder:/`).

## Alternativas

1. Esquema próprio do app: exigiria mudar a lista do servidor (mudança em produção). Adiado.
2. **Retorno em loopback (RFC 8252, seção 7.3)**: o app abre um servidor HTTP em `127.0.0.1` numa porta livre,
   registra `http://127.0.0.1:<porta>/callback`, abre o navegador no `/authorize` e recebe o código ali. Escolhida.
3. Token fixo (`MCP_STATIC_TOKENS`): mantido como **alternativa manual** nas Configurações, para o dono e para
   diagnóstico quando o login falhar.

## Decisão

Fluxo em `lib/services/oauth_loopback.dart`:

1. `GET /.well-known/oauth-authorization-server` (descobre `authorization_endpoint`, `token_endpoint`,
   `registration_endpoint`; se falhar, usa `/authorize`, `/token`, `/register`).
2. Sobe `HttpServer` em `127.0.0.1:0` (porta escolhida pelo sistema).
3. `POST /register` com `redirect_uris=[http://127.0.0.1:<porta>/callback]`, `token_endpoint_auth_method=none`.
4. PKCE S256 + `state` aleatório; abre o navegador externo no `/authorize`.
5. A pessoa entra com a conta do Nextcloud (tela do próprio servidor). O navegador volta para o loopback; o app
   confere o `state`, troca o código no `/token` e guarda `access_token` + `refresh_token` no cofre do aparelho
   (`flutter_secure_storage`, Keystore do Android).
6. Token vencido (HTTP 401) → renova com o `refresh_token` uma vez; se falhar, pede login de novo.

Cada login registra um cliente novo (a porta do loopback muda a cada vez). O `client_id` do último registro é
guardado para renovar o token. O servidor guarda clientes em SQLite (custo desprezível).

## Consequências

- Zero mudança no servidor.
- Se um dia o loopback der problema em algum aparelho, o plano B é acrescentar o esquema do app em
  `MCP_ALLOWED_REDIRECT_PREFIXES` (uma variável de ambiente, sem código) e trocar o retorno no app.
