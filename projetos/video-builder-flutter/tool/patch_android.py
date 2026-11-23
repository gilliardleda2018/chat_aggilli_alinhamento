#!/usr/bin/env python3
"""Ajusta o projeto Android gerado por `flutter create` (ADR-F05).

Roda no GitHub Actions depois de `flutter create --platforms=android .`. Idempotente.

- AndroidManifest.xml: permissão de internet, nome "Video Builder", consulta de navegador (abrir links no
  Android 11+), sem backup automático dos dados do app (o cofre não deve ir para o backup da nuvem).
- build.gradle(.kts): assinatura de release a partir de android/key.properties quando existir
  (gerado pelo workflow a partir dos segredos); sem ele, usa a chave de depuração.
"""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
manifest = root / "android/app/src/main/AndroidManifest.xml"
m = manifest.read_text()

if "android.permission.INTERNET" not in m:
    m = m.replace("<application", '<uses-permission android:name="android.permission.INTERNET"/>\n    <application', 1)

m = re.sub(r'android:label="[^"]*"', 'android:label="Video Builder"', m, count=1)

if "android:allowBackup" not in m:
    m = m.replace("<application", '<application\n        android:allowBackup="false"', 1)

browser_query = (
    '<intent>\n            <action android:name="android.intent.action.VIEW"/>\n'
    '            <category android:name="android.intent.category.BROWSABLE"/>\n'
    '            <data android:scheme="https"/>\n        </intent>'
)
if 'android:scheme="https"' not in m:
    if "<queries>" in m:
        m = m.replace("<queries>", "<queries>\n        " + browser_query, 1)
    else:
        m = m.replace("</manifest>", "    <queries>\n        " + browser_query + "\n    </queries>\n</manifest>", 1)

manifest.write_text(m)
print("AndroidManifest.xml ajustado")

# ---------------------------------------------------------------- assinatura
kts = root / "android/app/build.gradle.kts"
groovy = root / "android/app/build.gradle"
if kts.exists():
    g = kts.read_text()
    if "key.properties" not in g:
        props = (
            "val keystoreProperties = Properties()\n"
            "val keystorePropertiesFile = rootProject.file(\"key.properties\")\n"
            "if (keystorePropertiesFile.exists()) {\n"
            "    keystoreProperties.load(FileInputStream(keystorePropertiesFile))\n"
            "}\n"
        )
        # imports no topo; o código só depois do bloco plugins { } (regra do Gradle)
        g = "import java.util.Properties\nimport java.io.FileInputStream\n\n" + g
        g = re.sub(r"(plugins \{.*?\n\}\n)", lambda mm: mm.group(1) + "\n" + props, g, count=1, flags=re.S)
        signing = (
            "    signingConfigs {\n"
            "        create(\"release\") {\n"
            "            if (keystorePropertiesFile.exists()) {\n"
            "                keyAlias = keystoreProperties[\"keyAlias\"] as String\n"
            "                keyPassword = keystoreProperties[\"keyPassword\"] as String\n"
            "                storeFile = file(keystoreProperties[\"storeFile\"] as String)\n"
            "                storePassword = keystoreProperties[\"storePassword\"] as String\n"
            "            }\n"
            "        }\n"
            "    }\n\n"
            "    buildTypes {"
        )
        g = g.replace("    buildTypes {", signing, 1)
        g = g.replace(
            'signingConfig = signingConfigs.getByName("debug")',
            'signingConfig = if (keystorePropertiesFile.exists()) signingConfigs.getByName("release") '
            'else signingConfigs.getByName("debug")',
        )
        kts.write_text(g)
        print("build.gradle.kts: assinatura configurada")
elif groovy.exists():
    g = groovy.read_text()
    if "key.properties" not in g:
        header = (
            "def keystoreProperties = new Properties()\n"
            "def keystorePropertiesFile = rootProject.file('key.properties')\n"
            "if (keystorePropertiesFile.exists()) {\n"
            "    keystoreProperties.load(new FileInputStream(keystorePropertiesFile))\n"
            "}\n\n"
        )
        g = re.sub(r"(plugins \{.*?\n\}\n)", lambda mm: mm.group(1) + "\n" + header, g, count=1, flags=re.S)
        g = g.replace(
            "    buildTypes {",
            "    signingConfigs {\n        release {\n            if (keystorePropertiesFile.exists()) {\n"
            "                keyAlias keystoreProperties['keyAlias']\n"
            "                keyPassword keystoreProperties['keyPassword']\n"
            "                storeFile file(keystoreProperties['storeFile'])\n"
            "                storePassword keystoreProperties['storePassword']\n            }\n        }\n    }\n\n"
            "    buildTypes {",
            1,
        )
        g = g.replace(
            "signingConfig = signingConfigs.debug",
            "signingConfig = keystorePropertiesFile.exists() ? signingConfigs.release : signingConfigs.debug",
        )
        groovy.write_text(g)
        print("build.gradle: assinatura configurada")
else:
    print("AVISO: build.gradle não encontrado; APK sai com a chave de depuração")
