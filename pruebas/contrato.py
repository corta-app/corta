#!/usr/bin/env python3
"""Contrato entre la interfaz (ui/app.js) y la app de Mac.

Revisa: 1) cada host.enviar("x") de la interfaz (y de la pieza «componentes») lo responde la vista previa del navegador (simular() o,
para las comunes, PiezaHost.simulacionesComunes de ui/host.js); 2) la app de Mac atiende cada acción: registrada en app/Sources/Corta
(`registrar("x")`: lo nativo de Corta), del host (pieza «host-mac»: listo, config, abrirEnlace, copiar y, con la pieza
«actualizaciones», buscarActualizacion y actualizar) o declarada en acciones.json (las que solo corren un script: app.json →
«acciones» y las de las piezas); 3) toda función que llama la app (las de Swift, las del host y el «responde» de cada declarada)
existe en window.Corta (host.responder de ui/app.js); 4) acciones.json está al día con app.json, sus scripts existen y la carpeta de un
proyecto pasa siempre por el host (inyector «proyecto»); 5) los scripts que nombra Swift existen en bin/; 6) la seguridad que trae la
pieza (puente solo para el marco principal con un archivo de ui/, navegación solo dentro de ui/, scripts con límite y sin CORTA_* de
afuera, actualizaciones solo desde los Releases con huella) y que Corta no arma otra ventana ni otro puente; 7) el video por corta://."""
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

# 2, 3, 5, 6) La app de Mac: pieza «host-mac» (app/Sources/PiezaHost) + lo propio de Corta (app/Sources/Corta).
carpeta_swift = os.path.join(RAIZ, "app/Sources/Corta")
swift = "".join(leer(os.path.join("app/Sources/Corta", n)) for n in sorted(os.listdir(carpeta_swift)) if n.endswith(".swift"))
puente_mac = leer("app/Sources/PiezaHost/Puente.swift") or ""
host_mac = "".join(leer(f"app/Sources/PiezaHost/{n}.swift") or "" for n in ("Host", "Procesador", "Enchufe")) + puente_mac
registradas = internas(swift, r'registrar\("(\w+)"')
del_host = internas(puente_mac, r'internas\["(\w+)"\]')
atiende = registradas | del_host | declaradas
problemas += [f'Mac no atiende la acción "{a}" (ni registrada, ni del host, ni declarada)' for a in sorted(acciones - atiende)]
problemas += [f'Mac registra "{a}" y la interfaz nunca la pide' for a in sorted(registradas - acciones)]
problemas += [f'"{a}" está registrada y también declarada: gana la registrada (sácala de una)' for a in sorted(registradas & declaradas)]
llamadas = internas(swift, r'llamar\("(\w+)"') | internas(puente_mac, r'llamar\("(\w+)"')
if "copiar" not in acciones:
    llamadas.discard("copiado")  # del host, solo si la interfaz pide «copiar» (Corta no la usa)
problemas += [f"Mac llama window.Corta.{f} y la interfaz no la tiene" for f in sorted((llamadas | respuestas_declaradas) - funciones_ui)]
scripts = internas(swift, r'(?:correrJSON|conEntrada)\("(\w+\.py)"')
problemas += [f"La app llama bin/{s} y no existe" for s in sorted(scripts) if not os.path.exists(os.path.join(RAIZ, "bin", s))]
if not tiene(puente_mac, r"frameInfo\.isMainFrame", r'securityOrigin\.protocol == "file"', r"hasPrefix\(prefijoUI\)", r"decidePolicyFor",
             r'u\.scheme == "https"', r'runOpenPanelWith.*?marco\.isMainFrame, marco\.securityOrigin\.protocol == "file"'):
    problemas.append("Mac: el puente de la pieza «host-mac» atiende solo al marco principal con un archivo de ui/ y no navega fuera (Puente.swift)")
if re.search(r"WKWebView\(|WKScriptMessageHandler|NSApplicationDelegate|WKURLSchemeHandler", swift):
    problemas.append("Mac: la ventana, el puente, los medios y el delegado los pone la pieza «host-mac» (Corta no arma otros)")
if not tiene(host_mac, r"hasPrefix\(prefijo\)", r"matarArbol", r"latidoMuerto") or not tiene(swift, r"Host\.arrancar\(", r'registrarMedios\("video"\)',
                                                                                           r'inyectores\["proyecto"\].*?Rutas\.proyecto\(', r'entornoApp\[Host\.prefijo \+ "PROGRAMAS"\]'):
    problemas.append("Mac: Host.arrancar con corta://video (registrarMedios), la carpeta de un proyecto revisada por el inyector «proyecto», CORTA_PROGRAMAS para los scripts; el Procesador del host sin CORTA_* de afuera, con límite y latido")
if not tiene(swift, r"static func proyecto.*?baseReal.*?proyecto\.json", r"static func archivo\(_ ruta: String\).*?Rutas\.baseReal.*?\"musica\", \"clips\".*?fuente\[\"archivo\"\]"):
    problemas.append("Mac: Rutas.proyecto (una carpeta directa de ~/Corta con proyecto.json) y Medios.archivo (solo el video, la música o los clips de un proyecto)")
act = leer("app/Sources/PiezaActualizaciones/Actualizaciones.swift") or ""
paquete = leer("app/Package.swift") or ""
if not tiene(act, r"/releases/download/", r"esDescargaNuestra\(zip, repo: c\.repo\)", r"shasum -a 256", r"comillas\(", r"--proto-redir '=https'") \
        or not tiene(swift, r'Actualizaciones\.configurar\(\.init\(repo: "corta-app/corta", nombre: "Corta"', r"p\.actualizaciones = \.init\(") \
        or not tiene(paquete, r'\.target\(name: "PiezaActualizaciones"', r'\.target\(name: "PiezaHost"', r'dependencies: \["PiezaHost", "PiezaActualizaciones", "PiezaCatalogo"\]'):
    problemas.append("Mac: las actualizaciones solo desde los Releases de corta-app/corta, con huella y comillas() (pieza «actualizaciones», atendidas por el host) y los targets PiezaHost y PiezaActualizaciones")
if re.search(r'"(claude|codex)"\s*,\s*\[', swift):
    problemas.append("Mac: la app no llama a la IA por su cuenta (la corre bin/ia.py)")
if "acciones.json" not in (leer("herramientas/empaquetar.sh") or ""):
    problemas.append("Mac: herramientas/empaquetar.sh tiene que copiar acciones.json junto a app.json")

# 7) El video se pide con el esquema que sirve la app (corta://, el id de app.json).
if app_json.get("id") != "corta" or "corta://video/" not in ui:
    problemas.append("La interfaz ya no pide el video como corta://video/…: cambia también Medios.swift (registrarMedios)")
if problemas:
    print("✗ Contrato roto:\n  - " + "\n  - ".join(problemas))
    sys.exit(1)
print(f"✓ Contrato: {len(acciones)} acciones ({len(registradas)} registradas, {len(del_host & acciones)} del host, {len(declaradas & acciones)} declaradas) "
      f"y {len(funciones_ui)} funciones en orden")
