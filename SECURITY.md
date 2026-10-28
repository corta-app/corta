# Seguridad

Corta es gratis y abierta, y tus videos nunca salen de tu computador. Si encuentras una falla de seguridad, gracias por avisar: la arreglamos antes de contarla.
*(English below.)*

## Cómo reportar una falla (en privado)
**No abras un issue público ni lo cuentes en Discussions.** Usa el reporte privado de GitHub:
[**Reportar una vulnerabilidad**](https://github.com/corta-app/corta/security/advisories/new) (pestaña *Security* → *Report a vulnerability*).
Solo lo ven quienes mantienen el proyecto.

Cuéntanos qué pasa, cómo repetirlo (pasos, archivo o tema de ejemplo **con datos ficticios**), qué versión o commit usas y en qué
sistema. Nunca mandes un video real tuyo ni de otra persona: arma el ejemplo con un video de prueba.

Qué puedes esperar:
- Respuesta en **7 días** como máximo, diciendo si lo pudimos repetir.
- Mientras lo arreglamos te contamos cómo va. Cuando salga la versión con el arreglo publicamos un aviso (GitHub Security Advisory)
  y, si quieres, te damos el crédito.
- Pedimos no publicar detalles hasta que el arreglo esté disponible (como regla general, 90 días como máximo).

## Qué cuenta
- Que un **proyecto, un estilo de subtítulos, un efecto o una plantilla del catálogo o una respuesta de la IA** logre ejecutar código, leer o escribir archivos fuera de la
  carpeta del proyecto, o inyectar algo en el comando de ffmpeg o en la interfaz (XSS).
- Que un video, una canción o una transcripción hagan que Corta lea o mande datos a otra parte.
- Cualquier cosa que saque un video, su audio o su texto del computador sin que la persona lo pida.
- Problemas en los workflows de GitHub o en cómo se arma la app que permitan colar código.

No cuentan: fallas de tu IA (Claude Code, Codex, Gemini) o de ffmpeg o whisper.cpp (repórtalas a ellos; si Corta las expone de más, sí cuenta); ataques que ya necesitan control total del
computador; o pedir encabezados que GitHub Pages no deja configurar en la página pública.

## Cómo nos protegemos
- Todo entra por pull request y lo junta quien mantiene el proyecto, después de leer el diff completo (ver [CONTRIBUTING.md](CONTRIBUTING.md)).
- Las GitHub Actions están fijadas por SHA, con permisos mínimos y sin `pull_request_target`; Dependabot propone actualizaciones con
  unos días de espera (`.github/dependabot.yml`).
- Python solo con biblioteca estándar; la interfaz y el motor no tienen dependencias de npm.
- La interfaz tiene una Content-Security-Policy sin `unsafe-eval` ni scripts en línea; todo lo que viene de afuera se valida y se escapa.
- En la app de Mac, la ventana solo carga la interfaz que viene adentro, el puente solo le responde a ella y los videos se sirven por
  `corta://` solo desde los proyectos de `~/Corta`. ffmpeg solo abre archivos locales (`-protocol_whitelist file`), la IA corre sin
  herramientas y lo que se descarga al armar la app (Python, ffmpeg, whisper.cpp) o al usarla (modelos) tiene su huella SHA-256 fija.
- Los efectos de la comunidad son solo datos: la app los baja solo de `raw.githubusercontent.com/corta-app/corta-catalogo`, sin seguir
  redirecciones y con tamaño máximo, compara la huella SHA-256 del índice y los valida con el mismo formato que el catálogo antes de
  guardarlos. Ningún texto de un efecto llega a ffmpeg: el código arma los filtros (de una lista blanca) con sus números.
- Las plantillas (incluidas o del catálogo) siguen las mismas reglas: solo datos, sin archivos ni rutas (usan efectos y estilos por
  su id), validadas con el mismo formato que el catálogo (`bin/plantilla_formato.py`). Los clips que eliges se copian a `clips/`
  del proyecto y se arman con una lista blanca de filtros de ffmpeg y solo números. La interfaz no puede cambiar qué archivo va en
  cada hueco: eso lo hace `bin/plantillas.py` con lo que elegiste en el selector de archivos.

---

## Security policy (English)
**Please don't open a public issue.** Report vulnerabilities privately through GitHub:
[**Report a vulnerability**](https://github.com/corta-app/corta/security/advisories/new). Include what happens, how to reproduce it (with
**fictional data only**), the version or commit and your OS. We reply within **7 days**, keep you posted, publish a GitHub Security
Advisory with the fix and credit you if you want. Please don't disclose details until a fix is out (90 days at most as a general rule).

In scope: code execution, file access outside the project folder, ffmpeg command or UI (XSS) injection through projects, caption styles, catalog effects or templates, or AI responses; anything that makes media or text leave the computer; CI/build issues that let code slip in. Out of scope: bugs in your own AI CLI or in ffmpeg or whisper.cpp, attacks that already require full control of the
device, and headers GitHub Pages can't set.
