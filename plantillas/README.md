# Plantillas

Una plantilla es un video armado de antemano con **huecos** para tus clips o fotos: cuánto dura cada hueco, qué efecto lleva, con
qué transición pasa al siguiente y qué texto aparece encima. En Corta eliges una («Usar una plantilla»), eliges tus clips y se arma
sola; después la retocas como cualquier video (todo se puede editar y deshacer) y la exportas.

Una plantilla es un JSON de **solo datos**: nunca trae video, fotos, música, CSS, código ni filtros de ffmpeg. Lo visual va **por
referencia** a efectos ([`efectos/`](../efectos/README.md) o del [catálogo](https://github.com/corta-app/corta-catalogo)) y a un
estilo de subtítulos ([`estilos/`](../estilos/README.md)), que ya pasaron su propia validación. El formato y su validación están en
[`bin/plantilla_formato.py`](../bin/plantilla_formato.py): el mismo archivo que usa el catálogo de la comunidad.

Aquí están las incluidas en la app, una por archivo en la carpeta de su categoría: `plantillas/<categoria>/<id>.json`.

## Ejemplo
```json
{
 "formato": 1,
 "id": "receta-rapida",
 "categoria": "tutorial",
 "nombre": {"es": "Receta rápida", "en": "Quick recipe"},
 "descripcion": {"es": "Ingredientes, tres pasos y el plato listo, en 15 segundos.", "en": "…"},
 "autor": "Corta",
 "proporcion": "9:16",
 "huecos": [
  {"dur": 3, "tipo": "foto", "pista": {"es": "Los ingredientes", "en": "The ingredients"}, "transicion": "destello"},
  {"dur": 3, "tipo": "video", "pista": {"es": "Primer paso", "en": "First step"}, "velocidad": {"v": 2}},
  {"dur": 3, "tipo": "cualquiera", "pista": {"es": "El plato listo", "en": "The finished dish"}, "efectos": ["zoom-lento"]}
 ],
 "textos": [{"en_hueco": 0, "texto": {"es": "Ingredientes", "en": "Ingredients"}, "posicion": 0.18}],
 "subtitulos": {"estilo": "caja", "activos": true},
 "efectos": ["calido"],
 "musica": {"bpm": 110}
}
```

| Campo | Qué es |
|---|---|
| `id` | Minúsculas, números y guiones (2 a 40). El archivo se llama `<id>.json`. |
| `categoria` | `negocios`, `presentacion`, `recuerdos`, `tutorial` o `celebracion` (la carpeta donde va). |
| `nombre`, `descripcion` | Por idioma: `"es"` obligatorio, los demás opcionales. Hasta 30 y 140 caracteres, sin HTML. |
| `autor`, `etiquetas` | Opcionales. Las etiquetas (hasta 8) ayudan a encontrarla. |
| `proporcion` | `9:16`, `1:1`, `4:5` o `16:9`: el lienzo del video armado. |
| `huecos` | De 1 a 20, en orden; entre todos, hasta 90 s. Cada uno: `dur` (0,5 a 15 s) y `tipo` (`video`, `foto` o `cualquiera`: lo que conviene poner). Opcionales: `pista` (qué poner, hasta 40 caracteres), `efectos` (hasta 3, solo en ese hueco; no transiciones), `transicion` (cómo pasa al siguiente: un efecto de categoría `transicion` con solo pasos de transición, como `destello`, `transicion-negro`, `barrido`, `zoom-de-paso` o `interferencia`) `zoom` (si cae una foto: `acercar`, lo normal, `alejar` o `no`) y `velocidad` (abajo). |
| `huecos[].velocidad` | Opcional: `{"v": 0.25 a 3}` (menos de 1 es cámara lenta); `"rampa": true` pasa suave de 1× a `v` (hasta 0,75) y vuelve, «cámara lenta en el momento clave»; `"audio": "tono"` o `"silencio"` (bajo 0,5× se silencia sola); `"suavizar": "mezcla"` (casi gratis) o `"movimiento"` (más fluido, exportar tarda mucho más), solo en cámara lenta. `dur` sigue siendo lo que se toma del clip: en el video dura `dur / v` (la app muestra lo que dura de verdad). |
| `textos` | Opcional, hasta 10: `en_hueco` (número del hueco, desde 0), `texto` por idioma (hasta 60 caracteres) y `posicion` (altura, de 0,08 a 0,9; 0,18 si no se dice). El texto dura todo el hueco. |
| `subtitulos` | Opcional: `estilo` (id de un estilo de `estilos/`; con él se dibujan los subtítulos y los textos) y `activos`. |
| `efectos` | Opcional: hasta 3 efectos para todo el video. |
| `musica` | Opcional: solo `bpm` (60 a 200), el ritmo para el que se pensaron los cortes. Nunca un archivo: cada persona pone su música. |

## Cómo se arma
- **Llenar** (`bin/plantillas.py` `llenar`, igual en `ui/app.js`): los clips van a los huecos en el orden elegido. Cada hueco toma
  el primer clip sin usar que le calza (`video`, `foto` o `cualquiera`); si no hay, el primero sin usar; si se acaban, se empieza
  otra vuelta. Un video que cae en varios huecos se parte en partes iguales y cada hueco toma el centro de la suya. Después, en la
  pestaña **Clips**, eliges qué parte de cada video va (una barra) o cambias un clip.
- **El video**: los huecos se ponen uno detrás de otro en un solo video del tamaño del lienzo (`plantilla-N.mp4`, el `fuente` del
  proyecto), cada uno cubriendo el cuadro. Lo arma ffmpeg con una lista blanca de filtros (`trim`, `setpts`, `tpad`, `fps`,
  `scale`, `crop`, `setsar`, `format`, `atrim`, `asetpts`, `aresample`, `aformat`, `apad`, `anullsrc`, `concat`) y solo números.
- **Lo demás es un proyecto normal**: una división (`divisiones`) en cada unión, los textos, los efectos de cada hueco (con sus
  pasos copiados), la transición alrededor de cada unión (sus pasos trabajan en las divisiones), el estilo y los
  efectos de todo el video y la velocidad de cada hueco (`velocidades`). Una foto se mueve sola (zoom lento) salvo `zoom: "no"` o si su hueco ya trae un zoom. Exportar usa el
  render de siempre.
- Si un efecto no está (es del catálogo y no lo descargaste), se omite y la app ofrece descargarlo.

## Crear y compartir una
1. Copia una de estas, cámbiale el `id`, el nombre y los huecos, y déjala en `~/Corta/.corta/plantillas/<id>.json`.
2. Úsala en Corta («Usar una plantilla») con tus clips.
3. Compártela en el [catálogo de la comunidad](https://github.com/corta-app/corta-catalogo#plantillas): se puede proponer con
   palabras, sin escribir el JSON.
