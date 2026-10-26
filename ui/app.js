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
  };
  const ENLACES = { sitio: "https://corta-app.github.io/corta/", codigo: "https://github.com/corta-app/corta",
    comunidad: "https://github.com/corta-app/corta/discussions", guiaIA: "https://corta-app.github.io/corta/ia.html" };
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
  function lineas(palabras, porLinea) {
    const grupos = []; let actual = [];
    palabras.forEach((w, k) => {
      actual.push(w);
      const sig = palabras[k + 1];
      if (actual.length >= porLinea || /[.!?…,;:]$/.test(w.t) || (sig && sig.i - w.f > 0.6) || !sig) { grupos.push(actual); actual = []; }
    });
    return grupos;
  }

  // ───────────── Utilidades ─────────────
  const proy = () => E.proyectos.find((x) => x.carpeta === E.sel);
  const P = () => proy()?.proyecto;
  const reloj = (s) => { s = Math.max(0, s || 0); const m = Math.floor(s / 60), x = Math.floor(s % 60); return `${m}:${String(x).padStart(2, "0")}`; };
  const segundos = (s) => (Math.round(s * 10) / 10).toLocaleString(E.idioma === "es" ? "es-CL" : "en-US");
  const estilo = () => E.estilos.find((s) => s.id === P()?.subtitulos.estilo) || E.estilos[0];
  const nombreIA = () => E.ias.find((i) => i.id === E.config.ia)?.nombre || tr("tu IA");
  let avisosPendientes = [];  // avisos que llegan mientras la persona elige el idioma: se muestran después, ya traducidos
  function toast(texto) {
    if (E.bv === 0) { avisosPendientes.push(texto); return; }
    const t = $("#toast"); t.textContent = tr(texto); t.classList.add("visible");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("visible"), 2200);
  }
  let guardarLuego = null;  // al mover un borde con el teclado se guarda una vez, al soltar las flechas
  /** Guarda el proyecto (la app lo valida y deja respaldo para deshacer). */
  function guardar(p, aviso) {
    clearTimeout(guardarLuego);
    host.enviar("guardarProyecto", { carpeta: E.sel, proyecto: p });
    if (aviso) toast(aviso);
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
    raiz.innerHTML = E.bv === 0 ? dialogos() : `<div class="app">${barra()}${lateral()}${principal()}</div>${dialogos()}`;
    traducirDOM(raiz);
    if (E.bv === 0 && !document.activeElement?.closest?.(".dialogo")) $(".opcion-idioma.principal")?.focus();
    const cp = $(".cuerpo-panel"); if (cp) cp.scrollTop = scroll;
    const vl = $("#lt-vista"); if (vl) vl.scrollLeft = scrollLT;
    const nuevo = $("#video");
    if (nuevo && viejo && viejo.getAttribute("src") === nuevo.getAttribute("src")) nuevo.replaceWith(viejo);
    if ($("#video")) ajustarPantalla();  // el tamaño sale del proyecto, no hace falta esperar a que cargue el video
    if (activo) document.getElementById(activo)?.focus();
  }

  function barra() {
    const p = P();
    return `<header class="barra"><span class="marca">${LOGO}<span>Corta</span></span>
      <span class="titulo-proy" data-sin-traducir>${p ? `<b>${esc(p.titulo)}</b>` : ""}</span>
      ${p && p.palabras ? `<div class="segmentado" role="group" aria-label="Formato">${Object.keys(LIENZOS).map((l) =>
        `<button data-lienzo="${l}" aria-pressed="${p.lienzo === l}" data-sin-traducir>${l}</button>`).join("")}</div>
        <button class="icono" data-accion="deshacer" title="Deshacer" aria-label="Deshacer">↶</button>
        <button class="boton principal" data-accion="exportar">Exportar</button>` : ""}
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
    return `<aside class="lateral"><div class="caja"><button class="boton principal grande" data-accion="nuevo">＋ <span>Nuevo video</span></button></div>
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

  const PESTANAS = [["texto", "Texto"], ["subtitulos", "Subtítulos"], ["musica", "Música"], ["ia", "IA"], ["shorts", "Shorts"]];
  function panel() {
    const cuerpo = { texto: panelTexto, subtitulos: panelSubtitulos, musica: panelMusica, ia: panelIA, shorts: panelShorts }[E.pestana]();
    return `<div class="pestanas" role="tablist">${PESTANAS.map(([id, n]) => `<button class="pestana" role="tab" data-pestana="${id}" aria-selected="${E.pestana === id}">${n}</button>`).join("")}</div>
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
      const enSel = sel && k >= sel[0] && k <= sel[1];
      html += `<span class="w ${palabraCortada(p, w, cortes) ? "cortada" : ""} ${enSel ? "sel" : ""}" data-w="${k}">${esc(w.t)}</span> `;
    });
    const nSel = sel ? sel[1] - sel[0] + 1 : 0;
    const selCortada = sel && p.palabras.slice(sel[0], sel[1] + 1).every((w) => palabraCortada(p, w, cortes));
    return `<div class="tarjeta limpiar"><div class="txt"><b>Silencios y muletillas</b>
        <small>${E.ultimoAhorro != null ? frase("Listo: el video quedó **{s} s** más corto.", { s: esc(segundos(E.ultimoAhorro)) }) : "Saca las pausas largas y los «eh», «mmm» de una vez."}</small></div>
        <button class="boton ${E.ultimoAhorro == null ? "principal" : ""}" data-accion="limpiar" ${E.limpiando ? "disabled" : ""}>${E.limpiando ? "Limpiando…" : E.ultimoAhorro == null ? "Limpiar" : "Otra vez"}</button></div>
      ${nSel ? `<div class="acciones-sel">${frase(nSel === 1 ? "1 palabra elegida" : "{n} palabras elegidas", { n: nSel })}
        <button class="boton" data-accion="${selCortada ? "restaurar-sel" : "cortar-sel"}">${selCortada ? "Volver a poner" : "Cortar"}</button>
        <button class="boton sutil" data-accion="zoom-sel" title="Acercar la imagen mientras se dicen">🔍 <span>Zoom</span></button></div>`
        : `<p class="nota" style="margin:0 0 10px">Toca una palabra para ir a ese momento. Elige varias (toca la primera y la última con Mayús) y presiona Borrar para sacarlas del video.</p>`}
      <div class="transcripcion" data-sin-traducir>${html}</div>`;
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

  const EJEMPLOS_IA = ["Saca la parte donde me equivoco", "Pon zoom cuando digo algo importante", "Pon un título grande al inicio", "Subtítulos de una palabra a la vez", "Hazlo cuadrado para Instagram"];
  function panelIA() {
    const ia = E.ia, nombre = esc(nombreIA());
    const historial = ia.historial.map((c) => `<div class="cambio ${c.error ? "error" : ""}"><span class="pedido" data-sin-traducir>«${esc(c.pedido)}»</span>
      <span data-sin-traducir>${esc(c.error || c.resumen)}</span>${c.ok && c.aplicadas ? ` <button class="boton sutil" data-accion="deshacer" style="padding:2px 6px">↶ <span>Deshacer</span></button>` : ""}</div>`).join("");
    return `<div class="tarjeta"><h3>${frase("Dile a {ia} qué cambiar", { ia: nombre })}</h3>
      <textarea id="pedido-ia" rows="3" placeholder="${esc(tr("Ej.: corta desde «te muestro» hasta «cómo» y pon zoom en «publicar»"))}" ${ia.enviando ? "disabled" : ""} data-sin-traducir>${esc(ia.texto)}</textarea>
      <div class="ejemplos">${EJEMPLOS_IA.map((e) => `<button class="chip" data-ejemplo="${esc(tr(e))}">${esc(e)}</button>`).join("")}</div>
      <button class="boton principal grande" data-accion="pedir-ia" ${ia.enviando ? "disabled" : ""}>${ia.enviando ? frase("{ia} está editando…", { ia: nombre }) : "Aplicar"}</button>
      <p class="nota">${frase("{ia} usa tu cuenta y solo ve el texto con sus tiempos, nunca el video. Puedes deshacer cada cambio.", { ia: nombre })}</p></div>
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
    textos: ["Inicio del texto {n}", "Fin del texto {n}"] };
  const MOTIVOS = { silencio: "Silencio", muletilla: "Muletilla", manual: "Corte manual", ia: "Corte de la IA", fuera: "Fuera del Short" };
  const relojFino = (s) => {
    s = Math.max(0, s || 0); const m = Math.floor(s / 60), x = (s - m * 60).toFixed(1).padStart(4, "0");
    return `${m}:${E.idioma === "es" ? x.replace(".", ",") : x}`;
  };
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
    const bloque = (lista, k, o, clase, etiqueta = "", titulo = "") => `<div class="bloque ${clase} ${sel?.lista === lista && sel.k === k ? "sel" : ""}"
      data-lt="${lista}" data-k="${k}" style="${pos(o)}"${titulo ? ` title="${esc(titulo)}"` : ""}>${bordes(lista, k, o)}<span class="etq" data-sin-traducir>${etiqueta}</span></div>`;
    const onda = Array.from({ length: 120 }, (_, k) => {
      const t = (k + 0.5) / 120 * dur, habla = p.palabras.some((w) => w.i <= t && t <= w.f);
      return `<i style="height:${habla ? 30 + ((k * 37) % 50) : 4}%"></i>`;
    }).join("");
    const cortes = p.cortes.map((c, k) => bloque("cortes", k, c, "b-corte", "", MOTIVOS[c.motivo] || "")).join("");
    const zooms = p.zooms.map((z, k) => bloque("zooms", k, z, "b-zoom", esc(`🔍 ${z.escala}×`))).join("");
    const textos = p.textos.map((x, k) => bloque("textos", k, x, "b-texto", esc(x.texto))).join("");
    const cortados = unir(p.cortes);
    const subs = lineas(p.palabras.filter((w) => !palabraCortada(p, w, cortados)), p.subtitulos.palabras_por_linea)
      .map((g) => `<div class="bloque b-sub" style="${pos({ i: g[0].i, f: g[g.length - 1].f })}"><span class="etq" data-sin-traducir>${esc(g.map((w) => w.t).join(" "))}</span></div>`).join("");
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
        <div class="lt-zoom" role="group" aria-label="Zoom de la línea de tiempo">
          <button class="icono" data-lt-zoom="-1" title="Alejar" aria-label="Alejar" ${E.lt.zoom <= 1 ? "disabled" : ""}>−</button>
          <span class="num" data-sin-traducir>${esc(String(E.lt.zoom).replace(".", E.idioma === "es" ? "," : "."))}×</span>
          <button class="icono" data-lt-zoom="1" title="Acercar" aria-label="Acercar" ${E.lt.zoom >= niveles[niveles.length - 1] ? "disabled" : ""}>＋</button>
          <button class="icono" data-lt-zoom="0" title="Ver todo" aria-label="Ver todo" ${E.lt.zoom <= 1 ? "disabled" : ""}>⤢</button></div></div>
      <div class="lt-cuerpo"><div class="lt-nombres" aria-hidden="true"><span></span><span>Video</span><span>Subtítulos</span><span>Textos</span><span>Música</span></div>
        <div class="lt-vista" id="lt-vista"><div class="lt-contenido" id="lt-contenido" style="width:${E.lt.zoom * 100}%">
          <div class="lt-regla" id="linea" role="slider" tabindex="0" aria-label="Línea de tiempo" aria-valuemin="0" aria-valuemax="${Math.round(dur)}" aria-valuenow="0">
            <span id="lt-marcas">${marcasRegla()}</span></div>
          <div class="pista pista-video" role="group" aria-label="Video"><div class="fila-zoom">${zooms}</div><div class="fila-cortes"><div class="onda">${onda}</div>${cortes}</div></div>
          <div class="pista pista-subtitulos ${p.subtitulos.activos ? "" : "apagada"}" role="group" aria-label="Subtítulos"${p.subtitulos.activos ? "" : ` title="Subtítulos apagados"`}>
            ${subs || `<span class="lt-vacia">Sin transcripción</span>`}</div>
          <div class="pista pista-textos" role="group" aria-label="Textos">${textos || `<span class="lt-vacia">Sin textos</span>`}</div>
          <div class="pista pista-musica" role="group" aria-label="Música">${musica}</div>
          <div class="lt-sombras" aria-hidden="true">${sombras}</div>
          <span class="cabezal" id="cabezal" style="left:0"></span></div></div></div></div>`;
  }
  function infoSel() {
    const p = P(), s = E.lt.sel, o = s && p?.[s.lista]?.[s.k];
    if (!o) return `<span class="nota">Arrastra los bordes de un tramo para ajustarlo. Con el teclado, usa las flechas.</span>`;
    const v = { a: esc(relojFino(o.i)), b: esc(relojFino(o.f)) };
    const txt = { cortes: "Corte de {a} a {b}", zooms: "Zoom de {a} a {b}", textos: "Texto de {a} a {b}" }[s.lista];
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
    pintarInfo();
  }
  function quitarBloque(lista, k) {
    const p = P();
    p[lista].splice(k, 1);
    E.lt.sel = null;
    guardar(p, { cortes: "Corte quitado", zooms: "Zoom quitado", textos: "Texto quitado" }[lista]);
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
    return `<h2 id="t-aj">Ajustes</h2><p>Todo se procesa en tu computador. La IA usa tu propia cuenta.</p>
      <div class="seccion"><h3>Tu IA</h3>${filasIA()}</div>
      <div class="seccion"><h3>Transcripción</h3>${filasModelo()}</div>
      <div class="seccion"><h3>General</h3><div class="fila"><div class="txt"><b>Idioma de la app</b></div><select data-config="idioma_ui"><option value="es" ${E.idioma === "es" ? "selected" : ""}>Español</option><option value="en" ${E.idioma === "en" ? "selected" : ""}>English</option></select></div>
        <div class="fila"><div class="txt"><b>Carpeta de tus videos</b><small data-sin-traducir>${esc(E.carpeta)}</small></div><button class="boton" data-accion="abrir-carpeta">Abrir</button></div></div>
      <div class="seccion"><h3>Acerca de Corta</h3><p style="margin:0 0 8px;color:var(--suave)">${frase("Corta {v} · Gratis y de código abierto (AGPL-3.0).", { v: esc(E.version) })}</p>
        <div class="fila"><div class="txt"><b>Actualizaciones</b><small>${E.buscando === "buscando" ? "Buscando…" : E.buscando === "alDia" ? "Estás en la última versión." : E.actualizacion?.hay ? "Hay una versión nueva." : "Corta revisa sola cada 6 horas."}</small></div>
          ${E.actualizacion?.hay ? `<button class="boton principal" data-accion="actualizar">Actualizar</button>` : `<button class="boton" data-accion="buscar-act" ${E.buscando === "buscando" ? "disabled" : ""}>Buscar actualizaciones</button>`}</div>
        <div class="enlaces"><a href="#" data-enlace="${ENLACES.sitio}">Sitio web</a><a href="#" data-enlace="${ENLACES.codigo}">Código</a><a href="#" data-enlace="${ENLACES.comunidad}">Comunidad</a></div></div>
      <div class="pie-dialogo"><button class="boton principal" data-accion="cerrar">Listo</button></div>`;
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
    if (vista && vista.clientWidth && vista.clientWidth !== E.lt.ancho) { E.lt.ancho = vista.clientWidth; const m = $("#lt-marcas"); if (m) m.innerHTML = marcasRegla(); }
    actualizarCapas();
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
    // Zoom
    const z = (p.zooms || []).find((x) => x.i <= t && t <= x.f);
    const capa = $("#capa-zoom"); if (capa) capa.style.transform = z ? `scale(${z.escala})` : "none";
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
      if (p.subtitulos.activos && s) {
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
            return `<span style="${extra}">${esc(w.t)}</span>`;
          }).join(" ")}</div>`;
        }
      }
      if (subs.dataset.html !== html) { subs.innerHTML = html; subs.dataset.html = html; }
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
    requestAnimationFrame(bucle);
  }
  window.addEventListener("resize", () => ajustarPantalla());

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
    const el = ev.target.closest("[data-accion],[data-sel],[data-pestana],[data-w],[data-pausa],[data-lienzo],[data-estilo],[data-ejemplo],[data-ver-short],[data-crear-short],[data-probar],[data-modelo],[data-modelo-usar],[data-bv],[data-enlace],[data-lt-zoom],[data-elegir-idioma]");
    if (!el) return;
    const d = el.dataset, p = P(), v = $("#video");
    if (d.elegirIdioma) return elegirIdioma(d.elegirIdioma === "en" ? "en" : "es");
    if (d.ltZoom != null) return cambiarZoom(Number(d.ltZoom));
    if (d.enlace) { ev.preventDefault(); return host.enviar("abrirEnlace", { url: d.enlace }); }
    if (d.sel) { E.sel = d.sel; E.seleccion = null; E.shorts = null; E.ultimoAhorro = null; E.lt.sel = null; return pintar(); }
    if (d.pestana) { E.pestana = d.pestana; return pintar(); }
    if (d.w != null) {
      const k = Number(d.w);
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
      case "cortar-sel": return cortarSeleccion();
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
      case "cerrar": if (E.exportar?.paso !== "exportando") E.exportar = null; E.ajustes = false; return pintar();
      case "abrir-carpeta": return host.enviar("abrirCarpeta", {});
      case "actualizar": E.ajustes = false; host.enviar("actualizar"); return pintar();
      case "buscar-act": E.buscando = "buscando"; host.enviar("buscarActualizacion"); return pintar();
      case "bv-fin": E.bv = null; E.bvCerrada = true; host.enviar("config", { bienvenida: true }); return pintar();
    }
  });
  document.addEventListener("input", (ev) => {
    const ds = ev.target.dataset || {}, p = P();
    if (!p) return;
    if (ds.encuadre != null) { p.encuadre.x = Number(ev.target.value); return ajustarPantalla(); }
    if (ds.subPosicion != null) { p.subtitulos.posicion = Number(ev.target.value); return actualizarCapas(); }
    if (ds.musicaVolumen != null && p.musica) { p.musica.volumen = Math.round(Number(ev.target.value) * 100) / 100; const o = $("#musica-vol"); if (o) o.textContent = Math.round(p.musica.volumen * 100) + " %"; return; }
    if (ev.target.id === "pedido-ia") E.ia.texto = ev.target.value;
  });
  document.addEventListener("change", async (ev) => {
    const ds = ev.target.dataset || {}, p = P();
    if (ds.encuadre != null || ds.subPosicion != null || (ds.musicaVolumen != null && p?.musica)) return guardar(p);
    if (ds.relleno != null) { p.relleno = ev.target.value; return guardar(p); }
    if (ds.subActivos != null) { p.subtitulos.activos = ev.target.checked; return guardar(p); }
    if (ds.subPalabras != null) { p.subtitulos.palabras_por_linea = Number(ev.target.value); return guardar(p); }
    if (ds.config) {
      E.config[ds.config] = ev.target.value; host.enviar("config", { [ds.config]: ev.target.value });
      if (ds.config === "idioma_ui") await cargarIdioma(ev.target.value);
      return pintar();
    }
  });
  document.addEventListener("keydown", (ev) => {
    const escribiendo = ev.target.closest?.("input, textarea, select, [contenteditable]");
    if (E.bv !== null) return;  // con la bienvenida abierta, los atajos del editor no corren detrás
    if (ev.key === "Escape") { if (E.exportar?.paso !== "exportando") E.exportar = null; E.ajustes = false; E.seleccion = null; E.lt.sel = null; return pintar(); }
    if (teclaLinea(ev)) return;
    if (escribiendo) { if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey) && ev.target.id === "pedido-ia") $("[data-accion=pedir-ia]")?.click(); return; }
    if ((ev.key === "Backspace" || ev.key === "Delete") && E.seleccion) { ev.preventDefault(); return cortarSeleccion(); }
    if (ev.key === " " && P()) { ev.preventDefault(); return $("[data-accion=play]")?.click(); }
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "z" && P()) { ev.preventDefault(); host.enviar("deshacer", { carpeta: E.sel }); }
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
    if (bl) { seleccionar(bl.dataset.lt, Number(bl.dataset.k)); return irA(tiempoEn(ev.clientX)); }
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
      E.ia = { texto: r.ok ? "" : pedido, enviando: false, historial: [{ pedido, ok: r.ok, resumen: r.resumen || tr("Listo."), aplicadas: r.aplicadas, error: r.ok ? "" : r.error }, ...E.ia.historial].slice(0, 12) };
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
    actualizacionRevisada(r) { E.buscando = r.hay ? null : r.sinConexion ? "sinConexion" : "alDia"; if (r.hay) E.actualizacion = r; pintar(); },
    _probar(f) { f(E); pintar(); },
    _pruebas: { conservados, aSalida, duracionFinal, cortarPalabras, restaurar, cortesPorPalabras, lineas, unir, limitesBorde, moverBorde,
      tramosVoz, cuantoBaja, musica: () => musicaAudio, ganancia: () => gananciaMusica, demoConfig: () => DEMO?.config },
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
        const x = demoProy(d.carpeta), p = x.proyecto, t = d.texto.toLowerCase();
        (historial[d.carpeta] ||= []).push(clonar(p));
        let resumen = tr("En la vista previa la IA es de mentira: en la app, tu IA entiende cualquier pedido.");
        const idx = (palabra) => p.palabras.findIndex((w) => w.t.toLowerCase().startsWith(palabra));
        if (/zoom/.test(t)) { const k = idx("ahorrar"), j = idx("hora"); p.zooms.push({ i: p.palabras[k].i, f: p.palabras[j].f, escala: 1.3 }); resumen = tr("Puse un zoom cuando dices «ahorrar una hora»."); }
        else if (/t[ií]tulo|title/.test(t)) { p.textos.push({ i: p.palabras[idx("hola")].i, f: p.palabras[idx("ana")].f + 1.2, texto: tr("Edita en 1 minuto"), y: 0.16 }); resumen = tr("Agregué el título «Edita en 1 minuto» al inicio."); }
        else if (/una palabra|one word/.test(t)) { p.subtitulos.estilo = "palabra"; p.subtitulos.palabras_por_linea = 1; resumen = tr("Cambié los subtítulos a una palabra a la vez."); }
        else if (/cuadrad|square|instagram/.test(t)) { p.lienzo = "1:1"; resumen = tr("Lo dejé cuadrado (1:1) para Instagram."); }
        else if (/equivoc|mistake|corta|cut/.test(t)) { cortarPalabras(p, idx("mmm"), idx("cómo"), "ia"); resumen = tr("Corté «Mmm… te muestro cómo», que sobraba."); }
        A.iaRespondio({ ok: true, aplicadas: 1, resumen, proyecto: clonar(p) });
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
      case "abrirEnlace": return window.open(d.url, "_blank", "noopener");
      case "abrirCarpeta": return toast("En la app, aquí se abre la carpeta");
      case "buscarActualizacion": return luego(500, () => A.actualizacionRevisada({ hay: false }));
    }
  }

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
