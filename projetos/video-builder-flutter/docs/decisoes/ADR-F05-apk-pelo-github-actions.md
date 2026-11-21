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

- Se os segredos `ANDROID_KEYSTORE_BASE64` e `ANDROID_KEYSTORE_PASSWORD` existirem no repositório, o APK é assinado
  com essa chave (necessário para Play Store, para o registro de desenvolvedor verificado e para atualizar por cima
  sem desinstalar). `ANDROID_KEY_ALIAS` (padrão `videobuilder`) e `ANDROID_KEY_PASSWORD` (padrão: a senha do
  arquivo, como em todo PKCS12) são opcionais.

## Chave definitiva (21/11/2026)

- Gerada em 21/11/2026: PKCS12, RSA 4096, alias `videobuilder`, válida até 13/11/2056.
- SHA-256 do certificado:
  `71:90:DD:77:3E:63:8F:FD:2C:CC:EC:E7:A1:65:E1:C5:26:12:AA:E0:75:7F:3D:72:B2:DD:64:6B:A2:B4:4A:F5`
- A chave e a senha foram entregues ao dono; não estão no repositório. Local combinado para guardar:
  Nextcloud `Aggilli/Chaves/Video Builder Android` (pasta sem compartilhamento) + cópia offline.

## Verificação de desenvolvedor (Brasil, desde 30/09/2026)

Em Android certificado no Brasil, app de desenvolvedor não verificado só instala pelo "fluxo avançado" (configuração
única + espera de 24 h). Para instalar sem isso, o pacote `br.com.aggilli.videobuilder` precisa ser registrado pela
Aggilli no Android Developer Console com o SHA-256 acima. Por isso a chave definitiva é pré-requisito.
- Sem os segredos, sai assinado com a chave de depuração gerada no próprio build. Funciona para instalar, mas
  **cada build tem uma chave diferente**: para instalar uma versão nova é preciso desinstalar a anterior.
  Criar a chave definitiva é o próximo passo recomendado (ver README, seção "Assinatura").
