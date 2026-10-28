// Pruebas de la interfaz (ui/) en un navegador real con los datos ficticios de ui/demo.json.
// Uso: node pruebas/interfaz.mjs   (necesita Playwright; PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí)
// Revisa: 1) la lógica de ui/app.js da lo mismo que Python (pruebas/casos.json); 2) ninguna vista tira errores de JavaScript
// (español e inglés, escritorio y celular); 3) todo texto tiene traducción en ui/idiomas/en.json; 4) nada se sale de la pantalla a
// ancho de celular; 5) contraste del botón principal; 6) editar por texto corta de verdad; 7) la línea de tiempo mueve bordes con
// mouse, toque y teclado sin cambiar el formato, y la música suena y baja cuando hablas; 8) en el primer uso lo primero es elegir
// el idioma (con teclado) y lo que sigue sale en ese idioma; 12) plantillas: elegir una, llenar sus huecos y abrir el proyecto (a
// 390 px y en escritorio). Con CAPTURAS=carpeta guarda capturas (y las de plantillas, con CAPTURAS_PLANTILLAS=carpeta).
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const CAPTURAS = process.env.CAPTURAS || "";
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".ttf": "font/ttf", ".jpg": "image/jpeg" };
function servir(q, r, ruta, tipo) {
  // Con rangos (Range), como GitHub Pages: sin esto el navegador no puede adelantar el video.
  const total = fs.statSync(ruta).size, m = /bytes=(\d*)-(\d*)/.exec(q.headers.range || "");
  if (!m) { r.writeHead(200, { "Content-Type": tipo, "Content-Length": total, "Accept-Ranges": "bytes" }); return fs.createReadStream(ruta).pipe(r); }
  const i = m[1] ? Number(m[1]) : 0, f = m[2] ? Number(m[2]) : total - 1;
  r.writeHead(206, { "Content-Type": tipo, "Content-Range": `bytes ${i}-${f}/${total}`, "Content-Length": f - i + 1, "Accept-Ranges": "bytes" });
  fs.createReadStream(ruta, { start: i, end: f }).pipe(r);
}
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, "ui", decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(path.join(RAIZ, "ui")) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  servir(q, r, ruta, tipos[path.extname(ruta)] || "application/octet-stream");
}).listen(0);
const BASE = `http://localhost:${servidor.address().port}/index.html`;
const demo = fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8");
const casos = JSON.parse(fs.readFileSync(path.join(RAIZ, "pruebas", "casos.json"), "utf8"));
// Datos de la demo (títulos, palabras, nombres de estilos…): se comparan textos completos, no pedazos, para que un texto de la
// interfaz que por casualidad aparece dentro de un dato («Texto» en «Texto blanco sobre…») igual se revise.
const datosDemo = new Set();
(function juntar(v) { if (typeof v === "string") datosDemo.add(v.replace(/\s+/g, " ").trim()); else if (v && typeof v === "object") Object.values(v).forEach(juntar); })(JSON.parse(demo));
const esDato = (t) => datosDemo.has(t) || /^(Corta|Claude|ChatGPT \(Codex\)|Gemini|English|Español|9:16|1:1|4:5|16:9)$/.test(t);

