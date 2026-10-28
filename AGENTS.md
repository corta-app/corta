# Corta — guía para trabajar en el proyecto

> Para personas y para cualquier IA de programación (Claude Code, Codex, Gemini/Antigravity…). `CLAUDE.md` y `GEMINI.md` solo
> importan este archivo: la guía es una sola.

Corta es un editor de video para Shorts, Reels y TikTok. Transcribe el video en el computador (whisper.cpp, palabra por palabra) y
la persona edita **el texto**: lo que borra se corta del video. Saca silencios y muletillas, pone subtítulos animados, zooms y textos,
reencuadra a vertical y exporta con ffmpeg. La IA del usuario (Claude Code, Codex o Gemini, con su cuenta) aplica cambios pedidos en
palabras y elige los mejores momentos de un video largo. Interfaz web única; app de Mac (`app/`), Windows y Linux en camino.

**Principios que no se negocian**
1. **Los videos no salen del computador.** Transcripción y exportación locales. No hay servidores propios ni telemetría.
2. **El original nunca se toca.** Todo cambio vive en `proyecto.json`, con historial para deshacer.
3. **La IA es la del usuario** y solo ve el texto con números de palabra y tiempos. Nunca el video ni el audio. Responde
   **operaciones en JSON** que se validan una por una (`editar_ia.aplicar`); jamás se ejecuta nada que venga de la IA.
4. **Estilos = solo datos.** Un estilo nunca ejecuta código; se valida (`subtitulos.validar_estilo`) y sus textos se escapan.
5. **Lo que ves es lo que exportas.** La vista previa (CSS) y la exportación (libass) salen del mismo estilo y la misma lógica.
6. **Gratis y abierto** (AGPL-3.0). Sin cuentas, sin marca de agua, sin límites artificiales.
7. **Nada personal en el código.** La demo y las pruebas usan a «Ana», una presentadora dibujada con voz sintética.

## Mapa del repo

| Ruta | Qué es |
|---|---|
| `bin/` | Python **solo biblioteca estándar**. `proyecto.py` (formato, validación, tramos conservados, tiempo original → exportado, cortar/restaurar palabras, guardar con historial y deshacer), `limpiar.py` (silencios y muletillas por palabras, o `silencedetect` sin transcripción), `subtitulos.py` (estilos y archivo .ass), `render.py` (grafo de ffmpeg: piezas con trim + encuadre + zoom, concat, subtítulos, música con sidechain), `importar.py` (copiar el video, ffprobe, transcribir con `whisper-cli -ml 1 -sow -oj`), `musica.py` (copia la canción elegida a `musica/` del proyecto, sin pisar copias anteriores, y la deja en `musica`), `editar_ia.py` (pedidos, Shorts y crear un Short; `entrada <entrada.json>` para lo que manda la app), `ia.py` (la IA del usuario, sin herramientas), `estado.py` (proyectos, estilos, config y vocabulario para la app), `guardar.py` (guardar y deshacer lo que manda la interfaz, por archivo de entrada), `efecto_formato.py` (formato y validación de un efecto; el MISMO archivo que `corta-catalogo/herramientas/`), `plantilla_formato.py` (formato, validación y referencias de una plantilla; también el MISMO archivo que el catálogo), `plantillas.py` (plantillas incluidas y descargadas, `llenar`/`aplicar`, armar el video de los huecos con ffmpeg, crear/ajustar/cambiar por archivo de entrada, índice e instalar del catálogo), `efectos.py` (efectos incluidos y descargados, tiempos de un efecto en el video exportado y su cadena de ffmpeg con lista blanca; valida el índice del catálogo e instala lo que descarga la app), `vocabulario.py` (corregir palabras sin perder tiempos y el vocabulario de `~/Corta/vocabulario.json`, que `importar.py` aplica al transcribir y le pasa al transcriptor en un archivo, `--prompt-archivo`). El último argumento de cada script es la ruta del JSON de salida. |
| `app/` | App de Mac (SwiftPM, macOS 15, sin proyecto de Xcode). `Sources/Corta/`: `CortaApp.swift` (arranque y menús), `Ventana.swift` (WKWebView + puente: un `case` por acción; trabajos largos y su avance), `Medios.swift` (`corta://`), `Catalogo.swift` (efectos y plantillas de la comunidad, un `Tipo` por cada uno: dominio fijo, sin redirecciones, tamaño máximo y huella SHA-256), `Servicios.swift` (rutas, config, idioma, IA, modelos con huella, `Procesador`, `EnOrden`), `Actualizaciones.swift`. `Sources/Transcribir/` es `corta-transcribir` (whisper.cpp oficial con Metal, mismas opciones que `whisper-cli`). `Corta.icns` sale de `herramientas/generar_icono.mjs`. |
| `build.sh`, `herramientas/empaquetar.sh` | Arman `dist/Corta.app` (Python portátil, ffmpeg/ffprobe y whisper.framework verificados por SHA-256, más bin/, ui/, estilos/, efectos/ y plantillas/) + zip + `.sha256`; `build.sh` la instala en `~/Applications` y se niega si hay una exportación o transcripción en curso. |
| `estilos/` | Estilos de subtítulos incluidos y `README.md` con el formato. |
| `efectos/` | Efectos incluidos (`<categoria>/<id>.json`, solo datos) y `README.md` con el formato. Los de la comunidad viven en el repo `corta-app/corta-catalogo`. |
| `plantillas/` | Plantillas incluidas (`<categoria>/<id>.json`, solo datos) y `README.md` con el formato. Las de la comunidad, en `corta-catalogo/plantillas/`. |
| `ui/` | Interfaz única (`app.js`, `app.css`), `fuentes/` (OFL, las usan la vista previa y ffmpeg), `demo.json` + `demo/ana.mp4` + `demo/musica-demo.mp3` (música sintetizada, sin derechos de terceros) + `demo/foto-1.jpg`, `demo/foto-2.jpg` (dibujos para llenar plantillas; se generan con `herramientas/generar_demo.py`) e `idiomas/en.json`. |
| `docs/` | Página pública (GitHub Pages); `pagina.yml` publica también `ui/` en `/demo/`. |
| `pruebas/` | `correr.sh`, `test_python.py` (exporta de verdad con ffmpeg), `interfaz.mjs` (Playwright), `transiciones.mjs` (vista previa ↔ exportado, con `cuadros_transiciones.py`), `contrato.py` (interfaz ↔ `Ventana.swift`), `casos.json` (casos compartidos Python ↔ JS), `ia_falsa.py`, `datos/`. |
| `herramientas/` | `generar_demo.py` (Pillow, solo para desarrollo), `imagenes.mjs` (capturas de la página), `generar_icono.mjs` (ícono de la app de Mac), `empaquetar.sh` (arma la app de Mac), `revisar_privacidad.sh`. |

