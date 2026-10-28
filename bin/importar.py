"""Traer un video a Corta y transcribirlo en tu computador. Solo biblioteca estándar.

  importar.py <video> <salida.json>                 crea ~/Corta/<nombre>/ con proyecto.json (vertical por defecto)
  importar.py transcribir <carpeta> <salida.json>   transcribe con whisper (palabra por palabra) y guarda las palabras

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

MODELOS = os.path.join(proyecto.INTERNO, "modelos")
ARCHIVOS_MODELO = {"turbo": "ggml-large-v3-turbo-q5_0.bin", "small": "ggml-small-q5_1.bin"}
# Lo que whisper inventa cuando hay silencio o música (créditos de los videos con que se entrenó).
ALUCINACIONES = {"thank you", "thanks for watching", "gracias", "gracias por ver", "suscríbete", "amara.org", "subtítulos realizados por la comunidad de amara.org"}


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


def palabras_de_whisper(datos):
    """whisper.cpp con -ml 1 -sow -oj: cada segmento es una palabra. Se descartan marcas ([música]) e inventos en silencio."""
    r = []
    for s in datos.get("transcription", []):
        t = (s.get("text") or "").strip()
        if not t or re.fullmatch(r"[\[(].*[\])]", t):
            continue
        i, f = s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000
        if r and not re.match(r"^[\wáéíóúñü¿¡]", t, re.I):  # puntuación suelta: va pegada a la palabra anterior
            r[-1]["t"] += t
            r[-1]["f"] = max(r[-1]["f"], f)
            continue
        if f > i:
            r.append({"t": t, "i": round(i, 3), "f": round(f, 3)})
    texto = " ".join(w["t"] for w in r).lower().strip(" .")
    return [] if texto in ALUCINACIONES else r


def transcribir(carpeta):
    p = proyecto.cargar(carpeta)
    cfg = proyecto.config()
    modelo = os.path.join(MODELOS, ARCHIVOS_MODELO.get(cfg["modelo"], ARCHIVOS_MODELO["turbo"]))
    if not os.path.exists(modelo):
        raise RuntimeError("Falta el modelo de transcripción: descárgalo en Ajustes.")
    # En Mac viene dentro de la app (corta-transcribir, whisper.cpp con Metal y las mismas opciones); en desarrollo, whisper-cli.
    binario = proyecto.programa("corta-transcribir", "whisper-cli")
    if not os.path.isfile(binario):
        raise RuntimeError("No encontré el transcriptor (whisper-cli).")
    audio = os.path.join(carpeta, "audio.wav")
    proyecto.escribir_json(os.path.join(carpeta, "estado.json"), {"paso": "audio", "texto": "Preparando el audio…"})
    subprocess.run([proyecto.programa("ffmpeg"), "-hide_banner", "-y", "-loglevel", "error", *proyecto.SOLO_ARCHIVOS,
                    "-i", proyecto.entrada(os.path.join(carpeta, p["fuente"]["archivo"])),
                    "-vn", "-ac", "1", "-ar", "16000", audio], check=True)
    proyecto.escribir_json(os.path.join(carpeta, "estado.json"), {"paso": "transcribiendo", "texto": "Transcribiendo en tu computador…"})
    hilos = str(max(2, min(8, (os.cpu_count() or 4) - 1)))
    salida = os.path.join(carpeta, "transcripcion")
    r = subprocess.run([binario, "-m", modelo, "-l", cfg.get("idioma_audio") or "auto", "-t", hilos, "-f", audio,
                        "-ml", "1", "-sow", "-oj", "-of", salida, "-np"], capture_output=True, text=True, timeout=4 * 3600)
    os.remove(audio)
    if r.returncode != 0 or not os.path.exists(salida + ".json"):
        raise RuntimeError("La transcripción falló: " + (r.stderr or "")[-300:])
    p = proyecto.cargar(carpeta)
    p["palabras"] = palabras_de_whisper(proyecto.leer_json(salida + ".json", {}))
    os.remove(salida + ".json")
    proyecto.guardar(carpeta, p)
    os.remove(os.path.join(carpeta, "estado.json"))
    return {"ok": True, "palabras": len(p["palabras"]), "proyecto": p}


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
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[-1], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False))
