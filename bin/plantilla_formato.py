"""El formato de una plantilla de Corta y su validación. Solo biblioteca estándar y sin depender de nada más de Corta salvo
efecto_formato.py (que también es el mismo archivo en los dos repos).

Este archivo es el MISMO en la app (corta/bin/plantilla_formato.py) y en el catálogo de la comunidad
(corta-catalogo/herramientas/plantilla_formato.py): lo que el catálogo acepta es justo lo que la app acepta. Si lo cambias, cámbialo
en los dos repos (las pruebas de la app lo comparan si el catálogo está al lado).

Una plantilla es un video armado de antemano con **huecos** para tus clips o fotos: cuánto dura cada hueco, qué efecto lleva, con
qué transición pasa al siguiente y qué texto aparece encima. Es **solo datos**: nunca trae CSS, código, filtros de ffmpeg, audio
ni imágenes. Todo lo visual va **por referencia** a efectos (efectos/ de la app o del catálogo) y estilos de subtítulos (estilos/)
que ya pasaron su propia validación.

{
 "formato": 1,
 "id": "producto-en-15",                          minúsculas, números y guiones; el archivo se llama <id>.json
 "categoria": "negocios",                         ver CATEGORIAS
 "nombre": {"es": "Producto en 15 s", "en": "…"}, "es" obligatorio; otros idiomas opcionales (hasta 30 caracteres)
 "descripcion": {"es": "…"},                      opcional (hasta 140)
 "autor": "Corta", "etiquetas": ["venta"],        opcionales
 "proporcion": "9:16",                            9:16 | 1:1 | 4:5 | 16:9
 "huecos": [                                      de 1 a 20, en orden; entre todos, hasta 90 s
   {"dur": 2.5,                                   segundos (0,5 a 15)
    "tipo": "video",                              video | foto | cualquiera (qué conviene poner; si no hay, se usa lo que haya)
    "pista": {"es": "Tu producto de frente"},     opcional: qué poner en el hueco (hasta 40)
    "efectos": ["calido"],                        opcional: hasta 3 efectos que no sean transiciones, solo en este hueco
    "transicion": "destello",                     opcional: cómo pasa al hueco siguiente (un efecto con solo pasos de transición)
    "zoom": "acercar",                            opcional, solo si cae una foto: acercar (por defecto) | alejar | no
    "velocidad": {"v": 0.3, "rampa": true}}       opcional: cámara lenta o rápida en el hueco (ver VELOCIDAD); `dur` sigue
                                                  siendo lo que se toma del clip: en el video exportado dura dur / v
 ],
 "textos": [{"en_hueco": 0, "texto": {"es": "…"}, "posicion": 0.18}],   opcional, hasta 10: texto encima de un hueco
                                                  (hasta 60 caracteres; posicion = altura de 0,08 a 0,9)
 "subtitulos": {"estilo": "titular", "activos": true},   opcional: el estilo (subtítulos y textos se dibujan con él)
 "efectos": ["fundido-entrada"],                  opcional: hasta 3 efectos para todo el video
 "musica": {"bpm": 120}                           opcional: el ritmo para el que se pensaron los cortes (60 a 200); nunca un archivo
}
"""
import re

import efecto_formato as ef

FORMATO = 1
CATEGORIAS = ("negocios", "presentacion", "recuerdos", "tutorial", "celebracion")
PROPORCIONES = ("9:16", "1:1", "4:5", "16:9")
TIPOS = ("video", "foto", "cualquiera")
ZOOMS = ("acercar", "alejar", "no")
CLAVES = {"formato", "id", "categoria", "nombre", "descripcion", "autor", "etiquetas", "proporcion", "huecos", "textos",
          "subtitulos", "efectos", "musica"}
