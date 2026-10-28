"""El proyecto de Corta: un JSON abierto y documentado al lado del video (ver README, "Formato del proyecto"). Solo biblioteca estándar.

~/Corta/<Nombre del video>/
  proyecto.json          lo que hiciste: cortes, subtítulos, zooms, textos, encuadre (el video original nunca se toca)
  original.<ext>         el video tal como lo trajiste (o un enlace a él)
  audio.wav              audio a 16 kHz para transcribir (se borra al terminar)
  exportado-<lienzo>.mp4 lo que exportaste
  musica/                copia de la música elegida (bin/musica.py); "musica": {"archivo": "musica/<nombre>", "volumen"}
  historial/             copias de proyecto.json antes de cada cambio (para deshacer)
~/Corta/.corta/config.json   ajustes de la app
~/Corta/.corta/estilos/      estilos de subtítulos descargados (ganan sobre los incluidos)

Todos los tiempos del proyecto están en segundos del VIDEO ORIGINAL. Los cortes dicen qué partes no van; el resto se conserva.
"""
import json
import os
import re
import shutil
import tempfile
import time

import efecto_formato

BASE = os.environ.get("CORTA_CARPETA") or os.path.join(os.path.expanduser("~"), "Corta")
INTERNO = os.path.join(BASE, ".corta")
RECURSOS = os.environ.get("CORTA_RECURSOS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMATO = 1
LIENZOS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}
MOTIVOS = {"silencio", "muletilla", "manual", "ia", "fuera"}


# ───────────── JSON y escritura segura ─────────────
def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def escribir_json(ruta, valor):
    """Escribe en un temporal y lo renombra: si algo se corta a la mitad, el archivo anterior queda intacto."""
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta) or ".", prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(valor, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, ruta)


def config():
    return {"ia": "claude", "idioma_ui": "", "idioma_audio": "auto", "modelo": "turbo", **leer_json(os.path.join(INTERNO, "config.json"), {})}


# ───────────── Programas (ffmpeg, ffprobe, transcriptor) ─────────────
def programa(*nombres):
    """Ruta del primer programa que exista: primero los que vienen dentro de la app (CORTA_PROGRAMAS, verificados por huella al
    empaquetar), después los del sistema (desarrollo). Si no hay ninguno, el primer nombre (el error lo da quien lo llame)."""
    propios = os.environ.get("CORTA_PROGRAMAS")
    if propios:
        for n in nombres:
            r = os.path.join(propios, n)
            if os.path.isfile(r) and os.access(r, os.X_OK):
                return r
    for n in nombres:
        r = shutil.which(n)
        if r:
            return r
    return nombres[0]


#: ffmpeg y ffprobe solo abren archivos locales: nada de http, tcp, concat, subfile ni otros protocolos (aunque un nombre lo pida).
SOLO_ARCHIVOS = ["-protocol_whitelist", "file"]


def entrada(ruta):
    """Una ruta como entrada de ffmpeg: absoluta y con «file:» delante, así nunca se lee como opción ni como otro protocolo."""
    return "file:" + os.path.abspath(ruta)


def carpeta_valida(carpeta):
    """La carpeta de un proyecto: una carpeta directa de ~/Corta (sin enlaces que lleven a otro lado) con su proyecto.json.
    Lo que llega de la interfaz pasa por aquí antes de leer o escribir nada. Devuelve la ruta real o lanza ValueError."""
    if not isinstance(carpeta, str) or not carpeta or "\x00" in carpeta:
        raise ValueError("No encontré ese proyecto.")
    real, base = os.path.realpath(carpeta), os.path.realpath(BASE)
    nombre = os.path.basename(real)
    if os.path.dirname(real) != base or nombre.startswith(".") or not os.path.isfile(os.path.join(real, "proyecto.json")):
        raise ValueError("No encontré ese proyecto.")
    return real


# ───────────── Proyecto ─────────────
def nuevo(titulo, fuente):
    """fuente = {"archivo", "duracion", "ancho", "alto"}. Vertical por defecto (Shorts, Reels y TikTok)."""
    return {"formato": FORMATO, "titulo": titulo, "fuente": fuente, "lienzo": "9:16", "relleno": "recorte",
            "encuadre": {"x": 0.5, "y": 0.5}, "palabras": [], "cortes": [],
            "subtitulos": {"activos": True, "estilo": "pop", "palabras_por_linea": 3, "posicion": 0.7},
            "zooms": [], "textos": [], "musica": None, "creado": time.strftime("%Y-%m-%dT%H:%M:%S")}


# El video del proyecto es un archivo dentro de su carpeta («original.mp4»): sin «/» ni «\\», sin empezar con «-» (ffmpeg lo
# tomaría como opción) y sin caracteres de control. Así un proyecto.json cambiado a mano no hace leer ni enlazar archivos de afuera.
#: Id de un cambio de la IA («origen» de lo que agregó y «id» en cambios_ia).
ORIGEN = re.compile(r"ia-[0-9a-z]{1,24}")
ARCHIVO_FUENTE = re.compile(r"[^\\/\x00-\x1f\-][^\\/\x00-\x1f]{0,199}")


