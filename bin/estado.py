"""Todo lo que la app de escritorio le manda a la interfaz al abrir o después de un cambio. Solo biblioteca estándar.

  estado.py <salida.json>

{"ok", "proyectos": [{"carpeta", "proyecto"}] (los más nuevos primero), "estilos": [...], "config": {...},
"vocabulario": {...}, "efectos": [...] y "plantillas": [...] (incluidos y descargados)}. Lo propio de cada
app (IA instaladas, modelos descargados, versión, avance de lo que está corriendo) lo agrega la app. Un proyecto.json que no se
puede leer o no es válido no aparece (y no rompe la lista).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402
import efectos  # noqa: E402
import plantillas  # noqa: E402
import subtitulos  # noqa: E402
import vocabulario  # noqa: E402


def proyectos():
    base = os.path.realpath(proyecto.BASE)
    try:
        nombres = os.listdir(base)
    except OSError:
        return []
    r = []
    for n in nombres:
        carpeta = os.path.join(base, n)
        if n.startswith(".") or os.path.islink(carpeta) or not os.path.isdir(carpeta):
            continue
        p = proyecto.leer_json(proyecto.ruta(carpeta), None)
        if isinstance(p, dict) and not proyecto.validar(p):
            r.append({"carpeta": carpeta, "proyecto": p})
    # Los más nuevos primero; el nombre empieza con la fecha, así un cambio no reordena la lista.
    r.sort(key=lambda x: (str(x["proyecto"].get("creado", "")), os.path.basename(x["carpeta"])), reverse=True)
    return r


def estado():
    return {"ok": True, "proyectos": proyectos(), "estilos": list(subtitulos.estilos().values()), "config": proyecto.config(),
            "vocabulario": vocabulario.leer(), "efectos": list(efectos.disponibles().values()),
            "plantillas": list(plantillas.disponibles().values())}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        r = estado()
    except OSError as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(sys.argv[1], r)
    print(json.dumps({"ok": r["ok"], "proyectos": len(r.get("proyectos", []))}))