CLAVES_HUECO = {"dur", "tipo", "pista", "efectos", "transicion", "zoom", "velocidad"}
#: La velocidad de un hueco, con los mismos rangos que `velocidades` en proyecto.json (bin/proyecto.py):
#:   v          0,25 a 3 (1 = normal; menos es cámara lenta, más es rápida)
#:   rampa      true: pasa suave de 1× a v y vuelve (v hasta 0,75): «cámara lenta en el momento clave»
#:   audio      "tono" (la voz más lenta o rápida, con su tono) o "silencio" (bajo 0,5× se silencia sola)
#:   suavizar   solo en cámara lenta: "mezcla" (funde los cuadros, casi gratis) o "movimiento" (inventa cuadros; tarda más)
VELOCIDAD = {"v": (0.25, 3), "rampa_max": 0.75, "audio": ("tono", "silencio"), "suavizar": ("mezcla", "movimiento")}
CLAVES_TEXTO = {"en_hueco", "texto", "posicion"}
DUR = (0.5, 15)
MAX_HUECOS, MAX_TOTAL, MAX_TEXTOS, MAX_EFECTOS = 20, 90, 10, 3
ESTILO = re.compile(r"[a-z0-9-]{2,40}")

#: Lo que trae la app (corta/efectos y corta/estilos): una plantilla puede usarlo sin descargar nada. Cada efecto con su categoría
#: y los tipos de sus pasos. La prueba de la app revisa que esto sea igual a lo que de verdad incluye.
EFECTOS_INCLUIDOS = {
    "alejar": ("movimiento", ("zoom",)), "barrido": ("transicion", ("barrido",)), "blanco-y-negro": ("filtro", ("color",)),
    "calido": ("color", ("color", "tinte")), "contraste": ("color", ("color",)), "desenfoque": ("filtro", ("desenfoque",)),
    "deslizar-arriba": ("transicion", ("barrido",)), "destello": ("transicion", ("transicion",)),
    "destello-dorado": ("transicion", ("destello",)), "falla-leve": ("transicion", ("interferencia",)),
    "fogonazo": ("transicion", ("destello",)), "frio": ("color", ("color", "tinte")),
    "fundido-entrada": ("transicion", ("fundido",)), "fundido-salida": ("transicion", ("fundido",)),
    "interferencia": ("transicion", ("interferencia",)), "latido": ("transicion", ("rebote", "destello")),
    "latigazo": ("transicion", ("barrido",)), "luminoso": ("color", ("color",)), "noir": ("filtro", ("color", "vineta")),
    "persiana": ("transicion", ("franjas",)), "rebote": ("transicion", ("rebote",)),
    "transicion-negro": ("transicion", ("transicion",)), "tres-franjas": ("transicion", ("franjas",)),
    "vineta": ("filtro", ("vineta",)), "vintage": ("filtro", ("color", "vineta")), "vivido": ("filtro", ("color",)),
    "zoom-de-paso": ("transicion", ("zoom_paso",)), "zoom-golpe": ("movimiento", ("zoom",)),
    "zoom-lento": ("movimiento", ("zoom",)),
}
ESTILOS_INCLUIDOS = ("caja", "neon", "palabra", "pop", "suave", "titular")


def _numero(v):
    return ef._numero(v)


def _textos(v, largo):
    """{"es": "…", "en": "…"} con textos cortos sin HTML."""
    return (isinstance(v, dict) and "es" in v and len(v) <= 12
            and all(isinstance(k, str) and ef.IDIOMA.fullmatch(k) and ef._texto(x, largo) for k, x in v.items()))


def _ids(v, maximo):
    return isinstance(v, list) and len(v) <= maximo and len(set(map(str, v))) == len(v) and all(isinstance(x, str) and ef.ID.fullmatch(x) for x in v)


def velocidad_valida(x):
    if not (isinstance(x, dict) and set(x) <= {"v", "rampa", "audio", "suavizar"} and _numero(x.get("v"))):
        return False
    v = x["v"]
    lo, hi = VELOCIDAD["v"]
    return (lo <= v <= hi and ("rampa" not in x or (x["rampa"] is True and v <= VELOCIDAD["rampa_max"]))
            and (v != 1 or x.get("rampa") is True) and x.get("audio", "tono") in VELOCIDAD["audio"]
            and ("suavizar" not in x or (x["suavizar"] in VELOCIDAD["suavizar"] and v < 1)))


