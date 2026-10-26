"""Elegir la música de fondo de un proyecto. Solo biblioteca estándar.

  musica.py <carpeta> <archivo de audio> <salida.json>

Copia el audio dentro de la carpeta del proyecto (`musica/<nombre>`) para que el proyecto no dependa de dónde estaba y para que la
app pueda servirlo a la vista previa (corta://video/<carpeta>/musica/<nombre>, solo dentro de ~/Corta). Nunca reemplaza una copia
por otro contenido: si ya hay una distinta con ese nombre, usa «nombre (2)». Así deshacer sigue sonando con la música anterior.
Deja p["musica"] = {"archivo": "musica/<nombre>", "volumen"} (el formato de siempre; si ya había música, mantiene su volumen).
El archivo original nunca se modifica. Quitar la música es guardar el proyecto con "musica": null.
"""
import filecmp
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402
import render  # noqa: E402

EXTENSIONES = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".opus", ".flac"}
VOLUMEN = 0.15  # el mismo que usa render.py si falta
MAXIMO = 500 * 1024 * 1024


def nombre_seguro(nombre):
    """Solo el nombre (sin carpetas), sin caracteres de control ni los que no se pueden usar en Windows, de hasta 80 caracteres."""
    base, ext = os.path.splitext(os.path.basename(nombre.replace("\\", "/")))
    if not ext and base.startswith("."):  # «.wav» sin nombre
        base, ext = "", base
    base = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "", base).strip(" .") or "musica"
    return base[:80] + ext.lower()


def destino_libre(carpeta_musica, nombre, origen):
    """La ruta donde copiar: la misma si ya está esa copia exacta, o una con «(2)», «(3)»… si hay otra distinta."""
    base, ext = os.path.splitext(nombre)
    n = 1
    while True:
        candidato = os.path.join(carpeta_musica, nombre if n == 1 else f"{base} ({n}){ext}")
        if not os.path.exists(candidato) or filecmp.cmp(candidato, origen, shallow=False):
            return candidato
        n += 1


def elegir(carpeta, archivo):
    if os.path.splitext(archivo)[1].lower() not in EXTENSIONES:
        raise ValueError("Ese archivo no es de música. Usa MP3, M4A, WAV, OGG o FLAC.")
    if not os.path.isfile(archivo):
        raise ValueError("No encontré ese archivo de música.")
    if os.path.getsize(archivo) > MAXIMO:
        raise ValueError("Ese archivo de música es demasiado grande (más de 500 MB).")
    if not render.tiene_audio(archivo):
        raise ValueError("No pude leer el audio de ese archivo.")
    p = proyecto.cargar(carpeta)
    carpeta_musica = os.path.join(carpeta, "musica")
    os.makedirs(carpeta_musica, exist_ok=True)
    destino = destino_libre(carpeta_musica, nombre_seguro(archivo), archivo)
    if not os.path.exists(destino):
        shutil.copy2(archivo, destino)
    volumen = (p.get("musica") or {}).get("volumen", VOLUMEN)
    p["musica"] = {"archivo": "musica/" + os.path.basename(destino), "volumen": volumen}
    proyecto.guardar(carpeta, p)
    return {"ok": True, "carpeta": carpeta, "proyecto": p}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    try:
        r = elegir(sys.argv[1], sys.argv[2])
    except (OSError, ValueError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(sys.argv[3], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False))
