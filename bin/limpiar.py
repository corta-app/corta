"""Cortar silencios y muletillas. Solo biblioteca estándar.

  limpiar.py <carpeta> <silencio_min_seg> <muletillas 0|1> <salida.json>

Con transcripción, usa los espacios entre palabras; sin ella, el detector de silencio de ffmpeg. Los cortes nuevos tienen
motivo «silencio» o «muletilla»: al volver a limpiar se reemplazan (los cortes manuales y de la IA no se tocan).
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402

#: Muletillas que se cortan solas (palabra completa). Las que también son palabras normales («este», «o sea», «like») no están:
#: cortarlas sola rompería frases; para eso está pedirle a tu IA «saca los "o sea"».
MULETILLAS = {"eh", "ehh", "ehhh", "em", "emm", "ehm", "mm", "mmm", "mmmm", "um", "umm", "uh", "uhh", "er", "erm", "ah", "ahh", "hmm", "hm"}
MARGEN = 0.12  # aire que se deja antes y después de hablar, para que no suene cortado


def limpia(t):
    return re.sub(r"[^\wáéíóúñü]", "", t.lower())


def cortes_por_palabras(palabras, silencio_min, muletillas, duracion):
    cortes = []
    if muletillas:
        for k, w in enumerate(palabras):
            if limpia(w["t"]) in MULETILLAS:
                i = w["i"] if k == 0 else max(palabras[k - 1]["f"], w["i"] - 0.05)
                f = w["f"] if k == len(palabras) - 1 else min(palabras[k + 1]["i"], w["f"] + 0.05)
                cortes.append({"i": round(i, 3), "f": round(f, 3), "motivo": "muletilla"})
    huecos = []
    if palabras:
        huecos.append((0.0, palabras[0]["i"]))
        huecos += [(a["f"], b["i"]) for a, b in zip(palabras, palabras[1:])]
        huecos.append((palabras[-1]["f"], duracion))
    for a, b in huecos:
        if b - a >= silencio_min + 2 * MARGEN:
            cortes.append({"i": round(a + (0 if a == 0 else MARGEN), 3), "f": round(b - (0 if b == duracion else MARGEN), 3), "motivo": "silencio"})
    return cortes


def silencios_ffmpeg(video, silencio_min, duracion, ruido_db=-35):
    """Sin transcripción: tramos donde el audio está bajo `ruido_db` por más de silencio_min segundos."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-af", f"silencedetect=noise={ruido_db}dB:d={silencio_min}",
                        "-f", "null", "-"], capture_output=True, text=True)
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    fines = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    cortes = []
    for k, i in enumerate(inicios):
        f = fines[k] if k < len(fines) else duracion
        i2, f2 = i + (0 if i < 0.01 else MARGEN), f - (0 if f >= duracion - 0.01 else MARGEN)
        if f2 - i2 > 0.05:
            cortes.append({"i": round(i2, 3), "f": round(f2, 3), "motivo": "silencio"})
    return cortes


def limpiar(carpeta, silencio_min=0.5, muletillas=True):
    p = proyecto.cargar(carpeta)
    antes = proyecto.duracion_final(p)
    p["cortes"] = [c for c in p["cortes"] if c["motivo"] not in ("silencio", "muletilla")]
    dur = p["fuente"]["duracion"]
    if p["palabras"]:
        nuevos = cortes_por_palabras(p["palabras"], silencio_min, muletillas, dur)
    else:
        nuevos = silencios_ffmpeg(os.path.join(carpeta, p["fuente"]["archivo"]), silencio_min, dur)
    p["cortes"] += nuevos
    proyecto.guardar(carpeta, p)
    despues = proyecto.duracion_final(p)
    return {"ok": True, "silencios": sum(1 for c in nuevos if c["motivo"] == "silencio"),
            "muletillas": sum(1 for c in nuevos if c["motivo"] == "muletilla"), "antes": antes, "despues": despues,
            "ahorro": round(antes - despues, 1), "proyecto": p}


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(2)
    try:
        r = limpiar(sys.argv[1], float(sys.argv[2]), sys.argv[3] == "1")
    except (OSError, ValueError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(sys.argv[4], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False))