def duracion(d):
    """Lo que dura el video armado (la suma de los huecos)."""
    return round(sum(h["dur"] for h in d["huecos"]), 3)


def validar_plantilla(d, archivo=None):
    """Lista de problemas del formato (vacía = válida). Con `archivo`, revisa también que se llame <id>.json. Las referencias a
    efectos y estilos se revisan aparte (`referencias`), porque dependen de lo que hay en cada lugar."""
    if not isinstance(d, dict):
        return ["La plantilla no es un objeto JSON."]
    e = []
    if d.get("formato") != FORMATO:
        e.append(f"formato debe ser {FORMATO}.")
    if extra := set(d) - CLAVES:
        e.append("Campos desconocidos: " + ", ".join(sorted(map(str, extra))) + ".")
    if not (isinstance(d.get("id"), str) and ef.ID.fullmatch(d["id"])):
        e.append("id: minúsculas, números y guiones (2 a 40).")
    elif archivo is not None and archivo.replace("\\", "/").split("/")[-1] != d["id"] + ".json":
        e.append("El archivo debe llamarse <id>.json.")
    if d.get("categoria") not in CATEGORIAS:
        e.append("categoria: " + ", ".join(CATEGORIAS) + ".")
    for campo, largo, obligatorio in (("nombre", 30, True), ("descripcion", 140, False)):
        if (campo in d or obligatorio) and not _textos(d.get(campo), largo):
            e.append(f"{campo}: {{\"es\": \"…\", \"en\": \"…\"}}, textos de hasta {largo} caracteres sin HTML.")
    if "autor" in d and not ef._texto(d["autor"], 40):
        e.append("autor: texto corto sin HTML.")
    if "etiquetas" in d and not (isinstance(d["etiquetas"], list) and len(d["etiquetas"]) <= 8 and all(ef._texto(x, 24) for x in d["etiquetas"])):
        e.append("etiquetas: hasta 8 palabras cortas.")
    if d.get("proporcion") not in PROPORCIONES:
        e.append("proporcion: " + ", ".join(PROPORCIONES) + ".")
    huecos = d.get("huecos")
    if not isinstance(huecos, list) or not 1 <= len(huecos) <= MAX_HUECOS:
        e.append(f"huecos: lista de 1 a {MAX_HUECOS}.")
        huecos = []
    total = 0.0
    for k, h in enumerate(huecos):
        donde = f"huecos[{k}]"
        if not isinstance(h, dict):
            e.append(f"{donde}: debe ser un objeto.")
            continue
        if extra := set(h) - CLAVES_HUECO:
            e.append(f"{donde}: campos desconocidos: " + ", ".join(sorted(map(str, extra))) + ".")
        if not (_numero(h.get("dur")) and DUR[0] <= h["dur"] <= DUR[1]):
            e.append(f"{donde}.dur: segundos, de {DUR[0]} a {DUR[1]}.")
        else:
            total += h["dur"]
        if h.get("tipo") not in TIPOS:
            e.append(f"{donde}.tipo: " + ", ".join(TIPOS) + ".")
        if "pista" in h and not _textos(h["pista"], 40):
            e.append(f"{donde}.pista: {{\"es\": \"…\"}}, hasta 40 caracteres sin HTML.")
        if "efectos" in h and not _ids(h["efectos"], MAX_EFECTOS):
            e.append(f"{donde}.efectos: hasta {MAX_EFECTOS} ids de efectos distintos.")
        if "transicion" in h:
            if not (isinstance(h["transicion"], str) and ef.ID.fullmatch(h["transicion"])):
                e.append(f"{donde}.transicion: el id de un efecto de transición.")
            elif k == len(huecos) - 1:
                e.append(f"{donde}.transicion: el último hueco no pasa a otro.")
        if "zoom" in h and h["zoom"] not in ZOOMS:
            e.append(f"{donde}.zoom: " + ", ".join(ZOOMS) + ".")
        if "velocidad" in h and not velocidad_valida(h["velocidad"]):
            e.append(f"{donde}.velocidad: {{\"v\": 0.25 a 3, \"rampa\"?: true (v hasta 0.75), \"audio\"?: tono | silencio, "
                     "\"suavizar\"?: mezcla | movimiento (solo en cámara lenta)}.")
    if total > MAX_TOTAL + 1e-9:
        e.append(f"huecos: entre todos, hasta {MAX_TOTAL} s.")
    textos = d.get("textos", [])
    if not isinstance(textos, list) or len(textos) > MAX_TEXTOS:
        e.append(f"textos: lista de hasta {MAX_TEXTOS}.")
        textos = []
    for k, t in enumerate(textos):
        donde = f"textos[{k}]"
        if not isinstance(t, dict):
            e.append(f"{donde}: debe ser un objeto.")
            continue
        if extra := set(t) - CLAVES_TEXTO:
            e.append(f"{donde}: campos desconocidos: " + ", ".join(sorted(map(str, extra))) + ".")
        n = t.get("en_hueco")
        if not (isinstance(n, int) and not isinstance(n, bool) and 0 <= n < max(1, len(huecos))):
            e.append(f"{donde}.en_hueco: el número de un hueco (desde 0).")
        if not _textos(t.get("texto"), 60):
            e.append(f"{donde}.texto: {{\"es\": \"…\"}}, hasta 60 caracteres sin HTML.")
        if "posicion" in t and not (_numero(t["posicion"]) and 0.08 <= t["posicion"] <= 0.9):
            e.append(f"{donde}.posicion: altura de 0.08 a 0.9.")
    s = d.get("subtitulos")
    if s is not None and not (isinstance(s, dict) and set(s) <= {"estilo", "activos"} and isinstance(s.get("estilo"), str)
                              and ESTILO.fullmatch(s["estilo"]) and isinstance(s.get("activos", True), bool)):
        e.append("subtitulos: {\"estilo\": id de un estilo, \"activos\": true o false}.")
    if "efectos" in d and not _ids(d["efectos"], MAX_EFECTOS):
        e.append(f"efectos: hasta {MAX_EFECTOS} ids de efectos distintos.")
    m = d.get("musica")
    if m is not None and not (isinstance(m, dict) and set(m) == {"bpm"} and _numero(m["bpm"]) and 60 <= m["bpm"] <= 200):
        e.append("musica: {\"bpm\": 60 a 200} (solo el ritmo; nunca un archivo).")
    return e


