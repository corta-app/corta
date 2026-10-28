"""Plantillas: un video armado de antemano con huecos para tus clips o fotos (formato en bin/plantilla_formato.py y plantillas/README.md).

  plantillas.py indice <indice.json> <salida.json>     valida el índice del catálogo que bajó la app → {"ok", "plantillas": [...]}
  plantillas.py entrada <entrada.json> <salida.json>   lo que pide la app (en un archivo, nunca como argumento):
      {"accion": "crear", "plantilla": id, "archivos": [rutas], "idioma"}   copia los clips a <carpeta>/clips/, llena los huecos en
                                                       orden (`llenar`), arma el video y crea el proyecto → {"ok", "carpeta", "proyecto", "faltan"}
      {"accion": "ajustar", "carpeta", "hueco", "desde"}    desde qué segundo del clip se usa en ese hueco (vuelve a armar)
      {"accion": "cambiar", "carpeta", "hueco", "archivo"}  otro clip o foto para ese hueco (vuelve a armar)
      {"accion": "instalar", "archivo", "id", "sha256"}     valida una plantilla que bajó la app y la deja en ~/Corta/.corta/plantillas/

Dónde están: incluidas en la app (`plantillas/<categoria>/<id>.json`) y descargadas del catálogo (`~/Corta/.corta/plantillas/`,
ganan sobre las incluidas con el mismo id).

Cómo se arma: los huecos van uno detrás de otro en un solo video («plantilla-N.mp4», el `fuente` del proyecto), del tamaño del
lienzo. Lo demás es un proyecto normal y editable: textos, efectos de cada hueco (con sus pasos copiados), transiciones en la unión
de dos huecos (una división en `divisiones` + un efecto de pasos «transicion» alrededor; ver `efectos.uniones`), estilo de los
subtítulos y efectos de todo el video. `plantilla` en el proyecto recuerda qué clip va en cada hueco y desde qué segundo, para
cambiarlo después sin perder lo demás. Las mismas reglas (`llenar`, `aplicar`) existen en ui/app.js (casos «plantillas» en
pruebas/casos.json).

Lista blanca de filtros para armar (solo estos, con números que salen del código; ningún texto de la plantilla llega a ffmpeg):
  trim, setpts, tpad, fps, scale, crop, setsar, format, atrim, asetpts, aresample, aformat, apad, anullsrc, concat
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import efectos  # noqa: E402
import importar  # noqa: E402
import plantilla_formato  # noqa: E402
import proyecto  # noqa: E402
import subtitulos  # noqa: E402

DESCARGADAS = os.path.join(proyecto.INTERNO, "plantillas")
MAX_BYTES = 64 * 1024
ARCHIVO_CATALOGO = re.compile(r"plantillas/([a-z]+)/([a-z0-9][a-z0-9-]{0,38}[a-z0-9])\.json")
VIDEOS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
FOTOS = (".jpg", ".jpeg", ".png", ".webp")
#: Zoom de una foto: qué efecto incluido la mueve.
ZOOM_FOTO = {"acercar": "zoom-lento", "alejar": "alejar"}
FPS = 30


def incluidas_dir():
    return os.path.join(proyecto.RECURSOS, "plantillas")


def _leer(ruta):
    try:
        if os.path.getsize(ruta) > MAX_BYTES:
            return None
    except OSError:
        return None
    d = proyecto.leer_json(ruta, None)
    return d if d is not None and not plantilla_formato.validar_plantilla(d, ruta) else None


def disponibles():
    """Todas las plantillas válidas, por id: las incluidas y las descargadas (estas ganan). Cada una con `origen`."""
    todas = {}
    base = incluidas_dir()
    for categoria in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        carpeta = os.path.join(base, categoria)
        if not os.path.isdir(carpeta):
            continue
        for n in sorted(os.listdir(carpeta)):
            if n.endswith(".json"):
                d = _leer(os.path.join(carpeta, n))
                if d and d["categoria"] == categoria:
                    todas[d["id"]] = {**d, "origen": "incluida"}
    for n in sorted(os.listdir(DESCARGADAS)) if os.path.isdir(DESCARGADAS) else []:
        if n.endswith(".json"):
            d = _leer(os.path.join(DESCARGADAS, n))
            if d:
                todas[d["id"]] = {**d, "origen": "descargada"}
    return todas


def tipos_de_efectos(todos):
    """{id: (categoria, (tipos de sus pasos…))} de los efectos que hay, para revisar las referencias de una plantilla."""
    return {i: (e["categoria"], tuple(p["tipo"] for p in e["pasos"])) for i, e in todos.items()}


# ───────────── Llenar y aplicar (la misma lógica que ui/app.js; casos «plantillas» en pruebas/casos.json) ─────────────
def _r3(n):
    return math.floor(n * 1000 + 0.5) / 1000


def inicios(huecos):
    """Dónde empieza cada hueco en el video armado, y al final lo que dura todo."""
    r, t = [0.0], 0.0
    for h in huecos:
        t = _r3(t + h["dur"])
        r.append(t)
    return r


def llenar(huecos, clips):
    """Qué clip va en cada hueco y desde qué segundo. `clips` = [{tipo: "video" | "foto", duracion}] en el orden en que la persona
    los eligió. Cada hueco toma el primer clip sin usar que le calza (video, foto o cualquiera); si no hay, el primero sin usar; si
    ya se usaron todos, se empieza otra vuelta. Un video que se usa en m huecos se parte en m pedazos iguales y cada hueco toma el
    centro del suyo (así no se repite la misma parte); una foto no tiene «desde». → [{clip, desde}]"""
    n = len(clips)
    if not n:
        return []
    usados, asignados = [False] * n, []
    for h in huecos:
        if all(usados):
            usados = [False] * n
        libres = [c for c in range(n) if not usados[c]]
        calzan = [c for c in libres if h["tipo"] == "cualquiera" or clips[c]["tipo"] == h["tipo"]]
        c = (calzan or libres)[0]
        usados[c] = True
        asignados.append(c)
    usos = [asignados.count(c) for c in range(n)]
    vez = [0] * n
    r = []
    for h, c in zip(huecos, asignados):
        clip = clips[c]
        if clip["tipo"] == "foto":
            r.append({"clip": c, "desde": 0})
            continue
        centro = clip["duracion"] * (vez[c] + 0.5) / usos[c]
        vez[c] += 1
        r.append({"clip": c, "desde": _r3(max(0.0, min(centro - h["dur"] / 2, clip["duracion"] - h["dur"])))})
    return r


def aplicar(plantilla, tipos, idioma, efectos_disp, estilos):
    """Lo que la plantilla pone en el proyecto, ya en el tiempo del video armado. `tipos` = "video" | "foto" de lo que cayó en cada
    hueco; `efectos_disp` = {id: pasos} de los efectos que hay; `estilos` = ids. Una foto se mueve sola (zoom lento, salvo
    `zoom: "no"` o si el hueco ya trae un efecto con zoom). Un efecto que no está queda en `faltan` (la app ofrece descargarlo).
    → {lienzo, divisiones, textos, efectos, subtitulos (o None), faltan}"""
    huecos = plantilla["huecos"]
    ini = inicios(huecos)
    faltan, lista = [], []

    def poner(i, desde=None, hasta=None):
        if i not in efectos_disp:
            if i not in faltan:
                faltan.append(i)
            return
        x = {"efecto": i, "pasos": json.loads(json.dumps(efectos_disp[i]))}
        if desde is not None:
            x.update(i=desde, f=hasta)
        lista.append(x)

    for k, h in enumerate(huecos):
        for i in h.get("efectos", []):
            poner(i, ini[k], ini[k + 1])
        con_zoom = any(p["tipo"] == "zoom" for i in h.get("efectos", []) for p in efectos_disp.get(i, []))
        if tipos[k] == "foto" and h.get("zoom", "acercar") != "no" and not con_zoom:
            poner(ZOOM_FOTO[h.get("zoom", "acercar")], ini[k], ini[k + 1])
        if "transicion" in h and k + 1 < len(huecos):
            medio = _r3(min(0.5, h["dur"] / 2, huecos[k + 1]["dur"] / 2))
            poner(h["transicion"], _r3(ini[k + 1] - medio), _r3(ini[k + 1] + medio))
    for i in plantilla.get("efectos", []):
        poner(i)
    textos = [{"i": ini[t["en_hueco"]], "f": ini[t["en_hueco"] + 1], "texto": t["texto"].get(idioma) or t["texto"]["es"],
               "y": t.get("posicion", 0.18)} for t in plantilla.get("textos", [])]
    s = plantilla.get("subtitulos")
    sub = {"estilo": s["estilo"], "activos": s.get("activos", True)} if s and s["estilo"] in estilos else None
    return {"lienzo": plantilla["proporcion"], "divisiones": ini[1:-1], "textos": textos, "efectos": lista[:40], "subtitulos": sub,
            "faltan": faltan}


# ───────────── Armar el video ─────────────
def _probar_archivo(ruta):
    """{tipo, duracion, ancho, alto} de un clip o una foto (ffprobe, solo archivos locales)."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in FOTOS:
        r = subprocess.run([proyecto.programa("ffprobe"), *proyecto.SOLO_ARCHIVOS, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "json", proyecto.entrada(ruta)], capture_output=True, text=True)
        s = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
        if not (s.get("width") and s.get("height")):
            raise ValueError("No pude leer esa foto.")
        return {"tipo": "foto", "duracion": None, "ancho": int(s["width"]), "alto": int(s["height"])}
    if ext in VIDEOS:
        return {"tipo": "video", "audio": _tiene_audio(ruta), **importar.info(ruta)}
    raise ValueError("Elige videos (MP4, MOV, WebM) o fotos (JPG, PNG, WebP).")


