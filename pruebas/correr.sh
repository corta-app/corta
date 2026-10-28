#!/bin/bash
# Todas las pruebas (las mismas que corre GitHub en cada cambio). Necesita ffmpeg.
# Uso: bash pruebas/correr.sh   (la interfaz necesita Playwright: PLAYWRIGHT=/ruta/a/playwright si no está en node_modules)
set -e
cd "$(dirname "$0")/.."
echo "Sintaxis"; node --check ui/app.js; python3 -m py_compile bin/*.py pruebas/*.py ejemplos/*.py
python3 -c "import json, glob; [json.load(open(f, encoding='utf-8')) for f in glob.glob('ui/idiomas/*.json') + glob.glob('estilos/*.json') + glob.glob('efectos/*/*.json') + glob.glob('plantillas/*/*.json') + ['ui/demo.json', 'pruebas/casos.json']]"
for f in build.sh herramientas/*.sh pruebas/*.sh; do bash -n "$f"; done
echo "Privacidad"; bash herramientas/revisar_privacidad.sh --generico
echo "Contrato"; python3 pruebas/contrato.py
echo "Python"; python3 pruebas/test_python.py 2>&1 | tail -3
echo "Interfaz"; node pruebas/interfaz.mjs
echo "Transiciones (vista previa ↔ exportado)"; node pruebas/transiciones.mjs
echo "Velocidad (vista previa ↔ exportado)"; node pruebas/velocidad.mjs