const VISTAS = [
  ["texto", "E=>{E.pestana='texto'}"],
  ["texto-seleccion", "E=>{E.seleccion=[4,8];E.ancla=4}"],
  ["texto-limpio", "E=>{E.seleccion=null;E.ultimoAhorro=9.3}"],
  ["texto-corrigiendo", "E=>{E.editar={desde:3,hasta:3,valor:'Ana.',donde:'texto'}}"],
  ["texto-sugerencia", "E=>{E.editar=null;E.seleccion=[3,3];E.sugerencia={de:'calumi',a:'Kalumi',n:2,todo:false,recordado:false}}"],
  ["texto-sugerencia-hecha", "E=>{E.sugerencia={de:'calumi',a:'Kalumi',n:1,todo:true,recordado:false}}"],
  ["vista-corrigiendo", "E=>{E.sugerencia={de:'calumi',a:'Kalumi',n:0,todo:false,recordado:true};E.seleccion=null;E.editar={desde:3,hasta:3,valor:'Ana.',donde:'vista'}}"],
  ["texto-linea", "E=>{E.editar=null;E.sugerencia=null;E.proyectos[0].proyecto.palabras[1].linea='fin';E.proyectos[0].proyecto.palabras[5].linea='sigue';E.seleccion=[1,1]}"],
  ["subtitulos", "E=>{E.pestana='subtitulos'}"],
  ["ia", "E=>{E.pestana='ia';E.ia={texto:'',enviando:false,historial:[{pedido:'Pon zoom',ok:true,resumen:'Listo.',aplicadas:1,carpeta:E.sel},{pedido:'x',ok:false,error:'x',carpeta:E.sel}]}}"],
  ["ia-cambios", "E=>{const p=E.proyectos[0].proyecto;p.zooms=[{i:7.1,f:8.6,escala:1.3,origen:'ia-a'}];p.cambios_ia=[{id:'ia-a',estado:'aplicado',pedido:'Pon zoom',resumen:'Puse un zoom.',agregados:{zooms:[{i:7.1,f:8.6,escala:1.3,origen:'ia-a'}]}},{id:'ia-b',estado:'quitado',conservados:2,pedido:'Hazlo cuadrado',resumen:'Lo dejé cuadrado.'},{id:'ia-c',estado:'quitado',resumen:'Listo.',ajustes:[{campo:'lienzo',antes:'9:16',despues:'1:1'}]},{id:'ia-d',estado:'aplicado',resumen:'x',agregados:{zooms:[{i:1,f:2,escala:1.2},{i:3,f:4,escala:1.2}]}},{id:'ia-e',estado:'aplicado',resumen:'x',agregados:{textos:[{i:1,f:2,texto:'x',y:0.2}]}},{id:'ia-f',estado:'aplicado',resumen:'x',agregados:{cortes:[{i:1,f:2,motivo:'ia'},{i:3,f:4,motivo:'ia'}]}}]}"],
  ["ia-enviando", "E=>{E.ia.enviando=true;E.ia.texto='Pon un título';const p=E.proyectos[0].proyecto;p.zooms=[];p.cambios_ia=[]}"],
  ["shorts", "E=>{E.ia.enviando=false;E.pestana='shorts'}"],
  ["shorts-buscando", "E=>{E.buscandoShorts=true}"],
  ["shorts-lista", "E=>{E.buscandoShorts=false;E.shorts={lista:[{i:4,f:28,duracion:24,titulo:'Ahorra una hora',gancho:'¿Sabías…?',por_que:'Pregunta directa.'}]}}"],
  ["shorts-error", "E=>{E.shorts={error:'x'}}"],
  ["efectos", "E=>{E.shorts=null;E.pestana='efectos'}"],
  ["efectos-aplicados", "E=>{const p=E.proyectos[0].proyecto;p.efectos=[{efecto:'vintage',pasos:[{tipo:'color',sepia:0.4}]},{efecto:'zoom-golpe',pasos:[{tipo:'zoom',desde:1,hasta:1.25,curva:'golpe'}],i:5,f:8},{efecto:'borrado',pasos:[{tipo:'vineta',fuerza:0.5}],i:9,f:12}];p.divisiones=[10];E.seleccion=[4,8]}"],
  ["efectos-tramo", "E=>{E.seleccion=null;E.lt.sel={lista:'tramos',k:1};E.fx={categoria:'movimiento',busqueda:''}}"],
  ["efectos-buscar-nada", "E=>{E.lt.sel={lista:'efectos',k:1};E.fx={categoria:'todos',busqueda:'zzz'}}"],
  ["catalogo-cargando", "E=>{E.fx={categoria:'todos',busqueda:''};E.catalogo={estado:'cargando',efectos:[],categoria:'todos',busqueda:'',bajando:{}}}"],
  ["catalogo-error", "E=>{E.catalogo={estado:'error',efectos:[],categoria:'todos',busqueda:'',bajando:{}}}"],
  ["catalogo", "E=>{E.catalogo={estado:'listo',efectos:[{id:'neon',categoria:'filtro',nombre:{es:'Neón',en:'Neon'},descripcion:{es:'Colores eléctricos.',en:'Electric colors.'},autor:'Corta',pasos:[{tipo:'color',tono:40}]},{id:'vintage',categoria:'filtro',nombre:{es:'Vintage'},pasos:[{tipo:'color',sepia:0.4}]},{id:'zoom-x',categoria:'movimiento',nombre:{es:'Zoom'},pasos:[{tipo:'zoom',desde:1,hasta:1.2}]}],categoria:'todos',busqueda:'',bajando:{'zoom-x':true}}}"],
  ["catalogo-filtro-vacio", "E=>{E.catalogo.categoria='transicion'}"],
  ["musica", "E=>{E.catalogo=null;const p=E.proyectos[0].proyecto;p.efectos=[];p.divisiones=[];E.lt.sel=null;E.pestana='musica'}"],
  ["musica-elegida", "E=>{E.proyectos[0].proyecto.musica={archivo:'demo/musica-demo.mp3',volumen:0.15}}"],
  ["linea-pistas", "E=>{const p=E.proyectos[0].proyecto;p.cortes=[{i:0,f:1.1,motivo:'silencio'},{i:3.3,f:4.6,motivo:'muletilla'},{i:9.5,f:10.4,motivo:'manual'},{i:20,f:21,motivo:'ia'},{i:28,f:30.24,motivo:'fuera'}];p.zooms=[{i:5.2,f:7.4,escala:1.25}];p.textos=[{i:1.2,f:4,texto:'Edita en 1 minuto',y:0.16}];E.lt.sel={lista:'textos',k:0}}"],
  ["linea-zoom", "E=>{E.lt.zoom=4;E.lt.sel={lista:'zooms',k:0}}"],
  ["linea-corte-sin-subtitulos", "E=>{E.lt.zoom=1;E.lt.sel={lista:'cortes',k:1};E.proyectos[0].proyecto.subtitulos.activos=false}"],
  ["musica-fuera-y-muda", "E=>{const p=E.proyectos[0].proyecto;p.subtitulos.activos=true;p.musica={archivo:'/otra/carpeta/cancion.mp3',volumen:0};E.lt.sel=null}"],
  ["musica-sin-transcripcion", "E=>{E.sel=E.proyectos[1].carpeta;E.proyectos[1].proyecto.musica={archivo:'demo/musica-demo.mp3',volumen:0.2}}"],
  ["volver", "E=>{E.sel=E.proyectos[0].carpeta;E.proyectos[0].proyecto.musica=null}"],
  ["cuadrado-borroso", "E=>{E.pestana='texto';const p=E.proyectos[0].proyecto;p.lienzo='1:1';p.relleno='desenfoque'}"],
  ["horizontal", "E=>{const p=E.proyectos[0].proyecto;p.lienzo='16:9';p.relleno='recorte'}"],
  ["sin-transcripcion", "E=>{E.proyectos[0].proyecto.lienzo='9:16';E.sel=E.proyectos[1].carpeta}"],
  ["transcribiendo", "E=>{E.progreso[E.sel]={texto:'Transcribiendo en tu computador…',pct:40}}"],
  ["exportar", "E=>{E.progreso={};E.sel=E.proyectos[0].carpeta;E.exportar={paso:'pedir'}}"],
  ["exportando", "E=>{E.exportar={paso:'exportando',pct:45}}"],
  ["exportado", "E=>{E.exportar={paso:'listo',duracion:21}}"],
  ["exportar-error", "E=>{E.exportar={paso:'error',error:'x'}}"],
  ["ajustes", "E=>{E.exportar=null;E.ajustes=true}"],
  ["ajustes-vocabulario", "E=>{E.vocabulario={reemplazos:[{de:'calumi',a:'Kalumi'}],palabras:['Kalumi','Ana']}}"],
  ["ajustes-al-dia", "E=>{E.buscando='alDia'}"],
  ["plantillas", "E=>{E.ajustes=false;E.buscando=null;E.pl={fuente:'corta',categoria:'todas',busqueda:'',ver:null,armando:false,bajando:{},catalogo:null}}"],
  ["plantillas-categoria", "E=>{E.pl.categoria='recuerdos'}"],
  ["plantillas-buscar-nada", "E=>{E.pl.categoria='todas';E.pl.busqueda='zzz'}"],
  ["plantilla-detalle", "E=>{E.pl.busqueda='';E.pl.ver='producto-en-15'}"],
  ["plantilla-detalle-16x9", "E=>{E.pl.ver='intro-de-canal'}"],
  ["plantillas-comunidad-cargando", "E=>{E.pl.ver=null;E.pl.fuente='comunidad';E.pl.catalogo={estado:'cargando',plantillas:[],efectos:[]}}"],
  ["plantillas-comunidad-error", "E=>{E.pl.catalogo={estado:'error',plantillas:[],efectos:[]}}"],
  ["plantillas-comunidad", "E=>{E.pl.catalogo={estado:'listo',plantillas:window.Corta._pruebas.demoCatalogoPl(),efectos:[]}}"],
  ["plantilla-comunidad-detalle", "E=>{E.pl.ver='verano-en-fotos';E.pl.bajando={parpadeo:true}}"],
  ["plantilla-armando", "E=>{E.pl.armando=true}"],
  ["clips", "E=>{E.pl=null;const p=E.proyectos[0].proyecto;p.plantilla={id:'antes-y-despues',huecos:[{archivo:'demo/ana.mp4',tipo:'video',desde:2,dur:10,duracion:30.233},{archivo:'demo/foto-1.jpg',tipo:'foto',desde:0,dur:10.233,duracion:null},{archivo:'demo/ana.mp4',tipo:'video',desde:12,dur:10,duracion:30.233}]};p.divisiones=[10,20.233];E.pestana='clips'}"],
  ["clips-armando", "E=>{E.armando={carpeta:E.sel,k:0}}"],
  ["vacio", "E=>{E.armando=null;E.ajustes=false;E.proyectos=[];E.sel=null}"],
];
const navegador = await chromium.launch();
// Cualquier bloqueo de la Content-Security-Policy es un error: la interfaz tiene que funcionar entera con ella.
const abrirPagina = navegador.newPage.bind(navegador);
navegador.newPage = async (opciones) => {
  const p = await abrirPagina(opciones);
  p.on("console", (m) => { if (/Content Security Policy/i.test(m.text())) falla("CSP: " + m.text().slice(0, 200)); });
  return p;
};

