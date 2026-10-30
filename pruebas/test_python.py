"""Pruebas del motor en Python. Nunca tocan datos reales ni llaman a una IA de verdad: usan una carpeta temporal (CORTA_CARPETA)
y una IA falsa en el PATH (pruebas/ia_falsa.py, instalada como «claude»). Exportar usa ffmpeg de verdad con un video ficticio corto.

Uso: python3 pruebas/test_python.py
"""
import hashlib
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
import plantilla_formato  # noqa: E402
import plantillas  # noqa: E402
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
            {**bueno, "pasos": [{"tipo": "franjas", "duracion": 0.5, "franjas": 2.5}]},
            {**bueno, "pasos": [{"tipo": "franjas", "duracion": 0.5, "franjas": 4}]},
            {**bueno, "pasos": [{"tipo": "barrido", "duracion": 0.5, "direccion": "diagonal"}]},
            {**bueno, "pasos": [{"tipo": "interferencia", "duracion": 1.2}]},
            {**bueno, "pasos": [{"tipo": "interferencia", "intensidad": 0.5}]},
            {**bueno, "pasos": [{"tipo": "destello", "duracion": 0.3, "color": "white"}]},
            {**bueno, "pasos": [{"tipo": "zoom_paso", "duracion": 0.3, "desenfoque": 2}]},
            {**bueno, "pasos": [{"tipo": "rebote", "duracion": 0.3, "filtro": "rgbashift=rh=9"}]},
        ]
        for m in malos:
            self.assertTrue(efecto_formato.validar_efecto(m), m)
        self.assertTrue(efecto_formato.validar_efecto(bueno, "efectos/color/otro.json"), "el archivo se llama <id>.json")
        self.assertEqual(efecto_formato.validar_pasos([{"tipo": "franjas", "duracion": 0.5, "franjas": 2.0}]), [], "un entero escrito 2.0 vale")

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
        for x in c["transiciones"]:
            paso, juntas = x["paso"], x["juntas"]
            self.assertEqual(efecto_formato.validar_pasos([paso]), [], paso)
            self.assertEqual(efectos.ventanas(paso, juntas), x["ventanas"], paso)
            self.assertEqual(efectos.ventanas(paso, juntas, 0.5), x["centro"], paso)
            self.assertEqual(efectos.segmentos_paso(paso, juntas), x["segmentos"], paso)
            if "exposicion" in x:
                self.assertEqual(efectos.segmentos_exposicion(paso, juntas), x["exposicion"])
            if "interferencia" in x:
                self.assertEqual(efectos.cortes_interferencia(paso, juntas), x["interferencia"])
                self.assertEqual(list(efectos.franjas_interferencia(paso)), x["franjas"])
            neutro = 1 if paso["tipo"] in ("rebote", "zoom_paso") else 0
            for t, v in x.get("valores", []):
                self.assertEqual(efectos.valor_en(x["segmentos"], t, neutro), v, (paso["tipo"], t))

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
        permitidos = {"colorchannelmixer", "lutrgb", "gblur", "perspective", "color", "format", "geq", "scale", "setsar", "overlay",
                      "split", "crop", "rgbashift", "eq", "trim", "setpts", "tpad"}
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

    def test_transiciones_exportan(self):
        # Cada transición nueva exporta de verdad (ffmpeg) en un corte y en una división: dura lo mismo, cambia la imagen solo cerca
        # de la unión y lo de afuera queda igual que sin transición.
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        p["lienzo"], p["subtitulos"]["activos"] = "9:16", False
        p["cortes"] = [{"i": 1.5, "f": 2.5, "motivo": "manual"}, {"i": 5, "f": 9, "motivo": "manual"}]
        p["divisiones"] = [4]   # uniones en 1,5 (corte) y 3 (división) del video exportado, que dura 4 s

        def exportar(pasos):
            p["efectos"] = [{"efecto": "prueba", "pasos": pasos}] if pasos else []
            proyecto.guardar(carpeta, p)
            r = correr("render.py", carpeta)
            self.assertTrue(r["ok"], r)
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", r["archivo"]],
                                       capture_output=True, text=True).stdout)
            self.assertAlmostEqual(dur, 4, delta=0.1, msg=pasos)
            cuadros = subprocess.run(["ffmpeg", "-v", "error", "-i", r["archivo"], "-vf", "scale=27:48,format=rgb24", "-f", "rawvideo", "-"],
                                     capture_output=True).stdout
            return [cuadros[k:k + 27 * 48 * 3] for k in range(0, len(cuadros), 27 * 48 * 3)]

        def dif(a, b):
            return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

        base = exportar(None)
        for paso in ({"tipo": "interferencia", "duracion": 0.4, "intensidad": 0.8},
                     {"tipo": "destello", "duracion": 0.4, "color": "#FFC46B", "intensidad": 0.8, "exposicion": 0.6},
                     {"tipo": "franjas", "duracion": 0.6, "franjas": 3, "direccion": "vertical"},
                     {"tipo": "franjas", "duracion": 0.6, "franjas": 2, "direccion": "horizontal"},
                     {"tipo": "rebote", "duracion": 0.6, "intensidad": 1},
                     {"tipo": "barrido", "duracion": 0.6, "direccion": "izquierda", "desenfoque": 0.6},
                     {"tipo": "barrido", "duracion": 0.6, "direccion": "arriba"},
                     {"tipo": "zoom_paso", "duracion": 0.6, "intensidad": 0.8, "desenfoque": 0.5}):
            cuadros = exportar([paso])
            self.assertEqual(len(cuadros), len(base), paso)
            for union in (1.5, 3):
                cerca = max(dif(cuadros[k], base[k]) for k in range(round((union - 0.15) * 30), round((union + 0.15) * 30)))
                self.assertGreater(cerca, 4, f"{paso['tipo']}: no se nota en la unión de {union} s")
            for k in [*range(0, 30), *range(70, 75), *range(105, 120)]:
                self.assertLess(dif(cuadros[k], base[k]), 1.5, f"{paso['tipo']}: cambió el cuadro {k}, lejos de las uniones")

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
        self.assertFalse(con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "otro", "sha256": huella})["ok"], "otro id")
        for sin in ({}, {"sha256": ""}, {"sha256": None}, {"sha256": huella.upper()}, {"sha256": huella[:63]}):
            self.assertFalse(con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "neon", **sin})["ok"], f"sin huella válida: {sin}")
        with open(archivo, "w") as f:
            json.dump({**bueno, "id": "malo", "pasos": [{"tipo": "color", "brillo": 9}]}, f)
        with open(archivo, "rb") as f:
            huella_mala = hashlib.sha256(f.read()).hexdigest()
        self.assertFalse(con_entrada("efectos.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "malo", "sha256": huella_mala})["ok"])
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


class Plantillas(unittest.TestCase):
    """Plantillas como datos: formato estricto, referencias a efectos y estilos que existen, llenar huecos igual que la interfaz y
    armar de verdad con ffmpeg (clips y fotos, transición en la unión) con una lista blanca de filtros."""

    def test_incluidas_validas(self):
        todas = plantillas.disponibles()
        self.assertGreaterEqual(len(todas), 8)
        self.assertGreaterEqual(len({p["categoria"] for p in todas.values()}), 4)
        tipos = plantillas.tipos_de_efectos({i: e for i, e in efectos.disponibles().items() if e["origen"] == "incluido"})
        for p in todas.values():
            self.assertEqual(p["origen"], "incluida")
            self.assertEqual(plantilla_formato.referencias(p, tipos, set(subtitulos.estilos())), [], p["id"])
            self.assertTrue(p["nombre"].get("en") and p["descripcion"].get("en"), f"{p['id']}: falta el inglés")
            for h in p["huecos"]:
                self.assertTrue("pista" not in h or h["pista"].get("en"), p["id"])
            for t in p.get("textos", []):
                self.assertTrue(t["texto"].get("en"), p["id"])

    def test_incluidos_que_conoce_el_formato(self):
        # El catálogo revisa las plantillas contra lo que trae la app (EFECTOS_INCLUIDOS y ESTILOS_INCLUIDOS): tiene que ser igual.
        incluidos = {i: e for i, e in efectos.disponibles().items() if e["origen"] == "incluido"}
        self.assertEqual(plantillas.tipos_de_efectos(incluidos), plantilla_formato.EFECTOS_INCLUIDOS)
        base = os.path.join(RAIZ, "estilos")
        self.assertEqual(sorted(n[:-5] for n in os.listdir(base) if n.endswith(".json")), sorted(plantilla_formato.ESTILOS_INCLUIDOS))

    def test_rechaza_lo_raro(self):
        bueno = {"formato": 1, "id": "dos", "categoria": "recuerdos", "nombre": {"es": "Dos"}, "proporcion": "9:16",
                 "huecos": [{"dur": 2, "tipo": "video", "transicion": "destello"}, {"dur": 3, "tipo": "foto"}]}
        self.assertEqual(plantilla_formato.validar_plantilla(bueno, "plantillas/recuerdos/dos.json"), [])
        h = bueno["huecos"]
        malos = [
            {**bueno, "css": "x"}, {**bueno, "musica": {"archivo": "cancion.mp3"}}, {**bueno, "musica": {"bpm": 400}},
            {**bueno, "huecos": []}, {**bueno, "huecos": [{"dur": 0.2, "tipo": "video"}]}, {**bueno, "huecos": [{"dur": 16, "tipo": "video"}]},
            {**bueno, "huecos": [{"dur": 15, "tipo": "video"}] * 7}, {**bueno, "huecos": [{"dur": "2", "tipo": "video"}]},
            {**bueno, "huecos": [{"dur": True, "tipo": "video"}]}, {**bueno, "huecos": [{"dur": float("nan"), "tipo": "video"}]},
            {**bueno, "huecos": [{"dur": 2, "tipo": "audio"}]}, {**bueno, "huecos": [{"dur": 2, "tipo": "video", "filtro": "drawtext=text=x"}]},
            {**bueno, "huecos": [{"dur": 2, "tipo": "video", "efectos": ["../x"]}]}, {**bueno, "huecos": [{"dur": 2, "tipo": "video", "efectos": ["a", "a"]}]},
            {**bueno, "huecos": [{"dur": 2, "tipo": "video", "transicion": "destello"}]}, {**bueno, "huecos": [{"dur": 2, "tipo": "foto", "zoom": 2}]},
            {**bueno, "huecos": [{"dur": 2, "tipo": "foto", "pista": {"es": "<b>x</b>"}}]}, {**bueno, "textos": [{"en_hueco": 2, "texto": {"es": "x"}}]},
            {**bueno, "textos": [{"en_hueco": 0, "texto": {"es": "a{\\pos(1,1)}"}}]}, {**bueno, "textos": [{"en_hueco": 0, "texto": {"es": "x" * 61}}]},
            {**bueno, "textos": [{"en_hueco": 0, "texto": {"es": "x"}, "posicion": 1.5}]}, {**bueno, "textos": [{"en_hueco": True, "texto": {"es": "x"}}]},
            {**bueno, "subtitulos": {"estilo": "../pop"}}, {**bueno, "subtitulos": {"estilo": "pop", "css": 1}}, {**bueno, "efectos": "calido"},
            {**bueno, "proporcion": "2:1"}, {**bueno, "categoria": "sonido"}, {**bueno, "nombre": {"en": "Two"}}, {**bueno, "id": "Dos"},
            {**bueno, "formato": 2}, [h],
        ]
        for m in malos:
            self.assertTrue(plantilla_formato.validar_plantilla(m), m)
        self.assertTrue(plantilla_formato.validar_plantilla(bueno, "plantillas/recuerdos/otra.json"), "el archivo se llama <id>.json")

    def test_referencias(self):
        tipos = plantilla_formato.EFECTOS_INCLUIDOS
        base = {"formato": 1, "id": "x1", "categoria": "recuerdos", "nombre": {"es": "X"}, "proporcion": "9:16"}
        def errores(huecos, **extra):
            d = {**base, "huecos": huecos, **extra}
            self.assertEqual(plantilla_formato.validar_plantilla(d), [])
            return plantilla_formato.referencias(d, tipos, plantilla_formato.ESTILOS_INCLUIDOS)
        self.assertEqual(errores([{"dur": 2, "tipo": "video", "efectos": ["calido"], "transicion": "destello"}, {"dur": 2, "tipo": "foto"}],
                                 subtitulos={"estilo": "pop"}, efectos=["fundido-salida"]), [])
        self.assertTrue(errores([{"dur": 2, "tipo": "video", "efectos": ["no-existe"]}]))
        self.assertTrue(errores([{"dur": 2, "tipo": "video", "transicion": "fundido-salida"}, {"dur": 2, "tipo": "video"}]), "un fundido no es transición entre clips")
        self.assertTrue(errores([{"dur": 2, "tipo": "video", "transicion": "calido"}, {"dur": 2, "tipo": "video"}]))
        self.assertTrue(errores([{"dur": 2, "tipo": "video", "efectos": ["destello"]}]), "una transición no va en efectos del hueco")
        self.assertTrue(errores([{"dur": 2, "tipo": "video"}], subtitulos={"estilo": "no-existe"}))
        for t in ("interferencia", "fogonazo", "tres-franjas", "rebote", "latido", "barrido", "zoom-de-paso"):
            self.assertEqual(errores([{"dur": 2, "tipo": "video", "transicion": t}, {"dur": 2, "tipo": "foto"}]), [], f"«{t}» es transición entre clips")
        mezcla = {**tipos, "raro": ("transicion", ("barrido", "fundido"))}
        d = {**base, "huecos": [{"dur": 2, "tipo": "video", "transicion": "raro"}, {"dur": 2, "tipo": "foto"}]}
        self.assertTrue(plantilla_formato.referencias(d, mezcla, plantilla_formato.ESTILOS_INCLUIDOS), "con un fundido ya no es solo transición")

    def test_casos(self):
        c = CASOS["plantillas"]
        for x in c["llenar"]:
            self.assertEqual(plantillas.llenar(x["huecos"], x["clips"]), x["esperado"], x)
        for x in c["aplicar"]:
            self.assertEqual(plantillas.aplicar(x["plantilla"], x["tipos"], x["idioma"], c["efectos"], set(x["estilos"])), x["esperado"])
        u = c["uniones"]
        for x in u["casos"]:
            self.assertEqual(efectos.uniones(u["proyecto"], x["i"], x["f"]), x["esperado"], x)

    def test_grafo_solo_lista_blanca(self):
        import re
        g = plantillas.grafo([{"tipo": "video", "desde": 1.5, "dur": 2, "audio": True}, {"tipo": "foto", "desde": 0, "dur": 3},
                              {"tipo": "video", "desde": 0, "dur": 1, "audio": False}], 1080, 1920)
        permitidos = {"trim", "setpts", "tpad", "fps", "scale", "crop", "setsar", "format", "atrim", "asetpts", "aresample",
                      "aformat", "apad", "anullsrc", "concat"}
        for filtro in re.split(r"[,;]", re.sub(r"\[[^\]]*\]", "", g)):
            self.assertIn(filtro.split("=")[0], permitidos, filtro)
        self.assertRegex(g, r"^[0-9A-Za-z_.=:,;\[\]\-]*$", "solo números, nombres de filtros y etiquetas")

    def _clips(self):
        carpeta = os.path.join(TMP, "clips")
        os.makedirs(carpeta, exist_ok=True)
        rojo, azul = os.path.join(carpeta, "rojo.mp4"), os.path.join(carpeta, "azul.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=640x360:d=3:r=30", "-f", "lavfi", "-i", "sine=d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", rojo], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=300x400", "-frames:v", "1", azul], check=True)
        return rojo, azul

    def _instalar(self, d):
        crudo = json.dumps(d).encode()
        archivo = os.path.join(TMP, "plantilla.json")
        with open(archivo, "wb") as f:
            f.write(crudo)
        import hashlib
        return con_entrada("plantillas.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": d["id"], "sha256": hashlib.sha256(crudo).hexdigest()})

    def _color(self, video, t):
        cuadro = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", "scale=8:8,format=rgb24",
                                 "-f", "rawvideo", "-"], capture_output=True).stdout
        n = len(cuadro) // 3
        return [sum(cuadro[k::3]) // n for k in range(3)]

    def test_crear_armar_exportar_y_cambiar(self):
        rojo, azul = self._clips()
        pl = {"formato": 1, "id": "prueba-dos", "categoria": "recuerdos", "nombre": {"es": "Prueba dos", "en": "Two test"}, "proporcion": "9:16",
              "huecos": [{"dur": 2, "tipo": "video", "transicion": "destello"}, {"dur": 2.5, "tipo": "foto"}],
              "textos": [{"en_hueco": 1, "texto": {"es": "Hola", "en": "Hi"}}], "subtitulos": {"estilo": "titular"}}
        self.assertTrue(self._instalar(pl)["ok"])
        r = con_entrada("plantillas.py", "entrada", {"accion": "crear", "plantilla": "prueba-dos", "archivos": [azul, rojo], "idioma": "en"})
        self.assertTrue(r["ok"], r)
        carpeta, p = r["carpeta"], r["proyecto"]
        self.assertEqual(proyecto.validar(p), [])
        self.assertEqual([h["archivo"] for h in p["plantilla"]["huecos"]], ["clips/02.mp4", "clips/01.png"], "el video al hueco de video")
        self.assertEqual((p["lienzo"], p["divisiones"], p["textos"][0]["texto"], p["subtitulos"]["estilo"]), ("9:16", [2.0], "Hi", "titular"))
        self.assertEqual([e["efecto"] for e in p["efectos"]], ["destello", "zoom-lento"])
        fuente = os.path.join(carpeta, p["fuente"]["archivo"])
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json", fuente],
                                         capture_output=True, text=True).stdout)
        self.assertAlmostEqual(float(info["format"]["duration"]), 4.5, delta=0.1)
        self.assertEqual((info["streams"][0]["width"], info["streams"][0]["height"]), (1080, 1920))
        # Exportar con el render de siempre: rojo en el primer hueco, azul en el segundo y un destello blanco en la unión.
        e = correr("render.py", carpeta)
        self.assertTrue(e["ok"], e)
        a, b, union = self._color(e["archivo"], 0.8), self._color(e["archivo"], 3.5), self._color(e["archivo"], 2.0)
        self.assertTrue(a[0] > 180 and a[2] < 80, a)
        self.assertTrue(b[2] > 180 and b[0] < 80, b)
        self.assertTrue(min(union) > 200, f"en la unión se ve el destello: {union}")
        # La interfaz no cambia qué clip va en cada hueco; ajustar y cambiar sí (vuelven a armar el video).
        q = json.loads(json.dumps(p))
        q["plantilla"]["huecos"][0]["archivo"] = "clips/99.mp4"
        q["lienzo"] = "1:1"
        self.assertTrue(con_entrada("guardar.py", "proyecto", {"carpeta": carpeta, "proyecto": q})["ok"])
        self.assertEqual(proyecto.cargar(carpeta)["plantilla"], p["plantilla"])
        r = con_entrada("plantillas.py", "entrada", {"accion": "ajustar", "carpeta": carpeta, "hueco": 0, "desde": 0.6})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["proyecto"]["plantilla"]["huecos"][0]["desde"], 0.6)
        self.assertNotEqual(r["proyecto"]["fuente"]["archivo"], p["fuente"]["archivo"])
        self.assertFalse(os.path.exists(fuente), "el video armado anterior se borra")
        self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "ajustar", "carpeta": carpeta, "hueco": 1, "desde": 1})["ok"], "una foto no tiene «desde»")
        self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "ajustar", "carpeta": carpeta, "hueco": 5, "desde": 1})["ok"])
        r = con_entrada("plantillas.py", "entrada", {"accion": "cambiar", "carpeta": carpeta, "hueco": 1, "archivo": rojo})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["proyecto"]["plantilla"]["huecos"][1]["archivo"], "clips/02-2.mp4")
        self.assertFalse(os.path.exists(os.path.join(carpeta, "clips", "01.png")), "el clip que ya no se usa se borra")
        # Deshacer vuelve a lo editado, pero con el video armado de ahora.
        d = con_entrada("guardar.py", "deshacer", {"carpeta": carpeta})
        self.assertTrue(d["ok"])
        self.assertEqual(d["proyecto"]["fuente"], r["proyecto"]["fuente"])
        self.assertTrue(os.path.exists(os.path.join(carpeta, d["proyecto"]["fuente"]["archivo"])))
        self.assertIn(os.path.realpath(carpeta), [x["carpeta"] for x in correr("estado.py")["proyectos"]])
        os.remove(os.path.join(plantillas.DESCARGADAS, "prueba-dos.json"))

    def test_crear_rechaza(self):
        rojo, _ = self._clips()
        malos = [{"plantilla": "no-existe", "archivos": [rojo]}, {"plantilla": "producto-en-15", "archivos": []},
                 {"plantilla": "producto-en-15", "archivos": ["relativo.mp4"]}, {"plantilla": "producto-en-15", "archivos": [os.path.join(RAIZ, "README.md")]}]
        antes = set(os.listdir(proyecto.BASE)) if os.path.isdir(proyecto.BASE) else set()
        for m in malos:
            self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "crear", **m})["ok"], m)
        self.assertEqual(set(os.listdir(proyecto.BASE)) if os.path.isdir(proyecto.BASE) else set(), antes, "no deja carpetas a medias")
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 4, "ancho": 640, "alto": 360})
        for raro in ({"id": "x1", "huecos": [{"archivo": "../../etc/passwd", "tipo": "video", "desde": 0, "dur": 4, "duracion": 4}]},
                     {"id": "x1", "huecos": [{"archivo": "clips/01.mp4", "tipo": "video", "desde": 0, "dur": 3, "duracion": 4}]},
                     {"id": "x1", "huecos": [{"archivo": "clips/01.mp4", "tipo": "foto", "desde": 0, "dur": 4, "duracion": 4}]}):
            self.assertTrue(proyecto.validar({**p, "plantilla": raro}), raro)
        self.assertEqual(proyecto.validar({**p, "plantilla": {"id": "x1", "huecos": [{"archivo": "clips/01.mp4", "tipo": "video", "desde": 0, "dur": 4, "duracion": 9}]}}), [])

    def test_catalogo(self):
        bueno = {"formato": 1, "id": "tres", "categoria": "celebracion", "nombre": {"es": "Tres"}, "proporcion": "1:1", "huecos": [{"dur": 2, "tipo": "foto"}]}
        crudo = json.dumps(bueno).encode()
        import hashlib
        huella = hashlib.sha256(crudo).hexdigest()
        entrada = {**bueno, "archivo": "plantillas/celebracion/tres.json", "sha256": huella, "bytes": len(crudo)}
        indice = {"formato": 1, "plantillas": [entrada, {**entrada, "id": "otra"}, {**entrada, "archivo": "efectos/filtro/tres.json"},
                                               {**entrada, "bytes": 10 ** 6}, {**entrada, "id": "x2", "archivo": "plantillas/celebracion/x2.json", "huecos": []}]}
        self.assertEqual([e["id"] for e in plantillas.validar_indice(indice)], ["tres"])
        self.assertTrue(self._instalar(bueno)["ok"])
        self.assertEqual(plantillas.disponibles()["tres"]["origen"], "descargada")
        archivo = os.path.join(TMP, "plantilla.json")
        self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "tres", "sha256": "0" * 64})["ok"])
        with open(archivo, "rb") as f:
            huella = hashlib.sha256(f.read()).hexdigest()
        self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "otra", "sha256": huella})["ok"])
        for sin in ({}, {"sha256": ""}, {"sha256": None}, {"sha256": huella.upper()}, {"sha256": huella + "0"}):
            self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "instalar", "archivo": archivo, "id": "tres", **sin})["ok"], f"sin huella válida: {sin}")
        self.assertFalse(con_entrada("plantillas.py", "entrada", {"accion": "borrar_todo"})["ok"])
        os.remove(os.path.join(plantillas.DESCARGADAS, "tres.json"))

    def test_mismo_formato_que_el_catalogo(self):
        otro = os.path.join(RAIZ, "..", "corta-catalogo", "herramientas", "plantilla_formato.py")
        if not os.path.exists(otro):
            self.skipTest("corta-catalogo no está al lado")
        with open(otro, encoding="utf-8") as a, open(os.path.join(RAIZ, "bin", "plantilla_formato.py"), encoding="utf-8") as b:
            self.assertEqual(a.read(), b.read(), "bin/plantilla_formato.py y el del catálogo deben ser iguales")


