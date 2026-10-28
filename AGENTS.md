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
| `bin/` | Python **solo biblioteca estándar**. `proyecto.py` (formato, validación, tramos conservados, tiempo original → exportado, cortar/restaurar palabras, guardar con historial y deshacer), `limpiar.py` (silencios y muletillas por palabras, o `silencedetect` sin transcripción), `subtitulos.py` (estilos y archivo .ass), `render.py` (grafo de ffmpeg: piezas con trim + encuadre + zoom, concat, subtítulos, música con sidechain), `importar.py` (copiar el video, ffprobe, transcribir con `whisper-cli -ml 1 -sow -oj`), `musica.py` (copia la canción elegida a `musica/` del proyecto, sin pisar copias anteriores, y la deja en `musica`), `editar_ia.py` (pedidos, Shorts y crear un Short; `entrada <entrada.json>` para lo que manda la app), `ia.py` (la IA del usuario, sin herramientas), `estado.py` (proyectos, estilos y config para la app), `guardar.py` (guardar y deshacer lo que manda la interfaz, por archivo de entrada). El último argumento de cada script es la ruta del JSON de salida. |
| `app/` | App de Mac (SwiftPM, macOS 15, sin proyecto de Xcode). `Sources/Corta/`: `CortaApp.swift` (arranque y menús), `Ventana.swift` (WKWebView + puente: un `case` por acción; trabajos largos y su avance), `Medios.swift` (`corta://`), `Servicios.swift` (rutas, config, idioma, IA, modelos con huella, `Procesador`, `EnOrden`), `Actualizaciones.swift`. `Sources/Transcribir/` es `corta-transcribir` (whisper.cpp oficial con Metal, mismas opciones que `whisper-cli`). `Corta.icns` sale de `herramientas/generar_icono.mjs`. |
| `build.sh`, `herramientas/empaquetar.sh` | Arman `dist/Corta.app` (Python portátil, ffmpeg/ffprobe y whisper.framework verificados por SHA-256, más bin/, ui/ y estilos/) + zip + `.sha256`; `build.sh` la instala en `~/Applications` y se niega si hay una exportación o transcripción en curso. |
| `estilos/` | Estilos de subtítulos incluidos y `README.md` con el formato. |
| `ui/` | Interfaz única (`app.js`, `app.css`), `fuentes/` (OFL, las usan la vista previa y ffmpeg), `demo.json` + `demo/ana.mp4` + `demo/musica-demo.mp3` (música sintetizada, sin derechos de terceros; se generan con `herramientas/generar_demo.py`) e `idiomas/en.json`. |
| `docs/` | Página pública (GitHub Pages); `pagina.yml` publica también `ui/` en `/demo/`. |
| `pruebas/` | `correr.sh`, `test_python.py` (exporta de verdad con ffmpeg), `interfaz.mjs` (Playwright), `contrato.py` (interfaz ↔ `Ventana.swift`), `casos.json` (casos compartidos Python ↔ JS), `ia_falsa.py`, `datos/`. |
| `herramientas/` | `generar_demo.py` (Pillow, solo para desarrollo), `imagenes.mjs` (capturas de la página), `generar_icono.mjs` (ícono de la app de Mac), `empaquetar.sh` (arma la app de Mac), `revisar_privacidad.sh`. |

## Reglas de la lógica compartida
La misma regla existe en Python (para exportar) y en `ui/app.js` (para la vista previa): `conservados`, `a_salida`, `cortar_palabras`,
`restaurar`, `cortes_por_palabras` (limpiar) y `lineas` (subtítulos). Si cambias una, cambia las dos y su caso en `pruebas/casos.json`.
Todos los tiempos son segundos del video original; una palabra está cortada si su punto medio cae en un corte.

La línea de tiempo de `ui/app.js` tiene pistas (Video con cortes y zooms, Subtítulos, Textos y Música) en el tiempo del original y
solo mueve los bordes `i`/`f` de `cortes`, `zooms` y `textos` (`limitesBorde`, `moverBorde`: sin dar vuelta un tramo ni pisar a sus
vecinos); el formato no cambia. Los bordes se arrastran con eventos de puntero (mouse, toque y lápiz) y son `role="slider"` para el
teclado. En la vista previa la música suena en el tiempo del video exportado (parte en 0 y se repite, como en `render.py`) y baja con
las palabras que quedan (`tramosVoz`, `cuantoBaja`), imitando el sidechain que ffmpeg hace con la voz al exportar.

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` y la app responde con `window.Corta.<funcion>(json)`; en el navegador responde `simular()`.
Acciones: `listo, config, guardarProyecto, deshacer, elegirVideo, soltarVideo, transcribir, limpiar, pedirIA, buscarShorts, crearShort,
exportar, probarIA, descargarModelo, elegirMusica, abrirEnlace, abrirCarpeta, buscarActualizacion, actualizar`. Respuestas: `estado,
proyectoActualizado, progreso, limpiado, iaRespondio, shortsListos, exportarProgreso, exportado, iaProbada, modeloProgreso,
modeloListo, musicaElegida, actualizacionRevisada, actualizacionProgreso`. `pruebas/contrato.py` revisa que cada acción exista en
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
ffmpeg o de la IA). Estilos nuevos: válidos, con fuente libre incluida y una captura. Detalle en `CONTRIBUTING.md`.

**Seguridad** ([SECURITY.md](SECURITY.md)): las fallas se reportan en privado. Las actions van fijadas por SHA completo con su versión en un
comentario (Dependabot las sube), con `permissions` mínimos, `persist-credentials: false`, nunca `pull_request_target` ni
`${{ github.event.* }}` dentro de `run:`. La página de `docs/` tiene una Content-Security-Policy con la huella de cada script en
línea: si cambias uno, `pruebas/test_python.py` (clase `Seguridad`) dice la huella nueva para `script-src`.
