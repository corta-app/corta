"""Corregir palabras de la transcripción y el vocabulario de la persona. Solo biblioteca estándar.

  vocabulario.py entrada <entrada.json> <salida.json>   {"accion": "agregar", "de", "a"} | {"accion": "quitar", "de"}
                                                       | {"accion": "palabra", "palabra"} | {"accion": "quitar_palabra", "palabra"}
                                                       → {"ok", "vocabulario"}

El vocabulario vive en ~/Corta/vocabulario.json (formato en el README, «Vocabulario»):
  {"formato": 1, "reemplazos": [{"de": "calumi", "a": "Kalumi"}], "palabras": ["Kalumi"]}
Al transcribir un video nuevo (bin/importar.py) cada reemplazo se aplica por palabra completa, sin mirar tildes ni mayúsculas, y las
palabras (más las formas correctas de los reemplazos) se le pasan al transcriptor como vocabulario para que reconozca mejor nombres.

La misma lógica de corregir existe en ui/app.js (`normalizar`, `editarPalabras`, `reemplazarTodo`, `lineas`); casos en
pruebas/casos.json (sección «editar»). Corregir nunca cambia los tiempos: una palabra mantiene su inicio y su fin, y si se escriben
varias, se reparten el tiempo de la original según su largo.
"""
import json
import math
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402

FORMATO = 1
MAXIMO = 500       # reemplazos y palabras (cada lista)
LARGO = 60         # caracteres por texto
PROMPT_MAX = 600   # caracteres del vocabulario que recibe el transcriptor


def ruta():
    return os.path.join(proyecto.BASE, "vocabulario.json")


# ───────────── Lógica compartida con ui/app.js ─────────────
def _alnum(c):
    return c.isalnum()


def normalizar(t):
    """Para comparar: sin tildes, sin mayúsculas y sin nada que no sea letra o número («¿Calúmi?» → «calumi»)."""
    t = unicodedata.normalize("NFD", str(t))
    return "".join(c for c in t if not unicodedata.category(c).startswith("M") and _alnum(c)).lower()


def partes(t):
    """«¿Calumi?» → («¿», «Calumi», «?»): la puntuación de los bordes se conserva al corregir."""
    a, b = 0, len(t)
    while a < b and not _alnum(t[a]):
        a += 1
    while b > a and not _alnum(t[b - 1]):
        b -= 1
    return t[:a], t[a:b], t[b:]


def con_mayusculas(original, correcta):
    """Si la forma correcta trae mayúsculas, se respeta tal cual («Kalumi»). Si es toda minúscula, sigue a la original: «Hola» al
    empezar una frase o «HOLA» en mayúsculas."""
    if any(c.isupper() for c in correcta) or not original:
        return correcta
    if len(original) > 1 and original.isupper():
        return correcta.upper()
    if original[0].isupper():
        return correcta[:1].upper() + correcta[1:]
    return correcta


def _r3(n):
    """Redondeo a milésimas igual que ui/app.js (la mitad hacia arriba)."""
    return math.floor(n * 1000 + 0.5) / 1000


def repartir(i, f, textos):
    """Reparte el tiempo i..f entre varias palabras según su largo (letras y números). La última termina justo en f."""
    pesos = [max(1, sum(1 for c in t if _alnum(c))) for t in textos]
    total, acumulado, r = sum(pesos), 0, []
    inicio = i
    for k, (t, peso) in enumerate(zip(textos, pesos)):
        acumulado += peso
        fin = f if k == len(textos) - 1 else _r3(i + (f - i) * acumulado / total)
        r.append({"t": t, "i": _r3(inicio), "f": _r3(fin)})
        inicio = fin
    return r


def editar_palabras(palabras, desde, hasta, texto):
    """Cambia las palabras desde..hasta (incluidas) por `texto`, en el mismo tiempo. Vacío = se quitan del subtítulo (el video no
    se corta). Lo extra de la última palabra (p. ej. `linea`) pasa a la última nueva. Devuelve la lista nueva."""
    w = palabras
    desde, hasta = max(0, desde), min(len(w) - 1, hasta)
    if desde > hasta:
        return list(w)
    nuevas = str(texto).split()
    if not nuevas:
        return w[:desde] + w[hasta + 1:]
    r = repartir(w[desde]["i"], w[hasta]["f"], nuevas)
    extra = {k: v for k, v in w[hasta].items() if k not in ("t", "i", "f")}
    r[-1].update(extra)
    return w[:desde] + r + w[hasta + 1:]


def _de_partes(de):
    return [x for x in (normalizar(p) for p in str(de).split()) if x]


