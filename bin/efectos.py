"""Efectos y filtros: solo datos (formato en bin/efecto_formato.py y efectos/README.md), convertidos a ffmpeg por el código.

  efectos.py indice <indice.json> <salida.json>     valida el índice del catálogo que bajó la app → {"ok", "efectos": [...]}
  efectos.py entrada <entrada.json> <salida.json>   {"accion": "instalar", "archivo", "id", "sha256"}: valida el efecto
                                                    descargado y lo deja en ~/Corta/.corta/efectos/<id>.json → {"ok", "efecto"}

Dónde están: incluidos en la app (`efectos/<categoria>/<id>.json`) y descargados del catálogo de la comunidad
(`~/Corta/.corta/efectos/<id>.json`, ganan sobre los incluidos con el mismo id). En el proyecto, `efectos` es una lista de
efectos aplicados con sus pasos copiados (el proyecto se exporta igual aunque después borres el efecto):
  {"efecto": "calido", "pasos": [...], "i"?: s, "f"?: s, "origen"?: "ia-…"}     sin i/f = todo el video

Todo pasa en el tiempo del video EXPORTADO, después de unir las piezas y antes de los subtítulos (que nunca se desenfocan ni se
mueven). Un efecto de un tramo se activa en los pedazos de ese tramo que quedan (`intervalos`). La misma lógica de tiempos existe
en ui/app.js (`intervalosSalida`, `uniones`, `segmentosZoom`, `segmentosCapa`, `valorEn`); casos en pruebas/casos.json («efectos»).

Lista blanca de filtros de ffmpeg (solo estos, con números que salen de rangos validados; ningún texto del efecto llega a ffmpeg):
  colorchannelmixer   los filtros de color de CSS (brightness, contrast, saturate, hue-rotate, sepia, grayscale) juntos en una
                      matriz con los mismos números de la especificación
  lutrgb              el desplazamiento que deja contrast()
  gblur               desenfoque (sigma = radio de blur() de CSS)
  perspective         zoom animado (con interpolación: sin saltos)
  color + geq + scale + overlay   capas de color (viñeta, tinte, fundidos y transiciones) con su opacidad en el tiempo
  split + crop + overlay          transiciones que mueven la imagen: franjas, barrido (con la copia que entra por el otro lado) y
                                  las franjas que saltan en la interferencia; la posición es una expresión de `t` con números
  rgbashift                       los canales de color corridos de la interferencia
  trim + setpts + tpad            la rama de la interferencia: solo los cuadros de su ventana pasan a RGB (y vuelven a su lugar)
  eq                              la exposición del destello (brillo multiplicado, en YUV)
Las transiciones solo trabajan en su ventana alrededor de cada unión (`enable`): fuera de ella el video pasa sin costo.
"""
import hashlib
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import efecto_formato  # noqa: E402
import proyecto  # noqa: E402

DESCARGADOS = os.path.join(proyecto.INTERNO, "efectos")
MAX_BYTES = 64 * 1024
ARCHIVO_CATALOGO = re.compile(r"efectos/([a-z]+)/([a-z0-9][a-z0-9-]{0,38}[a-z0-9])\.json")
FPS = 30


def incluidos_dir():
    return os.path.join(proyecto.RECURSOS, "efectos")


def _leer_efecto(ruta):
    try:
        if os.path.getsize(ruta) > MAX_BYTES:
            return None
    except OSError:
        return None
    d = proyecto.leer_json(ruta, None)
    return d if d is not None and not efecto_formato.validar_efecto(d, ruta) else None


def disponibles():
    """Todos los efectos válidos, por id: los incluidos y los descargados (estos ganan). Cada uno con `origen`."""
    todos = {}
    base = incluidos_dir()
    for categoria in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        carpeta = os.path.join(base, categoria)
        if not os.path.isdir(carpeta):
            continue
        for n in sorted(os.listdir(carpeta)):
            if n.endswith(".json"):
                d = _leer_efecto(os.path.join(carpeta, n))
                if d and d["categoria"] == categoria:
                    todos[d["id"]] = {**d, "origen": "incluido"}
    for n in sorted(os.listdir(DESCARGADOS)) if os.path.isdir(DESCARGADOS) else []:
        if n.endswith(".json"):
            d = _leer_efecto(os.path.join(DESCARGADOS, n))
            if d:
                todos[d["id"]] = {**d, "origen": "descargado"}
    return todos


# ───────────── Tiempos (la misma lógica que ui/app.js) ─────────────
def _r3(n):
    return math.floor(n * 1000 + 0.5) / 1000


