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
| `bin/` | Python **solo biblioteca estándar**. `proyecto.py` (formato, validación, tramos conservados, tiempo original → exportado, cortar/restaurar palabras, guardar con historial y deshacer), `limpiar.py` (silencios y muletillas por palabras, o `silencedetect` sin transcripción), `subtitulos.py` (estilos y archivo .ass), `render.py` (grafo de ffmpeg: piezas con trim + velocidad + encuadre + zoom, concat, subtítulos, música con sidechain; su lista blanca de filtros está al inicio del archivo y la prueba `Velocidad.test_grafo_solo_lista_blanca` la revisa), `importar.py` (copiar el video, ffprobe y transcribir palabra por palabra con la pieza «transcribir», sin VAD), `musica.py` (copia la canción elegida a `musica/` del proyecto, sin pisar copias anteriores, y la deja en `musica`), `editar_ia.py` (pedidos, Shorts y crear un Short; `entrada <entrada.json>` para lo que manda la app), `nucleo.py` (pieza «nucleo»: `app.json`, carpeta de datos, config validada, escritura atómica), `ia.py` (pieza «ia»: la IA del usuario, sin herramientas ni memoria, en una carpeta temporal; `ia.py probar <entrada {ia}> <salida>`; errores como `{codigo, valores}` que `ia.frase()` pasa a texto), `estado.py` (proyectos, estilos, config y vocabulario para la app), `guardar.py` (guardar y deshacer lo que manda la interfaz, por archivo de entrada), `efecto_formato.py` (formato y validación de un efecto; la pieza «catálogo» usa `validar_efecto` y `CLAVES`; el MISMO archivo que `corta-catalogo/herramientas/`), `plantilla_formato.py` (formato, validación y referencias de una plantilla; también el MISMO archivo que el catálogo), `plantillas.py` (plantillas incluidas y descargadas, `llenar`/`aplicar`, armar el video de los huecos con ffmpeg, crear/ajustar/cambiar por archivo de entrada), `efectos.py` (efectos incluidos y descargados, tiempos de un efecto en el video exportado y su cadena de ffmpeg con lista blanca), `vocabulario.py` (corregir palabras sin perder tiempos y el vocabulario de `~/Corta/vocabulario.json`, que `importar.py` aplica al transcribir y le pasa al transcriptor (pieza «transcribir»: en un archivo privado 0600, fuera del proyecto, que se borra al terminar; `corta-transcribir --prompt-archivo` o `whisper-cli @archivo`, el vocabulario en una sola línea; nunca como argumento)), `transcribir.py` (pieza «transcribir»), `catalogo.py` (pieza «catálogo»). El último argumento de cada script es la ruta del JSON de salida. |
| `app/` | App de Mac (SwiftPM, macOS 15, sin proyecto de Xcode). `Sources/Corta/`: `CortaApp.swift` (arranque y menús), `Ventana.swift` (WKWebView + puente: un `case` por acción; trabajos largos y su avance), `Medios.swift` (`corta://`), `Servicios.swift` (rutas, config, idioma, IA, modelos con huella, `Procesador`, `EnOrden`), `Actualizaciones.swift`. `Sources/PiezaCatalogo/` es la pieza «catálogo» (su propio target: efectos y plantillas de la comunidad, dominio fijo, sin redirecciones, tamaño máximo y huella SHA-256; se configura en `CortaApp` con `app.json`). `Sources/Transcribir/` es `corta-transcribir` (whisper.cpp oficial con Metal, mismas opciones que `whisper-cli`). `Corta.icns` sale de `herramientas/generar_icono.mjs`. |
| `build.sh`, `herramientas/empaquetar.sh` | Arman `dist/Corta.app` (Python portátil, ffmpeg/ffprobe y whisper.framework verificados por SHA-256, más bin/, ui/, estilos/, efectos/, plantillas/ y app.json) + zip + `.sha256`; `build.sh` la instala en `~/Applications` y se niega si hay una exportación o transcripción en curso. |
| `estilos/` | Estilos de subtítulos incluidos y `README.md` con el formato. |
| `efectos/` | Efectos incluidos (`<categoria>/<id>.json`, solo datos) y `README.md` con el formato. Los de la comunidad viven en el repo `corta-app/corta-catalogo`. |
| `plantillas/` | Plantillas incluidas (`<categoria>/<id>.json`, solo datos) y `README.md` con el formato. Las de la comunidad, en `corta-catalogo/plantillas/`. |
| `app.json`, `piezas.json` | **Pieza** (ver «Piezas»): `app.json` describe la app para las piezas (id, nombre, datos, plataformas, claves de config); `piezas.json` lo escribe `pieza.py` (versión y huella de cada archivo copiado). |
| `ui/` | Interfaz única (`app.js`, `app.css`; de Pieza: `i18n.js`, `host.js`, `tema.js`/`tema.css` y `componentes.js`/`componentes.css`), `fuentes/` (OFL, las usan la vista previa y ffmpeg), `demo.json` + `demo/ana.mp4` + `demo/musica-demo.mp3` (música sintetizada, sin derechos de terceros) + `demo/foto-1.jpg`, `demo/foto-2.jpg` (dibujos para llenar plantillas; se generan con `herramientas/generar_demo.py`) e `idiomas/en.json`. |
| `docs/` | Página pública (GitHub Pages); `pagina.yml` publica también `ui/` en `/demo/`. |
| `pruebas/` | `correr.sh`, `test_python.py` (exporta de verdad con ffmpeg), `interfaz.mjs` (Playwright), `transiciones.mjs` (vista previa ↔ exportado, con `cuadros_transiciones.py`), `velocidad.mjs` (velocidad por tramo: cada cuadro y cada palabra exportados contra la vista previa, con `cuadros_velocidad.py`, y el costo de exportar), `contrato.py` (interfaz ↔ `Ventana.swift`), `casos.json` (casos compartidos Python ↔ JS), `ia_falsa.py`, `datos/`. |
| `CHANGELOG.md` | Lo que cambia para quien usa la app, en palabras simples (ver «Lo que rodea a un cambio»). |
| `herramientas/` | `generar_demo.py` (Pillow, solo para desarrollo), `imagenes.mjs` (capturas de la página), `generar_icono.mjs` (ícono de la app de Mac), `empaquetar.sh` (arma la app de Mac), `revisar_privacidad.sh`. |

