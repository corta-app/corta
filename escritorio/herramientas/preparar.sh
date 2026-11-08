#!/bin/bash
# Arma lo que la app (Mac, Windows o Linux) lleva adentro, para que la persona no instale nada:
#   vendor/<mac|linux|win>/python        Python portátil (python-build-standalone, verificado por SHA-256; ../herramientas/python.lock)
#   vendor/<mac|linux|win>/herramientas  Los programas de app.json → empaquetado.<mac|escritorio>.binarios (cada uno con su huella),
#                                    whisper-cli si empaquetado.whisper (compilado aquí) y lo que
#                                    arme herramientas/preparar-extra.sh (opcional, de la app).
# Uso: bash herramientas/preparar.sh mac|linux|windows      Necesita: curl, tar y gzip. Corre en Linux o macOS.
# Generado por la pieza «empaquetado» de Pieza (MPL-2.0, https://mozilla.org/MPL/2.0/) desde app.json: si lo cambias, desde ahí
# es de la app y Pieza ya no lo toca.
set -euo pipefail
cd "$(dirname "$0")/.."

SO="${1:?uso: preparar.sh mac|linux|windows}"
case "$SO" in mac) OS=mac; EXE="" ;; linux) OS=linux; EXE="" ;; windows | win) OS=win; EXE=".exe" ;; *) echo "sistema desconocido: $SO"; exit 1 ;; esac
DESTINO="vendor/$OS"
CACHE_VAR=CORTA_CACHE
CACHE="${!CACHE_VAR:-$HOME/.cache/corta-escritorio}"
mkdir -p "$CACHE" "$DESTINO/herramientas"

huella() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
bajar() { # url sha destino
  if [ -f "$3" ] && [ "$(huella "$3")" = "$2" ]; then return; fi
  echo "→ $(basename "$3")"
  curl -fL --proto '=https' --retry 3 -o "$3.tmp" "$1"
  [ "$(huella "$3.tmp")" = "$2" ] || { echo "✗ Huella distinta: $1 (no se usa)"; rm -f "$3.tmp"; exit 1; }
  mv "$3.tmp" "$3"
}

# ── Python portátil: el mismo que la app de Mac y que las demás apps de la familia ──
LOCK=../herramientas/python.lock
case "$OS" in mac) CLAVE=mac ;; linux) CLAVE=linux ;; *) CLAVE=windows ;; esac
read -r _ PY_URL PY_SHA < <(grep "^$CLAVE " "$LOCK")
PY_VER=$(sed -n 's/^version //p' "$LOCK")
bajar "$PY_URL" "$PY_SHA" "$CACHE/python-$PY_VER-$OS.tar.gz"
rm -rf "$DESTINO/python" "$DESTINO/python.tmp"; mkdir -p "$DESTINO/python.tmp"
tar -xzf "$CACHE/python-$PY_VER-$OS.tar.gz" -C "$DESTINO/python.tmp"
mv "$DESTINO/python.tmp/python" "$DESTINO/python"; rmdir "$DESTINO/python.tmp"
# Más liviano: sin pruebas, tkinter, idle, pip ni encabezados (la app solo usa la biblioteca estándar).
for d in lib/python3.13/test lib/python3.13/idlelib lib/python3.13/tkinter lib/python3.13/turtledemo lib/python3.13/ensurepip lib/python3.13/site-packages \
         lib/tcl9.0 lib/tk9.0 Lib/test Lib/idlelib Lib/tkinter Lib/turtledemo Lib/ensurepip Lib/site-packages Lib/venv include share tcl libs; do rm -rf "$DESTINO/python/$d"; done
find "$DESTINO/python" \( -name "*.pdb" -o -name "__pycache__" -o -name "libtcl*" -o -name "libtk*" -o -name "_tkinter*" \) -prune -exec rm -rf {} +
rm -f "$DESTINO/python/bin/"{idle3*,pip*,pydoc3*,python3*-config} 2>/dev/null || true

# ── ffmpeg (Mac) ──
if [ "$OS" = mac ]; then
  bajar "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-darwin-arm64.gz" "8923876afa8db5585022d7860ec7e589af192f441c56793971276d450ed3bbfa" "$CACHE/8923876afa8db5585022d7860ec7e589af192f441c56793971276d450ed3bbfa-ffmpeg"
  gzip -dc "$CACHE/8923876afa8db5585022d7860ec7e589af192f441c56793971276d450ed3bbfa-ffmpeg" > "$DESTINO/herramientas/ffmpeg"
fi

# ── ffprobe (Mac) ──
if [ "$OS" = mac ]; then
  bajar "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-darwin-arm64.gz" "d986a8ec7b030899fe66a8a288ed809a3543338705a3ce178cfb85869c5d80be" "$CACHE/d986a8ec7b030899fe66a8a288ed809a3543338705a3ce178cfb85869c5d80be-ffprobe"
  gzip -dc "$CACHE/d986a8ec7b030899fe66a8a288ed809a3543338705a3ce178cfb85869c5d80be-ffprobe" > "$DESTINO/herramientas/ffprobe"
