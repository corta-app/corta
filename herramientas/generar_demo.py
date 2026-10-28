"""Genera el video y los datos FICTICIOS de la vista previa (ui/demo/) y de las pruebas (pruebas/datos/).

Uso: python3 herramientas/generar_demo.py     (necesita Pillow y ffmpeg; solo para quien desarrolla, la app no lo usa)
     python3 herramientas/generar_demo.py --solo-musica    (solo la música de la vista previa, ui/demo/musica-demo.mp3)
     python3 herramientas/generar_demo.py --solo-plantillas (las fotos dibujadas y las plantillas de ui/demo.json, sin tocar el video)

Dibuja a «Ana», una presentadora animada en un video horizontal (16:9) que habla con pausas y muletillas, para mostrar el
encuadre vertical, la limpieza de silencios y los subtítulos. La «voz» son sílabas sintéticas: no es una persona real.
La música de la demo también se sintetiza aquí (acordes y un arpegio hechos con senos): no es música de terceros.
"""
import json
import math
import os
import random
import struct
import subprocess
import sys
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFilter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "bin"))
import efectos  # noqa: E402
import plantillas  # noqa: E402
import proyecto  # noqa: E402
import subtitulos  # noqa: E402

random.seed(11)
FPS, W, H, SR = 30, 1280, 720, 22050
GUION = [  # (palabra, pausa después en segundos)
    ("Eh…", 0.9), ("hola,", 0.1), ("soy", 0.08), ("Ana.", 1.4),
    ("¿Sabías", 0.08), ("que", 0.08), ("puedes", 0.08), ("ahorrar", 0.08), ("una", 0.08), ("hora", 0.08), ("cada", 0.08),
    ("semana", 0.08), ("editando", 0.08), ("tus", 0.08), ("videos?", 1.6),
    ("Mmm…", 0.7), ("te", 0.08), ("muestro", 0.08), ("cómo.", 1.0),
    ("Primero,", 0.25), ("sacas", 0.08), ("los", 0.08), ("silencios.", 0.9),
    ("Después,", 0.25), ("los", 0.08), ("subtítulos", 0.08), ("aparecen", 0.08), ("solos.", 1.2),
    ("Y", 0.08), ("listo:", 0.3), ("tu", 0.08), ("Short", 0.08), ("está", 0.08), ("para", 0.08), ("publicar.", 1.0),
]


def tiempos(inicio=1.2):
    t, palabras = inicio, []
    for txt, pausa in GUION:
        letras = sum(c.isalpha() for c in txt)
        dur = 0.16 + 0.065 * letras if not txt.lower().startswith(("eh", "mm")) else 0.6
        palabras.append({"t": txt, "i": round(t, 3), "f": round(t + dur, 3)})
        t += dur + pausa
    return palabras, round(t + 0.4, 2)


def voz(palabras, duracion, ruta):
    """Sílabas sintéticas (no es una voz real): un tono con vibrato por sílaba, para que se escuche el ritmo y los silencios."""
    n = int(duracion * SR)
    muestras = [0.0] * n
    for w in palabras:
        silabas = max(1, round(sum(c in "aeiouáéíóú" for c in w["t"].lower())))
        largo = (w["f"] - w["i"]) / silabas
        base = 190 + random.uniform(-15, 25)
        for s in range(silabas):
            a = int((w["i"] + s * largo) * SR)
            b = int((w["i"] + (s + 1) * largo) * SR)
            f0 = base * (1.06 if s % 2 else 0.97)
            for k in range(a, min(b, n)):
                x = (k - a) / max(1, b - a)
                env = math.sin(math.pi * x) ** 0.6
                t = k / SR
                v = math.sin(2 * math.pi * f0 * t) + 0.45 * math.sin(2 * math.pi * f0 * 2.01 * t) + 0.2 * math.sin(2 * math.pi * 760 * t)
                muestras[k] += 0.16 * env * v
    with wave.open(ruta, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in muestras))


