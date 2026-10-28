"""Exportar: aplica cortes, encuadre, zooms, subtítulos, textos y música con ffmpeg. Solo biblioteca estándar.

  render.py <carpeta> <salida.json>          deja exportado-<lienzo>.mp4 en la carpeta

El avance queda en <carpeta>/estado.json ({"paso": "exportando", "pct"}). El video original nunca se modifica.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proyecto  # noqa: E402
import subtitulos  # noqa: E402

FUENTES = os.path.join(proyecto.RECURSOS, "ui", "fuentes")


def ffmpeg():
    return proyecto.programa("ffmpeg")


def tiene_audio(video):
    r = subprocess.run([proyecto.programa("ffprobe"), *proyecto.SOLO_ARCHIVOS, "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", proyecto.entrada(video)],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def piezas(p):
    """Los tramos conservados, partidos donde empieza o termina un zoom: cada pieza lleva su escala."""
    zooms = sorted(p.get("zooms", []), key=lambda z: z["i"])
    r = []
    for t in proyecto.conservados(p):
        bordes = {t["i"], t["f"]}
        for z in zooms:
            for b in (z["i"], z["f"]):
                if t["i"] < b < t["f"]:
                    bordes.add(b)
        puntos = sorted(bordes)
        for a, b in zip(puntos, puntos[1:]):
            if b - a < 0.04:
                continue
            medio = (a + b) / 2
            escala = max([z["escala"] for z in zooms if z["i"] <= medio <= z["f"]] or [1])
            r.append({"i": round(a, 3), "f": round(b, 3), "escala": escala})
    return r


def par(n):
    return int(math.ceil(n / 2) * 2)


def encuadre(p, ancho, alto):
    """Filtros para llevar el video original al lienzo elegido (cubrir y recortar, o fondo desenfocado)."""
    W, H = proyecto.LIENZOS[p["lienzo"]]
    if p["relleno"] == "desenfoque":
        s_fondo = max(W / ancho, H / alto)
        s_frente = min(W / ancho, H / alto)
        fw, fh = par(ancho * s_frente), par(alto * s_frente)
        return (f"split[f1][f2];[f1]scale={par(ancho * s_fondo)}:{par(alto * s_fondo)},crop={W}:{H},boxblur=40:2,eq=brightness=-0.08[fondo];"
                f"[f2]scale={fw}:{fh}[frente];[fondo][frente]overlay=({W}-w)/2:({H}-h)/2")
    s = max(W / ancho, H / alto)
    nw, nh = par(ancho * s), par(alto * s)
    x = round((nw - W) * p["encuadre"]["x"])
    y = round((nh - H) * p["encuadre"]["y"])
    return f"scale={nw}:{nh},crop={W}:{H}:{x}:{y}"


def grafo(p, con_audio, ruta_ass, con_musica):
    W, H = proyecto.LIENZOS[p["lienzo"]]
    fuente = p["fuente"]
    marco = encuadre(p, fuente["ancho"], fuente["alto"])
    partes, etiquetas = [], []
    for k, pz in enumerate(piezas(p)):
        v = f"[0:v]trim=start={pz['i']}:end={pz['f']},setpts=PTS-STARTPTS,fps=30,{marco}"
        if pz["escala"] > 1:
            zw, zh = par(W * pz["escala"]), par(H * pz["escala"])
            v += f",scale={zw}:{zh},crop={W}:{H}"
        partes.append(v + f",setsar=1[v{k}]")
        if con_audio:
            partes.append(f"[0:a]atrim=start={pz['i']}:end={pz['f']},asetpts=PTS-STARTPTS,aresample=48000[a{k}]")
        else:
            partes.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={pz['f'] - pz['i']}[a{k}]")
        etiquetas.append(f"[v{k}][a{k}]")
    n = len(etiquetas)
    if not n:
        raise ValueError("No queda nada del video: quita algunos cortes.")
    partes.append("".join(etiquetas) + f"concat=n={n}:v=1:a=1[vc][ac]")
    ass = ruta_ass.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    dir_fuentes = FUENTES.replace("\\", "/").replace(":", r"\:")
    partes.append(f"[vc]ass='{ass}':fontsdir='{dir_fuentes}'[vs]")
    if con_musica:
        vol = p["musica"].get("volumen", 0.15)
        # La música baja sola cuando hay voz (sidechain), para que nunca tape lo que se dice.
        partes.append(f"[1:a]aloop=loop=-1:size=2e9,volume={vol},aresample=48000[m];[ac]asplit[voz][guia];"
                      f"[m][guia]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[mb];"
                      f"[voz][mb]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[as]")
    else:
        partes.append("[ac]anull[as]")
    return ";".join(partes)


def exportar(carpeta, al_avanzar=None):
    p = proyecto.cargar(carpeta)
    estilos = subtitulos.estilos()
    estilo = estilos.get(p["subtitulos"]["estilo"]) or estilos.get("pop") or next(iter(estilos.values()))
    W, H = proyecto.LIENZOS[p["lienzo"]]
    video = os.path.join(carpeta, p["fuente"]["archivo"])
    musica = None
    if p.get("musica"):
        musica = p["musica"]["archivo"] if os.path.isabs(p["musica"]["archivo"]) else os.path.join(carpeta, p["musica"]["archivo"])
        if not os.path.exists(musica):
            musica = None
    salida = os.path.join(carpeta, f"exportado-{p['lienzo'].replace(':', 'x')}.mp4")
    total = proyecto.duracion_final(p)
    with tempfile.TemporaryDirectory(prefix="corta-") as tmp:
        ruta_ass = os.path.join(tmp, "subtitulos.ass")
        with open(ruta_ass, "w", encoding="utf-8") as f:
            f.write(subtitulos.ass(p, estilo, W, H))
        grafo_txt = os.path.join(tmp, "grafo.txt")
        with open(grafo_txt, "w", encoding="utf-8") as f:
            f.write(grafo(p, tiene_audio(video), ruta_ass, bool(musica)))
        temporal = os.path.join(tmp, "salida.mp4")
        # Solo archivos locales como entrada (-protocol_whitelist file, con «file:» delante de cada ruta).
        cmd = [ffmpeg(), "-hide_banner", "-y", "-nostats", *proyecto.SOLO_ARCHIVOS, "-i", proyecto.entrada(video)]
        if musica:
            cmd += [*proyecto.SOLO_ARCHIVOS, "-i", proyecto.entrada(musica)]
        cmd += ["-filter_complex_script", grafo_txt, "-map", "[vs]", "-map", "[as]", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                "-progress", "pipe:1", temporal]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for linea in proc.stdout:
            m = re.match(r"out_time_us=(\d+)", linea)
            if m and total:
                pct = min(99, int(int(m.group(1)) / 1e6 / total * 100))
                proyecto.escribir_json(os.path.join(carpeta, "estado.json"), {"paso": "exportando", "pct": pct})
                if al_avanzar:
                    al_avanzar(pct)
        error = proc.stderr.read()
        if proc.wait() != 0 or not os.path.exists(temporal):
            raise RuntimeError("ffmpeg no pudo exportar: " + error.strip().splitlines()[-1][:300] if error.strip() else "ffmpeg falló.")
        shutil.move(temporal, salida)
    try:
        os.remove(os.path.join(carpeta, "estado.json"))
    except OSError:
        pass
    return {"ok": True, "archivo": salida, "duracion": total, "lienzo": p["lienzo"]}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    try:
        r = exportar(sys.argv[1])
    except (OSError, ValueError, RuntimeError) as e:
        r = {"ok": False, "error": str(e)}
    proyecto.escribir_json(sys.argv[2], r)
    print(json.dumps(r, ensure_ascii=False))