## Reglas de la lógica compartida
La misma regla existe en Python (para exportar) y en `ui/app.js` (para la vista previa): `conservados`, `a_salida`, `cortar_palabras`,
`restaurar`, `cortes_por_palabras` (limpiar), `lineas` (subtítulos, con `linea: "fin" | "sigue"` de la persona) y, en
`bin/vocabulario.py`, `normalizar`, `editar_palabras` y `reemplazar_todo` (corregir palabras). Si cambias una, cambia las dos y su
caso en `pruebas/casos.json`.
Todos los tiempos son segundos del video original; una palabra está cortada si su punto medio cae en un corte.

**Corregir subtítulos:** tocar otra vez la palabra elegida (o tocarla sobre la vista previa, con el video en pausa) la edita en el
lugar (`E.editar`, `empezarEdicion`/`terminarEdicion`): Enter guarda, Esc cancela, vacía la quita del subtítulo sin cortar el video. La
palabra mantiene su inicio y fin; varias palabras se reparten el tiempo según su largo. Después, un aviso (`E.sugerencia`) ofrece
cambiarla en todo el video (`reemplazarTodo`, una sola vez en el historial) y recordarla (acción `vocabulario`).

La línea de tiempo de `ui/app.js` tiene pistas (Video con cortes y zooms, Subtítulos, Textos y Música) en el tiempo del original y
solo mueve los bordes `i`/`f` de `cortes`, `zooms` y `textos` (`limitesBorde`, `moverBorde`: sin dar vuelta un tramo ni pisar a sus
vecinos); el formato no cambia. Los bordes se arrastran con eventos de puntero (mouse, toque y lápiz) y son `role="slider"` para el
teclado. En la vista previa la música suena en el tiempo del video exportado (parte en 0 y se repite, como en `render.py`) y baja con
las palabras que quedan (`tramosVoz`, `cuantoBaja`), imitando el sidechain que ffmpeg hace con la voz al exportar.