def _r4(n):
    return math.floor(n * 10000 + 0.5) / 10000


def alcance(p, ap):
    """Tramo del original al que se aplica: (i, f) o todo el video."""
    return (ap["i"], ap["f"]) if "i" in ap else (0.0, p["fuente"]["duracion"])


def intervalos_salida(p, i, f):
    """Los pedazos del tramo i..f (segundos del original) que quedan, en segundos del video exportado: [[a, b], …]."""
    r, acumulado = [], 0.0
    for t in proyecto.conservados(p):
        a, b = max(t["i"], i), min(t["f"], f)
        if b - a >= 0.02:
            r.append([_r3(acumulado + a - t["i"]), _r3(acumulado + b - t["i"])])
        acumulado += t["f"] - t["i"]
    return r


def uniones(p, i, f):
    """Dónde se juntan dos pedazos del tramo i..f en el video exportado: un corte en medio o una división (`divisiones`, donde
    dividiste o donde una plantilla pasa de un clip al siguiente). Ahí van las transiciones."""
    r, acumulado, anterior = [], 0.0, False
    divs = sorted(x for x in p.get("divisiones", []) if isinstance(x, (int, float)) and not isinstance(x, bool) and i + 0.02 < x < f - 0.02)
    for t in proyecto.conservados(p):
        dentro = min(t["f"], f) - max(t["i"], i) >= 0.02
        if dentro and anterior:
            r.append(_r3(acumulado))
        r += [_r3(acumulado + d - t["i"]) for d in divs if t["i"] + 0.02 < d < t["f"] - 0.02]
        anterior = dentro
        acumulado += t["f"] - t["i"]
    return r


def segmentos_zoom(paso, a, b):
    """[[t0, v0, t1, v1], …] de la escala entre a y b (segundos del exportado)."""
    d, h = paso["desde"], paso["hasta"]
    curva = paso.get("curva", "lineal")
    if curva == "golpe":
        g = _r3(a + min(0.15, (b - a) / 2))
        return [[a, d, g, h], [g, h, b, h]]
    if curva == "suave":
        s = lambda x: x * x * (3 - 2 * x)  # noqa: E731
        return [[_r3(a + (b - a) * k / 8), _r4(d + (h - d) * s(k / 8)), _r3(a + (b - a) * (k + 1) / 8), _r4(d + (h - d) * s((k + 1) / 8))]
                for k in range(8)]
    return [[a, d, b, h]]


def segmentos_capa(paso, a, b, juntas, pedazos):
    """[[t0, v0, t1, v1], …] de la opacidad de una capa de color (0 = no se ve)."""
    tipo = paso["tipo"]
    if tipo == "tinte":
        return [[x, paso["fuerza"], y, paso["fuerza"]] for x, y in pedazos]
    if tipo == "fundido":
        r = []
        if paso.get("entrada", 0) > 0:
            r.append([a, 1, _r3(min(b, a + paso["entrada"])), 0])
        if paso.get("salida", 0) > 0:
            r.append([_r3(max(a, b - paso["salida"])), 0, b, 1])
        return r
    if tipo == "transicion":
        m = paso["duracion"] / 2
        r = []
        for j in juntas:
            r += [[_r3(j - m), 0, j, 1], [j, 1, _r3(j + m), 0]]
        return r
    return []


def valor_en(segmentos, t, neutro):
    """El valor en el segundo t: el del primer segmento que lo contiene (interpolado), o `neutro`."""
    for t0, v0, t1, v1 in segmentos:
        if t0 <= t < t1:
            return _r4(v0 + (v1 - v0) * (t - t0) / (t1 - t0)) if t1 > t0 else v0
    return neutro


# ───────────── Transiciones en las uniones (la misma lógica que ui/app.js; casos «transiciones» en pruebas/casos.json) ─────────────
def ventanas(paso, juntas, parte=1):
    """[[t0, t1], …]: lo que dura la transición alrededor de cada unión (`parte` < 1: solo el centro, donde va más rápido)."""
    m = paso["duracion"] / 2 * parte
    return [[_r3(j - m), _r3(j + m)] for j in juntas]


def _curva(t0, t1, v0, v1, forma, n):
    """n segmentos rectos de (t0, v0) a (t1, v1) que siguen `forma` (0 → 0, 1 → 1)."""
    return [[_r3(t0 + (t1 - t0) * k / n), _r4(v0 + (v1 - v0) * forma(k / n)), _r3(t0 + (t1 - t0) * (k + 1) / n),
             _r4(v0 + (v1 - v0) * forma((k + 1) / n))] for k in range(n)]