class Velocidad(unittest.TestCase):
    """Velocidad por tramo: la misma cuenta en Python y JS (casos «velocidad»), validada, exportada con la duración justa."""

    def test_casos(self):
        c = CASOS["velocidad"]
        p = c["proyecto"]
        vels = proyecto.velocidades(p)
        self.assertEqual(proyecto.validar_velocidades(p["velocidades"], 10), [])
        for a, b, e in c["lento"]:
            self.assertEqual(proyecto.lento(vels, a, b), e, (a, b))
        for t, e in c["a_salida"]:
            self.assertEqual(proyecto.a_salida(p, t), e, t)
        self.assertEqual(proyecto.duracion_final(p), c["duracion_final"])
        for t, e in c["velocidad_en"]:
            self.assertEqual(proyecto.velocidad_en(vels, t), e, t)
        for x in c["intervalos"]:
            self.assertEqual(efectos.intervalos_salida(p, x["i"], x["f"]), x["esperado"], x)
            self.assertEqual(efectos.uniones(p, x["i"], x["f"]), x["uniones"], x)
        for x in c["poner"]:
            self.assertEqual(proyecto.poner_velocidad(json.loads(json.dumps(x["lista"])), x["i"], x["f"], x["nueva"]), x["esperado"], x)
        for e, a in c["audio"]:
            self.assertEqual(proyecto.audio_de(e), a)

    def test_rampa_continua_y_cuenta_exacta(self):
        e = {"i": 2, "f": 4, "v": 0.3, "rampa": True}
        # Sin saltos: la integral por pedazos coincide en los bordes y la velocidad va de 1 a 0,3 y vuelve.
        for u in (2.6, 3.4):
            self.assertAlmostEqual(proyecto._integral(e, u - 1e-9), proyecto._integral(e, u + 1e-9), places=6)
        self.assertAlmostEqual(proyecto.velocidad_en([e], 2), 1)
        self.assertAlmostEqual(proyecto.velocidad_en([e], 3), 0.3)
        self.assertAlmostEqual(proyecto.lento([e], 2, 4), 2 * (0.3 + 0.7 / 0.3), places=9)
        # La lentitud media de cada escalón de la voz da justo lo mismo que la imagen.
        import render
        trozos = render.tramos_audio(e, 2, 4)
        self.assertAlmostEqual(sum(proyecto.lento([e], a, b) for a, b in trozos), proyecto.lento([e], 2, 4), places=9)

    def test_validar(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 10, "ancho": 640, "alto": 360})
        bien = [{"i": 1, "f": 2, "v": 0.5, "suavizar": "mezcla", "audio": "tono"}, {"i": 2, "f": 4, "v": 0.3, "rampa": True}, {"i": 5, "f": 6, "v": 3, "origen": "ia-a"}]
        self.assertEqual(proyecto.validar({**p, "velocidades": bien}), [])
        for malo in ([{"i": 1, "f": 2, "v": 4}], [{"i": 1, "f": 2, "v": 0.1}], [{"i": 1, "f": 3, "v": 0.5}, {"i": 2, "f": 4, "v": 2}],
                     [{"i": 1, "f": 2, "v": 0.9, "rampa": True}], [{"i": 1, "f": 1.3, "v": 0.3, "rampa": True}], [{"i": 1, "f": 2, "v": 2, "suavizar": "mezcla"}],
                     [{"i": 1, "f": 2, "v": 0.5, "audio": "fuerte"}], [{"i": 1, "f": 2, "v": "0.5"}], [{"i": 1, "f": 1.05, "v": 0.5}],
                     [{"i": 9, "f": 12, "v": 0.5}], [{"i": 1, "f": 2, "v": 0.5, "filtro": "x"}], [{"i": 1, "f": 2, "v": 0.5, "rampa": False}], {"i": 1}, 5):
            self.assertTrue(proyecto.validar({**p, "velocidades": malo}), malo)

    def test_grafo_solo_lista_blanca(self):
        import re
        import render
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 9, "ancho": 640, "alto": 360})
        p["cortes"] = [{"i": 3.5, "f": 4, "motivo": "manual"}]
        p["zooms"] = [{"i": 1.5, "f": 2.5, "escala": 1.2}]
        p["musica"] = {"archivo": "musica/a.mp3", "volumen": 0.2}
        p["velocidades"] = [{"i": 1, "f": 3, "v": 0.25, "suavizar": "movimiento", "audio": "tono"}, {"i": 4.2, "f": 5, "v": 3},
                            {"i": 6, "f": 8, "v": 0.3, "rampa": True, "suavizar": "mezcla", "audio": "tono"}, {"i": 8, "f": 8.5, "v": 0.4}]
        self.assertEqual(proyecto.validar(p), [])
        g = render.grafo(p, True, "/tmp/s.ass", True)
        permitidos = {"trim", "setpts", "fps", "scale", "crop", "split", "boxblur", "eq", "overlay", "setsar", "format", "ass", "atrim", "asetpts",
                      "aresample", "anullsrc", "concat", "anull", "aloop", "volume", "asplit", "sidechaincompress", "amix", "tpad", "framerate",
                      "minterpolate", "atempo", "apad"}
        sin = re.sub(r"'[^']*'", "''", g)
        for filtro in re.split(r"[,;]", re.sub(r"\[[^\]]*\]", "", sin)):
            self.assertIn(filtro.split("=")[0], permitidos, filtro)
        for expr in re.findall(r"setpts='([^']*)'", g):
            self.assertRegex(expr, r"^[0-9A-Za-z_.+\-*/(),]*$")
        for x in re.findall(r"atempo=([0-9.]+)", g):
            self.assertTrue(0.5 <= float(x) <= 2, x)
        self.assertIn("atempo=0.5,atempo=0.5", g, "0,25× con tono: dos atempo")
        self.assertIn("volume=0", g, "0,4× sin decir nada: la voz se silencia")
        self.assertIn("minterpolate", g)
        self.assertIn("framerate=fps=30", g)

    def test_exportar_dura_lo_justo(self):
        import render
        carpeta = proyecto_de_prueba()
        p = proyecto.cargar(carpeta)
        p["cortes"] = [{"i": 4, "f": 4.5, "motivo": "manual"}]
        p["velocidades"] = [{"i": 1, "f": 2.5, "v": 0.5}, {"i": 3, "f": 4, "v": 2}, {"i": 5, "f": 7, "v": 0.3, "rampa": True, "audio": "tono"},
                            {"i": 7.5, "f": 8.5, "v": 0.25, "suavizar": "mezcla"}]
        proyecto.guardar(carpeta, p)
        r = correr("render.py", carpeta)
        self.assertTrue(r["ok"], r)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", r["archivo"]],
                                         capture_output=True, text=True).stdout)
        for s in info["streams"]:
            self.assertAlmostEqual(float(s["duration"]), proyecto.duracion_final(p), delta=1.5 / 30, msg=s["codec_type"])

    def test_ia_pone_velocidad_y_se_anota(self):
        p = proyecto.nuevo("x", {"archivo": "a.mp4", "duracion": 9, "ancho": 640, "alto": 360})
        p["palabras"] = json.loads(json.dumps(PALABRAS))
        n = len(p["palabras"])
        q, hechas, malas = editar_ia.aplicar(p, [{"op": "velocidad", "desde": 1, "hasta": 3, "v": 0.4, "rampa": True},
                                                 {"op": "velocidad", "desde": 2, "hasta": 4, "v": 2},
                                                 {"op": "velocidad", "desde": 5, "hasta": 6, "v": 9},
                                                 {"op": "velocidad", "desde": 5, "hasta": n + 3, "v": 2}], {}, "ia-v1")
        self.assertEqual((len(hechas), len(malas)), (1, 3), "pisar otra velocidad, fuera de rango o palabras que no existen: no")
        self.assertEqual(q["velocidades"], [{"i": PALABRAS[1]["i"], "f": PALABRAS[3]["f"], "v": 0.4, "rampa": True, "origen": "ia-v1"}])
        self.assertEqual(q["cambios_ia"][-1]["agregados"]["velocidades"], q["velocidades"])
        self.assertIn("velocidad", editar_ia.OPERACIONES)
        self.assertIn("rampa a 0.4×", editar_ia.velocidades_txt(q))

    def test_plantilla_con_velocidad(self):
        base = {"formato": 1, "id": "x-y", "categoria": "recuerdos", "nombre": {"es": "X"}, "proporcion": "9:16"}
        def errores(vel):
            return plantilla_formato.validar_plantilla({**base, "huecos": [{"dur": 2, "tipo": "video", "velocidad": vel}]})
        for bien in ({"v": 0.5}, {"v": 3, "audio": "silencio"}, {"v": 0.3, "rampa": True, "suavizar": "movimiento"}):
            self.assertEqual(errores(bien), [], bien)
        for malo in ({"v": 1}, {"v": 5}, {"v": 0.9, "rampa": True}, {"v": 2, "suavizar": "mezcla"}, {"v": 0.5, "filtro": "x"}, 0.5, {"v": True}):
            self.assertTrue(errores(malo), malo)


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
        for script in ("render.py", "importar.py", "limpiar.py", "plantillas.py"):
            fuente = open(os.path.join(RAIZ, "bin", script), encoding="utf-8").read()
            self.assertNotRegex(fuente, r'"-i", (?!proyecto\.entrada)', f"{script}: cada -i va con proyecto.entrada()")
            self.assertNotIn('["ffmpeg"', fuente)
            self.assertNotIn('["ffprobe"', fuente)