// 1) Lógica compartida con Python
{
  const p = await navegador.newPage();
  await p.goto(BASE); await p.waitForFunction(() => window.Corta);
  const malos = await p.evaluate((c) => {
    const P = window.Corta._pruebas, m = [], igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    for (const k of c.conservados) { const r = P.conservados({ fuente: { duracion: k.duracion }, cortes: k.cortes }); if (!igual(r, k.esperado)) m.push("conservados " + JSON.stringify(r)); }
    for (const k of c.a_salida) { const r = P.aSalida({ fuente: { duracion: k.duracion }, cortes: k.cortes }, k.t); if (r !== k.esperado) m.push("aSalida " + r); }
    for (const k of c.cortar) { const p = { fuente: { duracion: c.duracion }, palabras: c.palabras, cortes: [] }; P.cortarPalabras(p, k.desde, k.hasta); if (!igual(p.cortes, k.esperado)) m.push("cortar " + JSON.stringify(p.cortes)); }
    { const p = { cortes: JSON.parse(JSON.stringify(c.restaurar.cortes)) }; P.restaurar(p, c.restaurar.i, c.restaurar.f); if (!igual(p.cortes, c.restaurar.esperado)) m.push("restaurar " + JSON.stringify(p.cortes)); }
    { const r = P.cortesPorPalabras(c.palabras, c.limpiar.silencio, c.limpiar.muletillas, c.duracion); if (!igual(r, c.limpiar.esperado)) m.push("limpiar " + JSON.stringify(r)); }
    { const r = P.lineas(c.palabras, c.lineas.por_linea).map((g) => g.map((w) => w.t)); if (!igual(r, c.lineas.esperado)) m.push("lineas " + JSON.stringify(r)); }
    const ed = c.editar;
    for (const x of ed.editar) { const r = P.editarPalabras(ed.palabras, x.desde, x.hasta, x.texto); if (!igual(r, x.esperado)) m.push("editarPalabras " + JSON.stringify(r)); }
    for (const x of ed.reemplazar) { const r = P.reemplazarTodo(ed.palabras, x.pares); if (!igual(r, [x.esperado, x.n])) m.push("reemplazarTodo " + JSON.stringify(r)); }
    for (const [t, n] of ed.normalizar) if (P.normalizar(t) !== n) m.push("normalizar " + t);
    { const r = P.lineas(ed.lineas.palabras, ed.lineas.por_linea).map((g) => g.map((w) => w.t)); if (!igual(r, ed.lineas.esperado)) m.push("lineas con «linea» " + JSON.stringify(r)); }
    const fx = c.efectos, pf = { ...fx.proyecto };
    for (const x of fx.intervalos) {
      if (!igual(P.intervalosSalida(pf, x.i, x.f), x.esperado)) m.push("intervalosSalida " + JSON.stringify(P.intervalosSalida(pf, x.i, x.f)));
      if (!igual(P.uniones(pf, x.i, x.f), x.uniones)) m.push("uniones " + JSON.stringify(P.uniones(pf, x.i, x.f)));
    }
    for (const x of fx.zoom) {
      if (!igual(P.segmentosZoom(x.paso, x.a, x.b), x.esperado)) m.push("segmentosZoom " + JSON.stringify(P.segmentosZoom(x.paso, x.a, x.b)));
      for (const [t, v] of x.valores) if (P.valorEn(x.esperado, t, 1) !== v) m.push(`valorEn zoom ${t}: ${P.valorEn(x.esperado, t, 1)}`);
    }
    for (const x of fx.capa) {
      if (!igual(P.segmentosCapa(x.paso, x.a, x.b, x.juntas, x.pedazos), x.esperado)) m.push("segmentosCapa " + JSON.stringify(P.segmentosCapa(x.paso, x.a, x.b, x.juntas, x.pedazos)));
      for (const [t, v] of x.valores) if (P.valorEn(x.esperado, t, 0) !== v) m.push(`valorEn capa ${t}: ${P.valorEn(x.esperado, t, 0)}`);
    }
    const pc = c.plantillas;
    for (const x of pc.llenar) { const r = P.llenar(x.huecos, x.clips); if (!igual(r, x.esperado)) m.push("llenar " + JSON.stringify(r)); }
    for (const x of pc.aplicar) { const r = P.aplicarPlantilla(x.plantilla, x.tipos, x.idioma, pc.efectos, x.estilos); if (!igual(r, x.esperado)) m.push("aplicarPlantilla " + JSON.stringify(r)); }
    for (const x of pc.uniones.casos) { const r = P.uniones(pc.uniones.proyecto, x.i, x.f); if (!igual(r, x.esperado)) m.push("uniones con divisiones " + JSON.stringify(r)); }
    // Lo que ves es lo que exportas: los filtros de color de CSS (como los dibuja este navegador) dan los mismos colores que ffmpeg
    for (const x of fx.color) {
      const origen = document.createElement("canvas"); origen.width = 3; origen.height = 1;
      const o = origen.getContext("2d");
      x.entrada.forEach(([r, g, b], k) => { o.fillStyle = `rgb(${r},${g},${b})`; o.fillRect(k, 0, 1, 1); });
      const destino = document.createElement("canvas"); destino.width = 3; destino.height = 1;
      const d = destino.getContext("2d", { willReadFrequently: true }); d.filter = P.cssColor(x.paso); d.drawImage(origen, 0, 0);
      const px = d.getImageData(0, 0, 3, 1).data;
      x.esperado.forEach((e, k) => { const v = [px[k * 4], px[k * 4 + 1], px[k * 4 + 2]]; if (e.some((n, j) => Math.abs(n - v[j]) > 3)) m.push(`color ${JSON.stringify(x.paso)} ${x.entrada[k]}: CSS ${v}, ffmpeg ${e}`); });
    }
    return m;
  }, casos);
  malos.forEach((x) => falla("lógica distinta a Python: " + x));
  if (!malos.length) console.log("  ✓ Misma lógica que Python (pruebas/casos.json)");
  // 6) Editar por texto: elegir palabras y borrar las saca del video
  await p.evaluate(() => window.Corta._probar((E) => { E.bv = null; }));
  await p.click('[data-w="4"]'); await p.click('[data-w="8"]', { modifiers: ["Shift"] }); await p.keyboard.press("Backspace");
  const cortadas = await p.$$eval(".w.cortada", (els) => els.map((e) => e.dataset.w));
  if (!["4", "5", "6", "7", "8"].every((k) => cortadas.includes(k))) falla("borrar palabras elegidas no las cortó: " + cortadas.join(","));
  else console.log("  ✓ Editar por texto corta las palabras elegidas");
  await p.click('[data-accion="limpiar"]'); await p.waitForSelector(".ahorro, .limpiar small b", { timeout: 3000 }).catch(() => {});
  const ahorro = await p.textContent(".limpiar small");
  if (!/s/.test(ahorro || "")) falla("limpiar no mostró el ahorro"); else console.log("  ✓ Limpiar silencios muestra el ahorro");
  await p.close();
}

