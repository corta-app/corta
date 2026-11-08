#!/usr/bin/env python3
"""Contrato entre la interfaz (ui/app.js) y la app nativa (escritorio/, pieza «host-tauri»).

Revisa: 1) cada host.enviar("x") de la interfaz (y de la pieza «componentes») lo responde la vista previa del navegador (simular() o,
para las comunes, PiezaHost.simulacionesComunes de ui/host.js); 2) la app atiende cada acción: registrada en escritorio/src
(`registrar("x")`: lo nativo de Corta), del host (listo, config, abrirEnlace, copiar y, con la pieza «actualizaciones»,
buscarActualizacion y actualizar) o declarada en acciones.json (las que solo corren un script: app.json → «acciones» y las de las
piezas); 3) toda función que llama la app existe en window.Corta (host.responder de ui/app.js); 4) acciones.json está al día con
app.json, sus scripts existen y la carpeta de un proyecto pasa siempre por el host (inyector «proyecto»); 5) los scripts que nombra
la app existen en bin/; 6) la seguridad que trae la pieza y que Corta no arma otra ventana ni otro puente; 7) los medios por
host.medio."""
import glob
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer(r):
    ruta = os.path.join(RAIZ, r)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def tiene(texto, *patrones):
    return all(re.search(p, texto or "", re.S) for p in patrones)


def internas(texto, patron):
    """Lo que calza con el patrón, sin contar los comentarios (los ejemplos de las piezas nombran acciones que no existen)."""
    sin_comentarios = re.sub(r"^\s*(//|///|\*).*$", "", texto or "", flags=re.M)
    return set(re.findall(patron, sin_comentarios))


ui = leer("ui/app.js")
acciones = set(re.findall(r'host\.enviar\("(\w+)"', ui))
acciones |= set(re.findall(r'\benviar\("(\w+)"', leer("ui/componentes.js") or ""))
cuerpo = ui.split("host.responder({", 1)[1].split("\n  });", 1)[0]
funciones_ui = set(re.findall(r"^\s{4}(?:async\s+)?(\w+)\(", cuerpo, re.M))
problemas = []

# 1) La vista previa del navegador responde cada acción en simular() (aunque sea con un aviso «en la app, aquí…»).
simulado = ui.split("function simular(", 1)[1].split("\n  }\n", 1)[0]
casos_web = set(re.findall(r'case "(\w+)"', simulado))
if "simulacionesComunes()" in ui:  # las de la pieza «host-ui»
    comunes = (leer("ui/host.js") or "").split("function simulacionesComunes", 1)[1].split("\n  }\n", 1)[0]
    casos_web |= set(re.findall(r"^\s{6}(\w+): \(d, c\)", comunes, re.M))
problemas += [f'La vista previa (simular) no responde la acción "{a}"' for a in sorted(acciones - casos_web)]

# 4) Las acciones declaradas (acciones.json, lo arma pieza.py con app.json → «acciones» y las de las piezas).
app_json = json.loads(leer("app.json"))
acciones_json = json.loads(leer("acciones.json") or "{}").get("acciones") or {}
declaradas = set(acciones_json)
for n, d in (app_json.get("acciones") or {}).items():
    if {k: v for k, v in d.items() if k != "scriptDeLaApp"} != {k: v for k, v in acciones_json.get(n, {}).items() if k != "pieza"}:
        problemas.append(f'acciones.json no está al día con app.json en «{n}»: python3 <pieza>/herramientas/pieza.py acciones .')
for n in app_json.get("sin_acciones") or []:
    if n in acciones:
        problemas.append(f'app.json: «{n}» está en sin_acciones y la interfaz la usa')
respuestas_declaradas = set()
for n, d in acciones_json.items():
    if not os.path.exists(os.path.join(RAIZ, "bin", d.get("script", ""))):
        problemas.append(f'la acción declarada «{n}» usa bin/{d.get("script")}, que no existe')
    for f in (d.get("responde"), d.get("progreso")):
        if f:
            respuestas_declaradas.add(f)
            if f not in funciones_ui:
                problemas.append(f'la acción declarada «{n}» responde «{f}» y window.Corta no la tiene')
    # La carpeta de un proyecto la manda la interfaz (una ruta de ~/Corta): el host la revisa antes de correr (Rutas.proyecto, con el
    # inyector «proyecto»; si no es un proyecto, responde «falta» y el script no corre) y el script la vuelve a revisar.
    if "carpeta" in (d.get("datos") or {}) and (d.get("inyectar") or {}).get("carpeta_real") != "proyecto":
        problemas.append(f'«{n}»: la carpeta de un proyecto pasa por el inyector «proyecto» del host (inyectar: {{"carpeta_real": "proyecto"}})')
for n in ("guardarProyecto", "deshacer", "limpiar", "vocabulario"):
    if (acciones_json.get(n) or {}).get("cola") != "escritura":
        problemas.append(f'«{n}» va en la fila (cola: "escritura"): los cambios a un proyecto, de a uno y en orden')

# 2, 3, 5, 6) La app nativa (pieza «host-tauri», Rust): cada acción la atiende uno de tres lados, en este orden: lo que registra
#    Corta (`registrar("x")` en escritorio/src, fuera de pieza/), lo que trae el host (sus internas en escritorio/src/pieza/host.rs:
#    listo, config, abrirEnlace, copiar y, con `actualizaciones`, buscarActualizacion y actualizar) y lo declarado en acciones.json.
def juntar(patron):
    return "\n".join(open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(RAIZ, patron))))


def sin_comentarios(t):
    return re.sub(r"^\s*(//|///|//!).*$", "", t or "", flags=re.M)


