<p align="center"><img src="docs/img/logo.png" width="96" alt="Corta"></p>

<h1 align="center">Corta</h1>

<p align="center"><b>El editor gratis y de código abierto para Shorts, Reels y TikTok.</b><br>
Editas el texto y se edita el video. Subtítulos animados, sin silencios ni muletillas. Tu propia IA hace el trabajo pesado.<br>
Todo pasa en tu computador: tus videos no se suben a ningún lado. Sin marca de agua.</p>

<p align="center"><a href="https://corta-app.github.io/corta/"><b>Página</b></a> ·
<a href="https://corta-app.github.io/corta/demo/"><b>Pruébala en el navegador</b></a> ·
<a href="#instalar">Instalar</a> ·
<a href="https://github.com/corta-app/corta/wiki">Wiki</a> ·
<a href="https://github.com/corta-app/corta/discussions">Comunidad</a> ·
<a href="#como-aportar">Cómo aportar</a> ·
<a href="#english">English</a></p>

<p align="center"><picture><source srcset="docs/img/editor.png" media="(prefers-color-scheme: dark)"><img src="docs/img/editor-claro.png" width="860" alt="El editor de Corta: el video vertical con subtítulos, la transcripción con los silencios y muletillas cortados y la línea de tiempo con pistas (video de mentira)"></picture></p>
<p align="center">
<picture><source srcset="docs/img/app-celular-oscuro.png" media="(prefers-color-scheme: dark)"><img src="docs/img/app-celular-claro.png" width="250" alt="El editor a ancho de celular (video de mentira)"></picture>
<picture><source srcset="docs/img/app-plantillas-oscuro.png" media="(prefers-color-scheme: dark)"><img src="docs/img/app-plantillas-claro.png" width="250" alt="Las plantillas: eliges una, pones tus clips o fotos y se arma sola"></picture>
</p>
<p align="center"><sub>Video de mentira: Ana es dibujada y su voz es sintética.</sub></p>

---

## Qué hace
- **Edita por texto.** Corta transcribe tu video en tu computador, palabra por palabra. Borras una frase y se borra del video.
- **Saca silencios y muletillas** de una vez («eh», «mmm», pausas largas). Lo puedes deshacer cuando quieras.
- **Subtítulos animados** al estilo de los Shorts, en cualquier idioma. Los estilos son archivos simples. Cualquiera puede crear uno.
- **Corrige cualquier palabra.** Tócala en el texto o sobre el video. Los tiempos no cambian. Si el nombre de tu marca salió mal,
  lo cambias en todo el video de una vez. Corta lo recuerda para tus próximos videos.
- **Vertical primero:** 9:16, 1:1, 4:5 o 16:9. Para un video horizontal, ajustas el encuadre o usas un fondo borroso.
- **Dile a tu IA lo que quieres:** «pon zoom cuando digo el precio», «saca la parte donde me equivoco», «pon un título al inicio».
  Si no te gusta, **«Quitar»** deshace justo ese cambio de la IA, aunque hayas seguido editando.
- **Shorts desde un video largo.** Tu IA elige los mejores momentos de una clase, un podcast o un live. Cada momento queda como un
  video nuevo.
- **Velocidad y cámara lenta.** Toca un tramo y elige de 0,25× a 3×, o un valor exacto.
  - Los subtítulos, los textos y los efectos siguen sincronizados.
  - La voz mantiene su tono. Bajo 0,5× se silencia sola, y tú decides. La música no se acelera.
  - Una **rampa** pasa suave de 1× a cámara lenta y vuelve, justo en el momento clave.
  - **Suavizar** evita que la cámara lenta salte.
  - También se lo puedes pedir a tu IA: «pon en cámara lenta cuando digo…».
