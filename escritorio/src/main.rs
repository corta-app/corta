// Corta para Mac (y Windows y Linux cuando lleguen), sobre la pieza «host-tauri» (src/pieza/): la ventana con la interfaz de ui/,
// el puente con sus guardas (la ventana nunca sale de ui/ y un enlace https va al navegador), config e idioma desde app.json,
// menús en el idioma elegido, apariencia que sigue config.tema, los scripts de bin/ con límite de tiempo y las acciones declaradas
// en acciones.json (guardarProyecto, deshacer, limpiar, pedirIA, buscarShorts, crearShort, vocabulario y probarIA: solo corren un
// script, con sus datos validados). Los videos y proyectos viven en ~/Corta, fuera de la app: actualizar nunca borra nada.
//
// Aquí queda lo propio de Corta: traer un video (elegido o soltado), transcribir y exportar con su avance (videos.rs), los clips y
// fotos de una plantilla (plantillas.rs), los modelos de whisper (modelos.rs), el catálogo y los medios de la vista previa
// (medios.rs). Reemplaza a app/Sources/Corta (Swift).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod pieza;
#[path = "pieza/progreso.rs"]
mod progreso;
#[path = "pieza/catalogo.rs"]
mod catalogo;
#[path = "pieza/actualizaciones.rs"]
mod actualizaciones;
mod medios;
mod modelos;
mod plantillas;
mod videos;

use pieza::host::{arrancar, Host, ItemMenu, MenuPropio, Opciones, Ventana};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

/// ~/Corta: los videos y proyectos de la persona (la carpeta interna, ~/Corta/.corta, es `host.datos`).
pub fn base(h: &Host) -> PathBuf {
    h.datos.parent().map(PathBuf::from).unwrap_or_else(|| h.datos.clone())
}

/// La carpeta de un proyecto que manda la interfaz: una carpeta directa de ~/Corta con su proyecto.json (bin/proyecto.py
/// `carpeta_valida` la vuelve a revisar). La ruta real, o None.
pub fn proyecto_en(base: &Path, valor: &Value) -> Option<String> {
    let s = valor.as_str().filter(|s| Path::new(s).is_absolute() && !s.contains('\0'))?;
    let raiz = std::fs::canonicalize(base).ok()?;
    let real = std::fs::canonicalize(s).ok()?;
    let nombre = real.file_name()?.to_string_lossy().into_owned();
    (real.parent() == Some(raiz.as_path()) && !nombre.starts_with('.') && real.join("proyecto.json").is_file()).then(|| real.to_string_lossy().into_owned())
}

pub fn proyecto(h: &Host, valor: &Value) -> Option<String> {
    proyecto_en(&base(h), valor)
}

/// Un archivo dentro de ~/Corta (para «Mostrar en la carpeta»), o None.
pub fn dentro_en(base: &Path, valor: &Value) -> Option<PathBuf> {
    let s = valor.as_str().filter(|s| Path::new(s).is_absolute() && !s.contains('\0'))?;
    let raiz = std::fs::canonicalize(base).ok()?;
    let real = std::fs::canonicalize(s).ok()?;
    (real.starts_with(&raiz) && real != raiz).then_some(real)
}

/// Un número entero de verdad (no un booleano ni un texto; 2.0 cuenta como 2).
pub fn entero(v: &Value) -> Option<i64> {
    v.as_i64().or_else(|| v.as_f64().filter(|x| x.is_finite() && x.fract() == 0.0 && x.abs() < 1e12).map(|x| x as i64))
}

/// Un aviso que viaja con el próximo estado (lo muestra la interfaz).
static PENDIENTE: Mutex<Option<String>> = Mutex::new(None);

pub fn avisar(h: &Host, texto: &str) {
    if let Ok(mut g) = PENDIENTE.lock() {
        *g = Some(h.t(texto));
    }
    h.enviar_estado();
}

pub fn responder(h: &Host, funcion: &str, datos: Value) {
    h.llamar(funcion, datos, None);
}

