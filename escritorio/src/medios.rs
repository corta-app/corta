//! `host.medio("video", "<carpeta>/<archivo>")`: el video, la música y los clips de un proyecto, para la vista previa. Los rangos
//! (para adelantar) los sirve la pieza «host-tauri»; aquí se decide qué archivo se puede servir, y solo:
//!   · el video del proyecto (`fuente.archivo` de su proyecto.json) o un archivo de su carpeta `musica/` o `clips/` (los clips y
//!     fotos de una plantilla, para verlos al elegir qué parte va en cada hueco),
//!   · de una carpeta directa de ~/Corta con proyecto.json, y
//!   · sin enlaces simbólicos que lleven fuera de ~/Corta.
//! Todo lo demás (otra ruta, «..», ~/Corta/.corta, una carpeta que empieza con punto) no se sirve. Lo mismo que hacía Medios.swift.

use std::path::{Path, PathBuf};

pub fn archivo(base: &Path, rel: &str) -> Option<PathBuf> {
    let partes: Vec<&str> = rel.split('/').collect();
    let forma = partes.len() == 2 || (partes.len() == 3 && matches!(partes[1], "musica" | "clips"));
    if !forma || partes.iter().any(|p| p.is_empty() || *p == "." || *p == ".." || p.contains('\\') || p.contains('\0')) || partes[0].starts_with('.') {
        return None;
    }
    let raiz = std::fs::canonicalize(base).ok()?;
    let carpeta = std::fs::canonicalize(raiz.join(partes[0])).ok()?;
    if carpeta.parent() != Some(raiz.as_path()) {
        return None;
    }
    let p = crate::pieza::enchufe::leer_json(&carpeta.join("proyecto.json"), 64 * 1024 * 1024)?;
    let fuente = p.get("fuente")?.as_object()?;
    if partes.len() == 2 && fuente.get("archivo").and_then(|a| a.as_str()) != Some(partes[1]) {
        return None;
    }
    let mut ruta = carpeta.clone();
    for x in &partes[1..] {
        ruta.push(x);
    }
    let real = std::fs::canonicalize(&ruta).ok()?;
    (real.starts_with(&raiz) && real.is_file()).then_some(real)
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn solo_lo_de_cada_proyecto() {
        let b = std::env::temp_dir().join(format!("corta-medios-{}", crate::pieza::enchufe::aleatorio_hex(4)));
        let p = b.join("2026-11-08 Ana");
        std::fs::create_dir_all(p.join("musica")).unwrap();
        std::fs::create_dir_all(p.join("clips")).unwrap();
        std::fs::write(p.join("proyecto.json"), r#"{"fuente": {"archivo": "video.mp4"}}"#).unwrap();
        for a in ["video.mp4", "otro.mp4", "musica/fondo.mp3", "clips/clip-1.mp4"] {
            std::fs::write(p.join(a), b"x").unwrap();
        }
        std::fs::create_dir_all(b.join(".corta")).unwrap();
        std::fs::write(b.join(".corta/config.json"), "{}").unwrap();
        let a = |r: &str| archivo(&b, r);
        assert!(a("2026-11-08 Ana/video.mp4").is_some());
        assert!(a("2026-11-08 Ana/musica/fondo.mp3").is_some());
        assert!(a("2026-11-08 Ana/clips/clip-1.mp4").is_some());
        assert!(a("2026-11-08 Ana/otro.mp4").is_none(), "solo el video del proyecto");
        assert!(a("2026-11-08 Ana/proyecto.json").is_none());
        assert!(a("2026-11-08 Ana/musica").is_none());
        assert!(a("2026-11-08 Ana/../2026-11-08 Ana/video.mp4").is_none());
        assert!(a(".corta/config.json").is_none());
        assert!(a("2026-11-08 Ana/otra/fondo.mp3").is_none());
        #[cfg(unix)]
        {
            std::os::unix::fs::symlink("/etc/hosts", p.join("musica/afuera.mp3")).unwrap();
            assert!(a("2026-11-08 Ana/musica/afuera.mp3").is_none(), "un enlace que sale de ~/Corta");
        }
        std::fs::remove_dir_all(b).unwrap();
    }
}