def _acelera(x):
    return x * x


def _frena(x):
    return 1 - (1 - x) * (1 - x)


def _suave(x):
    return x * x * (3 - 2 * x)


def segmentos_paso(paso, juntas):
    """[[t0, v0, t1, v1], …] de lo que mueve una transición en cada unión (segundos del exportado):
       rebote, zoom_paso   la escala (1 = sin zoom)
       barrido             cuánto se corrió la imagen, en cuadros (0 → 1: sale entera y la siguiente queda en su lugar)
       franjas             lo mismo por franja: 0 → 1 al salir y −1 → 0 al entrar (cada franja va en sentido contrario a su vecina)
       destello            la opacidad del color"""
    tipo, m = paso["tipo"], paso["duracion"] / 2
    fuerza = paso.get("intensidad", 0.5)
    r = []
    for j in juntas:
        a, b = _r3(j - m), _r3(j + m)
        if tipo == "rebote":
            alto = _r4(1 + 0.04 + 0.16 * fuerza)
            medio, tres = _r3(j + m / 2), _r3(j + m * 3 / 4)
            r += (_curva(a, j, 1, alto, _frena, 3) + _curva(j, medio, alto, 1, _suave, 2)
                  + [[medio, 1, tres, _r4(1 + (alto - 1) * 0.3)], [tres, _r4(1 + (alto - 1) * 0.3), b, 1]])
        elif tipo == "zoom_paso":
            alto = _r4(1 + 0.1 + 0.5 * fuerza)
            r += _curva(a, j, 1, alto, _acelera, 4) + _curva(j, b, alto, 1, _frena, 4)
        elif tipo == "barrido":
            r += _curva(a, b, 0, 1, _suave, 8)
        elif tipo == "franjas":
            r += _curva(a, j, 0, 1, _acelera, 4) + _curva(j, b, -1, 0, _frena, 4)
        elif tipo == "destello":
            pico = paso.get("intensidad", 0.8)
            subida, bajada = _r3(j - m * 0.4), _r3(j + m * 0.3)
            r += [[a, 0, subida, _r4(pico * 0.2)], [subida, _r4(pico * 0.2), j, pico], [j, pico, bajada, _r4(pico * 0.45)],
                  [bajada, _r4(pico * 0.45), b, 0]]
    return r


def segmentos_exposicion(paso, juntas):
    """[[t0, v0, t1, v1], …]: la exposición de un destello (brillo multiplicado; 1 = igual), que sube y baja con su color."""
    if not paso.get("exposicion"):
        return []
    pico = paso.get("intensidad", 0.8)
    return [[t0, _r4(1 + paso["exposicion"] * v0 / pico), t1, _r4(1 + paso["exposicion"] * v1 / pico)]
            for t0, v0, t1, v1 in segmentos_paso(paso, juntas)]


def _azar(semilla):
    """Números «al azar» que se repiten igual en Python y en JS (Park–Miller: enteros exactos en los dos)."""
    x = semilla % 2147483646 + 1

    def siguiente():
        nonlocal x
        x = x * 16807 % 2147483647
        return x / 2147483647
    return siguiente


def franjas_interferencia(paso):
    """Lo alto de las dos franjas que saltan en una interferencia (fracciones del alto): una gruesa y una delgada."""
    return _r4(0.05 + 0.18 * paso.get("intensidad", 0.6)), 0.02


def cortes_interferencia(paso, juntas):
    """[[t0, t1, canales, y1, dx1, y2, dx2], …]: cada instante de una interferencia. `canales` = cuántos píxeles (a 1080 de
    ancho) se corre el rojo (el azul, al revés); la franja gruesa (y1, en fracciones del alto) salta dx1 (fracción del ancho) y la
    delgada, y2 y dx2. Más fuerte junto al corte."""
    m, fuerza = paso["duracion"] / 2, paso.get("intensidad", 0.6)
    alto1, alto2 = franjas_interferencia(paso)
    n = max(2, min(8, math.floor(paso["duracion"] * 10 + 0.5)))
    r = []
    for q, j in enumerate(juntas):
        azar = _azar(math.floor(j * 1000 + 0.5) * 31 + q * 7919 + 17)
        a = _r3(j - m)
        for k in range(n):
            t0, t1 = _r3(a + 2 * m * k / n), _r3(a + 2 * m * (k + 1) / n)
            f = fuerza * (1 - abs((t0 + t1) / 2 - j) / m * 0.5)
            canales = (1 if azar() < 0.5 else -1) * math.floor(f * (12 + 36 * azar()) + 0.5)
            y1 = _r4((1 - alto1) * azar())
            dx1 = _r4((1 if azar() < 0.5 else -1) * f * (0.06 + 0.2 * azar()))
            y2 = _r4((1 - alto2) * azar())
            dx2 = _r4((1 if azar() < 0.5 else -1) * f * (0.1 + 0.25 * azar()))
            r.append([t0, t1, canales, y1, dx1, y2, dx2])
    return r


