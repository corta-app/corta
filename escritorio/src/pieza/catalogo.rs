// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.
//! Pieza «catálogo» (Mac, Windows y Linux, «host-tauri»). Equivale a `catalogo.js` y a `Catalogo.swift`.
//! Baja el índice y los archivos de un catálogo de la comunidad SOLO desde https://raw.githubusercontent.com/<repo>/<rama>/,
//! sin seguir redirecciones, con tamaño máximo (cortado al leer). El índice lo valida bin/catalogo.py (con el validador que
//! pone la app); cada archivo se busca solo en ese índice validado (nunca en lo que manda la interfaz) y se compara su tamaño y
//! su SHA-256 antes de que Python lo vuelva a validar y lo guarde en la carpeta de datos de la app.
//!
//!   let cat = Arc::new(catalogo::Catalogo::nuevo(&host.app.crudo, &format!("Ana/{}", host.version()))?);
//!   host.registrar("catalogo", move |d, h, ctx| h.llamar("catalogoListo", cat.listar(h, d["tipo"].as_str().unwrap_or("")), ctx.destino()));

use crate::pieza::host::Host;
use crate::pieza::procesador::Opciones;
use regex::Regex;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::io::Read;
use std::sync::Mutex;
use std::time::Duration;

pub const HOST: &str = "raw.githubusercontent.com";

/// Frases en español (claves de traducción): la interfaz las muestra con Tp(r.frase). Las mismas de bin/catalogo.py.
pub fn frase(codigo: &str) -> &'static str {
    match codigo {
        "sin_conexion" => "No pude conectarme. Revisa tu conexión.",
        "indice" => "No pude leer el catálogo.",
        "danado" => "Llegó dañado. Intenta de nuevo.",
        "no_esta" => "Ya no está en el catálogo. Vuelve a abrirlo.",
        _ => "Eso no es válido.",
    }
}
fn error(codigo: &str, extra: Value) -> Value {
    let codigo = if ["sin_conexion", "indice", "no_valido", "danado", "no_esta"].contains(&codigo) { codigo } else { "no_valido" };
    let mut r = json!({"ok": false, "codigo": codigo, "frase": frase(codigo), "error": frase(codigo)});
    if let (Some(o), Some(e)) = (r.as_object_mut(), extra.as_object()) {
        o.extend(e.clone());
    }
    r
}

fn rx(p: &str) -> Regex {
    Regex::new(p).expect("patrón")
}

pub struct Tipo {
    pub indice: String,
    pub max_bytes: u64,
    pub max_indice: u64,
    pub patron: Regex,
}

pub struct Catalogo {
    pub repo: String,
    pub rama: String,
    pub base: String,
    pub tipos: HashMap<String, Tipo>,
    agente: String,
    /// Lo último que validó Python por tipo: de aquí salen la ruta, el tamaño y la huella de cada descarga.
    indices: Mutex<HashMap<String, Vec<Value>>>,
}

fn entero(v: Option<&Value>, defecto: u64, tope: u64) -> u64 {
    v.and_then(Value::as_u64).filter(|x| *x > 0 && *x <= tope).unwrap_or(defecto)
}