/// Una respuesta de un script con su error traducido (o `por_defecto` si no trae uno).
pub fn con_error(h: &Host, r: Value, por_defecto: &str) -> Value {
    let mut x = r;
    if x["ok"] != Value::Bool(true) {
        let e = x["error"].as_str().filter(|e| !e.is_empty()).unwrap_or(por_defecto).to_string();
        x["error"] = json!(h.t(&e));
    }
    x
}

fn abrir_carpeta_datos(h: &Host) {
    let b = base(h);
    let _ = std::fs::create_dir_all(&b);
    let _ = opener::open(&b);
}

fn main() {
    let menu = MenuPropio {
        archivo: vec![
            ItemMenu::Nativo {
                etiqueta: "Nuevo video…".into(),
                atajo: Some("CmdOrCtrl+O".into()),
                f: Arc::new(|h: &Host| {
                    if h.idioma_elegido() {
                        h.mostrar();
                        videos::elegir_video(h);
                    }
                }),
            },
            ItemMenu::Nativo { etiqueta: "Abrir la carpeta de tus videos".into(), atajo: None, f: Arc::new(abrir_carpeta_datos) },
        ],
        ..Default::default()
    };
    let op = Opciones {
        // La interfaz llega hasta arriba (barra de título transparente; ui/app.css deja lugar a los botones de la ventana con
        // `html[data-host="mac"] .barra`) y una franja invisible de 12 px mueve la ventana. El tamaño se guarda con el nombre de
        // siempre («Corta»).
        ventana: Ventana { ancho: 1280.0, alto: 820.0, min_ancho: 900.0, min_alto: 600.0, barra_transparente: true, alto_franja: 12.0, nombre: "Corta".into(), ..Default::default() },
        global: Some("Corta".into()),
        sitio: Some("https://corta-app.github.io/corta/".into()),
        codigo: Some("https://github.com/corta-app/corta".into()),
        menu,
        // Soltar un video en la ventana: el host guarda las rutas y la interfaz recibe solo los nombres (`soltados`).
        soltar: true,
        lector_progreso: Some(Arc::new(progreso::Lector)),
        // Pieza «actualizaciones»: solo los Releases de corta-app/corta (Corta-macOS.zip + .sha256); nunca con un script
        // corriendo (exportar, transcribir): el host espera.
        actualizaciones: actualizaciones::Actualizaciones::nuevas("corta-app/corta", "Corta").ok().map(|a| Arc::new(a) as _),
        ..Default::default()
    };
    arrancar(tauri::generate_context!(), op, |host| {
        // Lo de bin/estado.py (proyectos, estilos, config, vocabulario, efectos, plantillas e IA instaladas) + lo propio de la app:
        // modelos de whisper, la carpeta y el avance de lo que está corriendo.
        host.al_estado(|mut e, h| {
            e.insert("modelos".into(), modelos::para_js(h));
            let b = base(h).to_string_lossy().into_owned();
            let casa = pieza::enchufe::casa().to_string_lossy().into_owned();
            e.insert("carpeta".into(), json!(b.strip_prefix(&casa).map(|r| format!("~{r}")).unwrap_or(b)));
            e.insert("progreso".into(), videos::avance());
            for k in ["proyectos", "ias"] {
                e.entry(k).or_insert_with(|| json!([]));
            }
            if let Some(a) = PENDIENTE.lock().ok().and_then(|mut g| g.take()) {
                e.insert("aviso".into(), json!(a));
            }
            e
        });
        // La carpeta de un proyecto que manda la interfaz se revisa antes de correr cualquier script declarado.
        host.inyector("proyecto", |e, h| match proyecto(h, e.get("carpeta").unwrap_or(&Value::Null)) {
            Some(real) => pieza::host::Inyectado::Valor(json!(real)),
            None => h.falta("No encontré ese proyecto.", json!({})),
        });
        // `host.medio("video", "<carpeta>/<archivo>")`: solo el video, la música o los clips de un proyecto de ~/Corta.
        host.registrar_medios("video", |rel, h| medios::archivo(&base(h), rel));

        videos::registrar(host);
        plantillas::registrar(host);
        modelos::registrar(host);
        host.registrar("abrirCarpeta", |d, h, _| match dentro_en(&base(h), &d["ruta"]) {
            Some(u) => {
                pieza::sistema::mostrar_en_carpeta(&u);
            }
            None => abrir_carpeta_datos(h),
        });

        // Pieza «catálogo»: efectos y plantillas de la comunidad (repo y tipos de app.json; solo de
        // raw.githubusercontent.com/corta-app/corta-catalogo, sin redirecciones, con tamaño y SHA-256).
        match catalogo::Catalogo::nuevo(&host.app.crudo, &format!("Corta/{}", host.app.version())) {
            Ok(cat) => {
                let cat = Arc::new(cat);
                let c = cat.clone();
                host.registrar("catalogoEfectos", move |_, h, _| responder(h, "catalogoListo", c.listar(h, "efectos")));
                let c = cat.clone();
                host.registrar("descargarEfecto", move |d, h, _| {
                    let id: String = d["id"].as_str().unwrap_or("").chars().take(60).collect();
                    responder(h, "efectoDescargado", c.descargar(h, "efectos", &id));
                });
                // Plantillas (y el índice de efectos, para ofrecer los que una plantilla usa y la persona no tiene).
                let c = cat.clone();
                host.registrar("catalogoPlantillas", move |_, h, _| {
                    let mut r = c.listar(h, "plantillas");
                    if r["ok"] == Value::Bool(true) {
                        let e = c.listar(h, "efectos");
                        r["efectos"] = e.get("efectos").cloned().unwrap_or_else(|| json!([]));
                    }
                    responder(h, "catalogoPlantillasListo", r);
                });
                host.registrar("descargarPlantilla", move |d, h, _| {
                    let id: String = d["id"].as_str().unwrap_or("").chars().take(60).collect();
                    responder(h, "plantillaDescargada", cat.descargar(h, "plantillas", &id));
                });
            }
            Err(e) => eprintln!("Corta: catálogo: {e}"),
        }
    });
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn solo_proyectos_de_corta() {
        let b = std::env::temp_dir().join(format!("corta-base-{}", pieza::enchufe::aleatorio_hex(4)));
        std::fs::create_dir_all(b.join("2026-11-08 Ana")).unwrap();
        std::fs::write(b.join("2026-11-08 Ana/proyecto.json"), "{}").unwrap();
        std::fs::create_dir_all(b.join("sin proyecto")).unwrap();
        std::fs::create_dir_all(b.join(".corta")).unwrap();
        std::fs::write(b.join(".corta/proyecto.json"), "{}").unwrap();
        let p = |s: &str| proyecto_en(&b, &json!(b.join(s).to_string_lossy()));
        assert!(p("2026-11-08 Ana").is_some());
        assert!(p("2026-11-08 Ana/../2026-11-08 Ana").is_some());
        assert!(p("sin proyecto").is_none());
        assert!(p(".corta").is_none());
        assert!(proyecto_en(&b, &json!("2026-11-08 Ana")).is_none(), "relativa");
        assert!(proyecto_en(&b, &json!(3)).is_none());
        assert!(proyecto_en(&b, &json!("/etc")).is_none());
        assert!(dentro_en(&b, &json!(b.join("2026-11-08 Ana/proyecto.json").to_string_lossy())).is_some());
        assert!(dentro_en(&b, &json!("/etc/hosts")).is_none());
        assert!(dentro_en(&b, &json!(b.to_string_lossy())).is_none());
        std::fs::remove_dir_all(b).unwrap();
    }

    #[test]
    fn enteros() {
        assert_eq!(entero(&json!(3)), Some(3));
        assert_eq!(entero(&json!(2.0)), Some(2));
        assert_eq!(entero(&json!(2.5)), None);
        assert_eq!(entero(&json!(true)), None);
        assert_eq!(entero(&json!("3")), None);
    }
}
