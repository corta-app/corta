import AppKit
import ImageIO
import PiezaActualizaciones
import PiezaCatalogo
import PiezaHost
import UniformTypeIdentifiers

/// Corta para Mac, sobre la pieza «host-mac» (target `PiezaHost`): la ventana con la interfaz de ui/, el puente con sus guardas
/// (solo el marco principal con un archivo de ui/; la ventana nunca sale de ui/ y un enlace https va al navegador), config e idioma
/// desde app.json, menús en el idioma elegido, apariencia que sigue config.tema, los scripts de bin/ con límite de tiempo y las
/// acciones declaradas en acciones.json (guardarProyecto, deshacer, limpiar, pedirIA, buscarShorts, crearShort, vocabulario y probarIA:
/// solo corren un script, con sus datos validados). Aquí queda lo propio de Corta: traer un video (elegido o soltado), transcribir y
/// exportar con su avance (estado.json), música, clips y fotos de una plantilla (HEIC → JPEG), el catálogo, los modelos de whisper y
/// `corta://video/…` para la vista previa. Los videos y proyectos viven en ~/Corta, fuera de la app: actualizar nunca borra nada.
@main
enum CortaApp {
    @MainActor static func main() {
        // La interfaz llega hasta arriba (barra de título transparente; ui/app.css deja lugar a los botones de la ventana con
        // `html[data-host="mac"] .barra`) y una franja invisible de 12 puntos mueve la ventana: lo hace el host (`barraTransparente`).
        Host.arrancar(.init(minAncho: 900, minAlto: 600, sitio: "https://corta-app.github.io/corta/", codigo: "https://github.com/corta-app/corta",
                            barraTransparente: true, altoFranja: 12)) { p in
            // ffmpeg, ffprobe y corta-transcribir vienen dentro de la app (Contents/MacOS, verificados por huella al empaquetar):
            // proyecto.programa() y la pieza «transcribir» los prefieren a los del sistema.
            Procesador.entornoApp[Host.prefijo + "PROGRAMAS"] = Rutas.programas.path
            // La vista previa reproduce sin esperar un clic (el video lo pide la persona al tocar ▶ o una palabra).
            p.alConfigurarWeb = { conf in conf.mediaTypesRequiringUserActionForPlayback = [] }
            // `corta://video/<carpeta>/<archivo>`: solo el video, la música o los clips de un proyecto de ~/Corta (Medios).
            p.registrarMedios("video") { ruta in Medios.archivo(ruta) }
            // La carpeta de un proyecto que manda la interfaz se revisa antes de correr cualquier script declarado: tiene que ser
            // una carpeta directa de ~/Corta con su proyecto.json (bin/proyecto.py `carpeta_valida` la vuelve a revisar).
            p.inyectores["proyecto"] = { e -> Any? in
                if let real = Rutas.proyecto(e["carpeta"]) { return real }
                return Puente.Falta("No encontré ese proyecto.")
            }
            p.estado = { base, listo in listo(Corta.estado(base)) }
            p.menus = { m in Corta.menus(m) }

            // Pieza «actualizaciones»: solo los Releases de corta-app/corta (Corta-macOS.zip + .sha256). Instalación de desarrollo:
            // build.sh deja la ruta del checkout en ~/Corta/.corta/desarrollo y empaquetar.sh escribe su avance en CORTA_PROGRESO.
            // El host atiende buscarActualizacion/actualizar (nunca con un script corriendo), revisa al abrir y cada 6 h (recién
            // con el idioma elegido) y suma `actualizacion` al estado.
            Actualizaciones.configurar(.init(repo: "corta-app/corta", nombre: "Corta",
                archivoDesarrollo: Host.datos.appendingPathComponent("desarrollo"), variableProgreso: Host.prefijo + "PROGRESO"))
            p.actualizaciones = .init(revisar: Actualizaciones.revisar, revisarCadaRato: Actualizaciones.revisarCadaRato,
                seguir: Actualizaciones.seguir, instalar: Actualizaciones.instalar, aviso: Actualizaciones.aviso,
                disponible: { Actualizaciones.disponible })

            // Pieza «catálogo»: repo y tipos (efectos y plantillas) salen de app.json; los scripts los corre el Procesador del host.
            Catalogo.configurar(appJSON: Host.recursos.appendingPathComponent("app.json"), agente: "Corta/\(Host.version)") { s, a, d, fin in
                Procesador.conEntrada(s, a, d, fin: fin)
            }
            p.registrar("catalogoEfectos") { _ in Catalogo.listar("efectos") { p.llamar("catalogoListo", $0) } }
            // El id solo se busca en el último índice validado; la respuesta trae el efecto en «efecto» o {codigo, frase}.
            p.registrar("descargarEfecto") { d in Catalogo.descargar("efectos", d["id"] as? String ?? "") { p.llamar("efectoDescargado", $0) } }
            // Plantillas de la comunidad (y el índice de efectos, para ofrecer los que una plantilla usa y la persona no tiene).
            p.registrar("catalogoPlantillas") { _ in
                Catalogo.listar("plantillas") { r in
                    guard r["ok"] as? Bool == true else { return p.llamar("catalogoPlantillasListo", r) }
                    Catalogo.listar("efectos") { e in
                        var x = r
                        x["efectos"] = e["efectos"] ?? [Any]()
                        p.llamar("catalogoPlantillasListo", x)
                    }
                }
            }
            p.registrar("descargarPlantilla") { d in Catalogo.descargar("plantillas", d["id"] as? String ?? "") { p.llamar("plantillaDescargada", $0) } }

            p.registrar("elegirVideo") { _ in Corta.elegirVideo() }
            p.registrar("soltarVideo") { d in Corta.soltarVideo(d) }
            p.registrar("transcribir") { d in if let c = Rutas.proyecto(d["carpeta"]) { Trabajos.transcribir(c) } }
            p.registrar("exportar") { d in Trabajos.exportar(d) }
            p.registrar("descargarModelo") { d in Corta.descargarModelo(d) }
            p.registrar("elegirMusica") { d in Corta.elegirMusica(d) }
            p.registrar("elegirClips") { d in Plantillas.elegirClips(d) }
            p.registrar("ajustarHueco") { d in Plantillas.ajustarHueco(d) }
            p.registrar("cambiarClip") { d in Plantillas.cambiarClip(d) }
            // «Mostrar en la carpeta» del video exportado; sin ruta (o una de afuera), la carpeta de tus videos.
            p.registrar("abrirCarpeta") { d in
                if let u = Rutas.dentro(d["ruta"]) { p.mostrarEnFinder(u) } else { Corta.abrirCarpetaDatos() }
            }
        }
    }
}