## Piezas (de [Pieza](https://github.com/pieza-app/pieza))
Corta usa piezas de Pieza, la base de la familia de apps: código probado que se copia a la app (modelo «copiar y adueñarse»).

| Pieza | Versión | Archivos | Qué usa Corta |
|---|---|---|---|
| `nucleo` | 0.7.0 | `bin/nucleo.py` | `app.json`, carpeta de datos (`~/Corta/.corta`: `"datos": "visible"`; en las pruebas `CORTA_CARPETA` mueve `~/Corta` entero; `"privado": true` deja todo JSON en 0600, como antes), config validada por `app.json`, `leer_json`/`escribir_json` atómicos, `recursos()`. `proyecto.py` lo envuelve: `config()` suma lo de siempre (`CONFIG_DEFECTO`); `idioma_audio` va como `-l` del transcriptor y `app.json` solo lo deja «auto» o un código de idioma (`"patron": "auto|[a-z]{2,3}"`). Lo propio de Corta (`carpeta_valida`, `SOLO_ARCHIVOS`, `entrada`, `programa`) sigue en `proyecto.py`. |
| `ia` | 0.6.2 | `bin/ia.py` | `preguntar`, `nombre`, `frase`, `probar`. Lo propio de Corta (prompts y operaciones JSON) sigue en `editar_ia.py`, que responde `{ok: false, error, codigo}` (`error_ia`: la frase de la pieza, o la de Corta en `FRASES_IA` cuando dice dónde se elige la IA). La app de Mac prueba la IA con `Procesador.conEntrada("ia.py", "probar", ["ia": id])` (ya no arma el comando en Swift) y le pasa a la interfaz la respuesta tal cual; la fila de «Tu IA» (pieza «componentes») muestra el error traducido con su `plantilla` y `valores`. |
| `i18n` | 0.3.1 | `ui/i18n.js` | `T`, `Tp`, `tr`, `frase`, `traducirDOM` y `cargarIdioma` con `i18n.elegir` (elegido > `?idioma=` > config > sistema); se carga antes que `app.js`. `E.idioma` es una copia de `i18n.idioma`. `ui/idiomas/en.json` lleva `codigo` y `nombre` (los paquetes se validan). |
| `host-ui` | 0.2.0 | `ui/host.js` | `host = PiezaHost.crearHost({nombre: "corta", global: "Corta", simular})`: `host.enviar` (Mac `webkit.messageHandlers.corta`, Electron `window.cortaEscritorio`, navegador `simular()`; los datos viajan como copia JSON también en la vista previa), `HOST = host.plataforma` y `<html data-host>`. Las respuestas van en `host.responder({…})` (quedan en `window.Corta`); `window.Corta._pruebas` va aparte porque no es una función. `simular` atiende lo propio y deja `probarIA`, `buscarActualizacion`, `actualizar` y `abrirEnlace` a `PiezaHost.simulacionesComunes()`. |
| `tema` | 0.2.1 | `ui/tema.css`, `ui/tema.js` | Los tokens de color (`--fondo`, `--panel`, `--panel-2`, `--linea`, `--texto`, `--texto-suave`, `--acento`, `--sobre-acento`, `--rojo`, `--verde`, `--acento-suave`, `--rojo-suave`…) con `light-dark()`. `app.css` solo define los pares de Corta (`--x-claro`/`--x-oscuro`), también los de lo propio (`--lateral`, `--corte-fuerte`/`--corte-suave` para `--corte`, `--escenario`, `--violeta*`, `--azul*`), elegidos con `light-dark()` y con su respaldo `@supports` para navegadores sin él. El modo va en `<html data-pz-modo>`: se lee con `tema.valor`/`tema.resuelto()`, nunca del atributo. Ajustes → Apariencia (`tema.selectorHTML()`, config `tema`: sistema, claro u oscuro; «sistema» se ve igual que antes); `?tema=oscuro` para capturas. |
| `componentes` | 0.3.0 | `ui/componentes.js`, `ui/componentes.css` | `ui = PiezaComponentes.crear({…})`: `ui.dialogo` (cada `dialogoX()` devuelve `{titulo, valores?, cuerpo, pie, cerrable?, sinEsc?}`; `cerrarDialogo()` es el ✕/Esc/velo; el detalle de una plantilla vuelve a la lista con Esc), `toast` = `ui.aviso` (en cola; mientras se elige el idioma esperan con `retener`), `ui.filasIA` (`probarIA {ia}`; al probar bien guarda `config.ia`), `ui.filaActualizacion` (`actualizacionDisponible`/`Revisada` con `{pintar: false}` para no pintar detrás del idioma) y `ui.acercaDe` (con «Enviar comentarios» → issue en GitHub; la versión llega por `crear({version: () => E.version})`). El foco de un diálogo parte en su título (`data-autofoco` solo en un campo, o en el idioma sugerido); `confirmar({peligro})` lo deja en «Cancelar». El detalle de una plantilla pone «‹ Plantillas» en `antes`. Clases `pz-`: `.pz-boton` (+ `.pz-principal`, `.pz-plano`, `.pz-peligro`; `.grande` y `.chico` son de Corta), `.pz-fila`/`.pz-txt`, `.pz-chip`, `.pz-seg`, `.pz-ok`, `.pz-error-texto`. `app.css` les da la forma de Corta; el editor conserva sus tamaños (`:root { --pz-boton-alto: 0px; --pz-chip-alto: 0px }`) y la pieza sube a `--pz-tactil` (44 px) solo lo suyo (diálogos, filas de Ajustes, avisos) en celular y pantallas táctiles; la ✕ (`.pz-cerrar`) nunca baja de 36 px. Llamar `ui.despuesDePintar()` al final de `pintar()` y `ui.capas()` dentro de lo pintado. |
| `transcribir` | 0.2.0 | `bin/transcribir.py` | `importar.transcribir` llama `transcribir.transcribir(audio, palabras=True, idioma, modelo, vocabulario)` → `{t, i, f}` en segundos del original (3 decimales, la puntuación suelta pegada a la palabra anterior, sin marcas ni inventos). **Sin VAD** (palabra por palabra es lo de siempre en la pieza) aunque el detector esté descargado: puede recortar la palabra del borde y aquí cada palabra es un borde de corte. El vocabulario va por `--prompt-archivo` (`corta-transcribir`) o `whisper-cli @archivo`, en un temporal 0600 que se borra; la transcripción, en una carpeta temporal (ya no queda `transcripcion.json` en el proyecto). Modelos en `~/Corta/.corta/modelos` (`modelo_elegido(config.modelo)`: si falta el elegido usa el otro). La descarga de modelos sigue en `Modelos` de `Servicios.swift` (mismos archivos y huellas). Errores `ErrorTranscribir` → `{ok: false, error, codigo}`. |
| `catalogo` | 0.2.0 | `bin/catalogo.py`, `app/Sources/PiezaCatalogo/Catalogo.swift` | `app.json` → `catalogo`: repo `corta-app/corta-catalogo`, tipos `efectos` (validador `efecto_formato`) y `plantillas` (`plantilla_formato`), cada uno con su `index.json`, 64 KB por archivo, 512 KB el índice y 500 entradas; `singular` (`efecto`/`plantilla`) para que las respuestas sigan trayendo `efecto`/`plantilla`. `"funcion"` (`validar_efecto`/`validar_plantilla`) y `"campos": "CLAVES"` dicen qué usa la pieza del validador, sin alias en los archivos compartidos con el catálogo; el validador recibe el objeto entero y después se recorta a `CLAVES`. `efectos.disponibles()`/`plantillas.disponibles()` son `catalogo.listar(tipo)` por id (`origen`: «incluido» o «descargado», también en las plantillas). Swift: target `PiezaCatalogo`, `Catalogo.configurar(appJSON:agente:correr:)` en `CortaApp` y `Catalogo.listar/descargar(tipo, …)` en `Ventana.swift`. Los descargados siguen en `~/Corta/.corta/efectos/` y `plantillas/` (la carpeta de datos de siempre: no hubo que migrar nada). El índice del catálogo puede seguir con `archivo`/`bytes`: la pieza devuelve `ruta`/`tamano`. Errores `{codigo, frase}` → `errorCatalogo(r)` en `app.js` (en `plantilla` llega la plantilla descargada). Sin conexión, `Catalogo.listar` devuelve la última lista validada con `sin_conexion: true`: la galería se ve, con un aviso, y descargar pide conexión. |

