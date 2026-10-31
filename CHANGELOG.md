# Cambios · Changelog

Lo que cambia para quien usa Corta, en palabras simples. Las versiones anteriores a este archivo están en
[Releases](https://github.com/corta-app/corta/releases).
*What changes for people using Corta, in plain words. Earlier versions are listed in Releases.*

## Sin publicar · Unreleased

- Sin conexión, la galería de efectos y plantillas de la comunidad muestra la última lista que viste (para descargar, vuelve a
  abrirla con conexión).
  *When you're offline, the community effects and templates gallery shows the last list you saw (to download, open it again once
  you're connected).*
- Si el modelo de voz que elegiste no está descargado pero tienes el otro, Corta transcribe con ese en vez de detenerse. Además
  descarta más frases que whisper inventa en los silencios (como «Gracias por ver» o los créditos de subtítulos).
  *If the voice model you chose isn't downloaded but you have the other one, Corta transcribes with it instead of stopping. It also
  drops more phrases whisper makes up in silences (like "Thanks for watching" or subtitle credits).*
- Ahora eliges la apariencia en Ajustes: como el sistema, clara u oscura. Con «Como el sistema» Corta se ve igual que antes.
  *You can now choose the appearance in Settings: match system, light or dark. With "Match system" Corta looks the same as before.*
- Ahora puedes contarnos un error o una idea desde Ajustes → Acerca de → «Enviar comentarios»: se abre GitHub con tu mensaje listo
  y tú decides si lo publicas.
  *You can now tell us about a bug or an idea from Settings → About → "Send feedback": GitHub opens with your message ready and you
  decide whether to post it.*
- Los diálogos se manejan mejor con teclado: el foco entra al abrirlos (en su título, así el lector de pantalla lo lee), Tab no se sale, Esc o tocar afuera los cierra y el foco
  vuelve a donde estaba. Los avisos esperan su turno en vez de taparse, y al actualizar ves en qué paso va.
  *Dialogs work better with the keyboard: focus moves in when they open (to their title, so screen readers read it), Tab stays inside, Esc or clicking outside closes them and
  focus goes back where it was. Notices wait their turn instead of covering each other, and when updating you see which step it's on.*
- En «Tu IA» solo se destaca un botón, y si una IA no está instalada puedes tocar «Revisar de nuevo» después de instalarla.
  *In "Your AI" only one button stands out, and if an AI isn't installed you can tap "Check again" after installing it.*
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