def validar(p):
    """Lista de problemas (vacía = válido). Todo cambio que propone la IA pasa por aquí antes de guardarse."""
    if not isinstance(p, dict):
        return ["El proyecto no es un objeto."]
    e = []
    dur = (p.get("fuente") or {}).get("duracion")
    if p.get("formato") != FORMATO:
        e.append(f"formato debe ser {FORMATO}.")
    if not isinstance(dur, (int, float)) or dur <= 0:
        e.append("fuente.duracion debe ser un número mayor que 0.")
        dur = 1e9
    archivo = (p.get("fuente") or {}).get("archivo")
    if not (isinstance(archivo, str) and ARCHIVO_FUENTE.fullmatch(archivo) and archivo not in (".", "..")):
        e.append("fuente.archivo debe ser el nombre del video dentro de la carpeta del proyecto (sin carpetas).")
    if p.get("lienzo") not in LIENZOS:
        e.append("lienzo debe ser " + ", ".join(LIENZOS) + ".")
    if p.get("relleno") not in ("recorte", "desenfoque"):
        e.append("relleno debe ser «recorte» o «desenfoque».")
    for k in ("x", "y"):
        v = (p.get("encuadre") or {}).get(k)
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            e.append(f"encuadre.{k} debe estar entre 0 y 1.")

    def tramo(t, nombre):
        if not isinstance(t, dict) or not all(isinstance(t.get(k), (int, float)) for k in ("i", "f")):
            e.append(f"{nombre}: cada tramo necesita i y f (segundos).")
            return False
        if not 0 <= t["i"] < t["f"] <= dur + 0.05:
            e.append(f"{nombre}: el tramo {t['i']}–{t['f']} está fuera del video o al revés.")
            return False
        return True

    for c in p.get("cortes", []):
        if tramo(c, "cortes") and c.get("motivo") not in MOTIVOS:
            e.append("cortes: motivo debe ser " + ", ".join(sorted(MOTIVOS)) + ".")
    for z in p.get("zooms", []):
        if tramo(z, "zooms") and not (isinstance(z.get("escala"), (int, float)) and 1 <= z["escala"] <= 2):
            e.append("zooms: escala debe estar entre 1 y 2.")
    for t in p.get("textos", []):
        if tramo(t, "textos") and not (isinstance(t.get("texto"), str) and 0 < len(t["texto"]) <= 80):
            e.append("textos: texto de 1 a 80 caracteres.")
    for w in p.get("palabras", []):
        if not (isinstance(w, dict) and isinstance(w.get("t"), str) and 0 < len(w["t"]) <= 80 and tramo(w, "palabras")):
            e.append("palabras: cada una necesita t (1 a 80 caracteres), i y f.")
            break
        if w.get("linea") not in (None, "fin", "sigue"):
            e.append("palabras: linea debe ser «fin» o «sigue».")
            break
    s = p.get("subtitulos") or {}
    if not re.fullmatch(r"[a-z0-9-]{2,40}", str(s.get("estilo", ""))):
        e.append("subtitulos.estilo debe ser el id de un estilo.")
    if not (isinstance(s.get("palabras_por_linea"), int) and 1 <= s["palabras_por_linea"] <= 8):
        e.append("subtitulos.palabras_por_linea debe estar entre 1 y 8.")
    if not (isinstance(s.get("posicion"), (int, float)) and 0.1 <= s["posicion"] <= 0.95):
        e.append("subtitulos.posicion debe estar entre 0.1 y 0.95.")
    efectos = p.get("efectos", [])
    if not isinstance(efectos, list) or len(efectos) > 40:
        e.append("efectos: lista de hasta 40.")
        efectos = []
    for x in efectos:
        if not (isinstance(x, dict) and isinstance(x.get("efecto"), str) and efecto_formato.ID.fullmatch(x["efecto"])):
            e.append("efectos: cada uno necesita el id del efecto.")
            continue
        if extra := set(x) - {"efecto", "pasos", "i", "f", "origen"}:
            e.append("efectos: campos desconocidos: " + ", ".join(sorted(map(str, extra))) + ".")
        if ("i" in x or "f" in x) and not tramo(x, "efectos"):
            continue
        e += [f"efectos: {m}" for m in efecto_formato.validar_pasos(x.get("pasos"))]
    div = p.get("divisiones", [])
    if not (isinstance(div, list) and len(div) <= 500 and all(isinstance(t, (int, float)) and not isinstance(t, bool) and 0 < t < dur for t in div)):
        e.append("divisiones: lista de segundos dentro del video.")
    for lista in ("cortes", "zooms", "textos", "efectos"):
        if any(isinstance(o, dict) and "origen" in o and not (isinstance(o["origen"], str) and ORIGEN.fullmatch(o["origen"]))
               for o in p.get(lista, [])):
            e.append(f"{lista}: origen debe ser el id de un cambio de la IA.")
    c = p.get("cambios_ia")
    if c is not None and not (isinstance(c, list) and len(c) <= 50 and all(
            isinstance(x, dict) and isinstance(x.get("id"), str) and ORIGEN.fullmatch(x["id"]) and x.get("estado") in ("aplicado", "quitado")
            for x in c)):
        e.append("cambios_ia: lista de {id, estado: aplicado|quitado, …}.")
    m = p.get("musica")
    if m is not None and not (isinstance(m, dict) and isinstance(m.get("archivo"), str) and m["archivo"].strip()
                              and "\x00" not in m["archivo"] and isinstance(m.get("volumen"), (int, float))
                              and not isinstance(m["volumen"], bool) and 0 <= m["volumen"] <= 1):
        e.append("musica debe ser null o {archivo, volumen entre 0 y 1}.")
    return e


