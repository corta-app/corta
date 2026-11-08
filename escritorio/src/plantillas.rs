//! Plantillas: la persona elige sus clips o fotos (van a los huecos en orden de nombre) y bin/plantillas.py arma el video. Las fotos
//! HEIC/HEIF (las del iPhone) se pasan antes a JPEG: ffmpeg no siempre las lee. Lo mismo que hacía `Plantillas` en CortaApp.swift.

use crate::pieza::host::Host;
use crate::pieza::procesador::Opciones;
use crate::{con_error, entero, proyecto, responder};
use serde_json::{json, Value};
use std::cmp::Ordering;
use std::path::{Path, PathBuf};

/// Videos y fotos que acepta una plantilla.
pub const CLIPS: [&str; 11] = ["mp4", "mov", "m4v", "webm", "mkv", "jpg", "jpeg", "png", "webp", "heic", "heif"];

pub fn registrar(host: &Host) {
    host.registrar("elegirClips", |d, h, _| elegir_clips(h, &d));
    host.registrar("ajustarHueco", |d, h, _| ajustar_hueco(h, &d));
    host.registrar("cambiarClip", |d, h, _| cambiar_clip(h, &d));
}

fn no(h: &Host, texto: &str) {
    responder(h, "plantillaArmada", json!({"ok": false, "error": h.t(texto)}));
}

/// Un id de plantilla: minúsculas, números y guiones, 2 a 40.
pub fn id_valido(id: &str) -> bool {
    let b = id.as_bytes();
    let bueno = |c: &u8| c.is_ascii_lowercase() || c.is_ascii_digit();
    (2..=40).contains(&b.len()) && bueno(&b[0]) && bueno(&b[b.len() - 1]) && b.iter().all(|c| bueno(c) || *c == b'-')
}

fn elegir_clips(h: &Host, d: &Value) {
    let id = d["plantilla"].as_str().unwrap_or("");
    if !id_valido(id) {
        return no(h, "No encontré esa plantilla.");
    }
    let n = entero(&d["n"]).unwrap_or(1).clamp(1, 20);
    let titulo = h.f("Elige {n} clips o fotos. Van en orden de nombre; después puedes cambiar cada uno.", &json!({"n": n.to_string()}));
    let mut urls = h.dialogo_archivos(Some(titulo), &CLIPS, true, None);
    if urls.is_empty() {
        return responder(h, "plantillaArmada", json!({"ok": false}));
    }
    urls.sort_by(|a, b| natural(&nombre(a), &nombre(b)));
    armar(h, json!({"accion": "crear", "plantilla": id, "idioma": h.codigo_idioma()}), &urls);
}

fn ajustar_hueco(h: &Host, d: &Value) {
    let desde = d["desde"].as_f64().filter(|x| x.is_finite() && !d["desde"].is_boolean());
    let (Some(carpeta), Some(hueco), Some(desde)) = (proyecto(h, &d["carpeta"]), entero(&d["hueco"]), desde) else {
        return no(h, "Ese hueco no existe.");
    };
    armar(h, json!({"accion": "ajustar", "carpeta": carpeta, "hueco": hueco, "desde": desde}), &[]);
}

fn cambiar_clip(h: &Host, d: &Value) {
    let (Some(carpeta), Some(hueco)) = (proyecto(h, &d["carpeta"]), entero(&d["hueco"])) else { return no(h, "Ese hueco no existe.") };
    let titulo = h.t("Elige otro clip o foto para este hueco");
    let Some(u) = h.dialogo_archivos(Some(titulo), &CLIPS, false, None).into_iter().next() else {
        return responder(h, "plantillaArmada", json!({"ok": false}));
    };
    armar(h, json!({"accion": "cambiar", "carpeta": carpeta, "hueco": hueco}), &[u]);
}

/// Corre bin/plantillas.py (crear, ajustar o cambiar) con los archivos elegidos y responde `plantillaArmada`. Las fotos HEIC van
/// antes a JPEG en una carpeta temporal (se borra al terminar). Mientras arma, la app cuenta como ocupada.
fn armar(h: &Host, datos: Value, urls: &[PathBuf]) {
    let mut x = datos;
    let tmp = std::env::temp_dir().join(format!("corta-clips-{}", crate::pieza::enchufe::aleatorio_hex(8)));
    let mut rutas: Vec<String> = Vec::new();
    for u in urls {
        let ext = u.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
        if ext == "heic" || ext == "heif" {
            match a_jpeg(u, &tmp) {
                Some(j) => rutas.push(j.to_string_lossy().into_owned()),
                None => {
                    let _ = std::fs::remove_dir_all(&tmp);
                    return no(h, "No pude leer esa foto.");
                }
            }
        } else {
            rutas.push(u.to_string_lossy().into_owned());
        }
    }
    if x["accion"] == "crear" {
        x["archivos"] = json!(rutas);
    } else if let Some(r) = rutas.first() {
        x["archivo"] = json!(r);
    }
    h.ocupar();
    let r = h.fila.agregar(|| h.procesador.con_entrada("plantillas.py", &["entrada".into()], x, Opciones { latido: true, ..Default::default() }));
    let _ = std::fs::remove_dir_all(&tmp);
    h.soltar_ocupada();
    responder(h, "plantillaArmada", con_error(h, r, "No pude armar el video."));
}