@MainActor
enum Corta {
    /// Un aviso que viaja con el próximo estado (como antes: `enviarEstado(aviso:)`).
    static var pendiente: [String: Any] = [:]

    static func avisar(_ texto: String) {
        pendiente["aviso"] = Idioma.t(texto)
        Puente.shared.enviarEstado()
    }

    /// Lo del host (bin/estado.py: proyectos, estilos, config, vocabulario, efectos, plantillas e IA instaladas; versión, idioma y
    /// actualización) + lo propio de la app de Mac: modelos de whisper, la carpeta y el avance de lo que está corriendo.
    static func estado(_ base: [String: Any]) -> [String: Any] {
        var e = base
        e["modelos"] = Modelos.paraJS
        e["carpeta"] = Rutas.base.path.replacingOccurrences(of: FileManager.default.homeDirectoryForCurrentUser.path, with: "~")
        e["progreso"] = Trabajos.avance
        if e["proyectos"] == nil { e["proyectos"] = [Any]() }
        if e["ias"] == nil { e["ias"] = [Any]() }
        e.merge(pendiente) { _, nuevo in nuevo }
        pendiente = [:]
        return e
    }

    /// Archivo (video nuevo, la carpeta de tus videos y «Cerrar ventana») y Edición; el de la app (Acerca de, Ajustes, Salir), Ventana
    /// y Ayuda los pone el host. Nada antes de elegir el idioma.
    static func menus(_ m: Menus) -> [NSMenuItem] {
        [
            m.archivo([
                m.nativo("Nuevo video…", "o") {
                    guard Idioma.elegido else { return }
                    Puente.shared.mostrar()
                    elegirVideo()
                },
                m.nativo("Abrir la carpeta de tus videos") { abrirCarpetaDatos() },
            ]),
            m.edicion(),
        ]
    }

    static func abrirCarpetaDatos() {
        try? FileManager.default.createDirectory(at: Rutas.base, withIntermediateDirectories: true)
        NSWorkspace.shared.open(Rutas.base)
    }

    static let videos = ["mp4", "mov", "m4v", "webm", "mkv"]
    static let audios = ["mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac"]
    /// Fotos que acepta una plantilla (las de iPhone, HEIC, se pasan a JPEG antes: ffmpeg no siempre las lee).
    static let fotos = ["jpg", "jpeg", "png", "webp", "heic", "heif"]