def unir(tramos, margen=0.0):
    """Ordena y une tramos que se tocan o se traslapan (con un margen en segundos)."""
    r = []
    for t in sorted(tramos, key=lambda x: x["i"]):
        if r and t["i"] <= r[-1]["f"] + margen:
            r[-1]["f"] = max(r[-1]["f"], t["f"])
        else:
            r.append({"i": t["i"], "f": t["f"]})
    return r


def conservados(p, minimo=0.04):
    """Los tramos del original que quedan en el video, en orden (lo que no está cortado)."""
    dur = p["fuente"]["duracion"]
    r, t = [], 0.0
    for c in unir(p.get("cortes", [])):
        if c["i"] - t >= minimo:
            r.append({"i": round(t, 3), "f": round(min(c["i"], dur), 3)})
        t = max(t, c["f"])
    if dur - t >= minimo:
        r.append({"i": round(t, 3), "f": round(dur, 3)})
    return r


def duracion_final(p):
    return round(sum(t["f"] - t["i"] for t in conservados(p)), 3)


def a_salida(p, t, tramos=None):
    """Segundo del original → segundo del video exportado (None si ese momento quedó cortado)."""
    acumulado = 0.0
    for tr in tramos or conservados(p):
        if tr["i"] <= t <= tr["f"]:
            return round(acumulado + t - tr["i"], 3)
        acumulado += tr["f"] - tr["i"]
    return None


def palabra_cortada(p, w, cortes=None):
    """Una palabra está cortada si más de la mitad de su duración cae dentro de un corte."""
    medio = (w["i"] + w["f"]) / 2
    return any(c["i"] <= medio <= c["f"] for c in (cortes if cortes is not None else unir(p.get("cortes", []))))


def cortar_palabras(p, desde, hasta, motivo="manual"):
    """Corta las palabras desde..hasta (índices, incluidos) y el silencio que hay entre ellas."""
    w = p["palabras"]
    desde, hasta = max(0, desde), min(len(w) - 1, hasta)
    if desde > hasta:
        return
    i = w[desde]["i"] if desde == 0 else (w[desde - 1]["f"] + w[desde]["i"]) / 2
    f = w[hasta]["f"] if hasta == len(w) - 1 else (w[hasta]["f"] + w[hasta + 1]["i"]) / 2
    p["cortes"].append({"i": round(i, 3), "f": round(f, 3), "motivo": motivo})


def restaurar(p, i, f):
    """Quita los cortes que caen dentro de i..f (lo vuelve a poner en el video)."""
    nuevos = []
    for c in p.get("cortes", []):
        if c["f"] <= i or c["i"] >= f:
            nuevos.append(c)
            continue
        if c["i"] < i:
            nuevos.append({**c, "f": round(i, 3)})
        if c["f"] > f:
            nuevos.append({**c, "i": round(f, 3)})
    p["cortes"] = nuevos


# ───────────── En disco ─────────────
def ruta(carpeta):
    return os.path.join(carpeta, "proyecto.json")


def cargar(carpeta):
    p = leer_json(ruta(carpeta), None)
    if p is None:
        raise ValueError("No encontré proyecto.json en esa carpeta.")
    return p


def guardar(carpeta, p, respaldo=True):
    """Guarda (validando) y deja una copia del anterior en historial/ para poder deshacer."""
    problemas = validar(p)
    if problemas:
        raise ValueError(" ".join(problemas[:3]))
    actual = ruta(carpeta)
    if respaldo and os.path.exists(actual):
        hist = os.path.join(carpeta, "historial")
        os.makedirs(hist, exist_ok=True)
        shutil.copy2(actual, os.path.join(hist, time.strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1000000:06d}.json"))
        viejos = sorted(os.listdir(hist))[:-50]  # se guardan los últimos 50
        for v in viejos:
            os.remove(os.path.join(hist, v))
    escribir_json(actual, p)


def deshacer(carpeta):
    hist = os.path.join(carpeta, "historial")
    copias = sorted(os.listdir(hist)) if os.path.isdir(hist) else []
    if not copias:
        return False
    ultima = os.path.join(hist, copias[-1])
    os.replace(ultima, ruta(carpeta))
    return True
