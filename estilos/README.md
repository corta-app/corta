# Estilos de subtítulos

Un estilo es un JSON de **solo datos** (nunca código) que dice cómo se ven los subtítulos. La vista previa de Corta lo dibuja con CSS
y la exportación con ffmpeg (libass) a partir del mismo archivo, para que lo que ves sea lo que exportas.

## Ejemplo
```json
{
 "formato": 1,
 "id": "pop",
 "nombre": "Pop",
 "fuente": "Poppins ExtraBold",
 "peso": 800,
 "tamano": 9.2,
 "color": "#FFFFFF",
 "color_activo": "#FFE14D",
 "borde": 7,
 "color_borde": "#000000",
 "sombra": 2,
 "mayusculas": true,
 "fondo": false,
 "color_fondo": "#000000",
 "animacion": "pop",
 "autor": "Corta",
 "notas": "El clásico de los Shorts: palabra activa en amarillo y un poco más grande."
}
```

| Campo | Qué es |
|---|---|
| `id` | Minúsculas, números y guiones. El archivo se llama `<id>.json`. |
| `nombre` | Cómo se muestra en la galería (máx. 30 caracteres, sin HTML). |
| `fuente` | Nombre exacto de la tipografía. Tiene que estar en `ui/fuentes/` (con licencia libre, como OFL) para verse igual en todos los computadores. |
| `peso` | 400 a 900 (solo para la vista previa; el grosor real viene de la fuente). |
| `tamano` | Tamaño de la letra en % del ancho del video (3 a 16). |
| `color`, `color_activo` | Color del texto y de la palabra que se está diciendo (`#RRGGBB`). |
| `borde`, `color_borde` | Grosor del contorno en px para un video de 1080 de ancho (0 a 12) y su color. |
| `sombra` | Sombra (0 a 12). |
| `mayusculas` | `true` para TODO EN MAYÚSCULAS. |
| `fondo`, `color_fondo` | `true` para poner el texto sobre una caja de color. |
| `animacion` | `ninguna`, `pop` (la palabra activa crece y cambia de color), `subrayado` o `palabra` (una sola palabra gigante a la vez). |

## Compartir un estilo
Prueba tu estilo poniéndolo en `~/Corta/.corta/estilos/` (gana sobre los incluidos) y ábrelo en la pestaña Subtítulos. Si te gusta,
abre un pull request con el archivo en esta carpeta y una captura. Si usa una fuente nueva, agrégala a `ui/fuentes/` con su licencia.