**Efectos** (`bin/efectos.py`, formato en `efectos/README.md`): JSON de solo datos con `pasos` de tipos y rangos conocidos
(`bin/efecto_formato.py`). Se aplican en el tiempo del video EXPORTADO, después del concat y antes de los subtítulos:
`intervalos_salida`, `uniones`, `segmentos_zoom`, `segmentos_capa` y `valor_en` existen igual en `ui/app.js` (casos «efectos»). La vista
previa usa filtros de CSS (`cssColor`) y ffmpeg las mismas matrices (`matriz_color`); `pruebas/casos.json` («efectos.color») compara
lo que dibuja Chromium con lo que sale de ffmpeg. Lista blanca de filtros: `colorchannelmixer`, `lutrgb`, `gblur`, `perspective`,
`color`, `format`, `geq`, `scale`, `setsar`, `overlay`, `split`, `crop`, `rgbashift`, `eq`, `trim`, `setpts`, `tpad` (la prueba
`Efectos.test_cadena_solo_lista_blanca` lo revisa).
**Transiciones** (pasos de `efecto_formato.TRANSICIONES`: `transicion`, `interferencia`, `destello`, `franjas`, `rebote`, `barrido`,
`zoom_paso`): van en cada unión, en su ventana (`ventanas`); `segmentos_paso`, `segmentos_exposicion`, `cortes_interferencia` (al azar
repetible, Park–Miller) existen igual en `ui/app.js` (casos «efectos.transiciones»). Lo que mueve la imagen lo dibuja la vista previa en
el lienzo `#paso-fx` dentro de la capa del zoom (`pintarPasos`); `pruebas/transiciones.mjs` compara la vista previa con cuadros
exportados de verdad (`pruebas/cuadros_transiciones.py`) y mide cuánto cuesta exportar. Una transición no trabaja fuera de su ventana
(`enable`; la interferencia corre en una rama con solo esos cuadros: `trim` por número de cuadro + `tpad`). Nada del JSON
llega como texto a ffmpeg: solo números formateados por el código. En el proyecto, `efectos` guarda los pasos copiados.
**Cortes en la línea de tiempo:** `divisiones` (para elegir tramos, `tramosEdicion`; al exportar no cortan, pero `uniones` las cuenta:
una transición pestañea ahí como en un corte), «Dividir» (⌘B) en el cabezal, y un tramo
elegido se borra o se recorta hasta el cabezal como un corte `manual` de siempre; también recibe un efecto.

**Plantillas** (`bin/plantillas.py`, formato en `plantillas/README.md` y `bin/plantilla_formato.py`): solo datos; efectos y estilos
por id (`referencias`; `EFECTOS_INCLUIDOS`/`ESTILOS_INCLUIDOS` dicen lo que trae la app y una prueba revisa que sea verdad). Crear =
copiar los clips a `clips/`, `llenar` (qué clip va en cada hueco y desde qué segundo), armar `plantilla-N.mp4` del tamaño del lienzo
(lista blanca: `trim, setpts, tpad, fps, scale, crop, setsar, format, atrim, asetpts, aresample, aformat, apad, anullsrc, concat`) y
`aplicar` (divisiones en las uniones, textos, efectos por hueco, zoom de fotos, transición alrededor de cada unión, estilo, efectos
de todo el video). `llenar`, `aplicar`, `iniciosHuecos` y `uniones` (con divisiones) existen igual en `ui/app.js` (casos «plantillas»).
`plantilla` en el proyecto ({id, huecos}) solo lo cambia `plantillas.py` (`ajustar`, `cambiar`: vuelven a armar en un archivo nuevo y
borran el anterior); `guardar.py` lo conserva como `fuente`, y `deshacer` vuelve a lo editado pero con el video armado de ahora.