fn nombre(p: &Path) -> String {
    p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()
}

/// Orden como el Finder: sin mayúsculas y los números por su valor («clip 2» antes que «clip 10»).
pub fn natural(a: &str, b: &str) -> Ordering {
    let (a, b) = (a.to_lowercase(), b.to_lowercase());
    let (mut x, mut y) = (a.chars().peekable(), b.chars().peekable());
    loop {
        match (x.peek().copied(), y.peek().copied()) {
            (None, None) => return a.cmp(&b),
            (None, _) => return Ordering::Less,
            (_, None) => return Ordering::Greater,
            (Some(c), Some(d)) if c.is_ascii_digit() && d.is_ascii_digit() => {
                let mut n = String::new();
                while let Some(c) = x.peek().copied().filter(char::is_ascii_digit) {
                    n.push(c);
                    x.next();
                }
                let mut m = String::new();
                while let Some(d) = y.peek().copied().filter(char::is_ascii_digit) {
                    m.push(d);
                    y.next();
                }
                let (n, m) = (n.trim_start_matches('0'), m.trim_start_matches('0'));
                let o = n.len().cmp(&m.len()).then_with(|| n.cmp(m));
                if o != Ordering::Equal {
                    return o;
                }
            }
            (Some(c), Some(d)) => {
                if c != d {
                    return c.cmp(&d);
                }
                x.next();
                y.next();
            }
        }
    }
}

/// ImageIO por JavaScript for Automation (viene con macOS): la foto como JPEG con su orientación aplicada, hasta 4096 px de lado.
/// Recibe las dos rutas como argumentos (nunca dentro del guion).
#[cfg(target_os = "macos")]
const A_JPEG: &str = r#"ObjC.import("ImageIO");
function run(a) {
  const f = $.CGImageSourceCreateWithURL($.NSURL.fileURLWithPath(a[0]), $());
  if (!f) return "no";
  const op = $.NSMutableDictionary.alloc.init;
  op.setObjectForKey($.NSNumber.numberWithBool(true), "kCGImageSourceCreateThumbnailFromImageAlways");
  op.setObjectForKey($.NSNumber.numberWithBool(true), "kCGImageSourceCreateThumbnailWithTransform");
  op.setObjectForKey($.NSNumber.numberWithInt(4096), "kCGImageSourceThumbnailMaxPixelSize");
  const img = $.CGImageSourceCreateThumbnailAtIndex(f, 0, op);
  if (!img) return "no";
  const s = $.CGImageDestinationCreateWithURL($.NSURL.fileURLWithPath(a[1]), $("public.jpeg"), 1, $());
  if (!s) return "no";
  const q = $.NSMutableDictionary.alloc.init;
  q.setObjectForKey($.NSNumber.numberWithDouble(0.92), "kCGImageDestinationLossyCompressionQuality");
  $.CGImageDestinationAddImage(s, img, q);
  return $.CGImageDestinationFinalize(s) ? "ok" : "no";
}"#;

/// Una foto HEIC/HEIF como JPEG en `carpeta` (0700), o None. Fuera del Mac, la foto queda tal cual (ffmpeg la intenta leer).
fn a_jpeg(u: &Path, carpeta: &Path) -> Option<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        std::fs::create_dir_all(carpeta).ok()?;
        crate::pieza::enchufe::solo_persona(carpeta);
        let base = u.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "foto".into());
        let destino = carpeta.join(format!("{base}-{}.jpg", crate::pieza::enchufe::aleatorio_hex(3)));
        let r = std::process::Command::new("/usr/bin/osascript").args(["-l", "JavaScript", "-e", A_JPEG]).arg(u).arg(&destino).output().ok()?;
        (String::from_utf8_lossy(&r.stdout).trim() == "ok" && destino.is_file()).then_some(destino)
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = carpeta;
        Some(u.to_path_buf())
    }
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn ids() {
        assert!(id_valido("receta-rapida"));
        assert!(id_valido("a1"));
        assert!(!id_valido("a"));
        assert!(!id_valido("-ab"));
        assert!(!id_valido("ab-"));
        assert!(!id_valido("Receta"));
        assert!(!id_valido("../x"));
        assert!(!id_valido(&"a".repeat(41)));
    }

    #[test]
    fn orden_natural() {
        let mut v = vec!["clip 10.mp4", "Clip 2.mp4", "clip 1.mp4", "a.jpg"];
        v.sort_by(|a, b| natural(a, b));
        assert_eq!(v, ["a.jpg", "clip 1.mp4", "Clip 2.mp4", "clip 10.mp4"]);
        assert_eq!(natural("foto-2", "foto-10"), Ordering::Less);
    }
}