// 2–4) Todas las vistas
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1360, height: 860 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "light" }]]) {
    for (const bv of [false, true]) {
      const p = await navegador.newPage(opciones);
      p.on("pageerror", (e) => falla(`error de JavaScript (${idioma}, ${modo}): ${e.message}`));
      await p.addInitScript(() => { window._faltantes = new Set(); });
      await p.goto(BASE + "?" + [consulta, bv ? "bienvenida" : ""].filter(Boolean).join("&"));
      await p.waitForFunction((sel) => window.Corta && document.querySelector(sel), bv ? ".capa" : ".app");
      const pasos = bv ? [0, 1, 2, 3].map((n) => [`bienvenida-${n}`, `E=>{E.bv=${n}}`]) : VISTAS;
      for (const [nombre, f] of pasos) {
        await p.evaluate(`window.Corta._probar(${f})`);
        await p.waitForTimeout(80);
        if (modo === "celular") {
          const ancho = await p.evaluate(() => document.documentElement.scrollWidth);
          if (ancho > 392) falla(`se sale de la pantalla a ancho de celular (${ancho}px) en «${nombre}» (${idioma})`);
        }
        if (CAPTURAS && (idioma === "español" || modo === "escritorio")) await p.screenshot({ path: path.join(CAPTURAS, `${idioma}-${modo}-${nombre}.png`) });
      }
      if (idioma === "inglés") {
        const faltan = [...new Set(await p.evaluate(() => [...window._faltantes]))].filter((t) => !esDato(t));
        if (faltan.length) falla(`${faltan.length} textos sin traducción en ui/idiomas/en.json:\n      ` + faltan.map((t) => JSON.stringify(t)).join("\n      "));
      }
      await p.close();
    }
  }
  console.log(`  ✓ Vistas en ${idioma}`);
}

// 7) Línea de tiempo y música
{
  const p = await navegador.newPage({ viewport: { width: 1360, height: 860 } });
  p.on("pageerror", (e) => falla("error de JavaScript (línea de tiempo): " + e.message));
  await p.goto(BASE); await p.waitForFunction(() => window.Corta && document.querySelector("#lt-vista"));
  // Lógica de bordes y de cuándo baja la música
  const malos = await p.evaluate(() => {
    const P = window.Corta._pruebas, m = [], igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    const l = [{ i: 1, f: 2, motivo: "manual" }, { i: 3, f: 4, motivo: "silencio" }];
    if (!igual(P.limitesBorde(l, 1, "i", 10), [2, 3.95])) m.push("límites inicio " + P.limitesBorde(l, 1, "i", 10));
    if (!igual(P.limitesBorde(l, 0, "f", 10), [1.05, 3])) m.push("límites fin " + P.limitesBorde(l, 0, "f", 10));
    if (P.moverBorde(l, 1, "i", 0.5, 10) !== 2) m.push("no se detuvo en el vecino");
    if (P.moverBorde(l, 1, "f", 99, 10) !== 10) m.push("se salió del video");
    if (P.moverBorde(l, 0, "f", 0.2, 10) !== 1.05) m.push("se dio vuelta el tramo");
    if (!igual(l, [{ i: 1, f: 1.05, motivo: "manual" }, { i: 2, f: 10, motivo: "silencio" }])) m.push("cambió algo más que el borde " + JSON.stringify(l));
    const p = { cortes: [{ i: 2, f: 3, motivo: "manual" }], palabras: [{ t: "a", i: 0.5, f: 1 }, { t: "b", i: 1.1, f: 1.5 }, { t: "c", i: 2.2, f: 2.6 }, { t: "d", i: 5, f: 5.5 }] };
    const voz = P.tramosVoz(p);
    if (!igual(voz, [{ i: 0.47, f: 1.9 }, { i: 4.97, f: 5.9 }])) m.push("tramosVoz " + JSON.stringify(voz));
    if (P.cuantoBaja(voz, 1.2) !== 0.25 || P.cuantoBaja(voz, 2.4) !== 1 || P.cuantoBaja(voz, 4) !== 1) m.push("cuantoBaja");
    return m;
  });
  malos.forEach((x) => falla("línea de tiempo: " + x));
  if (!malos.length) console.log("  ✓ Bordes con límites y música que baja con la voz (lógica)");
  const proyecto = () => p.evaluate(() => { let r; window.Corta._probar((E) => { r = JSON.parse(JSON.stringify(E.proyectos[0].proyecto)); }); return r; });
  await p.evaluate(() => window.Corta._probar((E) => { E.bv = null; const q = E.proyectos[0].proyecto; q.cortes = [{ i: 3.3, f: 4.6, motivo: "muletilla" }]; q.textos = [{ i: 8, f: 10, texto: "Hola", y: 0.2 }]; }));
  // Mouse: arrastrar el fin del corte 40 px a la derecha
  const caja = await p.locator("#lt-cortes-0-f").boundingBox();
  await p.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2); await p.mouse.down();
  await p.mouse.move(caja.x + caja.width / 2 + 20, caja.y + 10, { steps: 3 }); await p.mouse.move(caja.x + caja.width / 2 + 40, caja.y + 10, { steps: 3 }); await p.mouse.up();
  let q = await proyecto();
  if (!(q.cortes[0].f > 4.6) || q.cortes[0].i !== 3.3 || Object.keys(q.cortes[0]).join() !== "i,f,motivo") falla("arrastrar con el mouse no movió el borde: " + JSON.stringify(q.cortes));
  else console.log(`  ✓ Mouse: el borde se arrastra (fin del corte 4,6 → ${q.cortes[0].f} s)`);
  // Teclado: foco visible en el borde, flechas y que se guarde
  await p.focus("#lt-textos-0-i");
  for (let k = 0; k < 3; k++) await p.keyboard.press("ArrowRight");
  await p.keyboard.press("Shift+ArrowLeft");
  await p.waitForTimeout(900);
  q = await proyecto();
  const foco = await p.evaluate(() => [document.activeElement?.id, document.activeElement?.getAttribute("aria-valuenow"), getComputedStyle(document.activeElement).outlineStyle]);
  if (q.textos[0].i !== 7.3 || foco[0] !== "lt-textos-0-i" || foco[1] !== "7.3") falla("teclado en el borde: " + JSON.stringify([q.textos[0], foco]));
  else if (foco[2] === "none") falla("el borde enfocado no muestra el foco");
  else console.log("  ✓ Teclado: flechas mueven el borde, se guarda y el foco se ve");
  await p.keyboard.press("Delete");
  q = await proyecto();
  if (q.textos.length !== 0) falla("Suprimir no quitó el texto"); else console.log("  ✓ Suprimir quita el tramo");
  // Toque: los mismos eventos de puntero con el dedo
  const c2 = await p.locator("#lt-cortes-0-i").boundingBox();
  await p.evaluate(({ x, y }) => {
    const h = document.querySelector("#lt-cortes-0-i"), ev = (tipo, dx) => new PointerEvent(tipo, { bubbles: true, cancelable: true, pointerId: 7, pointerType: "touch", clientX: x + dx, clientY: y, isPrimary: true });
    h.dispatchEvent(ev("pointerdown", 0)); document.dispatchEvent(ev("pointermove", -15)); document.dispatchEvent(ev("pointermove", -30)); document.dispatchEvent(ev("pointerup", -30));
  }, { x: c2.x + c2.width / 2, y: c2.y + c2.height / 2 });
  q = await proyecto();
  if (!(q.cortes[0].i < 3.3)) falla("arrastrar con el dedo no movió el borde: " + JSON.stringify(q.cortes)); else console.log(`  ✓ Toque: el borde se arrastra (inicio 3,3 → ${q.cortes[0].i} s)`);
  // Zoom horizontal
  await p.click('[data-lt-zoom="1"]'); await p.click('[data-lt-zoom="1"]');
  const zoom = await p.evaluate(() => { const v = document.querySelector("#lt-vista"); return v.scrollWidth / v.clientWidth; });
  if (!(zoom > 1.9)) falla("el zoom de la línea de tiempo no agrandó las pistas: " + zoom); else console.log(`  ✓ Zoom de la línea de tiempo (×${zoom.toFixed(1)})`);
  await p.click('[data-lt-zoom="0"]');
  // Música: elegir (simulado), formato {archivo, volumen}, suena y baja cuando hablas
  await p.click('[data-pestana="musica"]'); await p.click('.cuerpo-panel [data-accion="elegir-musica"]');
  await p.waitForSelector("[data-musica-volumen]");
  q = await proyecto();
  if (JSON.stringify(Object.keys(q.musica)) !== '["archivo","volumen"]' || q.musica.volumen !== 0.15) falla("la música no quedó como {archivo, volumen}: " + JSON.stringify(q.musica));
  const palabras = q.palabras, larga = palabras.findIndex((w) => w.t === "una"), pausa = palabras.findIndex((w) => w.t === "videos?");
  await p.evaluate(() => window.Corta._probar((E) => { E.proyectos[0].proyecto.cortes = []; }));
  await p.click('[data-accion="escuchar-musica"]');
  await p.evaluate((t) => { document.querySelector("#video").currentTime = t; }, palabras[larga].i);
  await p.waitForTimeout(450);
  const hablando = await p.evaluate(() => { const a = window.Corta._pruebas.musica(); return { sonando: !a.paused && a.currentTime > 0, vol: a.volume, video: !document.querySelector("#video").paused }; });
  await p.evaluate((t) => { document.querySelector("#video").currentTime = t; }, palabras[pausa].f + 0.45);
  await p.waitForTimeout(950);
  const callado = await p.evaluate(() => { const a = window.Corta._pruebas.musica(); return { sonando: !a.paused, vol: a.volume, texto: document.querySelector("#musica-ahora")?.textContent }; });
  // El Chromium de Playwright en GitHub no trae H.264: ahí el video de la demo no se reproduce y no hay cómo probar que suene.
  const h264 = await p.evaluate(() => document.createElement("video").canPlayType('video/mp4; codecs="avc1.42E01E"') !== "");
  if (!h264 && !hablando.video) console.log("  - Música en la vista previa: este Chromium no reproduce H.264, se prueba solo la lógica");
  else if (!hablando.sonando || !hablando.video) falla("la música no suena en la vista previa: " + JSON.stringify(hablando));
  else if (!(hablando.vol < 0.06 && callado.vol > 0.1)) falla(`la música no baja cuando hablas: ${hablando.vol.toFixed(3)} hablando, ${callado.vol.toFixed(3)} en la pausa`);
  else console.log(`  ✓ Música suena y baja cuando hablas (volumen ${hablando.vol.toFixed(3)} hablando, ${callado.vol.toFixed(3)} en la pausa: «${callado.texto}»)`);
  await p.click('[data-accion="escuchar-musica"]');
  await p.waitForTimeout(100);
  if (!(await p.evaluate(() => window.Corta._pruebas.musica().paused))) falla("la música sigue sonando con el video en pausa");
  await p.click('[data-accion="quitar-musica"]');
  if ((await proyecto()).musica !== null) falla("quitar la música no dejó musica: null");
  await p.close();
}

