// Ícono de la app de Mac (app/Corta.icns) desde docs/favicon.svg. Solo para desarrollo: Playwright dibuja el logo a 1024 px con la
// rejilla de íconos de macOS (824 px centrado, con sombra) y Pillow arma el .icns.
// Uso: node herramientas/generar_icono.mjs   (PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí)
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const svg = fs.readFileSync(path.join(RAIZ, "docs", "favicon.svg"), "utf8").replace("<svg ", '<svg width="824" height="824" ');
const png = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "corta-icono-")), "1024.png");
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1024, height: 1024 } });
await p.setContent(`<body style="margin:0;background:transparent"><div style="width:1024px;height:1024px;display:flex;align-items:center;justify-content:center">
  <div style="width:824px;height:824px;filter:drop-shadow(0 10px 14px rgba(0,0,0,.28))">${svg}</div></div></body>`);
await p.screenshot({ path: png, omitBackground: true });
await b.close();
execFileSync("python3", ["-c", `from PIL import Image
Image.open(${JSON.stringify(png)}).convert("RGBA").save(${JSON.stringify(path.join(RAIZ, "app", "Corta.icns"))}, sizes=[(16,16),(32,32),(64,64),(128,128),(256,256),(512,512),(1024,1024)])`]);
console.log("Listo: app/Corta.icns");