def referencias(d, efectos, estilos):
    """Problemas de las referencias de una plantilla ya válida: `efectos` = {id: (categoria, (tipos de sus pasos…))} y `estilos` =
    ids. Una transición tiene que ser un efecto de categoría «transicion» con solo pasos que van en las uniones
    (efecto_formato.TRANSICIONES: pestañeo, interferencia, destello, franjas, rebote, barrido o zoom de paso); los efectos de un hueco
    no pueden ser transiciones."""
    e = []

    def efecto(i, donde, transicion=None):
        if i not in efectos:
            e.append(f"{donde}: no existe el efecto «{i}».")
            return
        categoria, tipos = efectos[i]
        if transicion is True and not (categoria == "transicion" and tipos and all(t in ef.TRANSICIONES for t in tipos)):
            e.append(f"{donde}: «{i}» no es una transición entre clips.")
        if transicion is False and categoria == "transicion":
            e.append(f"{donde}: «{i}» es una transición: va en «transicion».")

    for k, h in enumerate(d.get("huecos", [])):
        for i in h.get("efectos", []):
            efecto(i, f"huecos[{k}].efectos", False)
        if "transicion" in h:
            efecto(h["transicion"], f"huecos[{k}].transicion", True)
    for i in d.get("efectos", []):
        efecto(i, "efectos")
    estilo = (d.get("subtitulos") or {}).get("estilo")
    if estilo is not None and estilo not in estilos:
        e.append(f"subtitulos.estilo: no existe el estilo «{estilo}».")
    return e


def efectos_usados(d):
    """Todos los ids de efectos que usa la plantilla, sin repetir y en orden."""
    r = []
    for h in d.get("huecos", []):
        r += h.get("efectos", []) + ([h["transicion"]] if "transicion" in h else [])
    r += d.get("efectos", [])
    return list(dict.fromkeys(r))