// 9) Corregir subtítulos por palabra: en el texto y sobre la vista previa, cambiar en todo el video, recordar y deshacer
{
  const p = await navegador.newPage({ viewport: { width: 1360, height: 860 } });
  p.on("pageerror", (e) => falla("error de JavaScript (corregir palabras): " + e.message));
  await p.goto(BASE + "?idioma=es"); await p.waitForSelector(".app");
  const proyecto = () => p.evaluate(() => { let r; window.Corta._probar((E) => { r = JSON.parse(JSON.stringify(E.proyectos[0].proyecto)); }); return r; });
  // «Kalumi» es una marca inventada; la transcripción la escribió mal dos veces («calumi.» y «Calumi»).
  const k1 = 3, k2 = await p.evaluate(() => { let k; window.Corta._probar((E) => { const w = E.proyectos[0].proyecto.palabras; k = w.findIndex((x) => x.t === "Short"); w[3].t = "calumi."; w[k].t = "Calumi"; }); return k; });
  const antes = (await proyecto()).palabras[k1];
  await p.click(`[data-w="${k1}"]`); await p.click(`[data-w="${k1}"]`);  // tocar otra vez la palabra elegida la corrige
  await p.fill("#editar-palabra", "Kalumi."); await p.keyboard.press("Enter");
  let q = await proyecto();
  if (q.palabras[k1].t !== "Kalumi." || q.palabras[k1].i !== antes.i || q.palabras[k1].f !== antes.f) falla("corregir en el texto no guardó la palabra con sus tiempos: " + JSON.stringify(q.palabras[k1]));
  const aviso = await p.textContent(".sugerencia").catch(() => "");
  if (!/«calumi» por «Kalumi» en todo el video \(1 vez\)/.test(aviso)) falla("no apareció «¿Cambiar en todo el video?»: " + aviso);
  await p.click('[data-accion="sug-todo"]');
  q = await proyecto();
  if (q.palabras[k2].t !== "Kalumi") falla("«Cambiar en todo el video» no cambió la otra: " + q.palabras[k2].t);
  await p.click('[data-accion="sug-recordar"]');
  await p.waitForFunction(() => { let r; window.Corta._probar((E) => { r = E.vocabulario.reemplazos.length; }); return r === 1; }, null, { timeout: 2000 }).catch(() => falla("«Recordar» no lo dejó en el vocabulario"));
  if (await p.$(".sugerencia")) falla("el aviso no se cerró después de cambiar y recordar");
  else console.log("  ✓ Corregir una palabra mantiene sus tiempos; se cambia en todo el video y se recuerda");
  // Sobre la vista previa: tocar la palabra del subtítulo y escribir dos palabras (se reparten el tiempo)
  await p.evaluate((t) => { document.querySelector("#video").currentTime = t; }, antes.i + 0.05);
  await p.waitForSelector(`[data-sub-w="${k1}"]`, { timeout: 3000 }).catch(() => {});
  if (!(await p.$(`[data-sub-w="${k1}"]`))) console.log("  - Vista previa: este Chromium no muestra el cuadro del video, se prueba solo el texto");
  else {
    await p.click(`[data-sub-w="${k1}"]`);
    await p.fill("#editar-sub", "Kalumi Studio."); await p.keyboard.press("Enter");
    q = await proyecto();
    const [a, b] = q.palabras.slice(k1, k1 + 2);
    if (a.t !== "Kalumi" || b.t !== "Studio." || a.i !== antes.i || b.f !== antes.f || a.f !== b.i) falla("corregir en la vista previa no repartió el tiempo: " + JSON.stringify([a, b]));
    else console.log("  ✓ Sobre la vista previa: tocar la palabra la corrige y dos palabras se reparten su tiempo");
    await p.click('[data-accion="deshacer"]');
    await p.waitForTimeout(150);
    if ((await proyecto()).palabras[k1].t !== "Kalumi.") falla("deshacer no volvió a la corrección anterior");
  }
  // Esc cancela; vacía la quita del subtítulo sin cortar el video
  await p.click(`[data-w="${k1}"]`); await p.click(`[data-w="${k1}"]`);
  await p.fill("#editar-palabra", "otra cosa"); await p.keyboard.press("Escape");
  q = await proyecto();
  if (q.palabras[k1].t !== "Kalumi.") falla("Esc no canceló la corrección");
  const n = q.palabras.length, cortes = JSON.stringify(q.cortes);
  await p.click(`[data-w="${k1}"]`); await p.fill("#editar-palabra", ""); await p.keyboard.press("Enter");  // sigue elegida: un toque basta
  q = await proyecto();
  if (q.palabras.length !== n - 1 || JSON.stringify(q.cortes) !== cortes) falla("dejarla vacía no la quitó solo del subtítulo");
  // Separar la frase después de una palabra
  await p.click('[data-w="1"]');
  await p.click('[data-accion="linea-sel"]');
  q = await proyecto();
  if (!["fin", "sigue"].includes(q.palabras[1].linea)) falla("separar o unir no marcó la palabra: " + JSON.stringify(q.palabras[1]));
  else console.log(`  ✓ Esc cancela, vacía sale del subtítulo y la frase se ${q.palabras[1].linea === "fin" ? "separa" : "une"} a mano`);
  // Ajustes: el vocabulario se ve y se borra
  await p.evaluate(() => window.Corta._probar((E) => { E.ajustes = true; }));
  const fila = await p.textContent(".dialogo").catch(() => "");
  if (!/calumi\s*→\s*Kalumi/.test(fila)) falla("Ajustes no muestra el vocabulario");
  await p.click("[data-vocab-quitar]");
  await p.waitForFunction(() => !document.querySelector("[data-vocab-quitar]"), null, { timeout: 2000 }).catch(() => falla("Quitar del vocabulario no lo borró"));
  await p.fill("#vocab-nueva", "Kalumi"); await p.keyboard.press("Enter");
  await p.waitForSelector(".chip-vocab", { timeout: 2000 }).then(() => console.log("  ✓ Ajustes: el vocabulario se ve, se borra y se agregan palabras")).catch(() => falla("no se agregó la palabra al vocabulario"));
  await p.close();
}

