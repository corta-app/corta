#!/usr/bin/env python3
"""Transcriptor falso para las pruebas: se instala como «corta-transcribir» (o «whisper-cli») en un PATH temporal. Acepta las opciones
de corta-transcribir y el archivo de argumentos de whisper-cli (`@archivo`, una opción por línea), deja el vocabulario que recibió
(--prompt-archivo o --prompt dentro del archivo) en $CORTA_PRUEBA_PROMPT, anota sus argumentos y los permisos de los archivos que
recibió en $CORTA_PRUEBA_REGISTRO y escribe una transcripción ficticia donde «Kalumi» (una marca inventada) sale mal escrita, como
la escribiría whisper sin conocerla."""
import json
import os
import stat
import sys

argv = sys.argv[1:]
archivos = {}
a = argv
if len(argv) == 1 and argv[0].startswith("@"):
    ruta = argv[0][1:]
    archivos[ruta] = stat.S_IMODE(os.stat(ruta).st_mode)
    with open(ruta, encoding="utf-8") as f:
        a = f.read().split("\n")
salida, prompt = "", ""
for k, x in enumerate(a):
    if x == "-of":
        salida = a[k + 1]
    if x == "--prompt":
        prompt = a[k + 1]
    if x == "--prompt-archivo":
        archivos[a[k + 1]] = stat.S_IMODE(os.stat(a[k + 1]).st_mode)
        with open(a[k + 1], encoding="utf-8") as f:
            prompt = f.read()
if os.environ.get("CORTA_PRUEBA_PROMPT"):
    with open(os.environ["CORTA_PRUEBA_PROMPT"], "w", encoding="utf-8") as f:
        f.write(prompt)
if os.environ.get("CORTA_PRUEBA_REGISTRO"):
    with open(os.environ["CORTA_PRUEBA_REGISTRO"], "w", encoding="utf-8") as f:
        json.dump({"argv": argv, "opciones": a, "archivos": archivos}, f)
palabras = [" Hola,", " soy", " de", " calumi.", " Calumi", " ayuda", " a", " Ana."]
segmentos = [{"text": t, "offsets": {"from": 500 + 400 * k, "to": 850 + 400 * k}} for k, t in enumerate(palabras)]
with open(salida + ".json", "w", encoding="utf-8") as f:
    json.dump({"transcription": segmentos}, f)
