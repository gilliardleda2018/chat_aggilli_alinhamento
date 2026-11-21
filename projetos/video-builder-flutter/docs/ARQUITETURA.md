# Arquitetura do app Flutter

## Pastas

| Caminho | Responsabilidade |
|---|---|
| `lib/main.dart` | Tema (cor da marca) e `AppScope`. |
| `lib/state/app_state.dart` | Estado único: projeto aberto (`EditPlan`), conexões, salvar/abrir, `addMedia`, `probeClip`. |
| `lib/models/edit_plan.dart` | Espelho do `EditPlan` do servidor (`edl.py`) + `computeTimeline` (mesma conta de `edl.timeline`). |
| `lib/services/mcp_client.dart` | Cliente MCP (JSON-RPC por HTTP em `/mcp`), renovação de token em 401, imagens e JSON do resultado. |
| `lib/services/oauth_loopback.dart` | Login OAuth com registro dinâmico + PKCE e retorno em `127.0.0.1` (ADR-F02). |
| `lib/services/nextcloud.dart` | Login Flow v2, PROPFIND, MKCOL, PUT sem sobrescrever (ADR-F03). |
| `lib/services/analysis.dart` | `vb_analyze_start` + espera no `vb_job_status`; modelo `Analysis`. |
| `lib/services/claude_api.dart` | Aba IA: API do Claude com a chave do usuário. |
| `lib/services/project_store.dart` | Projetos no aparelho (`shared_preferences`), equivalente ao `.vbp`. |
| `lib/services/secure_store.dart` | Cofre (Android Keystore) para tokens e senhas. |
| `lib/screens/home.dart` | Registro das 20 abas (`kTabs`), menu lateral por grupo e barra inferior com as 5 principais. |
| `lib/screens/settings_screen.dart` | Conexões e **diagnóstico embutido** (`/healthz`, conta, Nextcloud). |
| `lib/tabs/*.dart` | Uma aba por arquivo, na ordem do desktop (ver `MAPA-DAS-ABAS.md`). |
| `lib/widgets/common.dart` | Seções, controles, aviso "aguardando servidor", navegador do Nextcloud. |
| `tool/patch_android.py` | Ajusta o `android/` gerado no CI (permissões, nome, assinatura). |
| `test/` | Testes do roteiro, linha do tempo, auto-edição e de que as 20 abas constroem. |

## Fluxo de um vídeo

1. **Mídia**: navega no Nextcloud (WebDAV) e adiciona vídeos/fotos à timeline; áudio vira trilha; `.srt` vira legenda.
   Ao adicionar um vídeo, o app chama `vb_media_probe` para saber a duração (necessária para a conta da timeline).
2. **Timeline / Cor / Áudio / Textos**: editam o `EditPlan` em memória; `AppState.touch()` marca "não salvo".
3. **Render**: `vb_render_start({plan})` → `job_id` → `vb_job_status` a cada 5 s enquanto a aba está aberta →
   link do vídeo no Nextcloud. O projeto é salvo automaticamente ao renderizar.

## Por que sem pacote de gerenciamento de estado

`ChangeNotifier` + `InheritedNotifier` (do próprio Flutter) bastam para um estado único e evitam dependências.
Menos dependências = menos quebras ao atualizar o Flutter no CI.

## Compatibilidade com o servidor

O app não muda nada no servidor (ADR-F01). Se o `EditPlan` do servidor ganhar campos, atualize
`lib/models/edit_plan.dart` e `test/edit_plan_test.dart` juntos. Ferramentas novas do servidor entram nas abas
marcadas com ⏳ em `MAPA-DAS-ABAS.md`.