// 10) Cambios de la IA: cada tarjeta quita justo lo que hizo ese cambio, aunque después se siga editando
{
  const p = await navegador.newPage({ viewport: { width: 1360, height: 860 } });
  p.on("pageerror", (e) => falla("error de JavaScript (quitar un cambio de la IA): " + e.message));
  await p.goto(BASE + "?idioma=es"); await p.waitForSelector(".app");
  const proyecto = () => p.evaluate(() => { let r; window.Corta._probar((E) => { r = JSON.parse(JSON.stringify(E.proyectos[0].proyecto)); }); return r; });
  // Lógica: lo que la persona cambió a mano se conserva; un ajuste que ella volvió a cambiar, también
  const malos = await p.evaluate(() => {
    const P = window.Corta._pruebas, m = [], z = (i, o) => ({ i, f: i + 1, escala: 1.3, ...(o ? { origen: o } : {}) });
    const q = { palabras: [{ t: "Kalumi", i: 0, f: 1 }], cortes: [{ i: 5, f: 6, motivo: "manual" }], zooms: [z(1, "ia-a"), z(3, "ia-a"), z(8), z(10, "ia-b")], textos: [], lienzo: "1:1",
      subtitulos: { estilo: "neon" }, cambios_ia: [{ id: "ia-a", estado: "aplicado", agregados: { zooms: [z(1, "ia-a"), z(3, "ia-a")] }, ajustes: [{ campo: "lienzo", antes: "9:16", despues: "1:1" }],
        palabras: [{ antes: [{ t: "calumi", i: 0, f: 1 }], despues: [{ t: "Kalumi", i: 0, f: 1 }] }] },
      { id: "ia-b", estado: "aplicado", agregados: { zooms: [z(10, "ia-b")] }, ajustes: [{ campo: "subtitulos.estilo", antes: "pop", despues: "caja" }] }] };
    q.zooms[1].f = 4.5;  // la persona alargó uno de los zooms de la IA
    const r = P.quitarCambioIA(q, "ia-a");
    if (JSON.stringify(r) !== JSON.stringify({ quitados: 3, conservados: 1 })) m.push("resultado " + JSON.stringify(r));
    if (JSON.stringify(q.zooms) !== JSON.stringify([{ i: 3, f: 4.5, escala: 1.3 }, z(8), z(10, "ia-b")])) m.push("zooms " + JSON.stringify(q.zooms));
    if (q.lienzo !== "9:16" || q.palabras[0].t !== "calumi" || q.cambios_ia[0].estado !== "quitado") m.push("ajustes o palabras");
    if (P.quitarCambioIA(q, "ia-a") !== null) m.push("quitar dos veces");
    const r2 = P.quitarCambioIA(q, "ia-b");
    if (r2.conservados !== 1 || q.subtitulos.estilo !== "neon" || q.zooms.length !== 2) m.push("estilo cambiado después por la persona " + JSON.stringify([r2, q.subtitulos]));
    if (P.textoQueCabe("hola mundo", 4, "11px sans-serif") !== "" || !/^hola…$/.test(P.textoQueCabe("hola mundo grande y largo", 52, "11px sans-serif"))) m.push("textoQueCabe");
    return m;
  });
  malos.forEach((x) => falla("quitar un cambio de la IA: " + x));
  // En la interfaz: pedir zooms (IA simulada), editar a mano después y quitar solo los zooms de la IA
  await p.click('[data-pestana="ia"]');
  await p.fill("#pedido-ia", "Pon zoom cuando digo algo importante"); await p.click('[data-accion="pedir-ia"]');
  await p.waitForSelector("[data-quitar-ia]", { timeout: 4000 });
  const etiqueta = await p.textContent("[data-quitar-ia]");
  await p.evaluate(() => window.Corta._probar((E) => { E.proyectos[0].proyecto.cortes.push({ i: 20, f: 21, motivo: "manual" }); E.proyectos[0].proyecto.lienzo = "4:5"; }));
  await p.click("[data-quitar-ia]");
  const q = await proyecto();
  if (etiqueta.trim() !== "Quitar estos 3 zooms") falla("el botón no dice qué quita: " + etiqueta);
  else if (q.zooms.length || !q.cortes.some((c) => c.i === 20) || q.lienzo !== "4:5" || q.cambios_ia[0].estado !== "quitado") falla("quitar el cambio tocó otra cosa: " + JSON.stringify([q.zooms, q.cortes, q.lienzo]));
  else if (!(await p.textContent(".historial-ia")).includes("Quitado")) falla("la tarjeta no quedó como «Quitado»");
  else if (!malos.length) console.log("  ✓ Quitar un cambio de la IA quita justo lo suyo (aunque hayas seguido editando) y conserva lo que cambiaste a mano");
  // Línea de tiempo: la pista de subtítulos nunca muestra letras sueltas
  await p.evaluate(() => window.Corta._probar((E) => { E.proyectos[0].proyecto.subtitulos.palabras_por_linea = 1; }));
  const etiquetas = await p.$$eval(".pista-subtitulos .etq", (els) => els.map((e) => e.textContent));
  const rotas = etiquetas.filter((t) => t && !/^\S{2,}/.test(t.replace("…", "")));
  if (rotas.length) falla("la pista de subtítulos muestra pedazos ilegibles: " + rotas.join(" | "));
  else console.log(`  ✓ Pista de subtítulos legible (${etiquetas.filter(Boolean).length} de ${etiquetas.length} frases caben)`);
  await p.close();
}

