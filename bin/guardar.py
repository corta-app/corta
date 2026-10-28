"""Guardar o deshacer lo que la persona cambia en la interfaz. Solo biblioteca estándar.

  guardar.py proyecto <entrada.json> <salida.json>   {"carpeta", "proyecto"}: valida y guarda (con respaldo para deshacer)
  guardar.py deshacer <entrada.json> <salida.json>   {"carpeta"}: vuelve al proyecto anterior del historial

Lo que manda la app llega en un archivo de entrada (nunca como argumento). La carpeta tiene que ser un proyecto de ~/Corta.
La interfaz no puede cambiar el video del proyecto (`fuente` y `plantilla` se mantienen como están en disco) ni apuntar la música a otro archivo:
`musica` queda null, igual que antes, o con un archivo que ya está en `musica/` del proyecto (la elige bin/musica.py).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402


def musica_permitida(carpeta, nueva, actual):
    if nueva is None:
        return True
    if not isinstance(nueva, dict) or not isinstance(nueva.get("archivo"), str):
        return False
    a = nueva["archivo"]
    if actual and a == actual.get("archivo"):
        return True
    if not a.startswith("musica/") or "\\" in a or ".." in a.split("/") or a.count("/") != 1:
        return False
    real = os.path.realpath(os.path.join(carpeta, a))
    return os.path.dirname(real) == os.path.join(carpeta, "musica") and os.path.isfile(real)


def guardar(entrada):
    d = proyecto.leer_json(entrada, None)
    if not isinstance(d, dict):
        raise ValueError("No pude leer el cambio.")
    carpeta = proyecto.carpeta_valida(d.get("carpeta"))
    p = d.get("proyecto")
    if not isinstance(p, dict):
        raise ValueError("El proyecto no es válido.")
    actual = proyecto.cargar(carpeta)
    p["fuente"] = actual["fuente"]
    # Qué clip va en cada hueco de una plantilla lo cambia solo bin/plantillas.py (que copia los clips y vuelve a armar el video).
    p.pop("plantilla", None)
    if "plantilla" in actual:
        p["plantilla"] = actual["plantilla"]
    if not musica_permitida(carpeta, p.get("musica"), actual.get("musica")):
        raise ValueError("Elige la música con «Elegir música».")
    proyecto.guardar(carpeta, p)
    return {"ok": True, "carpeta": carpeta}


def deshacer(entrada):
    d = proyecto.leer_json(entrada, None)
    carpeta = proyecto.carpeta_valida((d or {}).get("carpeta"))
    antes = proyecto.cargar(carpeta)
    hecho = proyecto.deshacer(carpeta)
    p = proyecto.cargar(carpeta)
    if hecho and "plantilla" in antes and p.get("fuente") != antes["fuente"]:
        # Un proyecto de plantilla vuelve a armarse en otro archivo (el anterior se borra): deshacer vuelve a lo que editaste,
        # pero con el video y los clips de ahora (cambiar un clip se deshace eligiendo el anterior).
        p["fuente"], p["plantilla"] = antes["fuente"], antes["plantilla"]
        proyecto.escribir_json(proyecto.ruta(carpeta), p)
    return {"ok": True, "deshecho": hecho, "carpeta": carpeta, "proyecto": p}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 3 or a[0] not in ("proyecto", "deshacer"):
        print(__doc__)
        sys.exit(2)
    try:
        r = guardar(a[1]) if a[0] == "proyecto" else deshacer(a[1])
    except (OSError, ValueError, KeyError, TypeError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[2], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False))
