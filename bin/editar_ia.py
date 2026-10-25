"""Editar diciéndole a tu IA lo que quieres, y sacar Shorts de un video largo. Solo biblioteca estándar.

  editar_ia.py pedir <carpeta> "<lo que quieres>" <salida.json>   aplica los cambios (con respaldo para deshacer)
  editar_ia.py shorts <carpeta> <salida.json>                      propone los mejores momentos (no guarda nada)
  editar_ia.py crear_short <carpeta> <desde> <hasta> "<título>" <salida.json>   crea un proyecto nuevo con ese tramo

La IA nunca toca el proyecto directo: responde una lista de operaciones en JSON, se validan una por una y solo se aplican las
válidas. Ve la transcripción con números de palabra y tiempos, nunca el video.
"""
import copy
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ia  # noqa: E402
import proyecto  # noqa: E402
import subtitulos  # noqa: E402

OPERACIONES = """- {"op": "cortar", "desde": N, "hasta": M}             saca las palabras N a M (incluidas)
- {"op": "restaurar", "desde": N, "hasta": M}          vuelve a poner las palabras N a M si estaban cortadas
- {"op": "zoom", "desde": N, "hasta": M, "escala": 1.0-1.6}   acerca la imagen mientras se dicen esas palabras
- {"op": "texto", "desde": N, "hasta": M, "texto": "..."}      texto grande arriba (máx. 40 caracteres) mientras se dicen
- {"op": "estilo", "id": "<id>"}                        cambia el estilo de los subtítulos
- {"op": "subtitulos", "activos": true|false, "palabras_por_linea": 1-6}
- {"op": "lienzo", "valor": "9:16"|"1:1"|"4:5"|"16:9"}
- {"op": "musica", "volumen": 0-0.5}                    (solo si ya hay música elegida)"""


def transcripcion_numerada(p):
    cortes = proyecto.unir(p["cortes"])
    lineas, actual = [], []
    for k, w in enumerate(p["palabras"]):
        marca = "~" if proyecto.palabra_cortada(p, w, cortes) else ""
        actual.append(f"{k}:{marca}{w['t']}")
        if re.search(r"[.!?…]$", w["t"]) or len(actual) >= 14:
            lineas.append(f"[{p['palabras'][k - len(actual) + 1]['i']:.1f}s] " + " ".join(actual))
            actual = []
    if actual:
        lineas.append(f"[{p['palabras'][len(p['palabras']) - len(actual)]['i']:.1f}s] " + " ".join(actual))
    return "\n".join(lineas)


def prompt_pedir(p, pedido, estilos):
    return f"""Eres el asistente de un editor de video vertical (Shorts, Reels, TikTok). La persona te pide un cambio y tú respondes
SOLO con un JSON: {{"operaciones": [...], "resumen": "<una frase en el idioma del pedido contando qué hiciste>"}}.

Operaciones posibles (N y M son números de palabra de la transcripción de abajo):
{OPERACIONES}

Estilos de subtítulos disponibles: {", ".join(f"{s['id']} ({s['nombre']})" for s in estilos.values())}.
Estado actual: lienzo {p['lienzo']}, subtítulos {"activos" if p['subtitulos']['activos'] else "apagados"} con estilo {p['subtitulos']['estilo']},
{len(p['zooms'])} zooms, {len(p['textos'])} textos, música {"sí" if p.get('musica') else "no"}.

Reglas: haz solo lo que se pide. No cortes contenido importante si no te lo piden. Si el pedido no se puede hacer con estas
operaciones, responde {{"operaciones": [], "resumen": "<explica qué no se puede y qué sí>"}}.

Transcripción (cada palabra es número:palabra; las que empiezan con ~ ya están cortadas):
{transcripcion_numerada(p)}

Pedido: {pedido}"""