def _tiene_audio(ruta):
    r = subprocess.run([proyecto.programa("ffprobe"), *proyecto.SOLO_ARCHIVOS, "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", proyecto.entrada(ruta)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def _n(x):
    return efectos._n(x)


def grafo(huecos, ancho, alto):
    """El grafo de ffmpeg que pone los huecos uno detrás de otro, cada uno cubriendo el lienzo (escalar y recortar al centro).
    `huecos` = [{tipo, desde, dur, audio}] con una entrada de ffmpeg por hueco, en el mismo orden."""
    partes, etiquetas = [], []
    cubrir = f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto},setsar=1"
    for k, h in enumerate(huecos):
        dur = _n(h["dur"])
        if h["tipo"] == "foto":
            partes.append(f"[{k}:v]{cubrir},fps={FPS},format=yuv420p,trim=duration={dur},setpts=PTS-STARTPTS[v{k}]")
        else:
            # Si el clip es más corto que el hueco, el último cuadro se queda (tpad) hasta completar.
            partes.append(f"[{k}:v]trim=start={_n(h['desde'])},setpts=PTS-STARTPTS,fps={FPS},{cubrir},format=yuv420p,"
                          f"tpad=stop_mode=clone:stop_duration={dur},trim=duration={dur},setpts=PTS-STARTPTS[v{k}]")
        if h.get("audio"):
            partes.append(f"[{k}:a]atrim=start={_n(h['desde'])},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
                          f"apad=whole_dur={dur},atrim=duration={dur}[a{k}]")
        else:
            partes.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={dur}[a{k}]")
        etiquetas.append(f"[v{k}][a{k}]")
    partes.append("".join(etiquetas) + f"concat=n={len(huecos)}:v=1:a=1[v][a]")
    return ";".join(partes)


def armar_video(carpeta, huecos, lienzo, salida):
    """Arma el video de los huecos (rutas dentro de la carpeta) en `salida`. El avance queda en <carpeta>/estado.json."""
    ancho, alto = proyecto.LIENZOS[lienzo]
    cmd = [proyecto.programa("ffmpeg"), "-hide_banner", "-y", "-nostats"]
    for h in huecos:
        ruta = os.path.join(carpeta, h["archivo"])
        if h["tipo"] == "foto":
            cmd += [*proyecto.SOLO_ARCHIVOS, "-loop", "1", "-framerate", str(FPS), "-t", _n(h["dur"] + 0.5), "-i", proyecto.entrada(ruta)]
        else:
            cmd += [*proyecto.SOLO_ARCHIVOS, "-i", proyecto.entrada(ruta)]
    total = sum(h["dur"] for h in huecos)
    temporal = salida + ".tmp.mp4"
    datos = [{**h, "audio": h["tipo"] == "video" and _tiene_audio(os.path.join(carpeta, h["archivo"]))} for h in huecos]
    cmd += ["-filter_complex", grafo(datos, ancho, alto), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            "-progress", "pipe:1", temporal]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for linea in proc.stdout:
        m = re.match(r"out_time_us=(\d+)", linea)
        if m and total:
            proyecto.escribir_json(os.path.join(carpeta, "estado.json"),
                                   {"paso": "armando", "texto": "Armando tu video…", "pct": min(99, int(int(m.group(1)) / 1e6 / total * 100))})
    error = proc.stderr.read()
    if proc.wait() != 0 or not os.path.exists(temporal):
        raise RuntimeError("ffmpeg no pudo armar el video: " + (error.strip().splitlines()[-1][:300] if error.strip() else "falló."))
    os.replace(temporal, salida)
    try:
        os.remove(os.path.join(carpeta, "estado.json"))
    except OSError:
        pass


def _siguiente_nombre(carpeta):
    n = 1
    while os.path.exists(os.path.join(carpeta, f"plantilla-{n}.mp4")):
        n += 1
    return f"plantilla-{n}.mp4"


def _rearmar(carpeta, p):
    """Vuelve a armar el video con `plantilla.huecos` y lo deja como `fuente` (el anterior se borra)."""
    nombre = _siguiente_nombre(carpeta)
    armar_video(carpeta, p["plantilla"]["huecos"], p["lienzo"], os.path.join(carpeta, nombre))
    viejo = p["fuente"]["archivo"]
    p["fuente"] = {**p["fuente"], "archivo": nombre}
    proyecto.guardar(carpeta, p)
    if viejo != nombre and re.fullmatch(r"plantilla-\d+\.mp4", viejo):
        try:
            os.remove(os.path.join(carpeta, viejo))
        except OSError:
            pass


def crear(d):
    todas = disponibles()
    pl = todas.get(d.get("plantilla"))
    if not pl:
        raise ValueError("No encontré esa plantilla.")
    archivos = d.get("archivos")
    if not isinstance(archivos, list) or not archivos or not all(isinstance(a, str) and os.path.isabs(a) and os.path.isfile(a) for a in archivos):
        raise ValueError("Elige tus clips o fotos.")
    archivos = archivos[:len(pl["huecos"])]
    clips = [_probar_archivo(a) for a in archivos]
    idioma = d.get("idioma") if d.get("idioma") in ("es", "en") else "es"
    titulo = pl["nombre"].get(idioma) or pl["nombre"]["es"]
    carpeta = importar.nombre_carpeta(titulo)
    os.makedirs(os.path.join(carpeta, "clips"))
    try:
        nombres = []
        for k, ruta in enumerate(archivos):
            nombre = f"clips/{k + 1:02d}{os.path.splitext(ruta)[1].lower()}"
            shutil.copy2(ruta, os.path.join(carpeta, nombre))
            nombres.append(nombre)
        lugar = llenar(pl["huecos"], clips)
        huecos = [{"archivo": nombres[x["clip"]], "tipo": clips[x["clip"]]["tipo"], "desde": x["desde"], "dur": h["dur"],
                   "duracion": clips[x["clip"]]["duracion"]} for h, x in zip(pl["huecos"], lugar)]
        nombre = _siguiente_nombre(carpeta)
        armar_video(carpeta, huecos, pl["proporcion"], os.path.join(carpeta, nombre))
        ancho, alto = proyecto.LIENZOS[pl["proporcion"]]
        p = proyecto.nuevo(titulo, {"archivo": nombre, "duracion": inicios(pl["huecos"])[-1], "ancho": ancho, "alto": alto})
        disp = efectos.disponibles()
        ap = aplicar(pl, [h["tipo"] for h in huecos], idioma, {i: e["pasos"] for i, e in disp.items()}, set(subtitulos.estilos()))
        p.update(lienzo=ap["lienzo"], divisiones=ap["divisiones"], textos=ap["textos"], efectos=ap["efectos"])
        if ap["subtitulos"]:
            p["subtitulos"].update(ap["subtitulos"])
        p["plantilla"] = {"id": pl["id"], "huecos": huecos}
        proyecto.guardar(carpeta, p, respaldo=False)
    except BaseException:
        shutil.rmtree(carpeta, ignore_errors=True)
        raise
    return {"ok": True, "carpeta": carpeta, "proyecto": p, "faltan": ap["faltan"], "usados": len(archivos)}


def _hueco(d):
    carpeta = proyecto.carpeta_valida(d.get("carpeta"))
    p = proyecto.cargar(carpeta)
    k = d.get("hueco")
    huecos = (p.get("plantilla") or {}).get("huecos") or []
    if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k < len(huecos):
        raise ValueError("Ese hueco no existe.")
    return carpeta, p, k


def _quitar_palabras(p, k):
    """Las palabras transcritas del hueco k ya no corresponden al clip nuevo: se quitan (lo demás se conserva)."""
    ini = inicios(p["plantilla"]["huecos"])
    p["palabras"] = [w for w in p["palabras"] if not ini[k] <= (w["i"] + w["f"]) / 2 < ini[k + 1]]


def ajustar(d):
    carpeta, p, k = _hueco(d)
    h = p["plantilla"]["huecos"][k]
    desde = d.get("desde")
    if h["tipo"] != "video" or not isinstance(desde, (int, float)) or isinstance(desde, bool) or not math.isfinite(desde):
        raise ValueError("Ese hueco no se puede mover.")
    h["desde"] = _r3(max(0.0, min(desde, (h["duracion"] or 0) - h["dur"])))
    _quitar_palabras(p, k)
    _rearmar(carpeta, p)
    return {"ok": True, "carpeta": carpeta, "proyecto": p}


def cambiar(d):
    carpeta, p, k = _hueco(d)
    a = d.get("archivo")
    if not (isinstance(a, str) and os.path.isabs(a) and os.path.isfile(a)):
        raise ValueError("Elige un clip o una foto.")
    clip = _probar_archivo(a)
    huecos = p["plantilla"]["huecos"]
    viejo = huecos[k]["archivo"]
    n = 2
    while os.path.exists(os.path.join(carpeta, f"clips/{k + 1:02d}-{n}{os.path.splitext(a)[1].lower()}")):
        n += 1
    nombre = f"clips/{k + 1:02d}-{n}{os.path.splitext(a)[1].lower()}"
    shutil.copy2(a, os.path.join(carpeta, nombre))
    lugar = llenar([{"dur": huecos[k]["dur"], "tipo": "cualquiera"}], [clip])[0]
    huecos[k] = {"archivo": nombre, "tipo": clip["tipo"], "desde": lugar["desde"], "dur": huecos[k]["dur"], "duracion": clip["duracion"]}
    _quitar_palabras(p, k)
    try:
        _rearmar(carpeta, p)
    except BaseException:
        os.remove(os.path.join(carpeta, nombre))
        raise
    if all(h["archivo"] != viejo for h in huecos):
        try:
            os.remove(os.path.join(carpeta, viejo))
        except OSError:
            pass
    return {"ok": True, "carpeta": carpeta, "proyecto": p}


# ───────────── Catálogo (lo descarga la app; aquí solo se valida) ─────────────
def validar_indice(d):
    """Del índice del catálogo, solo las entradas válidas: {…plantilla, archivo, sha256, bytes}. Lo demás se descarta."""
    lista = d.get("plantillas") if isinstance(d, dict) else None
    r, vistos = [], set()
    for x in lista if isinstance(lista, list) else []:
        if not isinstance(x, dict):
            continue
        pl = {k: v for k, v in x.items() if k in plantilla_formato.CLAVES}
        m = ARCHIVO_CATALOGO.fullmatch(str(x.get("archivo", "")))
        if (plantilla_formato.validar_plantilla(pl) or not m or m.group(1) != pl["categoria"] or m.group(2) != pl["id"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(x.get("sha256", ""))) or not isinstance(x.get("bytes"), int)
                or not 0 < x["bytes"] <= MAX_BYTES or pl["id"] in vistos):
            continue
        vistos.add(pl["id"])
        r.append({**pl, "archivo": x["archivo"], "sha256": x["sha256"], "bytes": x["bytes"]})
    return r[:500]


def instalar(d):
    """Una plantilla que bajó la app: se valida otra vez (huella, id y formato) antes de guardarla."""
    if not isinstance(d, dict) or not isinstance(d.get("archivo"), str) or not isinstance(d.get("id"), str):
        raise ValueError("No pude leer la plantilla.")
    with open(d["archivo"], "rb") as f:
        crudo = f.read(MAX_BYTES + 1)
    if len(crudo) > MAX_BYTES or (d.get("sha256") and hashlib.sha256(crudo).hexdigest() != d["sha256"]):
        raise ValueError("La plantilla llegó dañada. Intenta de nuevo.")
    try:
        pl = json.loads(crudo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("Esa plantilla no es válida.") from None
    if plantilla_formato.validar_plantilla(pl) or pl["id"] != d["id"]:
        raise ValueError("Esa plantilla no es válida.")
    proyecto.escribir_json(os.path.join(DESCARGADAS, pl["id"] + ".json"), pl)
    return {"ok": True, "plantilla": {**pl, "origen": "descargada"}}


ACCIONES = {"crear": crear, "ajustar": ajustar, "cambiar": cambiar, "instalar": instalar}

if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) == 3 and a[0] == "indice":
            r = {"ok": True, "plantillas": validar_indice(proyecto.leer_json(a[1], None))}
        elif len(a) == 3 and a[0] == "entrada":
            datos = proyecto.leer_json(a[1], None)
            if not isinstance(datos, dict) or datos.get("accion") not in ACCIONES:
                raise ValueError("No sé hacer eso.")
            r = ACCIONES[datos["accion"]](datos)
        else:
            print(__doc__)
            sys.exit(2)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.CalledProcessError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(a[-1], r)
    print(json.dumps({k: v for k, v in r.items() if k != "proyecto"}, ensure_ascii=False))