def fondo():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):  # pared con degradado cálido
        c = (int(40 + 30 * y / H), int(32 + 18 * y / H), int(58 + 10 * y / H))
        d.line([(0, y), (W, y)], fill=c)
    d.rectangle([0, 520, W, H], fill=(58, 40, 34))  # mesa
    d.rectangle([0, 512, W, 524], fill=(86, 60, 48))
    d.rounded_rectangle([860, 120, 1170, 330], radius=18, fill=(24, 22, 34))  # cuadro con un gráfico
    for k, h in enumerate([60, 95, 75, 130, 165]):
        d.rounded_rectangle([890 + k * 55, 300 - h, 925 + k * 55, 300], radius=6, fill=(198, 244, 50) if k == 4 else (120, 110, 160))
    d.ellipse([90, 380, 210, 500], fill=(70, 120, 80))  # planta
    d.rectangle([135, 470, 165, 520], fill=(110, 70, 50))
    luz = Image.new("L", (W, H), 0)
    ImageDraw.Draw(luz).ellipse([300, -200, 980, 600], fill=70)
    luz = luz.filter(ImageFilter.GaussianBlur(120))
    return Image.composite(Image.new("RGB", (W, H), (255, 220, 180)), img, luz)


def ana(img, boca, parpadeo, gesto):
    d = ImageDraw.Draw(img)
    cx = 600  # un poco a la izquierda del centro: el encuadre vertical la sigue
    d.rounded_rectangle([cx - 150, 400, cx + 150, 640], radius=70, fill=(217, 119, 75))  # torso
    d.rectangle([cx - 28, 360, cx + 28, 410], fill=(236, 188, 150))  # cuello
    d.ellipse([cx - 108, 150, cx + 108, 390], fill=(60, 36, 28))  # pelo atrás
    d.ellipse([cx - 92, 175, cx + 92, 375], fill=(240, 196, 160))  # cara
    d.chord([cx - 100, 150, cx + 100, 300], 180, 360, fill=(60, 36, 28))  # flequillo
    ojo = 4 if parpadeo else 13
    for dx in (-38, 38):
        d.ellipse([cx + dx - 11, 268 - ojo // 2, cx + dx + 11, 268 + ojo // 2], fill=(34, 24, 20))
    d.ellipse([cx - 70, 300, cx - 44, 316], fill=(235, 150, 140))
    d.ellipse([cx + 44, 300, cx + 70, 316], fill=(235, 150, 140))
    abre = int(4 + 22 * boca)
    d.rounded_rectangle([cx - 26, 322 - abre // 4, cx + 26, 322 + abre], radius=12, fill=(120, 40, 50))
    brazo = int(gesto * 60)
    d.rounded_rectangle([cx + 120, 460 - brazo, cx + 175, 600 - brazo], radius=26, fill=(217, 119, 75))  # brazo que gesticula
    d.ellipse([cx + 118, 430 - brazo, cx + 178, 490 - brazo], fill=(240, 196, 160))


def video(palabras, duracion, salida):
    base = fondo()
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "voz.wav")
        voz(palabras, duracion, wav)
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                                 "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p",
                                 "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", "-shortest", salida], stdin=subprocess.PIPE)
        for k in range(int(duracion * FPS)):
            t = k / FPS
            hablando = next((w for w in palabras if w["i"] <= t <= w["f"]), None)
            boca = abs(math.sin((t - hablando["i"]) * 18)) if hablando else 0
            parpadeo = (t % 3.7) < 0.12
            gesto = max(0, math.sin(t * 1.3)) if hablando else 0
            img = base.copy()
            ana(img, boca, parpadeo, gesto)
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
        proc.wait()


def musica_demo(salida, segundos=8.0):
    """Un loop de 8 s (4 compases a 120 ppm: La menor, Fa, Do, Sol) hecho con senos, para probar la música de fondo sin usar
    canciones de nadie. Termina donde empieza, así se puede repetir sin salto."""
    sr = SR
    n = int(segundos * sr)
    acordes = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)]
    compas = segundos / len(acordes)
    m = [0.0] * n
    for c, notas in enumerate(acordes):
        a, b = int(c * compas * sr), int((c + 1) * compas * sr)
        for k in range(a, b):
            x, t = (k - a) / (b - a), k / sr
            env = min(1.0, x * 12) * (1 - x) ** 0.5
            m[k] += 0.09 * env * sum(math.sin(2 * math.pi * f * t) for f in notas)
        for paso in range(8):  # arpegio en corcheas, una octava arriba
            f = notas[paso % 3] * 2 * (2 if paso in (3, 7) else 1)
            i0 = a + int(paso * compas / 8 * sr)
            largo = int(compas / 8 * sr * 0.9)
            for k in range(i0, min(i0 + largo, n)):
                x, t = (k - i0) / largo, (k - i0) / sr
                m[k] += 0.08 * math.exp(-x * 5) * math.sin(2 * math.pi * f * t)
        for golpe in range(4):  # bombo suave en cada tiempo
            i0 = a + int(golpe * compas / 4 * sr)
            for k in range(i0, min(i0 + int(0.12 * sr), n)):
                t = (k - i0) / sr
                m[k] += 0.22 * math.exp(-t * 30) * math.sin(2 * math.pi * (55 + 90 * math.exp(-t * 40)) * t)
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "musica.wav")
        with wave.open(wav, "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 30000)) for s in m))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1",
                        "-map_metadata", "-1", salida], check=True)