**Cambios de la IA:** `editar_ia.aplicar` marca lo que agrega con `origen: <id>` (`ia-<base36>`) y anota el cambio en `cambios_ia`
(qué agregó, qué ajustes cambió con su valor anterior, cortes que volvió a poner y palabras corregidas). Cada tarjeta de la pestaña IA
sale de ahí y «Quitar estos N zooms» llama `quitarCambioIA` (solo en `ui/app.js`): quita lo que sigue tal como lo dejó la IA,
devuelve los ajustes que nadie volvió a cambiar y conserva (sin `origen`) lo que la persona ya editó, contándolo en `conservados`.
El resultado se guarda como cualquier edición (y se puede deshacer).

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` y la app responde con `window.Corta.<funcion>(json)`; en el navegador responde `simular()`.
Acciones: `listo, config, guardarProyecto, deshacer, elegirVideo, soltarVideo, transcribir, limpiar, pedirIA, buscarShorts, crearShort,
exportar, probarIA, descargarModelo, elegirMusica, abrirEnlace, abrirCarpeta, buscarActualizacion, actualizar, vocabulario, catalogoEfectos, descargarEfecto,
catalogoPlantillas, descargarPlantilla, elegirClips, ajustarHueco, cambiarClip`. Respuestas: `estado,
proyectoActualizado, progreso, limpiado, iaRespondio, shortsListos, exportarProgreso, exportado, iaProbada, modeloProgreso,
modeloListo, musicaElegida, actualizacionRevisada, actualizacionProgreso, vocabularioActualizado, catalogoListo, efectoDescargado,
catalogoPlantillasListo, plantillaDescargada, plantillaArmada`. Plantillas: `catalogoPlantillas` baja `plantillas/index.json` y, para
ofrecer los efectos que falten, también `efectos/index.json` → `catalogoPlantillasListo` `{ok, plantillas, efectos}`;
`descargarPlantilla` (`{id}`) igual que un efecto → `plantillaDescargada` `{ok, plantilla}`; `elegirClips` (`{plantilla, n}`) abre el
selector múltiple (videos y fotos; HEIC pasa a JPEG con ImageIO; orden por nombre) y corre `plantillas.py entrada` `crear`;
`ajustarHueco` (`{carpeta, hueco, desde}`) y `cambiarClip` (`{carpeta, hueco}`, con selector) vuelven a armar. Las tres responden
`plantillaArmada` `{ok, carpeta, proyecto, faltan?}` o `{ok: false, error}` (sin `error` si se canceló). `corta://` también sirve
`clips/<archivo>` de un proyecto (las miniaturas de la pestaña Clips). `catalogoEfectos` baja
`efectos/index.json` del catálogo y responde `catalogoListo` con lo que validó `bin/efectos.py indice`; `descargarEfecto` (`{id}`) busca
ese id en el último índice validado, baja el archivo, compara tamaño y SHA-256 y `bin/efectos.py entrada` (`instalar`) lo valida y lo deja en
`~/Corta/.corta/efectos/`; responde `efectoDescargado` con `{ok, efecto}` o `{ok: false, id, error}`. `vocabulario` (`{accion: "agregar" |
"quitar" | "palabra" | "quitar_palabra", de?, a?, palabra?}`) corre `bin/vocabulario.py entrada` y responde `vocabularioActualizado`
con `{ok, vocabulario}`. `pruebas/contrato.py` revisa que cada acción exista en `simular()`, en
`Ventana.swift` (y en Windows/Linux cuando exista) y que cada función que llama la app exista en `window.Corta`. Una acción nueva va en
`ui/app.js`, en `Ventana.swift` y simulada en `simular()`. El video se sirve como `corta://video/<carpeta>/<archivo>` (`Medios.swift`,
con rangos): solo el `fuente.archivo` de un proyecto o un archivo de su `musica/`, en una carpeta directa de `~/Corta` con
`proyecto.json`, sin enlaces que salgan de `~/Corta`.
`elegirMusica` (`{carpeta}`) abre el selector de archivos de audio y corre `bin/musica.py <carpeta> <archivo>`; responde
`musicaElegida` con `{ok, carpeta, proyecto}` o `{ok: false, error}` (sin `error` si la persona canceló). La música queda dentro de la
carpeta y se sirve igual que el video (`corta://video/<carpeta>/musica/<nombre>`). Quitarla o cambiar el volumen es `guardarProyecto`.

**Bienvenida (primer uso, `config.bienvenida` sin marcar):** el paso 0 es el idioma y va antes que todo: «Elige tu idioma · Choose
your language» con «Español» y «English» escritos en su propio idioma (`data-sin-traducir`), el del sistema sugerido y enfocado. Mientras
tanto no se pinta la app detrás ni el video, los avisos (`toast`) esperan y no corren atajos ni se suelta un video. Al elegir se guarda
`idioma_ui` igual que en Ajustes (`host.enviar("config")` + `cargarIdioma(codigo)`) y siguen, ya en ese idioma, «Hola», la IA y el
transcriptor. Quien ya hizo la bienvenida no la repite; el idioma se cambia en Ajustes. Una app nativa no debe mostrar ni pedir nada
(avisos de actualización, descargas) antes de que la interfaz pase ese paso.

## App de Mac
- Videos y proyectos en `~/Corta`; el código va dentro de la app (`Contents/Resources/corta`: bin/, ui/ sin la demo, estilos/) y los
  scripts corren con el Python portátil incluido (`CORTA_RECURSOS`). ffmpeg, ffprobe y `corta-transcribir` van en `Contents/MacOS`
  (`CORTA_PROGRAMAS`): `proyecto.programa()` los prefiere a los del sistema. Las variables `CORTA_*` de afuera no llegan a los scripts.