def reemplazar_todo(palabras, pares):
    """Aplica pares [{de, a}] por palabra completa (sin tildes ni mayúsculas al comparar; `de` puede tener varias palabras).
    Los más largos primero; lo ya reemplazado no se vuelve a mirar. Devuelve (palabras nuevas, cuántas cambiaron de verdad)."""
    reglas = []
    for par in pares:
        claves = _de_partes(par.get("de", ""))
        a = str(par.get("a", "")).split()
        if claves and a:
            reglas.append((claves, a))
    reglas.sort(key=lambda x: -len(x[0]))
    norm = [normalizar(w["t"]) for w in palabras]
    r, k, n = [], 0, 0
    while k < len(palabras):
        hecho = False
        for claves, a in reglas:
            m = len(claves)
            if norm[k:k + m] == claves:
                grupo = palabras[k:k + m]
                antes, primera, _ = partes(grupo[0]["t"])
                _, ultima, despues = partes(grupo[-1]["t"])
                textos = [con_mayusculas(primera, x) for x in a]
                textos[0] = antes + textos[0]
                textos[-1] = textos[-1] + despues
                nuevas = repartir(grupo[0]["i"], grupo[-1]["f"], textos)
                nuevas[-1].update({x: v for x, v in grupo[-1].items() if x not in ("t", "i", "f")})
                if [w["t"] for w in grupo] != textos:
                    n += 1
                    r += nuevas
                else:
                    r += grupo
                k += m
                hecho = True
                break
        if not hecho:
            r.append(palabras[k])
            k += 1
    return r, n


# ───────────── El archivo ─────────────
def _texto_valido(t):
    return isinstance(t, str) and 0 < len(t.strip()) <= LARGO and not re.search(r"[\x00-\x1f\x7f<>{}\\  ]", t) \
        and bool(normalizar(t))


def limpiar(v):
    """Solo lo válido (un archivo cambiado a mano nunca rompe la transcripción)."""
    v = v if isinstance(v, dict) else {}
    reemplazos, vistos = [], set()
    for r in v.get("reemplazos") or []:
        if isinstance(r, dict) and _texto_valido(r.get("de")) and _texto_valido(r.get("a")):
            clave = " ".join(_de_partes(r["de"]))
            if clave not in vistos:
                vistos.add(clave)
                reemplazos.append({"de": r["de"].strip(), "a": " ".join(r["a"].split())})
    palabras, vistas = [], set()
    for p in v.get("palabras") or []:
        if _texto_valido(p) and normalizar(p) not in vistas:
            vistas.add(normalizar(p))
            palabras.append(" ".join(p.split()))
    return {"formato": FORMATO, "reemplazos": reemplazos[:MAXIMO], "palabras": palabras[:MAXIMO]}


def leer():
    return limpiar(proyecto.leer_json(ruta(), {}))


def pares(v):
    """Lo que se aplica al transcribir: los reemplazos y cada palabra propia consigo misma (corrige mayúsculas y tildes)."""
    return v["reemplazos"] + [{"de": p, "a": p} for p in v["palabras"]]


def prompt(v):
    """Vocabulario para el transcriptor (whisper `initial_prompt`): nombres y palabras propias, separadas por comas."""
    vistos, lista = set(), []
    for t in [r["a"] for r in v["reemplazos"]] + v["palabras"]:
        if normalizar(t) not in vistos:
            vistos.add(normalizar(t))
            lista.append(t)
    texto = ""
    for t in lista:
        if len(texto) + len(t) + 2 > PROMPT_MAX:
            break
        texto = f"{texto}, {t}" if texto else t
    return texto


def cambiar(d):
    if not isinstance(d, dict):
        raise ValueError("No pude leer el cambio.")
    v = leer()
    accion = d.get("accion")
    if accion == "agregar":
        if not (_texto_valido(d.get("de")) and _texto_valido(d.get("a"))):
            raise ValueError("Esa palabra no se puede recordar.")
        clave = " ".join(_de_partes(d["de"]))
        v["reemplazos"] = [r for r in v["reemplazos"] if " ".join(_de_partes(r["de"])) != clave]
        v["reemplazos"].insert(0, {"de": d["de"].strip(), "a": " ".join(d["a"].split())})
    elif accion == "quitar":
        clave = " ".join(_de_partes(d.get("de", "")))
        v["reemplazos"] = [r for r in v["reemplazos"] if " ".join(_de_partes(r["de"])) != clave]
    elif accion == "palabra":
        if not _texto_valido(d.get("palabra")):
            raise ValueError("Esa palabra no se puede recordar.")
        v["palabras"] = [p for p in v["palabras"] if normalizar(p) != normalizar(d["palabra"])]
        v["palabras"].insert(0, " ".join(d["palabra"].split()))
    elif accion == "quitar_palabra":
        v["palabras"] = [p for p in v["palabras"] if normalizar(p) != normalizar(d.get("palabra", ""))]
    else:
        raise ValueError("No sé hacer eso.")
    v = limpiar(v)
    proyecto.escribir_json(ruta(), v)
    return {"ok": True, "vocabulario": v}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 3 or a[0] != "entrada":
        print(__doc__)
        sys.exit(2)
    try:
        r = cambiar(proyecto.leer_json(a[1], None))
    except (OSError, ValueError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[2], r)
    print(json.dumps({"ok": r["ok"]}, ensure_ascii=False))
