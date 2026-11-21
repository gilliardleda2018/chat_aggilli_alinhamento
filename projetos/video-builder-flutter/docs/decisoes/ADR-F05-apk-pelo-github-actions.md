# ADR-F05: APK gerado pelo GitHub Actions

- Situação: Aceito
- Data: 2026-11-21

## Contexto

O dono opera quase sempre pelo celular e não quer depender do computador para gerar o APK.

## Decisão

- O workflow `.github/workflows/flutter-apk.yml` (na raiz do repositório) roda a cada push que mexe em
  `projetos/video-builder-flutter/**` e pode ser disparado à mão (aba Actions → "Run workflow", funciona no app do
  GitHub no celular).
- A pasta `android/` **não** é versionada: o workflow roda `flutter create --platforms=android` sobre o projeto
  (só cria o que falta; não sobrescreve `lib/` nem `test/`) e depois `tool/patch_android.py` ajusta o
  `AndroidManifest.xml` (permissão de internet, nome "Video Builder", consulta de navegador para abrir links).
  Isso evita versionar dezenas de arquivos Gradle gerados, que mudam a cada versão do Flutter.
- Passos: `flutter pub get` → `flutter analyze` (informativo) → `flutter test` → `flutter build apk --release`.
- O APK sai em dois lugares: artefato da execução e o pre-release **`apk-latest`** (link fixo para baixar no
  celular), substituído a cada build.

## Assinatura

- Se os segredos `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` e
  `ANDROID_KEY_PASSWORD` existirem no repositório, o APK é assinado com essa chave (necessário para Play Store e para
  atualizar por cima sem desinstalar).
- Sem os segredos, sai assinado com a chave de depuração gerada no próprio build. Funciona para instalar, mas
  **cada build tem uma chave diferente**: para instalar uma versão nova é preciso desinstalar a anterior.
  Criar a chave definitiva é o próximo passo recomendado (ver README, seção "Assinatura").