def bloque(texto, inicio):
    i = texto.find(inicio)
    if i < 0:
        return ""
    j, n = texto.index("{", i), 0
    for k in range(j, len(texto)):
        n += {"{": 1, "}": -1}.get(texto[k], 0)
        if n == 0:
            return texto[j:k + 1]
    return ""


rust = sin_comentarios(juntar("escritorio/src/*.rs"))
host_rs = sin_comentarios(leer("escritorio/src/pieza/host.rs"))
procesador_rs = leer("escritorio/src/pieza/procesador.rs") or ""
registradas = set(re.findall(r'\.registrar\("(\w+)"', rust))
del_host = set(re.findall(r'^\s*"(\w+)"(?:\s*\|\s*"\w+")*(?:\s+if\s[^=]*)?\s*=>', bloque(host_rs, "fn interna("), re.M))
del_host |= {x for linea in re.findall(r'^\s*("\w+"(?:\s*\|\s*"\w+")+)', bloque(host_rs, "fn interna("), re.M) for x in re.findall(r'"(\w+)"', linea)}
if not re.search(r"^\s*actualizaciones:\s", rust, re.M):
    del_host -= {"buscarActualizacion", "actualizar"}
if not rust or not host_rs:
    problemas.append("Falta la app nativa (escritorio/src) o la pieza «host-tauri» (escritorio/src/pieza)")
atiende = registradas | del_host | declaradas
problemas += [f'La app no atiende la acción "{a}" (ni registrada, ni del host, ni declarada)' for a in sorted(acciones - atiende)]
problemas += [f'La app registra "{a}" y la interfaz nunca la pide' for a in sorted(registradas - acciones)]
problemas += [f'"{a}" está registrada y también declarada: gana la registrada (sácala de una)' for a in sorted(registradas & declaradas)]
# Lo que la app llama en window.Corta: responder/llamar("x") en Rust, lo de las declaradas y lo que el host manda siempre (estado,
# menu, soltados con `soltar: true`) o con las actualizaciones.
llamadas = set(re.findall(r'(?:llamar|responder)\((?:&?h2?, )?"(\w+)"', rust)) | {"estado", "menu", "soltados", "soltando", "actualizacionRevisada", "actualizacionProgreso"}
problemas += [f"La app llama window.Corta.{f} y la interfaz no la tiene" for f in sorted((llamadas | respuestas_declaradas) - funciones_ui)]
scripts = set(re.findall(r'(?:correr_json|con_entrada|correr)\("(\w+\.py)"', rust))
problemas += [f"La app llama bin/{s} y no existe" for s in sorted(scripts) if not os.path.exists(os.path.join(RAIZ, "bin", s))]
recursos = ((json.loads(leer("escritorio/tauri.conf.json") or "{}").get("bundle") or {}).get("resources") or {})
for r in ("app.json", "acciones.json", "bin/", "ui/", "estilos/", "efectos/", "plantillas/"):
    if recursos.get(f"../{r}") != f"recursos/{r}":
        problemas.append(f"escritorio/tauri.conf.json no lleva {r} dentro de la app (app.json → empaquetado.carpetas)")
# La seguridad que trae la pieza: el puente solo para la ventana propia con su página en ui/, la ventana nunca navega fuera, scripts
# con límite, sin CORTA_* de afuera y con los programas de la app en CORTA_HERRAMIENTAS.
if not tiene(host_rs, r"let en_ui = webview\.url\(\)", r"on_navigation", r"fn puente_js") \
        or not tiene(procesador_rs, r"starts_with\(&self\.prefijo\)", r"HERRAMIENTAS", r"grupo_propio"):
    problemas.append("La pieza «host-tauri» cambió: el puente solo para la ventana propia, sin navegar fuera de ui/, scripts con límite y sin CORTA_* de afuera")
if re.search(r"WebviewWindowBuilder|invoke_handler|register_uri_scheme_protocol", rust):
    problemas.append("La ventana, el puente y los medios los pone la pieza «host-tauri» (Corta no arma otros)")
if not tiene(rust, r'registrar_medios\("video"', r'inyector\("proyecto"', r"fn proyecto_en.*?proyecto\.json", r"soltar: true",
             r'Actualizaciones::nuevas\("corta-app/corta", "Corta"\)'):
    problemas.append("La app: medios «video» (solo lo de un proyecto), la carpeta de un proyecto por el inyector «proyecto», soltar y actualizaciones desde corta-app/corta")
if not tiene(leer("escritorio/src/medios.rs"), r'"musica" \| "clips"', r'fuente.*?"archivo"', r"starts_with\(&raiz\)"):
    problemas.append("escritorio/src/medios.rs: solo el video, la música o los clips de un proyecto de ~/Corta")
if re.search(r'"--disallowedTools"|"--strict-mcp-config"|"(claude|codex)"\s*,', rust):
    problemas.append("La app no llama a la IA por su cuenta (la corre bin/ia.py, pieza «ia»)")
if not tiene(leer("app.json"), r'"whisper": true') or "whisper-cli" not in (leer("escritorio/herramientas/preparar.sh") or ""):
    problemas.append("app.json → empaquetado.whisper: la app lleva whisper-cli (pieza «empaquetado»)")

# 7) Los medios se piden con host.medio (pieza «host-ui»), nunca con una dirección armada a mano.
if app_json.get("id") != "corta" or 'host.medio("video"' not in ui or re.search(r"corta://", ui):
    problemas.append('La interfaz pide el video, la música y los clips con host.medio("video", …) (escritorio/src/medios.rs)')
if problemas:
    print("✗ Contrato roto:\n  - " + "\n  - ".join(problemas))
    sys.exit(1)
print(f"✓ Contrato: {len(acciones)} acciones ({len(registradas)} registradas, {len(del_host & acciones)} del host, {len(declaradas & acciones)} declaradas) "
      f"y {len(funciones_ui)} funciones en orden")
