"""Editar diciéndole a tu IA lo que quieres, y sacar Shorts de un video largo. Solo biblioteca estándar.

  editar_ia.py pedir <carpeta> "<lo que quieres>" <salida.json>   aplica los cambios (con respaldo para deshacer)
  editar_ia.py shorts <carpeta> <salida.json>                      propone los mejores momentos (no guarda nada)
  editar_ia.py crear_short <carpeta> <desde> <hasta> "<título>" <salida.json>   crea un proyecto nuevo con ese tramo
  editar_ia.py entrada <entrada.json> <salida.json>   lo mismo, con lo que manda la app en un archivo (nunca texto de la persona
                                                      como argumento): {"accion": "pedir"|"shorts"|"crear_short", "carpeta",
                                                      "texto"?, "desde"?, "hasta"?, "titulo"?}; la carpeta tiene que ser de ~/Corta

La IA nunca toca el proyecto directo: responde una lista de operaciones en JSON, se validan una por una y solo se aplican las
válidas. Ve la transcripción con números de palabra y tiempos, nunca el video.
"""
import copy
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import efectos  # noqa: E402
import ia  # noqa: E402
import proyecto  # noqa: E402
import subtitulos  # noqa: E402
import vocabulario  # noqa: E402

#: Lo que cambió la IA queda anotado en el proyecto («cambios_ia», los últimos MAX_CAMBIOS) para poder quitar justo ese cambio
#: después, aunque la persona haya seguido editando (ui/app.js, `quitarCambioIA`). Formato en el README.
MAX_CAMBIOS = 20
AJUSTES = ("lienzo", "subtitulos.estilo", "subtitulos.activos", "subtitulos.palabras_por_linea", "musica.volumen")


def leer_campo(p, campo):
    v = p
    for k in campo.split("."):
        v = v.get(k) if isinstance(v, dict) else None
    return v


def nuevo_id():
    """ia-<base 36 del tiempo en ms>: corto, único en el proyecto y sin nada de la persona."""
    n, r = time.time_ns() // 1_000_000, ""
    while n:
        n, x = divmod(n, 36)
        r = "0123456789abcdefghijklmnopqrstuvwxyz"[x] + r
    return "ia-" + r

OPERACIONES = """- {"op": "cortar", "desde": N, "hasta": M}             saca las palabras N a M (incluidas)
- {"op": "restaurar", "desde": N, "hasta": M}          vuelve a poner las palabras N a M si estaban cortadas
- {"op": "zoom", "desde": N, "hasta": M, "escala": 1.0-1.6}   acerca la imagen mientras se dicen esas palabras
- {"op": "texto", "desde": N, "hasta": M, "texto": "..."}      título o dato clave arriba (máx. 40 caracteres) mientras se dicen;
                                                       nunca repitas lo que se dice: eso ya lo muestran los subtítulos
- {"op": "corregir", "desde": N, "hasta": M, "texto": "..."}   corrige cómo quedaron escritas esas palabras (nombres, marcas);
                                                       mantiene los tiempos, solo cambia el texto del subtítulo
- {"op": "estilo", "id": "<id>"}                        cambia el estilo de los subtítulos
- {"op": "subtitulos", "activos": true|false, "palabras_por_linea": 1-6}
- {"op": "lienzo", "valor": "9:16"|"1:1"|"4:5"|"16:9"}
- {"op": "musica", "volumen": 0-0.5}                    (solo si ya hay música elegida)
- {"op": "efecto", "id": "<id>", "desde": N, "hasta": M}  un efecto o filtro mientras se dicen esas palabras
                                                       (sin desde/hasta: a todo el video)
- {"op": "velocidad", "desde": N, "hasta": M, "v": 0.25-3, "rampa": true|false}   cámara lenta (v < 1) o rápida (v > 1)
                                                       mientras se dicen esas palabras; "rampa": true pasa suave de 1× a v
                                                       y vuelve (v de 0.25 a 0.75: «cámara lenta en el momento clave").
                                                       Bajo 0.5× la voz se silencia sola. No la uses donde ya hay otra velocidad."""


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


def velocidades_txt(p):
    """Las velocidades que ya hay, para que la IA no las pise: «, velocidad: 0.5× de 3.2 s a 5.1 s»."""
    vels = proyecto.velocidades(p)
    if not vels:
        return ""
    return ", velocidad: " + "; ".join(f"{'rampa a ' if e.get('rampa') else ''}{e['v']:g}× de {e['i']:.1f} s a {e['f']:.1f} s" for e in vels[:10])