def leer_json_ia(texto):
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def aplicar(p, operaciones, estilos):
    """Aplica las operaciones válidas sobre una copia. Devuelve (proyecto_nuevo, aplicadas, ignoradas)."""
    q = copy.deepcopy(p)
    w = q["palabras"]
    n = len(w)
    hechas, malas = [], []

    def rango(o):
        d, h = o.get("desde"), o.get("hasta")
        if isinstance(d, int) and isinstance(h, int) and 0 <= d <= h < n:
            return d, h
        return None

    for o in operaciones if isinstance(operaciones, list) else []:
        tipo = o.get("op") if isinstance(o, dict) else None
        r = rango(o) if tipo in ("cortar", "restaurar", "zoom", "texto") else None
        if tipo == "cortar" and r:
            proyecto.cortar_palabras(q, r[0], r[1], "ia")
        elif tipo == "restaurar" and r:
            proyecto.restaurar(q, w[r[0]]["i"] - 0.01, w[r[1]]["f"] + 0.01)
        elif tipo == "zoom" and r and isinstance(o.get("escala"), (int, float)) and 1 <= o["escala"] <= 1.6:
            q["zooms"].append({"i": w[r[0]]["i"], "f": w[r[1]]["f"], "escala": round(float(o["escala"]), 2)})
        elif tipo == "texto" and r and isinstance(o.get("texto"), str) and 0 < len(o["texto"].strip()) <= 40:
            q["textos"].append({"i": w[r[0]]["i"], "f": w[r[1]]["f"], "texto": o["texto"].strip(), "y": 0.18})
        elif tipo == "estilo" and o.get("id") in estilos:
            q["subtitulos"]["estilo"] = o["id"]
        elif tipo == "subtitulos" and (isinstance(o.get("activos"), bool) or isinstance(o.get("palabras_por_linea"), int)):
            if isinstance(o.get("activos"), bool):
                q["subtitulos"]["activos"] = o["activos"]
            if isinstance(o.get("palabras_por_linea"), int) and 1 <= o["palabras_por_linea"] <= 6:
                q["subtitulos"]["palabras_por_linea"] = o["palabras_por_linea"]
        elif tipo == "lienzo" and o.get("valor") in proyecto.LIENZOS:
            q["lienzo"] = o["valor"]
        elif tipo == "musica" and q.get("musica") and isinstance(o.get("volumen"), (int, float)) and 0 <= o["volumen"] <= 0.5:
            q["musica"]["volumen"] = round(float(o["volumen"]), 2)
        else:
            malas.append(o)
            continue
        hechas.append(o)
    if proyecto.validar(q):
        return p, [], list(operaciones)
    return q, hechas, malas


def pedir(carpeta, pedido):
    p = proyecto.cargar(carpeta)
    if not p["palabras"]:
        return {"ok": False, "error": "Primero hay que transcribir el video: así tu IA sabe qué se dice y cuándo."}
    estilos = subtitulos.estilos()
    texto, error = ia.preguntar(prompt_pedir(p, pedido.strip()[:500], estilos))
    if error:
        return {"ok": False, "error": error}
    datos = leer_json_ia(texto)
    if not isinstance(datos, dict):
        return {"ok": False, "error": f"{ia.nombre()} no respondió con cambios que pueda aplicar. Prueba diciéndolo de otra forma."}
    nuevo, hechas, malas = aplicar(p, datos.get("operaciones", []), estilos)
    if hechas:
        proyecto.guardar(carpeta, nuevo)
    return {"ok": True, "resumen": str(datos.get("resumen", ""))[:300], "aplicadas": len(hechas), "ignoradas": len(malas),
            "proyecto": nuevo}


# ───────────── Shorts desde un video largo ─────────────
def prompt_shorts(p):
    return f"""Eres editor de contenido para redes. Abajo está la transcripción de un video de {p['fuente']['duracion'] / 60:.1f} minutos,
con números de palabra y tiempos. Elige los 3 a 6 MEJORES momentos para Shorts/Reels/TikTok verticales.

Cada momento: entre 20 y 60 segundos, se entiende sin ver el resto, empieza con algo que enganche en los primeros 3 segundos y
termina en una idea cerrada (no a mitad de frase). Ordénalos del mejor al menos bueno. No inventes nada que no se diga.

Responde SOLO con JSON: {{"shorts": [{{"desde": N, "hasta": M, "titulo": "<máx. 60 caracteres, en el idioma del video>",
"gancho": "<la primera frase, tal cual>", "por_que": "<por qué funciona, una frase>"}}]}}
(N y M son números de palabra: la primera y la última del momento).

Transcripción:
{transcripcion_numerada(p)}"""


