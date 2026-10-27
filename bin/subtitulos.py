"""Subtítulos animados: de las palabras del proyecto a un archivo .ass que ffmpeg dibuja sobre el video. Solo biblioteca estándar.

Los estilos son JSON de **solo datos** (estilos/*.json; formato en estilos/README.md). La vista previa de la interfaz dibuja el
mismo estilo con CSS a partir del mismo JSON, para que lo que ves sea lo que exportas.
"""
import os
import re

import proyecto

CLAVES = {"formato", "id", "nombre", "autor", "fuente", "peso", "tamano", "color", "color_activo", "borde", "color_borde", "sombra",
          "mayusculas", "fondo", "color_fondo", "animacion", "notas"}
ANIMACIONES = {"ninguna", "pop", "subrayado", "palabra"}
HEX = re.compile(r"#[0-9a-fA-F]{6}")


def validar_estilo(s):
    if not isinstance(s, dict):
        return ["El estilo no es un objeto JSON."]
    e = []
    if s.get("formato") != 1:
        e.append("formato debe ser 1.")
    if extra := set(s) - CLAVES:
        e.append("Campos desconocidos: " + ", ".join(sorted(extra)) + ".")
    if not re.fullmatch(r"[a-z0-9-]{2,40}", str(s.get("id", ""))):
        e.append("id: minúsculas, números y guiones.")
    if not isinstance(s.get("nombre"), str) or not 0 < len(s["nombre"]) <= 30 or "<" in s["nombre"]:
        e.append("nombre: texto corto sin HTML.")
    if not re.fullmatch(r"[A-Za-z0-9 \-]{2,40}", str(s.get("fuente", ""))):
        e.append("fuente: nombre de la tipografía (letras, números, espacios).")
    if s.get("peso") not in (400, 500, 600, 700, 800, 900):
        e.append("peso: 400 a 900.")
    if not (isinstance(s.get("tamano"), (int, float)) and 3 <= s["tamano"] <= 16):
        e.append("tamano: % del ancho del video, entre 3 y 16.")
    for c in ("color", "color_activo", "color_borde", "color_fondo"):
        if not HEX.fullmatch(str(s.get(c, ""))):
            e.append(f"{c}: color #RRGGBB.")
    if not (isinstance(s.get("borde"), (int, float)) and 0 <= s["borde"] <= 12):
        e.append("borde: 0 a 12 (en px a 1080 de ancho).")
    if not (isinstance(s.get("sombra"), (int, float)) and 0 <= s["sombra"] <= 12):
        e.append("sombra: 0 a 12.")
    if not isinstance(s.get("mayusculas"), bool) or not isinstance(s.get("fondo"), bool):
        e.append("mayusculas y fondo: true o false.")
    if s.get("animacion") not in ANIMACIONES:
        e.append("animacion: " + ", ".join(sorted(ANIMACIONES)) + ".")
    return e


def estilos():
    """Todos los estilos válidos: los de la persona (.corta/estilos) ganan sobre los incluidos con el mismo id."""
    todos = {}
    for carpeta in (os.path.join(proyecto.RECURSOS, "estilos"), os.path.join(proyecto.INTERNO, "estilos")):
        try:
            nombres = sorted(os.listdir(carpeta))
        except OSError:
            continue
        for n in nombres:
            if n.endswith(".json"):
                s = proyecto.leer_json(os.path.join(carpeta, n), None)
                if s is not None and not validar_estilo(s):
                    todos[s["id"]] = s
    return todos


def lineas(palabras, por_linea):
    """Agrupa palabras en líneas: corta por cantidad, por puntuación y por pausas largas (más de 0,6 s)."""
    grupos, actual = [], []
    for k, w in enumerate(palabras):
        actual.append(w)
        siguiente = palabras[k + 1] if k + 1 < len(palabras) else None
        fin_frase = re.search(r"[.!?…,;:]$", w["t"])
        pausa = siguiente is not None and siguiente["i"] - w["f"] > 0.6
        if len(actual) >= por_linea or fin_frase or pausa or siguiente is None:
            grupos.append(actual)
            actual = []
    return grupos


