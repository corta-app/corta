// Interfaz de Corta: la misma en Mac (WKWebView), Windows y Linux (Electron) y en el navegador (vista previa con demo.json).
// La app manda el estado con window.Corta.estado(json); la interfaz pide cosas con host.enviar(accion, datos).
// La vista previa reproduce el video original saltando los cortes y dibuja los subtítulos con el mismo estilo que exporta ffmpeg.
(() => {
  "use strict";
  const HOST = window.CORTA_HOST || "web";
  document.documentElement.dataset.host = HOST;
  const E = {
    proyectos: [], sel: null, estilos: [], config: {}, ias: [], modelos: { lista: [] }, version: "", carpeta: "", progreso: {},
    pestana: "texto", seleccion: null, ancla: null, ia: { texto: "", enviando: false, historial: [] }, shorts: null, buscandoShorts: false,
    limpiando: false, ultimoAhorro: null, exportar: null, bv: null, bvCerrada: false, ajustes: false, probando: {}, resultadoIA: {},
    descarga: null, actualizacion: { hay: false }, act: null, buscando: null, idioma: "es", textos: {}, soltar: false,
    lt: { zoom: 1, sel: null, ancho: 0 },  // línea de tiempo: zoom horizontal, tramo elegido ({lista, k}) y ancho visible en px
    vocabulario: { reemplazos: [], palabras: [] },
    editar: null,      // palabra(s) que se están corrigiendo: {desde, hasta, valor, donde: "texto" | "vista"}
    sugerencia: null,  // después de corregir: {de, a, n, todo, recordado} («¿Cambiar en todo el video?», «Recordar»)
    efectos: [],       // los que se pueden usar: incluidos y descargados (bin/efectos.py)
    fx: { categoria: "todos", busqueda: "" },
    catalogo: null,    // efectos de la comunidad: {estado: "cargando" | "listo" | "error", efectos, error, categoria, busqueda, bajando: {id: true}}
    plantillas: [],    // las que se pueden usar: incluidas y descargadas (bin/plantillas.py)
    // Elegir una plantilla: {fuente: "corta" | "comunidad", categoria, busqueda, ver: id | null, armando, bajando: {id: true},
    // catalogo: null | {estado, plantillas, efectos, error}, pendiente: id de un efecto que espera el catálogo}
    pl: null,
    armando: null,     // hueco de una plantilla que se está volviendo a armar ({carpeta, k})
  };
  const ENLACES = { sitio: "https://corta-app.github.io/corta/", codigo: "https://github.com/corta-app/corta",
    comunidad: "https://github.com/corta-app/corta/discussions", guiaIA: "https://corta-app.github.io/corta/ia.html",
    catalogo: "https://github.com/corta-app/corta-catalogo#readme", plantillas: "https://github.com/corta-app/corta-catalogo#plantillas" };
  const LIENZOS = { "9:16": [1080, 1920], "1:1": [1080, 1080], "4:5": [1080, 1350], "16:9": [1920, 1080] };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ───────────── Puente con la app ─────────────
  const host = {
    enviar(accion, datos = {}) {
      const msg = { accion, datos };
      if (window.webkit?.messageHandlers?.corta) return window.webkit.messageHandlers.corta.postMessage(msg);
      if (window.cortaEscritorio) return window.cortaEscritorio.enviar(msg);
      return simular(accion, datos);
    },
  };

  // ───────────── Idiomas (las claves son el texto en español) ─────────────
  function tr(t) {
    if (E.idioma === "es" || !t) return t;
    const limpio = String(t).replace(/\s+/g, " ").trim();
    if (!limpio) return t;
    if (E.textos[limpio]) return t.replace(limpio, E.textos[limpio]);
    if (window._faltantes && /\p{L}{2}/u.test(limpio)) window._faltantes.add(limpio);
    return t;
  }
  /** Frase completa con marcadores ({x}, {n}…): se traduce entera y después se ponen los valores. Va dentro de data-sin-traducir. */
  function T(plantilla, valores = {}) {
    let t = plantilla;
    if (E.idioma !== "es") {
      if (E.textos[plantilla]) t = E.textos[plantilla];
      else if (window._faltantes) window._faltantes.add(plantilla);
    }
    t = esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    for (const [k, v] of Object.entries(valores)) t = t.split(`{${k}}`).join(String(v));
    return t;
  }
  /** Como T(), pero en texto plano (para atributos como aria-label; escápalo con esc() al ponerlo). */
  function Tp(plantilla, valores = {}) {
    let t = plantilla;
    if (E.idioma !== "es") {
      if (E.textos[plantilla]) t = E.textos[plantilla];
      else if (window._faltantes) window._faltantes.add(plantilla);
    }
    for (const [k, v] of Object.entries(valores)) t = t.split(`{${k}}`).join(String(v));
    return t;
  }
  const frase = (plantilla, valores, etiqueta = "span") => `<${etiqueta} data-sin-traducir>${T(plantilla, valores)}</${etiqueta}>`;
  function traducirDOM(raiz) {
    if (E.idioma === "es") return;
    const w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
    const nodos = []; let n; while ((n = w.nextNode())) nodos.push(n);
    for (const t of nodos) {
      const el = t.parentElement;
      if (!el || el.closest("[data-sin-traducir], script, style") || !/\p{L}/u.test(t.nodeValue)) continue;
      const v = tr(t.nodeValue); if (v !== t.nodeValue) t.nodeValue = v;
    }
    for (const el of raiz.querySelectorAll("[title],[aria-label],[placeholder]")) {
      if (el.closest("[data-sin-traducir]")) continue;
      for (const a of ["title", "aria-label", "placeholder"]) { const v = el.getAttribute(a); if (v) el.setAttribute(a, tr(v)); }
    }
  }
  /** Carga el idioma: el que la persona acaba de elegir (Ajustes o la bienvenida), ?idioma= de la vista previa, el guardado o el del sistema. */
  async function cargarIdioma(elegido) {
    const pedido = new URLSearchParams(location.search).get("idioma");
    const codigo = elegido || pedido || E.config.idioma_ui || ((navigator.language || "es").startsWith("es") ? "es" : "en");
    if (codigo === E.idioma && (codigo === "es" || Object.keys(E.textos).length)) return;
    E.idioma = codigo; E.textos = {};
    if (codigo !== "es") { try { E.textos = (await (await fetch(`idiomas/${codigo}.json`)).json()).textos || {}; } catch { E.idioma = "es"; } }
    document.documentElement.lang = E.idioma;
  }

  // ───────────── Lógica del proyecto (la misma que bin/proyecto.py, limpiar.py y subtitulos.py; casos en pruebas/casos.json) ─────────────
  const r3 = (n) => Math.round(n * 1000) / 1000;
  function unir(tramos, margen = 0) {
    const r = [];
    for (const t of [...tramos].sort((a, b) => a.i - b.i)) {
      if (r.length && t.i <= r[r.length - 1].f + margen) r[r.length - 1].f = Math.max(r[r.length - 1].f, t.f);
      else r.push({ i: t.i, f: t.f });
    }
    return r;
  }
  function conservados(p, minimo = 0.04) {
    const dur = p.fuente.duracion, r = [];
    let t = 0;
    for (const c of unir(p.cortes || [])) {
      if (c.i - t >= minimo) r.push({ i: r3(t), f: r3(Math.min(c.i, dur)) });
      t = Math.max(t, c.f);
    }
    if (dur - t >= minimo) r.push({ i: r3(t), f: r3(dur) });
    return r;
  }
  const duracionFinal = (p) => r3(conservados(p).reduce((a, t) => a + t.f - t.i, 0));
  function aSalida(p, t, tramos) {
    let acumulado = 0;
    for (const tr_ of tramos || conservados(p)) {
      if (tr_.i <= t && t <= tr_.f) return r3(acumulado + t - tr_.i);
      acumulado += tr_.f - tr_.i;
    }
    return null;
  }
  const palabraCortada = (p, w, cortes) => { const m = (w.i + w.f) / 2; return (cortes || unir(p.cortes || [])).some((c) => c.i <= m && m <= c.f); };
  function cortarPalabras(p, desde, hasta, motivo = "manual") {
    const w = p.palabras;
    desde = Math.max(0, desde); hasta = Math.min(w.length - 1, hasta);
    if (desde > hasta) return;
    const i = desde === 0 ? w[desde].i : (w[desde - 1].f + w[desde].i) / 2;
    const f = hasta === w.length - 1 ? w[hasta].f : (w[hasta].f + w[hasta + 1].i) / 2;
    p.cortes.push({ i: r3(i), f: r3(f), motivo });
  }
  function restaurar(p, i, f) {
    const nuevos = [];
    for (const c of p.cortes || []) {
      if (c.f <= i || c.i >= f) { nuevos.push(c); continue; }
      if (c.i < i) nuevos.push({ ...c, f: r3(i) });
      if (c.f > f) nuevos.push({ ...c, i: r3(f) });
    }
    p.cortes = nuevos;
  }
  const MULETILLAS = new Set(["eh", "ehh", "ehhh", "em", "emm", "ehm", "mm", "mmm", "mmmm", "um", "umm", "uh", "uhh", "er", "erm", "ah", "ahh", "hmm", "hm"]);
  const MARGEN = 0.12;
  const limpia = (t) => t.toLowerCase().replace(/[^\p{L}\p{N}_]/gu, "");
  function cortesPorPalabras(palabras, silencioMin, muletillas, duracion) {
    const cortes = [];
    if (muletillas) palabras.forEach((w, k) => {
      if (!MULETILLAS.has(limpia(w.t))) return;
      const i = k === 0 ? w.i : Math.max(palabras[k - 1].f, w.i - 0.05);
      const f = k === palabras.length - 1 ? w.f : Math.min(palabras[k + 1].i, w.f + 0.05);
      cortes.push({ i: r3(i), f: r3(f), motivo: "muletilla" });
    });
    const huecos = [];
    if (palabras.length) {
      huecos.push([0, palabras[0].i]);
      for (let k = 0; k + 1 < palabras.length; k++) huecos.push([palabras[k].f, palabras[k + 1].i]);
      huecos.push([palabras[palabras.length - 1].f, duracion]);
    }
    for (const [a, b] of huecos) {
      if (b - a >= silencioMin + 2 * MARGEN) cortes.push({ i: r3(a + (a === 0 ? 0 : MARGEN)), f: r3(b - (b === duracion ? 0 : MARGEN)), motivo: "silencio" });
    }
    return cortes;
  }
  const MAX_LINEA = 8;  // una línea unida a mano («sigue») igual se corta a este largo
  function lineas(palabras, porLinea) {
    const grupos = []; let actual = [];
    palabras.forEach((w, k) => {
      actual.push(w);
      const sig = palabras[k + 1];
      const cortar = w.linea === "sigue" ? actual.length >= MAX_LINEA
        : w.linea === "fin" || actual.length >= porLinea || /[.!?…,;:]$/.test(w.t) || (sig && sig.i - w.f > 0.6);
      if (cortar || !sig) { grupos.push(actual); actual = []; }
    });
    return grupos;
  }

  // ───────────── Corregir palabras (la misma lógica que bin/vocabulario.py; casos «editar» en pruebas/casos.json) ─────────────
  const ALNUM = /[\p{L}\p{N}]/u;
  const normalizar = (t) => [...String(t).normalize("NFD")].filter((c) => !/\p{M}/u.test(c) && ALNUM.test(c)).join("").toLowerCase();
  /** «¿Calumi?» → ["¿", "Calumi", "?"]: la puntuación de los bordes se conserva al corregir. */
  function partes(t) {
    const c = [...t]; let a = 0, b = c.length;
    while (a < b && !ALNUM.test(c[a])) a++;
    while (b > a && !ALNUM.test(c[b - 1])) b--;
    return [c.slice(0, a).join(""), c.slice(a, b).join(""), c.slice(b).join("")];
  }
  const esMayus = (c) => c !== c.toLowerCase() && c === c.toUpperCase();
  function conMayusculas(original, correcta) {
    if ([...correcta].some(esMayus) || !original) return correcta;
    if ([...original].length > 1 && original === original.toUpperCase() && original !== original.toLowerCase()) return correcta.toUpperCase();
    if (esMayus([...original][0])) return correcta.slice(0, 1).toUpperCase() + correcta.slice(1);
    return correcta;
  }
  const r3a = (n) => Math.floor(n * 1000 + 0.5) / 1000;
  /** Reparte el tiempo i..f entre varias palabras según su largo (letras y números). La última termina justo en f. */
  function repartir(i, f, textos) {
    const pesos = textos.map((t) => Math.max(1, [...t].filter((c) => ALNUM.test(c)).length));
    const total = pesos.reduce((a, b) => a + b, 0); let acumulado = 0, inicio = i;
    return textos.map((t, k) => {
      acumulado += pesos[k];
      const fin = k === textos.length - 1 ? f : r3a(i + (f - i) * acumulado / total);
      const w = { t, i: r3a(inicio), f: r3a(fin) }; inicio = fin; return w;
    });
  }
  const extras = (w) => Object.fromEntries(Object.entries(w).filter(([k]) => !["t", "i", "f"].includes(k)));
  /** Cambia las palabras desde..hasta por `texto` en el mismo tiempo. Vacío = se quitan del subtítulo (el video no se corta). */
  function editarPalabras(palabras, desde, hasta, texto) {
    const w = palabras; desde = Math.max(0, desde); hasta = Math.min(w.length - 1, hasta);
    if (desde > hasta) return [...w];
    const nuevas = String(texto).split(/\s+/).filter(Boolean);
    if (!nuevas.length) return [...w.slice(0, desde), ...w.slice(hasta + 1)];
    const r = repartir(w[desde].i, w[hasta].f, nuevas);
    Object.assign(r[r.length - 1], extras(w[hasta]));
    return [...w.slice(0, desde), ...r, ...w.slice(hasta + 1)];
  }
  const deClaves = (de) => String(de).split(/\s+/).map(normalizar).filter(Boolean);
  /** Pares [{de, a}] por palabra completa, sin tildes ni mayúsculas al comparar. Devuelve [palabras nuevas, cuántas cambiaron]. */
  function reemplazarTodo(palabras, pares) {
    const reglas = pares.map((x) => [deClaves(x.de || ""), String(x.a || "").split(/\s+/).filter(Boolean)]).filter(([c, a]) => c.length && a.length)
      .map((x, k) => [...x, k]).sort((x, y) => y[0].length - x[0].length || x[2] - y[2]);
    const norm = palabras.map((w) => normalizar(w.t)), r = [];
    let k = 0, n = 0;
    while (k < palabras.length) {
      const regla = reglas.find(([c]) => c.every((x, j) => norm[k + j] === x));
      if (!regla) { r.push(palabras[k]); k++; continue; }
      const [claves, a] = regla, grupo = palabras.slice(k, k + claves.length);
      const [antes, primera] = partes(grupo[0].t), despues = partes(grupo[grupo.length - 1].t)[2];
      const textos = a.map((x) => conMayusculas(primera, x));
      textos[0] = antes + textos[0]; textos[textos.length - 1] += despues;
      if (JSON.stringify(grupo.map((w) => w.t)) !== JSON.stringify(textos)) {
        const nuevas = repartir(grupo[0].i, grupo[grupo.length - 1].f, textos);
        Object.assign(nuevas[nuevas.length - 1], extras(grupo[grupo.length - 1]));
        r.push(...nuevas); n++;
      } else r.push(...grupo);
      k += claves.length;
    }
    return [r, n];
  }

  // ───────────── Efectos: tiempos (la misma lógica que bin/efectos.py; casos «efectos» en pruebas/casos.json) ─────────────
  const r4a = (n) => Math.floor(n * 10000 + 0.5) / 10000;
  const alcanceEf = (p, ap) => ("i" in ap ? [ap.i, ap.f] : [0, p.fuente.duracion]);
  /** Los pedazos del tramo i..f (segundos del original) que quedan, en segundos del video exportado. */
  function intervalosSalida(p, i, f) {
    const r = []; let acumulado = 0;
    for (const t of conservados(p)) {
      const a = Math.max(t.i, i), b = Math.min(t.f, f);
      if (b - a >= 0.02) r.push([r3a(acumulado + a - t.i), r3a(acumulado + b - t.i)]);
      acumulado += t.f - t.i;
    }
    return r;
  }
  /** Dónde se juntan dos pedazos del tramo en el video exportado (ahí van las transiciones): un corte en medio o una división
   *  (donde dividiste o donde una plantilla pasa de un clip al siguiente). */
  function uniones(p, i, f) {
    const r = []; let acumulado = 0, anterior = false;
    const divs = (p.divisiones || []).filter((x) => typeof x === "number" && Number.isFinite(x) && i + 0.02 < x && x < f - 0.02).sort((a, b) => a - b);
    for (const t of conservados(p)) {
      const dentro = Math.min(t.f, f) - Math.max(t.i, i) >= 0.02;
      if (dentro && anterior) r.push(r3a(acumulado));
      for (const d of divs) if (t.i + 0.02 < d && d < t.f - 0.02) r.push(r3a(acumulado + d - t.i));
      anterior = dentro; acumulado += t.f - t.i;
    }
    return r;
  }
  function segmentosZoom(paso, a, b) {
    const d = paso.desde, h = paso.hasta, curva = paso.curva || "lineal";
    if (curva === "golpe") { const g = r3a(a + Math.min(0.15, (b - a) / 2)); return [[a, d, g, h], [g, h, b, h]]; }
    if (curva === "suave") {
      const s = (x) => x * x * (3 - 2 * x);
      return Array.from({ length: 8 }, (_, k) => [r3a(a + (b - a) * k / 8), r4a(d + (h - d) * s(k / 8)), r3a(a + (b - a) * (k + 1) / 8), r4a(d + (h - d) * s((k + 1) / 8))]);
    }
    return [[a, d, b, h]];
  }
  function segmentosCapa(paso, a, b, juntas, pedazos) {
    if (paso.tipo === "tinte") return pedazos.map(([x, y]) => [x, paso.fuerza, y, paso.fuerza]);
    if (paso.tipo === "fundido") {
      const r = [];
      if ((paso.entrada || 0) > 0) r.push([a, 1, r3a(Math.min(b, a + paso.entrada)), 0]);
      if ((paso.salida || 0) > 0) r.push([r3a(Math.max(a, b - paso.salida)), 0, b, 1]);
      return r;
    }
    if (paso.tipo === "transicion") { const m = paso.duracion / 2; return juntas.flatMap((j) => [[r3a(j - m), 0, j, 1], [j, 1, r3a(j + m), 0]]); }
    return [];
  }
  function valorEn(segmentos, t, neutro) {
    for (const [t0, v0, t1, v1] of segmentos) if (t0 <= t && t < t1) return t1 > t0 ? r4a(v0 + (v1 - v0) * (t - t0) / (t1 - t0)) : v0;
    return neutro;
  }
  // Rangos de cada campo (los mismos de bin/efecto_formato.py): la vista previa nunca usa un número fuera de ellos.
  const RANGOS_FX = { brillo: [0.5, 1.5], contraste: [0.5, 2], saturacion: [0, 2], tono: [-180, 180], sepia: [0, 1], grises: [0, 1], fuerza: [0, 1],
    radio: [0.5, 20], desde: [1, 1.6], hasta: [1, 1.6], entrada: [0, 3], salida: [0, 3], duracion: [0.1, 1.5] };
  const numFx = (paso, k, def) => { const v = Number(paso[k]); const [lo, hi] = RANGOS_FX[k]; return Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : def; };
  const COLORES_FX = { negro: "0,0,0", blanco: "255,255,255" };
  const rgbFx = (paso) => (paso.tipo === "tinte" && /^#[0-9a-fA-F]{6}$/.test(paso.color || "") ? [1, 3, 5].map((x) => parseInt(paso.color.slice(x, x + 2), 16)).join(",") : COLORES_FX[paso.color] || COLORES_FX.negro);
  /** Un paso «color» como filtros de CSS, en el orden que también usa ffmpeg (bin/efectos.py, matriz_color). */
  function cssColor(paso) {
    const f = [];
    if ("brillo" in paso) f.push(`brightness(${numFx(paso, "brillo", 1)})`);
    if ("contraste" in paso) f.push(`contrast(${numFx(paso, "contraste", 1)})`);
    if ("saturacion" in paso) f.push(`saturate(${numFx(paso, "saturacion", 1)})`);
    if ("tono" in paso) f.push(`hue-rotate(${numFx(paso, "tono", 0)}deg)`);
    if ("sepia" in paso) f.push(`sepia(${numFx(paso, "sepia", 0)})`);
    if ("grises" in paso) f.push(`grayscale(${numFx(paso, "grises", 0)})`);
    return f.join(" ");
  }
  // ───────────── Plantillas: llenar huecos y aplicar (la misma lógica que bin/plantillas.py; casos «plantillas» en pruebas/casos.json) ─────────────
  /** Dónde empieza cada hueco en el video armado, y al final lo que dura todo. */
  function iniciosHuecos(huecos) {
    const r = [0]; let t = 0;
    for (const h of huecos) { t = r3a(t + h.dur); r.push(t); }
    return r;
  }
  /** Qué clip va en cada hueco y desde qué segundo: el primero sin usar que calza (video, foto o cualquiera), si no el primero sin
   *  usar, y otra vuelta cuando se usaron todos. Un video usado en m huecos se parte en m pedazos y cada hueco toma el centro del suyo. */
  function llenar(huecos, clips) {
    const n = clips.length;
    if (!n) return [];
    let usados = new Array(n).fill(false);
    const asignados = [];
    for (const h of huecos) {
      if (usados.every(Boolean)) usados = new Array(n).fill(false);
      const libres = [...Array(n).keys()].filter((c) => !usados[c]);
      const calzan = libres.filter((c) => h.tipo === "cualquiera" || clips[c].tipo === h.tipo);
      const c = (calzan.length ? calzan : libres)[0];
      usados[c] = true; asignados.push(c);
    }
    const usos = clips.map((_, c) => asignados.filter((x) => x === c).length), vez = new Array(n).fill(0);
    return huecos.map((h, k) => {
      const c = asignados[k], clip = clips[c];
      if (clip.tipo === "foto") return { clip: c, desde: 0 };
      const centro = clip.duracion * (vez[c] + 0.5) / usos[c]; vez[c]++;
      return { clip: c, desde: r3a(Math.max(0, Math.min(centro - h.dur / 2, clip.duracion - h.dur))) };
    });
  }
  const ZOOM_FOTO = { acercar: "zoom-lento", alejar: "alejar" };
  /** Lo que la plantilla pone en el proyecto, en el tiempo del video armado. `efectos` = {id: pasos}; `estilos` = ids. */
  function aplicarPlantilla(pl, tipos, idioma, efectos, estilos) {
    const huecos = pl.huecos, ini = iniciosHuecos(huecos), faltan = [], lista = [];
    const poner = (id, desde, hasta) => {
      if (!(id in efectos)) { if (!faltan.includes(id)) faltan.push(id); return; }
      const x = { efecto: id, pasos: clonarJSON(efectos[id]) };
      if (desde != null) Object.assign(x, { i: desde, f: hasta });
      lista.push(x);
    };
    huecos.forEach((h, k) => {
      for (const id of h.efectos || []) poner(id, ini[k], ini[k + 1]);
      const conZoom = (h.efectos || []).some((id) => (efectos[id] || []).some((p) => p.tipo === "zoom"));
      if (tipos[k] === "foto" && (h.zoom || "acercar") !== "no" && !conZoom) poner(ZOOM_FOTO[h.zoom || "acercar"], ini[k], ini[k + 1]);
      if (h.transicion && k + 1 < huecos.length) {
        const medio = r3a(Math.min(0.5, h.dur / 2, huecos[k + 1].dur / 2));
        poner(h.transicion, r3a(ini[k + 1] - medio), r3a(ini[k + 1] + medio));
      }
    });
    for (const id of pl.efectos || []) poner(id);
    const textos = (pl.textos || []).map((t) => ({ i: ini[t.en_hueco], f: ini[t.en_hueco + 1], texto: t.texto[idioma] || t.texto.es, y: t.posicion ?? 0.18 }));
    const s = pl.subtitulos, sub = s && estilos.includes(s.estilo) ? { estilo: s.estilo, activos: s.activos ?? true } : null;
    return { lienzo: pl.proporcion, divisiones: ini.slice(1, -1), textos, efectos: lista.slice(0, 40), subtitulos: sub, faltan };
  }
  /** Todos los efectos que usa una plantilla (sin repetir), como plantilla_formato.efectos_usados. */
  const efectosUsados = (pl) => [...new Set([...(pl.huecos || []).flatMap((h) => [...(h.efectos || []), ...(h.transicion ? [h.transicion] : [])]), ...(pl.efectos || [])])];
  const vinetaCSS = (fuerza) => `radial-gradient(ellipse at center, rgba(0,0,0,0) 40%, rgba(0,0,0,${(0.85 * fuerza).toFixed(3)}) 100%)`;

  // ───────────── Quitar un cambio de la IA (cambios_ia, lo anota bin/editar_ia.py) ─────────────
  const leerCampo = (p, campo) => campo.split(".").reduce((v, k) => (v && typeof v === "object" ? v[k] : undefined), p);
  function ponerCampo(p, campo, valor) {
    const ks = campo.split("."), ultimo = ks.pop(), o = ks.reduce((v, k) => (v && typeof v === "object" ? v[k] : undefined), p);
    if (o && typeof o === "object") o[ultimo] = valor;
  }
  const igualJSON = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  /** Quita justo lo que hizo el cambio `id` de la IA, aunque después se haya editado otra cosa: lo que agregó (zooms, textos, cortes,
   *  efectos con `origen: id`), los ajustes que cambió, los cortes que volvió a poner y las palabras que corrigió. Lo que la persona
   *  ya cambió a mano se conserva (deja de ser «de la IA») y se cuenta en `conservados`. Devuelve {quitados, conservados} o null. */
  function quitarCambioIA(p, id) {
    const c = (p.cambios_ia || []).find((x) => x.id === id);
    if (!c || c.estado === "quitado") return null;
    let quitados = 0, conservados = 0;
    for (const lista of ["zooms", "textos", "cortes", "efectos"]) {
      if (!Array.isArray(p[lista])) continue;
      const copias = (c.agregados?.[lista] || []).map((x) => JSON.stringify(x));
      p[lista] = p[lista].filter((o) => {
        if (o.origen !== id) return true;
        const k = copias.indexOf(JSON.stringify(o));
        if (k >= 0) { copias.splice(k, 1); quitados++; return false; }
        conservados++; delete o.origen; return true;
      });
    }
    for (const a of c.ajustes || []) {
      if (igualJSON(leerCampo(p, a.campo), a.despues)) { ponerCampo(p, a.campo, a.antes); quitados++; } else conservados++;
    }
    const rs = c.restaurados;
    if (rs) {
      const actuales = p.cortes.map((x) => JSON.stringify(x));
      if ((rs.despues || []).every((x) => actuales.includes(JSON.stringify(x)))) {
        const fuera = (rs.despues || []).map((x) => JSON.stringify(x));
        p.cortes = p.cortes.filter((x) => { const k = fuera.indexOf(JSON.stringify(x)); if (k >= 0) { fuera.splice(k, 1); return false; } return true; }).concat(clonarJSON(rs.antes || []));
        quitados++;
      } else conservados++;
    }
    for (const w of [...(c.palabras || [])].reverse()) {
      const n = w.despues.length, k = p.palabras.findIndex((_, j) => igualJSON(p.palabras.slice(j, j + n), w.despues));
      if (k >= 0) { p.palabras.splice(k, n, ...clonarJSON(w.antes)); quitados++; } else conservados++;
    }
    c.estado = "quitado";
    if (conservados) c.conservados = conservados;
    return { quitados, conservados };
  }
  const clonarJSON = (o) => JSON.parse(JSON.stringify(o));

  // ───────────── Utilidades ─────────────
  const proy = () => E.proyectos.find((x) => x.carpeta === E.sel);
  const P = () => proy()?.proyecto;
  const reloj = (s) => { s = Math.max(0, s || 0); const m = Math.floor(s / 60), x = Math.floor(s % 60); return `${m}:${String(x).padStart(2, "0")}`; };
  const segundos = (s) => (Math.round(s * 10) / 10).toLocaleString(E.idioma === "es" ? "es-CL" : "en-US");
  const estilo = () => E.estilos.find((s) => s.id === P()?.subtitulos.estilo) || E.estilos[0];
  const nombreIA = () => E.ias.find((i) => i.id === E.config.ia)?.nombre || tr("tu IA");
  let avisosPendientes = [];  // avisos que llegan mientras la persona elige el idioma: se muestran después, ya traducidos
  /** Aviso breve. `traducido`: el texto ya viene en el idioma de la interfaz (armado con Tp). */
  function toast(texto, traducido = false) {
    if (E.bv === 0) { avisosPendientes.push(texto); return; }
    const t = $("#toast"); t.textContent = traducido ? texto : tr(texto); t.classList.add("visible");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("visible"), 2200);
  }
  let guardarLuego = null;  // al mover un borde con el teclado se guarda una vez, al soltar las flechas
  /** Guarda el proyecto (la app lo valida y deja respaldo para deshacer). */
  function guardar(p, aviso, traducido = false) {
    clearTimeout(guardarLuego);
    host.enviar("guardarProyecto", { carpeta: E.sel, proyecto: p });
    if (aviso) toast(aviso, traducido);
    pintar();
  }

  // ───────────── Pintar ─────────────
  function pintar() {
    const raiz = $("#app");
    const scroll = $(".cuerpo-panel")?.scrollTop || 0, scrollLT = $("#lt-vista")?.scrollLeft || 0;
    // El <video> se reutiliza entre repintadas (si es el mismo archivo) para que no se recargue ni se corte la reproducción.
    const viejo = $("#video");
    const activo = document.activeElement?.id;
    // En el primer uso lo primero es el idioma: hasta elegirlo no se pinta nada más (ni la app detrás, ni el video).
    raiz.innerHTML = E.bv === 0 ? dialogos() : `<div class="app">${barra()}${lateral()}${principal()}</div>${sugerenciaHTML()}${dialogos()}`;
    traducirDOM(raiz);
    if (E.bv === 0 && !document.activeElement?.closest?.(".dialogo")) $(".opcion-idioma.principal")?.focus();
    const cp = $(".cuerpo-panel"); if (cp) cp.scrollTop = scroll;
    const vl = $("#lt-vista"); if (vl) vl.scrollLeft = scrollLT;
    const nuevo = $("#video");
    if (nuevo && viejo && viejo.getAttribute("src") === nuevo.getAttribute("src")) nuevo.replaceWith(viejo);
    if ($("#video")) ajustarPantalla();  // el tamaño sale del proyecto, no hace falta esperar a que cargue el video
    if (activo) document.getElementById(activo)?.focus();
    ajustarEtiquetas();
    pintarMuestras();
    if (activo === "editar-palabra" || activo === "editar-sub") { const inp = document.getElementById(activo); inp?.setSelectionRange?.(inp.value.length, inp.value.length); }
  }

  function barra() {
    const p = P();
    return `<header class="barra"><span class="marca">${LOGO}<span>Corta</span></span>
      <span class="titulo-proy" data-sin-traducir>${p ? `<b>${esc(p.titulo)}</b>` : ""}</span>
      ${p && p.palabras ? `<div class="segmentado" role="group" aria-label="Formato">${Object.keys(LIENZOS).map((l) =>
        `<button data-lienzo="${l}" aria-pressed="${p.lienzo === l}" data-sin-traducir>${l}</button>`).join("")}</div>
        <button class="icono" data-accion="deshacer" title="Deshacer" aria-label="Deshacer">↶</button>
        <button class="boton principal" data-accion="exportar">Exportar</button>` : ""}
      <button class="icono solo-angosto" data-accion="plantillas" title="Plantillas" aria-label="Plantillas">▦</button>
      <button class="icono" data-accion="ajustes" title="Ajustes" aria-label="Ajustes">⚙︎</button></header>`;
  }

  function lateral() {
    const items = E.proyectos.map((x) => {
      const p = x.proyecto, prog = E.progreso[x.carpeta];
      const meta = prog ? `<span data-sin-traducir>${esc(prog.texto || tr("Procesando…"))}</span>`
        : `<span data-sin-traducir>${esc(reloj(duracionFinal(p)))}</span> · <span data-sin-traducir>${esc(p.lienzo)}</span>`;
      return `<button class="item" data-sel="${esc(x.carpeta)}" aria-current="${x.carpeta === E.sel}">
        <span class="t" data-sin-traducir>${esc(p.titulo)}</span><span class="m">${meta}</span></button>`;
    }).join("");
    return `<aside class="lateral"><div class="caja"><button class="boton principal grande" data-accion="nuevo">＋ <span>Nuevo video</span></button>
      <button class="boton sutil grande" data-accion="plantillas">▦ <span>Usar una plantilla</span></button></div>
      <nav class="lista" aria-label="Videos">${E.proyectos.length ? `<h2>Tus videos</h2>${items}` : ""}</nav>
      <div class="pie-lateral"><span aria-hidden="true">🔒</span><span>Tus videos no salen de tu computador.</span></div></aside>`;
  }

  function principal() {
    const x = proy();
    if (!x) return vacio();
    const prog = E.progreso[x.carpeta];
    if (prog && !x.proyecto.palabras.length) {
      return `<section class="procesando"><div class="tarjeta"><h3>Preparando tu video</h3>
        <p style="margin:0 0 12px;font-weight:650" data-sin-traducir>${esc(prog.texto || tr("Transcribiendo en tu computador…"))}</p>
        <div class="barra-prog ${prog.pct ? "" : "indef"}"><i style="width:${prog.pct || 0}%"></i></div>
        <p class="nota">La transcripción se hace en tu computador. Un video de 10 minutos tarda un par de minutos.</p></div></section>`;
    }
    return `<section class="centro">${escenario()}</section><aside class="panel">${panel()}</aside>`;
  }

  function vacio() {
    return `<section class="vacio"><div class="dentro">${LOGO.replace('class="logo"', 'class="logo" style="width:60px;height:60px"')}
      <h1>Corta tu primer video</h1>
      <p>Trae un video y Corta lo transcribe en tu computador. Después sacas silencios y muletillas, eliges subtítulos y lo exportas vertical para Shorts, Reels o TikTok.</p>
      <div class="soltar ${E.soltar ? "encima" : ""}" data-soltar><span style="font-size:30px" aria-hidden="true">🎬</span>
        <button class="boton principal" data-accion="nuevo">Elegir video</button><small style="color:var(--suave)">MP4, MOV o WebM. También puedes arrastrarlo aquí.</small></div>
      <p class="o-plantilla"><span>¿Sin video todavía?</span> <button class="boton" data-accion="plantillas">▦ <span>Usar una plantilla</span></button></p>
      <div class="pasos"><div><b>1</b><span>Corta escucha tu video y escribe cada palabra con su tiempo.</span></div>
        <div><b>2</b><span>Editas el texto: lo que borras, se borra del video.</span></div>
        <div><b>3</b><span>Tu IA corta, pone zooms y busca los mejores momentos para Shorts.</span></div></div></div></section>`;
  }

  function escenario() {
    const p = P(), dur = p.fuente.duracion;
    const horizontal = p.fuente.ancho > p.fuente.alto && p.lienzo !== "16:9";
    return `<div class="escenario" id="escenario"><div class="pantalla" id="pantalla">
        ${p.relleno === "desenfoque" ? `<canvas id="fondo-borroso" aria-hidden="true"></canvas>` : ""}
        <div class="capa-zoom" id="capa-zoom"><video id="video" src="${esc(fuenteVideo())}" playsinline preload="auto"></video></div>
        <div class="capas-fx" id="capas-fx" aria-hidden="true"></div>
        <div class="subs" id="subs" aria-hidden="true"></div><div class="texto-sobre" id="texto-sobre" aria-hidden="true"></div></div></div>
      <div class="reproductor"><button class="play" data-accion="play" aria-label="Reproducir" id="boton-play">▶</button>
        <span class="tiempo" id="reloj" data-sin-traducir>${T("**{a}** de {b}", { a: "0:00", b: esc(reloj(duracionFinal(p))) })}</span>
        <span class="tiempo" data-sin-traducir style="opacity:.7">${duracionFinal(p) < dur ? T("(original {x})", { x: esc(reloj(dur)) }) : ""}</span>
        ${horizontal ? `<label class="encuadre"><span>Encuadre</span><input type="range" min="0" max="1" step="0.01" value="${p.encuadre.x}" data-encuadre aria-label="Mover el encuadre"></label>
          <select data-relleno aria-label="Relleno"><option value="recorte" ${p.relleno === "recorte" ? "selected" : ""}>Recortar</option><option value="desenfoque" ${p.relleno === "desenfoque" ? "selected" : ""}>Fondo borroso</option></select>` : ""}
      </div>
      ${lineaTiempo()}`;
  }
  function fuenteVideo() {
    const x = proy(), archivo = x.proyecto.fuente.archivo;
    if (HOST === "web") return archivo;
    return `corta://video/${encodeURIComponent(x.carpeta + "/" + archivo)}`;
  }

  const PESTANAS = [["texto", "Texto"], ["subtitulos", "Subtítulos"], ["efectos", "Efectos"], ["musica", "Música"], ["ia", "IA"], ["shorts", "Shorts"]];
  function panel() {
    // Un video armado con una plantilla tiene además la pestaña Clips (qué va en cada hueco), primero.
    const pestanas = P().plantilla ? [["clips", "Clips"], ...PESTANAS] : PESTANAS;
    if (!pestanas.some(([id]) => id === E.pestana)) E.pestana = "texto";
    const cuerpo = { clips: panelClips, texto: panelTexto, subtitulos: panelSubtitulos, efectos: panelEfectos, musica: panelMusica, ia: panelIA, shorts: panelShorts }[E.pestana]();
    return `<div class="pestanas" role="tablist">${pestanas.map(([id, n]) => `<button class="pestana" role="tab" data-pestana="${id}" aria-selected="${E.pestana === id}">${n}</button>`).join("")}</div>
      <div class="cuerpo-panel">${cuerpo}</div>`;
  }

  function panelTexto() {
    const p = P();
    if (!p.palabras.length) {
      return `<div class="tarjeta"><h3>Sin transcripción</h3><p class="nota">Este video todavía no tiene texto. Transcríbelo para editar por palabras y poner subtítulos.</p>
        <div style="margin-top:12px"><button class="boton principal" data-accion="transcribir">Transcribir</button></div></div>`;
    }
    const cortes = unir(p.cortes), sel = E.seleccion;
    let html = "";
    p.palabras.forEach((w, k) => {
      if (k > 0) {
        const hueco = w.i - p.palabras[k - 1].f;
        if (hueco >= 0.5) {
          const medio = (p.palabras[k - 1].f + w.i) / 2, cortada = cortes.some((c) => c.i <= medio && medio <= c.f);
          html += `<button class="pausa ${cortada ? "cortada" : ""}" data-pausa="${k}" title="${esc(tr(cortada ? "Volver a poner la pausa" : "Cortar la pausa"))}" data-sin-traducir>⋯ ${esc(segundos(hueco))} s</button>`;
        }
      }
      const ed = E.editar?.donde === "texto" ? E.editar : null;
      if (ed && k > ed.desde && k <= ed.hasta) return;
      if (ed && k === ed.desde) {
        html += `<input class="w-editar" id="editar-palabra" value="${esc(ed.valor)}" size="${Math.max(4, [...ed.valor].length + 2)}" maxlength="80"
          aria-label="${esc(tr("Corregir la palabra"))}" autocomplete="off" autocapitalize="off" spellcheck="false"> `;
        return;
      }
      const enSel = sel && k >= sel[0] && k <= sel[1];
      const marca = w.linea === "fin" ? `<span class="marca-linea" title="${esc(tr("La frase se separa aquí"))}">↵</span>`
        : w.linea === "sigue" ? `<span class="marca-linea" title="${esc(tr("La frase sigue con la siguiente"))}">⁀</span>` : "";
      html += `<span class="w ${palabraCortada(p, w, cortes) ? "cortada" : ""} ${enSel ? "sel" : ""}" data-w="${k}">${esc(w.t)}</span>${marca} `;
    });
    const nSel = sel ? sel[1] - sel[0] + 1 : 0;
    const selCortada = sel && p.palabras.slice(sel[0], sel[1] + 1).every((w) => palabraCortada(p, w, cortes));
    return `<div class="tarjeta limpiar"><div class="txt"><b>Silencios y muletillas</b>
        <small>${E.ultimoAhorro != null ? frase("Listo: el video quedó **{s} s** más corto.", { s: esc(segundos(E.ultimoAhorro)) }) : "Saca las pausas largas y los «eh», «mmm» de una vez."}</small></div>
        <button class="boton ${E.ultimoAhorro == null ? "principal" : ""}" data-accion="limpiar" ${E.limpiando ? "disabled" : ""}>${E.limpiando ? "Limpiando…" : E.ultimoAhorro == null ? "Limpiar" : "Otra vez"}</button></div>
      ${nSel && !E.editar ? `<div class="acciones-sel">${frase(nSel === 1 ? "1 palabra elegida" : "{n} palabras elegidas", { n: nSel })}
        <button class="boton sutil" data-accion="editar-sel" title="Corregir cómo se escribe (o tócala otra vez)">✎ <span>Corregir</span></button>
        ${nSel === 1 ? botonLinea(sel[0]) : ""}
        <button class="boton" data-accion="${selCortada ? "restaurar-sel" : "cortar-sel"}">${selCortada ? "Volver a poner" : "Cortar"}</button>
        <button class="boton sutil" data-accion="zoom-sel" title="Acercar la imagen mientras se dicen">🔍 <span>Zoom</span></button>
        <button class="boton sutil" data-pestana="efectos" title="Un filtro o un efecto solo mientras se dicen">✨ <span>Efecto</span></button></div>`
        : E.editar?.donde === "texto" ? `<p class="nota" style="margin:0 0 10px">Escribe cómo va. Enter guarda y Esc cancela; si la dejas vacía, sale del subtítulo (el video no se corta).</p>`
        : `<p class="nota" style="margin:0 0 10px">Toca una palabra para ir a ese momento y otra vez para corregirla. Elige varias (toca la primera y la última con Mayús) y presiona Borrar para sacarlas del video.</p>`}
      <div class="transcripcion" data-sin-traducir>${html}</div>`;
  }

  /** Separar o unir la frase después de la palabra k (`linea` en la palabra: «fin» o «sigue»). */
  function botonLinea(k) {
    const p = P(), w = p.palabras[k];
    if (!w || k === p.palabras.length - 1) return "";
    if (w.linea) return `<button class="boton sutil" data-accion="linea-sel" data-valor="">${w.linea === "fin" ? "Unir de nuevo" : "Separar de nuevo"}</button>`;
    const cortes = unir(p.cortes), grupos = lineas(p.palabras.filter((x) => !palabraCortada(p, x, cortes)), p.subtitulos.palabras_por_linea);
    const g = grupos.find((x) => x.includes(w)), ultima = g && g[g.length - 1] === w;
    return ultima ? `<button class="boton sutil" data-accion="linea-sel" data-valor="sigue" title="La frase sigue con la siguiente">⁀ <span>Unir</span></button>`
      : `<button class="boton sutil" data-accion="linea-sel" data-valor="fin" title="La frase se separa aquí">↵ <span>Separar</span></button>`;
  }
  /** Empieza a corregir las palabras desde..hasta, en el panel de texto o sobre la vista previa. */
  function empezarEdicion(desde, hasta, donde) {
    const p = P(), v = $("#video");
    if (!p?.palabras[desde]) return;
    if (v && !v.paused) v.pause();
    E.editar = { desde, hasta, valor: p.palabras.slice(desde, hasta + 1).map((w) => w.t).join(" "), donde };
    E.sugerencia = null;
    if (donde === "texto") E.pestana = "texto";
    pintar();
    const inp = $(donde === "texto" ? "#editar-palabra" : "#editar-sub");
    if (inp) { inp.focus(); inp.select(); }
  }
  /** Guarda la corrección (mismos tiempos) y ofrece cambiarla en todo el video y recordarla para los próximos. */
  function terminarEdicion(guardarla) {
    const ed = E.editar, p = P();
    if (!ed || !p) return;
    E.editar = null;
    const texto = guardarla ? String(ed.valor).replace(/\s+/g, " ").trim().slice(0, 80) : null;
    const antes = p.palabras.slice(ed.desde, ed.hasta + 1).map((w) => w.t).join(" ");
    if (texto == null || texto === antes) { pintar(); return; }
    p.palabras = editarPalabras(p.palabras, ed.desde, ed.hasta, texto);
    E.seleccion = null;
    if (!texto) return guardar(p, "Quitada del subtítulo");
    const de = partes(antes)[1], a = partes(texto)[1];
    if (de && a && normalizar(de) && de !== a) E.sugerencia = { de, a, n: reemplazarTodo(p.palabras, [{ de, a }])[1], todo: false, recordado: false };
    guardar(p);
  }
  function sugerenciaHTML() {
    const s = E.sugerencia;
    if (!s || !P()) return "";
    const v = { de: esc(s.de), a: esc(s.a), n: s.n };
    const texto = s.n && !s.todo ? (s.n === 1 ? "¿Cambiar «{de}» por «{a}» en todo el video (1 vez)?" : "¿Cambiar «{de}» por «{a}» en todo el video ({n} veces)?")
      : s.todo ? (s.n === 1 ? "Listo: cambié «{de}» por «{a}» 1 vez más." : "Listo: cambié «{de}» por «{a}» {n} veces más.") : "Corregiste «{de}» por «{a}».";
    return `<div class="sugerencia" role="status"><span class="txt" data-sin-traducir>${T(texto, v)}</span><span class="acciones">
      ${s.n && !s.todo ? `<button class="boton principal chico" data-accion="sug-todo">Cambiar en todo el video</button>` : ""}
      ${s.recordado ? `<span class="ok">✓ Lo recordaré</span>` : `<button class="boton chico" data-accion="sug-recordar" title="Corta la corregirá sola al transcribir tus próximos videos">Recordar para próximos videos</button>`}
      <button class="icono" data-accion="sug-cerrar" title="Cerrar" aria-label="Cerrar">×</button></span></div>`;
  }

  /** CSS de un estilo de subtítulos. El borde se dibuja con sombras en 16 direcciones (como el contorno de ffmpeg/libass),
   *  porque -webkit-text-stroke se come la letra por dentro. `escala` = px de pantalla por px de un video de 1080 de ancho. */
  function cssEstilo(s, escala = 1) {
    const borde = s.borde * escala, sombra = s.sombra * escala, capas = [];
    if (borde > 0) for (let k = 0; k < 16; k++) { const a = k / 16 * Math.PI * 2; capas.push(`${(Math.cos(a) * borde).toFixed(2)}px ${(Math.sin(a) * borde).toFixed(2)}px 0 ${s.color_borde}`); }
    if (sombra > 0) capas.push(`0 ${(sombra * .6).toFixed(1)}px ${(sombra * 1.4).toFixed(1)}px rgba(0,0,0,.6)`);
    return `font-family:'${s.fuente}',system-ui,sans-serif;font-weight:${/Bold|Black/.test(s.fuente) ? "normal" : s.peso};color:${s.color};` +
      `${s.mayusculas ? "text-transform:uppercase;" : ""}${capas.length ? `text-shadow:${capas.join(",")};` : ""}`;
  }
  function panelSubtitulos() {
    const p = P(), s = p.subtitulos;
    const tarjetas = E.estilos.map((e) => `<button class="estilo" data-estilo="${esc(e.id)}" aria-pressed="${s.estilo === e.id}">
      <span class="muestra"><span style="${cssEstilo(e, (e.animacion === "palabra" ? 26 : 19) / (e.tamano / 100 * 1080))}font-size:${e.animacion === "palabra" ? 26 : 19}px;line-height:1.1;text-align:center;${e.fondo ? `background:${e.color_fondo};padding:3px 8px;border-radius:5px;` : ""}" data-sin-traducir>${
        e.animacion === "palabra" ? `<span style="color:${e.color_activo}">${esc(tr("Así"))}</span>` : `${esc(tr("Así se"))} <span style="color:${e.color_activo};${e.fondo ? "" : ""}">${esc(tr("ven"))}</span>`}</span></span>
      <span class="nombre" data-sin-traducir>${esc(e.nombre)}</span></button>`).join("");
    return `<div class="tarjeta"><div class="fila"><div class="txt"><b>Subtítulos</b><small>Hechos con la transcripción, palabra por palabra.</small></div>
        <input type="checkbox" class="interruptor" data-sub-activos ${s.activos ? "checked" : ""} aria-label="Mostrar subtítulos"></div>
      <div class="fila"><div class="txt"><b>Palabras por línea</b></div><select data-sub-palabras>${[1, 2, 3, 4, 5].map((n) => `<option ${s.palabras_por_linea === n ? "selected" : ""}>${n}</option>`).join("")}</select></div>
      <div class="fila"><div class="txt"><b>Altura</b><small>Más abajo o más al centro.</small></div><input type="range" min="0.3" max="0.9" step="0.01" value="${s.posicion}" data-sub-posicion aria-label="Altura de los subtítulos"></div></div>
      <div class="galeria">${tarjetas}</div>
      <p class="nota">¿Quieres otro estilo? Los estilos son archivos simples que cualquiera puede crear y compartir con la comunidad.</p>`;
  }

  // ───────────── Efectos: incluidos, descargados y de la comunidad (solo datos; bin/efectos.py los exporta) ─────────────
  const CATEGORIAS_FX = [["todos", "Todos"], ["filtro", "Filtros"], ["color", "Color"], ["movimiento", "Movimiento"], ["transicion", "Transiciones"]];
  const nombreFx = (ef) => (ef?.nombre?.[E.idioma] || ef?.nombre?.es || "");
  const descripcionFx = (ef) => (ef?.descripcion?.[E.idioma] || ef?.descripcion?.es || "");
  const efectoPorId = (id) => E.efectos.find((x) => x.id === id);
  function coincideFx(ef, categoria, busqueda) {
    if (categoria !== "todos" && ef.categoria !== categoria) return false;
    const q = String(busqueda || "").split(/\s+/).map(normalizar).filter(Boolean);
    if (!q.length) return true;
    const texto = normalizar([...Object.values(ef.nombre || {}), ...Object.values(ef.descripcion || {}), ...(ef.etiquetas || []), ef.autor || ""].join(" "));
    return q.every((x) => texto.includes(x));
  }
  /** A qué se aplica un efecto: las palabras elegidas, el tramo elegido en la línea de tiempo o (null) todo el video. */
  function destinoEfecto() {
    const p = P();
    if (E.seleccion && p.palabras[E.seleccion[0]]) {
      const [a, b] = E.seleccion, texto = p.palabras.slice(a, b + 1).map((w) => w.t).join(" ");
      return { i: r3(p.palabras[a].i), f: r3(p.palabras[b].f), texto: texto.length > 40 ? texto.slice(0, 39) + "…" : texto };
    }
    const s = E.lt.sel;
    if (s?.lista === "tramos") { const t = tramosEdicion(p)[s.k]; if (t) return { i: r3(t.i), f: r3(t.f) }; }
    return null;
  }
  const mismoAlcance = (ap, d) => (d ? ap.i === d.i && ap.f === d.f : !("i" in ap));
  /** Muestra de un efecto: un cuadro del video con los mismos filtros de CSS que la vista previa (o un degradado sin video). */
  function muestraFx(ef, alto = 0) {
    const filtro = [], capas = [];
    let clase = "";
    for (const paso of ef.pasos || []) {
      if (paso.tipo === "color") filtro.push(cssColor(paso));
      else if (paso.tipo === "desenfoque") filtro.push(`blur(${(numFx(paso, "radio", 4) / 6).toFixed(2)}px)`);
      else if (paso.tipo === "vineta") capas.push(`<i style="background:${vinetaCSS(numFx(paso, "fuerza", 0.5))}"></i>`);
      else if (paso.tipo === "tinte") capas.push(`<i style="background:rgb(${rgbFx(paso)});opacity:${numFx(paso, "fuerza", 0.1)}"></i>`);
      else if (paso.tipo === "zoom") clase = paso.curva === "golpe" ? "anim-golpe" : numFx(paso, "hasta", 1) >= numFx(paso, "desde", 1) ? "anim-acercar" : "anim-alejar";
      else capas.push(`<i class="anim-capa" style="background:rgb(${rgbFx(paso)})"></i>`);
    }
    return `<span class="muestra-fx ${clase}"${alto ? ` style="height:${alto}px"` : ""}><canvas data-muestra width="96" height="128" style="filter:${filtro.join(" ") || "none"}"></canvas>${capas.join("")}</span>`;
  }
  /** Copia el cuadro actual del video a cada muestra (con el recorte del lienzo, como «cover»). */
  function pintarMuestras() {
    const v = $("#video");
    if (!v || v.readyState < 2 || !v.videoWidth) return;
    for (const c of document.querySelectorAll("canvas[data-muestra]")) {
      const ctx = c.getContext("2d"), s = Math.max(c.width / v.videoWidth, c.height / v.videoHeight);
      const w = c.width / s, h = c.height / s;
      try { ctx.drawImage(v, (v.videoWidth - w) / 2, (v.videoHeight - h) / 2, w, h, 0, 0, c.width, c.height); c.classList.add("con-video"); } catch {}
    }
  }
  function panelEfectos() {
    const p = P(), d = destinoEfecto(), aplicados = p.efectos || [];
    const destino = d ? `<div class="tarjeta fx-destino"><div class="txt"><b>${frase("Al tramo de {a} a {b}", { a: esc(relojFino(d.i)), b: esc(relojFino(d.f)) })}</b>
        ${d.texto ? `<small data-sin-traducir>«${esc(d.texto)}»</small>` : ""}</div><button class="boton sutil chico" data-accion="fx-todo">Todo el video</button></div>`
      : `<p class="nota" style="margin:0 0 10px">Se aplica a todo el video. Para un solo momento, elige palabras en Texto o un tramo en la línea de tiempo.</p>`;
    const filas = aplicados.map((ap, k) => {
      const ef = efectoPorId(ap.efecto), nombre = ef ? nombreFx(ef) : ap.efecto;
      const donde = "i" in ap ? T("{a} a {b}", { a: esc(relojFino(ap.i)), b: esc(relojFino(ap.f)) }) : esc(tr("Todo el video"));
      return `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(nombre)}</b><small data-sin-traducir>${donde}</small></div>
        <button class="boton sutil chico" data-quitar-fx="${k}" aria-label="${esc(Tp("Quitar «{x}»", { x: nombre }))}" data-sin-traducir>${esc(tr("Quitar"))}</button></div>`;
    }).join("");
    const lista = E.efectos.filter((ef) => coincideFx(ef, E.fx.categoria, E.fx.busqueda));
    const tarjetas = lista.map((ef) => `<button class="fx" data-fx="${esc(ef.id)}" aria-pressed="${aplicados.some((ap) => ap.efecto === ef.id && mismoAlcance(ap, d))}" title="${esc(descripcionFx(ef))}" data-sin-traducir>
      ${muestraFx(ef)}<span class="nombre">${esc(nombreFx(ef))}</span></button>`).join("");
    return `${destino}${filas ? `<div class="tarjeta"><h3>En este video</h3>${filas}</div>` : ""}
      <div class="chips-fx" role="group" aria-label="Categorías">${CATEGORIAS_FX.map(([id, n]) => `<button class="chip" data-fx-cat="${id}" aria-pressed="${E.fx.categoria === id}">${n}</button>`).join("")}</div>
      <input class="texto buscar-fx" id="buscar-fx" type="search" placeholder="Buscar efectos" value="${esc(E.fx.busqueda)}" autocomplete="off">
      ${tarjetas ? `<div class="galeria-fx">${tarjetas}</div>` : `<p class="nota">No hay efectos con eso. Prueba en la comunidad.</p>`}
      <div class="tarjeta comunidad"><div class="txt"><b>Más efectos de la comunidad</b><small>Gratis y hechos por personas como tú. Son solo datos: Corta los revisa antes de usarlos.</small></div>
        <button class="boton" data-accion="explorar-fx">Explorar</button></div>`;
  }
  function aplicarEfecto(id) {
    const p = P(), ef = efectoPorId(id);
    if (!p || !ef) return;
    const d = destinoEfecto();
    p.efectos ||= [];
    const k = p.efectos.findIndex((ap) => ap.efecto === id && mismoAlcance(ap, d));
    if (k >= 0) { p.efectos.splice(k, 1); return guardar(p, Tp("Quité «{x}»", { x: nombreFx(ef) }), true); }
    p.efectos.push({ efecto: id, pasos: clonarJSON(ef.pasos), ...(d ? { i: d.i, f: d.f } : {}) });
    guardar(p, Tp(d ? "«{x}» en el tramo elegido" : "«{x}» en todo el video", { x: nombreFx(ef) }), true);
  }
  function dialogoCatalogo() {
    const c = E.catalogo;
    let cuerpo;
    if (c.estado === "cargando") cuerpo = `<p class="nota">Buscando efectos…</p><div class="barra-prog indef"><i></i></div>`;
    else if (c.estado === "error") cuerpo = `<p class="error-txt" data-sin-traducir>${esc(c.error || tr("No pude conectarme. Revisa tu conexión."))}</p><div class="pie-dialogo"><button class="boton" data-accion="explorar-fx">Reintentar</button></div>`;
    else {
      const lista = c.efectos.filter((ef) => coincideFx(ef, c.categoria, c.busqueda));
      cuerpo = `<div class="chips-fx" role="group" aria-label="Categorías">${CATEGORIAS_FX.map(([id, n]) => `<button class="chip" data-cat-cat="${id}" aria-pressed="${c.categoria === id}">${n}</button>`).join("")}</div>
        <input class="texto buscar-fx" id="buscar-cat" type="search" placeholder="Buscar efectos" value="${esc(c.busqueda)}" autocomplete="off">
        <div class="lista-cat">${lista.map((ef) => {
          const propio = efectoPorId(ef.id), bajando = c.bajando[ef.id];
          const accion = propio ? `<span class="ok">${propio.origen === "incluido" ? esc(tr("Incluido")) : esc(tr("✓ Descargado"))}</span>`
            : `<button class="boton chico" data-bajar-fx="${esc(ef.id)}" ${bajando ? "disabled" : ""}>${esc(tr(bajando ? "Descargando…" : "Descargar"))}</button>`;
          return `<div class="item-cat" data-sin-traducir>${muestraFx(ef, 72)}<div class="txt"><b>${esc(nombreFx(ef))}</b><small>${esc(descripcionFx(ef))}</small>
            ${ef.autor ? `<small class="autor">${esc(Tp("por {x}", { x: ef.autor }))}</small>` : ""}</div>${accion}</div>`;
        }).join("") || `<p class="nota" data-sin-traducir>${esc(tr("No hay efectos con eso."))}</p>`}</div>`;
    }
    return `<h2 id="t-cat">Efectos de la comunidad</h2><p>Gratis y abiertos. Cualquiera puede crear uno sin programar y compartirlo.</p>
      ${cuerpo}
      <div class="pie-dialogo"><button class="boton izq" data-enlace="${ENLACES.catalogo}">Crear el tuyo</button><button class="boton principal" data-accion="cerrar">Listo</button></div>`;
  }

  // ───────────── Plantillas: elegir una, poner tus clips y retocar (solo datos; bin/plantillas.py arma el video) ─────────────
  const CATEGORIAS_PL = [["todas", "Todas"], ["negocios", "Negocios"], ["presentacion", "Presentación"], ["recuerdos", "Recuerdos"], ["tutorial", "Tutoriales"], ["celebracion", "Celebraciones"]];
  const enIdioma = (x) => (x?.[E.idioma] || x?.es || "");
  const plantillaPorId = (id) => E.plantillas.find((x) => x.id === id);
  const duracionPl = (pl) => iniciosHuecos(pl.huecos).at(-1);
  const segundosPl = (s) => (Number.isInteger(s) ? String(s) : segundos(s));
  function coincidePl(pl, categoria, busqueda) {
    if (categoria !== "todas" && pl.categoria !== categoria) return false;
    const q = String(busqueda || "").split(/\s+/).map(normalizar).filter(Boolean);
    if (!q.length) return true;
    const texto = normalizar([...Object.values(pl.nombre || {}), ...Object.values(pl.descripcion || {}), ...(pl.etiquetas || []), pl.autor || "",
      ...(pl.huecos || []).flatMap((h) => Object.values(h.pista || {}))].join(" "));
    return q.every((x) => texto.includes(x));
  }
  /** Los efectos que usa una plantilla y la persona no tiene (la app ofrece descargarlos del catálogo). */
  const faltanPl = (pl) => efectosUsados(pl).filter((id) => !efectoPorId(id));
  /** Color de un hueco en la vista previa: tonos tranquilos que cambian en cada corte (no es tu video, es la forma de la plantilla). */
  function colorHueco(id, k) {
    let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360;
    const t = (h + k * 53) % 360;
    return `linear-gradient(160deg, hsl(${t} 42% 60%), hsl(${(t + 28) % 360} 38% 30%))`;
  }
  const ICONO_HUECO = { video: "▶", foto: "◼", cualquiera: "＋" };
  /** Vista previa de una plantilla, sin video: bloques de color con sus cortes, sus textos (en su estilo) y una barra con las uniones.
   *  La anima `animarPlantillas` (un hueco a la vez, al ritmo de sus duraciones). */
  function vistaPl(pl, grande = false) {
    const [W, H] = LIENZOS[pl.proporcion] || LIENZOS["9:16"], ini = iniciosHuecos(pl.huecos), total = ini.at(-1);
    const alto = grande ? 260 : 150, ancho = W < H ? alto * W / H : grande ? 300 : 160;
    const st = E.estilos.find((x) => x.id === pl.subtitulos?.estilo) || E.estilos.find((x) => x.id === "pop") || E.estilos[0];
    const escala = ancho / 1080, filtroTodo = (pl.efectos || []).map((id) => (efectoPorId(id)?.pasos || []).filter((p) => p.tipo === "color").map(cssColor).join(" ")).join(" ").trim();
    const transicion = (id) => { const p = efectoPorId(id)?.pasos?.find((x) => x.tipo === "transicion"); return p ? (p.color === "negro" ? "negro" : "blanco") : id ? "blanco" : ""; };
    const bloques = pl.huecos.map((h, k) => {
      const filtro = (h.efectos || []).map((id) => (efectoPorId(id)?.pasos || []).filter((p) => p.tipo === "color").map(cssColor).join(" ")).join(" ").trim();
      const tr_ = k ? transicion(pl.huecos[k - 1].transicion) : "";
      return `<i class="pv-h ${h.tipo}${k ? "" : " on"}" data-k="${k}"${tr_ ? ` data-tr="${tr_}"` : ""} style="background:${colorHueco(pl.id, k)};--d:${h.dur}s${filtro ? `;filter:${filtro}` : ""}">
        <em aria-hidden="true">${ICONO_HUECO[h.tipo] || ""}</em>${grande && h.pista ? `<small>${esc(enIdioma(h.pista))}</small>` : ""}</i>`;
    }).join("");
    const textos = st ? (pl.textos || []).map((t) => `<b class="pv-t${t.en_hueco ? "" : " on"}" data-k="${t.en_hueco}" style="top:${(t.posicion ?? 0.18) * 100}%;${cssEstilo(st, escala)}font-size:${Math.max(7, st.tamano / 100 * ancho * 0.9).toFixed(1)}px">${esc(enIdioma(t.texto))}</b>`).join("") : "";
    const cortes = ini.slice(1, -1).map((x) => `<i style="left:${(x / total * 100).toFixed(2)}%"></i>`).join("");
    return `<span class="pv-marco${grande ? " grande" : ""}" aria-hidden="true"><span class="pv-pl" data-pv data-total="${total}" data-inicios="${ini.join(",")}" style="width:${ancho.toFixed(0)}px;aspect-ratio:${W}/${H}${filtroTodo ? `;filter:${filtroTodo}` : ""}">
      ${bloques}${textos}<span class="pv-barra">${cortes}<em class="pv-cabezal"></em></span></span></span>`;
  }
  const quieto = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  /** Mueve las vistas previas de plantillas que se ven: un hueco a la vez, cada uno lo que dura. */
  function animarPlantillas(ahora) {
    if (!E.pl || quieto?.matches) return;
    for (const el of document.querySelectorAll("[data-pv]")) {
      const total = Number(el.dataset.total), ini = el.dataset.inicios.split(",").map(Number), t = (ahora / 1000) % total;
      const k = Math.max(0, ini.findIndex((x, j) => t >= x && t < ini[j + 1]));
      if (el.dataset.k !== String(k)) { el.dataset.k = k; for (const x of el.querySelectorAll(".pv-h, .pv-t")) x.classList.toggle("on", x.dataset.k === String(k)); }
      const c = el.querySelector(".pv-cabezal"); if (c) c.style.left = (t / total * 100).toFixed(2) + "%";
    }
  }
  const metaPl = (pl) => T("{d} s · {n} clips", { d: esc(segundosPl(duracionPl(pl))), n: pl.huecos.length });
  function tarjetaPl(pl) {
    return `<button class="pl" data-ver-pl="${esc(pl.id)}" data-sin-traducir>${vistaPl(pl)}<span class="nombre">${esc(nombreFx(pl))}</span><small>${metaPl(pl)}</small></button>`;
  }
  function dialogoPlantillas() {
    const x = E.pl;
    if (x.armando) {
      return `<h2 id="t-pl">Armando tu video…</h2><p>Cada clip va a su hueco con sus efectos y textos. Esto pasa en tu computador.</p><div class="barra-prog indef"><i></i></div>`;
    }
    const comunidad = x.fuente === "comunidad", cat = x.catalogo;
    const lista = comunidad ? cat?.plantillas || [] : E.plantillas;
    const verla = x.ver && (lista.find((p) => p.id === x.ver) || plantillaPorId(x.ver));
    if (verla) return detallePlantilla(verla);
    const cabeza = `<h2 id="t-pl">Plantillas</h2><p>Elige una, pon tus clips o fotos y se arma sola. Después la retocas como cualquier video.</p>
      <div class="segmentado ancho" role="group" aria-label="Origen"><button data-pl-fuente="corta" aria-pressed="${!comunidad}">En Corta</button><button data-pl-fuente="comunidad" aria-pressed="${comunidad}">De la comunidad</button></div>`;
    let cuerpo;
    if (comunidad && (!cat || cat.estado === "cargando")) cuerpo = `<p class="nota">Buscando plantillas…</p><div class="barra-prog indef"><i></i></div>`;
    else if (comunidad && cat.estado === "error") cuerpo = `<p class="error-txt" data-sin-traducir>${esc(cat.error || tr("No pude conectarme. Revisa tu conexión."))}</p><div class="pie-dialogo"><button class="boton" data-pl-fuente="comunidad">Reintentar</button></div>`;
    else {
      const visibles = lista.filter((p) => coincidePl(p, x.categoria, x.busqueda));
      cuerpo = `<div class="chips-fx" role="group" aria-label="Categorías">${CATEGORIAS_PL.map(([id, n]) => `<button class="chip" data-pl-cat="${id}" aria-pressed="${x.categoria === id}">${n}</button>`).join("")}</div>
        <input class="texto buscar-fx" id="buscar-pl" type="search" placeholder="Buscar plantillas" value="${esc(x.busqueda)}" autocomplete="off">
        ${visibles.length ? `<div class="galeria-pl">${visibles.map(tarjetaPl).join("")}</div>` : `<p class="nota">No hay plantillas con eso.</p>`}`;
    }
    return `${cabeza}${cuerpo}
      <div class="pie-dialogo"><button class="boton izq" data-enlace="${ENLACES.plantillas}">Crear la tuya</button><button class="boton principal" data-accion="cerrar">Listo</button></div>`;
  }
  function detallePlantilla(pl) {
    const x = E.pl, propia = plantillaPorId(pl.id), faltan = faltanPl(pl), catEf = x.catalogo?.efectos || E.catalogo?.efectos || [];
    const huecos = pl.huecos.map((h, k) => `<li><span class="num">${k + 1}</span><span class="txt">${h.pista ? `<b data-sin-traducir>${esc(enIdioma(h.pista))}</b>` : `<b>Lo que quieras</b>`}</span>
      <small data-sin-traducir>${esc(tr({ video: "Video", foto: "Foto", cualquiera: "Video o foto" }[h.tipo]))} · ${T("{s} s", { s: esc(segundosPl(h.dur)) })}</small></li>`).join("");
    const faltaHTML = faltan.length ? `<div class="tarjeta falta-pl"><b>Usa efectos de la comunidad que no tienes</b>${faltan.map((id) => {
        const ef = catEf.find((e) => e.id === id), bajando = x.bajando[id];
        return `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(ef ? nombreFx(ef) : id)}</b></div>
          <button class="boton chico" data-pl-bajar-fx="${esc(id)}" ${bajando ? "disabled" : ""} data-sin-traducir>${esc(tr(bajando ? "Descargando…" : "Descargar"))}</button></div>`;
      }).join("")}<p class="nota">Sin ellos la plantilla igual funciona, pero sin esos efectos.</p></div>` : "";
    const accion = !propia ? `<button class="boton principal" data-bajar-pl="${esc(pl.id)}" ${x.bajando[pl.id] ? "disabled" : ""}>${x.bajando[pl.id] ? "Descargando…" : "Descargar plantilla"}</button>`
      : `<button class="boton principal" data-elegir-clips="${esc(pl.id)}" data-sin-traducir>${esc(Tp(pl.huecos.length === 1 ? "Elegir 1 clip o foto" : "Elegir {n} clips o fotos", { n: pl.huecos.length }))}</button>`;
    const bpm = pl.musica?.bpm ? ` · ${T("pensada para música de ~{b} BPM", { b: Math.round(pl.musica.bpm) })}` : "";
    return `<button class="boton sutil chico volver-pl" data-ver-pl="">‹ <span>Plantillas</span></button>
      <div class="detalle-pl">${vistaPl(pl, true)}<div class="txt"><h2 id="t-pl" data-sin-traducir>${esc(nombreFx(pl))}</h2>
        ${pl.descripcion ? `<p data-sin-traducir>${esc(enIdioma(pl.descripcion))}</p>` : ""}
        <small class="meta-pl" data-sin-traducir>${metaPl(pl)} · ${esc(pl.proporcion)}${bpm}${pl.autor ? ` · ${esc(Tp("por {x}", { x: pl.autor }))}` : ""}</small></div></div>
      <ol class="huecos-pl">${huecos}</ol>${faltaHTML}
      <p class="nota">Si eliges menos, se repiten; si eliges más, sobran. Después puedes cambiar cada uno y elegir qué parte de cada video se usa.</p>
      <div class="pie-dialogo"><button class="boton" data-ver-pl="">Atrás</button>${accion}</div>`;
  }
  /** Un clip o una foto de la plantilla, para verlo en el panel: por corta:// en la app; en la vista previa, la ruta de la demo. */
  const fuenteClip = (carpeta, archivo) => (HOST === "web" ? archivo : `corta://video/${encodeURIComponent(carpeta + "/" + archivo)}`);
  function panelClips() {
    const p = P(), pl = plantillaPorId(p.plantilla.id), ini = iniciosHuecos(p.plantilla.huecos);
    const filas = p.plantilla.huecos.map((h, k) => {
      const ocupado = E.armando?.carpeta === E.sel, este = ocupado && E.armando.k === k, max = h.tipo === "video" ? Math.max(0, r3((h.duracion || 0) - h.dur)) : 0;
      const pista = enIdioma(pl?.huecos?.[k]?.pista);
      const mini = h.tipo === "foto" ? `<img class="mini-clip" src="${esc(fuenteClip(E.sel, h.archivo))}" alt="">`
        : `<video class="mini-clip" src="${esc(fuenteClip(E.sel, h.archivo))}" muted playsinline preload="metadata" data-mini="${k}" data-desde="${h.desde}"></video>`;
      const control = este ? `<small class="ok">${esc(tr("Armando…"))}</small>`
        : max > 0.05 ? `<label class="desde"><input type="range" min="0" max="${max}" step="0.1" value="${h.desde}" data-hueco-desde="${k}" ${ocupado ? "disabled" : ""} aria-label="${esc(Tp("Desde qué segundo del clip {n}", { n: k + 1 }))}">
            <output id="desde-${k}">${T("desde {t}", { t: esc(relojFino(h.desde)) })}</output></label>` : "";
      return `<div class="hueco-fila" data-sin-traducir><span class="num">${k + 1}</span>${mini}<div class="txt"><b>${esc(pista || Tp("Clip {n}", { n: k + 1 }))}</b>
          <small>${esc(tr(h.tipo === "foto" ? "Foto" : "Video"))} · ${T("{a} a {b}", { a: esc(relojFino(ini[k])), b: esc(relojFino(ini[k + 1])) })}</small>${control}</div>
        <button class="boton chico" data-cambiar-clip="${k}" ${ocupado ? "disabled" : ""}>${esc(tr("Cambiar"))}</button></div>`;
    }).join("");
    return `<div class="tarjeta"><h3>Tus clips</h3>
      <p class="nota" style="margin:0 0 10px">${pl ? frase("Plantilla «{x}». Cambia un clip o mueve la barra para elegir qué parte del video va en su hueco.", { x: esc(nombreFx(pl)) })
        : esc(tr("Cambia un clip o mueve la barra para elegir qué parte del video va en su hueco."))}</p>${filas}</div>
      ${pl?.musica?.bpm ? `<p class="nota">${frase("Los cortes van al ritmo de una música de ~{b} BPM: elige una parecida en Música.", { b: Math.round(pl.musica.bpm) })}</p>` : ""}`;
  }

  /** Música de fondo: el proyecto guarda {archivo, volumen} y render.py la baja sola cuando hay voz (sidechain). */
  function panelMusica() {
    const p = P(), m = p.musica;
    const derechos = `<div class="tarjeta derechos"><b>Usa solo música tuya o libre</b>
      <p class="nota">Las canciones conocidas tienen derechos de autor: YouTube, Instagram y TikTok pueden silenciar tu video, bloquearlo o quitarle las ganancias. Usa música que hiciste tú, que tiene una licencia que permite usarla en videos o que es libre de derechos. Si la licencia pide nombrar a quien la hizo, ponlo en la descripción.</p></div>`;
    if (!m) {
      return `<div class="tarjeta"><h3>Música de fondo</h3>
        <p class="nota" style="margin:0 0 12px">Elige una canción de tu computador. Suena bajo tu voz y baja sola cuando hablas, para que siempre se entienda lo que dices.</p>
        <button class="boton principal" data-accion="elegir-musica">♪ <span>Elegir música</span></button>
        <p class="nota">MP3, M4A, WAV, OGG o FLAC. Si es más corta que el video, se repite.</p></div>${derechos}`;
    }
    const nombre = m.archivo.split(/[\\/]/).pop();
    const vol = Math.round(m.volumen * 100);
    return `<div class="tarjeta"><h3>Música de fondo</h3>
      <div class="fila archivo-m"><span class="disco" aria-hidden="true">♪</span><div class="txt"><b data-sin-traducir title="${esc(nombre)}">${esc(nombre)}</b><small>Se repite si es más corta que el video.</small></div>
        <span class="acciones-m"><button class="boton chico" data-accion="elegir-musica">Cambiar</button><button class="boton sutil chico" data-accion="quitar-musica">Quitar</button></span></div>
      <div class="fila"><div class="txt"><b>Volumen</b><small>Cuando no hablas. Al hablar, baja sola.</small></div>
        <input type="range" min="0" max="1" step="0.01" value="${m.volumen}" data-musica-volumen aria-label="Volumen de la música"><output id="musica-vol" class="num" data-sin-traducir>${vol} %</output></div>
      <div class="medidor"><div class="barra-prog"><i id="musica-nivel" style="width:100%"></i></div><small id="musica-ahora">Volumen normal</small></div>
      <button class="boton grande" data-accion="escuchar-musica">▶ <span>Escuchar cómo queda</span></button>
      ${!p.palabras.length ? `<p class="nota">Sin transcripción, la vista previa no baja la música mientras hablas. Al exportar sí baja.</p>` : ""}
      ${!fuenteMusica(p) ? `<p class="nota">Esta música está fuera de la carpeta del proyecto: no suena en la vista previa, pero sí al exportar. Elígela de nuevo para traerla a la carpeta.</p>` : ""}</div>${derechos}`;
  }

  const EJEMPLOS_IA = ["Saca la parte donde me equivoco", "Pon zoom cuando digo algo importante", "Pon un título grande al inicio", "Ponle un filtro cálido", "Subtítulos de una palabra a la vez", "Hazlo cuadrado para Instagram"];
  /** Qué dice el botón de un cambio de la IA: lo que agregó, contado («Quitar estos 6 zooms»), o «Quitar este cambio». */
  function etiquetaQuitar(c) {
    const a = c.agregados || {}, listas = Object.keys(a).filter((k) => a[k]?.length);
    const otros = (c.ajustes?.length || 0) + (c.restaurados ? 1 : 0) + (c.palabras?.length || 0);
    if (listas.length === 1 && !otros) {
      const n = a[listas[0]].length, nombres = { zooms: ["Quitar este zoom", "Quitar estos {n} zooms"], textos: ["Quitar este texto", "Quitar estos {n} textos"],
        cortes: ["Quitar este corte", "Quitar estos {n} cortes"], efectos: ["Quitar este efecto", "Quitar estos {n} efectos"] }[listas[0]];
      if (nombres) return Tp(n === 1 ? nombres[0] : nombres[1], { n });
    }
    return Tp("Quitar este cambio");
  }
  function panelIA() {
    const ia = E.ia, nombre = esc(nombreIA()), p = P();
    // Lo que la IA cambió en este video queda anotado en el proyecto: cada tarjeta quita justo ese cambio (`quitarCambioIA`).
    const cambios = [...(p.cambios_ia || [])].reverse().map((c) => {
      const pie = c.estado === "quitado"
        ? `<span class="estado-cambio">${c.conservados ? frase(c.conservados === 1 ? "Quitado. Dejé 1 cosa que cambiaste a mano." : "Quitado. Dejé {n} cosas que cambiaste a mano.", { n: c.conservados }) : "Quitado"}</span>`
        : `<button class="boton chico" data-quitar-ia="${esc(c.id)}" data-sin-traducir>${esc(etiquetaQuitar(c))}</button>`;
      return `<div class="cambio ${c.estado === "quitado" ? "quitado" : ""}">${c.pedido ? `<span class="pedido" data-sin-traducir>«${esc(c.pedido)}»</span>` : ""}
        <span data-sin-traducir>${esc(c.resumen || tr("Listo."))}</span><div class="pie-cambio">${pie}</div></div>`;
    }).join("");
    const historial = ia.historial.filter((c) => c.carpeta === E.sel).map((c) => `<div class="cambio ${c.error ? "error" : ""}"><span class="pedido" data-sin-traducir>«${esc(c.pedido)}»</span>
      <span data-sin-traducir>${esc(c.error || c.resumen)}</span></div>`).join("") + cambios;
    return `<div class="tarjeta"><h3>${frase("Dile a {ia} qué cambiar", { ia: nombre })}</h3>
      <textarea id="pedido-ia" rows="3" placeholder="${esc(tr("Ej.: corta desde «te muestro» hasta «cómo» y pon zoom en «publicar»"))}" ${ia.enviando ? "disabled" : ""} data-sin-traducir>${esc(ia.texto)}</textarea>
      <div class="ejemplos">${EJEMPLOS_IA.map((e) => `<button class="chip" data-ejemplo="${esc(tr(e))}">${esc(e)}</button>`).join("")}</div>
      <button class="boton principal grande" data-accion="pedir-ia" ${ia.enviando ? "disabled" : ""}>${ia.enviando ? frase("{ia} está editando…", { ia: nombre }) : "Aplicar"}</button>
      <p class="nota">${frase("{ia} usa tu cuenta y solo ve el texto con sus tiempos, nunca el video. Puedes quitar cada cambio, aunque hayas seguido editando.", { ia: nombre })}</p></div>
      <div class="historial-ia">${historial}</div>`;
  }

  function panelShorts() {
    const p = P(), nombre = esc(nombreIA());
    const largo = p.fuente.duracion >= 90;
    let cuerpo;
    if (E.buscandoShorts) cuerpo = `<div class="tarjeta">${frase("{ia} está buscando los mejores momentos…", { ia: nombre }, "p")}<div class="barra-prog indef"><i></i></div></div>`;
    else if (E.shorts?.error) cuerpo = `<p class="error-txt" data-sin-traducir>${esc(E.shorts.error)}</p>`;
    else if (E.shorts?.lista) {
      cuerpo = E.shorts.lista.map((s, k) => `<article class="short"><span class="meta" data-sin-traducir>${esc(T("#{n} · {s} s", { n: k + 1, s: Math.round(s.duracion) }))}</span>
        <h4 data-sin-traducir>${esc(s.titulo)}</h4><p data-sin-traducir>${s.gancho ? `<q>${esc(s.gancho)}</q><br>` : ""}${esc(s.por_que)}</p>
        <div class="acciones"><button class="boton" data-ver-short="${k}">▶ <span>Ver</span></button><button class="boton principal" data-crear-short="${k}">Crear este Short</button></div></article>`).join("");
    } else cuerpo = "";
    return `<div class="tarjeta"><h3>Shorts desde un video largo</h3>
      <p class="nota" style="margin-top:0">${frase("{ia} lee la transcripción y elige los momentos de 20 a 60 segundos que se entienden solos y enganchan desde el principio. Cada uno queda como un video nuevo, vertical y con subtítulos.", { ia: nombre })}</p>
      ${!largo ? `<p class="nota">Este video es corto: funciona mejor con videos de más de un minuto y medio (una clase, un podcast, un live).</p>` : ""}
      <div style="margin-top:12px"><button class="boton ${largo ? "principal" : ""}" data-accion="buscar-shorts" ${E.buscandoShorts || !p.palabras.length ? "disabled" : ""}>✨ <span>Buscar los mejores momentos</span></button></div></div>${cuerpo}`;
  }

  // ───────────── Línea de tiempo con pistas: video (cortes y zooms), subtítulos, textos y música ─────────────
  // El formato no cambia: todo sigue siendo tramos {i, f} en segundos del original. La línea de tiempo los muestra en el tiempo del
  // original (lo cortado se ve rayado) y solo mueve sus bordes; nunca crea campos nuevos.
  const MIN_TRAMO = 0.05;
  const ZOOMS_LT = [1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32];
  const zoomMax = (dur) => Math.max(1, dur / 2);  // con el zoom máximo se ven unos 2 segundos
  const NOMBRES_BORDE = { cortes: ["Inicio del corte {n}", "Fin del corte {n}"], zooms: ["Inicio del zoom {n}", "Fin del zoom {n}"],
    textos: ["Inicio del texto {n}", "Fin del texto {n}"], efectos: ["Inicio del efecto {n}", "Fin del efecto {n}"] };
  const MOTIVOS = { silencio: "Silencio", muletilla: "Muletilla", manual: "Corte manual", ia: "Corte de la IA", fuera: "Fuera del Short" };
  const relojFino = (s) => {
    s = Math.max(0, s || 0); const m = Math.floor(s / 60), x = (s - m * 60).toFixed(1).padStart(4, "0");
    return `${m}:${E.idioma === "es" ? x.replace(".", ",") : x}`;
  };
  /** Los tramos que quedan, partidos donde la persona dividió (`divisiones`): se eligen en la pista de video para borrarlos,
   *  recortarlos o ponerles un efecto. Al exportar no cortan nada: solo marcan dónde va una transición (`uniones`). */
  function tramosEdicion(p) {
    const div = [...new Set(p.divisiones || [])].sort((a, b) => a - b), r = [];
    for (const t of conservados(p)) {
      let a = t.i;
      for (const d of div) if (d > a + MIN_TRAMO && d < t.f - MIN_TRAMO) { r.push({ i: a, f: r3(d) }); a = r3(d); }
      r.push({ i: a, f: t.f });
    }
    return r;
  }
  /** Dónde se puede dividir: el cabezal dentro de un tramo que queda, lejos de sus bordes. Devuelve el índice del tramo o -1. */
  function tramoParaDividir(p, t) {
    return tramosEdicion(p).findIndex((x) => x.i + MIN_TRAMO < t && t < x.f - MIN_TRAMO);
  }
  function dividir() {
    const p = P(), t = r3($("#video")?.currentTime || 0);
    if (!p || tramoParaDividir(p, t) < 0) return toast("Pon el cabezal dentro del video para dividir");
    p.divisiones = [...new Set([...(p.divisiones || []), t])].sort((a, b) => a - b);
    E.lt.sel = { lista: "tramos", k: tramosEdicion(p).findIndex((x) => x.i === t) };
    guardar(p, "Dividido");
  }
  /** Lo que hacen los botones de un tramo elegido: borrarlo o recortarlo hasta el cabezal (todo como cortes «manual»). */
  function editarTramo(accion) {
    const p = P(), s = E.lt.sel, tr_ = s?.lista === "tramos" && tramosEdicion(p)[s.k], t = r3($("#video")?.currentTime || 0);
    if (!tr_) return;
    if (accion === "borrar") p.cortes.push({ i: tr_.i, f: tr_.f, motivo: "manual" });
    else if (accion === "inicio" && t > tr_.i + MIN_TRAMO && t < tr_.f) p.cortes.push({ i: tr_.i, f: t, motivo: "manual" });
    else if (accion === "fin" && t < tr_.f - MIN_TRAMO && t > tr_.i) p.cortes.push({ i: t, f: tr_.f, motivo: "manual" });
    else return toast("Pon el cabezal dentro del tramo");
    E.lt.sel = null;
    guardar(p, accion === "borrar" ? "Tramo borrado" : "Recortado");
  }
  /** Hasta dónde se puede mover un borde: sin dar vuelta el tramo (mínimo 0,05 s), sin salir del video y sin pisar a sus vecinos. */
  function limitesBorde(lista, k, borde, dur) {
    const t = lista[k];
    if (borde === "i") {
      let lo = 0;
      lista.forEach((o, j) => { if (j !== k && o.f <= t.i + 1e-9) lo = Math.max(lo, o.f); });
      return [r3(lo), r3(Math.max(lo, t.f - MIN_TRAMO))];
    }
    let hi = dur;
    lista.forEach((o, j) => { if (j !== k && o.i >= t.f - 1e-9) hi = Math.min(hi, o.i); });
    return [r3(Math.min(hi, t.i + MIN_TRAMO)), r3(hi)];
  }
  /** Mueve un borde (i o f) del tramo k dentro de sus límites. Solo cambia ese número: el resto del tramo queda igual. */
  function moverBorde(lista, k, borde, t, dur) {
    const [lo, hi] = limitesBorde(lista, k, borde, dur);
    lista[k][borde] = r3(Math.max(lo, Math.min(hi, t)));
    return lista[k][borde];
  }
  // Cuándo baja la música en la vista previa. Al exportar, ffmpeg la baja escuchando la voz (sidechaincompress, ataque 20 ms y
  // retorno 400 ms); aquí se imita con las palabras que quedan: desde un poco antes de cada palabra hasta 0,4 s después.
  const BAJA = 0.25, VOZ_ANTES = 0.03, VOZ_DESPUES = 0.4;
  function tramosVoz(p) {
    const cortes = unir(p.cortes || []);
    return unir(p.palabras.filter((w) => !palabraCortada(p, w, cortes)).map((w) => ({ i: Math.max(0, w.i - VOZ_ANTES), f: w.f + VOZ_DESPUES })));
  }
  const cuantoBaja = (voz, t) => (voz.some((x) => x.i <= t && t <= x.f) ? BAJA : 1);
  let vozCache = null;
  function voz() {
    const p = P(), k = JSON.stringify(p.cortes) + p.palabras.length;
    if (!vozCache || vozCache.p !== p || vozCache.k !== k) vozCache = { p, k, t: tramosVoz(p) };
    return vozCache.t;
  }

  function marcasRegla() {
    const p = P(), dur = p.fuente.duracion, pxs = (E.lt.ancho || 600) * E.lt.zoom / dur;
    const paso = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800].find((s) => s * pxs >= 64) || 3600;
    let html = "";
    for (let t = 0; t < dur - paso * 0.5; t += paso) html += `<span class="marca" style="left:${(t / dur * 100).toFixed(3)}%">${esc(paso < 1 ? relojFino(t) : reloj(t))}</span>`;
    return html;
  }
  function lineaTiempo() {
    const p = P(), dur = p.fuente.duracion, sel = E.lt.sel;
    const pct = (t) => (Math.max(0, Math.min(dur, t)) / dur * 100).toFixed(3) + "%";
    const pos = (o) => `left:${pct(o.i)};width:${((Math.min(dur, o.f) - Math.max(0, o.i)) / dur * 100).toFixed(3)}%`;
    const bordes = (lista, k, o) => ["i", "f"].map((b) => {
      const [lo, hi] = limitesBorde(p[lista], k, b, dur), nombre = Tp(NOMBRES_BORDE[lista][b === "i" ? 0 : 1], { n: k + 1 });
      return `<span class="borde ${b}" id="lt-${lista}-${k}-${b}" role="slider" tabindex="0" data-borde="${b}" aria-label="${esc(nombre)}"
        aria-valuemin="${lo}" aria-valuemax="${hi}" aria-valuenow="${o[b]}" aria-valuetext="${esc(relojFino(o[b]))}" data-sin-traducir></span>`;
    }).join("");
    // Las etiquetas con texto de la persona se llenan después, con lo que cabe (`ajustarEtiquetas`): nunca letras sueltas.
    const bloque = (lista, k, o, clase, etiqueta = "", titulo = "", texto = null) => `<div class="bloque ${clase} ${sel?.lista === lista && sel.k === k ? "sel" : ""}"
      data-lt="${lista}" data-k="${k}" style="${pos(o)}"${titulo ? ` title="${esc(titulo)}"` : ""}>${bordes(lista, k, o)}<span class="etq" data-sin-traducir${texto != null ? ` data-texto="${esc(texto)}"` : ""}>${etiqueta}</span></div>`;
    const onda = Array.from({ length: 120 }, (_, k) => {
      const t = (k + 0.5) / 120 * dur, habla = p.palabras.some((w) => w.i <= t && t <= w.f);
      return `<i style="height:${habla ? 30 + ((k * 37) % 50) : 4}%"></i>`;
    }).join("");
    const cortes = p.cortes.map((c, k) => bloque("cortes", k, c, "b-corte", "", MOTIVOS[c.motivo] || "")).join("");
    const tramosLt = tramosEdicion(p).map((x, k) => `<div class="bloque b-tramo ${sel?.lista === "tramos" && sel.k === k ? "sel" : ""}" data-lt="tramos" data-k="${k}" style="${pos(x)}"></div>`).join("");
    const efs = p.efectos || [], globales = efs.filter((ap) => !("i" in ap)).map((ap) => nombreFx(efectoPorId(ap.efecto)) || ap.efecto);
    const efectosLt = (globales.length ? `<button class="lt-global-fx" data-pestana="efectos" data-sin-traducir>✨ ${esc(globales.join(" · "))}</button>` : "")
      + efs.map((ap, k) => ("i" in ap ? bloque("efectos", k, ap, "b-efecto", "", "", "✨ " + (nombreFx(efectoPorId(ap.efecto)) || ap.efecto)) : "")).join("");
    const zooms = p.zooms.map((z, k) => bloque("zooms", k, z, "b-zoom", esc(`🔍 ${z.escala}×`))).join("");
    const textos = p.textos.map((x, k) => bloque("textos", k, x, "b-texto", "", "", x.texto)).join("");
    const cortados = unir(p.cortes);
    const subs = lineas(p.palabras.filter((w) => !palabraCortada(p, w, cortados)), p.subtitulos.palabras_por_linea)
      .map((g) => { const t = g.map((w) => w.t).join(" "); return `<div class="bloque b-sub" style="${pos({ i: g[0].i, f: g[g.length - 1].f })}" title="${esc(t)}" data-sin-traducir><span class="etq" data-sin-traducir data-texto="${esc(t)}"></span></div>`; }).join("");
    const sombras = cortados.map((c) => `<span style="${pos(c)}"></span>`).join("");
    let musica = `<button class="lt-agregar" data-accion="elegir-musica">＋ <span>Agregar música</span></button>`;
    if (p.musica) {
      const N = 200, vz = voz(), puntos = ["0,100"];
      for (let k = 0; k <= N; k++) {
        const t = k / N * dur, alto = palabraCortada(p, { i: t, f: t }, cortados) ? 0 : cuantoBaja(vz, t) === 1 ? 88 : 30;
        puntos.push(`${k},${100 - alto}`);
      }
      puntos.push(`${N},100`);
      musica = `<svg class="envolvente ${p.musica.volumen ? "" : "muda"}" viewBox="0 0 ${N} 100" preserveAspectRatio="none" aria-hidden="true"><polygon points="${puntos.join(" ")}"/></svg>
        <span class="nombre-m" data-sin-traducir>♪ ${esc(p.musica.archivo.split(/[\\/]/).pop())}</span>`;
    }
    const niveles = ZOOMS_LT.filter((z) => z <= zoomMax(dur));
    return `<div class="lt" id="lt">
      <div class="lt-herr"><div class="lt-info" id="lt-sel">${infoSel()}</div>
        <button class="boton sutil chico" data-accion="dividir" title="Divide el video en el cabezal (⌘B)">✂ <span>Dividir</span></button>
        <div class="lt-zoom" role="group" aria-label="Zoom de la línea de tiempo">
          <button class="icono" data-lt-zoom="-1" title="Alejar" aria-label="Alejar" ${E.lt.zoom <= 1 ? "disabled" : ""}>−</button>
          <span class="num" data-sin-traducir>${esc(String(E.lt.zoom).replace(".", E.idioma === "es" ? "," : "."))}×</span>
          <button class="icono" data-lt-zoom="1" title="Acercar" aria-label="Acercar" ${E.lt.zoom >= niveles[niveles.length - 1] ? "disabled" : ""}>＋</button>
          <button class="icono" data-lt-zoom="0" title="Ver todo" aria-label="Ver todo" ${E.lt.zoom <= 1 ? "disabled" : ""}>⤢</button></div></div>
      <div class="lt-cuerpo"><div class="lt-nombres" aria-hidden="true"><span></span><span>Video</span><span>Efectos</span><span>Subtítulos</span><span>Textos</span><span>Música</span></div>
        <div class="lt-vista" id="lt-vista"><div class="lt-contenido" id="lt-contenido" style="width:${E.lt.zoom * 100}%">
          <div class="lt-regla" id="linea" role="slider" tabindex="0" aria-label="Línea de tiempo" aria-valuemin="0" aria-valuemax="${Math.round(dur)}" aria-valuenow="0">
            <span id="lt-marcas">${marcasRegla()}</span></div>
          <div class="pista pista-video" role="group" aria-label="Video"><div class="fila-zoom">${zooms}</div><div class="fila-cortes"><div class="onda">${onda}</div>${tramosLt}${cortes}</div></div>
          <div class="pista pista-efectos" role="group" aria-label="Efectos">${efectosLt || `<span class="lt-vacia">Sin efectos</span>`}</div>
          <div class="pista pista-subtitulos ${p.subtitulos.activos ? "" : "apagada"}" role="group" aria-label="Subtítulos"${p.subtitulos.activos ? "" : ` title="Subtítulos apagados"`}>
            ${subs || `<span class="lt-vacia">Sin transcripción</span>`}</div>
          <div class="pista pista-textos" role="group" aria-label="Textos">${textos || `<span class="lt-vacia">Sin textos</span>`}</div>
          <div class="pista pista-musica" role="group" aria-label="Música">${musica}</div>
          <div class="lt-sombras" aria-hidden="true">${sombras}</div>
          <span class="cabezal" id="cabezal" style="left:0"></span></div></div></div></div>`;
  }
  /** Lo que cabe de un texto en `px`: entero; si no, cortado en una palabra con «…»; si ni la primera palabra cabe, nada. */
  let medidor = null;
  function textoQueCabe(texto, px, fuente) {
    medidor ||= document.createElement("canvas").getContext("2d");
    medidor.font = fuente;
    const ancho = (t) => medidor.measureText(t).width;
    if (ancho(texto) <= px) return texto;
    let r = "";
    for (const w of texto.split(" ")) { const t = r ? r + " " + w : w; if (ancho(t + "…") > px) break; r = t; }
    return r ? r + "…" : "";
  }
  function ajustarEtiquetas() {
    let fuente = null;
    for (const el of document.querySelectorAll(".lt .etq[data-texto]")) {
      fuente ||= getComputedStyle(el).font;
      const t = textoQueCabe(el.dataset.texto, el.parentElement.getBoundingClientRect().width - 14, fuente);
      if (el.textContent !== t) el.textContent = t;
    }
  }
  function infoSel() {
    const p = P(), s = E.lt.sel, o = s && (s.lista === "tramos" ? tramosEdicion(p)[s.k] : p?.[s.lista]?.[s.k]);
    if (!o || !("i" in o)) return `<span class="nota">Toca un tramo del video para borrarlo, recortarlo o ponerle un efecto. Arrastra los bordes para ajustarlos.</span>`;
    const v = { a: esc(relojFino(o.i)), b: esc(relojFino(o.f)) };
    if (s.lista === "tramos") {
      return `${frase("Tramo de {a} a {b}", v, "b")}<span class="herr-tramo"><button class="boton sutil chico" data-tramo="inicio" title="Recorta desde el inicio del tramo hasta el cabezal">⇤ <span>Recortar</span></button>
        <button class="boton sutil chico" data-tramo="fin" title="Recorta desde el cabezal hasta el final del tramo"><span>Recortar</span> ⇥</button>
        <button class="boton sutil chico" data-pestana="efectos">✨ <span>Efecto</span></button><button class="boton chico peligro" data-tramo="borrar">Borrar</button></span>`;
    }
    const txt = { cortes: "Corte de {a} a {b}", zooms: "Zoom de {a} a {b}", textos: "Texto de {a} a {b}", efectos: "Efecto de {a} a {b}" }[s.lista];
    return `${frase(txt, v, "b")}<button class="boton sutil chico" data-accion="lt-quitar">${s.lista === "cortes" ? "Volver a poner" : "Quitar"}</button>`;
  }
  function pintarInfo() { const el = $("#lt-sel"); if (el) { el.innerHTML = infoSel(); traducirDOM(el); } }
  function seleccionar(lista, k) {
    E.lt.sel = lista ? { lista, k } : null;
    document.querySelectorAll(".bloque.sel").forEach((el) => el.classList.remove("sel"));
    if (lista) document.querySelector(`.bloque[data-lt="${lista}"][data-k="${k}"]`)?.classList.add("sel");
    pintarInfo();
  }
  /** Mientras se arrastra no se repinta todo (se perdería el puntero): solo el tramo y sus bordes. */
  function pintarBloque(lista, k) {
    const p = P(), o = p[lista][k], dur = p.fuente.duracion, el = document.querySelector(`.bloque[data-lt="${lista}"][data-k="${k}"]`);
    if (!el) return;
    el.style.left = (Math.max(0, o.i) / dur * 100).toFixed(3) + "%";
    el.style.width = ((Math.min(dur, o.f) - Math.max(0, o.i)) / dur * 100).toFixed(3) + "%";
    for (const b of ["i", "f"]) {
      const h = $(`#lt-${lista}-${k}-${b}`), [lo, hi] = limitesBorde(p[lista], k, b, dur);
      if (!h) continue;
      h.setAttribute("aria-valuemin", lo); h.setAttribute("aria-valuemax", hi);
      h.setAttribute("aria-valuenow", o[b]); h.setAttribute("aria-valuetext", relojFino(o[b]));
    }
    ajustarEtiquetas();
    pintarInfo();
  }
  function quitarBloque(lista, k) {
    const p = P();
    p[lista].splice(k, 1);
    E.lt.sel = null;
    guardar(p, { cortes: "Corte quitado", zooms: "Zoom quitado", textos: "Texto quitado", efectos: "Efecto quitado" }[lista]);
  }
  function tiempoEn(x) {
    const c = $("#lt-contenido"), p = P();
    if (!c || !p) return 0;
    const r = c.getBoundingClientRect();
    return Math.max(0, Math.min(1, (x - r.left) / r.width)) * p.fuente.duracion;
  }
  function irA(t) {
    const v = $("#video"), p = P();
    if (!v || !p) return;
    E.rango = null; v.currentTime = Math.max(0, Math.min(p.fuente.duracion, t)); actualizarCapas();
  }
  /** Imán: al arrastrar, el borde se pega al principio o fin de una palabra o al cabezal si pasa a menos de 8 px (Alt lo apaga). */
  function iman(p, t, cabezal) {
    const c = $("#lt-contenido"), umbral = 8 / (c.getBoundingClientRect().width / p.fuente.duracion);
    let mejor = t, dist = umbral;
    const ver = (v) => { const d = Math.abs(v - t); if (d < dist) { dist = d; mejor = v; } };
    for (const w of p.palabras) { ver(w.i); ver(w.f); }
    if (cabezal != null) ver(cabezal);
    return mejor;
  }
  function cambiarZoom(dir, centro) {
    const p = P(), niveles = ZOOMS_LT.filter((z) => z <= zoomMax(p.fuente.duracion));
    const k = Math.max(0, niveles.indexOf(E.lt.zoom));
    const nuevo = dir === 0 ? 1 : niveles[Math.max(0, Math.min(niveles.length - 1, k + dir))];
    if (nuevo === E.lt.zoom) return;
    // Lo que está bajo el centro (o el cabezal) queda en el mismo lugar de la pantalla.
    const vista = $("#lt-vista"), t = centro ?? $("#video")?.currentTime ?? 0, dur = p.fuente.duracion;
    let rel = vista ? (t / dur * vista.scrollWidth - vista.scrollLeft) / vista.clientWidth : 0.5;
    if (!(rel >= 0 && rel <= 1)) rel = 0.5;
    E.lt.zoom = nuevo;
    pintar();
    const v2 = $("#lt-vista"); if (v2) v2.scrollLeft = t / dur * v2.scrollWidth - rel * v2.clientWidth;
  }

  // ───────────── Música en la vista previa: suena de verdad, sigue el tiempo del video exportado y baja cuando hablas ─────────────
  const musicaAudio = typeof Audio === "function" ? new Audio() : null;
  if (musicaAudio) { musicaAudio.loop = true; musicaAudio.preload = "auto"; }
  let gananciaMusica = 1, srcMusica = "";
  function fuenteMusica(p) {
    const a = p?.musica?.archivo;
    if (!a) return "";
    if (/^([\\/]|[A-Za-z]:)/.test(a)) return "";  // fuera de la carpeta: la app solo sirve archivos de ~/Corta
    if (HOST === "web") return a;
    return `corta://video/${encodeURIComponent(proy().carpeta + "/" + a)}`;
  }
  function sincronizarMusica(dt = 0) {
    if (!musicaAudio) return;
    const p = P(), v = $("#video"), src = p ? fuenteMusica(p) : "";
    if (src !== srcMusica) { srcMusica = src; if (src) musicaAudio.src = src; else { musicaAudio.pause(); musicaAudio.removeAttribute("src"); musicaAudio.load(); } }
    if (!p?.musica || !v) return;
    // Baja rápido (como el ataque de 20 ms) y vuelve lento (como el retorno de 400 ms).
    const objetivo = p.palabras.length ? cuantoBaja(voz(), v.currentTime) : 1;
    const tau = objetivo < gananciaMusica ? 0.03 : 0.4;
    gananciaMusica = dt > 0 ? gananciaMusica + (objetivo - gananciaMusica) * (1 - Math.exp(-dt / tau)) : objetivo;
    if (!src || v.paused) { if (!musicaAudio.paused) musicaAudio.pause(); return; }
    musicaAudio.volume = Math.max(0, Math.min(1, p.musica.volumen * gananciaMusica));
    const salida = aSalida(p, v.currentTime, tramos()), d = musicaAudio.duration;
    if (salida != null && d > 0) {  // en el video exportado la música parte en 0 y se repite: aquí igual
      const meta = salida % d, dif = Math.abs(musicaAudio.currentTime - meta);
      if (Math.min(dif, d - dif) > 0.3) musicaAudio.currentTime = meta;
    }
    if (musicaAudio.paused) musicaAudio.play().catch(() => {});
  }
  function reproducir() {
    const v = $("#video"); if (!v) return;
    E.rango = null;
    const tr_ = tramos(); if (tr_.length && v.currentTime >= tr_[tr_.length - 1].f - 0.05) v.currentTime = tr_[0].i;
    v.play().catch(() => {});
    sincronizarMusica();  // dentro del clic, para que el navegador deje sonar la música
  }

  // ───────────── Diálogos ─────────────
  function filasIA() {
    return E.ias.map((ia) => {
      const enUso = E.config.ia === ia.id, probando = E.probando[ia.id], r = E.resultadoIA[ia.id];
      const estado = !ia.instalada ? `<small>No está instalada · <a href="#" data-enlace="${ENLACES.guiaIA}#${ia.id}">Cómo instalarla</a></small>`
        : r && !r.ok ? `<small class="error-txt" data-sin-traducir>${esc(r.texto || tr("No respondió."))}</small>` : `<small>Instalada</small>`;
      const accion = enUso ? `<span class="ok">✓ En uso</span>` : ia.instalada ? `<button class="boton" data-probar="${esc(ia.id)}" ${probando ? "disabled" : ""}>${probando ? "Probando…" : "Usar"}</button>` : "";
      return `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(ia.nombre)}</b>${estado}</div>${accion}</div>`;
    }).join("");
  }
  function filasModelo() {
    return (E.modelos.lista || []).map((m) => {
      const enUso = (E.config.modelo || "turbo") === m.id && m.listo, bajando = E.descarga?.id === m.id;
      const accion = enUso ? `<span class="ok">✓ En uso</span>` : m.listo ? `<button class="boton" data-modelo-usar="${esc(m.id)}">Usar</button>`
        : bajando ? `<div style="width:120px"><div class="barra-prog"><i style="width:${Math.round(E.descarga.pct * 100)}%"></i></div></div>`
          : `<button class="boton" data-modelo="${esc(m.id)}" ${E.descarga ? "disabled" : ""}>${frase("Descargar · {mb} MB", { mb: m.mb })}</button>`;
      return `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(tr(m.nombre))}</b><small data-sin-traducir>${esc(tr(m.detalle))}</small></div>${accion}</div>`;
    }).join("");
  }
  function dialogoExportar() {
    const x = E.exportar, p = P();
    if (x.paso === "listo") {
      return `<h2 id="t-exp">¡Listo para publicar! 🎉</h2>${frase("Tu video vertical de **{d}** quedó guardado en la carpeta del proyecto.", { d: esc(reloj(x.duracion)) }, "p")}
        <div class="pie-dialogo"><button class="boton" data-accion="mostrar-exportado">Mostrar en la carpeta</button><button class="boton principal" data-accion="cerrar">Listo</button></div>`;
    }
    if (x.paso === "error") return `<h2 id="t-exp">No se pudo exportar</h2><p class="error-txt" data-sin-traducir>${esc(x.error)}</p><div class="pie-dialogo"><button class="boton" data-accion="cerrar">Cerrar</button><button class="boton principal" data-accion="exportar-ya">Reintentar</button></div>`;
    if (x.paso === "exportando") {
      return `<h2 id="t-exp">Exportando…</h2>${frase("Formato {l}, 1080 px, con subtítulos. Esto pasa en tu computador.", { l: esc(p.lienzo) }, "p")}
        <div class="barra-prog"><i style="width:${x.pct || 0}%"></i></div><p class="nota" data-sin-traducir>${esc(T("{n} %", { n: x.pct || 0 }))}</p>`;
    }
    return `<h2 id="t-exp">Exportar</h2>${frase("Queda un video de **{d}** en formato {l}, listo para subir.", { d: esc(reloj(duracionFinal(p))), l: esc(p.lienzo) }, "p")}
      <div class="pie-dialogo"><button class="boton" data-accion="cerrar">Cancelar</button><button class="boton principal" data-accion="exportar-ya">Exportar video</button></div>`;
  }
  function dialogoAjustes() {
    const actualizando = E.act && E.act.paso !== "error";  // la app de escritorio manda el avance (actualizacionProgreso)
    return `<h2 id="t-aj">Ajustes</h2><p>Todo se procesa en tu computador. La IA usa tu propia cuenta.</p>
      <div class="seccion"><h3>Tu IA</h3>${filasIA()}</div>
      <div class="seccion"><h3>Transcripción</h3>${filasModelo()}</div>
      <div class="seccion"><h3>Vocabulario</h3>${seccionVocabulario()}</div>
      <div class="seccion"><h3>General</h3><div class="fila"><div class="txt"><b>Idioma de la app</b></div><select data-config="idioma_ui"><option value="es" ${E.idioma === "es" ? "selected" : ""}>Español</option><option value="en" ${E.idioma === "en" ? "selected" : ""}>English</option></select></div>
        <div class="fila"><div class="txt"><b>Carpeta de tus videos</b><small data-sin-traducir>${esc(E.carpeta)}</small></div><button class="boton" data-accion="abrir-carpeta">Abrir</button></div></div>
      <div class="seccion"><h3>Acerca de Corta</h3><p style="margin:0 0 8px;color:var(--suave)">${frase("Corta {v} · Gratis y de código abierto (AGPL-3.0).", { v: esc(E.version) })}</p>
        <div class="fila"><div class="txt"><b>Actualizaciones</b>${actualizando ? `<small data-sin-traducir>${esc(E.act.texto || "")}</small>`
          : `<small>${E.buscando === "buscando" ? "Buscando…" : E.buscando === "alDia" ? "Estás en la última versión." : E.buscando === "sinConexion" ? "No pude revisar. Revisa tu conexión." : E.actualizacion?.hay ? "Hay una versión nueva." : "Corta revisa sola cada 6 horas."}</small>`}</div>
          ${actualizando ? `<div style="width:120px"><div class="barra-prog ${E.act.pct == null ? "indef" : ""}"><i style="width:${E.act.pct ?? 0}%"></i></div></div>`
            : E.actualizacion?.hay ? `<button class="boton principal" data-accion="actualizar">Actualizar</button>` : `<button class="boton" data-accion="buscar-act" ${E.buscando === "buscando" ? "disabled" : ""}>Buscar actualizaciones</button>`}</div>
        <div class="enlaces"><a href="#" data-enlace="${ENLACES.sitio}">Sitio web</a><a href="#" data-enlace="${ENLACES.codigo}">Código</a><a href="#" data-enlace="${ENLACES.comunidad}">Comunidad</a></div></div>
      <div class="pie-dialogo"><button class="boton principal" data-accion="cerrar">Listo</button></div>`;
  }
  /** Palabras que Corta corrige sola al transcribir y que le enseña al transcriptor (~/Corta/vocabulario.json). */
  function seccionVocabulario() {
    const v = E.vocabulario, filas = v.reemplazos.map((r, k) => `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(r.de)} <span class="flecha" aria-hidden="true">→</span> ${esc(r.a)}</b></div>
      <button class="boton sutil chico" data-vocab-quitar="${k}" aria-label="${esc(Tp("Quitar «{x}»", { x: r.de }))}" data-sin-traducir>${esc(tr("Quitar"))}</button></div>`).join("");
    const chips = v.palabras.map((w, k) => `<span class="chip-vocab"><span data-sin-traducir>${esc(w)}</span><button class="icono" data-vocab-quitar-palabra="${k}" aria-label="${esc(Tp("Quitar «{x}»", { x: w }))}" data-sin-traducir>×</button></span>`).join("");
    return `<p class="nota" style="margin:0 0 6px">Corta corrige estas palabras al transcribir tus próximos videos y se las enseña al transcriptor, para que reconozca nombres y marcas.</p>
      ${filas || chips ? "" : `<p class="nota" style="margin:0 0 6px">Todavía no hay nada. Cuando corrijas una palabra del subtítulo, toca «Recordar para próximos videos».</p>`}
      ${filas}${chips ? `<div class="chips-vocab">${chips}</div>` : ""}
      <div class="fila"><input class="texto" id="vocab-nueva" maxlength="60" placeholder="Un nombre o una marca" autocomplete="off"><button class="boton" data-accion="vocab-agregar">Agregar</button></div>`;
  }
  /** Paso 0 de la bienvenida: el idioma, antes que cualquier otra cosa. Cada opción va escrita en su propio idioma (no se traduce)
   *  y la del sistema (o la ya guardada) queda marcada como sugerida y con el foco. */
  function pasoIdioma() {
    const sugerido = E.idioma === "en" ? "en" : "es";
    const opcion = (codigo, nombre, detalle, etiqueta) => `<button class="boton opcion-idioma${codigo === sugerido ? " principal" : ""}" id="idioma-${codigo}" lang="${codigo}" data-elegir-idioma="${codigo}">
      <b>${nombre}</b><small>${detalle}</small>${codigo === sugerido ? `<em class="sugerido">${etiqueta}</em>` : ""}</button>`;
    return `<div class="idioma-bv" data-sin-traducir>${LOGO}
      <h2 id="t-bv" tabindex="-1"><span lang="es">Elige tu idioma</span> <span class="punto" aria-hidden="true">·</span> <span lang="en">Choose your language</span></h2>
      <div class="opciones-idioma">${opcion("es", "Español", "Continuar en español", "Sugerido")}${opcion("en", "English", "Continue in English", "Suggested")}</div>
      <p class="nota-idioma"><span lang="es">Puedes cambiarlo cuando quieras en Ajustes.</span> <span lang="en">You can change it anytime in Settings.</span></p></div>`;
  }
  async function elegirIdioma(codigo) {
    E.config.idioma_ui = codigo;
    host.enviar("config", { idioma_ui: codigo });  // el mismo camino que el selector de Ajustes
    await cargarIdioma(codigo);
    E.bv = 1;
    pintar();
    $("#t-bv")?.focus();
    const avisos = avisosPendientes; avisosPendientes = [];
    if (avisos.length) toast(avisos[avisos.length - 1]);
  }
  function bienvenida() {
    const paso = E.bv;
    const puntos = `<div class="pasos-bv" aria-hidden="true">${[0, 1, 2, 3].map((i) => `<i class="${i <= paso ? "hecho" : ""}"></i>`).join("")}</div>`;
    if (paso === 0) return puntos + pasoIdioma();
    const modeloListo = (E.modelos.lista || []).some((m) => m.listo);
    const pasos = [
      null,  // 0: el idioma (pasoIdioma)
      ["Hola, esto es Corta", `<p>Un editor para Shorts, Reels y TikTok que funciona en tu computador. Lo transcribe todo, editas el texto y tu propia IA hace el trabajo pesado. Gratis y sin marca de agua.</p>`, true],
      ["Elige tu IA", `<p>Corta usa la IA que ya tienes, con tu cuenta. La probamos con una pregunta corta.</p><div class="seccion">${filasIA()}</div>`, !!E.config.ia],
      ["Descarga el transcriptor", `<p>Convierte la voz en texto dentro de tu computador. Se descarga una sola vez.</p><div class="seccion">${filasModelo()}</div>`, modeloListo],
    ];
    const [titulo, cuerpo, puede] = pasos[paso];
    return `${puntos}<h2 id="t-bv" tabindex="-1">${titulo}</h2>${cuerpo}
      <div class="pie-dialogo"><button class="boton izq" data-bv="${paso - 1}">Atrás</button><button class="boton" data-accion="bv-fin">Lo hago después</button>
        ${paso < pasos.length - 1 ? `<button class="boton principal" data-bv="${paso + 1}" ${puede ? "" : "disabled"}>Siguiente</button>` : `<button class="boton principal" data-accion="bv-fin">Empezar</button>`}</div>`;
  }
  function dialogos() {
    const capa = (id, html) => `<div class="capa"><div class="dialogo" role="dialog" aria-modal="true" aria-labelledby="${id}">${html}</div></div>`;
    if (E.exportar) return capa("t-exp", dialogoExportar());
    if (E.bv === 0) return `<div class="capa capa-idioma"><div class="dialogo" role="dialog" aria-modal="true" aria-labelledby="t-bv">${bienvenida()}</div></div>`;
    if (E.bv !== null) return capa("t-bv", bienvenida());
    if (E.ajustes) return capa("t-aj", dialogoAjustes());
    if (E.catalogo) return capa("t-cat", dialogoCatalogo());
    if (E.pl) return capa("t-pl", dialogoPlantillas()).replace('class="dialogo"', 'class="dialogo dialogo-pl"');
    return "";
  }

  // ───────────── Vista previa: saltar cortes, subtítulos, zoom y encuadre ─────────────
  function ajustarPantalla() {
    const p = P(), esc_ = $("#escenario"), pant = $("#pantalla"), v = $("#video");
    if (!p || !esc_ || !pant || !v) return;
    const [W, H] = LIENZOS[p.lienzo];
    const maxW = esc_.clientWidth - 44, maxH = esc_.clientHeight - 44;
    const s = Math.min(maxW / W, maxH / H);
    const pw = Math.max(120, Math.round(W * s)), ph = Math.max(120, Math.round(H * s));
    pant.style.width = pw + "px"; pant.style.height = ph + "px";
    const sw = p.fuente.ancho, sh = p.fuente.alto;
    const cubrir = Math.max(pw / sw, ph / sh), contener = Math.min(pw / sw, ph / sh);
    const esc2 = p.relleno === "desenfoque" ? contener : cubrir;
    const vw = sw * esc2, vh = sh * esc2;
    Object.assign(v.style, { width: vw + "px", height: vh + "px",
      left: (p.relleno === "desenfoque" ? (pw - vw) / 2 : -(vw - pw) * p.encuadre.x) + "px",
      top: (p.relleno === "desenfoque" ? (ph - vh) / 2 : -(vh - ph) * p.encuadre.y) + "px" });
    const c = $("#fondo-borroso");
    if (c) { c.width = Math.round(pw / 4); c.height = Math.round(ph / 4); Object.assign(c.style, { inset: "0", width: pw + "px", height: ph + "px", filter: "blur(14px) brightness(.85)", transform: "scale(1.1)" }); }
    pant.dataset.escala = pw / W;
    // La línea de tiempo: con su ancho real se eligen cada cuánto van las marcas de la regla.
    const vista = $("#lt-vista");
    if (vista && vista.clientWidth && vista.clientWidth !== E.lt.ancho) { E.lt.ancho = vista.clientWidth; const m = $("#lt-marcas"); if (m) m.innerHTML = marcasRegla(); ajustarEtiquetas(); }
    actualizarCapas();
  }
  /** Qué efectos se ven en el segundo t del original (`te`: el mismo momento en el video exportado). */
  let fxCache = null;
  function infoEfectos(p) {
    const k = JSON.stringify([p.efectos, p.cortes, p.divisiones, p.fuente.duracion]);
    if (fxCache?.p === p && fxCache.k === k) return fxCache.v;
    const v = (p.efectos || []).map((ap) => {
      const [i, f] = alcanceEf(p, ap), pedazos = intervalosSalida(p, i, f);
      if (!pedazos.length || !Array.isArray(ap.pasos)) return null;
      const a = pedazos[0][0], b = pedazos[pedazos.length - 1][1], juntas = uniones(p, i, f);
      return { pedazos, pasos: ap.pasos.map((paso) => ({ paso, segs: paso.tipo === "zoom" ? segmentosZoom({ ...paso, desde: numFx(paso, "desde", 1), hasta: numFx(paso, "hasta", 1) }, a, b) : segmentosCapa(paso, a, b, juntas, pedazos) })) };
    }).filter(Boolean);
    fxCache = { p, k, v };
    return v;
  }
  function efectosEn(p, t, te, escala) {
    const r = { filtro: "", capas: "", zoom: 1 };
    if (te == null || !p.efectos?.length) return r;
    const filtro = [], capas = [], W = LIENZOS[p.lienzo][0];
    for (const ef of infoEfectos(p)) {
      const dentro = ef.pedazos.some(([a, b]) => a <= te && te <= b);
      for (const { paso, segs } of ef.pasos) {
        if (paso.tipo === "zoom") { r.zoom *= valorEn(segs, te, 1); continue; }
        if (["tinte", "fundido", "transicion"].includes(paso.tipo)) {
          const a = valorEn(segs, te, 0);
          if (a > 0.001) capas.push(`<i style="background:rgb(${rgbFx(paso)});opacity:${a.toFixed(3)}"></i>`);
          continue;
        }
        if (!dentro) continue;
        if (paso.tipo === "color") filtro.push(cssColor(paso));
        else if (paso.tipo === "desenfoque") filtro.push(`blur(${(numFx(paso, "radio", 4) * W / 1080 * escala).toFixed(2)}px)`);
        else if (paso.tipo === "vineta") capas.push(`<i style="background:${vinetaCSS(numFx(paso, "fuerza", 0.5))}"></i>`);
      }
    }
    r.filtro = filtro.join(" ");
    r.capas = capas.join("");
    return r;
  }
  let tramosCache = null, tramosDe = null;
  function tramos() { const p = P(); if (tramosDe !== p || !tramosCache || tramosCache.k !== JSON.stringify(p.cortes)) { tramosCache = { k: JSON.stringify(p.cortes), t: conservados(p) }; tramosDe = p; } return tramosCache.t; }
  function actualizarCapas() {
    const p = P(), v = $("#video");
    if (!p || !v) return;
    const t = v.currentTime, s = estilo(), escala = Number($("#pantalla")?.dataset.escala || 0.3);
    const [W] = LIENZOS[p.lienzo], pw = W * escala;
    // Reloj y cabezal
    const salida = aSalida(p, t, tramos());
    const rel = $("#reloj"); if (rel && salida != null) rel.innerHTML = T("**{a}** de {b}", { a: esc(reloj(salida)), b: esc(reloj(duracionFinal(p))) });
    const cab = $("#cabezal"); if (cab) cab.style.left = (t / p.fuente.duracion * 100).toFixed(3) + "%";
    const regla = $("#linea");
    if (regla && regla.getAttribute("aria-valuenow") !== String(Math.round(t))) { regla.setAttribute("aria-valuenow", Math.round(t)); regla.setAttribute("aria-valuetext", relojFino(t)); }
    // Con zoom, la línea de tiempo sigue al cabezal mientras se reproduce.
    const vista = $("#lt-vista");
    if (vista && E.lt.zoom > 1 && !v.paused && !arrastre) {
      const x = t / p.fuente.duracion * vista.scrollWidth;
      if (x < vista.scrollLeft || x > vista.scrollLeft + vista.clientWidth - 24) vista.scrollLeft = x - vista.clientWidth * 0.2;
    }
    // Medidor de la música (pestaña Música)
    const nivel = $("#musica-nivel");
    if (nivel && p.musica) {
      nivel.style.width = Math.round(gananciaMusica * 100) + "%";
      const ahora = $("#musica-ahora"), txt = tr(gananciaMusica < 0.6 ? "La música baja: estás hablando" : "Volumen normal");
      if (ahora && ahora.textContent !== txt) ahora.textContent = txt;
    }
    // Efectos (la misma lógica de tiempos que bin/efectos.py): filtros de CSS, capas de color y zoom animado
    const fx = efectosEn(p, t, salida, escala);
    // Zoom
    const z = (p.zooms || []).find((x) => x.i <= t && t <= x.f);
    const capa = $("#capa-zoom");
    if (capa) {
      const esc_ = (z ? z.escala : 1) * fx.zoom;
      capa.style.transform = esc_ !== 1 ? `scale(${esc_.toFixed(4)})` : "none";
      capa.style.transition = fx.zoom !== 1 ? "none" : "";
      if (capa.dataset.filtro !== fx.filtro) { capa.style.filter = fx.filtro; capa.dataset.filtro = fx.filtro; }
    }
    const cf = $("#capas-fx"); if (cf && cf.dataset.html !== fx.capas) { cf.innerHTML = fx.capas; cf.dataset.html = fx.capas; }
    // Fondo borroso
    const c = $("#fondo-borroso"); if (c && v.readyState >= 2) { try { c.getContext("2d").drawImage(v, 0, 0, c.width, c.height); } catch {} }
    // Palabra activa en el panel de texto
    const k = p.palabras.findIndex((w) => w.i <= t && t <= w.f + 0.05);
    document.querySelectorAll(".w.activa").forEach((el) => el.classList.remove("activa"));
    if (k >= 0) document.querySelector(`.w[data-w="${k}"]`)?.classList.add("activa");
    // Subtítulos
    const subs = $("#subs");
    if (subs) {
      subs.style.top = (p.subtitulos.posicion * 100) + "%";
      let html = "";
      const ed = E.editar?.donde === "vista" ? E.editar : null;
      if (ed && s) {
        // Corrigiendo sobre la vista previa: un campo en el lugar del subtítulo (se pinta una vez; lo escrito vive en E.editar).
        const tam = s.tamano / 100 * pw;
        const clave = `editar-${ed.desde}-${ed.hasta}-${E.sel}`;
        if (subs.dataset.html !== clave) {
          subs.innerHTML = `<input class="editar-sub" id="editar-sub" value="${esc(ed.valor)}" maxlength="80" autocomplete="off" autocapitalize="off" spellcheck="false"
            aria-label="${esc(tr("Corregir la palabra"))}" style="${cssEstilo(s, escala)}font-size:${Math.max(14, tam * 0.8).toFixed(1)}px" data-sin-traducir>`;
          subs.dataset.html = clave; subs.removeAttribute("aria-hidden");
        }
      } else if (p.subtitulos.activos && s) {
        const cortes = unir(p.cortes), visibles = p.palabras.filter((w) => !palabraCortada(p, w, cortes));
        const grupos = lineas(visibles, p.subtitulos.palabras_por_linea);
        const g = grupos.find((gr) => gr[0].i - 0.02 <= t && t <= gr[gr.length - 1].f + 0.25) || null;
        if (g) {
          const activa = g.findIndex((w, j) => t >= w.i - 0.02 && (j + 1 >= g.length || t < g[j + 1].i));
          const tam = s.tamano / 100 * pw, borde = s.borde * escala;
          const base = `${cssEstilo(s, escala)}font-size:${tam.toFixed(1)}px;${s.fondo ? `background:${s.color_fondo};border-radius:${(tam * .2).toFixed(1)}px;padding:${(tam * .12).toFixed(1)}px ${(tam * .3).toFixed(1)}px;` : ""}`;
          const palabras = s.animacion === "palabra" ? [g[Math.max(0, activa)]] : g;
          html = `<div style="${base}display:inline-block" data-sin-traducir>${palabras.map((w, j) => {
            const es = s.animacion === "palabra" || j === activa;
            const extra = !es || s.animacion === "ninguna" ? "" : `color:${s.color_activo};${s.animacion === "pop" || s.animacion === "palabra" ? "transform:scale(1.12);" : ""}${s.animacion === "subrayado" ? `text-decoration:underline;text-decoration-thickness:${Math.max(2, borde).toFixed(1)}px;` : ""}`;
            // Tocar una palabra del subtítulo la corrige ahí mismo (con el video en pausa, para no perseguirla).
            return `<span style="${extra}" data-sub-w="${p.palabras.indexOf(w)}" title="${esc(tr("Toca para corregir"))}">${esc(w.t)}</span>`;
          }).join(" ")}</div>`;
        }
      }
      if (!ed && subs.dataset.html !== html) { subs.innerHTML = html; subs.dataset.html = html; subs.setAttribute("aria-hidden", "true"); }
    }
    const ts = $("#texto-sobre");
    if (ts) {
      const tx = (p.textos || []).find((x) => x.i <= t && t <= x.f);
      ts.style.top = ((tx?.y ?? 0.18) * 100) + "%";
      const h2 = tx && s ? `<div style="${cssEstilo(s, escala)}font-size:${(s.tamano / 100 * pw * 0.9).toFixed(1)}px;display:inline-block" data-sin-traducir>${esc(tx.texto)}</div>` : "";
      if (ts.dataset.html !== h2) { ts.innerHTML = h2; ts.dataset.html = h2; }
    }
  }
  /** Mientras se reproduce: si cae dentro de un corte, salta al siguiente tramo; al final, se detiene. La música la sigue. */
  let ultimoCuadro = 0;
  function bucle(ahora = 0) {
    const dt = ultimoCuadro ? Math.min(0.25, (ahora - ultimoCuadro) / 1000) : 0;
    ultimoCuadro = ahora;
    const p = P(), v = $("#video");
    if (p && v && !v.paused) {
      const t = v.currentTime, tr_ = tramos();
      if (E.rango && t >= E.rango.f) { v.pause(); E.rango = null; }
      else if (!tr_.some((x) => x.i <= t && t < x.f - 0.02)) {
        const sig = tr_.find((x) => x.i > t);
        if (sig) v.currentTime = sig.i; else { v.pause(); v.currentTime = tr_[0]?.i || 0; }
      }
      const b = $("#boton-play"); if (b) b.textContent = "❚❚";
    } else { const b = $("#boton-play"); if (b && b.textContent !== "▶") b.textContent = "▶"; }
    sincronizarMusica(dt);
    actualizarCapas();
    animarPlantillas(ahora);
    requestAnimationFrame(bucle);
  }
  window.addEventListener("resize", () => ajustarPantalla());
  // Las muestras de los efectos usan el cuadro del video: se vuelven a copiar cuando hay un cuadro nuevo en pausa.
  document.addEventListener("seeked", (ev) => { if (ev.target.id === "video") pintarMuestras(); }, true);
  document.addEventListener("loadeddata", (ev) => { if (ev.target.id === "video") pintarMuestras(); }, true);
  // Cada clip del panel Clips muestra el cuadro donde empieza su parte (sin #t= en la dirección: corta:// no acepta fragmentos).
  document.addEventListener("loadedmetadata", (ev) => { const d = ev.target.dataset?.desde; if (d != null) ev.target.currentTime = Number(d) + 0.05; }, true);

  // ───────────── Eventos ─────────────
  function elegirPalabra(k, extender) {
    if (extender && E.ancla != null) E.seleccion = [Math.min(E.ancla, k), Math.max(E.ancla, k)];
    else { E.seleccion = [k, k]; E.ancla = k; }
  }
  function cortarSeleccion() {
    const p = P(), [a, b] = E.seleccion;
    cortarPalabras(p, a, b, "manual");
    E.seleccion = null;
    guardar(p);
  }
  function restaurarSeleccion() {
    const p = P(), [a, b] = E.seleccion;
    restaurar(p, p.palabras[a].i - 0.01, p.palabras[b].f + 0.01);
    E.seleccion = null;
    guardar(p);
  }
  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-accion],[data-sel],[data-pestana],[data-w],[data-pausa],[data-lienzo],[data-estilo],[data-ejemplo],[data-ver-short],[data-crear-short],[data-probar],[data-modelo],[data-modelo-usar],[data-bv],[data-enlace],[data-lt-zoom],[data-elegir-idioma],[data-sub-w],[data-vocab-quitar],[data-vocab-quitar-palabra],[data-quitar-ia],[data-fx],[data-fx-cat],[data-cat-cat],[data-bajar-fx],[data-quitar-fx],[data-tramo],[data-ver-pl],[data-pl-cat],[data-pl-fuente],[data-bajar-pl],[data-pl-bajar-fx],[data-elegir-clips],[data-cambiar-clip]");
    if (!el) return;
    const d = el.dataset, p = P(), v = $("#video");
    if (d.elegirIdioma) return elegirIdioma(d.elegirIdioma === "en" ? "en" : "es");
    if (d.ltZoom != null) return cambiarZoom(Number(d.ltZoom));
    if (d.enlace) { ev.preventDefault(); return host.enviar("abrirEnlace", { url: d.enlace }); }
    if (d.sel) { E.sel = d.sel; E.seleccion = null; E.shorts = null; E.ultimoAhorro = null; E.lt.sel = null; E.editar = null; E.sugerencia = null; return pintar(); }
    if (d.pestana) { E.pestana = d.pestana; return pintar(); }
    if (d.subW != null) return empezarEdicion(Number(d.subW), Number(d.subW), "vista");
    if (d.fx) return aplicarEfecto(d.fx);
    if (d.fxCat) { E.fx.categoria = d.fxCat; return pintar(); }
    if (d.catCat && E.catalogo) { E.catalogo.categoria = d.catCat; return pintar(); }
    if (d.bajarFx && E.catalogo) { E.catalogo.bajando[d.bajarFx] = true; host.enviar("descargarEfecto", { id: d.bajarFx }); return pintar(); }
    if (d.quitarFx != null) { const ap = p.efectos?.[Number(d.quitarFx)]; if (ap) { p.efectos.splice(Number(d.quitarFx), 1); E.lt.sel = null; guardar(p, "Efecto quitado"); } return; }
    if (d.tramo) return editarTramo(d.tramo);
    if (d.verPl != null && E.pl) { E.pl.ver = d.verPl || null; pintar(); return $(".dialogo-pl")?.scrollTo?.(0, 0); }
    if (d.plCat && E.pl) { E.pl.categoria = d.plCat; return pintar(); }
    if (d.plFuente && E.pl) {
      E.pl.fuente = d.plFuente;
      if (d.plFuente === "comunidad" && E.pl.catalogo?.estado !== "listo") { E.pl.catalogo = { estado: "cargando", plantillas: [], efectos: [] }; host.enviar("catalogoPlantillas"); }
      return pintar();
    }
    if (d.bajarPl && E.pl) { E.pl.bajando[d.bajarPl] = true; host.enviar("descargarPlantilla", { id: d.bajarPl }); return pintar(); }
    if (d.plBajarFx && E.pl) {
      E.pl.bajando[d.plBajarFx] = true;
      // Para descargar un efecto la app necesita el índice del catálogo: si todavía no está, primero se pide.
      if (E.pl.catalogo?.estado === "listo") host.enviar("descargarEfecto", { id: d.plBajarFx });
      else { E.pl.pendiente = d.plBajarFx; E.pl.catalogo = { estado: "cargando", plantillas: [], efectos: [] }; host.enviar("catalogoPlantillas"); }
      return pintar();
    }
    if (d.elegirClips && E.pl) { const pl = plantillaPorId(d.elegirClips); if (!pl) return; E.pl.armando = true; host.enviar("elegirClips", { plantilla: pl.id, n: pl.huecos.length }); return pintar(); }
    if (d.cambiarClip != null && p?.plantilla) { E.armando = { carpeta: E.sel, k: Number(d.cambiarClip) }; host.enviar("cambiarClip", { carpeta: E.sel, hueco: Number(d.cambiarClip) }); return pintar(); }
    if (d.quitarIa) {
      const r = quitarCambioIA(p, d.quitarIa);
      if (!r) return;
      E.lt.sel = null;
      return r.conservados ? guardar(p, Tp(r.conservados === 1 ? "Listo. Dejé 1 cosa que cambiaste a mano." : "Listo. Dejé {n} cosas que cambiaste a mano.", { n: r.conservados }), true)
        : guardar(p, "Cambio quitado");
    }
    if (d.vocabQuitar != null) { const r = E.vocabulario.reemplazos[Number(d.vocabQuitar)]; if (r) host.enviar("vocabulario", { accion: "quitar", de: r.de }); return; }
    if (d.vocabQuitarPalabra != null) { const w = E.vocabulario.palabras[Number(d.vocabQuitarPalabra)]; if (w) host.enviar("vocabulario", { accion: "quitar_palabra", palabra: w }); return; }
    if (d.w != null) {
      const k = Number(d.w);
      // Tocar otra vez la palabra elegida la corrige.
      if (!ev.shiftKey && E.seleccion && E.seleccion[0] === k && E.seleccion[1] === k) return empezarEdicion(k, k, "texto");
      elegirPalabra(k, ev.shiftKey);
      if (v && !ev.shiftKey) v.currentTime = p.palabras[k].i;
      return pintar();
    }
    if (d.pausa != null) {
      const k = Number(d.pausa), a = p.palabras[k - 1], b = p.palabras[k], medio = (a.f + b.i) / 2;
      if (unir(p.cortes).some((c) => c.i <= medio && medio <= c.f)) restaurar(p, a.f, b.i);
      else p.cortes.push({ i: r3(a.f + MARGEN), f: r3(b.i - MARGEN), motivo: "manual" });
      return guardar(p);
    }
    if (d.lienzo) { p.lienzo = d.lienzo; guardar(p); return ajustarPantalla(); }
    if (d.estilo) { p.subtitulos.estilo = d.estilo; return guardar(p); }
    if (d.ejemplo) { E.ia.texto = d.ejemplo; pintar(); return $("#pedido-ia")?.focus(); }
    if (d.verShort != null) { const s = E.shorts.lista[Number(d.verShort)]; E.rango = { i: s.i, f: s.f }; if (v) { v.currentTime = s.i; v.play(); } return; }
    if (d.crearShort != null) { const s = E.shorts.lista[Number(d.crearShort)]; host.enviar("crearShort", { carpeta: E.sel, desde: s.i, hasta: s.f, titulo: s.titulo }); return toast("Creando el Short…"); }
    if (d.probar) { E.probando[d.probar] = true; delete E.resultadoIA[d.probar]; host.enviar("probarIA", { id: d.probar }); return pintar(); }
    if (d.modelo) { E.descarga = { id: d.modelo, pct: 0 }; host.enviar("descargarModelo", { id: d.modelo }); return pintar(); }
    if (d.modeloUsar) { E.config.modelo = d.modeloUsar; host.enviar("config", { modelo: d.modeloUsar }); return pintar(); }
    if (d.bv) { E.bv = Number(d.bv); return pintar(); }
    switch (d.accion) {
      case "nuevo": return host.enviar("elegirVideo");
      case "play": case "escuchar-musica": if (v) { if (v.paused) reproducir(); else v.pause(); } return;
      case "elegir-musica": if (v) v.pause(); return host.enviar("elegirMusica", { carpeta: E.sel });
      case "quitar-musica": p.musica = null; return guardar(p, "Música quitada");
      case "lt-quitar": if (E.lt.sel && p[E.lt.sel.lista]?.[E.lt.sel.k]) quitarBloque(E.lt.sel.lista, E.lt.sel.k); return;
      case "dividir": return dividir();
      case "fx-todo": E.seleccion = null; if (E.lt.sel?.lista === "tramos") E.lt.sel = null; return pintar();
      case "explorar-fx": E.catalogo = { estado: "cargando", efectos: [], categoria: E.catalogo?.categoria || "todos", busqueda: E.catalogo?.busqueda || "", bajando: {} }; host.enviar("catalogoEfectos"); return pintar();
      case "cortar-sel": return cortarSeleccion();
      case "editar-sel": if (E.seleccion) empezarEdicion(E.seleccion[0], E.seleccion[1], "texto"); return;
      case "linea-sel": {
        const w = E.seleccion && p.palabras[E.seleccion[0]];
        if (!w) return;
        if (d.valor) w.linea = d.valor; else delete w.linea;
        return guardar(p, d.valor === "fin" ? "Frase separada" : d.valor === "sigue" ? "Frases unidas" : "Como antes");
      }
      case "sug-todo": {
        const sg = E.sugerencia; if (!sg) return;
        const [nuevas, n] = reemplazarTodo(p.palabras, [{ de: sg.de, a: sg.a }]);
        p.palabras = nuevas; sg.todo = true; sg.n = n;
        if (sg.recordado) E.sugerencia = null;
        return guardar(p);
      }
      case "sug-recordar": {
        const sg = E.sugerencia; if (!sg) return;
        host.enviar("vocabulario", { accion: "agregar", de: sg.de, a: sg.a });
        sg.recordado = true;
        if (sg.todo || !sg.n) { E.sugerencia = null; toast("Lo recordaré en tus próximos videos"); }
        return pintar();
      }
      case "sug-cerrar": E.sugerencia = null; return pintar();
      case "vocab-agregar": {
        const inp = $("#vocab-nueva"), t = (inp?.value || "").trim();
        if (!t) return inp?.focus();
        host.enviar("vocabulario", { accion: "palabra", palabra: t.slice(0, 60) });
        inp.value = ""; return;
      }
      case "restaurar-sel": return restaurarSeleccion();
      case "zoom-sel": { const [a, b] = E.seleccion; p.zooms.push({ i: p.palabras[a].i, f: p.palabras[b].f, escala: 1.25 }); E.seleccion = null; return guardar(p, "Zoom agregado"); }
      case "limpiar": E.limpiando = true; host.enviar("limpiar", { carpeta: E.sel, silencio: 0.5, muletillas: true }); return pintar();
      case "transcribir": host.enviar("transcribir", { carpeta: E.sel }); return;
      case "deshacer": host.enviar("deshacer", { carpeta: E.sel }); return;
      case "pedir-ia": {
        const texto = ($("#pedido-ia")?.value || "").trim();
        if (!texto) return $("#pedido-ia")?.focus();
        E.ia = { ...E.ia, texto, enviando: true };
        host.enviar("pedirIA", { carpeta: E.sel, texto });
        return pintar();
      }
      case "buscar-shorts": E.buscandoShorts = true; E.shorts = null; host.enviar("buscarShorts", { carpeta: E.sel }); return pintar();
      case "exportar": if (v) v.pause(); E.exportar = { paso: "pedir" }; return pintar();
      case "exportar-ya": E.exportar = { paso: "exportando", pct: 0 }; host.enviar("exportar", { carpeta: E.sel }); return pintar();
      case "mostrar-exportado": return host.enviar("abrirCarpeta", { ruta: E.exportar?.archivo || E.sel });
      case "ajustes": E.ajustes = true; return pintar();
      case "cerrar": if (E.exportar?.paso !== "exportando") E.exportar = null; E.ajustes = false; E.catalogo = null; if (!E.pl?.armando) E.pl = null; return pintar();
      case "plantillas": if ($("#video")) $("#video").pause(); E.pl = { fuente: "corta", categoria: "todas", busqueda: "", ver: null, armando: false, bajando: {}, catalogo: E.pl?.catalogo || null }; return pintar();
      case "abrir-carpeta": return host.enviar("abrirCarpeta", {});
      case "actualizar": E.act = { paso: 1, texto: tr("Preparando…") }; host.enviar("actualizar"); return pintar();
      case "buscar-act": E.buscando = "buscando"; host.enviar("buscarActualizacion"); return pintar();
      case "bv-fin": E.bv = null; E.bvCerrada = true; host.enviar("config", { bienvenida: true }); return pintar();
    }
  });
  document.addEventListener("input", (ev) => {
    const ds = ev.target.dataset || {}, p = P();
    if (ev.target.id === "buscar-pl" && E.pl) {
      E.pl.busqueda = ev.target.value;
      const pos = ev.target.selectionStart; pintar(); const c = document.getElementById("buscar-pl"); c?.focus(); c?.setSelectionRange?.(pos, pos);
      return;
    }
    if (!p) return;
    if (ds.encuadre != null) { p.encuadre.x = Number(ev.target.value); return ajustarPantalla(); }
    if (ds.subPosicion != null) { p.subtitulos.posicion = Number(ev.target.value); return actualizarCapas(); }
    if (ds.musicaVolumen != null && p.musica) { p.musica.volumen = Math.round(Number(ev.target.value) * 100) / 100; const o = $("#musica-vol"); if (o) o.textContent = Math.round(p.musica.volumen * 100) + " %"; return; }
    if (ev.target.id === "pedido-ia") E.ia.texto = ev.target.value;
    if (ds.huecoDesde != null) {
      // Mientras se arrastra solo se mueve el cuadro del clip; al soltar se vuelve a armar el video (change).
      const k = ds.huecoDesde, t = Number(ev.target.value), o = document.getElementById("desde-" + k), m = document.querySelector(`[data-mini="${k}"]`);
      if (o) o.innerHTML = T("desde {t}", { t: esc(relojFino(t)) });
      if (m) { m.dataset.desde = t; try { m.currentTime = t + 0.05; } catch {} }
      return;
    }
    if (ev.target.id === "buscar-fx" || (ev.target.id === "buscar-cat" && E.catalogo)) {
      // Se repinta al escribir: el foco y el cursor vuelven al mismo campo (pintar() recuerda el elemento activo).
      if (ev.target.id === "buscar-fx") E.fx.busqueda = ev.target.value; else E.catalogo.busqueda = ev.target.value;
      const pos = ev.target.selectionStart; pintar(); const c = document.getElementById(ev.target.id); c?.setSelectionRange?.(pos, pos);
    }
    if ((ev.target.id === "editar-palabra" || ev.target.id === "editar-sub") && E.editar) {
      E.editar.valor = ev.target.value;
      if (ev.target.id === "editar-palabra") ev.target.size = Math.max(4, [...ev.target.value].length + 2);
    }
  });
  // Salir del campo (tocar en otro lado) guarda la corrección; si el campo desapareció porque se repintó, no.
  document.addEventListener("focusout", (ev) => {
    if ((ev.target.id === "editar-palabra" || ev.target.id === "editar-sub") && E.editar && ev.target.isConnected) {
      setTimeout(() => { if (E.editar && !document.activeElement?.matches?.("#editar-palabra, #editar-sub")) terminarEdicion(true); }, 0);
    }
  });
  document.addEventListener("change", async (ev) => {
    const ds = ev.target.dataset || {}, p = P();
    if (ds.encuadre != null || ds.subPosicion != null || (ds.musicaVolumen != null && p?.musica)) return guardar(p);
    if (ds.relleno != null) { p.relleno = ev.target.value; return guardar(p); }
    if (ds.subActivos != null) { p.subtitulos.activos = ev.target.checked; return guardar(p); }
    if (ds.subPalabras != null) { p.subtitulos.palabras_por_linea = Number(ev.target.value); return guardar(p); }
    if (ds.huecoDesde != null && p?.plantilla) {
      E.armando = { carpeta: E.sel, k: Number(ds.huecoDesde) };
      host.enviar("ajustarHueco", { carpeta: E.sel, hueco: Number(ds.huecoDesde), desde: Math.round(Number(ev.target.value) * 1000) / 1000 });
      return pintar();
    }
    if (ds.config) {
      E.config[ds.config] = ev.target.value; host.enviar("config", { [ds.config]: ev.target.value });
      if (ds.config === "idioma_ui") await cargarIdioma(ev.target.value);
      return pintar();
    }
  });
  document.addEventListener("keydown", (ev) => {
    const escribiendo = ev.target.closest?.("input, textarea, select, [contenteditable]");
    if (E.bv !== null) return;  // con la bienvenida abierta, los atajos del editor no corren detrás
    if (ev.target.id === "editar-palabra" || ev.target.id === "editar-sub") {
      if (ev.key === "Enter") { ev.preventDefault(); terminarEdicion(true); }
      else if (ev.key === "Escape") { ev.preventDefault(); terminarEdicion(false); }
      return;
    }
    if (ev.target.id === "vocab-nueva" && ev.key === "Enter") { ev.preventDefault(); return $("[data-accion=vocab-agregar]")?.click(); }
    if (ev.key === "Escape") { if (E.exportar?.paso !== "exportando") E.exportar = null; E.ajustes = false; E.catalogo = null; if (E.pl?.ver) { E.pl.ver = null; return pintar(); } if (!E.pl?.armando) E.pl = null; E.seleccion = null; E.lt.sel = null; E.sugerencia = null; return pintar(); }
    if (teclaLinea(ev)) return;
    if (escribiendo) { if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey) && ev.target.id === "pedido-ia") $("[data-accion=pedir-ia]")?.click(); return; }
    if ((ev.key === "Backspace" || ev.key === "Delete") && E.seleccion) { ev.preventDefault(); return cortarSeleccion(); }
    if (ev.key === "Enter" && E.seleccion && P()) { ev.preventDefault(); return empezarEdicion(E.seleccion[0], E.seleccion[1], "texto"); }
    if (ev.key === " " && P()) { ev.preventDefault(); return $("[data-accion=play]")?.click(); }
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "z" && P()) { ev.preventDefault(); host.enviar("deshacer", { carpeta: E.sel }); }
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "b" && P()) { ev.preventDefault(); dividir(); }
  });
  // Línea de tiempo: arrastrar bordes (mouse, toque o lápiz con los mismos eventos de puntero), mover el cabezal y teclado.
  let arrastre = null;
  document.addEventListener("pointerdown", (ev) => {
    const vista = ev.target.closest?.("#lt-vista"), p = P();
    if (!vista || !p || ev.button > 0) return;
    const v = $("#video"), h = ev.target.closest(".borde");
    if (h) {
      const bl = h.closest(".bloque"), lista = bl.dataset.lt, k = Number(bl.dataset.k), borde = h.dataset.borde;
      ev.preventDefault();
      h.focus({ preventScroll: true });
      try { h.setPointerCapture(ev.pointerId); } catch {}
      if (v && !v.paused) v.pause();
      arrastre = { tipo: "borde", lista, k, borde, antes: p[lista][k][borde], cabezal: v?.currentTime, id: ev.pointerId };
      return seleccionar(lista, k);
    }
    const bl = ev.target.closest(".bloque[data-lt]");
    if (bl) {
      seleccionar(bl.dataset.lt, Number(bl.dataset.k)); irA(tiempoEn(ev.clientX));
      if (bl.dataset.lt === "tramos" && E.pestana === "efectos") { E.seleccion = null; pintar(); }  // el panel muestra a qué se aplica
      return;
    }
    if (ev.target.closest("button")) return;
    if (E.lt.sel) seleccionar(null);
    // Arrastrar en la regla (o en una pista con el mouse) mueve el cabezal; con el dedo, las pistas se desplazan.
    arrastre = { tipo: "cabezal", id: ev.pointerId };
    if (ev.pointerType === "mouse" || ev.target.closest("#linea")) { try { vista.setPointerCapture(ev.pointerId); } catch {} }
    irA(tiempoEn(ev.clientX));
  });
  document.addEventListener("pointermove", (ev) => {
    if (!arrastre || ev.pointerId !== arrastre.id) return;
    const p = P(); if (!p) return;
    if (arrastre.tipo === "cabezal") return irA(tiempoEn(ev.clientX));
    const t = ev.altKey ? tiempoEn(ev.clientX) : iman(p, tiempoEn(ev.clientX), arrastre.cabezal);
    const valor = moverBorde(p[arrastre.lista], arrastre.k, arrastre.borde, t, p.fuente.duracion);
    pintarBloque(arrastre.lista, arrastre.k);
    irA(valor);  // se ve el cuadro justo en el borde
  });
  const soltarArrastre = (ev) => {
    if (!arrastre || ev.pointerId !== arrastre.id) return;
    const a = arrastre, p = P();
    arrastre = null;
    if (a.tipo === "borde" && p && p[a.lista][a.k][a.borde] !== a.antes) guardar(p);
  };
  document.addEventListener("pointerup", soltarArrastre);
  document.addEventListener("pointercancel", soltarArrastre);
  document.addEventListener("focusin", (ev) => {
    const bl = ev.target.closest?.(".borde")?.closest(".bloque");
    if (bl && !(E.lt.sel?.lista === bl.dataset.lt && E.lt.sel.k === Number(bl.dataset.k))) seleccionar(bl.dataset.lt, Number(bl.dataset.k));
  });
  document.addEventListener("wheel", (ev) => {  // Ctrl/⌘ + rueda (o pellizcar en el trackpad): zoom de la línea de tiempo
    if (!(ev.ctrlKey || ev.metaKey) || !ev.target.closest?.("#lt-vista") || !P()) return;
    ev.preventDefault();
    cambiarZoom(ev.deltaY < 0 ? 1 : -1, tiempoEn(ev.clientX));
  }, { passive: false });
  /** Teclado en la línea de tiempo. Bordes: flechas 0,1 s (Mayús 1 s, Alt 0,01 s), Re Pág/Av Pág 1 s, Inicio/Fin hasta el límite,
   *  Suprimir quita el tramo. Regla: flechas mueven el cabezal 1 s (Mayús 5 s). Devuelve true si usó la tecla. */
  function teclaLinea(ev) {
    const p = P(); if (!p) return false;
    const dur = p.fuente.duracion, h = ev.target.closest?.(".borde");
    if (ev.target.id === "linea") {
      const t = $("#video")?.currentTime || 0, paso = ev.shiftKey ? 5 : 1;
      const nuevo = { ArrowLeft: t - paso, ArrowDown: t - paso, ArrowRight: t + paso, ArrowUp: t + paso, Home: 0, End: dur }[ev.key];
      if (nuevo == null) return false;
      ev.preventDefault(); irA(nuevo); return true;
    }
    if (!h) return false;
    const bl = h.closest(".bloque"), lista = bl.dataset.lt, k = Number(bl.dataset.k), b = h.dataset.borde;
    if (ev.key === "Delete" || ev.key === "Backspace") { ev.preventDefault(); quitarBloque(lista, k); return true; }
    const actual = p[lista][k][b], paso = ev.shiftKey ? 1 : ev.altKey ? 0.01 : 0.1, [lo, hi] = limitesBorde(p[lista], k, b, dur);
    const nuevo = { ArrowLeft: actual - paso, ArrowDown: actual - paso, ArrowRight: actual + paso, ArrowUp: actual + paso,
      PageDown: actual - 1, PageUp: actual + 1, Home: lo, End: hi }[ev.key];
    if (nuevo == null) return false;
    ev.preventDefault();
    const valor = moverBorde(p[lista], k, b, nuevo, dur);
    pintarBloque(lista, k); irA(valor);
    clearTimeout(guardarLuego);
    const carpeta = E.sel;
    guardarLuego = setTimeout(() => { if (E.sel === carpeta) guardar(p); else host.enviar("guardarProyecto", { carpeta, proyecto: p }); }, 700);
    return true;
  }

  for (const tipo of ["dragover", "dragleave", "drop"]) {
    document.addEventListener(tipo, (ev) => {
      if (!ev.dataTransfer?.types?.includes("Files")) return;
      ev.preventDefault();
      if (E.bv === 0) return;  // mientras se elige el idioma no se importa nada
      const encima = tipo === "dragover";
      if (E.soltar !== encima) { E.soltar = encima; const z = $("[data-soltar]"); if (z) z.classList.toggle("encima", encima); }
      if (tipo === "drop") host.enviar("soltarVideo", { nombres: [...ev.dataTransfer.files].map((f) => f.name) });
    });
  }

  // ───────────── Lo que manda la app ─────────────
  window.Corta = {
    async estado(e) {
      Object.assign(E, { proyectos: e.proyectos || [], estilos: e.estilos || [], config: e.config || {}, ias: e.ias || [], modelos: e.modelos || { lista: [] },
        vocabulario: e.vocabulario || { reemplazos: [], palabras: [] }, efectos: e.efectos || [], plantillas: e.plantillas || [],
        version: e.version || "", carpeta: e.carpeta || "", progreso: e.progreso || {}, actualizacion: e.actualizacion || { hay: false } });
      if (e.seleccionar) E.sel = e.seleccionar;
      if (E.sel && !E.proyectos.some((x) => x.carpeta === E.sel)) E.sel = null;
      if (!E.sel && E.proyectos.length) E.sel = E.proyectos[0].carpeta;
      if (!E.config.bienvenida && E.bv === null && !E.bvCerrada) E.bv = 0;
      await cargarIdioma();
      if (e.aviso) toast(e.aviso);
      pintar();
    },
    proyectoActualizado(r) {
      const x = E.proyectos.find((y) => y.carpeta === r.carpeta);
      if (x) x.proyecto = r.proyecto; else E.proyectos.unshift({ carpeta: r.carpeta, proyecto: r.proyecto });
      if (r.seleccionar) E.sel = r.carpeta;
      if (r.aviso) toast(r.aviso);
      pintar();
    },
    progreso(r) { if (r.listo) delete E.progreso[r.carpeta]; else E.progreso[r.carpeta] = r; pintar(); },
    limpiado(r) { E.limpiando = false; if (r.ok) { E.ultimoAhorro = r.ahorro; window.Corta.proyectoActualizado({ carpeta: E.sel, proyecto: r.proyecto }); } else { toast(r.error || "No se pudo limpiar"); pintar(); } },
    iaRespondio(r) {
      const pedido = E.ia.texto;
      // Lo que se aplicó queda en el proyecto (cambios_ia); aquí solo lo que no cambió nada (un error o «eso no se puede»).
      const nota = r.ok && r.cambio ? [] : [{ pedido, carpeta: E.sel, ok: r.ok, resumen: r.resumen || tr("Listo."), error: r.ok ? "" : r.error }];
      E.ia = { texto: r.ok ? "" : pedido, enviando: false, historial: [...nota, ...E.ia.historial].slice(0, 12) };
      if (r.ok && r.proyecto) window.Corta.proyectoActualizado({ carpeta: E.sel, proyecto: r.proyecto }); else pintar();
    },
    shortsListos(r) { E.buscandoShorts = false; E.shorts = r.ok ? { lista: r.shorts } : { error: r.error }; pintar(); },
    exportarProgreso(r) { if (E.exportar) { E.exportar.pct = r.pct; const b = $(".dialogo .barra-prog i"); if (b) { b.style.width = r.pct + "%"; $(".dialogo .nota").textContent = r.pct + " %"; } else pintar(); } },
    exportado(r) { E.exportar = r.ok ? { paso: "listo", ...r } : { paso: "error", error: r.error }; pintar(); },
    iaProbada(r) { delete E.probando[r.id]; E.resultadoIA[r.id] = r; if (r.ok) { E.config.ia = r.id; toast("Lista para usar"); } pintar(); },
    modeloProgreso(r) { E.descarga = { id: r.id, pct: r.pct }; pintar(); },
    modeloListo(r) { E.descarga = null; if (r.ok) { const m = E.modelos.lista.find((x) => x.id === r.id); if (m) m.listo = true; E.config.modelo = r.id; toast("Descargado"); } else toast(r.error || "No se pudo descargar"); pintar(); },
    /** Respuesta a elegirMusica: {ok, carpeta, proyecto} o {ok: false, error} ({ok: false} sin error si la persona canceló). */
    musicaElegida(r) {
      if (r.ok) return window.Corta.proyectoActualizado({ carpeta: r.carpeta, proyecto: r.proyecto, aviso: r.aviso || "Música lista" });
      if (r.error) toast(r.error);
    },
    /** Avance de una actualización: {paso: 1–3 o "error", texto (ya traducido por la app), pct?}. */
    actualizacionProgreso(r) { E.act = r; if (r.paso === "error") toast(r.texto || "No se pudo actualizar"); pintar(); },
    actualizacionRevisada(r) { E.buscando = r.hay ? null : r.sinConexion ? "sinConexion" : "alDia"; if (r.hay) E.actualizacion = r; pintar(); },
    /** Respuesta a `catalogoEfectos`: {ok, efectos} (ya validados por bin/efectos.py) o {ok: false, error}. */
    catalogoListo(r) {
      if (!E.catalogo) return;
      Object.assign(E.catalogo, r.ok ? { estado: "listo", efectos: r.efectos || [] } : { estado: "error", error: r.error });
      pintar();
    },
    /** Respuesta a `descargarEfecto`: {ok, efecto} o {ok: false, id, error}. */
    efectoDescargado(r) {
      if (E.catalogo) delete E.catalogo.bajando[r.ok ? r.efecto.id : r.id];
      if (E.pl) delete E.pl.bajando[r.ok ? r.efecto.id : r.id];
      if (r.ok) { E.efectos = [...E.efectos.filter((x) => x.id !== r.efecto.id), r.efecto]; toast(Tp("«{x}» quedó en tus efectos", { x: nombreFx(r.efecto) }), true); }
      else toast(r.error || "No pude descargarlo");
      pintar();
    },
    /** Respuesta a `elegirClips`, `ajustarHueco` y `cambiarClip`: {ok, carpeta, proyecto, faltan?, usados?} o {ok: false, error}
     *  ({ok: false} sin error si la persona canceló). Un video recién armado se abre en la pestaña Clips. */
    plantillaArmada(r) {
      const nuevo = E.pl?.armando;
      E.armando = null;
      if (E.pl) E.pl.armando = false;
      if (!r.ok) { if (r.error) toast(r.error); return pintar(); }
      if (nuevo) { E.pl = null; E.pestana = "clips"; E.seleccion = null; E.lt.sel = null; }
      const faltan = (r.faltan || []).length;
      window.Corta.proyectoActualizado({ carpeta: r.carpeta, proyecto: r.proyecto, seleccionar: !!nuevo });
      if (nuevo) toast(Tp(faltan ? "Listo. Faltan {n} efectos de la comunidad: puedes ponerlos después." : "Listo: tu video está armado", { n: faltan }), true);
    },
    /** Respuesta a `catalogoPlantillas`: {ok, plantillas, efectos} (ya validados por bin/) o {ok: false, error}. */
    catalogoPlantillasListo(r) {
      if (!E.pl) return;
      E.pl.catalogo = r.ok ? { estado: "listo", plantillas: r.plantillas || [], efectos: r.efectos || [] } : { estado: "error", error: r.error, plantillas: [], efectos: [] };
      const id = E.pl.pendiente; E.pl.pendiente = null;
      if (id) { if (r.ok) host.enviar("descargarEfecto", { id }); else delete E.pl.bajando[id]; }
      pintar();
    },
    /** Respuesta a `descargarPlantilla`: {ok, plantilla} o {ok: false, id, error}. */
    plantillaDescargada(r) {
      if (E.pl) delete E.pl.bajando[r.ok ? r.plantilla.id : r.id];
      if (r.ok) { E.plantillas = [...E.plantillas.filter((x) => x.id !== r.plantilla.id), r.plantilla]; toast(Tp("«{x}» quedó en tus plantillas", { x: nombreFx(r.plantilla) }), true); }
      else toast(r.error || "No pude descargarla");
      pintar();
    },
    /** Respuesta a `vocabulario`: {ok, vocabulario} o {ok: false, error}. */
    vocabularioActualizado(r) { if (r.ok) E.vocabulario = r.vocabulario; else toast(r.error || "No pude guardar."); pintar(); },
    _probar(f) { f(E); pintar(); },
    _pruebas: { conservados, aSalida, duracionFinal, cortarPalabras, restaurar, cortesPorPalabras, lineas, unir, limitesBorde, moverBorde,
      tramosVoz, cuantoBaja, textoQueCabe, normalizar, intervalosSalida, uniones, llenar, aplicarPlantilla, iniciosHuecos, segmentosZoom, segmentosCapa, valorEn, cssColor, tramosEdicion, partes, editarPalabras, reemplazarTodo, quitarCambioIA, musica: () => musicaAudio, ganancia: () => gananciaMusica, demoConfig: () => DEMO?.config, demoCatalogoPl: () => clonar(DEMO?.catalogo_plantillas || []) },
  };

  // ───────────── Vista previa en el navegador (datos ficticios de demo.json) ─────────────
  let DEMO = null;
  const clonar = (o) => JSON.parse(JSON.stringify(o));
  const demoProy = (c) => DEMO.proyectos.find((x) => x.carpeta === c);
  const historial = {};
  function simular(accion, d) {
    if (!DEMO) return;
    const A = window.Corta, luego = (ms, f) => setTimeout(f, ms);
    switch (accion) {
      case "listo": return A.estado(clonar(DEMO));
      case "config": Object.assign(DEMO.config, d); return;
      case "guardarProyecto": { const x = demoProy(d.carpeta); (historial[d.carpeta] ||= []).push(clonar(x.proyecto)); x.proyecto = clonar(d.proyecto); return; }
      case "deshacer": { const h = historial[d.carpeta]; if (!h?.length) return toast("No hay nada que deshacer"); const x = demoProy(d.carpeta); x.proyecto = h.pop(); return A.proyectoActualizado({ carpeta: d.carpeta, proyecto: clonar(x.proyecto), aviso: "Deshecho" }); }
      case "limpiar": return luego(600, () => {
        const x = demoProy(d.carpeta), p = x.proyecto, antes = duracionFinal(p);
        (historial[d.carpeta] ||= []).push(clonar(p));
        p.cortes = p.cortes.filter((c) => c.motivo !== "silencio" && c.motivo !== "muletilla").concat(cortesPorPalabras(p.palabras, d.silencio, d.muletillas, p.fuente.duracion));
        A.limpiado({ ok: true, ahorro: Math.round((antes - duracionFinal(p)) * 10) / 10, proyecto: clonar(p) });
      });
      case "pedirIA": return luego(1100, () => {
        const x = demoProy(d.carpeta), p = x.proyecto, t = d.texto.toLowerCase(), antes = clonar(p), origen = "ia-" + Date.now().toString(36);
        (historial[d.carpeta] ||= []).push(clonar(p));
        let resumen = tr("En la vista previa la IA es de mentira: en la app, tu IA entiende cualquier pedido.");
        const idx = (palabra) => p.palabras.findIndex((w) => w.t.toLowerCase().startsWith(palabra));
        if (/zoom/.test(t)) {
          for (const [a, b] of [["ahorrar", "hora"], ["primero", "silencios."], ["listo", "publicar."]]) p.zooms.push({ i: p.palabras[idx(a)].i, f: p.palabras[idx(b)].f, escala: 1.3, origen });
          resumen = tr("Puse 3 zooms en los momentos clave.");
        }
        else if (/t[ií]tulo|title/.test(t)) { p.textos.push({ i: p.palabras[idx("hola")].i, f: p.palabras[idx("ana")].f + 1.2, texto: tr("Edita en 1 minuto"), y: 0.16, origen }); resumen = tr("Agregué el título «Edita en 1 minuto» al inicio."); }
        else if (/una palabra|one word/.test(t)) { p.subtitulos.estilo = "palabra"; p.subtitulos.palabras_por_linea = 1; resumen = tr("Cambié los subtítulos a una palabra a la vez."); }
        else if (/cuadrad|square|instagram/.test(t)) { p.lienzo = "1:1"; resumen = tr("Lo dejé cuadrado (1:1) para Instagram."); }
        else if (/filtro|c[aá]lido|warm|filter/.test(t)) {
          const ef = (DEMO.efectos || []).find((x) => x.id === "calido");
          if (ef) { (p.efectos ||= []).push({ efecto: "calido", pasos: clonar(ef.pasos), origen }); resumen = tr("Le puse el filtro «Cálido» a todo el video."); }
        }
        else if (/equivoc|mistake|corta|cut/.test(t)) { cortarPalabras(p, idx("mmm"), idx("cómo"), "ia"); p.cortes[p.cortes.length - 1].origen = origen; resumen = tr("Corté «Mmm… te muestro cómo», que sobraba."); }
        // Igual que bin/editar_ia.py: lo agregado lleva `origen` y queda anotado en cambios_ia para poder quitarlo.
        const agregados = {};
        for (const l of ["zooms", "textos", "cortes", "efectos"]) { const s = (p[l] || []).filter((o) => o.origen === origen); if (s.length) agregados[l] = clonar(s); }
        const ajustes = ["lienzo", "subtitulos.estilo", "subtitulos.activos", "subtitulos.palabras_por_linea"].filter((c) => !igualJSON(leerCampo(antes, c), leerCampo(p, c)))
          .map((c) => ({ campo: c, antes: leerCampo(antes, c), despues: leerCampo(p, c) }));
        if (!Object.keys(agregados).length && !ajustes.length) return A.iaRespondio({ ok: true, aplicadas: 0, resumen, proyecto: clonar(p) });
        p.cambios_ia = [...(p.cambios_ia || []), { id: origen, estado: "aplicado", pedido: d.texto.slice(0, 200), resumen, agregados, ...(ajustes.length ? { ajustes } : {}) }].slice(-20);
        A.iaRespondio({ ok: true, aplicadas: 1, resumen, cambio: origen, proyecto: clonar(p) });
      });
      case "buscarShorts": return luego(1400, () => {
        const p = demoProy(d.carpeta).proyecto, w = p.palabras, k = (s) => w.findIndex((x) => x.t.toLowerCase().startsWith(s));
        A.shortsListos({ ok: true, shorts: [
          { i: w[k("¿sabías")].i, f: w[k("publicar")].f, duracion: w[k("publicar")].f - w[k("¿sabías")].i, titulo: tr("Ahorra una hora editando tus videos"), gancho: "¿Sabías que puedes ahorrar una hora cada semana editando tus videos?", por_que: tr("Abre con una pregunta y una promesa concreta.") },
          { i: w[k("primero")].i, f: w[k("publicar")].f, duracion: w[k("publicar")].f - w[k("primero")].i, titulo: tr("Dos pasos y tu Short está listo"), gancho: "Primero, sacas los silencios.", por_que: tr("Pasos cortos y claros, ideal para guardar.") }] });
      });
      case "crearShort": return luego(500, () => {
        const x = demoProy(d.carpeta), q = clonar(x.proyecto), carpeta = `${d.carpeta} — ${d.titulo}`;
        q.titulo = d.titulo; q.cortes = q.cortes.filter((c) => c.f > d.desde && c.i < d.hasta);
        if (d.desde > 0.05) q.cortes.push({ i: 0, f: r3(d.desde), motivo: "fuera" });
        if (d.hasta < q.fuente.duracion - 0.05) q.cortes.push({ i: r3(d.hasta), f: q.fuente.duracion, motivo: "fuera" });
        DEMO.proyectos.unshift({ carpeta, proyecto: q });
        E.shorts = null;
        A.proyectoActualizado({ carpeta, proyecto: clonar(q), seleccionar: true, aviso: "Short creado" });
      });
      case "exportar": { let pct = 0; const iv = setInterval(() => { pct += 9; if (pct >= 100) { clearInterval(iv); A.exportado({ ok: true, duracion: duracionFinal(demoProy(d.carpeta).proyecto), archivo: "exportado-9x16.mp4" }); } else A.exportarProgreso({ pct }); }, 220); return; }
      case "elegirMusica": return luego(300, () => {  // la demo usa una música hecha con código (herramientas/generar_demo.py)
        const x = demoProy(d.carpeta);
        (historial[d.carpeta] ||= []).push(clonar(x.proyecto));
        x.proyecto.musica = { archivo: "demo/musica-demo.mp3", volumen: x.proyecto.musica?.volumen ?? 0.15 };
        A.musicaElegida({ ok: true, carpeta: d.carpeta, proyecto: clonar(x.proyecto), aviso: "En la vista previa suena una música de prueba hecha por Corta" });
      });
      case "elegirVideo": case "soltarVideo": return toast("En la app, aquí eliges un video de tu computador");
      case "transcribir": return toast("En la app, aquí se transcribe el video");
      case "probarIA": return luego(500, () => { DEMO.config.ia = d.id; A.iaProbada({ id: d.id, ok: true }); });
      case "descargarModelo": { let p = 0; const iv = setInterval(() => { p += 0.25; A.modeloProgreso({ id: d.id, pct: Math.min(p, 1) }); if (p >= 1) { clearInterval(iv); A.modeloListo({ id: d.id, ok: true }); } }, 300); return; }
      case "vocabulario": return luego(150, () => {  // en la app queda en ~/Corta/vocabulario.json (bin/vocabulario.py)
        const v = DEMO.vocabulario ||= { formato: 1, reemplazos: [], palabras: [] }, clave = (t) => String(t).split(/\s+/).map(normalizar).filter(Boolean).join(" ");
        if (d.accion === "agregar") { v.reemplazos = [{ de: d.de, a: d.a }, ...v.reemplazos.filter((r) => clave(r.de) !== clave(d.de))]; }
        if (d.accion === "quitar") v.reemplazos = v.reemplazos.filter((r) => clave(r.de) !== clave(d.de));
        if (d.accion === "palabra") v.palabras = [d.palabra, ...v.palabras.filter((x) => normalizar(x) !== normalizar(d.palabra))];
        if (d.accion === "quitar_palabra") v.palabras = v.palabras.filter((x) => normalizar(x) !== normalizar(d.palabra));
        A.vocabularioActualizado({ ok: true, vocabulario: clonar(v) });
      });
      case "elegirClips": return luego(900, () => {  // en la app: eliges tus clips y bin/plantillas.py arma el video con ffmpeg
        const pl = (DEMO.plantillas || []).find((x) => x.id === d.plantilla);
        if (!pl) return A.plantillaArmada({ ok: false, error: tr("No encontré esa plantilla.") });
        const lugar = llenar(pl.huecos, CLIPS_DEMO), total = iniciosHuecos(pl.huecos).at(-1);
        const huecos = pl.huecos.map((h, k) => { const c = CLIPS_DEMO[lugar[k].clip]; return { archivo: c.archivo, tipo: c.tipo, desde: lugar[k].desde, dur: h.dur, duracion: c.duracion }; });
        const a = aplicarPlantilla(pl, huecos.map((h) => h.tipo), E.idioma, Object.fromEntries((DEMO.efectos || []).map((e) => [e.id, e.pasos])), (DEMO.estilos || []).map((e) => e.id));
        const titulo = nombreFx(pl);
        let carpeta = `~/Corta/2026-10-28 ${titulo}`, n = 2;
        while (demoProy(carpeta)) carpeta = `~/Corta/2026-10-28 ${titulo} (${n++})`;
        // En la vista previa el video armado es el de Ana (en la app, tus clips uno detrás de otro).
        const p = { formato: 1, titulo, fuente: { archivo: "demo/ana.mp4", duracion: total, ancho: 1280, alto: 720 }, lienzo: a.lienzo, relleno: "recorte",
          encuadre: { x: 0.45, y: 0.5 }, palabras: [], cortes: [], subtitulos: { activos: true, estilo: "pop", palabras_por_linea: 3, posicion: 0.7, ...(a.subtitulos || {}) },
          zooms: [], textos: a.textos, efectos: a.efectos, divisiones: a.divisiones, musica: null, plantilla: { id: pl.id, huecos }, creado: "2026-10-28T10:00:00" };
        DEMO.proyectos.unshift({ carpeta, proyecto: p });
        A.plantillaArmada({ ok: true, carpeta, proyecto: clonar(p), faltan: a.faltan, usados: CLIPS_DEMO.length });
      });
      case "ajustarHueco": return luego(500, () => {
        const x = demoProy(d.carpeta), h = x?.proyecto.plantilla?.huecos[d.hueco];
        if (!h) return A.plantillaArmada({ ok: false, error: tr("Ese hueco no existe.") });
        (historial[d.carpeta] ||= []).push(clonar(x.proyecto));
        h.desde = r3(Math.max(0, Math.min(d.desde, (h.duracion || 0) - h.dur)));
        A.plantillaArmada({ ok: true, carpeta: d.carpeta, proyecto: clonar(x.proyecto) });
      });
      case "cambiarClip": toast("En la app, aquí eliges otro clip o foto"); return luego(300, () => A.plantillaArmada({ ok: false }));
      case "catalogoPlantillas": return luego(500, () => A.catalogoPlantillasListo({ ok: true, plantillas: clonar(DEMO.catalogo_plantillas || []), efectos: clonar(DEMO.catalogo || []) }));
      case "descargarPlantilla": return luego(600, () => {  // en la app: Swift la baja de raw.githubusercontent.com y bin/plantillas.py la valida
        const x = (DEMO.catalogo_plantillas || []).find((y) => y.id === d.id);
        if (!x) return A.plantillaDescargada({ ok: false, id: d.id, error: tr("Esa plantilla no es válida.") });
        const plantilla = { ...Object.fromEntries(Object.entries(x).filter(([k]) => !["archivo", "sha256", "bytes"].includes(k))), origen: "descargada" };
        DEMO.plantillas = [...(DEMO.plantillas || []).filter((y) => y.id !== d.id), plantilla];
        A.plantillaDescargada({ ok: true, plantilla: clonar(plantilla) });
      });
      case "catalogoEfectos": return luego(500, () => A.catalogoListo({ ok: true, efectos: clonar(DEMO.catalogo || []) }));
      case "descargarEfecto": return luego(600, () => {  // en la app: Swift lo baja de raw.githubusercontent.com y bin/efectos.py lo valida
        const ef = (DEMO.catalogo || []).find((x) => x.id === d.id);
        if (!ef) return A.efectoDescargado({ ok: false, id: d.id, error: tr("Ese efecto no es válido.") });
        const efecto = { ...Object.fromEntries(Object.entries(ef).filter(([k]) => !["archivo", "sha256", "bytes"].includes(k))), origen: "descargado" };
        DEMO.efectos = [...(DEMO.efectos || []).filter((x) => x.id !== d.id), efecto];
        A.efectoDescargado({ ok: true, efecto: clonar(efecto) });
      });
      case "abrirEnlace": return window.open(d.url, "_blank", "noopener");
      case "abrirCarpeta": return toast("En la app, aquí se abre la carpeta");
      case "buscarActualizacion": return luego(500, () => A.actualizacionRevisada({ hay: false }));
      case "actualizar": return luego(400, () => A.actualizacionProgreso({ paso: "error", texto: tr("En la vista previa no hay nada que actualizar.") }));
    }
  }

  /** Lo que «elige» la vista previa al usar una plantilla: el video de Ana y dos fotos dibujadas (ui/demo/, ficticias). */
  const CLIPS_DEMO = [{ archivo: "demo/ana.mp4", tipo: "video", duracion: 30.233 }, { archivo: "demo/foto-1.jpg", tipo: "foto", duracion: null },
    { archivo: "demo/foto-2.jpg", tipo: "foto", duracion: null }];
  const LOGO = `<svg class="logo" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#111214"/><path d="M22 15.5 49 32 22 48.5z" fill="#c6f432"/><path d="M14 44 50 20" stroke="#111214" stroke-width="7" stroke-linecap="round"/><circle cx="14" cy="44" r="4.6" fill="none" stroke="#f4f4f0" stroke-width="2.6"/><circle cx="50" cy="20" r="4.6" fill="none" stroke="#f4f4f0" stroke-width="2.6"/></svg>`;

  async function iniciar() {
    if (HOST === "web") {
      try { DEMO = await (await fetch("demo.json")).json(); } catch { DEMO = { proyectos: [], estilos: [], config: {}, ias: [] }; }
      const q = new URLSearchParams(location.search);
      DEMO.config.bienvenida = !q.has("bienvenida");
      if (q.has("vacio")) DEMO.proyectos = [];
    }
    host.enviar("listo");
    requestAnimationFrame(bucle);
  }
  iniciar();
})();
