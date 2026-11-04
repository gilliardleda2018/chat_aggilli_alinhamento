#!/usr/bin/env bash
# ============================================================================
# Gera o pacote Linux (.deb) do Video Builder Pro - Aggilli Intelligence.
#
#   cd projetos/video-builder-pro
#   python instalador/gerar_icones.py            (ou --sem-logo para teste)
#   pyinstaller --noconfirm instalador/video_builder_pro.spec
#   bash instalador/build_deb.sh                 -> dist/instalador/video-builder-pro_<versao>_amd64.deb
#
# Instalar:     sudo apt install ./video-builder-pro_<versao>_amd64.deb
# Desinstalar:  sudo apt remove video-builder-pro
#
# Decisoes:
#  - Programa em /opt/aggilli/video-builder-pro, comando "video-builder-pro" em
#    /usr/bin, atalho no menu (.desktop) e icone no tema hicolor.
#  - FFmpeg: usa o do sistema (Depends: ffmpeg), atualizado pelo apt, em vez de
#    embutir um binario (diferente do Windows, onde nao ha gerenciador padrao).
#  - Configuracoes do usuario (~/.video_builder_pro) nunca sao tocadas.
# ============================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
VERSAO="$(python3 "$RAIZ/instalador/versao.py")"
DIST="$RAIZ/dist/VideoBuilderPro"
ICONES="$RAIZ/assets/gerados"
PKG="video-builder-pro"
ARQ="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
TRAB="$(mktemp -d)"
trap 'rm -rf "$TRAB"' EXIT

[ -x "$DIST/VideoBuilderPro" ] || { echo "ERRO: rode o PyInstaller antes ($DIST/VideoBuilderPro nao existe)"; exit 1; }
[ -f "$ICONES/icone_256.png" ] || { echo "ERRO: rode instalador/gerar_icones.py antes"; exit 1; }

R="$TRAB/raiz"
mkdir -p "$R/DEBIAN" "$R/opt/aggilli/$PKG" "$R/usr/bin" "$R/usr/share/applications" \
         "$R/usr/share/icons/hicolor/256x256/apps" "$R/usr/share/icons/hicolor/512x512/apps" \
         "$R/usr/share/doc/$PKG"

cp -a "$DIST/." "$R/opt/aggilli/$PKG/"
cp "$ICONES/icone_256.png" "$R/usr/share/icons/hicolor/256x256/apps/$PKG.png"
cp "$ICONES/icone_512.png" "$R/usr/share/icons/hicolor/512x512/apps/$PKG.png"

cat > "$R/usr/bin/$PKG" <<'SH'
#!/bin/sh
exec /opt/aggilli/video-builder-pro/VideoBuilderPro "$@"
SH
chmod 755 "$R/usr/bin/$PKG"

cat > "$R/usr/share/applications/$PKG.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Video Builder Pro
GenericName=Editor de video com IA
Comment=Editor de video profissional com Diretor IA - Aggilli Intelligence
Exec=$PKG %F
Icon=$PKG
Terminal=false
Categories=AudioVideo;Video;AudioVideoEditing;
MimeType=video/mp4;video/quicktime;video/x-matroska;video/webm;
StartupWMClass=VideoBuilderPro
DESK

cat > "$R/usr/share/doc/$PKG/copyright" <<TXT
Video Builder Pro
Copyright (c) Aggilli Intelligence
Usa FFmpeg do sistema (pacote ffmpeg, licencas LGPL/GPL).
TXT

TAM_KB="$(du -sk "$R/opt" | cut -f1)"
cat > "$R/DEBIAN/control" <<CTRL
Package: $PKG
Version: $VERSAO
Section: video
Priority: optional
Architecture: $ARQ
Depends: ffmpeg
Installed-Size: $TAM_KB
Maintainer: Aggilli Intelligence
Homepage: https://github.com/gilliardleda2018/chat_aggilli_alinhamento
Description: Editor de video profissional com IA (Aggilli Intelligence)
 Video Builder Pro: edicao, cor, audio, legendas, QC e Diretor IA
 (corte automatico de fala, direcao e revisao com Claude).
CTRL

cat > "$R/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
exit 0
POST
cp "$R/DEBIAN/postinst" "$R/DEBIAN/postrm"
chmod 755 "$R/DEBIAN/postinst" "$R/DEBIAN/postrm"

# permissoes previsiveis (dpkg reclama de arquivos de outros donos/modos)
find "$R/opt" -type d -exec chmod 755 {} +
find "$R/opt" -type f -exec chmod u+rw,go+r {} +
chmod 755 "$R/opt/aggilli/$PKG/VideoBuilderPro"

SAIDA="$RAIZ/dist/instalador"
mkdir -p "$SAIDA"
DEB="$SAIDA/${PKG}_${VERSAO}_${ARQ}.deb"
dpkg-deb --root-owner-group --build "$R" "$DEB" >/dev/null
echo "[OK] $DEB ($(du -h "$DEB" | cut -f1))"
