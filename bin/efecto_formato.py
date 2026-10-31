"""El formato de un efecto de Corta y su validación. Solo biblioteca estándar y sin depender de nada más de Corta.

Este archivo es el MISMO en la app (corta/bin/efecto_formato.py) y en el catálogo de la comunidad
(corta-catalogo/herramientas/efecto_formato.py): lo que el catálogo acepta es justo lo que la app acepta. Si lo cambias, cámbialo en
los dos repos (las pruebas de la app lo comparan si el catálogo está al lado).

Un efecto es un JSON de **solo datos**: nunca trae CSS, código ni texto de filtro de ffmpeg. Trae una lista de `pasos`, cada uno de
un tipo conocido y con números dentro de rangos conocidos. Con esos números la app arma la vista previa (CSS) y la exportación
(ffmpeg, con una lista blanca de filtros), para que lo que ves sea lo que exportas.

{
 "formato": 1,
 "id": "calido",                                   minúsculas, números y guiones; el archivo se llama <id>.json
 "categoria": "color",                             filtro | color | movimiento | transicion
 "nombre": {"es": "Cálido", "en": "Warm"},         "es" obligatorio; otros idiomas opcionales
 "descripcion": {"es": "…", "en": "…"},            opcional
 "autor": "Corta",                                 opcional (usuario de GitHub o nombre)
 "etiquetas": ["atardecer", "sunset"],             opcional, para buscar
 "pasos": [{"tipo": "color", "saturacion": 1.15}, {"tipo": "tinte", "color": "#FF8A2A", "fuerza": 0.1}]
}
"""
import math
import re

FORMATO = 1
CATEGORIAS = ("filtro", "color", "movimiento", "transicion")
CLAVES = {"formato", "id", "categoria", "nombre", "descripcion", "autor", "etiquetas", "pasos"}
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,38}[a-z0-9]")
IDIOMA = re.compile(r"[a-z]{2}")
HEX = re.compile(r"#[0-9a-fA-F]{6}")
#: Textos visibles: sin HTML, llaves, barras invertidas ni caracteres de control (la app igual los escapa).
RAROS = re.compile(r"[<>{}\\`\x00-\x1f\x7f  ]")
MAX_PASOS = 4

#: Cada tipo de paso: sus campos con (mínimo, máximo) para números, o la lista de valores posibles.
#   color       igual que los filtros de CSS, en este orden: brightness, contrast, saturate, hue-rotate (grados), sepia, grayscale
#   tinte       una capa de color encima, con esa opacidad (mezcla normal)
#   desenfoque  desenfoque gaussiano; radio en px para un video de 1080 de ancho
#   vineta      bordes más oscuros
#   zoom        de «desde» a «hasta» durante el tramo: lineal, suave (acelera y frena) o golpe (llega en 0,15 s y se queda)
#   fundido     desde/hacia un color al empezar (entrada) y al terminar (salida) el tramo, en segundos
#   transicion  un pestañeo a un color en cada corte dentro del tramo, de esa duración en segundos
# Transiciones en cada corte o división del tramo (centradas en la unión, de `duracion` segundos):
#   interferencia  la imagen se descompone: canales de color corridos y franjas que saltan de lado (glitch)
#   destello       un destello de color (`intensidad` = opacidad máxima) que además sube la exposición
#   franjas        la imagen se parte en 2 o 3 franjas que salen en sentidos opuestos y entran ya con el clip siguiente
#   rebote         la escala crece hasta el corte y rebota al volver
#   barrido        la imagen se desliza (con su estela de movimiento si `desenfoque` > 0) y entra el clip siguiente
#   zoom_paso      un acercamiento rápido que cruza el corte y se abre ya en el clip siguiente
TIPOS = {
    "color": {"brillo": (0.5, 1.5), "contraste": (0.5, 2), "saturacion": (0, 2), "tono": (-180, 180), "sepia": (0, 1), "grises": (0, 1)},
    "tinte": {"color": "hex", "fuerza": (0.02, 0.5)},
    "desenfoque": {"radio": (0.5, 20)},
    "vineta": {"fuerza": (0.1, 1)},
    "zoom": {"desde": (1, 1.6), "hasta": (1, 1.6), "curva": ("lineal", "suave", "golpe")},
    "fundido": {"entrada": (0, 3), "salida": (0, 3), "color": ("negro", "blanco")},
    "transicion": {"duracion": (0.1, 1.5), "color": ("negro", "blanco")},
    "interferencia": {"duracion": (0.1, 1), "intensidad": (0.1, 1)},
    "destello": {"duracion": (0.1, 1), "color": "hex", "intensidad": (0.1, 1), "exposicion": (0, 1)},
    "franjas": {"duracion": (0.1, 1), "franjas": (2, 3), "direccion": ("vertical", "horizontal")},
    "rebote": {"duracion": (0.1, 1), "intensidad": (0.1, 1)},
    "barrido": {"duracion": (0.1, 1), "direccion": ("izquierda", "derecha", "arriba", "abajo"), "desenfoque": (0, 1)},
    "zoom_paso": {"duracion": (0.1, 1), "intensidad": (0.1, 1), "desenfoque": (0, 1)},
}
#: Los pasos que van en las uniones (cortes y divisiones): una plantilla solo acepta estos como «transicion» entre huecos.
TRANSICIONES = ("transicion", "interferencia", "destello", "franjas", "rebote", "barrido", "zoom_paso")
#: Campos que son números enteros.
ENTEROS = {"franjas"}
#: Campos que cada tipo necesita (los demás son opcionales).
OBLIGATORIOS = {"tinte": {"color", "fuerza"}, "desenfoque": {"radio"}, "vineta": {"fuerza"}, "zoom": {"desde", "hasta"},
                "transicion": {"duracion"}, **{t: {"duracion"} for t in TRANSICIONES[1:]}}


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _texto(v, largo):
    return isinstance(v, str) and 0 < len(v.strip()) <= largo and not RAROS.search(v)