    // MARK: Video nuevo (elegido, soltado o desde el menú)

    static func elegirVideo() {
        guard let v = Puente.shared.ventana else { return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .mpeg4Movie, .quickTimeMovie] + videos.compactMap { UTType(filenameExtension: $0) }
        panel.message = Idioma.t("Elige el video que quieres editar")
        panel.beginSheetModal(for: v) { r in
            guard r == .OK, let u = panel.url else { return }
            Task { @MainActor in importar(u) }
        }
    }

    /// La interfaz solo sabe los nombres; las rutas las guardó el host al soltar (`soltado(nombre)`: nunca se arma una ruta con lo
    /// que manda la web).
    static func soltarVideo(_ d: [String: Any]) {
        let nombres = d["nombres"] as? [String] ?? []
        guard let u = nombres.lazy.compactMap({ Puente.shared.soltado($0) }).first(where: { videos.contains($0.pathExtension.lowercased()) }) else {
            return avisar("Suelta un video MP4, MOV o WebM.")
        }
        importar(u)
    }

    /// Copia el video a ~/Corta/<fecha> <nombre>/ (bin/importar.py; el original nunca se toca) y, si ya hay transcriptor, lo transcribe.
    static func importar(_ video: URL) {
        guard videos.contains(video.pathExtension.lowercased()) || UTType(filenameExtension: video.pathExtension)?.conforms(to: .movie) == true,
              FileManager.default.isReadableFile(atPath: video.path) else { return avisar("Elige un video MP4, MOV o WebM.") }
        avisar("Trayendo tu video…")
        // Copiar un video grande puede tardar: sin tope mientras bin/importar.py late (pieza «trabajos»).
        Procesador.correrJSON("importar.py", [video.standardizedFileURL.path], latido: true) { r in
            guard r["ok"] as? Bool == true, let carpeta = r["carpeta"] as? String, let p = r["proyecto"] else {
                return avisar(r["error"] as? String ?? "No pude traer ese video.")
            }
            Puente.shared.llamar("proyectoActualizado", ["carpeta": carpeta, "proyecto": p, "seleccionar": true])
            if Modelos.hayAlguno { Trabajos.transcribir(carpeta) }
        }
    }

    // MARK: Modelos de whisper y música

    static func descargarModelo(_ d: [String: Any]) {
        let id = d["id"] as? String ?? ""
        Modelos.descargar(id, progreso: { Puente.shared.llamar("modeloProgreso", ["id": id, "pct": $0]) }) { ok, error in
            if ok { Config.guardar(["modelo": id], desdeInterfaz: false) }
            Puente.shared.llamar("modeloListo", ["id": id, "ok": ok, "error": error ?? ""])
        }
    }

    /// `{carpeta}` → el selector de audio y bin/musica.py (copia la canción a musica/ del proyecto), de a uno con los guardados.
    static func elegirMusica(_ d: [String: Any]) {
        guard let carpeta = Rutas.proyecto(d["carpeta"]), let v = Puente.shared.ventana else { return Puente.shared.llamar("musicaElegida", ["ok": false]) }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.audio] + audios.compactMap { UTType(filenameExtension: $0) }
        panel.message = Idioma.t("Elige la música de fondo")
        panel.beginSheetModal(for: v) { r in
            Task { @MainActor in
                guard r == .OK, let u = panel.url else { return Puente.shared.llamar("musicaElegida", ["ok": false]) }
                Fila.agregar { listo in
                    Procesador.correrJSON("musica.py", [carpeta, u.standardizedFileURL.path], limite: 600) { r in
                        var x = r
                        if r["ok"] as? Bool != true { x["error"] = Idioma.t(r["error"] as? String ?? "No pude usar esa música.") }
                        Puente.shared.llamar("musicaElegida", x)
                        listo()
                    }
                }
            }
        }
    }
}

// MARK: - Trabajos largos (transcribir y exportar): el avance lo deja bin/ en <carpeta>/estado.json

/// Lo que está corriendo por proyecto («transcribir» o «exportar») y su último avance, para la interfaz. Los scripts no tienen tope
/// de tiempo mientras laten (pieza «trabajos», `mantener_vivo`): si dejan de latir, el host los corta; al salir, también.
@MainActor
enum Trabajos {
    private static var corriendo: [String: String] = [:]
    private(set) static var avance: [String: [String: Any]] = [:]
    private static var reloj: Timer?

