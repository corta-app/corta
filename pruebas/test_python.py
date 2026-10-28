"""Pruebas del motor en Python. Nunca tocan datos reales ni llaman a una IA de verdad: usan una carpeta temporal (CORTA_CARPETA)
y una IA falsa en el PATH (pruebas/ia_falsa.py, instalada como «claude»). Exportar usa ffmpeg de verdad con un video ficticio corto.

Uso: python3 pruebas/test_python.py
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "pruebas", "datos")
TMP = tempfile.mkdtemp(prefix="corta-pruebas-")
os.environ["CORTA_CARPETA"] = os.path.join(TMP, "Corta")
BIN_FALSO = os.path.join(TMP, "bin")
os.makedirs(BIN_FALSO)
destino = os.path.join(BIN_FALSO, "claude")
shutil.copy(os.path.join(RAIZ, "pruebas", "ia_falsa.py"), destino)
os.chmod(destino, os.stat(destino).st_mode | stat.S_IEXEC)
destino = os.path.join(BIN_FALSO, "corta-transcribir")
shutil.copy(os.path.join(RAIZ, "pruebas", "transcriptor_falso.py"), destino)
os.chmod(destino, os.stat(destino).st_mode | stat.S_IEXEC)
os.environ["PATH"] = BIN_FALSO + os.pathsep + os.environ["PATH"]
sys.path.insert(0, os.path.join(RAIZ, "bin"))

import editar_ia  # noqa: E402
import efecto_formato  # noqa: E402
import efectos  # noqa: E402
import importar  # noqa: E402
import limpiar  # noqa: E402
import proyecto  # noqa: E402
import subtitulos  # noqa: E402
import vocabulario  # noqa: E402

with open(os.path.join(RAIZ, "pruebas", "casos.json"), encoding="utf-8") as f:
    CASOS = json.load(f)
PALABRAS = CASOS["palabras"]
VIDEO = os.path.join(DATOS, "ana-corto.mp4")


def correr(script, *args):
    salida = os.path.join(TMP, "salida.json")
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", script), *args, salida], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with open(salida, encoding="utf-8") as f:
        return json.load(f)


def proyecto_de_prueba():
    """Importa el video ficticio y le pone las palabras (como si whisper ya hubiera transcrito)."""
    r = correr("importar.py", VIDEO)
    assert r["ok"], r
    p = proyecto.cargar(r["carpeta"])
    p["palabras"] = json.loads(json.dumps(PALABRAS))
    proyecto.guardar(r["carpeta"], p)
    return r["carpeta"]


class Proyecto(unittest.TestCase):
    def test_conservados(self):
        for c in CASOS["conservados"]:
            p = {"fuente": {"duracion": c["duracion"]}, "cortes": c["cortes"]}
            self.assertEqual(proyecto.conservados(p), c["esperado"])

    def test_a_salida(self):
        for c in CASOS["a_salida"]:
            p = {"fuente": {"duracion": c["duracion"]}, "cortes": c["cortes"]}
            self.assertEqual(proyecto.a_salida(p, c["t"]), c["esperado"])

    def test_cortar_y_restaurar(self):
        for c in CASOS["cortar"]:
            p = {"fuente": {"duracion": CASOS["duracion"]}, "palabras": PALABRAS, "cortes": []}
            proyecto.cortar_palabras(p, c["desde"], c["hasta"])
            self.assertEqual(p["cortes"], c["esperado"])
        r = CASOS["restaurar"]
        p = {"cortes": json.loads(json.dumps(r["cortes"]))}
        proyecto.restaurar(p, r["i"], r["f"])
        self.assertEqual(p["cortes"], r["esperado"])

    def test_validar(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 10, "ancho": 1920, "alto": 1080})
        self.assertEqual(proyecto.validar(p), [])
        malo = {**p, "lienzo": "3:2", "cortes": [{"i": 5, "f": 2, "motivo": "manual"}], "zooms": [{"i": 1, "f": 2, "escala": 5}]}
        texto = " ".join(proyecto.validar(malo))
        for parte in ("lienzo", "al revés", "escala"):
            self.assertIn(parte, texto)
        # El video es un archivo dentro de la carpeta: nada de rutas a otra parte ni nombres que ffmpeg lea como opción.
        for archivo in ("../../secreto.mp4", "/etc/passwd", "carpeta/a.mp4", "C:\\a.mp4", "-i.mp4", "..", "", None):
            self.assertTrue(proyecto.validar({**p, "fuente": {**p["fuente"], "archivo": archivo}}), archivo)
        self.assertEqual(proyecto.validar({**p, "fuente": {**p["fuente"], "archivo": "original.mov"}}), [])
        self.assertTrue(proyecto.validar({**p, "musica": {"archivo": "musica/a.mp3", "volumen": "alto"}}))

    def test_deshacer(self):
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        p["lienzo"] = "1:1"
        proyecto.guardar(carpeta, p)
        self.assertTrue(proyecto.deshacer(carpeta))
        self.assertEqual(proyecto.cargar(carpeta)["lienzo"], "9:16")


class Limpiar(unittest.TestCase):
    def test_casos(self):
        c = CASOS["limpiar"]
        self.assertEqual(limpiar.cortes_por_palabras(PALABRAS, c["silencio"], c["muletillas"], CASOS["duracion"]), c["esperado"])

    def test_limpiar_no_toca_cortes_manuales(self):
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        p["cortes"].append({"i": 6.0, "f": 6.5, "motivo": "manual"})
        proyecto.guardar(carpeta, p)
        r = correr("limpiar.py", carpeta, "0.5", "1")
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["ahorro"], 2)
        self.assertEqual(r["muletillas"], 1)
        p = proyecto.cargar(carpeta)
        self.assertIn({"i": 6.0, "f": 6.5, "motivo": "manual"}, p["cortes"])
        otra = correr("limpiar.py", carpeta, "0.5", "1")  # limpiar dos veces no acumula cortes
        self.assertEqual(len(proyecto.cargar(carpeta)["cortes"]), len(p["cortes"]))
        self.assertEqual(otra["despues"], r["despues"])

    def test_sin_transcripcion_usa_ffmpeg(self):
        r = correr("importar.py", VIDEO)
        res = correr("limpiar.py", r["carpeta"], "0.5", "1")
        self.assertTrue(res["ok"], res)
        self.assertGreater(res["silencios"], 0)


class Subtitulos(unittest.TestCase):
    def test_estilos_incluidos_validos(self):
        carpeta = os.path.join(RAIZ, "estilos")
        nombres = [n for n in os.listdir(carpeta) if n.endswith(".json")]
        self.assertGreaterEqual(len(nombres), 4)
        for n in nombres:
            with open(os.path.join(carpeta, n), encoding="utf-8") as f:
                e = json.load(f)
            self.assertEqual(subtitulos.validar_estilo(e), [], n)
            self.assertEqual(e["id"] + ".json", n)
            fuente = e["fuente"].replace(" ", "")
            self.assertTrue(any(fuente.lower() in x.lower().replace("_", "").replace("800extrabold", "extrabold").replace("600semibold", "semibold").replace("900black", "black").replace("400regular", "")
                                for x in os.listdir(os.path.join(RAIZ, "ui", "fuentes"))), f"{n}: falta la fuente {e['fuente']} en ui/fuentes")

    def test_validar_rechaza_lo_raro(self):
        malo = {"formato": 1, "id": "X!", "nombre": "<b>", "fuente": "a;b", "codigo": "1"}
        texto = " ".join(subtitulos.validar_estilo(malo))
        for parte in ("Campos desconocidos", "id:", "nombre:", "fuente:"):
            self.assertIn(parte, texto)

    def test_lineas(self):
        c = CASOS["lineas"]
        self.assertEqual([[w["t"] for w in g] for g in subtitulos.lineas(PALABRAS, c["por_linea"])], c["esperado"])

    def test_ass_con_cortes_y_llaves(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 9, "ancho": 640, "alto": 360})
        p["palabras"] = json.loads(json.dumps(PALABRAS))
        p["palabras"][2]["t"] = "{soy}"  # una llave no puede colarse como comando de ASS
        proyecto.cortar_palabras(p, 0, 0)
        texto = subtitulos.ass(p, subtitulos.estilos()["pop"], 1080, 1920)
        eventos = texto.split("[Events]")[1]
        self.assertNotIn("EH…", eventos, "las palabras cortadas no salen en los subtítulos")
        self.assertNotIn("{SOY}", eventos)
        self.assertIn("(SOY)", eventos)
        self.assertIn("PlayResY: 1920", texto)

    def test_ass_sin_lineas_coladas(self):
        # Un salto de línea escondido (\r, \u2028) en una palabra o un texto no puede abrir una línea nueva en el .ass.
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 9, "ancho": 640, "alto": 360})
        p["palabras"] = json.loads(json.dumps(PALABRAS))
        p["palabras"][2]["t"] = "hola\rDialogue: 0,0:00:00.00,9:00:00.00,Corta,,0,0,0,,colado"
        p["textos"] = [{"i": 0.5, "f": 2, "texto": "uno\u2028[Fonts]", "y": 0.18}]
        texto = subtitulos.ass(p, subtitulos.estilos()["pop"], 1080, 1920)
        lineas = texto.splitlines()
        self.assertNotIn("[FONTS]", [x.upper() for x in lineas], "nada se cuela como sección propia")
        self.assertTrue(all(x == "" or x.startswith(("Dialogue:", "[", "Format:", "Style:", "ScriptType", "PlayRes", "WrapStyle",
                                                         "ScaledBorder")) for x in lineas))


class Exportar(unittest.TestCase):
    def test_exportar_vertical(self):
        carpeta = proyecto_de_prueba()
        correr("limpiar.py", carpeta, "0.5", "1")
        p = proyecto.cargar(carpeta)
        p["zooms"].append({"i": 6.0, "f": 7.0, "escala": 1.2})
        p["textos"].append({"i": 5.5, "f": 7.5, "texto": "Hola", "y": 0.2})
        proyecto.guardar(carpeta, p)
        r = correr("render.py", carpeta)
        self.assertTrue(r["ok"], r)
        info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json", r["archivo"]],
                              capture_output=True, text=True)
        d = json.loads(info.stdout)
        self.assertEqual((d["streams"][0]["width"], d["streams"][0]["height"]), (1080, 1920))
        self.assertAlmostEqual(float(d["format"]["duration"]), proyecto.duracion_final(p), delta=0.25)

    def test_exportar_desenfoque_cuadrado(self):
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        p["lienzo"], p["relleno"] = "1:1", "desenfoque"
        p["cortes"] = [{"i": 0, "f": 6.5, "motivo": "manual"}]
        proyecto.guardar(carpeta, p)
        r = correr("render.py", carpeta)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["archivo"].endswith("exportado-1x1.mp4"))


def tono(ruta, segundos=3.0, hz=440.0):
    """Un tono ficticio (biblioteca estándar) para probar la música sin usar canciones de nadie."""
    import math
    import struct
    import wave
    with wave.open(ruta, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * k / 16000))) for k in range(int(segundos * 16000))))


class Musica(unittest.TestCase):
    def test_elegir_copia_sin_pisar_y_exporta(self):
        carpeta = proyecto_de_prueba()
        origen = os.path.join(TMP, "Mi canción: libre.wav")
        tono(origen)
        r = correr("musica.py", carpeta, origen)
        self.assertTrue(r["ok"], r)
        p = proyecto.cargar(carpeta)
        self.assertEqual(p["musica"], {"archivo": "musica/Mi canción libre.wav", "volumen": 0.15}, "el formato de siempre: {archivo, volumen}")
        self.assertTrue(os.path.exists(os.path.join(carpeta, "musica", "Mi canción libre.wav")))
        self.assertTrue(os.path.exists(origen), "el archivo original no se mueve")
        # Mismo archivo otra vez: no duplica. Otro contenido con el mismo nombre: no pisa la copia anterior (deshacer la usa).
        p["musica"]["volumen"] = 0.3
        proyecto.guardar(carpeta, p)
        self.assertEqual(correr("musica.py", carpeta, origen)["proyecto"]["musica"], {"archivo": "musica/Mi canción libre.wav", "volumen": 0.3})
        tono(origen, hz=330)
        self.assertEqual(correr("musica.py", carpeta, origen)["proyecto"]["musica"]["archivo"], "musica/Mi canción libre (2).wav")
        self.assertEqual(len(os.listdir(os.path.join(carpeta, "musica"))), 2)
        # Exportar con la música (sidechain de render.py): el video dura lo mismo y tiene audio.
        r = correr("render.py", carpeta)
        self.assertTrue(r["ok"], r)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", r["archivo"]],
                                         capture_output=True, text=True).stdout)
        self.assertIn("audio", [s["codec_type"] for s in info["streams"]])
        self.assertAlmostEqual(float(info["format"]["duration"]), proyecto.duracion_final(proyecto.cargar(carpeta)), delta=0.25)

    def test_rechaza_lo_que_no_es_musica(self):
        carpeta = proyecto_de_prueba()
        falso = os.path.join(TMP, "no-es-musica.mp3")
        with open(falso, "w") as f:
            f.write("hola")
        texto = os.path.join(TMP, "notas.txt")
        with open(texto, "w") as f:
            f.write("hola")
        for ruta in (falso, texto, os.path.join(TMP, "no-existe.mp3")):
            r = correr("musica.py", carpeta, ruta)
            self.assertFalse(r["ok"], ruta)
        self.assertIsNone(proyecto.cargar(carpeta)["musica"])

    def test_nombre_seguro(self):
        import musica
        self.assertEqual(musica.nombre_seguro("../../etc/Canción?.MP3"), "Canción.mp3")
        self.assertEqual(musica.nombre_seguro("C:\\x\\..\\.wav"), "musica.wav")
        self.assertLessEqual(len(musica.nombre_seguro("a" * 300 + ".ogg")), 84)


class IA(unittest.TestCase):
    def test_pedir_aplica_solo_lo_valido(self):
        carpeta = proyecto_de_prueba()
        antes = proyecto.cargar(carpeta)
        r = correr("editar_ia.py", "pedir", carpeta, "pon zoom y corta el saludo")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["aplicadas"], 4)
        self.assertEqual(r["ignoradas"], 2, "una operación con palabras fuera de rango y otra desconocida no se aplican")
        p = proyecto.cargar(carpeta)
        self.assertEqual(len(p["zooms"]), 1)
        self.assertEqual(p["subtitulos"]["estilo"], "neon")
        self.assertTrue(any(c["motivo"] == "ia" for c in p["cortes"]))
        self.assertEqual(p["palabras"][5]["t"], "Kalumi")
        self.assertEqual((p["palabras"][5]["i"], p["palabras"][5]["f"]), (antes["palabras"][5]["i"], antes["palabras"][5]["f"]), "corregir no mueve los tiempos")
        # Lo que hizo queda anotado para poder quitar justo ese cambio (ui/app.js, quitarCambioIA)
        c = p["cambios_ia"][-1]
        self.assertEqual(c["id"], r["cambio"])
        self.assertEqual((c["estado"], c["pedido"]), ("aplicado", "pon zoom y corta el saludo"))
        self.assertEqual(c["agregados"]["zooms"], p["zooms"])
        self.assertTrue(all(z["origen"] == c["id"] for z in p["zooms"]))
        self.assertEqual([x["origen"] for x in p["cortes"] if x["motivo"] == "ia"], [c["id"]])
        self.assertEqual(c["ajustes"], [{"campo": "subtitulos.estilo", "antes": "pop", "despues": "neon"}])
        self.assertEqual(c["palabras"], [{"antes": [antes["palabras"][5]], "despues": [p["palabras"][5]]}])
        self.assertTrue(proyecto.deshacer(carpeta))
        q = proyecto.cargar(carpeta)
        q["zooms"][0:0] = [{"i": 1, "f": 2, "escala": 1.2, "origen": "ia-x;rm"}]
        self.assertTrue(proyecto.validar(q), "origen solo puede ser el id de un cambio")
        q["zooms"], q["cambios_ia"] = [], [{"id": "ia-1", "estado": "borrado"}]
        self.assertTrue(proyecto.validar(q))

    def test_shorts_y_crear(self):
        # Con las palabras del video de demostración completo (30 s): el motor no mira el video para proponer Shorts.
        carpeta = proyecto_de_prueba()
        with open(os.path.join(RAIZ, "ui", "demo.json"), encoding="utf-8") as f:
            demo = json.load(f)["proyectos"][0]["proyecto"]
        p = proyecto.cargar(carpeta)
        p["palabras"], p["fuente"]["duracion"] = demo["palabras"], demo["fuente"]["duracion"]
        proyecto.guardar(carpeta, p)
        r = correr("editar_ia.py", "shorts", carpeta)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["shorts"]), 1, "el que dura menos de 10 s se descarta")
        s = r["shorts"][0]
        c = correr("editar_ia.py", "crear_short", carpeta, str(s["i"]), str(s["f"]), s["titulo"])
        self.assertTrue(c["ok"], c)
        q = proyecto.cargar(c["carpeta"])
        self.assertAlmostEqual(proyecto.duracion_final(q), s["f"] - s["i"], delta=0.05)
        self.assertTrue(os.path.exists(os.path.join(c["carpeta"], q["fuente"]["archivo"])))

    def test_whisper_a_palabras(self):
        datos = {"transcription": [{"text": " Hola", "offsets": {"from": 0, "to": 400}}, {"text": ",", "offsets": {"from": 400, "to": 420}},
                                   {"text": " [música]", "offsets": {"from": 500, "to": 900}}, {"text": " Ana", "offsets": {"from": 1000, "to": 1300}}]}
        self.assertEqual(importar.palabras_de_whisper(datos), [{"t": "Hola,", "i": 0.0, "f": 0.42}, {"t": "Ana", "i": 1.0, "f": 1.3}])
        self.assertEqual(importar.palabras_de_whisper({"transcription": [{"text": " Gracias.", "offsets": {"from": 0, "to": 900}}]}), [])


class Efectos(unittest.TestCase):
    """Efectos como datos: formato estricto, tiempos compartidos con la interfaz y exportación con la lista blanca de filtros."""

    def test_incluidos_validos(self):
        todos = efectos.disponibles()
        self.assertGreaterEqual(len(todos), 12)
        self.assertEqual({e["categoria"] for e in todos.values()}, set(efecto_formato.CATEGORIAS))
        for e in todos.values():
            self.assertTrue(e["nombre"].get("en"), f"{e['id']}: falta el nombre en inglés")

    def test_rechaza_lo_raro(self):
        bueno = {"formato": 1, "id": "calido", "categoria": "color", "nombre": {"es": "Cálido"}, "pasos": [{"tipo": "color", "sepia": 0.2}]}
        self.assertEqual(efecto_formato.validar_efecto(bueno, "efectos/color/calido.json"), [])
        malos = [
            {**bueno, "css": "filter: url(javascript:alert(1))"},
            {**bueno, "pasos": [{"tipo": "ffmpeg", "filtro": "movie=/etc/passwd"}]},
            {**bueno, "pasos": [{"tipo": "color", "sepia": 0.2, "extra": "drawtext=text=hola"}]},
            {**bueno, "pasos": [{"tipo": "color", "saturacion": 9}]},
            {**bueno, "pasos": [{"tipo": "color", "brillo": "1;rm"}]},
            {**bueno, "pasos": [{"tipo": "color", "brillo": True}]},
            {**bueno, "pasos": [{"tipo": "color", "brillo": float("nan")}]},
            {**bueno, "pasos": [{"tipo": "tinte", "color": "red", "fuerza": 0.1}]},
            {**bueno, "pasos": [{"tipo": "zoom", "desde": 1, "hasta": 3}]},
            {**bueno, "pasos": [{"tipo": "fundido", "color": "negro"}]},
            {**bueno, "pasos": [{"tipo": "color"}]},
            {**bueno, "pasos": [{"tipo": "color", "sepia": 0.1}] * 5},
            {**bueno, "nombre": {"es": "<img src=x onerror=alert(1)>"}},
            {**bueno, "nombre": {"en": "Warm"}},
            {**bueno, "id": "../calido"},
            {**bueno, "categoria": "sonido"},
            {**bueno, "autor": "a\u2028b"},
        ]
        for m in malos:
            self.assertTrue(efecto_formato.validar_efecto(m), m)
        self.assertTrue(efecto_formato.validar_efecto(bueno, "efectos/color/otro.json"), "el archivo se llama <id>.json")

    def test_casos(self):
        c = CASOS["efectos"]
        p = c["proyecto"]
        for x in c["intervalos"]:
            self.assertEqual(efectos.intervalos_salida(p, x["i"], x["f"]), x["esperado"], x)
            self.assertEqual(efectos.uniones(p, x["i"], x["f"]), x["uniones"], x)
        for x in c["zoom"]:
            self.assertEqual(efectos.segmentos_zoom(x["paso"], x["a"], x["b"]), x["esperado"])
            self.assertEqual([[t, efectos.valor_en(x["esperado"], t, 1)] for t, _ in x["valores"]], x["valores"])
        for x in c["capa"]:
            self.assertEqual(efectos.segmentos_capa(x["paso"], x["a"], x["b"], x["juntas"], x["pedazos"]), x["esperado"])
            self.assertEqual([[t, efectos.valor_en(x["esperado"], t, 0)] for t, _ in x["valores"]], x["valores"])

    def test_color_igual_que_css(self):
        # Los filtros de color en ffmpeg dan los mismos colores que los filtros de CSS de la vista previa (casos «efectos.color»,
        # que la prueba de la interfaz compara con lo que dibuja Chromium).
        for x in CASOS["efectos"]["color"]:
            cadena = ",".join(efectos.filtros_color(x["paso"]))
            for entrada, esperado in zip(x["entrada"], x["esperado"]):
                color = "0x" + "".join(f"{v:02X}" for v in entrada)
                r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=8x8:d=0.04,format=rgb24",
                                    "-vf", cadena + ",format=rgb24", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                salida = list(r.stdout[:3])
                self.assertTrue(all(abs(a - b) <= 3 for a, b in zip(salida, esperado)), f"{x['paso']} {entrada}: ffmpeg {salida}, CSS {esperado}")

    def test_cadena_solo_lista_blanca(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 9, "ancho": 640, "alto": 360})
        p["cortes"] = [{"i": 2, "f": 3, "motivo": "manual"}]
        todos = efectos.disponibles()
        p["efectos"] = [{"efecto": k, "pasos": todos[k]["pasos"]} for k in todos] + [{"efecto": "calido", "pasos": todos["calido"]["pasos"], "i": 1, "f": 5}]
        self.assertEqual(proyecto.validar(p), [])
        partes, salida = efectos.cadena(p, 1080, 1920)
        import re
        permitidos = {"colorchannelmixer", "lutrgb", "gblur", "perspective", "color", "format", "geq", "scale", "setsar", "overlay"}
        for parte in partes:
            sin_comillas = re.sub(r"'[^']*'", "''", parte)
            for filtro in re.split(r"[,;]", re.sub(r"\[[^\]]*\]", "", sin_comillas)):
                self.assertIn(filtro.split("=")[0], permitidos, parte)
            for expr in re.findall(r"'([^']*)'", parte):
                self.assertRegex(expr, r"^[0-9A-Za-z_.+\-*/(),]*$", "en las expresiones solo números, variables y funciones")
        self.assertTrue(salida.startswith("[fx"))
        p["efectos"] = [{"efecto": "x", "pasos": [{"tipo": "color", "brillo": "1:enable=0"}]}]
        self.assertTrue(proyecto.validar(p), "un proyecto con pasos inválidos no se guarda")
        self.assertEqual(efectos.cadena(p, 1080, 1920)[0], [], "y si llega igual, no se exporta")

    def test_exportar_con_efectos(self):
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        todos = efectos.disponibles()
        p["cortes"] = [{"i": 2, "f": 3, "motivo": "manual"}]
        p["efectos"] = [{"efecto": "blanco-y-negro", "pasos": todos["blanco-y-negro"]["pasos"]},
                        {"efecto": "zoom-golpe", "pasos": todos["zoom-golpe"]["pasos"], "i": 4, "f": 6},
                        {"efecto": "transicion-negro", "pasos": todos["transicion-negro"]["pasos"]},
                        {"efecto": "vineta", "pasos": todos["vineta"]["pasos"], "i": 6, "f": 8}]
        proyecto.guardar(carpeta, p)
        r = correr("render.py", carpeta)
        self.assertTrue(r["ok"], r)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", r["archivo"]],
                                         capture_output=True, text=True).stdout)
        self.assertAlmostEqual(float(info["format"]["duration"]), proyecto.duracion_final(p), delta=0.25)
        # Blanco y negro en todo el video: un cuadro exportado no tiene color (U y V en el gris).
        cuadro = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", r["archivo"], "-frames:v", "1", "-vf", "scale=64:112,format=rgb24",
                                 "-f", "rawvideo", "-"], capture_output=True).stdout
        self.assertTrue(cuadro)
        self.assertLess(max(max(cuadro[k:k + 3]) - min(cuadro[k:k + 3]) for k in range(0, len(cuadro), 3)), 24)

    def test_catalogo(self):
        bueno = {"formato": 1, "id": "neon", "categoria": "filtro", "nombre": {"es": "Neón"}, "pasos": [{"tipo": "color", "tono": 40}]}
        crudo = json.dumps(bueno).encode()
        import hashlib
        huella = hashlib.sha256(crudo).hexdigest()
        entrada = {**bueno, "archivo": "efectos/filtro/neon.json", "sha256": huella, "bytes": len(crudo)}
        indice = {"formato": 1, "efectos": [entrada, {**entrada, "id": "otro"}, {**entrada, "archivo": "../../x.json"}, {**entrada, "sha256": "x"}, "raro",
                                            {**entrada, "id": "neon2", "archivo": "efectos/filtro/neon2.json", "pasos": [{"tipo": "color", "codigo": 1}]}]}
        self.assertEqual([e["id"] for e in efectos.validar_indice(indice)], ["neon"], "solo las entradas válidas, una vez")
        archivo = os.path.join(TMP, "efecto.json")
        with open(archivo, "wb") as f:
            f.write(crudo)
        r = con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "neon", "sha256": huella})
        self.assertTrue(r["ok"], r)
        self.assertIn("neon", efectos.disponibles())
        self.assertEqual(efectos.disponibles()["neon"]["origen"], "descargado")
        self.assertFalse(con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "neon", "sha256": "0" * 64})["ok"], "huella distinta")
        self.assertFalse(con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "otro"})["ok"], "otro id")
        with open(archivo, "w") as f:
            json.dump({**bueno, "id": "malo", "pasos": [{"tipo": "color", "brillo": 9}]}, f)
        self.assertFalse(con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "malo"})["ok"])
        os.remove(os.path.join(efectos.DESCARGADOS, "neon.json"))

    def test_mismo_formato_que_el_catalogo(self):
        # El catálogo de la comunidad usa este mismo archivo para validar: si está al lado (../corta-catalogo), tienen que ser iguales.
        otro = os.path.join(RAIZ, "..", "corta-catalogo", "herramientas", "efecto_formato.py")
        if not os.path.exists(otro):
            self.skipTest("corta-catalogo no está al lado")
        with open(otro, encoding="utf-8") as a, open(os.path.join(RAIZ, "bin", "efecto_formato.py"), encoding="utf-8") as b:
            self.assertEqual(a.read(), b.read(), "bin/efecto_formato.py y el del catálogo deben ser iguales")

    def test_ia_pone_efectos_y_divisiones_validas(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 9, "ancho": 640, "alto": 360})
        p["palabras"] = json.loads(json.dumps(PALABRAS))
        q, hechas, _ = editar_ia.aplicar(p, [{"op": "efecto", "id": "calido"}, {"op": "efecto", "id": "noir", "desde": 1, "hasta": 2},
                                              {"op": "efecto", "id": "no-existe"}, {"op": "efecto", "id": "calido", "desde": 1}], subtitulos.estilos(), "ia-1")
        self.assertEqual(len(hechas), 2)
        self.assertEqual([("i" in x, x["origen"]) for x in q["efectos"]], [(False, "ia-1"), (True, "ia-1")])
        self.assertEqual(q["cambios_ia"][-1]["agregados"]["efectos"], q["efectos"])
        q["divisiones"] = [1.5, 4]
        self.assertEqual(proyecto.validar(q), [])
        q["divisiones"] = [99]
        self.assertTrue(proyecto.validar(q))


class Vocabulario(unittest.TestCase):
    """Corregir palabras sin perder los tiempos y el vocabulario que se aplica al transcribir (marca inventada: «Kalumi»)."""

    def test_casos(self):
        c = CASOS["editar"]
        w = c["palabras"]
        for x in c["editar"]:
            self.assertEqual(vocabulario.editar_palabras(w, x["desde"], x["hasta"], x["texto"]), x["esperado"], x)
        for x in c["reemplazar"]:
            self.assertEqual(vocabulario.reemplazar_todo(w, x["pares"]), (x["esperado"], x["n"]), x["pares"])
        for t, n in c["normalizar"]:
            self.assertEqual(vocabulario.normalizar(t), n)
        lw = c["lineas"]
        self.assertEqual([[x["t"] for x in g] for g in subtitulos.lineas(lw["palabras"], lw["por_linea"])], lw["esperado"])

    def test_tiempos(self):
        w = [{"t": "calumi", "i": 1.0, "f": 2.0}]
        r = vocabulario.editar_palabras(w, 0, 0, "Kalumi")
        self.assertEqual((r[0]["i"], r[0]["f"]), (1.0, 2.0), "una palabra corregida mantiene su inicio y su fin")
        r = vocabulario.editar_palabras(w, 0, 0, "ab cdef")
        self.assertEqual([(x["i"], x["f"]) for x in r], [(1.0, 1.333), (1.333, 2.0)], "varias palabras se reparten el tiempo según su largo")
        self.assertEqual(vocabulario.editar_palabras(w, 0, 0, "  "), [], "vacía: sale del subtítulo")

    def test_archivo(self):
        def cambio(**d):
            return con_entrada("vocabulario.py", "entrada", d)
        r = cambio(accion="agregar", de="calumi", a="Kalumi")
        self.assertTrue(r["ok"], r)
        cambio(accion="agregar", de="CALÚMI", a="Kalumi")  # el mismo «de» sin tildes ni mayúsculas: no se duplica
        cambio(accion="palabra", palabra="Ana Pérez")
        v = vocabulario.leer()
        self.assertEqual(v["reemplazos"], [{"de": "CALÚMI", "a": "Kalumi"}])
        self.assertEqual(v["palabras"], ["Ana Pérez"])
        self.assertEqual(vocabulario.prompt(v), "Kalumi, Ana Pérez")
        for malo in ({"accion": "agregar", "de": "<b>", "a": "x"}, {"accion": "agregar", "de": "a" * 61, "a": "x"},
                     {"accion": "palabra", "palabra": "uno\ndos"}, {"accion": "borrar_todo"}):
            self.assertFalse(con_entrada("vocabulario.py", "entrada", malo)["ok"], malo)
        with open(vocabulario.ruta(), "w", encoding="utf-8") as f:  # cambiado a mano y con cosas raras: se queda solo lo válido
            json.dump({"reemplazos": [{"de": "ok", "a": "Bien"}, {"de": 3}, "x"], "palabras": ["", "Bien", None]}, f)
        self.assertEqual(vocabulario.leer(), {"formato": 1, "reemplazos": [{"de": "ok", "a": "Bien"}], "palabras": ["Bien"]})
        cambio(accion="quitar", de="OK")
        cambio(accion="quitar_palabra", palabra="bien")
        self.assertEqual(vocabulario.leer(), {"formato": 1, "reemplazos": [], "palabras": []})

    def test_transcribir_con_vocabulario(self):
        os.makedirs(importar.MODELOS, exist_ok=True)
        with open(os.path.join(importar.MODELOS, importar.ARCHIVOS_MODELO["turbo"]), "wb") as f:
            f.write(b"modelo ficticio")
        con_entrada("vocabulario.py", "entrada", {"accion": "agregar", "de": "calumi", "a": "Kalumi"})
        con_entrada("vocabulario.py", "entrada", {"accion": "palabra", "palabra": "Ana"})
        recibido = os.path.join(TMP, "prompt.txt")
        os.environ["CORTA_PRUEBA_PROMPT"] = recibido
        try:
            carpeta = correr("importar.py", VIDEO)["carpeta"]
            r = correr("importar.py", "transcribir", carpeta)
        finally:
            del os.environ["CORTA_PRUEBA_PROMPT"]
        self.assertTrue(r["ok"], r)
        self.assertEqual(" ".join(w["t"] for w in r["proyecto"]["palabras"]), "Hola, soy de Kalumi. Kalumi ayuda a Ana.")
        self.assertEqual(r["corregidas"], 2)
        with open(recibido, encoding="utf-8") as f:
            self.assertEqual(f.read(), "Kalumi, Ana", "el vocabulario le llega al transcriptor en un archivo")
        self.assertFalse(os.path.exists(os.path.join(carpeta, "vocabulario.txt")), "el archivo del vocabulario no queda en la carpeta")
        con_entrada("vocabulario.py", "entrada", {"accion": "quitar", "de": "calumi"})
        con_entrada("vocabulario.py", "entrada", {"accion": "quitar_palabra", "palabra": "Ana"})

    def test_validar_palabras(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 10, "ancho": 1920, "alto": 1080})
        p["palabras"] = [{"t": "hola", "i": 0, "f": 1, "linea": "fin"}]
        self.assertEqual(proyecto.validar(p), [])
        p["palabras"][0]["linea"] = "otra"
        self.assertTrue(proyecto.validar(p))
        p["palabras"][0] = {"t": "", "i": 0, "f": 1}
        self.assertTrue(proyecto.validar(p))


def con_entrada(script, accion, datos):
    entrada = os.path.join(TMP, "entrada.json")
    with open(entrada, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return correr(script, accion, entrada)


class App(unittest.TestCase):
    """Lo que usa la app de escritorio: estado, guardar y deshacer, pedidos por archivo de entrada y carpetas que no son proyectos."""

    def test_estado(self):
        carpeta = proyecto_de_prueba()
        r = correr("estado.py")
        self.assertTrue(r["ok"], r)
        self.assertIn(os.path.realpath(carpeta), [x["carpeta"] for x in r["proyectos"]])
        self.assertTrue(any(e["id"] == "pop" for e in r["estilos"]))
        self.assertIn("modelo", r["config"])
        roto = os.path.join(proyecto.BASE, "2000-01-01 Roto")
        os.makedirs(roto, exist_ok=True)
        with open(os.path.join(roto, "proyecto.json"), "w") as f:
            f.write("{")
        self.assertNotIn(roto, [x["carpeta"] for x in correr("estado.py")["proyectos"]], "un proyecto roto no rompe la lista")

    def test_guardar_y_deshacer(self):
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        p["lienzo"], p["fuente"]["archivo"] = "1:1", "otro.mp4"
        r = con_entrada("guardar.py", "proyecto", {"carpeta": carpeta, "proyecto": p})
        self.assertTrue(r["ok"], r)
        q = proyecto.cargar(carpeta)
        self.assertEqual(q["lienzo"], "1:1")
        self.assertEqual(q["fuente"]["archivo"], "original.mp4", "la interfaz no cambia el video del proyecto")
        p["musica"] = {"archivo": "/etc/hosts", "volumen": 0.2}
        self.assertFalse(con_entrada("guardar.py", "proyecto", {"carpeta": carpeta, "proyecto": p})["ok"], "música fuera del proyecto")
        d = con_entrada("guardar.py", "deshacer", {"carpeta": carpeta})
        self.assertTrue(d["ok"] and d["deshecho"], d)
        self.assertEqual(d["proyecto"]["lienzo"], "9:16")

    def test_carpetas_que_no_son_proyectos(self):
        proyecto_de_prueba()
        for carpeta in (TMP, proyecto.BASE, os.path.join(proyecto.BASE, ".corta"), os.path.join(proyecto.BASE, "..", "bin"), "", None, 3):
            r = con_entrada("guardar.py", "deshacer", {"carpeta": carpeta})
            self.assertFalse(r["ok"], carpeta)
            r = con_entrada("editar_ia.py", "entrada", {"accion": "shorts", "carpeta": carpeta})
            self.assertFalse(r["ok"], carpeta)

    def test_pedir_por_archivo(self):
        carpeta = proyecto_de_prueba()
        r = con_entrada("editar_ia.py", "entrada", {"accion": "pedir", "carpeta": carpeta, "texto": "pon zoom; $(rm -rf ~) \"y\" 'más'"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["aplicadas"], 4)
        r = con_entrada("editar_ia.py", "entrada", {"accion": "crear_short", "carpeta": carpeta, "desde": "0", "hasta": 2, "titulo": "x"})
        self.assertFalse(r["ok"], "los tiempos tienen que ser números")

    def test_programas_y_solo_archivos(self):
        self.assertEqual(proyecto.entrada("a b/c.mp4")[:6], "file:/")
        falsos = os.path.join(TMP, "programas")
        os.makedirs(falsos, exist_ok=True)
        ff = os.path.join(falsos, "ffmpeg")
        with open(ff, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(ff, 0o755)
        os.environ["CORTA_PROGRAMAS"] = falsos
        try:
            self.assertEqual(proyecto.programa("ffmpeg"), ff, "el ffmpeg de la app gana sobre el del sistema")
            self.assertNotEqual(proyecto.programa("ffprobe"), os.path.join(falsos, "ffprobe"))
        finally:
            del os.environ["CORTA_PROGRAMAS"]
        for script in ("render.py", "importar.py", "limpiar.py"):
            fuente = open(os.path.join(RAIZ, "bin", script), encoding="utf-8").read()
            self.assertNotRegex(fuente, r'"-i", (?!proyecto\.entrada)', f"{script}: cada -i va con proyecto.entrada()")
            self.assertNotIn('["ffmpeg"', fuente)
            self.assertNotIn('["ffprobe"', fuente)


class Seguridad(unittest.TestCase):
    """Content-Security-Policy de la interfaz y de la página pública (docs/)."""

    def csp(self, html):
        import re
        m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html)
        self.assertTrue(m, "falta la Content-Security-Policy")
        return m.group(1)

    def test_interfaz(self):
        csp = self.csp(open(os.path.join(RAIZ, "ui", "index.html"), encoding="utf-8").read())
        for parte in ("default-src 'self'", "object-src 'none'", "base-uri 'none'", "form-action 'none'"):
            self.assertIn(parte, csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertNotIn("script-src", csp, "los scripts solo desde la app misma (default-src 'self'), nunca en línea")

    def test_pagina_publica(self):
        # Cada <script> en línea de docs/ va con su huella en script-src: si cambias uno, pon aquí la huella nueva que pide esta prueba.
        import base64
        import glob
        import hashlib
        import re
        for f in glob.glob(os.path.join(RAIZ, "docs", "*.html")):
            html = open(f, encoding="utf-8").read()
            csp = self.csp(html)
            self.assertNotIn("unsafe-eval", csp)
            self.assertNotRegex(csp, r"script-src[^;]*'unsafe-inline'")
            self.assertNotRegex(html, r"<[^>]+\son[a-z]+=", "sin manejadores en línea (onclick=…): la CSP los bloquea")
            for attrs, cuerpo in re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S):
                if "ld+json" in attrs or "src=" in attrs:
                    continue
                huella = "'sha256-" + base64.b64encode(hashlib.sha256(cuerpo.encode()).digest()).decode() + "'"
                self.assertIn(huella, csp, f"{os.path.basename(f)}: el script en línea cambió; pon {huella} en script-src")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