// 11) Cortes y efectos: dividir, ponerle un efecto a un tramo, borrarlo, la vista previa y el catálogo de la comunidad
{
  const p = await navegador.newPage({ viewport: { width: 1360, height: 860 } });
  p.on("pageerror", (e) => falla("error de JavaScript (cortes y efectos): " + e.message));
  await p.goto(BASE + "?idioma=es"); await p.waitForSelector(".app");
  const proyecto = () => p.evaluate(() => { let r; window.Corta._probar((E) => { r = JSON.parse(JSON.stringify(E.proyectos[0].proyecto)); }); return r; });
  const ir = (t) => p.evaluate((x) => { document.querySelector("#video").currentTime = x; }, t);
  // Dividir en el cabezal (botón y ⌘B) y elegir el tramo
  await ir(10); await p.waitForTimeout(150);
  // El Chromium de Playwright en GitHub no trae H.264: sin video no hay cabezal que mover; se prueba lo demás.
  const conVideo = await p.evaluate(() => Math.abs(document.querySelector("#video").currentTime - 10) < 0.1 && document.querySelector("#video").readyState >= 1);
  if (conVideo) {
    await p.click('[data-accion="dividir"]');
    await ir(20); await p.waitForTimeout(150);
    await p.keyboard.press("Control+b");
  } else {
    console.log("  - Dividir: este Chromium no reproduce H.264, las divisiones se ponen a mano");
    await p.evaluate(() => window.Corta._probar((E) => { E.proyectos[0].proyecto.divisiones = [10, 20]; }));
  }
  let q = await proyecto();
  const div = q.divisiones || [];
  if (div.length !== 2 || Math.abs(div[0] - 10) > 0.05 || Math.abs(div[1] - 20) > 0.05) falla("dividir no dejó las divisiones: " + JSON.stringify(div));
  else console.log("  ✓ Dividir en el cabezal (botón y ⌘B)");
  // Un efecto solo en el tramo del medio
  await p.click('.b-tramo[data-k="1"]');
  await p.click('#lt-sel [data-pestana="efectos"]');
  if (!(await p.textContent(".fx-destino").catch(() => "")).includes("0:10,0 a 0:20,0")) falla("el panel de efectos no dice a qué tramo se aplica");
  await p.click('[data-fx="blanco-y-negro"]');
  q = await proyecto();
  const ap = q.efectos?.[0];
  if (!ap || ap.efecto !== "blanco-y-negro" || Math.abs(ap.i - 10) > 0.05 || Math.abs(ap.f - 20) > 0.05 || !Array.isArray(ap.pasos)) falla("el efecto no quedó en el tramo: " + JSON.stringify(q.efectos));
  // Vista previa: dentro del tramo el video lleva el filtro de CSS; fuera, no
  await ir(15); await p.waitForTimeout(150);
  const dentro = await p.evaluate(() => document.querySelector("#capa-zoom").style.filter);
  await ir(5); await p.waitForTimeout(150);
  const fuera = await p.evaluate(() => document.querySelector("#capa-zoom").style.filter);
  if (!conVideo) console.log("  - Vista previa de efectos: sin H.264 no se prueba");
  else if (!/grayscale\(1\)/.test(dentro) || fuera) falla(`la vista previa no aplica el efecto solo en su tramo: «${dentro}» / «${fuera}»`);
  else console.log("  ✓ Efecto en un tramo: se guarda con sus pasos y la vista previa lo muestra solo ahí");
  // Fundido de entrada a todo el video: capa negra que se va
  await p.click('[data-accion="fx-todo"]');
  await p.click('[data-fx="fundido-entrada"]');
  await ir(0.05); await p.waitForTimeout(150);
  const capa = await p.evaluate(() => Number(document.querySelector("#capas-fx i")?.style.opacity || 0));
  if (conVideo && !(capa > 0.8)) falla("el fundido de entrada no se ve en la vista previa: " + capa);
  // Quitar el efecto del panel y borrar el tramo (queda como corte manual)
  await p.click('[data-quitar-fx="1"]');
  q = await proyecto();
  if (q.efectos.length !== 1) falla("quitar el efecto no lo quitó");
  await p.click('.b-tramo[data-k="1"]');
  await p.click('[data-tramo="borrar"]');
  q = await proyecto();
  if (!q.cortes.some((c) => c.motivo === "manual" && Math.abs(c.i - 10) < 0.05 && Math.abs(c.f - 20) < 0.05)) falla("borrar el tramo no lo cortó: " + JSON.stringify(q.cortes));
  else console.log("  ✓ Borrar un tramo lo deja como corte (se puede volver a poner) y el fundido se ve en la vista previa");
  // Recortar el inicio de un tramo hasta el cabezal
  await p.click('.b-tramo[data-k="0"]');
  await ir(3); await p.waitForTimeout(100);
  await p.click('[data-tramo="inicio"]');
  q = await proyecto();
  if (conVideo && !q.cortes.some((c) => c.i === 0 && Math.abs(c.f - 3) < 0.05)) falla("recortar el inicio no cortó hasta el cabezal: " + JSON.stringify(q.cortes));
  // Catálogo de la comunidad (simulado): abrir, buscar, descargar y usar
  await p.click('[data-accion="explorar-fx"]');
  await p.waitForSelector("[data-bajar-fx]", { timeout: 3000 });
  await p.fill("#buscar-cat", "noche");
  const encontrados = await p.$$eval("[data-bajar-fx]", (els) => els.map((e) => e.dataset.bajarFx));
  if (encontrados.join() !== "neon") falla("buscar en el catálogo: " + encontrados.join());
  await p.click('[data-bajar-fx="neon"]');
  await p.waitForFunction(() => { let r; window.Corta._probar((E) => { r = E.efectos.some((x) => x.id === "neon" && x.origen === "descargado"); }); return r; }, null, { timeout: 3000 })
    .then(() => console.log("  ✓ Catálogo: buscar y descargar un efecto lo deja listo para usar"))
    .catch(() => falla("descargar del catálogo no dejó el efecto disponible"));
  await p.keyboard.press("Escape");
  await p.click('[data-fx-cat="filtro"]');
  if (!(await p.$('[data-fx="neon"]'))) falla("el efecto descargado no aparece en su categoría");
  await p.close();
}