def catalogo_demo():
    """Los efectos de la comunidad que muestra la vista previa: los del catálogo si está al lado (../corta-catalogo), si no los de antes."""
    indice = os.path.join(RAIZ, "..", "corta-catalogo", "efectos", "index.json")
    if os.path.exists(indice):
        with open(indice, encoding="utf-8") as f:
            return efectos.validar_indice(json.load(f))
    with open(os.path.join(RAIZ, "ui", "demo.json"), encoding="utf-8") as f:
        return json.load(f).get("catalogo", [])


def catalogo_plantillas_demo():
    """Las plantillas de la comunidad que muestra la vista previa: las del catálogo si está al lado, si no las de antes."""
    indice = os.path.join(RAIZ, "..", "corta-catalogo", "plantillas", "index.json")
    if os.path.exists(indice):
        with open(indice, encoding="utf-8") as f:
            return plantillas.validar_indice(json.load(f))
    with open(os.path.join(RAIZ, "ui", "demo.json"), encoding="utf-8") as f:
        return json.load(f).get("catalogo_plantillas", [])


def fotos_demo(carpeta):
    """Dos «fotos» dibujadas (una taza y un pastel, sin personas ni lugares reales) para llenar plantillas en la vista previa."""
    for nombre, fondo, dibujo in (("foto-1.jpg", ((247, 214, 170), (196, 120, 80)), "taza"), ("foto-2.jpg", ((190, 220, 240), (120, 90, 170)), "pastel")):
        im = Image.new("RGB", (720, 960))
        d = ImageDraw.Draw(im)
        for y in range(960):
            a = y / 959
            d.line([(0, y), (720, y)], fill=tuple(int(fondo[0][k] * (1 - a) + fondo[1][k] * a) for k in range(3)))
        if dibujo == "taza":
            d.ellipse((170, 640, 550, 720), fill=(250, 245, 235))
            d.rounded_rectangle((230, 380, 490, 660), 40, fill=(255, 255, 250))
            d.arc((450, 440, 570, 580), -90, 90, fill=(255, 255, 250), width=26)
            d.ellipse((250, 360, 470, 410), fill=(110, 70, 45))
            for k in range(3):
                d.arc((270 + k * 60, 200, 330 + k * 60, 340), 200, 340, fill=(255, 255, 255), width=8)
        else:
            d.rounded_rectangle((180, 470, 540, 720), 24, fill=(255, 240, 245))
            d.rectangle((180, 560, 540, 600), fill=(240, 120, 150))
            d.ellipse((170, 430, 550, 510), fill=(255, 250, 252))
            for k in range(3):
                x = 270 + k * 90
                d.rectangle((x, 330, x + 16, 450), fill=(120, 200, 230))
                d.ellipse((x - 6, 296, x + 22, 336), fill=(255, 200, 60))
        im = im.filter(ImageFilter.GaussianBlur(1.2))
        im.save(os.path.join(carpeta, nombre), quality=82)


