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
os.environ["PATH"] = BIN_FALSO + os.pathsep + os.environ["PATH"]
sys.path.insert(0, os.path.join(RAIZ, "bin"))

import editar_ia  # noqa: E402
import importar  # noqa: E402
import limpiar  # noqa: E402
import proyecto  # noqa: E402
import subtitulos  # noqa: E402

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


class IA(unittest.TestCase):
    def test_pedir_aplica_solo_lo_valido(self):
        carpeta = proyecto_de_prueba()
        r = correr("editar_ia.py", "pedir", carpeta, "pon zoom y corta el saludo")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["aplicadas"], 3)
        self.assertEqual(r["ignoradas"], 2, "una operación con palabras fuera de rango y otra desconocida no se aplican")
        p = proyecto.cargar(carpeta)
        self.assertEqual(len(p["zooms"]), 1)
        self.assertEqual(p["subtitulos"]["estilo"], "neon")
        self.assertTrue(any(c["motivo"] == "ia" for c in p["cortes"]))
        self.assertTrue(proyecto.deshacer(carpeta))

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


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