- ffmpeg y ffprobe abren solo archivos: `proyecto.SOLO_ARCHIVOS` (`-protocol_whitelist file`) antes de cada entrada y la ruta con
  `proyecto.entrada()` (`file:` + ruta absoluta). Nunca va texto de la persona en los argumentos: los pedidos a la IA, los títulos y
  los proyectos van en un JSON de entrada (`Procesador.conEntrada`); toda carpeta que manda la interfaz pasa por
  `Rutas.proyecto` (Swift) y `proyecto.carpeta_valida` (Python). `guardar.py` no deja cambiar `fuente` ni apuntar la música fuera de `musica/`.
- La IA corre sin herramientas ni MCP (`claude --disallowedTools "*" --strict-mcp-config`, `codex -s read-only`), igual al probarla.
- La ventana solo carga archivos de `ui/` (navegación), el puente solo atiende al marco principal con origen `file` y la interfaz tiene
  acceso de lectura solo a `ui/` (lo demás, por `corta://`). Un enlace https se abre en el navegador.
- Transcribir y exportar: el avance lo dejan los scripts en `<carpeta>/estado.json`; `Ventana` lo lee cada medio segundo (`progreso`,
  `exportarProgreso`). Guardar, deshacer, limpiar y música corren de a uno (`EnOrden`). No se actualiza ni se arma con `build.sh`
  mientras hay un trabajo en curso.
- Arranque: menús y ventana de inmediato; revisar actualizaciones (`CortaApp.iniciarTareas`) parte solo cuando `Idioma.elegido`.
- Modelos de whisper: los descarga la app (`Modelos`, huella SHA-256 fija, los mismos de Graba y Minuta) en `~/Corta/.corta/modelos`.
- Desarrollo en el Mac: el checkout va en `~/Developer/corta` (macOS no distingue `~/corta` de `~/Corta`); `bash build.sh` arma e
  instala en `~/Applications/Corta.app` y deja `~/Corta/.corta/desarrollo` (actualizar = `git pull` + armar). Compilar solo:
  `cd app && swift build -c release`. Swift solo compila en un Mac (o en el job `mac` de GitHub).
- Toda descarga del armado (Python, ffmpeg, ffprobe, whisper.xcframework) tiene su huella fija en `empaquetar.sh` o `Package.swift`;
  si no coincide, el armado se detiene. Nunca cambies una huella sin comprobarla contra el archivo de origen.

## Reglas al cambiar cosas
- Código, comentarios, commits y textos en **español** (de Chile neutro). Todo texto nuevo visible va con su traducción en
  `ui/idiomas/en.json` en el mismo cambio, como frase completa con marcadores (`T("Listo: quedó **{s} s** más corto.", {s})`).
- Contenido del usuario (títulos, palabras) con `esc()` y `data-sin-traducir`.
- No cambies el formato de `proyecto.json` sin compatibilidad (subir `formato` y migrar).
- Antes de cerrar un cambio: `bash pruebas/correr.sh` y mirar la interfaz (`cd ui && python3 -m http.server 8765`, `?idioma=en`,
  `?bienvenida`, `?vacio`, `window.Corta._probar(E => …)`), también a ancho de celular y en modo claro y oscuro.
- Privacidad: `bash herramientas/revisar_privacidad.sh` antes de cada commit. Nunca subas videos reales: `.gitignore` solo deja los de la demo.
- Commits con autor `@users.noreply.github.com`. El repo es público: cada commit se ve al tiro.

## Revisar aportes
Todo entra por pull request y lo junta quien mantiene el proyecto, solo con su aprobación. Leer todo el diff antes de correr nada
(alerta roja: workflows, scripts de instalación, red nueva, dependencias nuevas, binarios, cambios en cómo se arma el comando de
ffmpeg o de la IA). Estilos nuevos: válidos, con fuente libre incluida y una captura. Efectos y plantillas: se aportan en `corta-catalogo` (si
cambia un formato, `bin/efecto_formato.py` o `bin/plantilla_formato.py` cambia igual en los dos repos y la app sube su validación
antes que el catálogo; si cambian los efectos o estilos incluidos, también `EFECTOS_INCLUIDOS`/`ESTILOS_INCLUIDOS`). Detalle en `CONTRIBUTING.md`.

**Seguridad** ([SECURITY.md](SECURITY.md)): las fallas se reportan en privado. Las actions van fijadas por SHA completo con su versión en un
comentario (Dependabot las sube), con `permissions` mínimos, `persist-credentials: false`, nunca `pull_request_target` ni
`${{ github.event.* }}` dentro de `run:`. La página de `docs/` tiene una Content-Security-Policy con la huella de cada script en
línea: si cambias uno, `pruebas/test_python.py` (clase `Seguridad`) dice la huella nueva para `script-src`.