// 12) Plantillas: abrir, elegir una por categoría, llenar sus huecos con los clips «elegidos», abrir el proyecto y mover un hueco
const antesPlantillas = errores.length;
for (const [modo, opciones] of [["celular", { viewport: { width: 390, height: 844 }, colorScheme: "light" }], ["escritorio", { viewport: { width: 1360, height: 860 } }]]) {
  const p = await navegador.newPage(opciones);
  p.on("pageerror", (e) => falla(`error de JavaScript (plantillas, ${modo}): ` + e.message));
  const fotos = process.env.CAPTURAS_PLANTILLAS || "";
  const foto = async (n) => { if (fotos) await p.screenshot({ path: path.join(fotos, `plantillas-${modo}-${n}.png`) }); };
  await p.goto(BASE + "?idioma=es"); await p.waitForFunction(() => window.Corta && document.querySelector(".app"));
  await p.click(modo === "celular" ? '.barra [data-accion="plantillas"]' : '.lateral [data-accion="plantillas"]');
  await p.waitForSelector(".galeria-pl");
  await p.waitForTimeout(700);
  await foto("1-galeria");
  await p.click('[data-pl-cat="tutorial"]');
  const ids = await p.$$eval("[data-ver-pl]:not([data-ver-pl=''])", (els) => els.map((e) => e.dataset.verPl));
  if (ids.join() !== "receta-rapida,tutorial-3-pasos") falla(`categoría Tutoriales (${modo}): ` + ids.join());
  await p.click('[data-ver-pl="receta-rapida"]');
  await p.waitForSelector("[data-elegir-clips]");
  await p.waitForTimeout(1200);
  await foto("2-detalle");
  if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla("el detalle de una plantilla se sale a 390 px");
  await p.click("[data-elegir-clips]");
  await p.waitForSelector('[data-pestana="clips"][aria-selected="true"]', { timeout: 4000 }).catch(() => falla(`elegir clips no abrió el proyecto en Clips (${modo})`));
  const q = await p.evaluate(() => { let r; window.Corta._probar((E) => { r = JSON.parse(JSON.stringify(E.proyectos.find((x) => x.carpeta === E.sel).proyecto)); }); return r; });
  const ok = q.plantilla?.id === "receta-rapida" && q.plantilla.huecos.length === 5 && q.plantilla.huecos[0].tipo === "foto"
    && JSON.stringify(q.divisiones) === "[3,6,9,12]" && q.textos.length === 5 && q.textos[0].texto === "Ingredientes"
    && q.efectos.some((e) => e.efecto === "destello" && e.i === 2.5 && e.f === 3.5) && q.subtitulos.estilo === "caja" && q.fuente.duracion === 15;
  if (!ok) falla(`el proyecto de la plantilla no quedó bien (${modo}): ` + JSON.stringify({ pl: q.plantilla, d: q.divisiones, t: q.textos, e: q.efectos }).slice(0, 600));
  const filas = await p.$$eval(".hueco-fila", (els) => els.length);
  if (filas !== 5) falla(`el panel Clips no muestra los 5 huecos (${modo}): ${filas}`);
  await p.waitForTimeout(600);
  await foto("3-clips");
  // Mover la barra de un hueco de video vuelve a armar ese hueco (aquí, simulado) y queda en el proyecto
  const barra = await p.$('[data-hueco-desde="1"]');
  await barra.evaluate((el) => { el.value = 7.5; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); });
  await p.waitForFunction(() => { let r; window.Corta._probar((E) => { r = !E.armando && E.proyectos.find((x) => x.carpeta === E.sel).proyecto.plantilla.huecos[1].desde === 7.5; }); return r; }, null, { timeout: 3000 })
    .catch(() => falla(`mover la barra del hueco no cambió desde dónde se usa el clip (${modo})`));
  // Es un proyecto normal: la línea de tiempo tiene un tramo por hueco y se puede deshacer
  const tramos = await p.$$eval(".b-tramo", (els) => els.length);
  if (tramos !== 5) falla(`la línea de tiempo no tiene un tramo por hueco (${modo}): ${tramos}`);
  if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla("el proyecto de plantilla se sale a 390 px");
  await p.close();
}
if (errores.length === antesPlantillas) console.log("  ✓ Plantillas: categoría, detalle, elegir clips, proyecto con sus huecos, efectos y textos, y mover un hueco (celular y escritorio)");

// 8) Primer uso: lo primero es el idioma, antes que cualquier otra cosa
for (const [esquema, ancho] of [["light", 1360], ["dark", 390]]) {
  const p = await navegador.newPage({ viewport: { width: ancho, height: 844 }, colorScheme: esquema, locale: "es-CL" });
  p.on("pageerror", (e) => falla("error de JavaScript (idioma): " + e.message));
  await p.goto(BASE + "?bienvenida"); await p.waitForSelector(".capa");
  const primera = await p.evaluate(() => ({
    titulo: document.querySelector("#t-bv")?.textContent.replace(/\s+/g, " ").trim(), detras: !!document.querySelector(".app, video"),
    opciones: [...document.querySelectorAll("[data-elegir-idioma]")].map((b) => b.querySelector("b").textContent), foco: document.activeElement?.id,
    ancho: document.documentElement.scrollWidth }));
  if (primera.titulo !== "Elige tu idioma · Choose your language" || primera.detras || primera.opciones.join() !== "Español,English")
    falla("la primera pantalla de la bienvenida no es la del idioma: " + JSON.stringify(primera));
  else if (primera.foco !== "idioma-es") falla("el idioma del sistema no quedó enfocado: " + primera.foco);
  else if (primera.ancho > ancho + 2) falla(`la pantalla del idioma se sale a ${ancho}px (${primera.ancho}px)`);
  // Con teclado: Tab hasta «English» (foco visible) y Enter
  await p.keyboard.press("Tab");
  const foco = await p.evaluate(() => [document.activeElement?.id, getComputedStyle(document.activeElement).outlineStyle]);
  if (foco[0] !== "idioma-en" || foco[1] === "none") falla("Tab no llevó a «English» con foco visible: " + JSON.stringify(foco));
  await p.keyboard.press("Enter");
  await p.waitForFunction(() => document.querySelector("#t-bv")?.textContent === "Hi, this is Corta", null, { timeout: 3000 })
    .catch(() => falla("después de elegir English el siguiente paso no salió en inglés"));
  const despues = await p.evaluate(() => ({ guardado: window.Corta._pruebas.demoConfig()?.idioma_ui, lang: document.documentElement.lang,
    boton: document.querySelector('.pie-dialogo [data-bv="2"]')?.textContent }));
  if (despues.guardado !== "en" || despues.lang !== "en" || despues.boton !== "Next") falla("elegir English no guardó idioma_ui o no cambió la app: " + JSON.stringify(despues));
  else if (esquema === "light") console.log("  ✓ Primer uso: lo primero es el idioma; con teclado se elige English, se guarda idioma_ui y lo que sigue sale en inglés");
  await p.close();
}
{
  const p = await navegador.newPage();
  await p.goto(BASE); await p.waitForSelector(".app");
  if (await p.$(".capa")) falla("con la bienvenida ya hecha se volvió a mostrar"); else console.log("  ✓ Con la bienvenida ya hecha no se repite");
  await p.close();
}

// 5) Contraste del botón principal
for (const esquema of ["light", "dark"]) {
  const p = await navegador.newPage({ colorScheme: esquema });
  await p.goto(BASE); await p.waitForSelector(".boton.principal");
  const c = await p.evaluate(() => {
    const lum = (s) => { const [r, g, b] = s.match(/[\d.]+/g).slice(0, 3).map((x) => { x = x / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const cs = getComputedStyle(document.querySelector(".boton.principal")); const a = lum(cs.color), b = lum(cs.backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
  if (c < 4.5) falla(`contraste del botón principal en modo ${esquema}: ${c.toFixed(2)} (mínimo 4.5)`);
  else console.log(`  ✓ Contraste en modo ${esquema === "light" ? "claro" : "oscuro"}: ${c.toFixed(2)}`);
  await p.close();
}
await navegador.close();
servidor.close();
if (errores.length) { console.log(`\n✗ ${errores.length} problemas`); process.exit(1); }
console.log("✓ Interfaz OK");