def solo_plantillas():
    demo_dir = os.path.join(RAIZ, "ui", "demo")
    fotos_demo(demo_dir)
    ruta = os.path.join(RAIZ, "ui", "demo.json")
    with open(ruta, encoding="utf-8") as f:
        demo = json.load(f)
    demo["efectos"] = list(efectos.disponibles().values())
    demo["catalogo"] = catalogo_demo()
    demo["plantillas"] = list(plantillas.disponibles().values())
    demo["catalogo_plantillas"] = catalogo_plantillas_demo()
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    if "--solo-plantillas" in sys.argv:
        solo_plantillas()
        return print("✓ fotos y plantillas de la demo")
    if "--solo-musica" in sys.argv:
        musica_demo(os.path.join(RAIZ, "ui", "demo", "musica-demo.mp3"))
        return print("✓ música de la demo")
    palabras, duracion = tiempos()
    demo_dir = os.path.join(RAIZ, "ui", "demo")
    os.makedirs(demo_dir, exist_ok=True)
    video(palabras, duracion, os.path.join(demo_dir, "ana.mp4"))
    musica_demo(os.path.join(demo_dir, "musica-demo.mp3"))
    fotos_demo(demo_dir)
    p = proyecto.nuevo("Ahorra una hora editando", {"archivo": "demo/ana.mp4", "ancho": W, "alto": H, "duracion": duracion})
    p["encuadre"] = {"x": 0.45, "y": 0.5}
    p["palabras"] = palabras
    p["creado"] = "2026-10-25T20:00:00"
    assert not proyecto.validar(p), proyecto.validar(p)
    estilos = {e["id"]: e for e in subtitulos.estilos().values()}
    demo = {"version": "0.1.0", "carpeta": "~/Corta", "config": {"ia": "claude", "bienvenida": True},
            "ias": [{"id": "claude", "nombre": "Claude", "instalada": True}, {"id": "codex", "nombre": "ChatGPT (Codex)", "instalada": True},
                    {"id": "gemini", "nombre": "Gemini", "instalada": False}],
            "modelos": {"recomendado": "turbo", "lista": [{"id": "turbo", "nombre": "Preciso", "detalle": "Mejor para cualquier idioma. 574 MB.", "mb": 574, "listo": True},
                                                          {"id": "small", "nombre": "Rápido", "detalle": "Más liviano, un poco menos preciso. 190 MB.", "mb": 190, "listo": False}]},
            "estilos": list(estilos.values()), "efectos": list(efectos.disponibles().values()), "catalogo": catalogo_demo(),
            "plantillas": list(plantillas.disponibles().values()), "catalogo_plantillas": catalogo_plantillas_demo(),
            "vocabulario": {"formato": 1, "reemplazos": [], "palabras": []},
            "proyectos": [{"carpeta": "~/Corta/2026-10-25 Ahorra una hora editando", "proyecto": p},
                          {"carpeta": "~/Corta/2026-10-24 Mi rutina de mañana", "proyecto": {**p, "titulo": "Mi rutina de mañana", "palabras": [], "creado": "2026-10-24T09:10:00"}}]}
    with open(os.path.join(RAIZ, "ui", "demo.json"), "w", encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # Pruebas: una copia corta (los primeros 9 segundos) con sus palabras.
    corto = os.path.join(RAIZ, "pruebas", "datos", "ana-corto.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(demo_dir, "ana.mp4"), "-t", "9", "-vf", "scale=640:360",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "32", "-c:a", "aac", "-b:a", "48k", corto], check=True)
    with open(os.path.join(RAIZ, "pruebas", "datos", "ana-corto.json"), "w", encoding="utf-8") as f:
        json.dump([w for w in palabras if w["f"] <= 9], f, ensure_ascii=False, indent=1)
    print(f"✓ demo: {duracion:.1f} s, {len(palabras)} palabras")


if __name__ == "__main__":
    main()
