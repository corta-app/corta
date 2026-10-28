# Efectos y filtros

Un efecto es un JSON de **solo datos**: nunca trae CSS, código ni texto de filtro de ffmpeg. Trae una lista de `pasos` de tipos
conocidos, con números dentro de rangos conocidos. Con esos números Corta arma la vista previa (filtros de CSS) y la exportación
(ffmpeg, con una lista blanca de filtros), para que lo que ves sea lo que exportas. El formato y su validación están en
[`bin/efecto_formato.py`](../bin/efecto_formato.py): el mismo archivo que usa el
[catálogo de la comunidad](https://github.com/corta-app/corta-catalogo).

Aquí están los incluidos en la app, uno por archivo en la carpeta de su categoría: `efectos/<categoria>/<id>.json`.

## Ejemplo
```json
{
 "formato": 1,
 "id": "calido",
 "categoria": "color",
 "nombre": {"es": "Cálido", "en": "Warm"},
 "descripcion": {"es": "Tonos dorados, como al atardecer.", "en": "Golden tones, like a sunset."},
 "autor": "Corta",
 "etiquetas": ["atardecer", "sunset"],
 "pasos": [{"tipo": "color", "saturacion": 1.15, "sepia": 0.12}, {"tipo": "tinte", "color": "#FF8A2A", "fuerza": 0.1}]
}
```

| Campo | Qué es |
|---|---|
| `id` | Minúsculas, números y guiones (2 a 40). El archivo se llama `<id>.json`. |
| `categoria` | `filtro`, `color`, `movimiento` o `transicion` (la carpeta donde va). |
| `nombre`, `descripcion` | Por idioma: `"es"` obligatorio, los demás opcionales. Hasta 30 y 140 caracteres, sin HTML. |
| `autor`, `etiquetas` | Opcionales. Las etiquetas (hasta 8) ayudan a encontrarlo. |
| `pasos` | De 1 a 4, en orden. |

## Pasos
| `tipo` | Campos | Vista previa (CSS) | Exportación (ffmpeg) |
|---|---|---|---|
| `color` | `brillo` 0,5–1,5 · `contraste` 0,5–2 · `saturacion` 0–2 · `tono` −180–180 (grados) · `sepia` 0–1 · `grises` 0–1 | `brightness() contrast() saturate() hue-rotate() sepia() grayscale()` | `colorchannelmixer` (+ `lutrgb`) con las mismas matrices |
| `tinte` | `color` `#RRGGBB` · `fuerza` 0,02–0,5 | capa de color con opacidad | capa `color` + `overlay` |
| `desenfoque` | `radio` 0,5–20 (px a 1080 de ancho) | `blur()` | `gblur` |
| `vineta` | `fuerza` 0,1–1 | `radial-gradient` | la misma capa calculada con `geq` |
| `zoom` | `desde`, `hasta` 1–1,6 · `curva` `lineal`, `suave` o `golpe` | `transform: scale()` | `perspective` (suave, sin saltos) |
| `fundido` | `entrada`, `salida` 0–3 s · `color` `negro` o `blanco` | capa de color | capa `color` + `geq` + `overlay` |
| `transicion` | `duracion` 0,1–1,5 s · `color` `negro` o `blanco` | un pestañeo en cada corte del tramo | igual, en cada unión |

### Transiciones
Van en cada **unión** del tramo (un corte o una división; en una plantilla, donde pasa de un clip al siguiente), centradas en ella y
de `duracion` 0,1–1 s. Funcionan con un solo video: lo que sale antes de la unión es el clip que termina y lo que entra después, el
siguiente. La vista previa las dibuja igual que ffmpeg (`pintarPasos` en `ui/app.js`, con la misma lógica de tiempos que
`bin/efectos.py`) y `pruebas/transiciones.mjs` compara cuadros de la vista previa con cuadros exportados de verdad.

| `tipo` | Campos | Qué hace | Exportación (ffmpeg) |
|---|---|---|---|
| `interferencia` | `intensidad` 0,1–1 | glitch: dos franjas de la imagen saltan de lado y el rojo y el azul se corren (al azar, pero siempre igual) | solo en los cuadros de la ventana: `split`, `trim`, `crop`, `overlay`, `rgbashift`, `tpad` |
| `destello` | `color` `#RRGGBB` · `intensidad` 0,1–1 (opacidad) · `exposicion` 0–1 | un destello de color que sube la exposición | capa de color + `eq` (brillo multiplicado, sin pasar a RGB) |
| `franjas` | `franjas` 2 o 3 · `direccion` `vertical` u `horizontal` | la imagen se parte; cada franja sale en sentido contrario a su vecina y entra ya con el clip siguiente | `split`, `crop` y `overlay` sobre negro |
| `rebote` | `intensidad` 0,1–1 | la escala crece hasta el corte y rebota | `perspective` |
| `barrido` | `direccion` `izquierda`, `derecha`, `arriba` o `abajo` · `desenfoque` 0–1 | la imagen se desliza (con estela) y entra la siguiente | `split` + dos `overlay` + `gblur` en un solo sentido |
| `zoom_paso` | `intensidad` 0,1–1 · `desenfoque` 0–1 | un acercamiento rápido que cruza el corte y se abre en el clip siguiente | `perspective` + `gblur` |

Fuera de su ventana, una transición no hace trabajo: los filtros llevan `enable` y lo caro (pasar a RGB para `rgbashift`) corre solo
en los cuadros de la ventana. Exportar 8 s a 1080×1920 con una transición en dos uniones cuesta casi lo mismo que sin ella.

Un efecto se aplica a todo el video o a un tramo (palabras elegidas o un tramo de la línea de tiempo). Pasa después de unir las
piezas y antes de los subtítulos: los subtítulos nunca se desenfocan ni se mueven.

## Crear y compartir uno
1. Copia uno de estos archivos, cámbiale el `id`, el nombre y los números, y déjalo en `~/Corta/.corta/efectos/<id>.json`.
2. Ábrelo en Corta (pestaña Efectos) y pruébalo en un video tuyo.
3. Si te gusta, compártelo en el [catálogo de la comunidad](https://github.com/corta-app/corta-catalogo): ahí se explica cómo, sin
   programar.
