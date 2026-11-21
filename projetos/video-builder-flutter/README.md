# Video Builder 8.0 · app Flutter (Android)

O Video Builder Pro (desktop v7.6, Python/Tkinter) reestruturado em **Flutter** para usar no celular.
O celular monta o roteiro; o **servidor do Video Builder** (`mcp_videobuilder`, video.aggillintelligence.com.br)
renderiza e grava o vídeo no **Nextcloud**.

```
Celular (este app)                         Servidor (mcp_videobuilder)          Nextcloud
 ├─ Projeto/Timeline/Cor/Áudio/Textos  ──►  vb_render_start ─► FFmpeg ─────►  Video Builder/Renders/x.mp4
 ├─ Mídia/Enviar  ── WebDAV ─────────────────────────────────────────────────►  suas pastas
 └─ IA ── API do Claude (sua chave)
```

- Mapa das 20 abas e o que cada uma faz no app: [docs/MAPA-DAS-ABAS.md](docs/MAPA-DAS-ABAS.md)
- Arquitetura e código: [docs/ARQUITETURA.md](docs/ARQUITETURA.md)
- Decisões: [docs/decisoes/](docs/decisoes/) (ADR-F01 a ADR-F05)
- Histórico: [CHANGELOG.md](CHANGELOG.md)

## Instalar no celular (sem computador)

1. No celular, abra **github.com/gilliardleda2018/chat_aggilli_alinhamento/releases** → pre-release
   **apk-latest** → toque em `VideoBuilder-xxxxxxx.apk`.
2. Permita "instalar apps desconhecidos" para o navegador quando o Android pedir.
3. Abra o app → engrenagem (Configurações):
   - **Entrar com a conta do Nextcloud** (servidor do Video Builder). O navegador abre, você entra e volta ao app.
   - **Conectar Nextcloud** (para navegar e enviar mídias). Mesmo processo.
   - (Opcional) chave da API do Claude para a aba IA.
   - **Testar conexões** mostra o diagnóstico completo.

Para gerar um APK novo: aba **Actions** do repositório → "APK Video Builder (Flutter)" → **Run workflow**
(funciona no app do GitHub). Todo push que mexe nesta pasta também gera.

> Enquanto a chave de assinatura definitiva não for criada, cada APK sai com uma chave diferente: para instalar uma
> versão nova, desinstale a anterior (os projetos salvos no aparelho se perdem; os vídeos no Nextcloud não).

## Assinatura (passo recomendado)

Para atualizar por cima e publicar na Play Store, crie uma chave uma única vez (em qualquer computador com Java):

```bash
keytool -genkey -v -keystore videobuilder.jks -keyalg RSA -keysize 2048 -validity 10000 -alias videobuilder
base64 -w0 videobuilder.jks   # copie a saída
```

No GitHub: Settings → Secrets and variables → Actions → crie `ANDROID_KEYSTORE_BASE64` (saída acima) e
`ANDROID_KEYSTORE_PASSWORD`. Guarde o `.jks` em local seguro: sem ele não é possível atualizar o app na Play Store.

> A chave definitiva já foi gerada em 21/11/2026 (alias `videobuilder`; SHA-256 no ADR-F05). Falta só criar os
> dois segredos.

### "O Android não deixa instalar"

Desde 30/09/2026, Android certificado no Brasil bloqueia apps de desenvolvedor não verificado. Até o app ser
registrado pela Aggilli no Android Developer Console, use o fluxo avançado que o próprio aviso oferece (configuração
única e espera de 24 h) ou, em aparelho Samsung, confira também o "Bloqueador automático" em Segurança.

## Desenvolver

```bash
cd projetos/video-builder-flutter
flutter create --platforms=android --org br.com.aggilli --project-name videobuilder .   # só na 1ª vez
python3 tool/patch_android.py .
flutter pub get
flutter test
flutter run
```

## Regras que o app segue

- Nada é sobrescrito no Nextcloud (envios ganham " (2)"; o servidor também não sobrescreve renders).
- Tokens, senha de app do Nextcloud e chave do Claude ficam só no cofre do aparelho (Android Keystore).
- Sem download de YouTube ou de outras plataformas (ADR-F04).
- O roteiro enviado é exatamente o `EditPlan` de `mcp_videobuilder/docs/ROTEIRO.md`.
