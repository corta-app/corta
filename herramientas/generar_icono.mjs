// Íconos de la app (escritorio/iconos/) desde docs/favicon.svg. Solo para desarrollo, cuando cambia el logo.
//   icon.icns (Mac): el logo a 1024 px con la rejilla de íconos de macOS (824 px centrado, con sombra); Pillow arma el .icns.
//   icon.ico (Windows) y los PNG que pide Tauri (32x32, 128x128, 128x128@2x, icono.png): el logo entero, sin margen.
// Uso: node herramientas/generar_icono.mjs   (PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí; necesita Pillow)
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIR = path.join(RAIZ, "escritorio", "iconos");
fs.mkdirSync(DIR, { recursive: true });
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const logo = fs.readFileSync(path.join(RAIZ, "docs", "favicon.svg"), "utf8").replace("<svg ", '<svg width="100%" height="100%" ');
const b = await chromium.launch();
const p = await b.newPage();

// Mac: 1024 px con la rejilla de macOS y sombra → .icns con Pillow (como siempre).
const png1024 = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "corta-icono-")), "1024.png");
await p.setViewportSize({ width: 1024, height: 1024 });
await p.setContent(`<body style="margin:0;background:transparent"><div style="width:1024px;height:1024px;display:flex;align-items:center;justify-content:center">
  <div style="width:824px;height:824px;filter:drop-shadow(0 10px 14px rgba(0,0,0,.28))">${logo}</div></div></body>`);
await p.screenshot({ path: png1024, omitBackground: true });
execFileSync("python3", ["-c", `from PIL import Image
Image.open(${JSON.stringify(png1024)}).convert("RGBA").save(${JSON.stringify(path.join(DIR, "icon.icns"))}, sizes=[(16,16),(32,32),(64,64),(128,128),(256,256),(512,512),(1024,1024)])`]);

// Windows y Linux: el logo entero.
const planos = {};
for (const lado of [16, 24, 32, 48, 64, 128, 256, 512]) {
  await p.setViewportSize({ width: lado, height: lado });
  await p.setContent(`<html><body style="margin:0;width:${lado}px;height:${lado}px;overflow:hidden;background:transparent"><div style="width:${lado}px;height:${lado}px">${logo}</div></body></html>`);
  planos[lado] = await p.screenshot({ omitBackground: true });
}
await b.close();
for (const [lado, nombre] of [[32, "32x32.png"], [128, "128x128.png"], [256, "128x128@2x.png"], [512, "icono.png"]]) fs.writeFileSync(path.join(DIR, nombre), planos[lado]);
// ICO con PNG adentro (Windows Vista en adelante): cabecera, una entrada de 16 bytes por tamaño y los PNG.
const lados = [16, 24, 32, 48, 64, 128, 256];
const ico = [Buffer.from([0, 0, 1, 0, lados.length, 0])];
let lugar = 6 + 16 * lados.length;
for (const lado of lados) {
  const e = Buffer.alloc(16);
  e.writeUInt8(lado % 256, 0); e.writeUInt8(lado % 256, 1); e.writeUInt16LE(1, 4); e.writeUInt16LE(32, 6);
  e.writeUInt32LE(planos[lado].length, 8); e.writeUInt32LE(lugar, 12);
  ico.push(e); lugar += planos[lado].length;
}
fs.writeFileSync(path.join(DIR, "icon.ico"), Buffer.concat([...ico, ...lados.map((l) => planos[l])]));
console.log("Listo: escritorio/iconos/ (icon.icns, icon.ico y PNG)");
