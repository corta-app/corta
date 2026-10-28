"""Exporta de verdad (ffmpeg) un proyecto con velocidad por tramo y cuenta qué cuadro del original quedó en cada cuadro exportado,
para compararlo con la vista previa (pruebas/velocidad.mjs). También mide cuánto cuesta exportar 8 s a cada velocidad.

Uso: python3 pruebas/cuadros_velocidad.py <entrada.json> <salida.json>
  entrada: {"proyecto": {...} (sin fuente), "carpeta": temporal, "medir": [{"nombre", "velocidad": {...} o null}], "demo": ruta a un video}
  salida:  {"video": ruta del video de prueba, "duracion": s del exportado, "cuadros": [n° de cuadro del original en cada cuadro
            exportado, o -1 si no se pudo leer], "texto": [hay subtítulo en ese cuadro], "ass": [[inicio, texto] de cada palabra],
            "costos": [{"nombre", "segundos", "duracion"}]}
El video de prueba lleva el número de cada cuadro escrito en 12 franjas blancas y negras (binario) en la mitad de arriba; abajo es
negro, para ver los subtítulos. Su audio es un tono.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRANJAS, ANCHO, ALTO = 12, 360, 640


def main(entrada, salida):
    with open(entrada, encoding="utf-8") as f:
        d = json.load(f)
    os.environ["CORTA_CARPETA"] = d["carpeta"]
    sys.path.insert(0, os.path.join(RAIZ, "bin"))
    import proyecto  # noqa: E402
    import render  # noqa: E402
    import subtitulos  # noqa: E402

    carpeta = os.path.join(d["carpeta"], "velocidad")
    os.makedirs(carpeta, exist_ok=True)
    video = os.path.join(carpeta, "original.mp4")
    numeros = f"geq=lum='if(lt(Y,{ALTO // 2}),if(mod(floor(N/pow(2,floor(X/{ANCHO // FRANJAS}))),2),235,16),16)':cb=128:cr=128"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={ANCHO}x{ALTO}:r=30:d=8,format=yuv420p,{numeros}",
                    "-f", "lavfi", "-i", "sine=f=440:d=8", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-g", "15", "-pix_fmt",
                    "yuv420p", "-c:a", "aac", "-shortest", video], check=True)
    p = {**proyecto.nuevo("velocidad", {"archivo": "original.mp4", "duracion": 8.0, "ancho": ANCHO, "alto": ALTO}), **d["proyecto"]}
    p["fuente"] = {"archivo": "original.mp4", "duracion": 8.0, "ancho": ANCHO, "alto": ALTO}
    problemas = proyecto.validar(p)
    if problemas:
        raise ValueError(problemas)
    proyecto.guardar(carpeta, p, respaldo=False)
    r = render.exportar(carpeta)
    W, H = proyecto.LIENZOS[p["lienzo"]]
    # Cada cuadro exportado: la fila del medio de las franjas (12 valores) y lo más claro de la zona de los subtítulos.
    franjas = subprocess.run(["ffmpeg", "-v", "error", "-i", r["archivo"], "-vf", f"crop={W}:{H // 8}:0:{H // 5},scale={FRANJAS}:1:flags=area,format=gray",
                              "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    cuadros = []
    for k in range(len(franjas) // FRANJAS):
        fila = franjas[k * FRANJAS:(k + 1) * FRANJAS]
        if any(60 < x < 190 for x in fila):
            cuadros.append(-1)  # un cuadro mezclado (no debería haber: el proyecto de prueba no suaviza)
        else:
            cuadros.append(sum(1 << b for b, x in enumerate(fila) if x >= 190))
    abajo = subprocess.run(["ffmpeg", "-v", "error", "-i", r["archivo"], "-vf", f"crop={W}:{H // 4}:0:{H * 3 // 4},scale=64:16:flags=area,format=gray",
                            "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    texto = [max(abajo[k * 1024:(k + 1) * 1024]) > 120 for k in range(len(abajo) // 1024)]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", r["archivo"]],
                               capture_output=True, text=True).stdout)
    # Cuándo empieza cada palabra en el archivo de subtítulos (el mismo que usó ffmpeg).
    estilo = subtitulos.estilos()["pop"]
    q = {**p, "subtitulos": {**p["subtitulos"], "palabras_por_linea": 1}}
    ass = [[sum(float(x) * m for x, m in zip(re.split("[:]", a), (3600, 60, 1))), t]
           for a, t in re.findall(r"Dialogue: 0,([^,]+),[^,]+,Corta,,0,0,0,,\{[^}]*\}([^{\n]+)", subtitulos.ass(q, estilo, W, H))]
    costos = []
    demo = d.get("demo")
    for m in d.get("medir", []) if demo else []:
        c = os.path.join(d["carpeta"], "costo-" + m["nombre"])
        os.makedirs(c, exist_ok=True)
        shutil.copy(demo, os.path.join(c, "original.mp4"))
        x = proyecto.nuevo(m["nombre"], {"archivo": "original.mp4", "duracion": 30.24, "ancho": 1280, "alto": 720})
        x["subtitulos"]["activos"] = False
        x["cortes"] = [{"i": 8, "f": 30.24, "motivo": "manual"}]
        if m.get("velocidad"):
            x["velocidades"] = [{"i": 0, "f": 8, **m["velocidad"]}]
        proyecto.guardar(c, x, respaldo=False)
        inicio = time.time()
        e = render.exportar(c)
        costos.append({"nombre": m["nombre"], "segundos": round(time.time() - inicio, 2), "duracion": e["duracion"]})
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"video": video, "duracion": dur, "cuadros": cuadros, "texto": texto, "ass": ass, "costos": costos}, f)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