impl Catalogo {
    /// La sección «catalogo» de app.json, validada igual que en bin/catalogo.py (config()).
    pub fn nuevo(app_json: &Value, agente: &str) -> Result<Self, String> {
        let c = app_json.get("catalogo").ok_or("app.json: falta «catalogo».")?;
        let repo = c.get("repo").and_then(Value::as_str).unwrap_or("");
        if !rx(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$").is_match(repo) {
            return Err("app.json: «catalogo.repo» debe ser «dueño/repo».".into());
        }
        let rama = c.get("rama").map(|v| v.as_str().unwrap_or("\0")).unwrap_or("main");
        if !rx(r"^[A-Za-z0-9._-]{1,60}$").is_match(rama) || rama.contains("..") {
            return Err("app.json: «catalogo.rama» no es válida.".into());
        }
        let mut tipos = HashMap::new();
        let vacio = Map::new();
        for (id, t) in c.get("tipos").and_then(Value::as_object).unwrap_or(&vacio) {
            if !rx(r"^[a-z][a-z0-9-]{0,30}$").is_match(id) || !t.is_object() {
                return Err(format!("app.json: tipo de catálogo raro «{id}»."));
            }
            let carpeta = t.get("carpeta").map(|v| v.as_str().unwrap_or("")).unwrap_or(id);
            if !rx(r"^[a-z][a-z0-9-]{0,30}$").is_match(carpeta) {
                return Err(format!("app.json: «catalogo.tipos.{id}.carpeta» no es válida."));
            }
            let indice = t.get("indice").map(|v| v.as_str().unwrap_or("").to_string()).unwrap_or(format!("{carpeta}/index.json"));
            if !rx(r"^(?:[a-z0-9-]+/)?[a-z0-9-]+\.json$").is_match(&indice) {
                return Err(format!("app.json: «catalogo.tipos.{id}.indice» no es válido."));
            }
            let ident = if t.get("mayusculas") == Some(&Value::Bool(true)) { "[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*" } else { "[a-z0-9]+(?:-[a-z0-9]+)*" };
            // <carpeta>/<categoria>/<id>.json, o <carpeta>/<id>.json con "categoria": false (un catálogo plano)
            let patron = if t.get("categoria") == Some(&Value::Bool(false)) {
                format!(r"^{carpeta}/{ident}\.json$")
            } else {
                format!(r"^{carpeta}/[a-z0-9]+(?:-[a-z0-9]+)*/{ident}\.json$")
            };
            tipos.insert(
                id.clone(),
                Tipo {
                    indice,
                    max_bytes: entero(t.get("max_bytes"), 100 * 1024, 5 * 1024 * 1024),
                    max_indice: entero(t.get("max_indice"), 1024 * 1024, 20 * 1024 * 1024),
                    patron: rx(&patron),
                },
            );
        }
        Ok(Catalogo {
            base: format!("https://{HOST}/{repo}/{rama}/"),
            repo: repo.into(),
            rama: rama.into(),
            tipos,
            agente: agente.into(),
            indices: Mutex::new(HashMap::new()),
        })
    }

    /// Pide `ruta`: los bytes solo si es un 200 del mismo dominio y sin redirecciones; Err(true) si pasa del máximo (llegó
    /// algo que no es lo del índice); Err(false) si no se pudo.
    fn pedir(&self, ruta: &str, maximo: u64) -> Result<Vec<u8>, bool> {
        let u = url::Url::parse(&format!("{}{ruta}", self.base)).map_err(|_| false)?;
        if u.scheme() != "https" || u.host_str() != Some(HOST) || !u.path().starts_with(&format!("/{}/{}/", self.repo, self.rama)) || u.query().is_some() || u.fragment().is_some() {
            return Err(false);
        }
        let agente = ureq::AgentBuilder::new().redirects(0).https_only(true).timeout_connect(Duration::from_secs(15)).timeout_read(Duration::from_secs(60)).build();
        let r = agente.get(u.as_str()).set("User-Agent", &self.agente).set("Cache-Control", "no-store").call().map_err(|_| false)?;
        if r.status() != 200 || url::Url::parse(r.get_url()).ok().and_then(|x| x.host_str().map(String::from)).as_deref() != Some(HOST) {
            return Err(false);
        }
        if r.header("content-length").and_then(|x| x.parse::<u64>().ok()).is_some_and(|n| n > maximo) {
            return Err(true);
        }
        // Se lee de a pedazos y se corta apenas pasa del máximo (un archivo enorme nunca llega entero a la memoria).
        let mut b = Vec::new();
        r.into_reader().take(maximo + 1).read_to_end(&mut b).map_err(|_| false)?;
        if b.len() as u64 > maximo {
            return Err(true);
        }
        Ok(b)
    }