def validar_shorts(p, lista):
    w, r = p["palabras"], []
    for s in lista if isinstance(lista, list) else []:
        if not isinstance(s, dict):
            continue
        d, h = s.get("desde"), s.get("hasta")
        if not (isinstance(d, int) and isinstance(h, int) and 0 <= d < h < len(w)):
            continue
        dur = w[h]["f"] - w[d]["i"]
        if not 10 <= dur <= 90:
            continue
        titulo = str(s.get("titulo", "")).strip()[:60] or " ".join(x["t"] for x in w[d:d + 6])
        r.append({"desde": d, "hasta": h, "i": w[d]["i"], "f": w[h]["f"], "duracion": round(dur, 1), "titulo": titulo,
                  "gancho": str(s.get("gancho", ""))[:200], "por_que": str(s.get("por_que", ""))[:200]})
    return r[:6]


def shorts(carpeta):
    p = proyecto.cargar(carpeta)
    if not p["palabras"]:
        return {"ok": False, "error": "Primero hay que transcribir el video."}
    texto, error = ia.preguntar(prompt_shorts(p))
    if error:
        return {"ok": False, "error": error}
    datos = leer_json_ia(texto) or {}
    lista = validar_shorts(p, datos.get("shorts"))
    if not lista:
        return {"ok": False, "error": f"{ia.nombre()} no propuso momentos que se puedan usar. Inténtalo de nuevo."}
    return {"ok": True, "shorts": lista}


def crear_short(carpeta, desde, hasta, titulo):
    """Proyecto nuevo con el mismo video y todo lo que está fuera del tramo cortado (motivo «fuera»)."""
    p = proyecto.cargar(carpeta)
    dur = p["fuente"]["duracion"]
    desde, hasta = max(0.0, desde), min(dur, hasta)
    if hasta - desde < 3:
        return {"ok": False, "error": "El tramo es muy corto."}
    q = copy.deepcopy(p)
    q["titulo"] = titulo.strip()[:80] or p["titulo"] + " (short)"
    q["cortes"] = [c for c in q["cortes"] if c["f"] > desde and c["i"] < hasta]
    if desde > 0.05:
        q["cortes"].append({"i": 0.0, "f": round(desde, 3), "motivo": "fuera"})
    if hasta < dur - 0.05:
        q["cortes"].append({"i": round(hasta, 3), "f": dur, "motivo": "fuera"})
    q["zooms"] = [z for z in q["zooms"] if z["f"] > desde and z["i"] < hasta]
    q["textos"] = [t for t in q["textos"] if t["f"] > desde and t["i"] < hasta]
    q["lienzo"] = "9:16"
    limpio = re.sub(r"[\\/:*?<>|]+", " ", q["titulo"])[:40]
    destino = os.path.join(os.path.dirname(carpeta), f"{os.path.basename(carpeta)} — {limpio}")
    n = 2
    base = destino
    while os.path.exists(destino):
        destino, n = f"{base} ({n})", n + 1
    os.makedirs(destino)
    original = os.path.join(carpeta, p["fuente"]["archivo"])
    try:
        os.link(original, os.path.join(destino, p["fuente"]["archivo"]))  # sin duplicar el video (mismo disco)
    except OSError:
        shutil.copy2(original, os.path.join(destino, p["fuente"]["archivo"]))
    proyecto.guardar(destino, q, respaldo=False)
    return {"ok": True, "carpeta": destino, "proyecto": q}


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) == 4 and a[0] == "pedir":
            r = pedir(a[1], a[2])
        elif len(a) == 3 and a[0] == "shorts":
            r = shorts(a[1])
        elif len(a) == 6 and a[0] == "crear_short":
            r = crear_short(a[1], float(a[2]), float(a[3]), a[4])
        else:
            print(__doc__)
            sys.exit(2)
    except (OSError, ValueError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[-1], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False)[:500])