def prompt_pedir(p, pedido, estilos):
    return f"""Eres el asistente de un editor de video vertical (Shorts, Reels, TikTok). La persona te pide un cambio y tú respondes
SOLO con un JSON: {{"operaciones": [...], "resumen": "<una frase en el idioma del pedido contando qué hiciste>"}}.

Operaciones posibles (N y M son números de palabra de la transcripción de abajo):
{OPERACIONES}

Estilos de subtítulos disponibles: {", ".join(f"{s['id']} ({s['nombre']})" for s in estilos.values())}.
Efectos disponibles: {", ".join(f"{e['id']} ({e['nombre']['es']}, {e['categoria']})" for e in efectos.disponibles().values())}.
Estado actual: lienzo {p['lienzo']}, subtítulos {"activos" if p['subtitulos']['activos'] else "apagados"} con estilo {p['subtitulos']['estilo']},
{len(p['zooms'])} zooms, {len(p['textos'])} textos, música {"sí" if p.get('musica') else "no"}{velocidades_txt(p)}.

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


def aplicar(p, operaciones, estilos, origen=None):
    """Aplica las operaciones válidas sobre una copia. Devuelve (proyecto_nuevo, aplicadas, ignoradas). Con `origen` (el id del
    cambio), lo que se agrega lleva `"origen": <id>` y en `cambios_ia` queda qué agregó y qué cambió, para poder quitarlo."""
    q = copy.deepcopy(p)
    w = q["palabras"]
    n = len(w)
    hechas, malas, correcciones = [], [], []

    def marca(o):
        if origen:
            o["origen"] = origen
        return o

    def rango(o):
        d, h = o.get("desde"), o.get("hasta")
        if isinstance(d, int) and isinstance(h, int) and 0 <= d <= h < n:
            return d, h
        return None

    for o in operaciones if isinstance(operaciones, list) else []:
        tipo = o.get("op") if isinstance(o, dict) else None
        r = rango(o) if tipo in ("cortar", "restaurar", "zoom", "texto", "corregir", "efecto", "velocidad") else None
        if tipo == "cortar" and r:
            proyecto.cortar_palabras(q, r[0], r[1], "ia")
            marca(q["cortes"][-1])
        elif tipo == "restaurar" and r:
            proyecto.restaurar(q, w[r[0]]["i"] - 0.01, w[r[1]]["f"] + 0.01)
        elif tipo == "zoom" and r and isinstance(o.get("escala"), (int, float)) and 1 <= o["escala"] <= 1.6:
            q["zooms"].append(marca({"i": w[r[0]]["i"], "f": w[r[1]]["f"], "escala": round(float(o["escala"]), 2)}))
        elif tipo == "texto" and r and isinstance(o.get("texto"), str) and 0 < len(o["texto"].strip()) <= 40:
            q["textos"].append(marca({"i": w[r[0]]["i"], "f": w[r[1]]["f"], "texto": o["texto"].strip(), "y": 0.18}))
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
        elif tipo == "efecto" and isinstance(o.get("id"), str) and o["id"] in (lib := efectos.disponibles()) \
                and (r or ("desde" not in o and "hasta" not in o)):
            ap = {"efecto": o["id"], "pasos": copy.deepcopy(lib[o["id"]]["pasos"])}
            if r:
                ap.update(i=w[r[0]]["i"], f=w[r[1]]["f"])
            q.setdefault("efectos", []).append(marca(ap))
        elif tipo == "velocidad" and r and (vel := velocidad_valida(q, w[r[0]]["i"], w[r[1]]["f"], o)):
            # Solo donde no hay otra velocidad: así «Quitar» deja todo como estaba (nada de lo de la persona se recorta).
            q["velocidades"] = proyecto.poner_velocidad(q.get("velocidades", []), w[r[0]]["i"], w[r[1]]["f"], marca(vel))
        elif tipo == "corregir" and r and isinstance(o.get("texto"), str) and 0 < len(o["texto"].strip()) <= 80 \
                and not any(a <= r[1] and r[0] <= b for a, b, _ in correcciones):
            correcciones.append((r[0], r[1], o["texto"].strip()))  # al final, de atrás para adelante (los números no se corren)
        else:
            malas.append(o)
            continue
        hechas.append(o)
    cambios_palabras = []
    for a, b, texto in sorted(correcciones, reverse=True):
        antes = q["palabras"][a:b + 1]
        q["palabras"] = vocabulario.editar_palabras(q["palabras"], a, b, texto)
        cambios_palabras.insert(0, {"antes": antes, "despues": q["palabras"][a:a + len(texto.split())]})
    if origen and hechas:
        agregados = {}
        for lista in ("zooms", "textos", "cortes", "efectos", "velocidades"):
            suyos = [o for o in q.get(lista, []) if o.get("origen") == origen]
            if suyos:
                agregados[lista] = copy.deepcopy(suyos)
        cambio = {"id": origen, "estado": "aplicado", "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"), "agregados": agregados}
        ajustes = [{"campo": c, "antes": leer_campo(p, c), "despues": leer_campo(q, c)} for c in AJUSTES if leer_campo(p, c) != leer_campo(q, c)]
        if ajustes:
            cambio["ajustes"] = ajustes
        antes_c = [c for c in p.get("cortes", [])]
        despues_c = [c for c in q["cortes"] if c.get("origen") != origen]
        quitados, nuevos = [c for c in antes_c if c not in despues_c], [c for c in despues_c if c not in antes_c]
        if quitados or nuevos:
            cambio["restaurados"] = {"antes": quitados, "despues": nuevos}
        if cambios_palabras:
            cambio["palabras"] = cambios_palabras
        q["cambios_ia"] = (q.get("cambios_ia") or [])[-(MAX_CAMBIOS - 1):] + [cambio]
    if proyecto.validar(q):
        return p, [], list(operaciones)
    return q, hechas, malas


def velocidad_valida(q, i, f, o):
    """{v, rampa?} de una operación «velocidad» si se puede poner en i..f (rangos de proyecto.validar_velocidades y sin pisar
    otra velocidad), o None."""
    v, rampa = o.get("v"), o.get("rampa", False)
    if not (proyecto.num(v) and proyecto.VEL_MIN <= v <= proyecto.VEL_MAX and isinstance(rampa, bool)):
        return None
    v = round(float(v), 2)
    if (rampa and (v > proyecto.RAMPA_MAX or f - i < proyecto.MIN_RAMPA)) or f - i < proyecto.MIN_VEL or (v == 1 and not rampa):
        return None
    if any(x["f"] > i and x["i"] < f for x in proyecto.velocidades(q)):
        return None
    return {"v": v, "rampa": True} if rampa else {"v": v}


def pedir(carpeta, pedido):
    p = proyecto.cargar(carpeta)
    if not p["palabras"]:
        return {"ok": False, "error": "Primero hay que transcribir el video: así tu IA sabe qué se dice y cuándo."}
    estilos = subtitulos.estilos()
    texto, error = ia.preguntar(prompt_pedir(p, pedido.strip()[:500], estilos))
    if error:  # pieza «ia»: {codigo, valores}; la interfaz traduce la frase y puede decidir por el código
        return {"ok": False, "error": ia.frase(error), "codigo": error["codigo"]}
    datos = leer_json_ia(texto)
    if not isinstance(datos, dict):
        return {"ok": False, "error": f"{ia.nombre()} no respondió con cambios que pueda aplicar. Prueba diciéndolo de otra forma."}
    origen = nuevo_id()
    nuevo, hechas, malas = aplicar(p, datos.get("operaciones", []), estilos, origen)
    resumen = str(datos.get("resumen", ""))[:300]
    if hechas:
        cambio = nuevo["cambios_ia"][-1]
        cambio["pedido"], cambio["resumen"] = pedido.strip()[:200], resumen
        proyecto.guardar(carpeta, nuevo)
    return {"ok": True, "resumen": resumen, "aplicadas": len(hechas), "ignoradas": len(malas), "cambio": origen if hechas else None,
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
    if error:  # pieza «ia»: {codigo, valores}; la interfaz traduce la frase y puede decidir por el código
        return {"ok": False, "error": ia.frase(error), "codigo": error["codigo"]}
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
    q["efectos"] = [x for x in q.get("efectos", []) if "i" not in x or (x["f"] > desde and x["i"] < hasta)]
    if "velocidades" in q:
        q["velocidades"] = [x for x in q["velocidades"] if x["f"] > desde and x["i"] < hasta]
    q["lienzo"] = "9:16"
    q["cambios_ia"] = []  # los cambios de la IA se quitan en el video donde se hicieron
    q.pop("plantilla", None)  # un Short de un video de plantilla es un video normal (sus clips quedan en el original)
    if problemas := proyecto.validar(q):  # antes de crear la carpeta y enlazar el video
        raise ValueError(" ".join(problemas[:3]))
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


def desde_entrada(ruta):
    """Lo que manda la app (la interfaz) llega en un JSON: se revisa cada campo antes de usarlo."""
    d = proyecto.leer_json(ruta, None)
    if not isinstance(d, dict):
        raise ValueError("No pude leer el pedido.")
    carpeta = proyecto.carpeta_valida(d.get("carpeta"))
    accion = d.get("accion")
    if accion == "pedir":
        texto = d.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("Escribe qué quieres cambiar.")
        return pedir(carpeta, texto.strip()[:2000])
    if accion == "shorts":
        return shorts(carpeta)
    if accion == "crear_short":
        desde, hasta, titulo = d.get("desde"), d.get("hasta"), d.get("titulo", "")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (desde, hasta)) or not isinstance(titulo, str):
            raise ValueError("Ese tramo no es válido.")
        return crear_short(carpeta, float(desde), float(hasta), titulo[:80])
    raise ValueError("No sé hacer eso.")


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) == 3 and a[0] == "entrada":
            r = desde_entrada(a[1])
        elif len(a) == 4 and a[0] == "pedir":
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
