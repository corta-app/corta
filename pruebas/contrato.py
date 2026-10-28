#!/usr/bin/env python3
"""Contrato entre la interfaz (ui/app.js) y las apps: cada host.enviar("x") de la interfaz debe existir en Mac (Ventana.swift), en la
vista previa del navegador (simular())
y, cuando exista, en Windows/Linux (escritorio/src/main.js, objeto ACCIONES). Y cada window.Corta.x que llaman las apps debe existir.
También revisa que los scripts que llaman las apps existan en bin/ y que el video se pida con el esquema que sirve la app (corta://)."""
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


ui = leer("ui/app.js")
acciones = set(re.findall(r'host\.enviar\("(\w+)"', ui))
cuerpo = ui.split("window.Corta = {", 1)[1].split("\n  };", 1)[0]
funciones_ui = set(re.findall(r"^\s{4}(?:async\s+)?(\w+)\(", cuerpo, re.M))
problemas = []
# La vista previa del navegador responde cada acción en simular() (aunque sea con un aviso «en la app, aquí…»).
simulado = ui.split("function simular(", 1)[1].split("\n  }\n", 1)[0]
casos_web = set(re.findall(r'case "(\w+)"', simulado))
problemas += [f'La vista previa (simular) no responde la acción "{a}"' for a in sorted(acciones - casos_web)]
mac = leer("app/Sources/Corta/Ventana.swift")
if mac is None:
    problemas.append("Falta app/Sources/Corta/Ventana.swift")
else:
    casos_mac = set(re.findall(r'"(\w+)"', " ".join(re.findall(r"case ([^:]+):", mac))))
    problemas += [f'Mac (Ventana.swift) no atiende la acción "{a}"' for a in sorted(acciones - casos_mac)]
    swift = "".join(leer(os.path.join("app/Sources/Corta", n)) for n in os.listdir(os.path.join(RAIZ, "app/Sources/Corta")) if n.endswith(".swift"))
    problemas += [f"Mac llama window.Corta.{f} y la interfaz no la tiene" for f in sorted(set(re.findall(r'llamar\("(\w+)"', swift)) - funciones_ui)]
    scripts = set(re.findall(r'(?:correrJSON|conEntrada)\("(\w+\.py)"', swift))
    problemas += [f"La app llama bin/{s} y no existe" for s in sorted(scripts) if not os.path.exists(os.path.join(RAIZ, "bin", s))]
escritorio = leer("escritorio/src/main.js")
if escritorio:
    casos_e = set(re.findall(r"^\s{2}(?:async\s+)?(\w+)\s*\(", escritorio.split("const ACCIONES = {", 1)[1].split("\n};", 1)[0], re.M))
    problemas += [f'Windows/Linux (ACCIONES) no atiende la acción "{a}"' for a in sorted(acciones - casos_e)]
    problemas += [f"Windows/Linux llama window.Corta.{f} y la interfaz no la tiene" for f in sorted(set(re.findall(r'llamar\("(\w+)"', escritorio)) - funciones_ui)]
if mac is not None and 'esquema = "corta"' not in swift:
    problemas.append("Mac: Medios.swift tiene que servir corta:// (la interfaz pide el video así)")
if "corta://video/" not in ui:
    problemas.append("La interfaz ya no pide el video como corta://video/…: cambia también Medios.swift")
if problemas:
    print("✗ Contrato roto:\n  - " + "\n  - ".join(problemas))
    sys.exit(1)
print(f"✓ Contrato: {len(acciones)} acciones y {len(funciones_ui)} funciones en orden")
