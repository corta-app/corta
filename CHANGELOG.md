# Cambios · Changelog

Lo que cambia para quien usa Corta, en palabras simples. Las versiones anteriores a este archivo están en
[Releases](https://github.com/corta-app/corta/releases).
*What changes for people using Corta, in plain words. Earlier versions are listed in Releases.*

## Sin publicar · Unreleased

- Tu vocabulario (nombres y marcas) ahora también ayuda a transcribir con `whisper-cli`, y va siempre en un archivo privado que se
  borra al terminar: nunca queda en la carpeta del video ni a la vista de otros programas.
  *Your vocabulary (names and brands) now also helps transcribe with `whisper-cli`, and it always goes in a private file that is
  deleted when done: it never stays in the video's folder or visible to other programs.*
- Por dentro, tu IA, los ajustes y los idiomas usan las piezas compartidas de la familia ([Pieza](https://github.com/pieza-app/pieza)).
  Al probar tu IA en Ajustes, Corta la prueba igual que cuando edita (sin herramientas, sin tu memoria y en una carpeta temporal),
  y si algo falla te dice por qué en tu idioma. Si tu IA es tan antigua que no conoce esas protecciones, Corta te pide actualizarla
  en vez de usarla sin ellas.
  *Under the hood, your AI, settings and languages use the family's shared pieces ([Pieza](https://github.com/pieza-app/pieza)).
  When you test your AI in Settings, Corta tests it the same way it edits (no tools, no memory, in a temporary folder), and if
  something fails it tells you why in your language. If your AI is too old to know those protections, Corta asks you to update it
  instead of using it without them.*
- Corta solo instala efectos y plantillas de la comunidad que traen su huella completa y coinciden con ella; si falta, no se instalan.
  *Corta only installs community effects and templates that come with their full fingerprint and match it; otherwise they are not installed.*
- Tu IA ya no recibe los datos internos de Corta ni tu memoria de Claude, y lo que le pides a Gemini (Antigravity) ya no queda a la vista de otros programas.
  *Your AI no longer receives Corta's internal settings or your Claude memory, and what you ask Gemini (Antigravity) is no longer visible to other programs.*
- Los nombres de archivos, plantillas e IA se muestran siempre como texto, nunca como parte de la página.
  *File, template and AI names are always shown as plain text, never as part of the page.*