    static func transcribir(_ carpeta: String) {
        guard corriendo[carpeta] == nil else { return }
        guard Modelos.hayAlguno else { return Corta.avisar("Primero descarga el transcriptor en Ajustes.") }
        empezar(carpeta, "transcribir", ["paso": "audio", "texto": Idioma.t("Preparando el audio…")])
        Procesador.correrJSON("importar.py", ["transcribir", carpeta], latido: true) { r in
            terminar(carpeta)
            if r["ok"] as? Bool == true, let p = r["proyecto"] {
                let n = Texto.entero(r["corregidas"]) ?? 0
                let aviso = n > 0 ? Idioma.f("Transcripción lista. Corregí {n} palabras con tu vocabulario.", ["n": String(n)])
                    : Idioma.t("Transcripción lista")
                Puente.shared.llamar("proyectoActualizado", ["carpeta": carpeta, "proyecto": p, "aviso": aviso])
            } else {
                Corta.avisar(r["error"] as? String ?? "No pude transcribir.")
            }
        }
    }

    static func exportar(_ d: [String: Any]) {
        let p = Puente.shared
        guard let carpeta = Rutas.proyecto(d["carpeta"]) else { return p.llamar("exportado", ["ok": false, "error": Idioma.t("No encontré ese proyecto.")]) }
        guard corriendo[carpeta] == nil else { return p.llamar("exportado", ["ok": false, "error": Idioma.t("Espera a que termine lo que está haciendo este video.")]) }
        empezar(carpeta, "exportar", ["paso": "exportando", "pct": 0])
        Procesador.correrJSON("render.py", [carpeta], latido: true) { r in
            terminar(carpeta)
            var x = r
            if r["ok"] as? Bool != true { x["error"] = Idioma.t(r["error"] as? String ?? "No pude exportar.") }
            p.llamar("exportado", x)
        }
    }

    private static func empezar(_ carpeta: String, _ tipo: String, _ inicial: [String: Any]) {
        corriendo[carpeta] = tipo
        let a = inicial.merging(["carpeta": carpeta]) { x, _ in x }
        avance[carpeta] = a
        Puente.shared.llamar("progreso", a)
        guard reloj == nil else { return }
        reloj = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
            Task { @MainActor in revisar() }
        }
    }

    private static func revisar() {
        for (carpeta, tipo) in corriendo {
            let e = Archivos.leerJSON(URL(fileURLWithPath: carpeta).appendingPathComponent("estado.json"), maximo: 64 * 1024)
            guard !e.isEmpty else { continue }
            var a: [String: Any] = ["carpeta": carpeta, "paso": e["paso"] as? String ?? tipo]
            if let t = e["texto"] as? String { a["texto"] = Idioma.t(t) }
            if let pct = (e["pct"] as? NSNumber)?.intValue { a["pct"] = max(0, min(100, pct)) }
            if NSDictionary(dictionary: a) == NSDictionary(dictionary: avance[carpeta] ?? [:]) { continue }
            avance[carpeta] = a
            // Exportando, solo se mueve la barra del diálogo (sin repintar todo); transcribiendo, la tarjeta «Preparando tu video».
            if tipo == "exportar" { Puente.shared.llamar("exportarProgreso", ["carpeta": carpeta, "pct": a["pct"] ?? 0]) } else { Puente.shared.llamar("progreso", a) }
        }
    }

    private static func terminar(_ carpeta: String) {
        corriendo.removeValue(forKey: carpeta)
        avance.removeValue(forKey: carpeta)
        try? FileManager.default.removeItem(at: URL(fileURLWithPath: carpeta).appendingPathComponent("estado.json"))
        Puente.shared.llamar("progreso", ["carpeta": carpeta, "listo": true])
        if corriendo.isEmpty { reloj?.invalidate(); reloj = nil }
    }
}

// MARK: - Plantillas: clips y fotos de la persona → bin/plantillas.py