class Piezas(unittest.TestCase):
    """Lo que Corta usa de Pieza (nucleo, ia, i18n): app.json, carpeta de datos, config validada y probar la IA por archivo."""

    def test_app_json_y_carpeta_de_datos(self):
        with open(os.path.join(RAIZ, "app.json"), encoding="utf-8") as f:
            app = json.load(f)
        self.assertEqual((app["id"], app["nombre"], app["datos"]), ("corta", "Corta", "visible"), "~/Corta/.corta, igual que la app de Mac")
        self.assertEqual(os.path.realpath(proyecto.INTERNO), os.path.realpath(os.path.join(proyecto.BASE, ".corta")))
        import nucleo
        self.assertEqual(os.path.realpath(nucleo.carpeta_datos()), os.path.realpath(proyecto.INTERNO))
        # Las claves que acepta Ventana.swift (Config.guardar) son las de app.json.
        swift = open(os.path.join(RAIZ, "app", "Sources", "Corta", "Servicios.swift"), encoding="utf-8").read()
        for clave in app["config"]:
            self.assertIn(f'case "{clave}"', swift, f"Config.guardar acepta {clave}")
        sh = open(os.path.join(RAIZ, "herramientas", "empaquetar.sh"), encoding="utf-8").read()
        self.assertIn('cp "$RAIZ/app.json" "$APP/Contents/Resources/corta/app.json"', sh, "app.json va dentro de la app")

    def test_config_validada(self):
        ruta = os.path.join(proyecto.INTERNO, "config.json")
        antes = proyecto.leer_json(ruta, None)
        try:
            proyecto.escribir_json(ruta, {"ia": "otra", "modelo": "small", "idioma_audio": "es; rm -rf ~", "extra": 1, "bienvenida": True})
            c = proyecto.config()
            self.assertEqual((c["ia"], c["modelo"], c["idioma_audio"], c["bienvenida"]), ("claude", "small", "auto", True))
            self.assertNotIn("extra", c)
            proyecto.escribir_json(ruta, {"idioma_audio": "pt"})
            self.assertEqual(proyecto.config()["idioma_audio"], "pt")
        finally:
            if antes is None:
                os.remove(ruta)
            else:
                proyecto.escribir_json(ruta, antes)

    def test_probar_ia_por_archivo(self):
        r = con_entrada("ia.py", "probar", {"ia": "claude"})
        self.assertEqual((r["ia"], r["ok"]), ("claude", True), r)
        r = con_entrada("ia.py", "probar", {"ia": "otra"})
        self.assertEqual((r["ok"], r["codigo"]), (False, "desconocida"))
        swift = open(os.path.join(RAIZ, "app", "Sources", "Corta", "Servicios.swift"), encoding="utf-8").read()
        self.assertIn('Procesador.conEntrada("ia.py", "probar", ["ia": id])', swift, "la app prueba la IA con la pieza, por archivo")

    def test_error_de_ia_con_codigo(self):
        import ia
        antes = ia.preguntar
        ia.preguntar = lambda *a, **k: ("", {"codigo": "no_instalada", "valores": {"ia": "Claude", "detalle": ""}})
        try:
            carpeta = proyecto_de_prueba()
            r = editar_ia.pedir(carpeta, "pon zoom")
        finally:
            ia.preguntar = antes
        self.assertEqual(r, {"ok": False, "codigo": "no_instalada", "error": "No encontré Claude en este computador. Revisa en Ajustes → Tu IA."})


