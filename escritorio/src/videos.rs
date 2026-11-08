//! Un video nuevo (elegido, soltado o desde el menú), la música de fondo y los trabajos largos: transcribir y exportar. El avance
//! lo dejan los scripts en <carpeta>/estado.json y llega a la interfaz cada medio segundo. Los scripts no tienen tope de tiempo
//! mientras laten (pieza «trabajos», `mantener_vivo`): si dejan de latir, el host los corta; al salir de la app, también.
//! Lo mismo que hacían `Corta` y `Trabajos` en CortaApp.swift.

use crate::pieza::host::Host;
use crate::pieza::procesador::Opciones;
use crate::{avisar, con_error, entero, proyecto, responder};
use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

pub const VIDEOS: [&str; 5] = ["mp4", "mov", "m4v", "webm", "mkv"];
pub const AUDIOS: [&str; 8] = ["mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac"];

pub fn es_video(p: &Path) -> bool {
    p.extension().is_some_and(|e| VIDEOS.contains(&e.to_string_lossy().to_lowercase().as_str()))
}

/// Lo que está corriendo por proyecto («transcribir» o «exportar») y su último avance, para la interfaz.
static CORRIENDO: Mutex<Option<Map<String, Value>>> = Mutex::new(None);
static AVANCE: Mutex<Option<Map<String, Value>>> = Mutex::new(None);

fn con<T>(m: &Mutex<Option<Map<String, Value>>>, f: impl FnOnce(&mut Map<String, Value>) -> T) -> T {
    let mut g = m.lock().unwrap_or_else(|e| e.into_inner());
    f(g.get_or_insert_with(Map::new))
}

/// {carpeta: {paso, texto?, pct?}} de lo que está corriendo (va en el estado).
pub fn avance() -> Value {
    Value::Object(con(&AVANCE, |a| a.clone()))
}

pub fn registrar(host: &Host) {
    host.registrar("elegirVideo", |_, h, _| elegir_video(h));
    host.registrar("soltarVideo", |d, h, _| soltar_video(h, &d));
    host.registrar("transcribir", |d, h, _| {
        if let Some(c) = proyecto(h, &d["carpeta"]) {
            transcribir(h, &c);
        }
    });
    host.registrar("exportar", |d, h, _| exportar(h, &d));
    host.registrar("elegirMusica", |d, h, _| elegir_musica(h, &d));
}

pub fn elegir_video(h: &Host) {
    let titulo = h.t("Elige el video que quieres editar");
    if let Some(u) = h.dialogo_archivos(Some(titulo), &VIDEOS, false, None).into_iter().next() {
        importar(h, &u);
    }
}

/// La interfaz solo sabe los nombres; las rutas las guardó el host al soltar (`soltado(nombre)`: nunca se arma una ruta con lo
/// que manda la página).
fn soltar_video(h: &Host, d: &Value) {
    let nombres = d["nombres"].as_array().cloned().unwrap_or_default();
    let elegido = nombres.iter().filter_map(Value::as_str).filter_map(|n| h.soltado(n)).find(|p| es_video(p));
    match elegido {
        Some(u) => importar(h, &u),
        None => avisar(h, "Suelta un video MP4, MOV o WebM."),
    }
}

/// Copia el video a ~/Corta/<fecha> <nombre>/ (bin/importar.py; el original nunca se toca) y, si ya hay transcriptor, lo transcribe.
pub fn importar(h: &Host, video: &Path) {
    if !es_video(video) || std::fs::File::open(video).is_err() {
        return avisar(h, "Elige un video MP4, MOV o WebM.");
    }
    avisar(h, "Trayendo tu video…");
    // Copiar un video grande puede tardar: sin tope mientras bin/importar.py late.
    let r = h.procesador.correr_json("importar.py", &[video.to_string_lossy().into_owned()], Opciones { latido: true, ..Default::default() });
    let (Some(carpeta), Some(p)) = (r["carpeta"].as_str().filter(|_| r["ok"] == Value::Bool(true)), r.get("proyecto")) else {
        return avisar(h, r["error"].as_str().filter(|e| !e.is_empty()).unwrap_or("No pude traer ese video."));
    };
    responder(h, "proyectoActualizado", json!({"carpeta": carpeta, "proyecto": p, "seleccionar": true}));
    if crate::modelos::hay_alguno(h) {
        transcribir(h, carpeta);
    }
}

fn transcribir(h: &Host, carpeta: &str) {
    if con(&CORRIENDO, |c| c.contains_key(carpeta)) {
        return;
    }
    if !crate::modelos::hay_alguno(h) {
        return avisar(h, "Primero descarga el transcriptor en Ajustes.");
    }
    let sigue = empezar(h, carpeta, "transcribir", json!({"paso": "audio", "texto": h.t("Preparando el audio…")}));
    let r = h.procesador.correr_json("importar.py", &["transcribir".into(), carpeta.into()], Opciones { latido: true, ..Default::default() });
    terminar(h, carpeta, &sigue);
    match r.get("proyecto").filter(|_| r["ok"] == Value::Bool(true)) {
        Some(p) => {
            let n = entero(&r["corregidas"]).unwrap_or(0);
            let aviso = if n > 0 { h.f("Transcripción lista. Corregí {n} palabras con tu vocabulario.", &json!({"n": n.to_string()})) } else { h.t("Transcripción lista") };
            responder(h, "proyectoActualizado", json!({"carpeta": carpeta, "proyecto": p, "aviso": aviso}));
        }
        None => avisar(h, r["error"].as_str().filter(|e| !e.is_empty()).unwrap_or("No pude transcribir.")),
    }
}

