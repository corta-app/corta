//! Los modelos de transcripción (whisper.cpp): se descargan de huggingface.co/ggerganov/whisper.cpp a ~/Corta/.corta/modelos y solo
//! quedan si su huella SHA-256 es la de aquí (los mismos de Graba y Minuta). Lo mismo que hacía `Modelos` en Servicios.swift.

use crate::pieza::host::Host;
use crate::responder;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

pub struct Modelo {
    pub id: &'static str,
    pub nombre: &'static str,
    /// El nombre que usa la pieza «transcribir» (bin/transcribir.py, MODELOS).
    pub archivo: &'static str,
    pub bytes: u64,
    pub sha256: &'static str,
    pub detalle: &'static str,
}

/// Nombre y detalle se traducen en la interfaz.
pub const LISTA: [Modelo; 2] = [
    Modelo {
        id: "turbo",
        nombre: "Preciso",
        archivo: "ggml-large-v3-turbo-q5_0.bin",
        bytes: 574_041_195,
        sha256: "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2",
        detalle: "Mejor para cualquier idioma. 574 MB.",
    },
    Modelo {
        id: "small",
        nombre: "Rápido",
        archivo: "ggml-small-q5_1.bin",
        bytes: 190_085_487,
        sha256: "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
        detalle: "Más liviano, un poco menos preciso. 190 MB.",
    },
];

const DESDE: &str = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/";

static DESCARGANDO: AtomicBool = AtomicBool::new(false);

pub fn carpeta(h: &Host) -> PathBuf {
    h.datos.join("modelos")
}

pub fn existe(h: &Host, m: &Modelo) -> bool {
    std::fs::metadata(carpeta(h).join(m.archivo)).map(|x| x.len() == m.bytes).unwrap_or(false)
}

pub fn hay_alguno(h: &Host) -> bool {
    LISTA.iter().any(|m| existe(h, m))
}

/// La memoria del computador en bytes (0 si no se sabe).
fn memoria() -> u64 {
    #[cfg(target_os = "macos")]
    {
        if let Ok(s) = std::process::Command::new("/usr/sbin/sysctl").args(["-n", "hw.memsize"]).output() {
            return String::from_utf8_lossy(&s.stdout).trim().parse().unwrap_or(0);
        }
    }
    #[cfg(target_os = "linux")]
    {
        if let Ok(s) = std::fs::read_to_string("/proc/meminfo") {
            if let Some(kb) = s.lines().find_map(|l| l.strip_prefix("MemTotal:")).and_then(|l| l.trim().trim_end_matches("kB").trim().parse::<u64>().ok()) {
                return kb * 1024;
            }
        }
    }
    0
}

/// Con 8 GB o más, el preciso; si no (o si no se sabe), el rápido.
pub fn recomendado() -> &'static str {
    if memoria() >= 8 << 30 {
        "turbo"
    } else {
        "small"
    }
}

pub fn para_js(h: &Host) -> Value {
    let lista: Vec<Value> = LISTA
        .iter()
        .map(|m| json!({"id": m.id, "nombre": m.nombre, "mb": m.bytes / 1_000_000, "detalle": m.detalle, "listo": existe(h, m)}))
        .collect();
    json!({"recomendado": recomendado(), "lista": lista})
}

pub fn registrar(host: &Host) {
    host.registrar("descargarModelo", |d, h, _| {
        let id = d["id"].as_str().unwrap_or("").to_string();
        let r = descargar(h, &id, &|pct| responder(h, "modeloProgreso", json!({"id": id, "pct": pct})));
        let (ok, error) = match r {
            Ok(()) => (true, String::new()),
            Err(e) => (false, h.t(e)),
        };
        if ok {
            h.config.guardar(&json!({"modelo": id}), false);
        }
        responder(h, "modeloListo", json!({"id": id, "ok": ok, "error": error}));
    });
}

fn descargar(h: &Host, id: &str, progreso: &dyn Fn(f64)) -> Result<(), &'static str> {
    let m = LISTA.iter().find(|m| m.id == id).ok_or("No pude descargar.")?;
    if existe(h, m) {
        return Ok(());
    }
    if DESCARGANDO.swap(true, Ordering::SeqCst) {
        return Err("Ya hay una descarga en curso.");
    }
    let r = bajar(&format!("{DESDE}{}", m.archivo), m, &carpeta(h), progreso);
    DESCARGANDO.store(false, Ordering::SeqCst);
    r
}

/// A un archivo temporal; solo queda en su lugar si el tamaño y la huella SHA-256 coinciden.
fn bajar(url: &str, m: &Modelo, carpeta: &Path, progreso: &dyn Fn(f64)) -> Result<(), &'static str> {
    std::fs::create_dir_all(carpeta).map_err(|_| "No pude guardar la descarga.")?;
    let destino = carpeta.join(m.archivo);
    let temporal = carpeta.join(format!("{}.descarga", m.archivo));
    // huggingface.co responde con una redirección a su CDN: se siguen, siempre por https, y lo que llega se revisa por huella.
    let agente = ureq::AgentBuilder::new().redirects(5).https_only(true).timeout_connect(Duration::from_secs(20)).timeout_read(Duration::from_secs(60)).build();
    let mut lector = agente.get(url).call().map_err(|_| "No pude descargar.")?.into_reader();
    let mut archivo = std::fs::File::create(&temporal).map_err(|_| "No pude guardar la descarga.")?;
    let mut huella = Sha256::new();
    let (mut total, mut ultimo) = (0u64, -1i64);
    let mut buf = vec![0u8; 256 * 1024];
    let resultado = loop {
        let n = match lector.read(&mut buf) {
            Ok(0) => break Ok(()),
            Ok(n) => n,
            Err(_) => break Err("No pude descargar."),
        };
        total += n as u64;
        if total > m.bytes {
            break Err("La descarga llegó dañada. Intenta de nuevo.");
        }
        if archivo.write_all(&buf[..n]).is_err() {
            break Err("No pude guardar la descarga.");
        }
        huella.update(&buf[..n]);
        // La interfaz se repinta con cada aviso: solo cuando cambia el porcentaje.
        let pct = (total * 100 / m.bytes) as i64;
        if pct != ultimo {
            ultimo = pct;
            progreso((total as f64 / m.bytes as f64).min(1.0));
        }
    };
    drop(archivo);
    let hex: String = huella.finalize().iter().map(|x| format!("{x:02x}")).collect();
    let resultado = resultado.and_then(|_| if total == m.bytes && hex == m.sha256 { Ok(()) } else { Err("La descarga llegó dañada. Intenta de nuevo.") });
    if resultado.is_err() {
        let _ = std::fs::remove_file(&temporal);
        return resultado;
    }
    let _ = std::fs::remove_file(&destino);
    std::fs::rename(&temporal, &destino).map_err(|_| "No pude guardar la descarga.")
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn lista_bien_armada() {
        for m in &LISTA {
            assert_eq!(m.sha256.len(), 64);
            assert!(m.sha256.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()));
            assert!(m.archivo.starts_with("ggml-") && m.archivo.ends_with(".bin"));
        }
        assert!(["turbo", "small"].contains(&recomendado()));
    }

    #[test]
    fn nombres_como_importar_py() {
        // La pieza «transcribir» busca los modelos con estos nombres.
        let py = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../bin/transcribir.py")).unwrap();
        for m in &LISTA {
            assert!(py.contains(m.archivo), "{} no está en bin/transcribir.py", m.archivo);
        }
    }
}