@MainActor
enum Plantillas {
    private static func panel(multiple: Bool) -> NSOpenPanel {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = multiple
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .image] + (Corta.videos + Corta.fotos).compactMap { UTType(filenameExtension: $0) }
        return panel
    }

    /// Una plantilla: la persona elige sus clips o fotos (van a los huecos en orden de nombre) y bin/plantillas.py arma el video.
    static func elegirClips(_ d: [String: Any]) {
        let id = d["plantilla"] as? String ?? ""
        let n = max(1, min(20, Texto.entero(d["n"]) ?? 1))
        guard Texto.calza(id, "[a-z0-9][a-z0-9-]{0,38}[a-z0-9]"), let v = Puente.shared.ventana else {
            return Puente.shared.llamar("plantillaArmada", ["ok": false, "error": Idioma.t("No encontré esa plantilla.")])
        }
        let p = panel(multiple: true)
        p.message = Idioma.f("Elige {n} clips o fotos. Van en orden de nombre; después puedes cambiar cada uno.", ["n": String(n)])
        p.beginSheetModal(for: v) { r in
            Task { @MainActor in
                guard r == .OK, !p.urls.isEmpty else { return Puente.shared.llamar("plantillaArmada", ["ok": false]) }
                let urls = p.urls.sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
                armar(["accion": "crear", "plantilla": id, "idioma": Idioma.codigo], urls)
            }
        }
    }

    static func ajustarHueco(_ d: [String: Any]) {
        guard let carpeta = Rutas.proyecto(d["carpeta"]), let hueco = Texto.entero(d["hueco"]),
              let desde = (d["desde"] as? NSNumber)?.doubleValue, desde.isFinite, !Texto.esBool(d["desde"]) else {
            return Puente.shared.llamar("plantillaArmada", ["ok": false, "error": Idioma.t("Ese hueco no existe.")])
        }
        armar(["accion": "ajustar", "carpeta": carpeta, "hueco": hueco, "desde": desde], [])
    }

    static func cambiarClip(_ d: [String: Any]) {
        guard let carpeta = Rutas.proyecto(d["carpeta"]), let hueco = Texto.entero(d["hueco"]), let v = Puente.shared.ventana else {
            return Puente.shared.llamar("plantillaArmada", ["ok": false, "error": Idioma.t("Ese hueco no existe.")])
        }
        let p = panel(multiple: false)
        p.message = Idioma.t("Elige otro clip o foto para este hueco")
        p.beginSheetModal(for: v) { r in
            Task { @MainActor in
                guard r == .OK, let u = p.url else { return Puente.shared.llamar("plantillaArmada", ["ok": false]) }
                armar(["accion": "cambiar", "carpeta": carpeta, "hueco": hueco], [u])
            }
        }
    }

    /// Corre bin/plantillas.py (crear, ajustar o cambiar) con los archivos elegidos y responde `plantillaArmada`. Las fotos HEIC se
    /// pasan antes a JPEG en una carpeta temporal (se borra al terminar). Mientras arma, la app cuenta como ocupada.
    private static func armar(_ datos: [String: Any], _ urls: [URL]) {
        var x = datos
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("corta-clips-\(UUID().uuidString)")
        var rutas: [String] = []
        for u in urls.map(\.standardizedFileURL) {
            let ext = u.pathExtension.lowercased()
            if ext == "heic" || ext == "heif" {
                guard let jpg = aJPEG(u, en: tmp) else {
                    try? FileManager.default.removeItem(at: tmp)
                    return Puente.shared.llamar("plantillaArmada", ["ok": false, "error": Idioma.t("No pude leer esa foto.")])
                }
                rutas.append(jpg.path)
            } else {
                rutas.append(u.path)
            }
        }
        if x["accion"] as? String == "crear" { x["archivos"] = rutas } else if let r = rutas.first { x["archivo"] = r }
        let p = Puente.shared
        p.ocupar()
        Fila.agregar { listo in
            Procesador.conEntrada("plantillas.py", "entrada", x, latido: true) { r in
                try? FileManager.default.removeItem(at: tmp)
                p.soltar()
                var y = r
                if r["ok"] as? Bool != true { y["error"] = Idioma.t(r["error"] as? String ?? "No pude armar el video.") }
                p.llamar("plantillaArmada", y)
                listo()
            }
        }
    }

    /// Una foto HEIC/HEIF como JPEG (ImageIO, con su orientación aplicada), en `carpeta`.
    private static func aJPEG(_ u: URL, en carpeta: URL) -> URL? {
        try? FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let destino = carpeta.appendingPathComponent(u.deletingPathExtension().lastPathComponent + "-\(UUID().uuidString.prefix(6)).jpg")
        let opciones: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceCreateThumbnailWithTransform: true,
                                         kCGImageSourceThumbnailMaxPixelSize: 4096]
        guard let fuente = CGImageSourceCreateWithURL(u as CFURL, nil),
              let imagen = CGImageSourceCreateThumbnailAtIndex(fuente, 0, opciones as CFDictionary),
              let salida = CGImageDestinationCreateWithURL(destino as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(salida, imagen, [kCGImageDestinationLossyCompressionQuality: 0.92] as CFDictionary)
        return CGImageDestinationFinalize(salida) ? destino : nil
    }
}