- **No edites a mano los archivos de una pieza.** Se actualizan con «Pieza al día» (`.github/workflows/pieza-al-dia.yml`, una vez por
  semana abre un PR o un issue) o con `python3 <pieza>/herramientas/pieza.py actualizar .`. Si hay que cambiar algo, el cambio va
  primero a Pieza (`pieza.py diferencias . <pieza>` lo muestra) y vuelve desde allá; `pieza.py estado .` dice si algo quedó distinto.
- `app.json` va dentro de la app (`herramientas/empaquetar.sh` lo copia a `Contents/Resources/corta/`): `bin/nucleo.py` lo busca junto
  a `bin/`. Las claves de config que acepta `Config.guardar` (Swift) son las de `app.json` (una prueba lo revisa).
- `.gitignore` es una lista blanca: `app.json` y `piezas.json` están en ella.
- La pantalla del idioma (paso 0 de la bienvenida) es de Corta: `.pz-capa.capa-idioma` con `data-pz-sin-esc` y `data-autofoco` en el
  idioma sugerido, para que la pieza «componentes» le dé el foco sin dejar cerrarla.
- No adoptadas: `red` (los scripts de Corta no salen a internet: lo que baja, lo baja la app) y `trabajos` (transcribir y exportar
  son un solo paso con su `estado.json`; no hay etapas, preguntas ni «seguir donde quedó» que justifiquen el cambio).
