"""Cuadros exportados de verdad (ffmpeg) para comparar la vista previa de las transiciones con lo que sale (pruebas/interfaz.mjs).

Uso: python3 pruebas/cuadros_transiciones.py <entrada.json> <salida.json>
  entrada: {"proyecto": {...}, "video": ruta, "casos": [{"nombre", "pasos" (o null: sin efecto), "tiempos": [s del exportado]}],
            "grilla": [ancho, alto]}
  salida:  {"nombre": {"tiempos": [...], "cuadros": [[r, g, b, r, g, b, …] por tiempo], "duracion": s, "segundos": lo que tardó}}
Cada cuadro es el promedio de bloques de una grilla chica (área), en RGB.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "bin"))
import proyecto  # noqa: E402
import render  # noqa: E402
import subtitulos  # noqa: E402


def main(entrada, salida):
    with open(entrada, encoding="utf-8") as f:
        d = json.load(f)
    gw, gh = d.get("grilla", [18, 32])
    r = {}
    with tempfile.TemporaryDirectory(prefix="corta-cuadros-") as tmp:
        for caso in d["casos"]:
            p = json.loads(json.dumps(d["proyecto"]))
            p["efectos"] = [{"efecto": "prueba", "pasos": caso["pasos"]}] if caso.get("pasos") else []
            problemas = proyecto.validar(p)
            if problemas:
                raise ValueError(f"{caso['nombre']}: {problemas}")
            W, H = proyecto.LIENZOS[p["lienzo"]]
            ass = os.path.join(tmp, "s.ass")
            with open(ass, "w", encoding="utf-8") as f:
                f.write(subtitulos.ass(p, next(iter(subtitulos.estilos().values())), W, H))
            grafo = os.path.join(tmp, "g.txt")
            with open(grafo, "w", encoding="utf-8") as f:
                f.write(render.grafo(p, render.tiene_audio(d["video"]), ass, False))
            video = os.path.join(tmp, caso["nombre"] + ".mp4")
            inicio = time.time()
            x = subprocess.run(["ffmpeg", "-v", "error", "-y", *proyecto.SOLO_ARCHIVOS, "-i", proyecto.entrada(d["video"]),
                                "-filter_complex_script", grafo, "-map", "[vs]", "-map", "[as]", "-c:v", "libx264", "-preset", "veryfast",
                                "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "aac", video], capture_output=True, text=True)
            if x.returncode:
                raise RuntimeError(x.stderr[-500:])
            segundos = time.time() - inicio
            cuadros = []
            for t in caso["tiempos"]:
                crudo = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"select='eq(n,{round(t * 30)})',scale={gw}:{gh}:flags=area,format=rgb24",
                                        "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True).stdout
                cuadros.append(list(crudo))
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                       capture_output=True, text=True).stdout)
            r[caso["nombre"]] = {"tiempos": caso["tiempos"], "cuadros": cuadros, "duracion": dur, "segundos": round(segundos, 2)}
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(r, f)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