# ───────────── ffmpeg ─────────────
def _n(x):
    """Número para el grafo de ffmpeg: siempre dígitos, punto y signo (nunca texto)."""
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _por(a, b):
    """a·b (matrices 3×3)."""
    return [[sum(a[f][k] * b[k][c] for k in range(3)) for c in range(3)] for f in range(3)]


def matriz_color(paso):
    """Los filtros de CSS de un paso «color» (brightness, contrast, saturate, hue-rotate, sepia, grayscale, en ese orden y con las
    matrices de la especificación Filter Effects) como una sola transformación: color' = M·color + o (0 a 255)."""
    m, o = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0.0, 0.0, 0.0]

    def aplicar(a, desplazamiento=0.0):
        nonlocal m, o
        m = _por(a, m)
        o = [sum(a[f][k] * o[k] for k in range(3)) + desplazamiento for f in range(3)]

    if "brillo" in paso:
        b = paso["brillo"]
        aplicar([[b, 0, 0], [0, b, 0], [0, 0, b]])
    if "contraste" in paso:
        c = paso["contraste"]
        aplicar([[c, 0, 0], [0, c, 0], [0, 0, c]], 127.5 * (1 - c))
    if "saturacion" in paso:
        s = paso["saturacion"]
        aplicar([[0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
                 [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
                 [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s]])
    if "tono" in paso:
        a = math.radians(paso["tono"])
        co, si = math.cos(a), math.sin(a)
        aplicar([[0.213 + co * 0.787 - si * 0.213, 0.715 - co * 0.715 - si * 0.715, 0.072 - co * 0.072 + si * 0.928],
                 [0.213 - co * 0.213 + si * 0.143, 0.715 + co * 0.285 + si * 0.140, 0.072 - co * 0.072 - si * 0.283],
                 [0.213 - co * 0.213 - si * 0.787, 0.715 - co * 0.715 + si * 0.715, 0.072 + co * 0.928 + si * 0.072]])
    if "sepia" in paso:
        x = 1 - paso["sepia"]
        aplicar([[0.393 + 0.607 * x, 0.769 - 0.769 * x, 0.189 - 0.189 * x],
                 [0.349 - 0.349 * x, 0.686 + 0.314 * x, 0.168 - 0.168 * x],
                 [0.272 - 0.272 * x, 0.534 - 0.534 * x, 0.131 + 0.869 * x]])
    if "grises" in paso:
        x = 1 - paso["grises"]
        aplicar([[0.2126 + 0.7874 * x, 0.7152 - 0.7152 * x, 0.0722 - 0.0722 * x],
                 [0.2126 - 0.2126 * x, 0.7152 + 0.2848 * x, 0.0722 - 0.0722 * x],
                 [0.2126 - 0.2126 * x, 0.7152 - 0.7152 * x, 0.0722 + 0.9278 * x]])
    return m, o


def filtros_color(paso):
    """Un paso «color» en ffmpeg: colorchannelmixer con la matriz y, si hace falta, lutrgb con el desplazamiento (contraste).
    Juntar todo en una matriz hace que exportar con un filtro de color cueste poco más que sin él."""
    m, o = matriz_color(paso)
    r = []
    if any(abs(m[f][c] - (1 if f == c else 0)) > 1e-6 for f in range(3) for c in range(3)):
        nombres = ("rr", "rg", "rb", "gr", "gg", "gb", "br", "bg", "bb")
        r.append("colorchannelmixer=" + ":".join(f"{k}={_n(max(-2, min(2, v)))}" for k, v in zip(nombres, [x for fila in m for x in fila])))
    if any(abs(x) > 1e-3 for x in o):
        r.append("lutrgb=" + ":".join(f"{c}='clip(val+{_n(x)},0,255)'" for c, x in zip("rgb", o)))
    return r


def _expr(segmentos, neutro, var):
    """Los segmentos como expresión de ffmpeg: el primero que contiene el tiempo manda (igual que valor_en)."""
    e = _n(neutro)
    for t0, v0, t1, v1 in reversed(segmentos):
        pendiente = (v1 - v0) / (t1 - t0) if t1 > t0 else 0
        e = f"if(gte({var},{_n(t0)})*lt({var},{_n(t1)}),{_n(v0)}+{_n(pendiente)}*({var}-{_n(t0)}),{e})"
    return e


COLORES = {"negro": (0, 0, 0), "blanco": (255, 255, 255)}
#: Viñeta: transparente hasta el 40 % de la distancia al borde (elipse hasta las esquinas) y hasta 85 % de negro en las esquinas.
VINETA_DESDE, VINETA_ALFA = 0.4, 0.85


def cadena(p, ancho, alto, entrada="[vc]"):
    """Filtros de los efectos del proyecto, desde `entrada` (el video ya unido). Devuelve (partes del grafo, etiqueta de salida)."""
    total = proyecto.duracion_final(p)
    dur = p["fuente"]["duracion"]
    partes, actual, k = [], entrada, 0

    def poner(filtro):
        nonlocal actual, k
        partes.append(f"{actual}{filtro}[fx{k}]")
        actual, k = f"[fx{k}]", k + 1

    def nueva():
        nonlocal k
        k += 1
        return f"fx{k - 1}"

    def capa_color(rgb, segs, tramos):
        """Una capa de color con la opacidad de `segs`, solo en los `tramos` [[t0, t1], …] (las ventanas de una transición): cada
        una es una fuente corta (16×16 agrandada) que empieza en su cuadro (setpts: medio cuadro más, porque el tiempo se trunca a un
        cuadro entero) y se acaba; antes y después overlay deja pasar el video sin trabajo."""
        nonlocal actual
        for w0, w1 in tramos:
            f0, f1 = max(0, math.ceil(w0 * FPS - 1e-6)), math.floor(w1 * FPS + 1e-6)
            if f1 < f0 or f0 >= total * FPS:
                continue
            cero = f0 / FPS
            propios = [[t0 - cero, v0, t1 - cero, v1] for t0, v0, t1, v1 in segs if t1 > w0 - 1e-6 and t0 < w1 + 1e-6]
            capa, salida = f"capa{k}", nueva()
            partes.append(f"color=c=black:s=16x16:r={FPS}:d={_n((f1 - f0 + 1) / FPS)},format=rgba,geq=r='{rgb[0]}':g='{rgb[1]}':b='{rgb[2]}'"
                          f":a='255*({_expr(propios, 0, 'T')})',scale={ancho}:{alto}:flags=neighbor,setsar=1,setpts=PTS+{_n((f0 + 0.5) / FPS)}/TB[{capa}]")
            partes.append(f"{actual}[{capa}]overlay=eof_action=pass:repeatlast=0[{salida}]")
            actual = f"[{salida}]"

    def escala(segs, cuando):
        """Zoom desde el centro (la mitad del ancho y el 45 % del alto, como la vista previa), con interpolación: sin saltos."""
        z = "(" + _expr(segs, 1, f"(in/{FPS})") + ")"
        x0, x1 = f"W*0.5*(1-1/{z})", f"W*0.5+W*0.5/{z}"
        y0, y2 = f"H*0.45*(1-1/{z})", f"H*0.45+H*0.55/{z}"
        poner(f"perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':x2='{x0}':y2='{y2}':x3='{x1}':y3='{y2}':eval=frame{cuando}")

    def solo(tramos, exacto=False):
        """:enable con los tramos [[t0, t1], …] (exacto: sin repetir el cuadro del borde entre dos tramos seguidos)."""
        return ":enable='" + "+".join((f"gte(t,{_n(x)})*lt(t,{_n(y)})" if exacto else f"between(t,{_n(x)},{_n(y)})") for x, y in tramos) + "'"

    def transicion(paso, juntas):
        nonlocal actual
        tipo, cuando = paso["tipo"], solo(ventanas(paso, juntas))
        if tipo in ("rebote", "zoom_paso"):
            escala(segmentos_paso(paso, juntas), cuando)
            if tipo == "zoom_paso" and paso.get("desenfoque", 0) > 0:
                poner(f"gblur=sigma={_n(paso['desenfoque'] * 16 * ancho / 1080)}{solo(ventanas(paso, juntas, 0.4))}")
        elif tipo == "destello":
            if paso.get("exposicion", 0) > 0:
                # Exposición = brillo multiplicado (brightness() de CSS) hecho en YUV con eq, sin pasar a RGB:
                # Y' = 16 + (Y − 16)·b y el color (U, V) por b.
                b = "(" + _expr(segmentos_exposicion(paso, juntas), 1, "t") + ")"
                poner(f"eq=contrast='{b}':brightness='0.437255*({b}-1)':saturation='{b}':eval=frame{cuando}")
            color = paso.get("color", "#FFFFFF")
            capa_color(tuple(int(color[x:x + 2], 16) for x in (1, 3, 5)), segmentos_paso(paso, juntas), ventanas(paso, juntas))
        elif tipo == "barrido":
            # La imagen se corre y por el otro lado entra la misma (al pasar la unión, ya es el clip siguiente).
            u = "(" + _expr(segmentos_paso(paso, juntas), 0, "t") + ")"
            direccion = paso.get("direccion", "izquierda")
            lado, otro, largo = ("x", "y", ancho) if direccion in ("izquierda", "derecha") else ("y", "x", alto)
            signo = -1 if direccion in ("izquierda", "arriba") else 1
            uno = f"{_n(signo * largo)}*{u}"
            dos = uno + ("+" if signo < 0 else "-") + str(largo)
            a, b, c, m1, m2 = nueva(), nueva(), nueva(), nueva(), nueva()
            partes.append(f"{actual}split=3[{a}][{b}][{c}]")
            partes.append(f"[{a}][{b}]overlay={lado}='{uno}':{otro}=0:eval=frame{cuando}[{m1}]")
            partes.append(f"[{m1}][{c}]overlay={lado}='{dos}':{otro}=0:eval=frame{cuando}[{m2}]")
            actual = f"[{m2}]"
            if paso.get("desenfoque", 0) > 0:
                # Estela de movimiento: desenfoque solo a lo largo del barrido, en el centro de la ventana (donde va más rápido).
                s_ = _n(paso["desenfoque"] * 40 * ancho / 1080)
                poner((f"gblur=sigma={s_}:sigmaV=0" if lado == "x" else f"gblur=sigma=0:sigmaV={s_}") + solo(ventanas(paso, juntas, 0.5)))
        elif tipo == "franjas":
            n = int(paso.get("franjas", 3))
            vertical = paso.get("direccion", "vertical") == "vertical"
            largo = alto if vertical else ancho
            bordes = [2 * math.floor((ancho if vertical else alto) * q / n / 2 + 0.5) for q in range(n + 1)]
            v = "(" + _expr(segmentos_paso(paso, juntas), 0, "t") + ")"
            etiquetas = [nueva() for _ in range(n + 1)]
            fondo = nueva()
            partes.append(f"{actual}split={n + 1}" + "".join(f"[{e}]" for e in etiquetas))
            # Detrás de las franjas, negro: eq lo hace en YUV sin generar otro video (y solo en la ventana).
            partes.append(f"[{etiquetas[0]}]eq=contrast=0:brightness=-1:saturation=0{cuando}[{fondo}]")
            for q in range(n):
                desde, hasta, recorte, salida = bordes[q], bordes[q + 1], nueva(), nueva()
                w, h, x, y = (hasta - desde, alto, desde, 0) if vertical else (ancho, hasta - desde, 0, desde)
                partes.append(f"[{etiquetas[q + 1]}]crop={w}:{h}:{x}:{y}[{recorte}]")
                mueve = f"{_n((1 if q % 2 == 0 else -1) * largo)}*{v}"
                pos = f"x={x}:y='{mueve}'" if vertical else f"x='{mueve}':y={y}"
                partes.append(f"[{fondo}][{recorte}]overlay={pos}:eval=frame{cuando}[{salida}]")
                fondo = salida
            actual = f"[{fondo}]"
        elif tipo == "interferencia":
            # rgbashift trabaja en RGB: pasar todo el video a RGB y de vuelta costaría tanto como exportarlo otra vez. Por eso cada
            # unión tiene su rama: una copia que se queda solo con los cuadros de su ventana (trim por número de cuadro), los
            # descompone y vuelve encima del video justo ahí (tpad la pone en su lugar; overlay la deja pasar al terminar).
            instantes = cortes_interferencia(paso, juntas)
            altos = [max(2, 2 * math.floor(h * alto / 2 + 0.5)) for h in franjas_interferencia(paso)]
            for (w0, w1), j in zip(ventanas(paso, juntas), juntas):
                f0, f1 = max(0, math.ceil(w0 * FPS - 1e-6)), math.floor(w1 * FPS + 1e-6)
                if f1 < f0 or f0 >= total * FPS:
                    continue
                cero = f0 / FPS
                propios = [[x[0] - cero, x[1] - cero, *x[2:]] for x in instantes if w0 - 1e-6 <= x[0] and x[1] <= w1 + 1e-6]
                a, b, salida = nueva(), nueva(), nueva()
                filtros = [f"trim=start_frame={f0}:end_frame={f1 + 1}", "setpts=PTS-STARTPTS"]
                partes.append(f"{actual}split[{a}][{b}]")
                rama = f"[{b}]"
                for cual, hh in enumerate(altos):
                    # Una franja de la imagen salta de lado; su posición cambia en cada instante (expresiones de t).
                    ys = [[x[0], x[3 + 2 * cual], x[1], x[3 + 2 * cual]] for x in propios]
                    dxs = [[x[0], x[4 + 2 * cual], x[1], x[4 + 2 * cual]] for x in propios]
                    yy = f"min({alto - hh},2*floor(({_expr(ys, 0, 't')})*{alto}/2))"
                    xx = f"2*floor(({_expr(dxs, 0, 't')})*{ancho}/2)"
                    c, d, recorte, junta = nueva(), nueva(), nueva(), nueva()
                    partes.append(f"{rama}{','.join(filtros)},split[{c}][{d}]" if filtros else f"{rama}split[{c}][{d}]")
                    filtros = []
                    partes.append(f"[{d}]crop={ancho}:{hh}:0:'{yy}'[{recorte}]")
                    partes.append(f"[{c}][{recorte}]overlay=x='{xx}':y='{yy}':eval=frame[{junta}]")
                    rama = f"[{junta}]"
                # Los canales corridos (el rojo a un lado, el azul al otro), seguidos: se pasa a RGB una sola vez.
                corridos = [f"rgbashift=rh={px}:bh={-px}{solo([[x[0], x[1]]], True)}" for x in propios
                            if (px := math.floor(abs(x[2]) * ancho / 1080 + 0.5) * (1 if x[2] >= 0 else -1))]
                lista = ",".join(corridos + ["format=yuv420p", f"tpad=start={f0}"])
                listo = nueva()
                partes.append(f"{rama}{lista}[{listo}]")
                partes.append(f"[{a}][{listo}]overlay=eof_action=pass:repeatlast=0:enable='between(n,{f0},{f1})'[{salida}]")
                actual = f"[{salida}]"

    for ap in p.get("efectos", []):
        if efecto_formato.validar_pasos(ap.get("pasos")):
            continue
        i, f = alcance(p, ap)
        pedazos = intervalos_salida(p, i, f)
        if not pedazos:
            continue
        a, b = pedazos[0][0], pedazos[-1][1]
        todo = i <= 0.001 and f >= dur - 0.001
        activo = "" if todo else ":enable='" + "+".join(f"between(t,{_n(x)},{_n(y)})" for x, y in pedazos) + "'"
        juntas = uniones(p, i, f)
        for paso in ap["pasos"]:
            tipo = paso["tipo"]
            if tipo == "color":
                for filtro in filtros_color(paso):
                    poner(filtro + activo)
            elif tipo == "desenfoque":
                poner(f"gblur=sigma={_n(paso['radio'] * ancho / 1080)}{activo}")
            elif tipo == "vineta":
                # Una capa negra que se oscurece hacia los bordes, igual que el radial-gradient de la vista previa (se calcula una
                # sola vez: un cuadro que overlay repite).
                capa = f"capa{k}"
                alfa = _n(255 * VINETA_ALFA * paso["fuerza"])
                partes.append(f"color=c=black:s={ancho // 4}x{alto // 4}:r={FPS}:d=0.04,format=rgba,geq=r='0':g='0':b='0'"
                              f":a='{alfa}*clip((hypot((X-W/2)/(W/2),(Y-H/2)/(H/2))/sqrt(2)-{_n(VINETA_DESDE)})/{_n(1 - VINETA_DESDE)},0,1)'"
                              f",scale={ancho}:{alto},setsar=1[{capa}]")
                partes.append(f"{actual}[{capa}]overlay=eof_action=repeat{activo}[fx{k}]")
                actual, k = f"[fx{k}]", k + 1
            elif tipo in efecto_formato.TRANSICIONES[1:]:
                if juntas:
                    transicion(paso, juntas)
            elif tipo == "zoom":
                # perspective (con interpolación) en vez de zoompan: el zoom lento queda suave, sin saltos de un píxel. El centro a
                # la mitad del ancho y al 45 % del alto, como la vista previa.
                z = "(" + _expr(segmentos_zoom(paso, a, b), 1, f"(in/{FPS})") + ")"
                x0, x1 = f"W*0.5*(1-1/{z})", f"W*0.5+W*0.5/{z}"
                y0, y2 = f"H*0.45*(1-1/{z})", f"H*0.45+H*0.55/{z}"
                poner(f"perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':x2='{x0}':y2='{y2}':x3='{x1}':y3='{y2}':eval=frame"
                      + (":enable='" + "+".join(f"between(t,{_n(x)},{_n(y)})" for x, y in pedazos) + "'" if not todo else ""))
            elif tipo == "transicion":
                # El pestañeo: una capa de color solo alrededor de cada unión.
                segs = segmentos_capa(paso, a, b, juntas, pedazos)
                if segs:
                    capa_color(COLORES[paso.get("color", "negro")], segs, ventanas(paso, juntas))
            else:
                segs = segmentos_capa(paso, a, b, juntas, pedazos)
                if not segs:
                    continue
                rojo, verde, azul = (tuple(int(paso["color"][x:x + 2], 16) for x in (1, 3, 5)) if tipo == "tinte"
                                     else COLORES[paso.get("color", "negro")])
                capa = f"capa{k}"
                partes.append(f"color=c=black:s=16x16:r={FPS}:d={_n(total + 1)},format=rgba,geq=r='{rojo}':g='{verde}':b='{azul}'"
                              f":a='255*({_expr(segs, 0, 'T')})',scale={ancho}:{alto}:flags=neighbor,setsar=1[{capa}]")
                partes.append(f"{actual}[{capa}]overlay=eof_action=pass[fx{k}]")
                actual, k = f"[fx{k}]", k + 1
    return partes, actual


# ───────────── Catálogo (lo descarga la app; aquí solo se valida) ─────────────
def validar_indice(d):
    """Del índice del catálogo, solo las entradas válidas: {…efecto, archivo, sha256, bytes}. Lo demás se descarta."""
    lista = d.get("efectos") if isinstance(d, dict) else None
    r, vistos = [], set()
    for x in lista if isinstance(lista, list) else []:
        if not isinstance(x, dict):
            continue
        efecto = {k: v for k, v in x.items() if k in efecto_formato.CLAVES}
        m = ARCHIVO_CATALOGO.fullmatch(str(x.get("archivo", "")))
        if (efecto_formato.validar_efecto(efecto) or not m or m.group(1) != efecto["categoria"] or m.group(2) != efecto["id"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(x.get("sha256", ""))) or not isinstance(x.get("bytes"), int)
                or not 0 < x["bytes"] <= MAX_BYTES or efecto["id"] in vistos):
            continue
        vistos.add(efecto["id"])
        r.append({**efecto, "archivo": x["archivo"], "sha256": x["sha256"], "bytes": x["bytes"]})
    return r[:500]


def instalar(d):
    """Un efecto que bajó la app: se valida otra vez (huella, id y formato) antes de guardarlo."""
    if not isinstance(d, dict) or not isinstance(d.get("archivo"), str) or not isinstance(d.get("id"), str):
        raise ValueError("No pude leer el efecto.")
    with open(d["archivo"], "rb") as f:
        crudo = f.read(MAX_BYTES + 1)
    if len(crudo) > MAX_BYTES or (d.get("sha256") and hashlib.sha256(crudo).hexdigest() != d["sha256"]):
        raise ValueError("El efecto llegó dañado. Intenta de nuevo.")
    try:
        efecto = json.loads(crudo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("Ese efecto no es válido.") from None
    if efecto_formato.validar_efecto(efecto) or efecto["id"] != d["id"]:
        raise ValueError("Ese efecto no es válido.")
    proyecto.escribir_json(os.path.join(DESCARGADOS, efecto["id"] + ".json"), efecto)
    return {"ok": True, "efecto": {**efecto, "origen": "descargado"}}


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) == 3 and a[0] == "indice":
            r = {"ok": True, "efectos": validar_indice(proyecto.leer_json(a[1], None))}
        elif len(a) == 3 and a[0] == "entrada":
            datos = proyecto.leer_json(a[1], None)
            if not isinstance(datos, dict) or datos.get("accion") != "instalar":
                raise ValueError("No sé hacer eso.")
            r = instalar(datos)
        else:
            print(__doc__)
            sys.exit(2)
    except (OSError, ValueError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[-1], r)
    print(json.dumps({"ok": r["ok"]}, ensure_ascii=False))
