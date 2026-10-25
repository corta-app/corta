#!/usr/bin/env python3
"""IA falsa para las pruebas: se instala como «claude» en un PATH temporal y responde según lo que se le pide. Nunca sale a internet."""
import json
import sys

pedido = sys.stdin.read()
if "La persona te pide un cambio" in pedido:
    print("Listo:\n" + json.dumps({"operaciones": [
        {"op": "zoom", "desde": 6, "hasta": 8, "escala": 1.3},
        {"op": "cortar", "desde": 1, "hasta": 3},
        {"op": "estilo", "id": "neon"},
        {"op": "cortar", "desde": 2, "hasta": 999},
        {"op": "borrar_todo"},
    ], "resumen": "Puse zoom, corté el saludo y cambié el estilo."}, ensure_ascii=False))
elif "MEJORES momentos" in pedido:
    print(json.dumps({"shorts": [
        {"desde": 4, "hasta": 34, "titulo": "Ahorra una hora", "gancho": "¿Sabías que puedes ahorrar una hora?", "por_que": "Pregunta directa."},
        {"desde": 1, "hasta": 2, "titulo": "Muy corto", "gancho": "", "por_que": ""},
    ]}, ensure_ascii=False))
else:
    print("listo")