- No adoptadas todavía: `bienvenida` y `actualizaciones` (se están mejorando en Pieza; la bienvenida de Corta tiene su paso de
  transcriptor y su `Actualizaciones.swift` arma con `empaquetar.sh` en desarrollo).

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
**Velocidad por tramo** (`velocidades` en el proyecto, formato en el README): todo sigue en segundos del original y la velocidad
entra solo al pasar al tiempo exportado: `lento(vels, a, b)` (lo que dura a..b exportado: la integral de 1/v; en una rampa, la
lentitud sigue un smoothstep y su integral es un polinomio, sin aproximar), `a_salida`, `duracion_final`, `velocidad_en`,
`audio_de` y `poner_velocidad` (recorta lo que había en el tramo) existen igual en `bin/proyecto.py` y `ui/app.js` (casos
«velocidad», comparados exactos), y `intervalos_salida`/`uniones` los usan. Así subtítulos, textos, efectos, música y el reloj quedan
sincronizados solos. Al exportar (`render.piezas`) cada pieza se parte también en los bordes de una velocidad: `setpts` (`PTS/v` o la
expresión de la rampa, `tiempo_vel`), `framerate`/`minterpolate` si se suaviza (`SUAVIZAR`), `fps`, y `tpad`+`trim` la dejan justo
del largo de `lento`; la voz va con `atempo` encadenado (cada uno entre 0,5 y 2), en escalones en una rampa (`tramos_audio`), o
muda (`volume=0` + `apad`/`atrim`). La música se agrega después: nunca se acelera. En la vista previa, `aplicarVelocidad` pone
`playbackRate` (con `preservesPitch`) y `muted` en cada cuadro; la línea de tiempo dibuja cada tramo con lo que dura exportado
(`ltX`/`ltT`). `tramosEdicion` también parte en los bordes de una velocidad (el tramo lento se elige solo); el panel «Velocidad» del
tramo (`panelVelocidad`, `cambiarVelocidad`) guarda solo lo que no es lo de siempre. La IA tiene la operación `velocidad` (solo donde
no hay otra, para que «Quitar» deje todo igual). `pruebas/velocidad.mjs` compara cada cuadro exportado con la vista previa y mide
el costo (los números están junto a `render.SUAVIZAR`: suavizar con «mezcla» casi no cuesta; «movimiento» tarda ~13 veces más).
**Cortes en la línea de tiempo:** `divisiones` (para elegir tramos, `tramosEdicion`; al exportar no cortan, pero `uniones` las cuenta:
una transición pestañea ahí como en un corte), «Dividir» (⌘B) en el cabezal, y un tramo
elegido se borra o se recorta hasta el cabezal como un corte `manual` de siempre; también recibe un efecto.

