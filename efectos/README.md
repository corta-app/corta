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

Un efecto se aplica a todo el video o a un tramo (palabras elegidas o un tramo de la línea de tiempo). Pasa después de unir las
piezas y antes de los subtítulos: los subtítulos nunca se desenfocan ni se mueven.

## Crear y compartir uno
1. Copia uno de estos archivos, cámbiale el `id`, el nombre y los números, y déjalo en `~/Corta/.corta/efectos/<id>.json`.
2. Ábrelo en Corta (pestaña Efectos) y pruébalo en un video tuyo.
3. Si te gusta, compártelo en el [catálogo de la comunidad](https://github.com/corta-app/corta-catalogo): ahí se explica cómo, sin
   programar.
