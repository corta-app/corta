"""Exportar: aplica cortes, encuadre, zooms, velocidad, efectos (bin/efectos.py), subtítulos, textos y música con ffmpeg. Solo biblioteca
estándar.

  render.py <carpeta> <salida.json>          deja exportado-<lienzo>.mp4 en la carpeta

El avance queda en <carpeta>/estado.json ({"paso": "exportando", "pct"}). El video original nunca se modifica.

Lista blanca de filtros de ffmpeg de este grafo (más los de bin/efectos.py), siempre con números que calcula el código:
  trim, setpts, fps, scale, crop, split, boxblur, eq, overlay, setsar, format, ass     cada pieza, el encuadre y los subtítulos
  atrim, asetpts, aresample, anullsrc, concat, anull, aloop, volume, asplit, sidechaincompress, amix   voz y música
  tpad, framerate, minterpolate, atempo, apad                                         velocidad por tramo (cámara lenta y rápida)
La música se agrega después de unir las piezas: nunca se acelera ni se pone lenta.
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
import efectos  # noqa: E402
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
    """Los tramos conservados, partidos donde empieza o termina un zoom o una velocidad: cada pieza lleva su escala y su
    velocidad (`vel`: el tramo de `velocidades` que la cubre, o None)."""
    zooms = sorted(p.get("zooms", []), key=lambda z: z["i"])
    vels = proyecto.velocidades(p)
    r = []
    for t in proyecto.conservados(p):
        bordes = {t["i"], t["f"]}
        for x in zooms + vels:
            for b in (x["i"], x["f"]):
                if t["i"] < b < t["f"]:
                    bordes.add(b)
        puntos = sorted(bordes)
        for a, b in zip(puntos, puntos[1:]):
            if b - a < 0.04:
                continue
            medio = (a + b) / 2
            escala = max([z["escala"] for z in zooms if z["i"] <= medio <= z["f"]] or [1])
            vel = next((e for e in vels if e["i"] <= medio < e["f"]), None)
            r.append({"i": round(a, 3), "f": round(b, 3), "escala": escala, "vel": vel})
    return r


def _n(x):
    """Número para el grafo de ffmpeg: siempre dígitos, punto y signo (nunca texto)."""
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def atempo(v):
    """La voz más rápida o más lenta sin cambiar el tono: atempo encadenado, cada uno entre 0,5 y 2 (donde suena mejor)."""
    r = []
    while v < 0.5 - 1e-9:
        r.append("atempo=0.5")
        v /= 0.5
    while v > 2 + 1e-9:
        r.append("atempo=2")
        v /= 2
    if abs(v - 1) > 1e-6:
        r.append(f"atempo={_n(v)}")
    return r


def tiempo_vel(e, a):
    """setpts de una pieza que empieza en el segundo a del original y cae en el tramo de velocidad `e` (después de
    setpts=PTS-STARTPTS): cada cuadro va al segundo del exportado que le toca (`proyecto.lento`, la misma cuenta)."""
    if not e.get("rampa"):
        return f"setpts=PTS/{_n(e['v'])}"
    d = e["f"] - e["i"]
    lado, k = d * proyecto.RAMPA_LADO, 1 / e["v"]
    x = f"({_n(a - e['i'])}+T)"
    y1 = f"({x}/{_n(lado)})"
    y3 = f"(({x}-{_n(d - lado)})/{_n(lado)})"
    curva = lambda y: f"({y}*{y}*{y}-{y}*{y}*{y}*{y}/2)"  # noqa: E731
    sube = lado * (1 + k) / 2
    r1 = f"{x}+{_n((k - 1) * lado)}*{curva(y1)}"
    r2 = f"{_n(sube)}+({x}-{_n(lado)})*{_n(k)}"
    r3 = f"{_n(sube + (d - 2 * lado) * k)}+{_n(k)}*({x}-{_n(d - lado)})+{_n((1 - k) * lado)}*{curva(y3)}"
    w0 = proyecto._integral(e, a)
    return f"setpts='(if(lte({x},{_n(lado)}),{r1},if(lte({x},{_n(d - lado)}),{r2},{r3}))-{_n(w0)})/TB'"


#: Cámara lenta fluida (`suavizar`): «mezcla» funde cada cuadro con el siguiente (framerate: cuesta casi nada) y «movimiento»
#: inventa los cuadros que faltan siguiendo el movimiento (minterpolate, compensación bilateral con búsqueda corta: la forma
#: eficiente). Medido con pruebas/velocidad.mjs (8 s de 1280×720 a 1080×1920, 2 núcleos): 1× 3 s; 0,5× 5,6 s; 0,25× 10 s; 0,25×
#: con «mezcla» 11 s; 2× 1,6 s; 3× 1,5 s; rampa a 0,3× 6–9 s; 0,5× con «movimiento» 74 s (unas 13 veces más que «mezcla»). Por eso
#: «mezcla» es la de siempre y «movimiento» es opcional («Más fluido»).
SUAVIZAR = {"mezcla": "framerate=fps=30", "movimiento": "minterpolate=fps=30:mi_mode=mci:mc_mode=obmc:me_mode=bilat:search_param=8"}


def tramos_audio(e, a, b, pasos=8):
    """La voz de una rampa va en escalones (atempo no cambia de velocidad por sí solo): cada lado de la rampa en `pasos` pedazos,
    cada uno a su velocidad media, así dura justo lo mismo que la imagen. → [(c, d), …] dentro de a..b."""
    d = e["f"] - e["i"]
    lado = d * proyecto.RAMPA_LADO
    bordes = {a, b}
    for j in range(pasos + 1):
        for x in (e["i"] + lado * j / pasos, e["f"] - lado + lado * j / pasos):
            if a < x < b:
                bordes.add(x)
    puntos = sorted(bordes)
    return [(c, dd) for c, dd in zip(puntos, puntos[1:]) if dd - c > 0.001]


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
    vels = proyecto.velocidades(p)
    for k, pz in enumerate(piezas(p)):
        e = pz["vel"]
        # Con velocidad: cada cuadro va a su segundo del exportado (setpts), la cámara lenta se puede suavizar y la pieza dura
        # justo lo que dice proyecto.lento (tpad repite el último cuadro si faltara uno; trim corta lo que sobre).
        largo = _n(proyecto.lento(vels, pz["i"], pz["f"]))
        v = f"[0:v]trim=start={pz['i']}:end={pz['f']},setpts=PTS-STARTPTS"
        if e:
            v += "," + tiempo_vel(e, pz["i"]) + ("," + SUAVIZAR[e["suavizar"]] if e.get("suavizar") in SUAVIZAR else "")
        v += ",fps=30" + (f",tpad=stop_mode=clone:stop_duration=0.2,trim=end={largo}" if e else "") + f",{marco}"
        if pz["escala"] > 1:
            zw, zh = par(W * pz["escala"]), par(H * pz["escala"])
            v += f",scale={zw}:{zh},crop={W}:{H}"
        partes.append(v + f",setsar=1,format=yuv420p[v{k}]")
        recorte = f"[0:a]atrim=start={pz['i']}:end={pz['f']},asetpts=PTS-STARTPTS,aresample=48000"
        justo = f"apad=whole_dur={largo},atrim=end={largo}"
        if not con_audio:
            partes.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={largo if e else pz['f'] - pz['i']}[a{k}]")
        elif not e:
            partes.append(recorte + f"[a{k}]")
        elif proyecto.audio_de(e) == "silencio":
            partes.append(recorte + f",volume=0,{justo}[a{k}]")
        elif not e.get("rampa"):
            partes.append(",".join([recorte, *atempo(e["v"]), justo]) + f"[a{k}]")
        else:
            trozos = tramos_audio(e, pz["i"], pz["f"])
            for j, (c, d) in enumerate(trozos):
                partes.append(",".join([f"[0:a]atrim=start={_n(c)}:end={_n(d)},asetpts=PTS-STARTPTS,aresample=48000",
                                        *atempo((d - c) / proyecto.lento(vels, c, d))]) + f"[a{k}r{j}]")
            partes.append("".join(f"[a{k}r{j}]" for j in range(len(trozos))) + f"concat=n={len(trozos)}:v=0:a=1,{justo}[a{k}]")
        etiquetas.append(f"[v{k}][a{k}]")
    n = len(etiquetas)
    if not n:
        raise ValueError("No queda nada del video: quita algunos cortes.")
    partes.append("".join(etiquetas) + f"concat=n={n}:v=1:a=1[vc][ac]")
    # Efectos y filtros (solo datos validados → lista blanca de filtros), antes de los subtítulos: nunca se desenfocan ni se mueven.
    fx, video = efectos.cadena(p, W, H, "[vc]")
    partes += fx
    ass = ruta_ass.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    dir_fuentes = FUENTES.replace("\\", "/").replace(":", r"\:")
    partes.append(f"{video}ass='{ass}':fontsdir='{dir_fuentes}'[vs]")
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