class Seguridad(unittest.TestCase):
    """Content-Security-Policy de la interfaz y de la página pública (docs/), lo que recibe la IA y cómo se arma el HTML."""

    def _ia_falsa(self, nombre):
        """Un CLI falso que anota sus argumentos, su entorno y los archivos de su carpeta, y responde «listo»."""
        carpeta = tempfile.mkdtemp(dir=TMP)
        anotado = os.path.join(carpeta, "anotado.json")
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("#!" + sys.executable + "\nimport json, os, sys\n"
                    f"json.dump({{'argv': sys.argv[1:], 'env': dict(os.environ), 'archivos': os.listdir('.')}}, open({anotado!r}, 'w'))\n"
                    "print('listo')\n")
        os.chmod(ruta, 0o755)
        return carpeta, anotado

    def _con_ia(self, id_ia, nombre):
        import ia
        carpeta, anotado = self._ia_falsa(nombre)
        antes_path, antes_elegida = os.environ["PATH"], ia.elegida
        os.environ["PATH"] = carpeta + os.pathsep + antes_path
        os.environ["CORTA_SECRETO_PRUEBA"] = "no-debe-llegar"
        ia.elegida = lambda: id_ia
        try:
            r = ia.ejecutar("PEDIDO-SECRETO de la persona", timeout=60)
        finally:
            os.environ["PATH"], ia.elegida = antes_path, antes_elegida
            del os.environ["CORTA_SECRETO_PRUEBA"]
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(anotado, encoding="utf-8") as f:
            return json.load(f)

    def test_ia_no_recibe_variables_de_corta(self):
        for id_ia, nombre in (("claude", "claude"), ("codex", "codex"), ("gemini", "agy")):
            x = self._con_ia(id_ia, nombre)
            self.assertFalse([k for k in x["env"] if k.startswith("CORTA_")], f"{id_ia}: las variables CORTA_* no llegan a la IA")
        x = self._con_ia("claude", "claude")
        self.assertEqual((x["env"].get("CLAUDE_CODE_DISABLE_CLAUDE_MDS"), x["env"].get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")), ("1", "1"),
                         "Claude corre sin la memoria de la persona")
        self.assertIn("--disallowedTools", x["argv"])

    def test_pedido_a_antigravity_va_en_archivo(self):
        x = self._con_ia("gemini", "agy")
        self.assertFalse(any("PEDIDO-SECRETO" in a for a in x["argv"]), "el pedido nunca va en los argumentos (los ve cualquier programa)")
        self.assertIn("instrucciones.md", x["archivos"])

    def test_T_escapa_los_valores(self):
        """T es de la pieza «i18n» (ui/i18n.js): escapa la frase y cada valor; app.js la usa tal cual."""
        js = open(os.path.join(RAIZ, "ui", "app.js"), encoding="utf-8").read()
        if not shutil.which("node"):
            self.skipTest("falta node")
        prueba = (f"const {{ T }} = require({os.path.join(RAIZ, 'ui', 'i18n.js')!r}).crear();\n"
                  "console.log(T('Plantilla «{x}» de **{n}**', { x: '<img src=x onerror=alert(1)>', n: 'a&b' }));")
        r = subprocess.run(["node", "-e", prueba], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Plantilla «&lt;img src=x onerror=alert(1)&gt;» de <b>a&amp;b</b>")
        self.assertIn("const { T, Tp, tr, frase, traducirDOM } = i18n;", js, "app.js usa la T de la pieza, no una propia")
        self.assertNotRegex(js, r"function (T|tr|traducirDOM)\(", "sin copias propias de lo que trae la pieza «i18n»")
        self.assertNotRegex(js, r"esc\((T|frase)\(", "T ya escapa: no escapar dos veces")
        html = open(os.path.join(RAIZ, "ui", "index.html"), encoding="utf-8").read()
        self.assertLess(html.index('src="i18n.js"'), html.index('src="app.js"'), "i18n.js se carga antes que app.js")

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