fi

# ── whisper-cli (app.json → empaquetado.whisper): whisper.cpp oficial compilado aquí, un solo ejecutable sin bibliotecas aparte.
# Mac: Apple clang con Metal (la GPU) y Accelerate, Apple Silicon. Windows y Linux: zig (glibc 2.28+, Windows 10+), x86-64 con AVX2.
# La etiqueta se puede mover, el commit no: si no coincide, no se compila. Necesita git y cmake (y python3 para zig).
WHISPER_VER=v1.8.3
WHISPER_COMMIT=2eeeba56e9edd762b4b38467bab96c2517163158
ZIG_VER=0.17.0
if [ ! -x "$CACHE/whisper-$WHISPER_VER-$OS/whisper-cli$EXE" ]; then
  [ -d "$CACHE/whisper.cpp" ] || git clone -q --depth 1 --branch "$WHISPER_VER" https://github.com/ggml-org/whisper.cpp "$CACHE/whisper.cpp"
  [ "$(git -C "$CACHE/whisper.cpp" rev-parse HEAD)" = "$WHISPER_COMMIT" ] || { echo "✗ whisper.cpp $WHISPER_VER no es el commit esperado (no se usa)"; exit 1; }
  COMUN=(-DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_BACKEND_DL=OFF -DGGML_OPENMP=OFF
         -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_BUILD_SERVER=OFF -DWHISPER_SDL2=OFF -DWHISPER_CURL=OFF)
  rm -rf "$CACHE/whisper.cpp/build-$OS"
  if [ "$OS" = mac ]; then
    cmake -S "$CACHE/whisper.cpp" -B "$CACHE/whisper.cpp/build-$OS" "${COMUN[@]}" -DCMAKE_OSX_ARCHITECTURES=arm64 \
      -DCMAKE_OSX_DEPLOYMENT_TARGET=13.3 -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON > "$CACHE/whisper-cmake.log"
  else
    python3 -m ziglang version >/dev/null 2>&1 || python3 -m pip install --user --break-system-packages -q "ziglang==$ZIG_VER" 2>/dev/null || python3 -m pip install --user -q "ziglang==$ZIG_VER"
    Z="$CACHE/zig-$OS"; mkdir -p "$Z"
    OBJETIVO=$([ "$OS" = linux ] && echo x86_64-linux-gnu.2.28 || echo x86_64-windows-gnu)
    for h in cc c++; do printf '#!/bin/bash\nexec python3 -m ziglang %s -target %s "$@"\n' "$h" "$OBJETIVO" > "$Z/$h"; done
    for h in ar ranlib; do printf '#!/bin/bash\nexec python3 -m ziglang %s "$@"\n' "$h" > "$Z/$h"; done
    chmod +x "$Z"/*
    EXTRA=(); [ "$OS" = win ] && EXTRA=(-DCMAKE_SYSTEM_NAME=Windows -DCMAKE_SYSTEM_PROCESSOR=x86_64 -DCMAKE_RC_COMPILER=/bin/true)
    cmake -S "$CACHE/whisper.cpp" -B "$CACHE/whisper.cpp/build-$OS" "${COMUN[@]}" "${EXTRA[@]}" -DCMAKE_C_COMPILER="$Z/cc" \
      -DCMAKE_CXX_COMPILER="$Z/c++" -DCMAKE_AR="$Z/ar" -DCMAKE_RANLIB="$Z/ranlib" \
      -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_BMI2=ON > "$CACHE/whisper-cmake.log"
  fi
  cmake --build "$CACHE/whisper.cpp/build-$OS" -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)" --target whisper-cli > "$CACHE/whisper-build.log"
  mkdir -p "$CACHE/whisper-$WHISPER_VER-$OS"
  cp "$CACHE/whisper.cpp/build-$OS/bin/whisper-cli$EXE" "$CACHE/whisper-$WHISPER_VER-$OS/"
fi
cp "$CACHE/whisper-$WHISPER_VER-$OS/whisper-cli$EXE" "$DESTINO/herramientas/"
if [ "$OS" = linux ]; then strip "$DESTINO/herramientas/whisper-cli" 2>/dev/null || true; fi

# Lo que la app arma a su manera (p. ej. compilar un programa): recibe el sistema, el destino y el caché.
if [ -f herramientas/preparar-extra.sh ]; then bash herramientas/preparar-extra.sh "$OS" "$DESTINO" "$CACHE"; fi
if [ "$OS" != win ]; then chmod +x "$DESTINO/herramientas/"* 2>/dev/null || true; fi
echo "Listo: $DESTINO ($(du -sh "$DESTINO" | cut -f1))"
