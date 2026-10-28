#!/usr/bin/env python3
"""Transcriptor falso para las pruebas: se instala como «corta-transcribir» en un PATH temporal. Acepta las opciones de
corta-transcribir, deja el vocabulario que recibió (--prompt-archivo) en $CORTA_PRUEBA_PROMPT y escribe una transcripción ficticia
donde «Kalumi» (una marca inventada) sale mal escrita, como la escribiría whisper sin conocerla."""
import json
import os
import sys

a = sys.argv[1:]
salida, prompt = "", ""
for k, x in enumerate(a):
    if x == "-of":
        salida = a[k + 1]
    if x == "--prompt-archivo":
        with open(a[k + 1], encoding="utf-8") as f:
            prompt = f.read()
if os.environ.get("CORTA_PRUEBA_PROMPT"):
    with open(os.environ["CORTA_PRUEBA_PROMPT"], "w", encoding="utf-8") as f:
        f.write(prompt)
palabras = [" Hola,", " soy", " de", " calumi.", " Calumi", " ayuda", " a", " Ana."]
segmentos = [{"text": t, "offsets": {"from": 500 + 400 * k, "to": 850 + 400 * k}} for k, t in enumerate(palabras)]
with open(salida + ".json", "w", encoding="utf-8") as f:
    json.dump({"transcription": segmentos}, f)
