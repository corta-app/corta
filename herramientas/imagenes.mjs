// Genera las imágenes de la página (docs/img, docs/apple-touch-icon.png) con la interfaz y el video ficticio de la demo.
// Uso: PLAYWRIGHT=/ruta/a/playwright node herramientas/imagenes.mjs
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".mp4": "video/mp4", ".ttf": "font/ttf", ".jpg": "image/jpeg" };
function servir(q, r, ruta, tipo) {
  const total = fs.statSync(ruta).size, m = /bytes=(\d*)-(\d*)/.exec(q.headers.range || "");
  if (!m) { r.writeHead(200, { "Content-Type": tipo, "Content-Length": total, "Accept-Ranges": "bytes" }); return fs.createReadStream(ruta).pipe(r); }
  const i = m[1] ? Number(m[1]) : 0, f = m[2] ? Number(m[2]) : total - 1;
  r.writeHead(206, { "Content-Type": tipo, "Content-Range": `bytes ${i}-${f}/${total}`, "Content-Length": f - i + 1, "Accept-Ranges": "bytes" });
  fs.createReadStream(ruta, { start: i, end: f }).pipe(r);
}
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(RAIZ) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  servir(q, r, ruta, tipos[path.extname(ruta)] || "application/octet-stream");
}).listen(0);
const URL_BASE = `http://localhost:${servidor.address().port}`;
const IMG = path.join(RAIZ, "docs", "img");
fs.mkdirSync(IMG, { recursive: true });
const navegador = await chromium.launch();

// Captura del editor en modo oscuro, con subtítulos en pantalla.
const p = await navegador.newPage({ viewport: { width: 1360, height: 820 }, colorScheme: "dark" });
await p.goto(`${URL_BASE}/ui/index.html?idioma=es`);
await p.waitForFunction(() => document.querySelector("#video")?.readyState >= 2);
await p.evaluate(() => { window.Corta._probar((E) => { E.seleccion = null; }); document.querySelector('[data-accion="limpiar"]').click(); });
await p.waitForTimeout(900);
await p.evaluate(() => { document.querySelector("#video").currentTime = 5.6; });
await p.waitForTimeout(900);
await p.screenshot({ path: path.join(IMG, "editor.png") });
await p.close();

const svg = fs.readFileSync(path.join(RAIZ, "ui", "favicon.svg"), "utf8");
for (const [lado, destino] of [[512, path.join(IMG, "logo.png")], [180, path.join(RAIZ, "docs", "apple-touch-icon.png")]]) {
  const q = await navegador.newPage({ viewport: { width: lado, height: lado } });
  await q.setContent(`<style>html,body{margin:0;background:#111214}svg{width:${lado}px;height:${lado}px;display:block}</style>${svg.replace('rx="15"', 'rx="0"')}`);
  await q.screenshot({ path: destino });
  await q.close();
}
// Imagen para compartir (1200×630)
const cuadro = fs.readFileSync(path.join(IMG, "despues.jpg")).toString("base64");
const c = await navegador.newPage({ viewport: { width: 1200, height: 630 } });
await c.setContent(`<style>
  body{margin:0;width:1200px;height:630px;background:radial-gradient(55% 80% at 80% 20%,#2d3a0c 0%,transparent 60%),#0d0e10;color:#f4f4f0;font-family:-apple-system,"Segoe UI",system-ui,sans-serif;overflow:hidden;position:relative}
  .txt{position:absolute;left:64px;top:72px;width:620px}
  .marca{display:flex;align-items:center;gap:14px;font-size:34px;font-weight:800}.marca svg{width:58px;height:58px}
  h1{font-size:58px;line-height:1.02;margin:34px 0 18px;letter-spacing:-.02em}h1 em{font-style:normal;color:#c6f432}
  p{font-size:23px;color:#9a9ca3;margin:0;line-height:1.4}
  .chips{margin-top:28px;display:flex;gap:10px}.chips span{font-size:17px;padding:7px 14px;border-radius:99px;border:1px solid #2a2c31}
  .tel{position:absolute;right:90px;top:40px;width:310px;height:551px;border-radius:30px;overflow:hidden;box-shadow:0 30px 90px rgba(0,0,0,.7),0 0 0 8px #1d1f23}
  .tel img{width:100%;height:100%;object-fit:cover}
</style><div class="txt"><div class="marca">${svg}<span>Corta</span></div>
<h1>Editas el texto, <em>se edita el video</em></h1><p>Subtítulos animados, sin silencios y tu propia IA. Para Shorts, Reels y TikTok.</p>
<div class="chips"><span>Gratis</span><span>Código abierto</span><span>Sin marca de agua</span></div></div>
<div class="tel"><img src="data:image/jpeg;base64,${cuadro}"></div>`);
await c.screenshot({ path: path.join(IMG, "compartir.png") });
await navegador.close();
servidor.close();
console.log("✓ Imágenes en docs/img");
