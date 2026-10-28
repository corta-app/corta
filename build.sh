#!/bin/bash
# Compila Corta y la instala en ~/Applications/Corta.app (para desarrollo en este Mac).
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH
RAIZ="$(cd "$(dirname "$0")" && pwd)"
# Cerrar la app en medio de una exportación, una transcripción o mientras trae un video los cortaría.
if pgrep -f "bin/render.py|bin/importar.py" >/dev/null && [ "${FORZAR:-0}" != "1" ]; then
  echo "✗ Corta está trabajando en un video (exportando o transcribiendo). Espera a que termine (o usa FORZAR=1)." >&2; exit 3
fi
bash "$RAIZ/herramientas/empaquetar.sh"
APP="$HOME/Applications/Corta.app"
mkdir -p "$HOME/Applications"
osascript -e 'tell application id "app.corta.mac" to quit' 2>/dev/null || true
sleep 1
rm -rf "$APP"
ditto "$RAIZ/dist/Corta.app" "$APP"
# La app sabe que viene de este checkout: se actualiza con git pull (Ajustes → Buscar actualizaciones).
mkdir -p "$HOME/Corta/.corta" && echo "$RAIZ" > "$HOME/Corta/.corta/desarrollo"
echo "Instalada en $APP ($(du -sh "$APP" | cut -f1))"