**Plantillas** (`bin/plantillas.py`, formato en `plantillas/README.md` y `bin/plantilla_formato.py`): solo datos; efectos y estilos
por id (`referencias`; `EFECTOS_INCLUIDOS`/`ESTILOS_INCLUIDOS` dicen lo que trae la app y una prueba revisa que sea verdad). Crear =
copiar los clips a `clips/`, `llenar` (qué clip va en cada hueco y desde qué segundo), armar `plantilla-N.mp4` del tamaño del lienzo
(lista blanca: `trim, setpts, tpad, fps, scale, crop, setsar, format, atrim, asetpts, aresample, aformat, apad, anullsrc, concat`) y
`aplicar` (divisiones en las uniones, textos, efectos por hueco, zoom de fotos, transición alrededor de cada unión, estilo, efectos
de todo el video y `velocidad` de cada hueco como un tramo de `velocidades`). `llenar`, `aplicar`, `iniciosHuecos` y `uniones` (con divisiones) existen igual en `ui/app.js` (casos «plantillas»).
`plantilla` en el proyecto ({id, huecos}) solo lo cambia `plantillas.py` (`ajustar`, `cambiar`: vuelven a armar en un archivo nuevo y
borran el anterior); `guardar.py` lo conserva como `fuente`, y `deshacer` vuelve a lo editado pero con el video armado de ahora.