def _color_ass(hexa, alfa=0):
    """#RRGGBB → &HAABBGGRR (ASS usa azul-verde-rojo y alfa invertida)."""
    r, g, b = hexa[1:3], hexa[3:5], hexa[5:7]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _tiempo(s):
    s = max(0.0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def _escapar(t):
    """Texto seguro dentro de una línea Dialogue: sin bloques {…} de ASS y sin saltos ni caracteres de control (un «\\r» o un
    separador de línea en una palabra o un texto podría abrir una línea nueva en el archivo .ass y agregarle estilos o eventos)."""
    t = re.sub(r"[\x00-\x1f\x7f\u0085\u2028\u2029]", " ", t)
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def ass(p, estilo, ancho, alto):
    """El archivo .ass completo, con tiempos del video EXPORTADO (los cortes ya aplicados)."""
    sub = p["subtitulos"]
    tramos = proyecto.conservados(p)
    cortes = proyecto.unir(p["cortes"])
    visibles = []
    for w in p["palabras"]:
        if proyecto.palabra_cortada(p, w, cortes):
            continue
        i, f = proyecto.a_salida(p, w["i"], tramos), proyecto.a_salida(p, w["f"], tramos)
        if i is None:
            i = proyecto.a_salida(p, (w["i"] + w["f"]) / 2, tramos)
        if f is None or (i is not None and f <= i):
            f = (i or 0) + max(0.08, w["f"] - w["i"])
        if i is not None:
            visibles.append({"t": w["t"], "i": i, "f": f})
    escala = ancho / 1080
    tam = round(estilo["tamano"] / 100 * ancho)
    borde = estilo["borde"] * escala
    caja = estilo["fondo"]
    margen_v = round(alto * (1 - sub["posicion"]))
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Corta,{estilo['fuente']},{tam},{_color_ass(estilo['color'])},{_color_ass(estilo['color_activo'])},{_color_ass(estilo['color_borde'] if not caja else estilo['color_fondo'])},{_color_ass(estilo['color_borde'], 0x60)},0,0,0,0,100,100,0,0,{3 if caja else 1},{round(tam * 0.25) if caja else round(borde, 1)},{round(estilo['sombra'] * escala, 1)},2,{round(ancho * 0.08)},{round(ancho * 0.08)},{margen_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    if sub.get("activos", True):
        activo = _color_ass(estilo["color_activo"])
        for grupo in lineas(visibles, sub["palabras_por_linea"]):
            textos = [(w["t"].upper() if estilo["mayusculas"] else w["t"]) for w in grupo]
            fin_linea = grupo[-1]["f"]
            for k, w in enumerate(grupo):
                desde = w["i"] if k else grupo[0]["i"]
                hasta = grupo[k + 1]["i"] if k + 1 < len(grupo) else fin_linea
                if hasta - desde < 0.02:
                    continue
                partes = []
                for j, t in enumerate(textos):
                    t = _escapar(t)
                    if estilo["animacion"] == "ninguna":
                        partes.append(t)
                    elif j == k and estilo["animacion"] == "pop":
                        partes.append(r"{\c" + activo + r"\fscx112\fscy112}" + t + r"{\r}")
                    elif j == k and estilo["animacion"] == "subrayado":
                        partes.append(r"{\c" + activo + r"\u1}" + t + r"{\r}")
                    elif j == k:
                        partes.append(r"{\c" + activo + "}" + t + r"{\r}")
                    else:
                        partes.append(t)
                if estilo["animacion"] == "palabra":
                    partes = [r"{\c" + activo + r"\fscx112\fscy112}" + _escapar(textos[k])]
                eventos.append(f"Dialogue: 0,{_tiempo(desde)},{_tiempo(hasta)},Corta,,0,0,0,,{' '.join(partes)}")
    for t in p.get("textos", []):
        i, f = proyecto.a_salida(p, t["i"], tramos), proyecto.a_salida(p, t["f"], tramos)
        if i is None or f is None:
            continue
        y = round(alto * t.get("y", 0.18))
        eventos.append(f"Dialogue: 1,{_tiempo(i)},{_tiempo(f)},Corta,,0,0,0,,{{\\an8\\pos({ancho // 2},{y})}}{_escapar(t['texto'])}")
    return cab + "\n".join(eventos) + "\n"
