#!/bin/bash
# Instala (o actualiza) Corta con un solo comando, en Mac:
#   curl -fsSL https://raw.githubusercontent.com/corta-app/corta/main/instalar.sh | bash
# Baja la última versión publicada en GitHub, verifica su huella SHA-256 y la instala solo para tu usuario.
# No pide contraseña ni instala nada más: tus datos quedan en tu computador y nunca se tocan.
# Generado por la pieza «empaquetado» de Pieza (MPL-2.0, https://mozilla.org/MPL/2.0/) desde app.json.
set -euo pipefail
REPO="corta-app/corta"
verde() { printf "\033[32m%s\033[0m\n" "$1"; }
error() { printf "\033[31m✗ %s\033[0m\n" "$1" >&2; exit 1; }
huella() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

SO=$(uname -s)
case "$SO" in
  Darwin)
    [ "$(uname -m)" = "arm64" ] || error "Corta para Mac necesita chip Apple (M1 o posterior)."
    VER=$(sw_vers -productVersion | cut -d. -f1)
    [ "$VER" -ge 15 ] || error "Corta necesita macOS 15 (Sequoia) o posterior. Tienes $(sw_vers -productVersion)."
    ARCHIVO=Corta-macOS.zip ;;
  *) error "Este instalador no tiene Corta para tu sistema." ;;
esac

echo "Buscando la última versión de Corta…"
INFO=$(curl -fsSL -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$REPO/releases/latest") || error "No pude consultar GitHub."
# (sin python: en un Mac recién comprado /usr/bin/python3 pide instalar herramientas de Apple)
TAG=$(printf '%s' "$INFO" | tr ',' '\n' | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || error "No encontré una versión publicada."
BASE="https://github.com/$REPO/releases/download/$TAG"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
echo "Descargando Corta $TAG…"
curl -fL --proto '=https' --progress-bar "$BASE/$ARCHIVO" -o "$TMP/$ARCHIVO" || error "Esta versión aún no tiene descarga para tu sistema."
curl -fsSL --proto '=https' "$BASE/$ARCHIVO.sha256" -o "$TMP/$ARCHIVO.sha256"
[ "$(huella "$TMP/$ARCHIVO")" = "$(cut -d' ' -f1 "$TMP/$ARCHIVO.sha256")" ] || error "La descarga no coincide con su huella. No instalé nada."
verde "✓ Descarga verificada"

if [ "$SO" = Darwin ]; then
  ditto -x -k "$TMP/$ARCHIVO" "$TMP/app"
  xattr -dr com.apple.quarantine "$TMP/app/Corta.app" 2>/dev/null || true
  mkdir -p "$HOME/Applications"
  osascript -e 'tell application id "app.corta.mac" to quit' >/dev/null 2>&1 || true
  sleep 1
  rm -rf "$HOME/Applications/Corta.app"
  ditto "$TMP/app/Corta.app" "$HOME/Applications/Corta.app"
  verde "✓ Corta $TAG instalada en ~/Applications"
  open "$HOME/Applications/Corta.app"
fi
echo "Se abrió Corta: lo primero es elegir tu idioma."
