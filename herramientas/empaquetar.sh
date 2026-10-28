#!/bin/bash
# Arma dist/Corta.app (autosuficiente) y dist/Corta-macOS.zip + .sha256, sin instalar nada. Solo en un Mac (Apple Silicon).
# Lo usan build.sh (en tu Mac) y, cuando exista, la acción de GitHub que publica cada versión.
# Dentro van: la app; corta-transcribir + whisper.framework (whisper.cpp oficial, con Metal); ffmpeg y ffprobe; Python portátil;
# y el código (bin/, ui/, estilos/, efectos/, plantillas/) en Contents/Resources/corta. Los videos y proyectos de la persona quedan en ~/Corta.
# Todo lo que se descarga tiene su huella SHA-256 fija aquí: si no coincide, no se usa y el armado se detiene.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
[ "$(uname -s)" = Darwin ] || { echo "✗ La app de Mac se arma en un Mac." >&2; exit 1; }
[ "$(uname -m)" = arm64 ] || { echo "✗ Por ahora Corta para Mac es solo para Apple Silicon (arm64)." >&2; exit 1; }
cd "$RAIZ/app"
swift build -c release 2>&1 | tee "${CORTA_PROGRESO:-/dev/null}" | tail -20
REL=.build/release
CACHE=.build/descargas
mkdir -p "$CACHE"

huella() { shasum -a 256 "$1" | cut -d' ' -f1; }
bajar() { # url huella destino
  if [ -f "$3" ] && [ "$(huella "$3")" = "$2" ]; then return; fi
  echo "→ $(basename "$3")"
  curl -fsSL --proto '=https' --retry 3 "$1" -o "$3.tmp"
  [ "$(huella "$3.tmp")" = "$2" ] || { rm -f "$3.tmp"; echo "✗ $(basename "$3") no coincide con su huella: no se usa." >&2; exit 1; }
  mv "$3.tmp" "$3"
}

# Python portátil (python-build-standalone): la misma versión y huella que Alcancía, Graba y Minuta. La persona no instala nada.
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261003/cpython-3.13.16%2B20261003-aarch64-apple-darwin-install_only_stripped.tar.gz"
PY_SHA="9e01f63bbb08576cd9c8bc2d0564d098cb30c8453a0cd4bcf6aef458f6d2a147"
bajar "$PY_URL" "$PY_SHA" "$CACHE/python-3.13.16.tar.gz"

# ffmpeg y ffprobe estáticos para Apple Silicon, de ffmpeg-static (github.com/eugeneware/ffmpeg-static, etiqueta b6.1.1; la misma
# fuente que usa Graba en Windows y Linux). Traen libx264 (exportar), libass + fontconfig (subtítulos) y solo enlazan bibliotecas
# del sistema. Licencia GPL: son programas aparte que la app ejecuta (ver LICENCIAS-TERCEROS.txt dentro de la app).
# ffmpeg-static no publica huellas: estas se calcularon al descargarlos de ese Release (28-10-2026) y quedan fijas.
FF_BASE="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
FFMPEG_SHA="8923876afa8db5585022d7860ec7e589af192f441c56793971276d450ed3bbfa"   # ffmpeg-darwin-arm64.gz
FFPROBE_SHA="d986a8ec7b030899fe66a8a288ed809a3543338705a3ce178cfb85869c5d80be"  # ffprobe-darwin-arm64.gz
bajar "$FF_BASE/ffmpeg-darwin-arm64.gz" "$FFMPEG_SHA" "$CACHE/b6.1.1-ffmpeg-darwin-arm64.gz"
bajar "$FF_BASE/ffprobe-darwin-arm64.gz" "$FFPROBE_SHA" "$CACHE/b6.1.1-ffprobe-darwin-arm64.gz"

DIST="$RAIZ/dist"; APP="$DIST/Corta.app"
rm -rf "$DIST"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/corta" "$APP/Contents/Frameworks"
cp "$REL/Corta" "$REL/corta-transcribir" "$APP/Contents/MacOS/"
gzip -dc "$CACHE/b6.1.1-ffmpeg-darwin-arm64.gz" > "$APP/Contents/MacOS/ffmpeg"
gzip -dc "$CACHE/b6.1.1-ffprobe-darwin-arm64.gz" > "$APP/Contents/MacOS/ffprobe"
chmod +x "$APP/Contents/MacOS/"*
cp Info.plist "$APP/Contents/Info.plist"
[ -f Corta.icns ] && cp Corta.icns "$APP/Contents/Resources/Corta.icns"
ditto "$REL/whisper.framework" "$APP/Contents/Frameworks/whisper.framework"
tar -xzf "$CACHE/python-3.13.16.tar.gz" -C "$APP/Contents/Resources"   # → Resources/python/bin/python3
for d in bin ui estilos efectos plantillas; do ditto "$RAIZ/$d" "$APP/Contents/Resources/corta/$d"; done
# La app usa tus videos, nunca la demo (y el video de Ana pesa).
rm -rf "$APP/Contents/Resources/corta/ui/demo.json" "$APP/Contents/Resources/corta/ui/demo"
find "$APP/Contents/Resources/corta" -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
chmod +x "$APP/Contents/Resources/corta/bin/"*.py
cat > "$APP/Contents/Resources/LICENCIAS-TERCEROS.txt" <<'TXT'
Corta se distribuye con la licencia AGPL-3.0 (https://github.com/corta-app/corta). Dentro de la app van, como programas aparte:

- ffmpeg y ffprobe (https://ffmpeg.org), compilación estática de ffmpeg-static b6.1.1
  (https://github.com/eugeneware/ffmpeg-static). Licencia GPL; el código fuente está en https://ffmpeg.org/download.html.
- whisper.cpp v1.8.3 (https://github.com/ggml-org/whisper.cpp), licencia MIT.
- Python 3.13 de python-build-standalone (https://github.com/astral-sh/python-build-standalone), licencia PSF y las de sus partes.
- Tipografías de ui/fuentes con la SIL Open Font License (ver ui/fuentes/OFL.txt).
TXT

# Firma ad hoc, de adentro hacia afuera, con requisito por identificador (macOS reconoce la app entre versiones).
codesign --force --sign - "$APP/Contents/Frameworks/whisper.framework"
find "$APP/Contents/Resources/python" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -u+x \) -exec codesign --force --sign - {} \; 2>/dev/null || true
for p in ffmpeg ffprobe corta-transcribir; do codesign --force --sign - "$APP/Contents/MacOS/$p"; done
codesign --force --sign - --requirements '=designated => identifier "app.corta.mac"' "$APP"

cd "$DIST"
ditto -c -k --keepParent Corta.app Corta-macOS.zip
shasum -a 256 Corta-macOS.zip > Corta-macOS.zip.sha256
echo "Listo: $DIST/Corta-macOS.zip ($(du -h Corta-macOS.zip | cut -f1))"
