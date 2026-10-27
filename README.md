<p align="center"><img src="docs/img/logo.png" width="96" alt="Corta"></p>

<h1 align="center">Corta</h1>

<p align="center"><b>El editor gratis y de código abierto para Shorts, Reels y TikTok.</b><br>
Editas el texto y se edita el video. Subtítulos animados, sin silencios ni muletillas, y tu propia IA hace el trabajo pesado.<br>
Todo en tu computador: tus videos no se suben a ningún lado. Sin marca de agua.</p>

<p align="center"><a href="https://corta-app.github.io/corta/">Sitio</a> ·
<a href="https://corta-app.github.io/corta/demo/">Vista previa</a> ·
<a href="https://github.com/corta-app/corta/discussions">Comunidad</a> ·
<a href="CONTRIBUTING.md">Cómo aportar</a> ·
<a href="SECURITY.md">Seguridad</a> ·
<a href="#english">English</a></p>

---

## Qué hace
- **Edita por texto.** Corta transcribe tu video en tu computador, palabra por palabra. Borras una frase y se borra del video.
- **Saca silencios y muletillas** de una vez («eh», «mmm», pausas largas). Lo puedes deshacer cuando quieras.
- **Subtítulos animados** al estilo de los Shorts, en cualquier idioma. Los estilos son archivos simples que cualquiera puede crear.
- **Vertical primero:** 9:16, 1:1, 4:5 o 16:9, con encuadre ajustable o fondo borroso para videos horizontales.
- **Dile a tu IA lo que quieres:** «pon zoom cuando digo el precio», «saca la parte donde me equivoco», «pon un título al inicio».
- **Shorts desde un video largo:** tu IA elige los mejores momentos de una clase, un podcast o un live, y cada uno queda como un video nuevo.
- **Música de fondo que baja sola cuando hablas**, y una **línea de tiempo con pistas** (video, subtítulos, textos y música) donde
  arrastras los bordes con el mouse, el dedo o el teclado.

## Tus videos son tuyos
- Transcripción (whisper.cpp) y exportación (ffmpeg) en tu computador. **No hay servidores de Corta**, ni cuentas, ni telemetría.
- La IA es **la tuya** (Claude Code, Codex o Gemini), con tu cuenta, y solo ve el texto con sus tiempos. Nunca el video ni el audio.
- El video original nunca se modifica: los cambios viven en un `proyecto.json` abierto, con historial para deshacer.
- Sin marca de agua, sin límite de resolución ni de duración.

## Estado
Versión 0.1, recién nacida. Ya funcionan el motor (cortes, silencios, subtítulos, zooms, textos, encuadre, exportación vertical,
edición con IA y Shorts) y la interfaz. La app de escritorio para Mac, Windows y Linux viene en camino. Puedes
[probar la interfaz con un video de mentira](https://corta-app.github.io/corta/demo/).

## Cómo funciona
```
tu video ──► whisper (en tu computador) ──► palabras con tiempos ──► editas el texto / limpias / le pides a tu IA
                                                                         │
                                         proyecto.json (cortes, subtítulos, zooms, textos) ◄─┘
                                                                         │
                                               ffmpeg ──► exportado-9x16.mp4 (con subtítulos)
```

## Formato del proyecto
Cada video vive en `~/Corta/<fecha> <nombre>/`: `original.<ext>` (tu video tal cual), `proyecto.json`, `historial/` (para deshacer),
`musica/` (una copia de la música que elegiste) y lo que exportas. `proyecto.json` es abierto: puedes armar tus propios scripts encima (ver [`ejemplos/`](ejemplos/)).

| Campo | Qué guarda |
|---|---|
| `fuente` | `{archivo, duracion, ancho, alto}` del video original. |
| `lienzo`, `relleno`, `encuadre` | Formato (`9:16`, `1:1`, `4:5`, `16:9`), `recorte` o `desenfoque`, y qué parte del video se ve (`x`, `y` de 0 a 1). |
| `palabras` | `[{t, i, f}]`: cada palabra con su inicio y fin en segundos del original. |
| `cortes` | `[{i, f, motivo}]`: lo que no va. `motivo`: `silencio`, `muletilla`, `manual`, `ia` o `fuera` (fuera de un Short). |
| `subtitulos` | `{activos, estilo, palabras_por_linea, posicion}` |
| `zooms`, `textos` | `[{i, f, escala}]` y `[{i, f, texto, y}]` |
| `musica` | `null` o `{archivo, volumen}`: `archivo` relativo a la carpeta del proyecto (la app copia la canción a `musica/`) o una ruta absoluta; `volumen` de 0 a 1. La música baja sola cuando hablas. |

Todos los tiempos están en segundos **del video original**: los cortes dicen qué se saca y lo demás se conserva.

## Desarrollo
Necesitas Python 3 (solo biblioteca estándar), ffmpeg y, para transcribir, whisper.cpp (`whisper-cli`).
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
tienes que publicar tu código con la misma licencia. Las tipografías de `ui/fuentes/` usan la [SIL Open Font License](ui/fuentes/OFL.txt).

---

## English
**Corta** ("cut") is a free, open-source editor for Shorts, Reels and TikTok. It transcribes your video on your computer, so you edit
the video by editing its text; it removes silences and filler words in one click, adds animated captions in any language, reframes
landscape footage to vertical, and lets your own AI (Claude Code, Codex or Gemini, with your account) apply edits from plain requests
or pick the best moments of a long video as new Shorts. Add background music that ducks itself under your voice and fine-tune cuts,
zooms and text on a multi-track timeline. Videos never leave your computer, there's no watermark, and the project is a
plain open JSON file. Caption styles are data-only files anyone can create. Spanish-first, English included. Licensed under AGPL-3.0.