fn exportar(h: &Host, d: &Value) {
    let Some(carpeta) = proyecto(h, &d["carpeta"]) else {
        return responder(h, "exportado", json!({"ok": false, "error": h.t("No encontré ese proyecto.")}));
    };
    if con(&CORRIENDO, |c| c.contains_key(&carpeta)) {
        return responder(h, "exportado", json!({"ok": false, "error": h.t("Espera a que termine lo que está haciendo este video.")}));
    }
    let sigue = empezar(h, &carpeta, "exportar", json!({"paso": "exportando", "pct": 0}));
    let r = h.procesador.correr_json("render.py", std::slice::from_ref(&carpeta), Opciones { latido: true, ..Default::default() });
    terminar(h, &carpeta, &sigue);
    responder(h, "exportado", con_error(h, r, "No pude exportar."));
}

/// Anota el trabajo y revisa su estado.json cada medio segundo hasta que `terminar` lo apague.
fn empezar(h: &Host, carpeta: &str, tipo: &str, inicial: Value) -> Arc<AtomicBool> {
    con(&CORRIENDO, |c| c.insert(carpeta.into(), json!(tipo)));
    let mut a = inicial;
    a["carpeta"] = json!(carpeta);
    con(&AVANCE, |m| m.insert(carpeta.into(), a.clone()));
    responder(h, "progreso", a);
    let sigue = Arc::new(AtomicBool::new(true));
    let (s, h2, c, t) = (sigue.clone(), h.clone(), carpeta.to_string(), tipo.to_string());
    std::thread::spawn(move || {
        let estado = PathBuf::from(&c).join("estado.json");
        while s.load(Ordering::SeqCst) {
            std::thread::sleep(Duration::from_millis(500));
            if !s.load(Ordering::SeqCst) {
                break;
            }
            let Some(e) = crate::pieza::enchufe::leer_json(&estado, 64 * 1024).filter(|e| e.as_object().is_some_and(|o| !o.is_empty())) else { continue };
            let Some(a) = leer_avance(&h2, &c, &t, &e) else { continue };
            if con(&AVANCE, |m| m.get(&c) == Some(&a)) {
                continue;
            }
            con(&AVANCE, |m| m.insert(c.clone(), a.clone()));
            // Exportando, solo se mueve la barra del diálogo (sin repintar todo); transcribiendo, la tarjeta «Preparando tu video».
            if t == "exportar" {
                responder(&h2, "exportarProgreso", json!({"carpeta": c, "pct": a.get("pct").cloned().unwrap_or(json!(0))}));
            } else {
                responder(&h2, "progreso", a);
            }
        }
    });
    sigue
}

/// {carpeta, paso, texto?, pct?} desde lo que dejó el script (el texto, traducido; el porcentaje, entre 0 y 100).
fn leer_avance(h: &Host, carpeta: &str, tipo: &str, e: &Value) -> Option<Value> {
    let mut a = json!({"carpeta": carpeta, "paso": e["paso"].as_str().unwrap_or(tipo)});
    if let Some(t) = e["texto"].as_str() {
        a["texto"] = json!(h.t(t));
    }
    if let Some(p) = e["pct"].as_f64().filter(|p| p.is_finite()) {
        a["pct"] = json!((p as i64).clamp(0, 100));
    }
    Some(a)
}

fn terminar(h: &Host, carpeta: &str, sigue: &AtomicBool) {
    sigue.store(false, Ordering::SeqCst);
    con(&CORRIENDO, |c| c.remove(carpeta));
    con(&AVANCE, |m| m.remove(carpeta));
    let _ = std::fs::remove_file(Path::new(carpeta).join("estado.json"));
    responder(h, "progreso", json!({"carpeta": carpeta, "listo": true}));
}

/// `{carpeta}` → el selector de audio y bin/musica.py (copia la canción a musica/ del proyecto), de a uno con los guardados.
fn elegir_musica(h: &Host, d: &Value) {
    let Some(carpeta) = proyecto(h, &d["carpeta"]) else { return responder(h, "musicaElegida", json!({"ok": false})) };
    let titulo = h.t("Elige la música de fondo");
    let Some(u) = h.dialogo_archivos(Some(titulo), &AUDIOS, false, None).into_iter().next() else {
        return responder(h, "musicaElegida", json!({"ok": false}));
    };
    let r = h.fila.agregar(|| h.procesador.correr_json("musica.py", &[carpeta, u.to_string_lossy().into_owned()], Opciones { limite: Some(600), ..Default::default() }));
    responder(h, "musicaElegida", con_error(h, r, "No pude usar esa música."));
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn solo_videos() {
        assert!(es_video(Path::new("/a/Mi Video.MOV")));
        assert!(es_video(Path::new("clip.webm")));
        assert!(!es_video(Path::new("foto.jpg")));
        assert!(!es_video(Path::new("sin_extension")));
    }
}