    fn temporal(datos: &[u8]) -> Option<std::path::PathBuf> {
        let ruta = std::env::temp_dir().join(format!("pieza-catalogo-{}.json", crate::pieza::enchufe::aleatorio_hex(16)));
        let mut o = std::fs::OpenOptions::new();
        o.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            o.mode(0o600);
        }
        use std::io::Write;
        o.open(&ruta).ok()?.write_all(datos).ok()?;
        Some(ruta)
    }

    fn python(h: &Host, orden: &str, entrada: Value) -> Value {
        h.procesador.con_entrada("catalogo.py", &[orden.to_string()], entrada, Opciones { limite: Some(60), ..Default::default() })
    }

    /// El índice de un tipo, validado por Python: {ok, tipo, <tipo>: […]} o {ok: false, codigo, frase, error}. Sin conexión, la
    /// última lista validada (si hay) con `sin_conexion: true`, `fecha` y la frase: se ve, pero no se descarga.
    pub fn listar(&self, h: &Host, tipo: &str) -> Value {
        let Some(t) = self.tipos.get(tipo) else { return error("no_valido", json!({"tipo": tipo})) };
        let datos = match self.pedir(&t.indice, t.max_indice) {
            Ok(d) => d,
            Err(true) => return error("indice", json!({"tipo": tipo})),
            Err(false) => {
                let r = Self::python(h, "ultima", json!({"tipo": tipo}));
                if r.get("ok") == Some(&Value::Bool(true)) && r.get(tipo).and_then(Value::as_array).is_some_and(|l| !l.is_empty()) {
                    let mut r = r;
                    r["sin_conexion"] = json!(true);
                    r["codigo"] = json!("sin_conexion");
                    r["frase"] = json!(frase("sin_conexion"));
                    return r;
                }
                return error("sin_conexion", json!({"tipo": tipo}));
            }
        };
        let Some(archivo) = Self::temporal(&datos) else { return error("indice", json!({"tipo": tipo})) };
        let r = Self::python(h, "indice", json!({"tipo": tipo, "archivo": archivo.to_string_lossy()}));
        let _ = std::fs::remove_file(&archivo);
        match r.get(tipo).and_then(Value::as_array) {
            Some(l) if r.get("ok") == Some(&Value::Bool(true)) => {
                if let Ok(mut i) = self.indices.lock() {
                    i.insert(tipo.into(), l.clone());
                }
                r
            }
            _ => error("indice", json!({"tipo": tipo})),
        }
    }

    /// Descarga uno del índice validado, revisa tamaño y huella, y Python lo valida y lo guarda.
    pub fn descargar(&self, h: &Host, tipo: &str, id: &str) -> Value {
        let malo = |c: &str| error(c, json!({"tipo": tipo, "id": id}));
        let Some(t) = self.tipos.get(tipo) else { return malo("no_valido") };
        let e = self.indices.lock().ok().and_then(|i| i.get(tipo).and_then(|l| l.iter().find(|x| x.get("id").and_then(Value::as_str) == Some(id)).cloned()));
        let Some(e) = e else { return malo("no_esta") };
        let ruta = e.get("ruta").and_then(Value::as_str).unwrap_or("");
        let sha = e.get("sha256").and_then(Value::as_str).unwrap_or("");
        let tamano = e.get("tamano").and_then(Value::as_u64).unwrap_or(0);
        if !t.patron.is_match(ruta) || sha.len() != 64 || !sha.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()) || tamano == 0 || tamano > t.max_bytes {
            return malo("no_valido");
        }
        let datos = match self.pedir(ruta, tamano) {
            Ok(d) => d,
            Err(true) => return malo("danado"),
            Err(false) => return malo("sin_conexion"),
        };
        let huella: String = Sha256::digest(&datos).iter().map(|x| format!("{x:02x}")).collect();
        if datos.len() as u64 != tamano || huella != sha {
            return malo("danado");
        }
        let Some(archivo) = Self::temporal(&datos) else { return malo("no_valido") };
        let r = Self::python(h, "instalar", json!({"tipo": tipo, "archivo": archivo.to_string_lossy(), "id": id, "sha256": huella}));
        let _ = std::fs::remove_file(&archivo);
        if r.get("ok") == Some(&Value::Bool(true)) {
            r
        } else {
            malo(r.get("codigo").and_then(Value::as_str).unwrap_or("no_valido"))
        }
    }
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn config_como_python() {
        let a = json!({"catalogo": {"repo": "ana-app/ana-catalogo", "tipos": {"plantillas": {"max_bytes": 10}, "temas": {"categoria": false}}}});
        let c = Catalogo::nuevo(&a, "Ana/1").unwrap();
        assert_eq!(c.base, "https://raw.githubusercontent.com/ana-app/ana-catalogo/main/");
        assert!(c.tipos["plantillas"].patron.is_match("plantillas/cocina/sopa.json"));
        assert!(!c.tipos["plantillas"].patron.is_match("plantillas/../x.json"));
        assert!(c.tipos["temas"].patron.is_match("temas/oscuro.json"));
        assert_eq!(c.tipos["plantillas"].max_bytes, 10);
        assert!(Catalogo::nuevo(&json!({"catalogo": {"repo": "x"}}), "a").is_err());
        assert!(Catalogo::nuevo(&json!({"catalogo": {"repo": "a/b", "rama": "../x"}}), "a").is_err());
    }
}
