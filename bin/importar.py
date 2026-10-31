"""Traer un video a Corta y transcribirlo en tu computador. Solo biblioteca estándar.

  importar.py <video> <salida.json>                 crea ~/Corta/<nombre>/ con proyecto.json (vertical por defecto)
  importar.py transcribir <carpeta> <salida.json>   transcribe con whisper (palabra por palabra, pieza «transcribir») y guarda
                                                    las palabras, ya corregidas con el vocabulario de la persona (bin/vocabulario.py)

El video se copia a la carpeta del proyecto (nunca se modifica). El avance queda en <carpeta>/estado.json.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402
import transcribir as transcribir_  # noqa: E402
import vocabulario  # noqa: E402


def info(video):
    r = subprocess.run([proyecto.programa("ffprobe"), *proyecto.SOLO_ARCHIVOS, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation:format=duration",
                        "-of", "json", proyecto.entrada(video)], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    s = (d.get("streams") or [{}])[0]
    ancho, alto = int(s.get("width") or 0), int(s.get("height") or 0)
    rot = abs(int(float((s.get("tags") or {}).get("rotate") or next((x.get("rotation", 0) for x in s.get("side_data_list", [])), 0) or 0)))
    if rot in (90, 270):  # videos de celular grabados en vertical
        ancho, alto = alto, ancho
    dur = float((d.get("format") or {}).get("duration") or 0)
    if not (ancho and alto and dur):
        raise ValueError("No pude leer ese video (¿está completo?).")
    return {"ancho": ancho, "alto": alto, "duracion": round(dur, 3)}


def nombre_carpeta(titulo):
    limpio = re.sub(r"[\\/:*?\"<>|]+", " ", titulo).strip()[:60] or "Video"
    base = os.path.join(proyecto.BASE, f"{time.strftime('%Y-%m-%d')} {limpio}")
    ruta, n = base, 2
    while os.path.exists(ruta):
        ruta, n = f"{base} ({n})", n + 1
    return ruta


def importar(video):
    datos = info(video)
    titulo = os.path.splitext(os.path.basename(video))[0]
    carpeta = nombre_carpeta(titulo)
    os.makedirs(carpeta)
    archivo = "original" + os.path.splitext(video)[1].lower()
    shutil.copy2(video, os.path.join(carpeta, archivo))
    p = proyecto.nuevo(titulo, {"archivo": archivo, **datos})
    if datos["alto"] > datos["ancho"]:  # ya es vertical: el encuadre no importa
        p["encuadre"] = {"x": 0.5, "y": 0.5}
    proyecto.guardar(carpeta, p, respaldo=False)
    return {"ok": True, "carpeta": carpeta, "proyecto": p}


def transcribir(carpeta):
    """Palabra por palabra con la pieza «transcribir» ({t, i, f} en segundos del original). Sin VAD: el detector de voz puede
    recortar la primera o la última palabra de una frase y aquí cada palabra es un borde de corte."""
    p = proyecto.cargar(carpeta)
    cfg = proyecto.config()
    modelo = transcribir_.modelo_elegido(cfg["modelo"])
    if not modelo:
        raise transcribir_.ErrorTranscribir("sin_modelo")
    if not transcribir_.transcriptor():
        raise transcribir_.ErrorTranscribir("sin_transcriptor")
    audio = os.path.join(carpeta, "audio.wav")
    proyecto.escribir_json(os.path.join(carpeta, "estado.json"), {"paso": "audio", "texto": "Preparando el audio…"})
    subprocess.run([proyecto.programa("ffmpeg"), "-hide_banner", "-y", "-loglevel", "error", *proyecto.SOLO_ARCHIVOS,
                    "-i", proyecto.entrada(os.path.join(carpeta, p["fuente"]["archivo"])),
                    "-vn", "-ac", "1", "-ar", "16000", audio], check=True)
    proyecto.escribir_json(os.path.join(carpeta, "estado.json"), {"paso": "transcribiendo", "texto": "Transcribiendo en tu computador…"})
    vocab = vocabulario.leer()
    try:
        palabras = transcribir_.transcribir(audio, palabras=True, vad=False, idioma=cfg.get("idioma_audio") or "auto",
                                            modelo=modelo, vocabulario=vocabulario.prompt(vocab))
    finally:
        if os.path.exists(audio):
            os.remove(audio)
    p = proyecto.cargar(carpeta)
    p["palabras"], corregidas = vocabulario.reemplazar_todo(palabras, vocabulario.pares(vocab))
    proyecto.guardar(carpeta, p)
    os.remove(os.path.join(carpeta, "estado.json"))
    return {"ok": True, "palabras": len(p["palabras"]), "corregidas": corregidas, "proyecto": p}

if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) == 3 and a[0] == "transcribir":
            r = transcribir(a[1])
        elif len(a) == 2:
            r = importar(a[0])
        else:
            print(__doc__)
            sys.exit(2)
    except transcribir_.ErrorTranscribir as e:
        r = {"ok": False, "error": str(e), "codigo": e.codigo}
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[-1], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False))