def validar_pasos(pasos):
    """Lista de problemas de una lista de pasos (vacía = válida)."""
    if not isinstance(pasos, list) or not 1 <= len(pasos) <= MAX_PASOS:
        return [f"pasos: lista de 1 a {MAX_PASOS}."]
    e = []
    for k, paso in enumerate(pasos):
        donde = f"pasos[{k}]"
        if not isinstance(paso, dict) or paso.get("tipo") not in TIPOS:
            e.append(f"{donde}: tipo debe ser " + ", ".join(TIPOS) + ".")
            continue
        campos = TIPOS[paso["tipo"]]
        if extra := set(paso) - set(campos) - {"tipo"}:
            e.append(f"{donde}: campos desconocidos: " + ", ".join(sorted(map(str, extra))) + ".")
        if falta := OBLIGATORIOS.get(paso["tipo"], set()) - set(paso):
            e.append(f"{donde}: falta " + ", ".join(sorted(falta)) + ".")
        if len(paso) == 1:
            e.append(f"{donde}: no cambia nada.")
        for campo, regla in campos.items():
            if campo not in paso:
                continue
            v = paso[campo]
            if regla == "hex":
                ok = isinstance(v, str) and HEX.fullmatch(v)
            elif isinstance(regla[0], str):
                ok = v in regla
            else:
                ok = _numero(v) and regla[0] <= v <= regla[1] and (campo not in ENTEROS or v == int(v))
            if not ok:
                e.append(f"{donde}.{campo}: " + ("color #RRGGBB" if regla == "hex" else " o ".join(regla) if isinstance(regla[0], str)
                                                 else f"{'entero' if campo in ENTEROS else 'número'} de {regla[0]} a {regla[1]}") + ".")
        if paso["tipo"] == "fundido" and not (paso.get("entrada", 0) or paso.get("salida", 0)):
            e.append(f"{donde}: entrada o salida mayor que 0.")
    return e


def validar_efecto(d, archivo=None):
    """Lista de problemas de un efecto (vacía = válido). Con `archivo`, revisa también que se llame <id>.json."""
    if not isinstance(d, dict):
        return ["El efecto no es un objeto JSON."]
    e = []
    if d.get("formato") != FORMATO:
        e.append(f"formato debe ser {FORMATO}.")
    if extra := set(d) - CLAVES:
        e.append("Campos desconocidos: " + ", ".join(sorted(map(str, extra))) + ".")
    if not (isinstance(d.get("id"), str) and ID.fullmatch(d["id"])):
        e.append("id: minúsculas, números y guiones (2 a 40).")
    elif archivo is not None and archivo.replace("\\", "/").split("/")[-1] != d["id"] + ".json":
        e.append("El archivo debe llamarse <id>.json.")
    if d.get("categoria") not in CATEGORIAS:
        e.append("categoria: " + ", ".join(CATEGORIAS) + ".")
    for campo, largo, obligatorio in (("nombre", 30, True), ("descripcion", 140, False)):
        v = d.get(campo)
        if v is None and not obligatorio:
            continue
        if not (isinstance(v, dict) and "es" in v and len(v) <= 12 and all(isinstance(k, str) and IDIOMA.fullmatch(k) and _texto(x, largo) for k, x in v.items())):
            e.append(f"{campo}: {{\"es\": \"…\", \"en\": \"…\"}}, textos de hasta {largo} caracteres sin HTML.")
    if "autor" in d and not _texto(d["autor"], 40):
        e.append("autor: texto corto sin HTML.")
    if "etiquetas" in d and not (isinstance(d["etiquetas"], list) and len(d["etiquetas"]) <= 8 and all(_texto(x, 24) for x in d["etiquetas"])):
        e.append("etiquetas: hasta 8 palabras cortas.")
    e += validar_pasos(d.get("pasos"))
    return e


# Para la pieza «catálogo» (bin/catalogo.py de la app): validar(obj) -> [problemas] y los campos que se guardan.
validar = validar_efecto
CAMPOS = CLAVES