- **Cortes, efectos y filtros.**
  - Divide en el cabezal. Borra o recorta un tramo.
  - Ponle un filtro a todo el video o a un momento: blanco y negro, cálido, vintage…
  - Suma un zoom, o una transición en cada corte: interferencia, destello, franjas, rebote, barrido o zoom de paso.
  - La vista previa y el video exportado se ven igual.
  - Los efectos son archivos simples. La comunidad crea más en el [catálogo](https://github.com/corta-app/corta-catalogo). Los
    descargas gratis desde la app, ordenados por categoría.
- **Plantillas.** Elige una: presentación de producto, pitch en 30 s, antes y después, recuerdos del mes, receta rápida… Pon tus
  clips o fotos y el video se arma solo, con sus cortes, transiciones, efectos y textos. Después lo retocas como cualquier video. La
  comunidad aporta más en el [catálogo](https://github.com/corta-app/corta-catalogo#plantillas), por categorías y gratis.
- **Música de fondo que baja sola cuando hablas.**
- **Una línea de tiempo con pistas:** video, subtítulos, textos y música. Arrastras los bordes con el mouse, el dedo o el teclado.

<a id="instalar"></a>
## Instalar

| | Cómo | Estado |
|---|---|---|
| 🌐 **Navegador** | [Vista previa con un video de mentira](https://corta-app.github.io/corta/demo/). No hay que instalar nada. | Para ver cómo funciona |
| 🍎 **Mac** | [**Descargar Corta-macOS.zip**](https://github.com/corta-app/corta/releases/latest/download/Corta-macOS.zip) (Apple Silicon, macOS 15). [Cómo instalarla](#instalar-en-mac). Trae todo adentro. | Funciona. Sin firma de Apple |
| 🪟 🐧 **Windows y Linux** | La misma interfaz, en una app de escritorio. | En camino |

La IA es opcional y es la tuya, con tu cuenta: Claude Code, Codex (ChatGPT) o Gemini CLI
([cómo instalarla](https://corta-app.github.io/corta/ia.html)). Sin IA igual puedes editar por texto, limpiar silencios y poner
subtítulos, efectos y plantillas. Todas las versiones están en [Releases](https://github.com/corta-app/corta/releases), cada una
con su huella `.sha256`.

## Tus videos son tuyos
- La transcripción (whisper.cpp) y la exportación (ffmpeg) pasan en tu computador. **Corta no tiene servidores**, cuentas ni
  telemetría.
- La IA es **la tuya** (Claude Code, Codex o Gemini), con tu cuenta. Solo ve el texto con sus tiempos. Nunca ve el video ni el audio.
- El video original nunca cambia. Los cambios viven en un `proyecto.json` abierto, con historial para deshacer.
- No hay marca de agua ni límite de resolución o de duración.
- **Sin permisos especiales** en el Mac: ni micrófono, ni cámara, ni avisos, ni el Llavero. Corta solo abre los archivos que eliges
  o sueltas.
- Corta sale a internet solo para tres cosas:
  1. Bajar el transcriptor, una vez (huggingface.co).
  2. Abrir el catálogo de la comunidad (raw.githubusercontent.com).
  3. Buscar o bajar versiones nuevas (GitHub).

  Corta comprueba todo lo que baja con su huella SHA-256.

<a id="como-aportar"></a>
## Cómo aportar
Corta es gratis y abierta. La hacemos entre todos. Casi nada exige programar:
- 💬 **Crea un estilo de subtítulos, un efecto o una plantilla.** Son archivos JSON cortos ([estilos](estilos/README.md),
  [efectos](efectos/README.md), [plantillas](plantillas/README.md)). Se comparten en el
  [catálogo de la comunidad](https://github.com/corta-app/corta-catalogo). Desde ahí, cualquiera los descarga gratis en la app. Una
  plantilla la puedes proponer con palabras, sin escribir el JSON.
- 🎬 **Pruébala con tus videos:** mira los issues con la etiqueta [`probar`](https://github.com/corta-app/corta/labels/probar).
- 🗣️ **Conversa** en [Discussions](https://github.com/corta-app/corta/discussions): dudas, ideas o lo que publicaste.
- 🛠️ **Programa, con o sin IA.** [`AGENTS.md`](AGENTS.md) es la guía para personas y para cualquier IA de programación. Empieza
  por [CONTRIBUTING.md](CONTRIBUTING.md).

Al participar, aceptas el [código de conducta](CODE_OF_CONDUCT.md). ¿Encontraste una falla de seguridad? Avísanos en privado:
[SECURITY.md](SECURITY.md).

## Estado
Corta está en la versión 0.2 y [lista para descargar](#instalar-en-mac). Ya funcionan:
- El motor: cortes, silencios, subtítulos, zooms, textos, encuadre, exportación vertical, edición con IA y Shorts.
- La interfaz.
- La **app para Mac** (Apple Silicon, macOS 15 o más nuevo), hecha con Rust y Tauri.

Windows y Linux vienen en camino. Puedes [probar la interfaz con un video de mentira](https://corta-app.github.io/corta/demo/).

## Instalar en Mac
Corta para Mac trae todo adentro. No necesitas instalar Python, ffmpeg ni whisper. Necesitas un Mac con Apple Silicon (M1 o más
nuevo) y macOS 15 o más nuevo.
1. Descarga [**Corta-macOS.zip**](https://github.com/corta-app/corta/releases/latest/download/Corta-macOS.zip), la última versión.
   Su huella SHA-256 está en el mismo [Release](https://github.com/corta-app/corta/releases/latest), en `Corta-macOS.zip.sha256`.
2. Descomprime el archivo.
3. Arrastra **Corta** a Aplicaciones.
4. Ábrela. Corta es una app **sin firmar**: no pagamos el certificado de Apple. Por eso, la primera vez, macOS avisa que no puede
   verificarla.
5. Ve a **Ajustes del Sistema → Privacidad y seguridad**. Abajo, toca **«Abrir igualmente»**. Esto se hace solo la primera vez.

**Desde el código**, si prefieres armarla tú. Necesitas las herramientas de línea de comandos de Xcode (`xcode-select --install`),
[Rust](https://rustup.rs) y `cmake` (arma whisper.cpp):
```bash
git clone https://github.com/corta-app/corta ~/Developer/corta   # no en ~/corta: macOS no distingue ~/corta de ~/Corta (tus videos)
cd ~/Developer/corta && bash build.sh                            # queda en ~/Applications/Corta.app
```

La primera vez, eliges tu idioma y tu IA, y descargas el transcriptor. Corta verifica su huella.

Tus videos y proyectos quedan en `~/Corta`. Actualizar nunca los toca. Corta revisa sola si hay una versión nueva y te avisa en
Ajustes. En una instalación desde el código, actualiza con `git pull`.

Dentro de la app van estos programas:
- [ffmpeg](https://ffmpeg.org) (GPL, como programa aparte), con su huella SHA-256 fija.
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (MIT), compilado al empaquetar con Metal, desde un commit fijo.
- Python portátil, con su huella SHA-256 fija.

El detalle está en `escritorio/herramientas/preparar.sh`.

## Cómo funciona
```
tu video ──► whisper (en tu computador) ──► palabras con tiempos ──► editas el texto / limpias / le pides a tu IA
                                                                         │
                                         proyecto.json (cortes, subtítulos, zooms, textos) ◄─┘
                                                                         │
                                               ffmpeg ──► exportado-9x16.mp4 (con subtítulos)
```

## Formato del proyecto
Cada video vive en `~/Corta/<fecha> <nombre>/`. La carpeta tiene:
- `original.<ext>`: tu video tal cual.
- `proyecto.json`: los cambios.
- `historial/`: para deshacer.
- `musica/`: una copia de la música que elegiste.
- Lo que exportas.

Un video hecho con una plantilla no tiene `original.<ext>`. En su lugar tiene `clips/` (copias de tus clips y fotos) y
`plantilla-N.mp4` (los clips ya armados).

`proyecto.json` es abierto: puedes armar tus propios scripts encima (ver [`ejemplos/`](ejemplos/)).

| Campo | Qué guarda |
|---|---|
| `fuente` | `{archivo, duracion, ancho, alto}` del video original. |
| `lienzo`, `relleno`, `encuadre` | Formato (`9:16`, `1:1`, `4:5`, `16:9`), `recorte` o `desenfoque`, y qué parte del video se ve (`x`, `y` de 0 a 1). |
| `palabras` | `[{t, i, f, linea?}]`: cada palabra con su inicio y fin en segundos del original. `linea` (opcional) es lo que decidiste a mano: `"fin"` corta la frase del subtítulo después de esa palabra y `"sigue"` la une con la siguiente. |
| `cortes` | `[{i, f, motivo}]`: lo que no va. `motivo`: `silencio`, `muletilla`, `manual`, `ia` o `fuera` (fuera de un Short). |
| `subtitulos` | `{activos, estilo, palabras_por_linea, posicion}` |
| `zooms`, `textos` | `[{i, f, escala}]` y `[{i, f, texto, y}]` |
| `efectos` | (opcional) `[{efecto, pasos, i?, f?, origen?}]`: los efectos aplicados, con sus pasos copiados (formato en [`efectos/README.md`](efectos/README.md)). Sin `i`/`f`, a todo el video. |
| `velocidades` | (opcional) `[{i, f, v, rampa?, audio?, suavizar?, origen?}]`: la velocidad de un tramo del original, sin traslaparse. `v` de 0,25 a 3 (menos de 1 es cámara lenta). `rampa: true` pasa suave de 1× a `v` (hasta 0,75) y vuelve: sube en el primer 30 % del tramo y baja en el último 30 % (al menos 0,5 s). `audio`: `"tono"` (la voz más lenta o rápida con su tono, `atempo`) o `"silencio"`; sin decirlo, bajo 0,5× (y en una rampa así) se silencia. `suavizar` (solo en cámara lenta): `"mezcla"` (funde cuadros, casi gratis) o `"movimiento"` (inventa los cuadros que faltan; exportar tarda mucho más). Todo lo demás (palabras, textos, efectos) sigue en segundos del original: al exportar, cada momento cae donde le toca. |
| `divisiones` | (opcional) `[segundos]`: dónde dividiste el video en la línea de tiempo (para elegir tramos). Al exportar no cortan nada: una transición del tramo pestañea ahí, como en un corte. |
| `plantilla` | (opcional, solo en un video hecho con una plantilla) `{id, huecos: [{archivo, tipo, desde, dur, duracion}]}`: qué clip o foto (una copia en `clips/`) va en cada hueco, desde qué segundo y cuánto dura el hueco. Lo cambia solo la app (pestaña Clips), que vuelve a armar el video (`fuente`). |
| `cambios_ia` | (opcional) Lo que hizo tu IA, para quitar justo ese cambio aunque hayas seguido editando: `[{id, estado: "aplicado" \| "quitado", pedido, resumen, fecha, agregados: {zooms, textos, cortes, efectos, velocidades}, ajustes?: [{campo, antes, despues}], restaurados?: {antes, despues}, palabras?: [{antes, despues}], conservados?}]` (los últimos 20). Lo que agregó la IA lleva `"origen": "<id>"`. |
| `musica` | `null` o `{archivo, volumen}`: `archivo` relativo a la carpeta del proyecto (la app copia la canción a `musica/`) o una ruta absoluta; `volumen` de 0 a 1. La música baja sola cuando hablas. |

Todos los tiempos están en segundos **del video original**: los cortes dicen qué se saca y lo demás se conserva. Un tramo a 0,5×
dura el doble en el video exportado; un programa que lea el formato puede pasar al tiempo exportado con `proyecto.a_salida`.

### Vocabulario
`~/Corta/vocabulario.json` guarda las palabras que corregiste y pediste recordar:
```json
{"formato": 1, "reemplazos": [{"de": "calumi", "a": "Kalumi"}], "palabras": ["Kalumi"]}
```
Al transcribir un video nuevo, cada reemplazo se aplica por palabra completa (sin mirar tildes ni mayúsculas; `de` puede tener varias
palabras, como «ca lumi») y las palabras propias se le pasan al transcriptor como vocabulario, para que reconozca mejor nombres y
marcas. Lo ves y lo borras en Ajustes → Vocabulario.

### Efectos
Los efectos son JSON de solo datos (formato en [`efectos/README.md`](efectos/README.md)). Vienen algunos incluidos (`efectos/`) y los
que descargas del [catálogo de la comunidad](https://github.com/corta-app/corta-catalogo) quedan en `~/Corta/.corta/efectos/`. La
app solo descarga desde `raw.githubusercontent.com/corta-app/corta-catalogo`, compara la huella SHA-256 del índice y valida cada
efecto con el mismo formato que el catálogo antes de guardarlo.

### Plantillas
Las plantillas son JSON de solo datos (formato en [`plantillas/README.md`](plantillas/README.md)): huecos con su duración, efectos y
transiciones por nombre, textos, la velocidad de cada hueco (cámara lenta, rápida o una rampa) y el ritmo de la música para el que se pensaron (nunca un archivo de audio). Vienen 12 incluidas
(`plantillas/`) y las que descargas del [catálogo](https://github.com/corta-app/corta-catalogo#plantillas) quedan en
`~/Corta/.corta/plantillas/`, con la misma descarga verificada que los efectos. Si una plantilla usa un efecto del catálogo que no
tienes, Corta te ofrece descargarlo.

## Desarrollo
Necesitas Python 3 (solo biblioteca estándar) y ffmpeg. Para transcribir, necesitas whisper.cpp (`whisper-cli`).

La app nativa está en `escritorio/`. Es Rust + Tauri, con la pieza «host-tauri» de Pieza. La misma app servirá para Windows y Linux.
- `bash build.sh` la arma y la instala en el Mac.
- `cd escritorio && cargo run` la abre en cualquier sistema.
```bash
cd ui && python3 -m http.server 8765         # interfaz con el video de mentira: http://localhost:8765 (?idioma=en, ?bienvenida, ?vacio)
python3 bin/importar.py mi-video.mp4 /tmp/r.json   # crea el proyecto en ~/Corta
python3 bin/limpiar.py "<carpeta>" 0.5 1 /tmp/r.json
python3 bin/render.py "<carpeta>" /tmp/r.json      # exporta
bash pruebas/correr.sh                       # todas las pruebas
```
Lee [`AGENTS.md`](AGENTS.md) antes de cambiar algo: sirve igual para personas y para tu IA.

## Licencia
[AGPL-3.0](LICENSE). Puedes usar, estudiar, cambiar y compartir Corta. Si la ofreces como servicio o la distribuyes modificada,
publica tu código con la misma licencia. Las tipografías de `ui/fuentes/` usan la [SIL Open Font License](ui/fuentes/OFL.txt).

---

## English
**Corta** ("cut") is a free, open-source editor for Shorts, Reels and TikTok.
- It transcribes your video on your computer. You edit the video by editing its text.
- It removes silences and filler words in one click.
- It adds animated captions in any language. Caption styles are data-only files anyone can create.
- It reframes landscape footage to vertical.
- Your own AI (Claude Code, Codex or Gemini, with your account) applies edits from plain requests. It can also pick the best
  moments of a long video as new Shorts. If you don't like an AI edit, **Remove** undoes just that change, even after you kept
  editing.
- Fix any caption word in place. Corta remembers your brand names for future videos.
- Split and trim segments. Add filters, zooms and transitions (glitch, flash, split, bounce, swipe, zoom through) to the whole video
  or one moment.
- Change the speed of any segment, from 0.25× to 3×, or use a smooth slow-motion ramp at the key moment. Captions and text stay in
  sync. The voice keeps its pitch and the music doesn't change.
- Add background music that ducks under your voice. Fine-tune cuts, zooms and text on a multi-track timeline.
- **Templates:** pick one (product showcase, 30-second pitch, before and after, month in memories, quick recipe…). Add your clips
  or photos and the video builds itself, with its cuts, transitions, effects and texts. Then edit it like any other video.
- The community shares more effects and templates in the [catalog](https://github.com/corta-app/corta-catalogo). Download them for
  free from the app.

Videos never leave your computer. There's no watermark. The project is a plain, open JSON file. Spanish first, English included.
License: AGPL-3.0.

**Mac app** (Apple Silicon, macOS 15+). Everything is bundled: Python and ffmpeg pinned by SHA-256, and whisper.cpp built with Metal
from a pinned commit.
1. [**Download Corta-macOS.zip**](https://github.com/corta-app/corta/releases/latest/download/Corta-macOS.zip). Every version, with
   its `.sha256`, is in [Releases](https://github.com/corta-app/corta/releases).
2. Unzip it and drag Corta to Applications.
3. It's an **unsigned app**. The first time, macOS says it can't verify it. Go to **System Settings → Privacy & Security** and, at
   the bottom, click **"Open Anyway"**. You do this only the first time.

Corta checks for new versions itself and tells you in Settings. To build it from source, install the Xcode command line tools,
[Rust](https://rustup.rs) and `cmake`, then run:
`git clone https://github.com/corta-app/corta ~/Developer/corta && cd ~/Developer/corta && bash build.sh`.
It installs to `~/Applications/Corta.app`. Your videos live in `~/Corta`. Windows and Linux are on the way.

Corta needs no special permissions: no microphone, camera, notifications or Keychain. It goes online only to download the
transcriber once (huggingface.co), open the community catalog (raw.githubusercontent.com) and check for or download new versions
(GitHub). It verifies everything by SHA-256.

**Try it** in your browser with a made-up video: [live preview](https://corta-app.github.io/corta/demo/?idioma=en). Caption styles,
effects and templates are welcome in the [community catalog](https://github.com/corta-app/corta-catalogo). Questions and ideas are
welcome in [Discussions](https://github.com/corta-app/corta/discussions), in English or Spanish. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

[![Hecho con Pieza](https://pieza-app.github.io/pieza/sello.svg)](https://pieza-app.github.io/pieza/) · Las piezas comunes (tu IA, idiomas, actualizaciones, la app de Mac…) viven en [Pieza](https://github.com/pieza-app/pieza).
[![Made with Pieza](https://pieza-app.github.io/pieza/sello-en.svg)](https://pieza-app.github.io/pieza/) · The shared pieces (your AI, languages, updates, the Mac app shell…) live in [Pieza](https://github.com/pieza-app/pieza).
