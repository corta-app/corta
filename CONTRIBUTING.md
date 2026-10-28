# Cómo aportar a Corta

Corta es gratis y abierta, y la hacemos entre todos. Hay lugar para cualquiera, programes o no. *(English below.)*

## Sin programar
- **Crea un estilo de subtítulos:** es un archivo JSON corto (formato en [`estilos/README.md`](estilos/README.md)). Pruébalo y
  compártelo con una captura.
- **Crea un efecto o un filtro:** también es un JSON corto (formato en [`efectos/README.md`](efectos/README.md)). Se comparte en el
  [catálogo de la comunidad](https://github.com/corta-app/corta-catalogo) y cualquiera lo descarga gratis desde la app.
- **Crea una plantilla:** huecos para clips o fotos con sus duraciones, efectos, transiciones y textos (formato en
  [`plantillas/README.md`](plantillas/README.md)). También se comparte en el [catálogo](https://github.com/corta-app/corta-catalogo#plantillas),
  y ahí la puedes proponer con palabras, sin escribir el JSON.
- **Pruébala con tus videos** y cuéntanos qué tal: los issues con la etiqueta [`probar`](https://github.com/corta-app/corta/labels/probar)
  piden justo eso.
- **Conversa:** dudas, ideas o lo que publicaste editado con Corta → [Discussions](https://github.com/corta-app/corta/discussions).
- **Cuéntanos qué falla o qué te gustaría** en [issues](https://github.com/corta-app/corta/issues/new/choose).
- **Traducciones:** revisa o mejora `ui/idiomas/en.json`, o propón otro idioma.

## Programando (con o sin IA)
1. Lee [`AGENTS.md`](AGENTS.md): cómo funciona, reglas y cómo se conectan las piezas. Sirve igual para personas y para tu IA.
2. Haz un fork, una rama y tu cambio. La sección "Desarrollo" del [README](README.md#desarrollo) explica cómo correrla.
3. Corre `bash pruebas/correr.sh` (lo mismo que revisa GitHub en cada cambio).
4. Si tu cambio se nota (una función nueva, otra forma de hacer algo, otra pantalla), deja al día lo que lo cuenta: el
   README, la página (`docs/`), las capturas y [`CHANGELOG.md`](CHANGELOG.md). Si no sabes bien qué tocar, dilo en el pull
   request y lo completamos nosotros.
5. Abre un pull request contando qué cambia para quien usa Corta y cómo lo probaste.

Reglas que importan: código, comentarios y textos en español (todo texto nuevo de la interfaz con su traducción en `ui/idiomas/en.json`);
**nunca subas videos reales ni datos personales**; solo biblioteca estándar en Python; la vista previa y la exportación tienen que verse
igual; y no romper el [formato del proyecto](README.md#formato-del-proyecto).

Los aportes entran con la licencia del proyecto, [AGPL-3.0](LICENSE).

## Cómo revisamos
Todo entra por pull request y lo junta alguien que mantiene el proyecto: nadie puede subir cambios directo. Revisamos:
- **Siempre:** que las pruebas de GitHub pasen, que no haya datos personales y que el cambio haga lo que dice. Si es tu primer
  aporte, GitHub espera a que aprobemos correr las pruebas (es normal).
- **Que la documentación diga la verdad:** si el cambio agrega, cambia o quita algo que se nota, revisamos que el
  README, la página, las guías y el `CHANGELOG.md` cuenten la app como queda. Lo que falte lo completamos antes de juntar.
- **Código:** que no cambie el formato del proyecto, que la lógica compartida cambie en Python y JS a la vez, que los textos tengan
  traducción y que no agregue dependencias ni conexiones a internet nuevas sin conversarlo.
- **Efectos y plantillas** (en el catálogo): que pasen la validación, que el nombre y la descripción digan lo que hacen y que se vean
  bien. Las plantillas, además, sin música, video ni imágenes de nadie.
- **Estilos:** que sean válidos, que la fuente sea libre y venga incluida, y que se vean bien en la vista previa y exportados.
- **Traducciones:** que una persona que hable el idioma revise el texto.

Si algo falta te lo pedimos con un comentario; casi nunca cerramos un aporte sin conversar.

¿Buscas por dónde empezar? Mira los issues con la etiqueta
[`good first issue`](https://github.com/corta-app/corta/labels/good%20first%20issue) (o [`sin programar`](https://github.com/corta-app/corta/labels/sin%20programar)) o pregunta en Discussions.

**¿Encontraste una falla de seguridad?** No abras un issue: repórtala en privado como explica [SECURITY.md](SECURITY.md).

Al participar aceptas el [código de conducta](CODE_OF_CONDUCT.md).

---

## Contributing (English)
- **No code needed:** create a caption style, an effect or a template (short JSON files; effects and templates are shared in the
  [community catalog](https://github.com/corta-app/corta-catalogo), where you can also propose a template in plain words), try Corta with your videos (label `probar`), chat in
  [Discussions](https://github.com/corta-app/corta/discussions), report bugs or ideas, and help with translations.
- **Code (with or without AI):** read [`AGENTS.md`](AGENTS.md), fork, branch, run `bash pruebas/correr.sh` and open a pull request.
  Code and comments are in Spanish; UI text needs its English entry in `ui/idiomas/en.json`; never commit real videos or personal data.
  If your change is visible, also update the README, the page (`docs/`), screenshots and `CHANGELOG.md`, or say so in the
  pull request and we'll do it.
- **Review:** everything goes through a pull request and a maintainer merges it. Contributions are licensed under AGPL-3.0.
  We also check that the README, the page and the docs still describe the app as it is.
- **Security issues:** don't open a public issue; report them privately as explained in [SECURITY.md](SECURITY.md).