**Cambios de la IA:** `editar_ia.aplicar` marca lo que agrega (zooms, textos, cortes, efectos y velocidades) con `origen: <id>` (`ia-<base36>`) y anota el cambio en `cambios_ia`
(qué agregó, qué ajustes cambió con su valor anterior, cortes que volvió a poner y palabras corregidas). Cada tarjeta de la pestaña IA
sale de ahí y «Quitar estos N zooms» llama `quitarCambioIA` (solo en `ui/app.js`): quita lo que sigue tal como lo dejó la IA,
devuelve los ajustes que nadie volvió a cambiar y conserva (sin `origen`) lo que la persona ya editó, contándolo en `conservados`.
El resultado se guarda como cualquier edición (y se puede deshacer).

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` (pieza «host-ui») y la app responde con `window.Corta.<funcion>(json)` (las de `host.responder`); en
el navegador responde `simular()`. `probarIA` es `{ia}` → `iaProbada {ia, ok, codigo?, plantilla?, valores?, error?}` (lo que devuelve
`ia.py probar`); `actualizacionRevisada` es `{hay, notas, sinConexion}` y `estado.actualizacion` es `{hay, notas}`. La pieza
«componentes» también manda `probarIA`, `config`, `buscarActualizacion`, `actualizar` y `abrirEnlace` (`pruebas/contrato.py` las lee de `ui/componentes.js`).
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
`efectos/index.json` del catálogo y responde `catalogoListo` con lo que validó `bin/catalogo.py indice` (`{ok, tipo, efectos}`, cada uno
con `ruta`, `sha256` y `tamano`); `descargarEfecto` (`{id}`) busca ese id en el último índice validado, baja el archivo, compara tamaño y
SHA-256 y `bin/catalogo.py instalar` lo vuelve a comparar con ese índice, lo valida y lo deja en `~/Corta/.corta/efectos/`; responde
`efectoDescargado` con `{ok, efecto}` o `{ok: false, tipo, id, codigo, plantilla, error}` (la interfaz muestra `Tp(plantilla)`). `vocabulario` (`{accion: "agregar" |
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
- La IA corre sin herramientas ni MCP (`claude --disallowedTools "*" --strict-mcp-config`, `codex -s read-only`), igual al probarla
  (la app la prueba con `bin/ia.py probar`, pieza «ia»);
  sin las variables `CORTA_*` (`ia._entorno`), Claude sin la memoria de la persona (`SIN_MEMORIA_CLAUDE`) y el pedido a Antigravity
  siempre en `instrucciones.md`, nunca en `-p`. Instalar un efecto o plantilla exige `sha256` (64 hex) y `T()` escapa sus valores.
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
- Archivos de piezas (`bin/nucleo.py`, `bin/ia.py`, `ui/i18n.js`, `ui/host.js`, `ui/tema.*`, `ui/componentes.*`): no se editan aquí; ver «Piezas».
- Colores solo con los tokens de la pieza «tema» (`var(--texto-suave)`, `var(--panel-2)`…); un color nuevo que cambia con el modo va como par `--x-claro`/`--x-oscuro`, elegido con `light-dark()` y repetido en el respaldo `@supports` de `app.css`.
- Antes de cerrar un cambio: `bash pruebas/correr.sh` y mirar la interfaz (`cd ui && python3 -m http.server 8765`, `?idioma=en`,
  `?bienvenida`, `?vacio`, `window.Corta._probar(E => …)`), también a ancho de celular y en modo claro y oscuro.
- Privacidad: `bash herramientas/revisar_privacidad.sh` antes de cada commit. Nunca subas videos reales: `.gitignore` solo deja los de la demo.
- Commits con autor `@users.noreply.github.com`. El repo es público: cada commit se ve al tiro.

## Lo que rodea a un cambio
Un cambio está listo cuando la app **y lo que la cuenta** dicen lo mismo. Antes de empezar, anota qué tipo de cambio es; al terminar,
revisa cada fila ("no aplica" se decide, no se supone):

| Si el cambio… | Deja al día |
|---|---|
| agrega o cambia una función | la página (`docs/`: funciones, «cómo funciona», comparación, preguntas frecuentes), el README y la guía si la hay |
| cambia lo que se ve | capturas de la página y del README (datos ficticios, español e inglés, normal y celular) e imagen para compartir si sale esa vista |
| cambia un flujo o un paso | instrucciones paso a paso, preguntas frecuentes, textos de la bienvenida e instalación si la toca |
| quita algo | bórralo de la página, el README y las guías: nada que prometa lo que ya no hace |
| cambia el formato de datos o el puente | la documentación del formato, `ejemplos/` si existe y esta guía |
| cambia carpetas, reglas o pruebas | esta guía (`AGENTS.md`) y `CONTRIBUTING.md` |
| actualiza o agrega una pieza | `piezas.json` (lo escribe `pieza.py`), la tabla «Piezas» de esta guía y `app.json` si pide config |
| resuelve un issue | ciérralo con «Resuelto en …» dando crédito y abre issues para lo que quedó pendiente |
| lo nota quien usa Corta | `CHANGELOG.md`: una línea en «Sin publicar», en lenguaje de persona («Ahora puedes…»), en español e inglés |

Todo texto nuevo de la página y del README va en los dos idiomas, sin nada inventado. Antes de cerrar, busca con `grep` en `docs/` y el
README el nombre o el texto viejo de lo que cambió. Al publicar una versión, las líneas de «Sin publicar» pasan a su número.
Los issues que abrimos para una tarea traen una sección «Qué actualizar alrededor» con las filas de esta tabla que le tocan.

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
