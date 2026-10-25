"""Ejemplo: exporta los subtítulos de un proyecto de Corta como .srt, con los tiempos del video ya editado.

Uso: python3 ejemplos/a_srt.py "<carpeta del proyecto>" [palabras_por_linea]
Solo biblioteca estándar. Deja subtitulos.srt en la carpeta del proyecto.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin"))
import proyecto  # noqa: E402
import subtitulos  # noqa: E402


def tiempo(s):
    ms = int(round(max(0, s) * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def main(carpeta, por_linea=5):
    p = proyecto.cargar(carpeta)
    tramos, cortes = proyecto.conservados(p), proyecto.unir(p["cortes"])
    visibles = []
    for w in p["palabras"]:
        if not proyecto.palabra_cortada(p, w, cortes):
            i = proyecto.a_salida(p, (w["i"] + w["f"]) / 2, tramos)
            if i is not None:
                visibles.append({"t": w["t"], "i": i, "f": i + (w["f"] - w["i"]) / 2})
    bloques = [f"{n}\n{tiempo(g[0]['i'])} --> {tiempo(g[-1]['f'])}\n{' '.join(w['t'] for w in g)}\n"
               for n, g in enumerate(subtitulos.lineas(visibles, por_linea), 1)]
    with open(os.path.join(carpeta, "subtitulos.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(bloques))
    print(f"✓ {len(bloques)} subtítulos en subtitulos.srt")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5)
